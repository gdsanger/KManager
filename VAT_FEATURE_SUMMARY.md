# VAT (Umsatzsteuer) Feature Implementation Summary

## Overview
This document describes the implementation of VAT (Umsatzsteuer/sales tax) support for rental contracts in the KManager application.

## Requirements
The issue requested:
1. A new selection field "Umsatzsteuer" with three options:
   - 0% Umsatzsteuer (steuerfrei / tax-free)
   - 7% Umsatzsteuer (Beherbergung / accommodation)
   - 19% Umsatzsteuer (Gewerbe / commercial)
2. Calculate VAT amount based on net amounts from rental objects (Mietobjekte)
3. Calculate and display gross amount (net + VAT)

## Implementation Details

### 1. Model Changes (`vermietung/models.py`)

#### Added VAT Rate Choices
```python
UMSATZSTEUER_SAETZE = [
    ('0', '0% Umsatzsteuer (steuerfrei)'),
    ('7', '7% Umsatzsteuer (Beherbergung)'),
    ('19', '19% Umsatzsteuer (Gewerbe)'),
]
```

#### Added Field to Vertrag Model
- **Field**: `umsatzsteuer_satz` (CharField, max_length=2)
- **Choices**: UMSATZSTEUER_SAETZE
- **Default**: '19' (19% commercial rate)
- **Location**: After `status` field in Vertrag model

#### Added Calculation Methods to Vertrag Model
1. **`berechne_umsatzsteuer()`**: Calculates VAT amount
   - Formula: (net amount × VAT rate) / 100
   - Returns: Decimal with 2 decimal places
   
2. **`berechne_bruttobetrag()`**: Calculates gross amount
   - Formula: net amount + VAT amount
   - Returns: Decimal with 2 decimal places

Both methods use the existing `berechne_gesamtmiete()` method to get the net amount from all VertragsObjekt items.

### 2. Form Changes (`vermietung/forms.py`)

#### Updated VertragForm
- Added `umsatzsteuer_satz` to fields list
- Added widget configuration for Bootstrap 5 select element
- Added label: "Umsatzsteuer *"
- Added help text explaining the purpose

### 3. Database Migration

**Migration**: `0014_add_umsatzsteuer_field.py`
- Adds `umsatzsteuer_satz` field to `vermietung_vertrag` table
- Default value: '19'
- No data migration needed (default applies to existing records)

### 4. Template Changes

#### Contract Form Template (`templates/vermietung/vertraege/form.html`)

**Changes in Financial Conditions Section**:
- Renamed "Gesamtmiete (€)" label to "Gesamtmiete (€) (Netto)"
- Added VAT rate selector field
- Added real-time calculation display card showing:
  - Net amount (Nettobetrag)
  - VAT amount with rate (Umsatzsteuer)
  - Gross amount (Bruttobetrag)
- Moved deposit field below calculation display

**JavaScript Updates**:
- Added `updateVATCalculations()` function
- Modified `updateGesamtmiete()` to call VAT calculations
- Added event listener for VAT rate change to update calculations in real-time

**Key Features**:
- Live updates when rental objects are added/removed
- Live updates when VAT rate changes
- Calculations update automatically on quantity/price changes

#### Contract Detail Template (`templates/vermietung/vertraege/detail.html`)

**Changes in Financial Conditions Section**:
- Shows "Monatliche Miete (Netto)" instead of just "Monatliche Miete"
- Displays selected VAT rate with description
- Shows calculated VAT amount in parentheses
- Shows "Monatliche Miete (Brutto)" as bold final amount
- Keeps deposit and other fields below

### 5. Tests

**New Test File**: `vermietung/test_vertrag_vat.py`

Contains comprehensive test suite with 6 tests (all passing):

1. **test_vat_calculation_19_percent**: Verifies 19% VAT calculation
   - Net: 1000.00 → VAT: 190.00 → Gross: 1190.00

2. **test_vat_calculation_7_percent**: Verifies 7% VAT calculation
   - Net: 1000.00 → VAT: 70.00 → Gross: 1070.00

3. **test_vat_calculation_0_percent**: Verifies tax-free calculation
   - Net: 1000.00 → VAT: 0.00 → Gross: 1000.00

4. **test_vat_calculation_multiple_objects**: Tests with multiple rental objects
   - Net: 2500.00 (1000 + 1500) → VAT: 475.00 → Gross: 2975.00

5. **test_vat_calculation_with_quantities**: Tests with quantity > 1
   - Net: 3000.00 (1000 × 3) → VAT: 570.00 → Gross: 3570.00

6. **test_default_vat_rate**: Verifies default rate is 19%

All tests verify:
- Correct net amount calculation from VertragsObjekt items
- Correct VAT amount calculation based on selected rate
- Correct gross amount calculation (net + VAT)
- Proper rounding to 2 decimal places

## Usage

### Creating/Editing a Contract

1. When creating or editing a contract, users will see the VAT rate selector in the "Finanzielle Konditionen" section
2. Select the appropriate VAT rate (0%, 7%, or 19%)
3. Add rental objects to the contract
4. The form automatically calculates and displays:
   - Net amount (sum of all rental objects)
   - VAT amount (based on selected rate)
   - Gross amount (total to be paid including VAT)
5. All amounts update in real-time as rental objects are added/removed or VAT rate changes

### Viewing Contract Details

1. Contract detail page shows:
   - Net monthly rent
   - Selected VAT rate with description
   - VAT amount
   - Gross monthly rent (highlighted)
2. All amounts are displayed with 2 decimal precision

## Technical Notes

1. **Net amounts**: All prices in VertragsObjekt (rental objects) are net amounts
2. **Calculation precision**: All calculations use Python's `Decimal` type with ROUND_HALF_UP rounding
3. **Default value**: New contracts default to 19% VAT (commercial rate)
4. **Backwards compatibility**: Existing contracts get 19% VAT rate when migrated
5. **Database**: Field is stored as CharField ('0', '7', '19') not as numeric to match choice values

## Future Considerations

1. The existing test suite (test_vertrag_crud.py) uses the deprecated single-mietobjekt approach and needs updating to work with the new formset-based contract form. This is beyond the scope of the minimal VAT feature addition.

2. Consider adding VAT information to:
   - Contract list view (showing gross amounts)
   - PDF export of contracts
   - Financial reports

3. Consider making VAT rate configurable per rental object instead of per contract, if different objects require different tax rates.

## Files Modified

1. `vermietung/models.py` - Added VAT field and calculation methods
2. `vermietung/forms.py` - Added VAT field to form
3. `vermietung/migrations/0014_add_umsatzsteuer_field.py` - Database migration
4. `templates/vermietung/vertraege/form.html` - Updated form UI with calculations
5. `templates/vermietung/vertraege/detail.html` - Updated detail view to show VAT
6. `vermietung/test_vertrag_vat.py` - New comprehensive test suite

## Validation

✅ All 6 new VAT tests pass
✅ Database migration runs successfully  
✅ Model calculations work correctly with various VAT rates
✅ UI displays calculations in real-time
✅ Form validation works (field is required)
✅ Default value (19%) applies correctly
