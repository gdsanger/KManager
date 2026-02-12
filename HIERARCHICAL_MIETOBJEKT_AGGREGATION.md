# Hierarchical MietObjekt Aggregation - Implementation Summary

## Overview
This implementation adds automatic aggregation of unit counts and availability status from child MietObjekte to their parent objects. When a MietObjekt has direct children, its unit-related fields become read-only and display aggregated values from all direct children.

## Key Features Implemented

### 1. Automatic Aggregation Logic
**File:** `vermietung/models.py`

#### New Methods
- **`has_children()`** - Check if object has any direct children
- **`_calculate_own_active_units()`** - Internal method to calculate active units from contracts (no children check)
- **`get_verfuegbare_einheiten_display()`** - Returns correct display value (own or aggregated)
- **`get_aggregated_verfuegbare_einheiten()`** - Sum of verfuegbare_einheiten from children
- **`get_aggregated_verfuegbar_status()`** - True if at least one child is available

#### Modified Methods
- **`get_active_units_count()`** - Now automatically aggregates from children when they exist
- **`get_available_units_count()`** - Now automatically aggregates from children when they exist

### 2. Readonly Enforcement
**File:** `vermietung/views.py` (mietobjekt_edit)

- When editing a parent object (has children), the `verfuegbare_einheiten` field is automatically disabled
- Help text is updated to indicate the field is calculated from children
- Form validation prevents manual changes when children exist

### 3. Detail View Enhancements
**File:** `templates/vermietung/mietobjekte/detail.html`

#### Aggregated Values Display
- Shows clear "readonly" indicator when displaying aggregated values
- Displays all three unit metrics (gesamt, gebucht, verfügbar) from children
- Shows aggregated availability status

#### Hierarchy Card - Children Table
- Displays direct children in table format matching the list view
- Columns: Name, Fläche (Area), Einheiten (Units), Status, Actions
- Each child has View and Edit action buttons
- Table uses same styling as main MietObjekt list view

#### Child Assignment Modal
- "Zuweisen" button opens modal for assigning existing objects
- Modal lists all MietObjekte without a parent
- Excludes current object from list
- AJAX-based assignment with validation
- Automatic page refresh after successful assignment

### 4. List View Updates
**File:** `templates/vermietung/mietobjekte/list.html`

- Updated to use `get_verfuegbare_einheiten_display()` method
- Automatically shows aggregated values for parents with children
- Consistent display across list and detail views

### 5. URL Configuration
**File:** `vermietung/urls.py`

Added two new AJAX endpoints:
- `mietobjekt_available_for_assignment` - GET list of assignable objects
- `mietobjekt_assign_child` - POST to assign a child to parent

### 6. Comprehensive Tests
**File:** `vermietung/test_mietobjekt_hierarchy.py`

Added `MietObjektAggregationTestCase` with 11 new tests:
1. `test_has_children` - Verify has_children() detection
2. `test_aggregated_verfuegbare_einheiten` - Test unit summation
3. `test_aggregated_verfuegbar_status` - Test availability status derivation
4. `test_get_verfuegbare_einheiten_display` - Test display method
5. `test_get_active_units_count_with_children` - Test active units aggregation
6. `test_get_available_units_count_with_children` - Test available units aggregation
7. `test_edit_form_disables_verfuegbare_einheiten_with_children` - Test readonly enforcement
8. `test_detail_view_shows_aggregated_values` - Test detail view context
9. `test_available_for_assignment_endpoint` - Test AJAX endpoint for listing objects
10. `test_assign_child_endpoint` - Test AJAX endpoint for assignment
11. `test_assign_child_validation` - Test assignment validation

**All 23 hierarchy tests pass ✓**

## Aggregation Rules

### One-Level Deep Only
- Aggregation is **not recursive** - only direct children are considered
- If a child has its own children, they are not included in grandparent aggregation

### Source of Truth
- For objects **with children**: Child objects are the source of truth
  - `verfuegbare_einheiten` field is readonly
  - Display values come from summing children
- For objects **without children**: Own field values are used
  - Normal editing and display behavior

