# Fix for Issue #338: Long Text Update Error in SalesDocumentLine

## Problem Description

When users edited the long text (Langtext) field in a SalesDocumentLine and left the textarea, they encountered a 500 Internal Server Error. The error appeared in:

- **Browser Console**: `POST https://app.ebner-vermietung.de/auftragsverwaltung/ajax/documents/invoice/5/lines/7/update/ 500 (Internal Server Error)`
- **Server Log**: 
```
ERROR 2026-02-08 15:33:47,131 Error updating line 7 in document 5: Expecting value: line 1 column 1 (char 0)
Traceback (most recent call last):
  File "/opt/KManager/auftragsverwaltung/views.py", line 774, in ajax_update_line
    data = json.loads(request.body)
  File "/usr/lib/python3.13/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^
  File "/usr/lib/python3.13/json/decoder.py", line 345, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.13/json/decoder.py", line 363, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## Root Cause Analysis

The issue was caused by **mismatched data formats between HTMX and Django**.

### Why This Happened

1. **HTMX Default Behavior**: When using `hx-vals`, HTMX sends data as **form-encoded** (application/x-www-form-urlencoded) by default, not JSON.

2. **Backend Expectation**: The `ajax_update_line` view was using `json.loads(request.body)` which expects JSON data.

3. **The Conflict**: When HTMX sent form-encoded data, `request.body` contained URL-encoded parameters, not JSON. Attempting to parse this as JSON caused the JSONDecodeError.

### Example of the Problem

Template code (detail.html):
```html
<textarea class="form-control form-control-sm line-long-text" 
          hx-post="{% url 'auftragsverwaltung:ajax_update_line' ... %}"
          hx-vals='js:{"long_text": this.value}'
          hx-swap="none">{{ line.long_text }}</textarea>
```

This sends: `long_text=Updated+text` (form-encoded)
Backend expected: `{"long_text": "Updated text"}` (JSON)

### Why Tests Passed

The existing tests in `test_ajax_line_update.py` all passed because they explicitly sent JSON:
```python
response = self.client.post(
    url,
    data=json.dumps(data),
    content_type='application/json'  # Explicitly JSON
)
```

## Solution Implemented

### Flexible Data Format Parsing

Modified the `ajax_update_line` view in `auftragsverwaltung/views.py` to accept **both JSON and form-encoded data**:

```python
# Parse request data - support both JSON and form-encoded data
# HTMX with hx-vals sends form-encoded data, while tests send JSON
try:
    data = json.loads(request.body) if request.body else {}
except (json.JSONDecodeError, ValueError):
    # Fall back to form-encoded data (from HTMX hx-vals)
    data = request.POST.dict()
```

**How it works:**
1. First attempts to parse `request.body` as JSON (for backward compatibility)
2. If JSON parsing fails (JSONDecodeError), falls back to `request.POST.dict()` which handles form-encoded data
3. Both data formats are now supported seamlessly

**Benefits:**
- ✅ Backward compatible with existing tests that send JSON
- ✅ Works with HTMX `hx-vals` which sends form-encoded data
- ✅ Minimal code change (4 lines)
- ✅ No changes to frontend code required
- ✅ Handles all fields: long_text, short_text_1, quantity, unit_price_net, etc.

### Enhanced Test Coverage

Added a new test case `test_ajax_update_line_form_encoded_data` in `test_ajax_line_update.py`:

```python
def test_ajax_update_line_form_encoded_data(self):
    """Test updating with form-encoded data (simulates real HTMX hx-vals behavior)"""
    url = reverse('auftragsverwaltung:ajax_update_line', ...)
    
    # Simulate HTMX hx-vals sending form-encoded data
    data = {'long_text': 'Form-encoded long text from HTMX'}
    
    response = self.client.post(url, data=data)
    # No content_type='application/json' - simulates HTMX default behavior
    
    self.assertEqual(response.status_code, 200)
    self.line.refresh_from_db()
    self.assertEqual(self.line.long_text, 'Form-encoded long text from HTMX')
```

**Purpose:**
- Validates that form-encoded data is properly handled
- Catches this type of issue in future development
- Documents expected HTMX behavior for developers

## Files Modified

1. **auftragsverwaltung/views.py**: Updated `ajax_update_line` to support both JSON and form-encoded data
2. **auftragsverwaltung/test_ajax_line_update.py**: Added `test_ajax_update_line_form_encoded_data` test case
3. **LANGTEXT_UPDATE_FIX.md**: Updated documentation to reflect the actual fix

## Impact

### Fixed Issues
- ✅ Long text updates in SalesDocumentLine now work correctly
- ✅ All HTMX `hx-vals` POST requests work properly
- ✅ Backward compatible with JSON requests
- ✅ Better test coverage for HTMX scenarios

### Test Results
All tests pass successfully:
- `test_ajax_update_line_long_text`: ✅ PASS (JSON format)
- `test_ajax_update_line_form_encoded_data`: ✅ PASS (Form-encoded format)
- `test_ajax_update_line_multiple_fields`: ✅ PASS
- `test_ajax_update_line_other_document_types`: ✅ PASS
- `test_ajax_update_line_quantity_and_price`: ✅ PASS
- All 17 decimal parsing tests: ✅ PASS

### Security Check
- CodeQL analysis: ✅ No security alerts
- No new vulnerabilities introduced
- Maintains existing security measures

### Scope of Fix
The fix applies to all field updates in `ajax_update_line`:
- `long_text` (primary issue)
- `short_text_1`, `short_text_2`
- `quantity`, `unit_price_net`, `discount`
- `tax_rate_id`, `unit_id`
- `kostenart1_id`, `kostenart2_id`

### No Breaking Changes
- All existing tests pass
- No changes to API contracts
- No changes to frontend code
- No database migrations required

## Deployment Notes

### Requirements
- No new dependencies required
- No database migrations needed
- No environment variable changes
- No frontend code changes

### Rollout
1. The fix is backward compatible
2. No special deployment steps required
3. Works immediately upon deployment
4. Handles both JSON and form-encoded requests automatically

## Lessons Learned

1. **HTMX Default Behavior**: HTMX with `hx-vals` sends form-encoded data by default, not JSON
2. **Data Format Flexibility**: Backend APIs should be flexible enough to handle multiple data formats when appropriate
3. **Test Coverage Gap**: Browser-based HTMX behavior differs from test client behavior - need tests that simulate real HTMX requests
4. **Error Messages Matter**: The detailed JSONDecodeError in server logs was crucial for identifying the root cause
5. **Minimal Changes**: Supporting both formats required only 4 lines of code change

## Alternative Solutions Considered

### 1. Change HTMX to Send JSON (Not Chosen)
Could configure HTMX to send JSON by adding `hx-headers='{"Content-Type": "application/json"}'` to each element.

**Why not chosen:**
- Would require changes to multiple frontend templates
- More error-prone (easy to forget on new elements)
- Less maintainable

### 2. Change Backend to Only Accept Form Data (Not Chosen)
Could change all test cases and backend to only use form-encoded data.

**Why not chosen:**
- Would break backward compatibility
- Larger code change required
- JSON is more flexible for complex data structures

### 3. Flexible Parsing (Chosen ✅)
Accept both JSON and form-encoded data with automatic fallback.

**Why chosen:**
- Minimal code change (4 lines)
- Backward compatible
- Handles both test and production scenarios
- Most robust solution

## References

- Issue: #338
- Related Issues: #336, #337
- HTMX Documentation: https://htmx.org/attributes/hx-vals/
- Django Request/Response: https://docs.djangoproject.com/en/stable/ref/request-response/
