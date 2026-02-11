# Kanban Drag & Drop Implementation Summary

## Overview
This document describes the implementation of drag & drop functionality for the Aktivitäten Kanban view in the Vermietung module, along with enhanced filtering for completed activities and improved permission controls.

## Changes Implemented

### 1. Hint Text for Drag & Drop (UI Enhancement)
**File:** `templates/vermietung/aktivitaeten/kanban.html`

Added a visible information banner at the top of the Kanban view to inform users about the drag & drop functionality:

```html
<div class="alert alert-info mb-3" role="alert">
    <i class="bi bi-info-circle"></i>
    <strong>Tipp:</strong> Aufgaben können per Drag &amp; Drop in eine andere Spalte gezogen werden, um den Status zu ändern.
</div>
```

**Location:** Displayed prominently above the Kanban board columns.

### 2. Seven-Day Filter for "Erledigt" Column
**File:** `vermietung/views.py` - Function `aktivitaet_kanban()`

Modified the query for the "Erledigt" (Completed) column to only show activities that were updated within the last 7 days:

**Before:**
```python
aktivitaeten_erledigt = aktivitaeten.filter(status='ERLEDIGT').order_by('-updated_at')[:20]
```

**After:**
```python
# Erledigt: Only show activities completed in last 7 days (based on updated_at)
seven_days_ago = timezone.now() - timedelta(days=7)
aktivitaeten_erledigt = aktivitaeten.filter(
    status='ERLEDIGT',
    updated_at__gte=seven_days_ago
).order_by('-updated_at')
```

**Rationale:** 
- Reduces clutter by hiding older completed activities
- Uses `updated_at` field as the basis for filtering
- Uses `__gte` (greater than or equal) to include activities from exactly 7 days ago

### 3. Permission Check for Status Updates
**File:** `vermietung/views.py` - Function `aktivitaet_update_status()`

Added permission validation to ensure only authorized users can change activity status:

```python
# Check permissions: user must be assigned_user or ersteller
if aktivitaet.assigned_user != request.user and aktivitaet.ersteller != request.user:
    return JsonResponse({
        'error': 'Sie haben keine Berechtigung, den Status dieser Aktivität zu ändern.'
    }, status=403)
```

**Permission Model:**
- Users who can change status:
  - `assigned_user` - The user assigned to the activity
  - `ersteller` - The user who created the activity
- Returns HTTP 403 Forbidden for unauthorized users
- Error message is displayed to the user via JavaScript alert

### 4. Enhanced Error Handling in JavaScript
**File:** `templates/vermietung/aktivitaeten/kanban.html`

Improved the drag & drop JavaScript to handle errors gracefully:

**Before:**
```javascript
.then(response => response.json())
.then(data => {
    if (data.success) {
        location.reload();
    } else {
        alert('Fehler: ' + (data.error || 'Status konnte nicht aktualisiert werden'));
    }
})
.catch(error => {
    console.error('Error:', error);
    alert('Fehler beim Aktualisieren des Status');
});
```

**After:**
```javascript
.then(response => {
    if (!response.ok) {
        // Handle HTTP errors
        return response.json().then(data => {
            throw new Error(data.error || 'Status konnte nicht aktualisiert werden');
        });
    }
    return response.json();
})
.then(data => {
    if (data.success) {
        // Reload page to show updated status
        location.reload();
    } else {
        // Show error and reload to restore UI state
        alert('Fehler: ' + (data.error || 'Status konnte nicht aktualisiert werden'));
        location.reload();
    }
})
.catch(error => {
    console.error('Error:', error);
    alert('Fehler beim Aktualisieren des Status: ' + error.message);
    // Reload page to restore consistent state
    location.reload();
});
```

**Improvements:**
- Properly handles HTTP error responses (403, 500, etc.)
- Always reloads the page after an error to maintain UI consistency
- Provides clear error messages to users
- Prevents the UI from getting into an inconsistent state

## Testing

### New Test File: `vermietung/test_aktivitaet_kanban_drag_drop.py`

Created comprehensive tests covering all new functionality:

1. **test_status_update_by_ersteller** - Verifies that the activity creator can update status
2. **test_status_update_by_assigned_user** - Verifies that the assigned user can update status
3. **test_status_update_permission_denied** - Verifies that unauthorized users receive 403 error
4. **test_status_update_invalid_status** - Verifies that invalid status values are rejected
5. **test_kanban_erledigt_filter_last_7_days** - Verifies the 7-day filter works correctly
6. **test_kanban_erledigt_filter_excludes_other_statuses** - Verifies status-based filtering
7. **test_status_update_requires_post** - Verifies that only POST requests are accepted
8. **test_kanban_view_shows_hint_text** - Verifies the hint text is displayed

**Test Results:** All 8 tests pass ✓

### Updated Existing Tests

Modified `vermietung/test_aktivitaet_views.py` to include Mandant setup in `setUp()`:
- Fixed pre-existing test failures caused by missing Mandant
- All 19 existing tests now pass ✓

## Acceptance Criteria Met

✅ **1. Drag & Drop Status Change**
- Activity cards can be dragged between columns
- Status is updated server-side upon drop
- Changes persist after browser reload

✅ **2. Permission Control**
- Only `assigned_user` or `ersteller` can change status
- Unauthorized attempts return 403 Forbidden
- Error handling prevents UI inconsistency

✅ **3. Error Handling**
- UI reloads on errors to maintain consistency
- Clear error messages are shown to users
- No orphaned state changes

✅ **4. Hint Text**
- Visible information banner explaining drag & drop
- Positioned prominently above the Kanban board
- Uses Bootstrap alert styling for consistency

✅ **5. Seven-Day Filter for "Erledigt"**
- Only shows activities updated in the last 7 days
- Based on `updated_at` field
- Other columns remain unaffected

## Technical Details

### Database Queries
- The 7-day filter uses an efficient database query with `updated_at__gte`
- No additional database migrations required
- Existing indexes on `updated_at` field support performance

### Security Considerations
- Permission checks happen server-side (cannot be bypassed)
- CSRF protection is maintained via Django's CSRF token
- HTTP method restriction (POST only) enforced via decorator

### Browser Compatibility
- Uses standard Drag and Drop API (supported in all modern browsers)
- No additional JavaScript libraries required
- Fallback: Page reload ensures consistency even if drag fails

## Files Modified

1. `templates/vermietung/aktivitaeten/kanban.html` - Added hint text and improved error handling
2. `vermietung/views.py` - Added 7-day filter and permission check
3. `vermietung/test_aktivitaet_kanban_drag_drop.py` - New test file (8 tests)
4. `vermietung/test_aktivitaet_views.py` - Fixed existing tests by adding Mandant setup

## Migration Status
No database migrations required - all changes use existing schema.

## Deployment Notes
- No special deployment steps required
- Changes are backward compatible
- Existing data is not affected
- Cache clearing not necessary

## Future Enhancements (Not in Scope)
- Visual feedback during drag (ghost image, dropzone highlighting)
- Undo functionality for status changes
- Configurable time window for "Erledigt" filter
- Batch status updates
- Activity history/audit trail in UI