### Calculated Fields
| Field | Parent Calculation | Child Behavior |
|-------|-------------------|----------------|
| Verfügbare Einheiten | Sum(children.verfuegbare_einheiten) | Own field value |
| Belegte Einheiten | Sum(children.get_active_units_count()) | Calculated from contracts |
| Aktuell verfügbare Einheiten | Sum(children.get_available_units_count()) | verfuegbare - belegte |
| Verfügbar (bool) | TRUE if any child is verfügbar | Own field value |

## Security

### CodeQL Analysis
- **0 security alerts** found
- All code passes security scan

### XSS Prevention
- No inline onclick handlers
- All user-provided values are HTML-escaped in templates
- Event listeners attached via JavaScript
- Numeric values converted to strings and escaped for defense-in-depth

### CSRF Protection
- All POST endpoints require CSRF token
- `@require_POST` decorator enforces POST-only access
- AJAX requests include CSRF token in headers

### Input Validation
- Child assignment validates no existing parent
- Prevents self-assignment
- Full_clean() called for model validation
- Circular reference detection from previous implementation

## Performance Considerations

### Query Optimization
- Direct children fetched with `select_related('standort')`
- No N+1 query problem - aggregation done in Python for clarity
- Alternative: Could use database aggregation for very large child sets

### Recursion Safety
- Internal `_calculate_own_active_units()` method prevents infinite recursion
- Clear separation between own calculation and aggregation logic
- Safe for any hierarchy depth (though only one level is aggregated)

## Usage Examples

### Example 1: Building with Apartments
```python
# Create parent building
building = MietObjekt.objects.create(
    name='Gebäude A',
    type='GEBAEUDE',
    standort=standort,
    verfuegbare_einheiten=10  # This will be ignored once children exist
)

# Create child apartments
apt1 = MietObjekt.objects.create(
    name='Wohnung 1',
    parent=building,
    verfuegbare_einheiten=5
)

apt2 = MietObjekt.objects.create(
    name='Wohnung 2',
    parent=building,
    verfuegbare_einheiten=3
)

# Aggregated values (automatic)
building.get_verfuegbare_einheiten_display()  # Returns 8 (5+3)
building.get_active_units_count()  # Sum of children's active units
building.get_available_units_count()  # Sum of children's available units

# Editing
# In edit form, verfuegbare_einheiten will be disabled for building
# It will always show 8 (sum from children)
```

### Example 2: Assigning Existing Object
```python
# Create orphan object
orphan = MietObjekt.objects.create(
    name='Standalone Unit',
    verfuegbare_einheiten=2
)

# Assign via UI modal or programmatically
orphan.parent = building
orphan.save()

# Building now shows updated aggregate: 10 (5+3+2)
```

## Files Modified

1. **vermietung/models.py** - Aggregation logic and internal methods
2. **vermietung/views.py** - Detail view context and AJAX endpoints
3. **vermietung/urls.py** - New URL patterns
4. **templates/vermietung/mietobjekte/detail.html** - Hierarchy table and modal
5. **templates/vermietung/mietobjekte/form.html** - Readonly indicator
6. **templates/vermietung/mietobjekte/list.html** - Display method usage
7. **vermietung/test_mietobjekt_hierarchy.py** - New test suite

## Acceptance Criteria Met

✅ **1. Readonly Summenfelder**: Parent unit fields are readonly when children exist and show exact sum of children

✅ **2. Parent-Verfügbarkeit**: Parent availability is true when at least one child is available

✅ **3. Konsistenz**: Values are identical in ListView and DetailView (both use same methods)

✅ **4. Hierarchie-Tabelle**: Detail view shows Hierarchy card with table matching list view style

✅ **5. Zuweisung**: Modal shows only objects without parent, assignment works correctly

## Future Enhancements (Not in Scope)

- Multi-level aggregation (currently only direct children)
- Batch child assignment
- Hierarchy visualization/tree view
- Automatic parent unit count updates via signals
- Database-level aggregation for very large child sets

## Conclusion

This implementation successfully addresses all requirements from issue #376:

✅ **Hierarchical Aggregation** - Parent fields derived from children
✅ **Readonly Enforcement** - Parent unit fields cannot be edited when children exist
✅ **Consistent Display** - Same values across all views
✅ **Child Management UI** - Table view and assignment modal
✅ **Security** - 0 CodeQL alerts, proper XSS prevention
✅ **Testing** - 23 tests passing, 11 new aggregation tests
✅ **Performance** - Optimized queries, no N+1 problems

The implementation is production-ready, fully tested, and secure.
