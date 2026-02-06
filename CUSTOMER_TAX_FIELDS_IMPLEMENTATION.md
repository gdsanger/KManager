# Customer/Address Extension: Tax & Accounting Fields Implementation

## Overview
This implementation extends the Customer/Address (Adresse) model with tax and accounting-related fields to prepare for EU Reverse Charge and accounting integration.

## Changes Summary

### 1. Model Extension (core/models.py)
Added 5 new fields to the `Adresse` model:

- **vat_id** (CharField, max_length=32, optional)
  - Stores VAT identification number (Umsatzsteuer-Identifikationsnummer)
  - Automatically normalized to uppercase and trimmed
  - Example: `DE123456789`

- **country_code** (CharField, max_length=2, default='DE')
  - ISO 3166-1 Alpha-2 country code
  - Automatically normalized to uppercase and trimmed
  - Validated to be exactly 2 characters
  - Examples: `DE`, `AT`, `FR`

- **is_eu** (BooleanField, default=False)
  - Indicates if the customer is from the EU
  - Used for Reverse Charge handling

- **is_business** (BooleanField, default=True)
  - Distinguishes between business and private customers
  - Important for tax calculations

- **debitor_number** (CharField, max_length=32, optional)
  - Accounting debtor number
  - Optional field for accounting integration

### 2. Data Validation & Normalization
Implemented in model's `clean()` and `save()` methods:
- `country_code`: Trimmed, converted to uppercase, validated to be exactly 2 characters
- `vat_id`: Trimmed, converted to uppercase

### 3. Migration
Created `core/migrations/0017_add_tax_accounting_fields.py`:
- Adds all 5 new fields with proper defaults
- Backwards compatible - existing data remains valid
- Default values ensure no data migration needed

### 4. Form Updates (vermietung/forms.py)
Extended `AdresseKundeForm`:
- Added all new fields to the form
- Country code dropdown with common EU countries (DE, AT, CH, FR, IT, NL, BE, LU, PL, ES)
- Checkboxes for boolean fields (is_eu, is_business)
- Proper labels and help texts in German
- Validation integrated

### 5. User Interface Templates

#### Customer List (templates/vermietung/kunden/list.html)
Added columns:
- **Land**: Shows country code badge (e.g., `DE`) + EU badge if applicable
- **Typ**: Shows business/private badge
  - `Geschäft` (blue badge) for business customers
  - `Privat` (gray badge) for private customers

#### Customer Detail (templates/vermietung/kunden/detail.html)
Added new card section "Steuer & Buchhaltung" showing:
- Country code with badge styling
- VAT ID
- EU customer status (badge if EU)
- Customer type (business/private with badges)
- Debtor number

#### Customer Form (templates/vermietung/kunden/form.html)
Added new section "Steuer & Buchhaltung" with fields:
- Country code dropdown
- VAT ID input with placeholder
- EU customer checkbox
- Business customer checkbox
- Debtor number input
All with proper help texts

### 6. Admin Interface (core/admin.py)
Enhanced `AdressenAdmin`:
- Added `country_code`, `is_business`, `is_eu` to `list_display`
- Added `country_code`, `is_business`, `is_eu` to `list_filter`
- Added `vat_id` and `debitor_number` to `search_fields`
- New collapsible fieldset "Steuer & Buchhaltung"

### 7. Testing

#### New Test File: core/test_adresse_tax_fields.py
11 tests covering:
- Country code validation (uppercase, length, whitespace)
- VAT ID normalization (uppercase, whitespace)
- Optional fields (vat_id, debitor_number)
- Default values (is_eu=False, is_business=True, country_code='DE')
- All fields together integration test

#### Extended: vermietung/test_kunde_crud.py
Added 2 new tests:
- `test_form_with_tax_fields`: Validates form accepts and saves all tax fields
- `test_form_tax_fields_optional`: Validates tax fields are optional

**Test Results**: All 30 customer-related tests passing ✅

## Database Schema Changes

```python
# New fields added to core_adresse table
vat_id            VARCHAR(32)   NULL
country_code      VARCHAR(2)    DEFAULT 'DE'
is_eu             BOOLEAN       DEFAULT FALSE
is_business       BOOLEAN       DEFAULT TRUE
debitor_number    VARCHAR(32)   NULL
```

## Usage Examples

### Creating a Customer with Tax Fields
```python
kunde = Adresse.objects.create(
    adressen_type='KUNDE',
    firma='Test GmbH',
    name='Max Mustermann',
    strasse='Teststrasse 123',
    plz='12345',
    ort='Berlin',
    land='Deutschland',
    country_code='DE',
    vat_id='DE123456789',
    is_eu=True,
    is_business=True,
    debitor_number='DEB-2024-001'
)
```

### Field Normalization Example
```python
# Input
kunde.country_code = ' de '
kunde.vat_id = ' de123456789 '

# After save
kunde.save()
# Output
kunde.country_code  # 'DE'
kunde.vat_id        # 'DE123456789'
```

## Acceptance Criteria Status

✅ Migration runs through, existing data remains valid  
✅ Customer User-UI (List/Detail/Form) shows new fields  
✅ country_code validated (2 characters, uppercase)  
✅ vat_id optional, normalized  
✅ debitor_number optional, editable and visible  
✅ Tests present (minimum model + view/form)  

## Security Considerations

- No sensitive data exposure - all fields are appropriate for customer records
- Proper validation prevents injection attacks
- No security vulnerabilities introduced (verified with code review)
- Database constraints ensure data integrity

## Performance Impact

- Minimal: Only 5 new fields added to existing model
- Default values prevent NULL checks overhead
- No additional database queries required
- Indexed fields if needed can be added later based on query patterns

## Future Enhancements (Not in Scope)

- VAT ID validation against VIES (EU VAT Information Exchange System)
- Automatic EU detection based on country code
- Integration with accounting systems using debitor_number
- Similar fields for Supplier (Lieferant) addresses
- Tax rate calculation based on country_code and is_business

## Files Changed

1. `core/models.py` - Model extension
2. `core/migrations/0017_add_tax_accounting_fields.py` - Migration
3. `core/admin.py` - Admin interface
4. `core/test_adresse_tax_fields.py` - New test file
5. `vermietung/forms.py` - Form updates
6. `vermietung/test_kunde_crud.py` - Extended tests
7. `templates/vermietung/kunden/list.html` - List view updates
8. `templates/vermietung/kunden/detail.html` - Detail view updates
9. `templates/vermietung/kunden/form.html` - Form updates

## Migration Notes

1. Run migration: `python manage.py migrate core`
2. All existing addresses will get default values:
   - `country_code='DE'`
   - `is_eu=False`
   - `is_business=True`
   - `vat_id=NULL`
   - `debitor_number=NULL`
3. No data loss or manual data migration required

## Compatibility

- Django 5.2+
- Python 3.12+
- SQLite/PostgreSQL/MySQL
- Bootstrap 5 (for UI components)

---
**Implementation Date**: February 6, 2026  
**Issue**: #272 - Kunden (Adresse) erweitern: USt-/EU-Felder + Debitorennummer inkl. User-UI  
**PR**: copilot/extend-customer-address-fields
