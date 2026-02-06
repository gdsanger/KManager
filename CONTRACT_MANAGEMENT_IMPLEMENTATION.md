# Contract Management Implementation Summary

## Overview
This document summarizes the implementation of the contract management feature for recurring billing (Vertragsverwaltung für wiederkehrende Abrechnung) as specified in issue #277.

## Implementation Date
February 6, 2026

## Feature Description
The contract management system enables recurring invoices/payments for rentals, service contracts, maintenance, etc. Contracts periodically generate invoice drafts and maintain a traceable execution history.

## Components Implemented

### 1. Models

#### Contract Model (`auftragsverwaltung/models.py`)
Manages recurring billing contracts with the following key fields:
- **company**: FK to Mandant (required)
- **customer**: FK to Adresse (required)
- **document_type**: FK to DocumentType (required)
- **payment_term**: FK to PaymentTerm (optional)
- **name**: Contract name (string)
- **currency**: Currency code (default: 'EUR')
- **interval**: Billing interval (ENUM: MONTHLY, QUARTERLY, SEMI_ANNUAL, ANNUAL)
- **start_date**: Contract start date (required)
- **end_date**: Contract end date (optional, unbounded if null)
- **next_run_date**: Next execution date (required)
- **last_run_date**: Last execution date (optional)
- **is_active**: Active flag (boolean, default: True)
- **auto_finalize**: Auto-finalize flag (boolean, optional MVP feature)
- **auto_send**: Auto-send flag (boolean, optional MVP feature)
- **reference**: External reference (string, optional)

**Business Rules:**
- end_date (if set) must be >= start_date
- next_run_date must be >= start_date
- Contract is active only if is_active=True AND (no end_date OR today <= end_date)

**Key Methods:**
- `is_contract_active()`: Checks if contract is currently active
- `advance_next_run_date()`: Advances next_run_date based on interval

#### ContractLine Model (`auftragsverwaltung/models.py`)
Position templates for contracts with snapshot values:
- **contract**: FK to Contract (CASCADE)
- **item**: FK to Item (optional, PROTECT)
- **tax_rate**: FK to TaxRate (required, PROTECT)
- **cost_type_1**: FK to Kostenart (optional, PROTECT)
- **cost_type_2**: FK to Kostenart (optional, PROTECT)
- **position_no**: Position number (integer, unique per contract)
- **description**: Description (text)
- **quantity**: Quantity (decimal)
- **unit_price_net**: Net unit price (decimal, 2 places)
- **is_discountable**: Discountable flag (boolean, default: True)

**Constraints:**
- Unique constraint on (contract, position_no)

#### ContractRun Model (`auftragsverwaltung/models.py`)
Audit trail for contract executions:
- **contract**: FK to Contract (PROTECT)
- **document**: FK to SalesDocument (SET_NULL, optional)
- **run_date**: Execution date (date)
- **status**: Status (ENUM: SUCCESS, FAILED, SKIPPED)
- **message**: Status message (text, optional)
- **created_at**: Creation timestamp (auto)

**Constraints:**
- Unique constraint on (contract, run_date) - prevents duplicate runs

### 2. Service Layer

#### ContractBillingService (`auftragsverwaltung/services/contract_billing.py`)
Automated invoice generation service with the following methods:

**`generate_due(today=None)`**
- Finds all active contracts with next_run_date <= today
- Filters by is_contract_active() to check end_date
- Processes each contract and returns list of ContractRuns

**`_process_contract(contract, today)`**
- Checks for duplicate runs
- Generates invoice within transaction
- Updates contract dates (last_run_date, next_run_date)
- Handles exceptions and creates FAILED runs

**`_generate_invoice(contract)`**
- Creates SalesDocument in DRAFT status
- Sets issue_date = contract.next_run_date
- Creates payment_term snapshot
- Calculates due_date from payment_term
- Copies ContractLine → SalesDocumentLine
- Calls DocumentCalculationService to calculate totals
- Creates ContractRun with SUCCESS status

