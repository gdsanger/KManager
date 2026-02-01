# Aktivitäten: Optional Context & Category Implementation

## Summary

This implementation addresses issue #223 - "Bei einer neuen Aktivität muss ich anscheinend zwingend Mietobjekt angeben sonst speichert er es aber nicht"

### Problem Solved
- Activities (Aktivitäten) previously required exactly one context (Mietobjekt, Vertrag, or Kunde)
- Private/personal activities without rental context could not be created
- No global categorization system existed for organizing activities

### Solution Implemented
1. **Made rental context optional** - Activities can now be created without any context (Mietobjekt, Vertrag, or Kunde)
2. **Added category system (Bereiche)** - Global categories for organizing activities (e.g., "Privat", "Sport", "Finanzen")
3. **Inline category creation** - Categories can be created directly from the activity form via AJAX modal
4. **Updated UI** - Activity lists and Kanban views now display category badges

## Changes Made

### 1. Database Models

#### New Model: AktivitaetsBereich
```python
class AktivitaetsBereich(models.Model):
    name = models.CharField(max_length=100, unique=True)
    beschreibung = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

#### Updated Model: Aktivitaet
- Removed validation requiring exactly one context
- Added optional `bereich` FK to AktivitaetsBereich (with SET_NULL on delete)
- Made `ersteller` field fully optional (blank=True)
- Updated docstring to reflect optional contexts

**Migration Files:**
- `0029_add_aktivitaetsbereich_and_optional_context.py` - Adds new model and bereich field
- `0030_make_ersteller_optional.py` - Makes ersteller field optional

### 2. Forms

#### AktivitaetForm
- Added `bereich` field to form fields list
- Removed context validation in `clean()` method
- Context fields now fully optional
- Pre-fills ersteller with current user

#### New Form: AktivitaetsBereichForm
- Simple form for creating/editing categories
- Fields: name, beschreibung

### 3. Views

#### New Category CRUD Views
- `bereich_list` - Display all categories with activity counts
- `bereich_create` - Create new category
- `bereich_edit` - Edit existing category
- `bereich_delete` - Delete category (sets aktivitaet.bereich to NULL)
- `bereich_create_ajax` - AJAX endpoint for inline category creation

#### Updated Activity Views
- Updated imports to include AktivitaetsBereich
- Activity views unchanged (context is now optional in forms)

### 4. Templates

#### New Templates
- `templates/vermietung/bereich/list.html` - Category list view with table
- `templates/vermietung/bereich/form.html` - Category create/edit form

#### Updated Templates
- `templates/vermietung/aktivitaeten/form.html`:
  - Added bereich field with inline creation button
  - Added modal for creating new categories
  - Added JavaScript for AJAX category creation
  
- `templates/vermietung/aktivitaeten/list.html`:
  - Added "Bereich" column to table
  - Displays category badge or "-" if none
  
- `templates/vermietung/aktivitaeten/_kanban_card.html`:
  - Added category badge display on Kanban cards

### 5. URLs

Added new URL patterns in `vermietung/urls.py`:
```python
path('bereiche/', views.bereich_list, name='bereich_list'),
path('bereiche/neu/', views.bereich_create, name='bereich_create'),
path('bereiche/<int:pk>/bearbeiten/', views.bereich_edit, name='bereich_edit'),
path('bereiche/<int:pk>/loeschen/', views.bereich_delete, name='bereich_delete'),
path('bereiche/ajax/neu/', views.bereich_create_ajax, name='bereich_create_ajax'),
```

### 6. Admin

#### Updated AktivitaetAdmin
- Added `bereich` to list_display
- Added `bereich__name` to search_fields
- Added `bereich` to list_filter
- Updated fieldsets to include bereich in "Aufgabendetails"
- Changed context fieldset description to reflect optional nature
- Added `bereich` to select_related in get_queryset

#### New Admin: AktivitaetsBereichAdmin
- Displays: name, beschreibung, created_at, aktivitaeten_count
- Custom method `get_aktivitaeten_count` shows number of activities per category

### 7. Tests

#### Updated Existing Tests
Changed tests that previously expected ValidationError for activities without context:
- `test_aktivitaet_without_context_is_allowed` - Now validates activities can be created without context
- `test_aktivitaet_with_multiple_contexts_is_allowed` - Multiple contexts now allowed
- `test_aktivitaet_with_all_three_contexts_is_allowed` - All contexts can be set

#### New Test Class: AktivitaetsBereichTest
- Tests category creation
- Tests unique name constraint
- Tests activity-category relationship
- Tests SET_NULL behavior on category deletion
- Tests ordering by name

**Test Results:** All 40 tests pass ✓

## Features

### 1. Create Activities Without Context
Users can now create personal/private activities without linking them to rental objects, contracts, or customers.

Example:
```python
Aktivitaet.objects.create(
    titel='Joggen gehen',
    beschreibung='30 Minuten Joggen im Park',
    bereich=sport_category,
    ersteller=user
)
```

### 2. Category Management (Bereiche)
- Navigate to "Bereiche" in the Aktivitäten section
- Create, edit, delete categories
- View activity count per category
- Categories are ordered alphabetically

### 3. Inline Category Creation
When creating/editing an activity:
1. Click the "+" button next to the Bereich dropdown
2. Modal opens with category creation form
3. Submit the form via AJAX
4. New category is automatically added to dropdown and selected
5. Continue editing activity without leaving the page

### 4. Visual Indicators
- **List View**: Category column shows badge with category name
- **Kanban View**: Category badge displayed on each card
- **Color**: Primary blue badge for categories

## Backward Compatibility

✅ **Fully backward compatible** - Existing activities with context continue to work unchanged
✅ **No data loss** - All existing activities retain their context relationships
✅ **Optional fields** - Context and category fields are all optional, no required changes

## Database Impact

- New table: `aktivitaetsbereich`
- New field in `aktivitaet`: `bereich_id` (nullable FK)
- New index on `aktivitaet.bereich_id`
- Modified field: `aktivitaet.ersteller` (now allows blank)

## Security

- Categories use SET_NULL on delete (no cascade deletes)
- AJAX endpoint includes CSRF protection
- Permission decorator `@vermietung_required` on all views
- Form validation prevents duplicate category names (unique constraint)

## Performance

- Added select_related('bereich') in admin queryset optimization
- Index on bereich_id for efficient filtering
- Minimal query overhead (single JOIN when bereich is accessed)

## Future Enhancements (Not Implemented)

The following were marked as out of scope but could be added later:
- Category-based filtering in activity list/Kanban views
- Category-specific permissions
- Category colors/icons for better visual distinction
- Category-based reporting/dashboard widgets
- Hierarchical categories (parent-child relationships)

## Navigation

To access category management:
1. Navigate to Aktivitäten section
2. Access "Bereiche" submenu (navigation placement may vary)
3. Alternatively: Direct URL `/vermietung/bereiche/`

## Usage Examples

### Creating a Personal Activity
```python
# No context required!
activity = Aktivitaet.objects.create(
    titel='Steuerberater anrufen',
    bereich=finanzen_category,
    prioritaet='HOCH',
    ersteller=current_user
)
```

### Creating an Activity with Context
```python
# Context still works as before
activity = Aktivitaet.objects.create(
    titel='Heizung reparieren',
    mietobjekt=apartment,
    bereich=maintenance_category,
    assigned_supplier=plumber,
    prioritaet='HOCH'
)
```

### Mixing Context and Categories
```python
# Can have both context AND category
activity = Aktivitaet.objects.create(
    titel='Mietvertrag erneuern',
    vertrag=contract,
    bereich=admin_category,
    faellig_am=date(2026, 3, 1)
)
```

## Files Modified

### Models & Migrations
- `vermietung/models.py`
- `vermietung/migrations/0029_add_aktivitaetsbereich_and_optional_context.py`
- `vermietung/migrations/0030_make_ersteller_optional.py`

### Forms
- `vermietung/forms.py`

### Views
- `vermietung/views.py`

### URLs
- `vermietung/urls.py`

### Admin
- `vermietung/admin.py`

### Templates
- `templates/vermietung/bereich/list.html` (new)
- `templates/vermietung/bereich/form.html` (new)
- `templates/vermietung/aktivitaeten/form.html` (updated)
- `templates/vermietung/aktivitaeten/list.html` (updated)
- `templates/vermietung/aktivitaeten/_kanban_card.html` (updated)

### Tests
- `vermietung/test_aktivitaet_model.py`

## Conclusion

This implementation successfully addresses the original issue by:
1. ✅ Making rental context optional for activities
2. ✅ Enabling creation of private/personal activities
3. ✅ Providing global categorization system
4. ✅ Supporting inline category creation
5. ✅ Maintaining backward compatibility
6. ✅ All tests passing
7. ✅ Clean, minimal code changes

The system is now flexible enough to handle both rental-related activities and personal tasks, with clear organization through optional categories.
