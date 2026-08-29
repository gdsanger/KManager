# DocumentCalculationService Implementation

## Overview

This document describes the implementation of the `DocumentCalculationService`, a central, deterministic service for calculating sales document totals (net, tax, gross) based on document lines.

## Implementation Summary

### Components Created

1. **Service**: `auftragsverwaltung/services/document_calculation.py`
   - `DocumentCalculationService` class
   - `TotalsResult` dataclass for return values

2. **Admin Integration**: `auftragsverwaltung/admin.py`
   - Added "Recalculate totals" action to `SalesDocumentAdmin`

3. **Tests**: 
   - `auftragsverwaltung/test_document_calculation.py` (10 tests)
   - `auftragsverwaltung/test_admin_calculation.py` (3 tests)

## Service API

### Method: `DocumentCalculationService.recalculate(document, persist=False)`

Calculates totals for a sales document based on its lines.

**Parameters:**
- `document`: SalesDocument instance
- `persist`: If `True`, saves calculated totals to database (default: `False`)

**Returns:**
- `TotalsResult` object with fields:
  - `total_net`: Total net amount (after discount)
  - `total_tax`: Total tax amount
  - `total_gross`: Total gross amount
  - `total_discount`: Total discount amount (sum of all line discount amounts)

**Example Usage:**

```python
from auftragsverwaltung.models import SalesDocument
from auftragsverwaltung.services import DocumentCalculationService

# Get a document
document = SalesDocument.objects.get(pk=1)

# Calculate without persisting (in-memory only)
result = DocumentCalculationService.recalculate(document)
print(f"Net: {result.total_net}, Tax: {result.total_tax}, Gross: {result.total_gross}")

# Calculate and persist to database
result = DocumentCalculationService.recalculate(document, persist=True)
```

## Business Logic

### Line Selection

The service determines which lines to include in the calculation based on `line_type`:

- **NORMAL**: Always included (regardless of `is_selected` value)
- **OPTIONAL**: Included only if `is_selected=True`
- **ALTERNATIVE**: Included only if `is_selected=True`

### Discount (Positionsrabatt)

`SalesDocumentLine.discount` is a percentage (0..100) and is deducted from the
line amount before tax is calculated:

- A line with `is_discountable=False` never carries a discount, regardless of
  the stored `discount` value (`DocumentCalculationService.effective_discount_percent()`
  is the single source of truth for calculation *and* display).
- Values outside 0..100 are rejected on input (model validation and the AJAX
  line endpoints); legacy values are clamped defensively during calculation.

### Calculation Process

1. **Line-Level Calculation** (for each line):
   ```
   line_subtotal = round(quantity × unit_price_net, 2 decimal places, HALF_UP)
   line_discount = round(line_subtotal × discount% ÷ 100, 2 decimal places, HALF_UP)
   line_net      = line_subtotal − line_discount
   line_tax      = round(line_net × tax_rate.rate, 2 decimal places, HALF_UP)
   line_gross    = line_net + line_tax
   ```
   The discount amount is rounded *before* it is deducted, so
   `line_subtotal = line_net + line_discount` holds cent-exactly.

2. **Document-Level Aggregation** (only included lines):
   ```
   total_net      = sum(all line_net values)
   total_tax      = sum(all line_tax values)
   total_gross    = sum(all line_gross values)
   total_discount = sum(all line discount amounts)
   ```
   `SalesDocument.total_net_before_discount` (= `total_net + total_discount`) is
   the Zwischensumme shown in the UI and on the PDF whenever a discount exists.

### Key Features

- **Deterministic**: Same inputs always produce same outputs
- **Decimal Precision**: Uses only `Decimal` arithmetic (no floats)
- **Rounding**: HALF_UP rounding to 2 decimal places at line level
- **UI-Independent**: Can be called from UI, background jobs, or tasks
- **No Model Side Effects**: No calculation logic in `Model.save()`

## Admin Integration

### Admin Action: "Recalculate totals"

The admin interface for `SalesDocument` includes a bulk action to recalculate totals.

**How to Use:**
1. Go to Django Admin → Auftragsverwaltung → Sales Documents
2. Select one or more documents
3. Choose "Recalculate totals" from the action dropdown
4. Click "Go"
5. Success/error messages will be displayed

**What it Does:**
- Calls `DocumentCalculationService.recalculate(document, persist=True)` for each selected document
- Updates `total_net`, `total_tax`, `total_gross` and `total_discount` fields in the database
- Provides feedback on success/failure

### Management Command: `recalculate_document_totals`

