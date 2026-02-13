# Fix Summary: Missing Save/Create Button on Activity Creation Page

## Issue Description
On the route `/vermietung/aktivitaeten/neu/` (new activity creation), the "Save/Create" button was missing. Only the "Cancel" button was visible, making it impossible to save a new activity.

## Root Cause
The template `templates/vermietung/aktivitaeten/form.html` had incorrect conditional block structure:

### Before (Problematic Structure)
```django
Line 189: {% if not is_create %}
  Lines 190-297: Attachments Section (upload form, existing attachments list)
  Lines 298-470: Form fields (privat, ersteller, assigned_user, context fields, etc.)
  Lines 472-509: **Action Buttons** (including Save/Create button) ← WRONGLY HIDDEN
  Lines 514-594: Hidden forms (delete, complete, assignment modal, JavaScript)
Line 595: {% endif %}
```

The `{% if not is_create %}` block that started at line 189 was intended to wrap only the attachments section, but it extended all the way to line 595. This meant that **everything between lines 189-595 was hidden in create mode**, including the Action Buttons section that contains the "Save/Create" button.

## Solution
Fixed the conditional block structure to properly separate create-mode and edit-mode sections:

### After (Fixed Structure)
```django
Line 189: {% if not is_create %}
  Lines 190-297: Attachments Section (only shown in edit mode)
Line 298: {% endif %} ← NEW: Properly close attachments section

Lines 298-470: Form fields (visible in BOTH create and edit modes)

Lines 472-509: **Action Buttons** (visible in BOTH modes) ✅
  - Shows "Anlegen" button in create mode
  - Shows "Speichern" button in edit mode

Line 513: {% if not is_create %} ← NEW: Wrap edit-only elements
  Lines 514-594: Hidden forms (delete, complete, assignment modal, JavaScript)
Line 595: {% endif %}
```

## Changes Made

### 1. Template Fix (`templates/vermietung/aktivitaeten/form.html`)
- **Line 298**: Added `{% endif %}` to properly close the attachments section conditional
- **Line 513**: Added `{% if not is_create %}` before hidden forms to wrap edit-only elements
- This ensures the Action Buttons section is **always visible** in both create and edit modes

### 2. Test Coverage (`vermietung/test_aktivitaet_create_button.py`)
Added comprehensive tests to verify the fix:
- **test_anlegen_button_appears_on_create_page**: Verifies "Anlegen" button appears in create mode
- **test_hidden_forms_not_present_in_create_mode**: Verifies edit-only elements are hidden in create mode
- **test_attachments_info_appears_in_create_mode**: Verifies attachment info message appears in create mode
- **test_delete_button_appears_in_edit_mode**: Verifies delete button appears in edit mode but not in create mode

## Testing Results

### Existing Tests
All 24 existing `vermietung.test_aktivitaet_views` tests pass ✅

### New Tests
All 4 new tests in `vermietung.test_aktivitaet_create_button` pass ✅

### Security Check
CodeQL analysis found 0 security vulnerabilities ✅

## Acceptance Criteria (from Issue)

- [x] On `/vermietung/aktivitaeten/neu/` there is a visible primary "Anlegen" button
- [x] Clicking the button saves a new activity successfully (with valid inputs)
- [x] Validation errors prevent saving and show error messages to the user
- [x] "Cancel" button remains present and works as before
- [x] The button label shows "Anlegen" in create mode and "Speichern" in edit mode

## Impact
This fix restores full functionality to the activity creation page, allowing users to:
1. Create new activities via the `/vermietung/aktivitaeten/neu/` route
2. See the appropriate "Anlegen" (Create) button in create mode
3. See the appropriate "Speichern" (Save) button in edit mode
4. Access all edit-only features (delete, assignment, etc.) only when editing existing activities

## Notes
- The fix is minimal and surgical, changing only the template conditional structure
- No business logic changes were made
- All existing functionality remains intact
- Test coverage ensures the fix works correctly in both create and edit modes
