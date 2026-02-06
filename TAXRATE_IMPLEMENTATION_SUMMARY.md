# TaxRate Entity Implementation - Summary

## Overview
This document summarizes the implementation of the `core.TaxRate` entity as specified in issue #261.

## Implementation Date
2026-02-06

## Scope Completed
This implementation covers all requirements from issue #261:
- ✅ TaxRate model with data-driven management
- ✅ Case-insensitive unique constraint on code
- ✅ Rate validation (0 <= rate <= 1)
- ✅ Admin CRUD interface
- ✅ Delete protection (deactivation only via is_active)
- ✅ FK-ready for future models (Item, SalesDocumentLine)
- ✅ Comprehensive tests
- ✅ Security checks passed

## Files Changed/Added

### Models
- **core/models.py**: Added `TaxRate` model (lines 195-251)
  - Fields: `code`, `name`, `rate`, `is_active`
  - Case-insensitive unique constraint on `code`
  - Validation: `0 <= rate <= 1`
  - String representation with percentage formatting

### Migrations
- **core/migrations/0013_add_taxrate_model.py**: Database migration
  - Creates `core_taxrate` table
  - Adds unique constraint index: `taxrate_code_unique_case_insensitive`

### Admin Interface
- **core/admin.py**: Added `TaxRateAdmin` class (lines 123-155)
  - List display: code, name, rate_percentage, is_active
  - Search: code, name
  - Filter: is_active
  - Delete protection: `has_delete_permission()` returns False
  - Delete action removed from admin

### Tests
- **core/test_taxrate.py**: 15 tests for model functionality
  - Rate validation tests (negative, > 1, boundaries)
  - Case-insensitive uniqueness tests
  - CRUD operations
  - String representation
  - Ordering
  
- **core/test_taxrate_fk.py**: 2 tests for FK relationship capability
  - Validates TaxRate can be used as ForeignKey
  - Tests PROTECT on_delete behavior

### Documentation
- **docs/TAXRATE_FK_INTEGRATION.md**: Integration guide
  - Examples for adding TaxRate FK to models
  - Design patterns and best practices
  - Migration strategies
  - Admin integration examples

### Management Commands
- **core/management/commands/populate_taxrates.py**: Sample data command
  - Creates standard German tax rates (VAT 19%, 7%, 0%, Export)
  - Prevents duplicates (case-insensitive check)
  - Usage: `python manage.py populate_taxrates`

## Database Schema

### Table: core_taxrate
```sql
CREATE TABLE core_taxrate (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    rate DECIMAL(5, 4) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE UNIQUE INDEX taxrate_code_unique_case_insensitive 
ON core_taxrate (LOWER(code));
```

## Model API

### TaxRate Fields
```python
code        CharField(max_length=50, unique=True)
name        CharField(max_length=200)
rate        DecimalField(max_digits=5, decimal_places=4)
is_active   BooleanField(default=True)
```

### Validation Rules
1. **code**: Must be globally unique (case-insensitive)
2. **rate**: Must be between 0 and 1 (inclusive)
3. **Deletion**: Not allowed via admin; use `is_active=False` instead

### Methods
```python
def __str__(self):
    """Returns: 'CODE: Name (XX.XX%)'"""
    
def clean(self):
    """Validates rate is between 0 and 1"""
```

## Usage Examples

### Creating Tax Rates
```python
from core.models import TaxRate
from decimal import Decimal

# Create a tax rate
vat = TaxRate.objects.create(
    code='VAT19',
    name='Standard VAT',
    rate=Decimal('0.19')
)

# Query active tax rates
active_rates = TaxRate.objects.filter(is_active=True)

# Deactivate a tax rate (don't delete!)
vat.is_active = False
vat.save()
```

### Using as ForeignKey (Future Models)
```python
from core.models import TaxRate

class Item(models.Model):
    name = models.CharField(max_length=200)
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.PROTECT,  # Required!
        verbose_name="Steuersatz"
    )
```

## Testing

### Test Results
- **Total tests**: 17 (15 model + 2 FK)
- **Status**: ✅ All passing
- **Core regression tests**: 147 tests passing
- **Coverage**: Model validation, uniqueness, CRUD, FK relationships

