# Price per Square Meter (€/m²) Feature - Implementation Summary

## Overview
This feature adds an optional `price_per_sqm` field to rental objects (MietObjekt) that allows users to store and manage the price per square meter. When both `price_per_sqm` and area (`fläche`) are set, the system can automatically calculate the total rent with user confirmation.

## Implementation Details

### 1. Database Changes
- **New Field**: `price_per_sqm` in `MietObjekt` model
  - Type: `DecimalField(max_digits=10, decimal_places=2)`
  - Nullable: Yes (optional field)
  - Validation: Must be ≥ 0 (non-negative)
  - Migration: `0028_mietobjekt_price_per_sqm.py`

### 2. User Interface Changes

#### Form View (Create/Edit MietObjekt)
The "Preise & Kosten" section now includes the new field:

```
┌─────────────────────────────────────────────────────────────┐
│ Preise & Kosten                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐│
│ │ Mietpreis (€) * │ │ €/m²            │ │ Nebenkosten (€) ││
│ │ [___________]   │ │ [___________]   │ │ [___________]   ││
│ └─────────────────┘ └─────────────────┘ └─────────────────┘│
│                       ↑ NEW FIELD                           │
│                       Help text: "Optional: Mietpreis pro   │
│                       Quadratmeter. Kann zur Berechnung des │
│                       Gesamtmietpreises verwendet werden."  │
│                                                             │
│ ┌─────────────────┐                                        │
│ │ Kaution (€)     │                                        │
│ │ [___________]   │                                        │
│ └─────────────────┘                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Layout**:
- Row 1: Mietpreis (€) * | €/m² | Nebenkosten (€)
- Row 2: Kaution (€)
- All fields use Bootstrap 5 form-control styling
- The €/m² field accepts decimal values with 2 decimal places
- Client-side validation prevents negative values (min="0")

#### Detail View
The "Preise & Kosten" section displays the price information:

```
┌─────────────────────────────────────────────────────────────┐
│ Preise & Kosten                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Mietpreis:                     1000.00 €                    │
│ €/m² (eingegeben):             20.00 €/m²  ← NEW (if set)  │
│ Berechneter Preis pro m²:      20.00 €/m²  ← Existing      │
│ Nebenkosten:                   200.00 €                     │
│ Kaution:                       3000.00 €                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Display Logic**:
- `€/m² (eingegeben)` - Only shown if `price_per_sqm` is set (user-entered value)
- `Berechneter Preis pro m²` - Only shown if `fläche` is set (calculated as mietpreis/fläche)
- Both fields can be shown simultaneously for comparison
- Clear differentiation between entered and calculated values

### 3. Calculation Feature with User Confirmation

When saving a MietObjekt (create or edit):

**Trigger Conditions**:
1. `price_per_sqm` is set (not null)
2. `fläche` (area) is set (not null)

**Behavior**:
1. Before form submission, a Bootstrap modal appears
2. Modal displays the calculation preview: "€/m² × area = result"
3. User is asked: "Gesamtmiete aus €/m² und Fläche berechnen und übernehmen?"
4. Two options:
   - **"Ja, übernehmen"**: Sets `mietpreis = price_per_sqm × fläche` and submits form
   - **"Nein"**: Leaves `mietpreis` unchanged and submits form

**Modal Structure**:
```
┌──────────────────────────────────────────────┐
│ Mietpreis berechnen                     [×]  │
├──────────────────────────────────────────────┤
│                                              │
│ Gesamtmiete aus €/m² und Fläche berechnen   │
│ und übernehmen?                              │
│                                              │
│ Berechnung: 20.00 €/m² × 50.00 m² = 1000.00 €│
│                                              │
├──────────────────────────────────────────────┤
│                     [Nein] [Ja, übernehmen] │
└──────────────────────────────────────────────┘
```

**JavaScript Implementation**:
- Event listener on form submit
- Checks for both `price_per_sqm` and `fläche` values
- Shows modal only when both are present
- Calculates: `price_per_sqm × fläche`, rounded to 2 decimal places
- Updates `mietpreis` field on confirmation
- Bypasses modal if either field is missing

### 4. Validation

**Model-Level Validation**:
- `MinValueValidator(Decimal('0.00'))` ensures non-negative values
- Field is optional (null=True, blank=True)