**Date Advancement Logic:**
- MONTHLY: +1 month
- QUARTERLY: +3 months
- SEMI_ANNUAL: +6 months
- ANNUAL: +1 year
- Uses `dateutil.relativedelta` for correct month/year arithmetic
- Handles missing days correctly (e.g., Jan 31 → Feb 28)

### 3. Django Admin

#### Contract Admin (`auftragsverwaltung/admin.py`)
- List display: name, company, customer, interval, dates, active status
- Filters: company, interval, is_active, dates
- Search: name, reference, company name, customer name
- Inline: ContractLine editing
- Custom method: `is_contract_active()` with boolean indicator

#### ContractLine Admin
- List display: contract, position_no, description, quantity, price, tax_rate
- Filters: company, is_discountable
- Search: contract name, description, item fields

#### ContractRun Admin
- List display: contract, run_date, status, document, created_at, message
- Filters: status, company, dates
- Search: contract name, document number, message
- Date hierarchy: run_date

### 4. Management Command

#### `generate_contract_invoices` (`auftragsverwaltung/management/commands/`)
Command-line tool for automated execution:

**Arguments:**
- `--date YYYY-MM-DD`: Custom reference date (default: today)
- `--dry-run`: Show what would be done without executing

**Output:**
- Success/failed/skipped counts
- Detailed status per contract
- Color-coded console output

**Usage:**
```bash
# Generate invoices for today
python manage.py generate_contract_invoices

# Generate invoices for specific date
python manage.py generate_contract_invoices --date 2026-02-01

# Dry-run to see what would happen
python manage.py generate_contract_invoices --dry-run
```

### 5. Database Migrations

#### Migration 0007 (`auftragsverwaltung/migrations/`)
- Creates Contract, ContractLine, ContractRun tables
- Adds indexes for performance:
  - (company, is_active) on Contract
  - (next_run_date) on Contract
  - (company, customer) on Contract
  - (contract, position_no) on ContractLine
  - (contract, run_date) on ContractRun
- Adds unique constraints:
  - (contract, position_no) on ContractLine
  - (contract, run_date) on ContractRun

### 6. Tests

#### Test Coverage (`auftragsverwaltung/test_contract.py`)
Comprehensive test suite with 20 tests covering:

**ContractModelTestCase (12 tests):**
- Basic contract creation
- end_date validation
- next_run_date validation
- is_contract_active() with various conditions
- Date advancement for all intervals (MONTHLY, QUARTERLY, SEMI_ANNUAL, ANNUAL)
- End-of-month handling (Jan 31 → Feb 28)

**ContractLineModelTestCase (2 tests):**
- Basic contract line creation
- Unique position_no constraint

**ContractRunModelTestCase (2 tests):**
- Basic contract run creation
- Unique (contract, run_date) constraint

**ContractBillingServiceTestCase (4 tests):**
- No contracts scenario
- Contract not yet due
- Inactive contract
- Successful invoice generation with full validation
- Duplicate run prevention

**Test Results:**
- All 109 tests in auftragsverwaltung pass
- 2 concurrency tests skipped (SQLite limitation)
- 0 failures
- 0 errors

## Integration Points

### DocumentCalculationService
- Used to calculate totals (net, tax, gross) for generated invoices
- Ensures consistent calculation logic across the system

### NumberRange (future integration)
- Invoice numbers currently empty ('') in generated documents
- Will be integrated with NumberRangeService in future implementation

### PaymentTerm
- Snapshots created at invoice generation time
- Due dates calculated using PaymentTerm.calculate_due_date()

## Code Quality

### Code Review
- ✅ No issues found
- ✅ All code follows project conventions
- ✅ Proper documentation and docstrings
- ✅ Type hints where appropriate

### Security Scan (CodeQL)
- ✅ No vulnerabilities detected
- ✅ No SQL injection risks
- ✅ No authentication/authorization issues

### Test Coverage
- ✅ 20 new tests added
- ✅ All critical paths covered
- ✅ Edge cases tested (end of month, validation, etc.)

## Files Changed