Recalculates line sums and document totals for all (or one Mandant's) sales
documents — needed after the discount became part of the calculation, because
documents saved before that still carry sums without any discount deducted.

```bash
python manage.py recalculate_document_totals --dry-run   # nur Bericht
python manage.py recalculate_document_totals             # schreibt
python manage.py recalculate_document_totals --company 1 # nur ein Mandant
```

## Testing

### Test Coverage

All tests pass successfully:

**Service Tests** (`test_document_calculation.py`):
1. Only NORMAL lines with same tax rate
2. Mixed line types (NORMAL, OPTIONAL, ALTERNATIVE)
3. Multiple tax rates in same document
4. Reproducibility
5. HALF_UP rounding behavior
6. `persist=True` saves to database
7. `persist=False` doesn't save to database
8. Empty document (no lines)
9. NORMAL lines always included
10. TotalsResult dataclass

**Admin Tests** (`test_admin_calculation.py`):
1. Admin action exists
2. Admin action calculates and persists single document
3. Admin action calculates and persists multiple documents

### Running Tests

```bash
# Run all document calculation tests
python manage.py test auftragsverwaltung.test_document_calculation

# Run admin action tests
python manage.py test auftragsverwaltung.test_admin_calculation

# Run all auftragsverwaltung tests
python manage.py test auftragsverwaltung
```

## Example Calculations

### Example 1: Simple Document

**Lines:**
- Line 1 (NORMAL): 2 × €100.00 @ 19% VAT
- Line 2 (NORMAL): 3 × €50.00 @ 19% VAT

**Calculation:**
```
Line 1: net = 200.00, tax = 38.00, gross = 238.00
Line 2: net = 150.00, tax = 28.50, gross = 178.50
Total:  net = 350.00, tax = 66.50, gross = 416.50
```

### Example 2: Mixed Types

**Lines:**
- Line 1 (NORMAL): 2 × €100.00 @ 19% VAT
- Line 2 (OPTIONAL, selected): 3 × €50.00 @ 7% VAT
- Line 3 (OPTIONAL, not selected): 1 × €999.00 @ 19% VAT

**Calculation:**
```
Line 1: net = 200.00, tax = 38.00, gross = 238.00
Line 2: net = 150.00, tax = 10.50, gross = 160.50
Line 3: NOT INCLUDED
Total:  net = 350.00, tax = 48.50, gross = 398.50
```

### Example 3: Rounding

**Line:**
- Quantity: 2.5
- Unit Price: €10.01
- Tax Rate: 19%

**Calculation:**
```
net = 2.5 × 10.01 = 25.025 → round(HALF_UP) = 25.03
tax = 25.03 × 0.19 = 4.7557 → round(HALF_UP) = 4.76
gross = 25.03 + 4.76 = 29.79
```

### Example 4: Discount

**Line:**
- Quantity: 2
- Unit Price: €45.00
- Discount: 50 %
- Tax Rate: 19%

**Calculation:**
```
subtotal = 2 × 45.00      = 90.00
discount = 90.00 × 50/100 = 45.00
net      = 90.00 − 45.00  = 45.00
tax      = 45.00 × 0.19   =  8.55
gross    = 45.00 + 8.55   = 53.55
```

## Security

No security vulnerabilities were found during CodeQL analysis.

## Acceptance Criteria

✅ Totals calculation is deterministic and reproducible  
✅ No calculation logic in `Model.save()` methods  
✅ Service is UI-independent  
✅ Admin provides manual trigger for recalculation  
✅ Decimal handling with 2 decimal places and HALF_UP rounding  
✅ Line selection logic correctly implemented  
✅ Multiple tax rates supported  
✅ Comprehensive tests (13 tests, all passing)  
✅ Code review completed (no issues)  
✅ Security check completed (no vulnerabilities)  

## Migration Path

The service is ready to use immediately:

1. **From UI**: Use the admin action "Recalculate totals"
2. **From Code**: Call `DocumentCalculationService.recalculate(document, persist=True)`
3. **From Jobs/Tasks**: Import and call the service as needed

No database migrations are required as the service uses existing fields.

## Future Enhancements (Out of Scope)

The following were explicitly marked as out of scope for this implementation:

- Automatic calculation on save (should remain opt-in via explicit service calls)
- UI workflows beyond the admin action
- ~~Discount handling~~ (nachgeliefert, siehe Abschnitt „Discount (Positionsrabatt)")
- Document-level tax adjustments
- Workflow/state machine integration

## Related Issues

- Lokales Item: /items/268/ (Auftragsverwaltung: Summenberechnung)
- Lokales Item: /items/266/ (Auftragsverwaltung: Dokumentpositionen / SalesDocumentLine)
- Lokales Item: /items/265/ (Grundmodell SalesDocument)
- Lokales Item: /items/261/ (Core: TaxRate als Entität)
- Lokales Item: /items/184/ (EPIC Auftragsverwaltung)