**Form-Level Validation**:
- HTML5 validation: `min="0"`
- Django form validation inherits model validators
- Negative values rejected with error message

**Test Coverage**:
- ✅ Model field can be null
- ✅ Model field accepts valid positive values
- ✅ Model field accepts zero
- ✅ Model field rejects negative values
- ✅ Form includes price_per_sqm field
- ✅ Form accepts omitted price_per_sqm (optional)
- ✅ Form accepts valid price_per_sqm values
- ✅ Form rejects negative price_per_sqm values
- ✅ View can create MietObjekt with price_per_sqm
- ✅ View can create MietObjekt without price_per_sqm
- ✅ View can edit MietObjekt to add price_per_sqm
- ✅ Detail view displays price_per_sqm when set
- ✅ Detail view works correctly when price_per_sqm is not set
- ✅ Form view includes price_per_sqm input field

## Files Changed

1. **vermietung/models.py**
   - Added `price_per_sqm` field to MietObjekt model

2. **vermietung/migrations/0028_mietobjekt_price_per_sqm.py**
   - Database migration to add the new field

3. **vermietung/forms.py**
   - Added `price_per_sqm` to MietObjektForm fields
   - Added widget with Bootstrap styling and min="0"
   - Added label "€/m²"
   - Added help text

4. **templates/vermietung/mietobjekte/form.html**
   - Added price_per_sqm input field in "Preise & Kosten" section
   - Added confirmation modal HTML
   - Added JavaScript for calculation logic

5. **templates/vermietung/mietobjekte/detail.html**
   - Added conditional display of price_per_sqm
   - Improved label clarity for calculated vs entered values

6. **vermietung/test_price_per_sqm.py** (NEW)
   - Comprehensive test suite with 14 tests
   - All tests passing

## Backward Compatibility

✅ **Full backward compatibility maintained**:
- Field is optional/nullable - existing MietObjekt records work without changes
- No data migration needed
- Existing forms and views continue to work
- Existing tests (27 tests) all passing

## Security

✅ **No security vulnerabilities found** (CodeQL scan)
- Proper input validation (non-negative values)
- No SQL injection risks (Django ORM)
- No XSS risks (Django template escaping)
- No CSRF issues (Django CSRF protection)

## Example Usage Scenarios

### Scenario 1: Creating a new rental object with €/m²
1. User navigates to "Neues Mietobjekt"
2. Fills in basic info (Name, Typ, Beschreibung)
3. Enters Fläche: 50 m²
4. Enters €/m²: 20.00
5. Clicks "Speichern"
6. Modal appears: "20.00 €/m² × 50.00 m² = 1000.00 €"
7. User clicks "Ja, übernehmen"
8. Mietpreis is automatically set to 1000.00
9. Object is saved

### Scenario 2: Creating without €/m² (traditional method)
1. User fills in all fields as before
2. Enters Mietpreis directly: 1000.00
3. Does NOT enter €/m²
4. Clicks "Speichern"
5. No modal appears (backward compatible)
6. Object is saved normally

### Scenario 3: Viewing an object with €/m²
1. User views detail page
2. Sees "Mietpreis: 1000.00 €"
3. Sees "€/m² (eingegeben): 20.00 €/m²"
4. Sees "Berechneter Preis pro m²: 20.00 €/m²"
5. Can verify that entered and calculated values match

## Future Enhancements (Out of Scope)

The following were explicitly excluded from this implementation:
- No automatic price updates without user confirmation
- No changes to contract logic
- No list view modifications
- No reporting/analytics features
- No price history tracking

## Acceptance Criteria Status

✅ All acceptance criteria met:
- [x] DB contains new optional field `price_per_sqm` with migration
- [x] MietObjekte can be created/saved without `price_per_sqm`
- [x] Create/Edit: `price_per_sqm` can be entered and saved as "€/m²"
- [x] Detail view shows `price_per_sqm` correctly formatted (EUR) only when set
- [x] Validation prevents negative values for `price_per_sqm`
- [x] When saving: If `price_per_sqm` set AND area available:
  - [x] Confirm dialog is shown
  - [x] On confirmation, `mietpreis = price_per_sqm × area` is applied
  - [x] On decline, `mietpreis` remains unchanged
- [x] If no area: Saving works without prompt; `price_per_sqm` is persisted