1. `auftragsverwaltung/models.py` - Added 3 new models
2. `auftragsverwaltung/admin.py` - Added admin classes for 3 models
3. `auftragsverwaltung/services/contract_billing.py` - New service (179 lines)
4. `auftragsverwaltung/management/commands/generate_contract_invoices.py` - New command (120 lines)
5. `auftragsverwaltung/migrations/0007_contract_contractline_contractrun_and_more.py` - New migration
6. `auftragsverwaltung/test_contract.py` - New test file (655 lines)
7. `core/migrations/0019_rename_core_item_article_idx_core_item_article_e3fd5c_idx_and_more.py` - Auto-generated index rename

## Acceptance Criteria Met

✅ **Verträge sind pro Company pflegbar (CRUD)**
- Full CRUD via Django admin with filters and search

✅ **Positionen pro Vertrag pflegbar**
- Inline editing in Contract admin
- Separate ContractLine admin for bulk operations

✅ **Run-Historie ist nachvollziehbar**
- ContractRun model with status, message, timestamps
- Linked to generated documents

✅ **Rechnungsentwürfe werden für fällige Verträge erzeugt**
- ContractBillingService.generate_due() creates draft invoices
- Management command for automated execution

✅ **next_run_date wird korrekt fortgeschrieben**
- Date advancement logic for all intervals
- Handles edge cases (end of month, leap years)

✅ **Keine Doppel-Runs pro Vertrag/Tag**
- Database constraint on (contract, run_date)
- Service checks for existing runs before processing

## Out of Scope (as specified)

The following were explicitly excluded from this implementation:
- ❌ Mahnwesen / Zahlungseingänge automatisiert (dunning/payment tracking)
- ❌ Teilabrechnungen / anteilige Perioden (partial billing)
- ❌ Dynamische Mengen / Indexmieten (dynamic quantities/index-based rent)
- ❌ Mehrere Dokumente pro Run (multiple documents per run)

## Future Enhancements

Potential improvements for future iterations:
1. Integration with NumberRangeService for automatic invoice numbering
2. Email notifications for generated invoices (if auto_send=True)
3. Automatic finalization of invoices (if auto_finalize=True)
4. Dashboard/reporting for contract overview
5. Bulk contract creation/import
6. Contract templates
7. Integration with accounting system

## Usage Example

```python
from django.utils import timezone
from datetime import date
from decimal import Decimal
from auftragsverwaltung.models import Contract, ContractLine
from auftragsverwaltung.services.contract_billing import ContractBillingService
from core.models import Mandant, Adresse, TaxRate

# Create a monthly service contract
contract = Contract.objects.create(
    company=my_company,
    customer=my_customer,
    document_type=invoice_type,
    payment_term=net_30,
    name="Monthly Office Rent",
    currency='EUR',
    interval='MONTHLY',
    start_date=date(2026, 1, 1),
    next_run_date=date(2026, 1, 1),
    is_active=True
)

# Add contract lines
ContractLine.objects.create(
    contract=contract,
    position_no=1,
    description="Office Space - 100 sqm",
    quantity=Decimal('1.0000'),
    unit_price_net=Decimal('1000.00'),
    tax_rate=vat_19,
    is_discountable=False
)

# Generate invoice manually
runs = ContractBillingService.generate_due(today=date(2026, 1, 1))

# Or use management command
# python manage.py generate_contract_invoices
```

## Deployment Notes

1. Run migrations: `python manage.py migrate`
2. Create initial document types if needed
3. Set up cron job or scheduled task for `generate_contract_invoices` command
4. Configure payment terms for contracts
5. Create contracts via admin interface

## Support and Documentation

- Model documentation in docstrings
- Service layer documented with examples
- Test cases serve as usage examples
- This summary document for overview

## Conclusion

The contract management feature has been successfully implemented with:
- ✅ All acceptance criteria met
- ✅ Comprehensive test coverage
- ✅ No code quality or security issues
- ✅ Clean, maintainable code following project conventions
- ✅ Ready for production deployment

The implementation provides a solid foundation for recurring billing that can be extended with additional features as needed.
