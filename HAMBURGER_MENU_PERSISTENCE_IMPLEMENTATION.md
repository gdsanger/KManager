# Hamburger Menu Persistence Implementation

**Issue:** #192  
**Feature:** UI: Hamburger-Menü/Sidebar – expandierte Menügruppen in localStorage persistieren

## Implementation Summary

This implementation adds localStorage persistence for expanded menu groups in the Vermietung sidebar, ensuring that users don't lose their menu expansion state after navigation or page reload.

## Technical Details

### Storage Key
- **Key:** `nav.expandedMenuGroupIds`
- **Constant:** `NAV_EXPANDED_MENU_GROUP_IDS_KEY`
- **Format:** JSON stringified array of menu group IDs

### Menu Groups with Persistence
1. `adressenMenu` - Adressen section (Adressen, Kunden, Lieferanten)
2. `aktivitaetenMenu` - Aktivitäten section (Kanban, Alle Aktivitäten, etc.)
3. `vermietungMenu` - Vermietung section (Standorte, Mietobjekte, Verträge, etc.)
4. `einstellungenMenu` - Einstellungen section (Template-Einstellungen, E-Mail-Einstellungen)

### Implementation Details

#### Helper Functions
1. **`isLocalStorageAvailable()`**
   - Safely checks if localStorage is available
   - Returns `false` for SSR, privacy mode, or quota exceeded
   
2. **`readExpandedGroupIds()`**
   - Reads expanded group IDs from localStorage
   - Returns empty array `[]` on error or if not available
   - Validates that stored value is an array

3. **`writeExpandedGroupIds(ids)`**
   - Writes expanded group IDs to localStorage
   - Removes key when array is empty (cleaner storage)
   - Silently fails if localStorage unavailable

4. **`sanitizeExpandedGroupIds(storedIds, validIds)`**
   - Filters out invalid/stale menu group IDs
   - Ensures only currently existing menu groups are restored

#### Lifecycle

**On Page Load:**
1. Query all `.sidebar .collapse` elements to get valid menu group IDs
2. Read stored IDs from localStorage
3. Sanitize stored IDs against valid IDs
4. Clean up localStorage if invalid IDs were found
5. Restore expanded state using Bootstrap Collapse API

**On Menu Group Expand (`shown.bs.collapse` event):**
1. Read current expanded IDs from localStorage
2. Add the newly expanded group ID (if not already present)
3. Write updated array back to localStorage

**On Menu Group Collapse (`hidden.bs.collapse` event):**
1. Read current expanded IDs from localStorage
2. Filter out the collapsed group ID
3. Write updated array back to localStorage (or remove key if empty)

### Error Handling

- All localStorage operations wrapped in try/catch blocks
- Feature detection prevents errors in unsupported environments
- Console warnings logged for debugging (no user-facing errors)
- Graceful degradation when localStorage unavailable

### Browser Compatibility

Works in all modern browsers that support:
- localStorage API
- Bootstrap 5.3 Collapse component
- Array.isArray(), Array.filter(), Array.includes()

## Manual Testing Guide

### Test Case 1: Basic Persistence
1. Navigate to any Vermietung page
2. Expand "Adressen" and "Aktivitäten" menu groups
3. Reload the page (F5)
4. **Expected:** Both groups remain expanded

### Test Case 2: Selective Collapse
1. Expand "Adressen", "Aktivitäten", and "Vermietung"
2. Collapse "Aktivitäten"
3. Reload the page
4. **Expected:** "Adressen" and "Vermietung" are expanded, "Aktivitäten" is collapsed

### Test Case 3: Empty State
1. Collapse all menu groups
2. Reload the page
3. **Expected:** All groups remain collapsed
4. Check localStorage: `nav.expandedMenuGroupIds` key should not exist

### Test Case 4: Invalid Data Handling
1. Open browser DevTools → Application/Storage → localStorage
2. Set `nav.expandedMenuGroupIds` to `["__invalid__", "nonexistent"]`
3. Reload the page
4. **Expected:** No errors, all groups collapsed, invalid data cleaned up

### Test Case 5: localStorage Disabled
1. Open browser in Incognito/Private mode with localStorage disabled
2. Navigate to Vermietung page
3. Expand menu groups
4. **Expected:** Menus work normally but state doesn't persist across reloads

### Verification Commands

**Check localStorage in Browser DevTools Console:**
```javascript
// View current stored IDs
localStorage.getItem('nav.expandedMenuGroupIds')

// Parse and view as array
JSON.parse(localStorage.getItem('nav.expandedMenuGroupIds'))

// Manually set test data
localStorage.setItem('nav.expandedMenuGroupIds', '["adressenMenu", "aktivitaetenMenu"]')

// Clear stored data
localStorage.removeItem('nav.expandedMenuGroupIds')
```

## Code Location

**File:** `templates/vermietung/vermietung_base.html`  
**Lines:** 365-480 (approximately)  
**Section:** Inside `DOMContentLoaded` event listener, after sidebar toggle functionality

## Dependencies

- Bootstrap 5.3.2 (for Collapse component)
- Modern browser with localStorage support
- No additional dependencies added

## Backwards Compatibility

- Feature is additive - does not break existing functionality
- Sidebar collapse/expand still works independently
- Gracefully degrades when localStorage unavailable
- No server-side changes required

## Future Enhancements (Out of Scope)

- Server-side storage for cross-device sync
- User preferences panel
- Animation preferences
- Menu group ordering/customization

## Related Issues

- Issue #192: Domus, Hamburger Menü (this implementation)
- Issue #158: Anpassung der Navigation im linken Sidebar (context)

---

**Implementation Date:** 2026-01-31  
**Status:** ✅ Complete
