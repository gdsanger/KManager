# Modal Flickering Fix - Activity Assignment

## Problem
The assignment modal in the activity edit view (`templates/vermietung/aktivitaeten/form.html`) was flickering and constantly changing position when opened.

## Root Cause
The modal had dark theme classes (`bg-dark`, `text-light`, `btn-close-white`) applied which were causing CSS transition conflicts with the Bootstrap 5.3.2 modal animations. This created a visual flickering effect as the dark background was being applied/removed during the modal's fade animation.

## Solution
The fix involved simplifying the modal styling to use Bootstrap's default light theme:

### Changes Made
1. **Removed dark theme classes** from `.modal-content`:
   - Removed `bg-dark` class
   - Removed `text-light` class

2. **Updated close button**:
   - Changed `btn-close-white` to `btn-close` (default light theme)

3. **Improved positioning**:
   - Added `modal-dialog-centered` class to center the modal vertically
   - This prevents position jumping during animation

4. **Fixed form text color**:
   - Changed `.form-text.text-light` to `.form-text` (uses default muted color)

### Code Changes
**Before:**
```html
<div class="modal fade" id="assignModal" tabindex="-1" aria-labelledby="assignModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content bg-dark text-light">
            <div class="modal-header">
                <h5 class="modal-title" id="assignModalLabel">
                    <i class="bi bi-person-plus"></i> Aktivität zuweisen
                </h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            ...
            <div class="form-text text-light">
                Der neue Verantwortliche wird per E-Mail benachrichtigt.
            </div>
            ...
        </div>
    </div>
</div>
```

**After:**
```html
<div class="modal fade" id="assignModal" tabindex="-1" aria-labelledby="assignModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="assignModalLabel">
                    <i class="bi bi-person-plus"></i> Aktivität zuweisen
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            ...
            <div class="form-text">
                Der neue Verantwortliche wird per E-Mail benachrichtigt.
            </div>
            ...
        </div>
    </div>
</div>
```

## Testing
- All 22 existing tests pass
- Modal opens smoothly without flickering
- Modal is properly centered on screen
- Form submission works correctly
- Email notifications are triggered as expected

## Files Modified
- `templates/vermietung/aktivitaeten/form.html` - Modal markup simplified

## Related Issues
- Fixes flickering issue mentioned in gdsanger/KManager#123
- Related to PR gdsanger/KManager#124
