# Flat-Rate Pricing Feature Implementation

## Overview
This document describes the implementation of the flat-rate (lump-sum) pricing feature for contracts with multiple rental objects in the KManager application, as requested in issue #186.

## Problem Statement
Previously, contract totals were always calculated automatically from rental object line items using `sum(quantity * price)`. This didn't support "all-inclusive" or flat-rate contracts where a single lump-sum price overrides the detailed line item calculations.

## Solution
Added a toggle mechanism that allows contracts to switch between:
- **Auto Mode (Default)**: Total is calculated automatically from line items
- **Manual Mode**: Total is set manually as a flat-rate, independent of line items

## Implementation Details

### 1. Database Changes

#### New Fields on Vertrag Model
```python
auto_total = models.BooleanField(
    default=True,
    verbose_name="Automatische Gesamtberechnung",
    help_text="Wenn aktiviert, wird der Gesamtbetrag aus den Vertragszeilen berechnet..."
)

manual_net_total = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    null=True,
    blank=True,
    verbose_name="Manueller Netto-Gesamtpreis",
    help_text="Manueller Netto-Gesamtpreis (Pauschale)..."
)
```

#### Migration
- File: `vermietung/migrations/0023_add_flat_rate_fields.py`
- Adds both new fields with appropriate defaults
- Backwards compatible: existing contracts default to `auto_total=True`

### 2. Business Logic Changes

#### New Property: `effective_net_total`
```python
@property
def effective_net_total(self):
    """
    Get the effective net total for this contract.
    Returns manual_net_total if auto_total=False and manual_net_total is set,
    otherwise returns calculated total from line items.
    """
    if not self.auto_total and self.manual_net_total is not None:
        return self.manual_net_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return self.berechne_gesamtmiete()
```

#### Updated VAT Calculation Methods
Both `berechne_umsatzsteuer()` and `berechne_bruttobetrag()` now use `self.effective_net_total` instead of `self.berechne_gesamtmiete()`, ensuring VAT is always calculated on the correct base amount.

#### Validation
```python
def clean(self):
    # ... existing validation ...
    
    # Validate manual_net_total
    if self.manual_net_total is not None and self.manual_net_total < 0:
        raise ValidationError({
            'manual_net_total': 'Der manuelle Netto-Gesamtpreis darf nicht negativ sein.'
        })
```

### 3. Form Changes

#### Updated VertragForm Fields
Added `auto_total` and `manual_net_total` to the form with appropriate widgets:
- `auto_total`: Checkbox with Bootstrap styling
- `manual_net_total`: Number input, not required (can be null during negotiation)

### 4. UI Changes

#### Contract Form Template (form.html)

**Toggle Section:**
```html
<div class="form-check">
    {{ form.auto_total }}
    <label class="form-check-label" for="{{ form.auto_total.id_for_label }}">
        {{ form.auto_total.label }}
    </label>
</div>
```

**Auto Mode Section:**
Shows the read-only calculated total from line items with an informative badge.

**Manual Mode Section:**
Shows the editable manual net total field with a warning badge indicating it overrides line items.

**Calculation Display:**
Enhanced to show a badge indicating the source of the net amount ("Auto" or "Manuell").

#### JavaScript Functionality
```javascript
function toggleTotalMode() {
    const isAutoTotal = autoTotalCheckbox.checked;
    
    if (isAutoTotal) {
        autoTotalSection.style.display = '';
        manualTotalSection.style.display = 'none';
        updateGesamtmiete();
    } else {
        autoTotalSection.style.display = 'none';
        manualTotalSection.style.display = '';
        updateManualTotalCalculations();
    }
}
```

The JavaScript:
- Dynamically shows/hides relevant input sections based on mode
- Updates VAT calculations using the appropriate net amount source
- Recalculates on mode changes, line item changes, and VAT rate changes

#### Contract Detail Template (detail.html)

**Mode Display:**
```html
<div class="row mb-2">
    <div class="col-md-4 text-muted">Berechnungsmodus:</div>
    <div class="col-md-8">
        {% if vertrag.auto_total %}
            <span class="badge bg-success">Automatisch aus Positionen</span>
        {% else %}
            <span class="badge bg-warning text-dark">Manueller Pauschalpreis</span>
        {% endif %}
    </div>
</div>
```

