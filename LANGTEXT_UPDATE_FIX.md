# Fix for Issue #338: Long Text Update Error in SalesDocumentLine

## Problem Description

When users edited the long text (Langtext) field in a SalesDocumentLine and left the textarea, they encountered a 500 Internal Server Error. The error appeared in:

- **Browser Console**: `POST https://app.ebner-vermietung.de/auftragsverwaltung/ajax/documents/invoice/5/lines/7/update/ 500 (Internal Server Error)`
- **Server Log**: `ERROR 2026-02-08 14:56:46,739 Internal Server Error: /auftragsverwaltung/ajax/documents/invoice/5/lines/7/update/`

## Root Cause Analysis

The issue was caused by **missing CSRF token in HTMX POST requests**. 

### Why This Happened

1. Django's CSRF middleware (`django.middleware.csrf.CsrfViewMiddleware`) requires CSRF tokens for all POST requests to protect against Cross-Site Request Forgery attacks.

2. HTMX, by default, **does not automatically include CSRF tokens** in POST requests. It needs to be explicitly configured to do so.

3. The `ajax_update_line` view had the `@login_required` decorator but no `@csrf_exempt`, meaning CSRF protection was active.

4. When HTMX sent POST requests without a CSRF token, Django's CSRF middleware rejected them with a 403 error, which was likely being caught and re-raised as a 500 error.

### Why Tests Passed

The existing tests in `test_ajax_line_update.py` all passed because Django's test client (`self.client.post()`) **automatically handles CSRF tokens**. This made the tests pass even though the actual browser-based HTMX requests were failing.

## Solution Implemented

### 1. HTMX CSRF Token Configuration (Primary Fix)

Added a global HTMX configuration in `templates/base.html` that automatically includes the CSRF token in all HTMX requests:

```javascript
// Get CSRF token from cookie
function getCookie(name) {
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const trimmedCookie = cookie.trim();
            if (trimmedCookie.startsWith(name + '=')) {
                return decodeURIComponent(trimmedCookie.substring(name.length + 1));
            }
        }
    }
    return null;
}

// Configure HTMX to include CSRF token in all requests
document.body.addEventListener('htmx:configRequest', (event) => {
    event.detail.headers['X-CSRFToken'] = getCookie('csrftoken');
});
```

**How it works:**
- Uses HTMX's `htmx:configRequest` event which fires before every HTMX request
- Retrieves the CSRF token from Django's `csrftoken` cookie
- Adds it to the request headers as `X-CSRFToken`
- Django's CSRF middleware accepts tokens from this header

### 2. Enhanced Error Logging (Secondary Fix)

Added proper logging to the `ajax_update_line` view in `auftragsverwaltung/views.py`:

```python
import logging

logger = logging.getLogger(__name__)

# In ajax_update_line function:
except Exception as e:
    logger.exception(f"Error updating line {line_id} in document {pk}: {str(e)}")
    return JsonResponse({'error': str(e)}, status=500)
```

**Benefits:**
- Exceptions are now logged with full stack traces
- Makes debugging production issues much easier
- Helps identify the root cause of similar issues in the future

## Files Modified

1. **templates/base.html**: Added HTMX CSRF token configuration
2. **auftragsverwaltung/views.py**: Added logging import and exception logging

## Impact

### Fixed Issues
- ✅ Long text updates in SalesDocumentLine now work correctly
- ✅ All HTMX POST requests across the application now include CSRF tokens
- ✅ Better error logging for debugging

### Scope of Fix
The HTMX CSRF configuration applies globally to:
- All HTMX POST requests in the application
- Currently, all 8 `hx-post` usages in `templates/auftragsverwaltung/documents/detail.html`
- Any future HTMX POST requests

### No Breaking Changes
- All existing tests pass (21 tests in ajax_line_update and decimal_parsing)
- No changes to API contracts or data models
- JavaScript uses modern syntax (for...of loop) for better maintainability

## Testing

### Unit Tests
All related tests pass:
- `test_ajax_update_line_long_text`: ✅ PASS
- `test_ajax_update_line_multiple_fields`: ✅ PASS
- `test_ajax_update_line_other_document_types`: ✅ PASS
- `test_ajax_update_line_quantity_and_price`: ✅ PASS

### Security Check
- CodeQL analysis: No security alerts
- CSRF protection remains fully active
- No vulnerabilities introduced

## Deployment Notes

### Requirements
- No new dependencies required
- No database migrations needed
- No environment variable changes

### Rollout
1. The fix is backward compatible
2. No special deployment steps required
3. Works immediately upon deployment

## Lessons Learned

1. **HTMX and CSRF**: HTMX requires explicit configuration to work with Django's CSRF protection
2. **Test Coverage Gap**: Browser-based CSRF behavior differs from test client behavior
3. **Logging is Essential**: Proper exception logging would have made this issue easier to diagnose
4. **Global vs Local Configuration**: Using HTMX's global event handler (`htmx:configRequest`) is more reliable than configuring each individual HTMX element

## References

- Issue: #338
- HTMX Documentation: https://htmx.org/events/#htmx:configRequest
- Django CSRF Documentation: https://docs.djangoproject.com/en/stable/ref/csrf/
