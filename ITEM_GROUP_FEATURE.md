# Item Group Feature Implementation

## Overview
This feature adds optional categorization of Items (Artikel) using Item Groups (Warengruppen), specifically allowing items to be assigned to sub-item groups (Unterwarengruppen).

## Changes Made

### 1. Data Model
**File:** `core/models.py`

Added `item_group` field to the `Item` model:
- **Type:** `ForeignKey` to `core.ItemGroup`
- **Nullable:** Yes (`null=True`, `blank=True`)
- **Delete behavior:** `PROTECT` (consistent with other foreign keys in the model)
- **Related name:** `items`

### 2. Validation
**File:** `core/models.py` - `Item.clean()` method

Added validation to ensure:
- `NULL` values are allowed (no assignment)
- Only SUB item groups (those with `parent != NULL`) can be assigned
- MAIN item groups (those with `parent == NULL`) are rejected with a clear error message

**Error Message (German):**
```
Ein Artikel kann nur einer Unterwarengruppe (SUB) zugeordnet werden, 
nicht einer Hauptwarengruppe (MAIN). Bitte wählen Sie eine Unterwarengruppe.
```

### 3. Database Migration
**File:** `core/migrations/0021_add_item_group_to_item.py`

Created migration to add the `item_group` field to the database.

### 4. Admin Interface
**File:** `core/admin.py` - `ItemAdmin` class

Updated admin interface to:
- Display `item_group` in the list view
- Add filters for:
  - Direct item group filtering (`item_group`)
  - Parent item group filtering (`item_group__parent`) for indirect filtering by main group
- Add a new fieldset "Klassifizierung" (Classification) with the `item_group` field

### 5. Tests
**File:** `core/test_item.py`

Added three comprehensive tests:
1. `test_item_group_null_valid`: Verifies that NULL values are accepted
2. `test_item_group_sub_valid`: Verifies that SUB item groups can be assigned
3. `test_item_group_main_invalid`: Verifies that MAIN item groups are rejected with ValidationError

## Usage

### In Code
```python
from core.models import Item, ItemGroup

# Create or get item groups
main_group = ItemGroup.objects.create(
    code="ELEC",
    name="Elektronik",
    group_type="MAIN"
)
sub_group = ItemGroup.objects.create(
    code="PHONE",
    name="Smartphones",
    group_type="SUB",
    parent=main_group
)

# Create item with sub group (VALID)
item = Item.objects.create(
    article_no="ART-001",
    short_text_1="iPhone 15",
    item_group=sub_group,  # Valid: SUB group
    # ... other required fields
)

# Create item without group (VALID)
item2 = Item.objects.create(
    article_no="ART-002",
    short_text_1="Generic Item",
    item_group=None,  # Valid: NULL
    # ... other required fields
)

# Trying to assign MAIN group (INVALID)
item3 = Item(
    article_no="ART-003",
    short_text_1="Invalid Item",
    item_group=main_group,  # Invalid: MAIN group
    # ... other required fields
)
item3.full_clean()  # Raises ValidationError
```

### In Admin
1. Navigate to Items in Django Admin
2. When creating/editing an item, select an item group from the "Klassifizierung" section
3. Only SUB item groups will be valid (MAIN groups will cause validation errors)
4. Use the filters on the right side to filter by item group or parent group

## Business Rules

### Deterministic Classification
- **SUB** (Unterwarengruppe): `ItemGroup.parent IS NOT NULL`
- **MAIN** (Hauptwarengruppe): `ItemGroup.parent IS NULL`

### Assignment Rules
| Item.item_group | Validity | Reason |
|-----------------|----------|--------|
| `NULL` | ✅ Valid | Items can remain unclassified |
| SUB (parent ≠ NULL) | ✅ Valid | Correct classification level |
| MAIN (parent = NULL) | ❌ Invalid | Direct assignment to MAIN not allowed |

## Testing
All tests pass successfully:
- 3 new tests specific to item_group feature
- 15 total tests in `core.test_item`
- 19 tests in `core.test_itemgroup`
- 224 total tests in core app

## Security
✅ No security vulnerabilities detected by CodeQL

## Acceptance Criteria Status
- ✅ `Item` has an optional FK field `item_group` on `core.ItemGroup`
- ✅ Items can be saved without assignment (`NULL`)
- ✅ Items can be assigned to a SUB item group (parent != NULL)
- ✅ Direct assignment of a MAIN item group (parent == NULL) is prevented by validation
- ✅ Admin/CRUD supports display + editing of `item_group`
- ✅ Admin/CRUD offers filter by `item_group` and `item_group__parent`
- ✅ Tests cover MAIN-invalid, SUB-valid, NULL-valid scenarios