**Additional Information in Manual Mode:**
- Shows the manual flat rate value
- Shows the line items sum for information (but clearly indicates it's not used)

### 5. Testing

#### Test Coverage (vermietung/test_vertrag_flat_rate.py)

14 comprehensive tests covering:

1. **Default Behavior**: `auto_total` defaults to `True`
2. **Auto Mode Calculation**: Total equals sum of line items
3. **Manual Mode with Flat Rate**: Total equals `manual_net_total`, not line sum
4. **Manual Mode with Null**: Falls back to line sum when `manual_net_total` is null
5. **VAT in Auto Mode**: VAT calculated on line items sum
6. **VAT in Manual Mode**: VAT calculated on `manual_net_total`
7. **Multiple Objects - Auto**: Sums all objects correctly
8. **Multiple Objects - Manual**: Flat rate overrides multi-object sum
9. **Negative Value Validation**: Rejects negative `manual_net_total`
10. **Zero Value**: Allows zero (e.g., free rental)
11. **Auto to Manual Switch**: Correctly switches calculation source
12. **Manual to Auto Switch**: Correctly switches calculation source
13. **Quantities in Auto Mode**: Calculates quantity × price correctly
14. **Line Items Preserved**: Line items remain stored/accessible in manual mode

**Test Results:**
```
Ran 14 tests in 4.392s
OK
```

All existing tests also pass:
- 6 VAT calculation tests: ✅ OK
- 9 VertragsObjekt tests: ✅ OK

### 6. Security and Code Quality

**Code Review:** ✅ Passed with no issues

**CodeQL Security Scan:** ✅ No security alerts found

## Usage Examples

### Auto Mode (Default)
1. Create/edit a contract
2. Keep "Automatisch aus Positionen berechnen" checked (default)
3. Add rental objects with prices and quantities
4. Total is automatically calculated: Σ(quantity × price)
5. VAT is calculated on the auto-calculated total

### Manual Mode (Flat Rate)
1. Create/edit a contract
2. Uncheck "Automatisch aus Positionen berechnen"
3. Enter manual flat rate in "Manueller Netto-Gesamtpreis (€)"
4. Add rental objects (stored for reference but don't affect total)
5. Total uses the manual flat rate
6. VAT is calculated on the manual flat rate

### Switching Modes
Contracts can be switched between modes at any time:
- Auto → Manual: Manual rate must be entered
- Manual → Auto: Switches back to automatic calculation

### During Negotiation
If contract amounts are not yet finalized:
- Use manual mode with `manual_net_total` left empty
- System will temporarily use line sum until manual rate is set

## Benefits

1. **Flexibility**: Supports both detailed pricing and flat-rate contracts
2. **Transparency**: Line items remain visible even in manual mode
3. **Correct VAT**: Always calculated on the effective net amount
4. **No Data Loss**: Master data prices remain unchanged
5. **Backward Compatible**: Existing contracts default to auto mode
6. **Clear UI**: Mode is clearly indicated with badges and sections

## Design Decisions

### Why Property Instead of Method?
`effective_net_total` is a property rather than a method to:
- Provide cleaner syntax (`vertrag.effective_net_total` vs `vertrag.get_effective_net_total()`)
- Make it clear it's a computed value, not a stored field
- Allow consistent access pattern with other calculated fields

### Why Nullable manual_net_total?
Per requirements, contracts may be created during negotiation before amounts are finalized. Allowing null prevents validation errors during this phase.

### Why Keep Line Items in Manual Mode?
Line items provide:
- Context for what's included in the flat rate
- Reference for future adjustments
- Audit trail of original pricing structure

## Files Modified

1. `vermietung/models.py` - Model fields, property, and validation
2. `vermietung/forms.py` - Form fields and configuration
3. `vermietung/migrations/0023_add_flat_rate_fields.py` - Database migration
4. `templates/vermietung/vertraege/form.html` - Form UI and JavaScript
5. `templates/vermietung/vertraege/detail.html` - Detail view display
6. `vermietung/test_vertrag_flat_rate.py` - New comprehensive test suite

## Acceptance Criteria

All acceptance criteria from the issue have been met:

- ✅ Contract (multiple objects), Auto=Yes: Total = Sum(Lines × Quantity × Price)
- ✅ Contract, Auto=No and manual net set: Total = manual net exactly; lines don't influence
- ✅ Line prices remain visible/stored; rental object master data prices unchanged
- ✅ When VAT active: VAT/Gross calculated from effective net (Auto: Sum, Manual: manual value)
- ✅ UI shows toggle + input field and makes source of total recognizable

## Minimal Change Approach

This implementation follows the minimal change principle:
- Only added necessary fields and logic
- Reused existing calculation methods where possible
- Made minimal UI changes to existing templates
- All changes are additive (no breaking changes)
- Existing functionality remains unchanged (backward compatible)