### Running Tests
```bash
# TaxRate-specific tests
python manage.py test core.test_taxrate
python manage.py test core.test_taxrate_fk

# All core tests
python manage.py test core
```

## Security

### CodeQL Analysis
- **Status**: ✅ Passed
- **Alerts**: 0
- **Scan Date**: 2026-02-06

### Security Considerations
1. **Delete Protection**: TaxRates cannot be deleted if referenced by FK
2. **Validation**: Rate bounds enforced at model level
3. **Case-Insensitive Uniqueness**: Prevents duplicate codes with different cases
4. **Decimal Precision**: Uses Decimal type to avoid float precision issues

## Admin Interface Features

### List View
- Columns: Code, Name, Rate (%), Active
- Sortable by: Code (default), Name, Active status
- Filterable by: Active status
- Searchable by: Code, Name

### Edit/Create Form
- Fields: Code, Name, Rate, Active
- Validation: Real-time validation of rate bounds
- Help text: Guides users on proper values

### Delete Protection
- Delete button: Hidden
- Bulk delete action: Removed
- User message: "Deactivate via 'Active' field instead"

## Migration Path

### For Existing Projects
1. Apply migration: `python manage.py migrate core`
2. Populate initial data: `python manage.py populate_taxrates`
3. Review and adjust tax rates in admin

### For New Projects
1. Migration will be applied automatically
2. Optionally run `populate_taxrates` for sample data

## Future Work (Out of Scope)

The following items are NOT part of this implementation and will come in future issues:

1. **Item Model**: Creation with TaxRate FK
   - Status: Not implemented (model doesn't exist yet)
   - Future issue: TBD

2. **SalesDocumentLine Model**: Creation with TaxRate FK
   - Status: Not implemented (confirmed in issue description)
   - Future issue: Referenced in issue as "later issue"

3. **Kostenart Migration**: Converting from hardcoded rates to TaxRate FK
   - Status: Not implemented (out of scope per issue description)
   - Note: Kostenart still uses choice field for now

## Known Limitations

1. **Item & SalesDocumentLine**: Models don't exist yet
   - Documented in `docs/TAXRATE_FK_INTEGRATION.md`
   - FK field definitions ready for future implementation

2. **No UI outside Admin**: 
   - Only admin interface implemented
   - User-facing UI not in scope for this issue

## Acceptance Criteria Status

All acceptance criteria from issue #261 met:

- ✅ `core.TaxRate` exists with migration
- ✅ `code` is globally unique and case-insensitive
- ✅ `rate` is validated: `0 <= rate <= 1`
- ✅ Admin/UserUI provides CRUD for TaxRates
- ✅ List view shows: `code`, `name`, `rate`, `is_active`
- ✅ TaxRate can be used as FK in future models (ready and documented)
- ✅ Deletion of TaxRate is not possible; only deactivation via `is_active`
- ✅ Tests for uniqueness and rate validation are present and passing

## Developer Notes

### Design Decisions

1. **Decimal vs Float**: Used `DecimalField` for `rate` to avoid floating-point precision issues
2. **Delete Strategy**: PROTECT on FK relationships to prevent accidental data loss
3. **Case Sensitivity**: UniqueConstraint with Lower() function for database-agnostic case-insensitive uniqueness
4. **Rate Format**: Stored as decimal (0.19), displayed as percentage (19.00%)

### Best Practices Applied

1. **DRY Principle**: Centralized tax rate management
2. **Data Integrity**: Constraints at database level
3. **Validation**: Both at model and admin level
4. **Documentation**: Inline comments and separate docs
5. **Testing**: Comprehensive test coverage
6. **Security**: CodeQL scan passed

## Conclusion

The TaxRate entity implementation is complete and production-ready. All requirements from issue #261 have been met. The model is ready to be used as a ForeignKey in future models (Item, SalesDocumentLine) as documented.

## References

- Issue: #261 - Core: Steuersätze (TaxRate) als Entität
- Project: Domus - Immobilien, Besitz, Finanzen
- Type: Feature
- Implementation Date: 2026-02-06
