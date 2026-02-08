# Fix for Issue #338: Long Text Saves as "undefined"

## Problem Description

After the initial fix in PR #339 that resolved the JSON parsing error, a new issue emerged:
- When editing the long text (Langtext) field in a SalesDocumentLine, the text was being saved as the literal string "undefined" instead of the actual text content
- No error messages appeared, but the data was incorrect

## Root Cause

The issue was in the HTMX configuration for the long_text textarea field:

```html
<textarea class="form-control form-control-sm line-long-text" 
          hx-vals='js:{"long_text": this.value}'>
```

### Why This Failed

1. **JavaScript Context Issue**: When HTMX evaluated `this.value` in the `hx-vals='js:{...}'` expression, the `this` keyword was not properly bound to the textarea element
2. **Timing Problem**: With the `hx-trigger="change, keyup changed delay:500ms"`, the evaluation context might have been different from the expected textarea element
3. **Result**: The JavaScript expression evaluated to `undefined`, which was then converted to the string "undefined" and sent to the server

## Solution Implemented

### The Fix

Replaced the `hx-vals` approach with the standard HTML form pattern:

**Before:**
```html
<textarea class="form-control form-control-sm line-long-text" 
          rows="2" 
          placeholder="Langtext"
          hx-post="{% url 'auftragsverwaltung:ajax_update_line' doc_key document.pk line.pk %}"
          hx-trigger="change, keyup changed delay:500ms"
          hx-vals='js:{"long_text": this.value}'
          hx-swap="none">{{ line.long_text }}</textarea>
```

**After:**
```html
<textarea class="form-control form-control-sm line-long-text" 
          name="long_text"
          rows="2" 
          placeholder="Langtext"
          hx-post="{% url 'auftragsverwaltung:ajax_update_line' doc_key document.pk line.pk %}"
          hx-trigger="change, keyup changed delay:500ms"
          hx-swap="none">{{ line.long_text }}</textarea>
```

### Key Changes

1. **Added `name="long_text"`**: This tells HTMX to automatically include the textarea's value in the POST request
2. **Removed `hx-vals='js:{"long_text": this.value}'`**: No longer needed; HTMX handles it automatically

### How It Works

When the textarea triggers an HTMX request:
1. HTMX automatically collects all form inputs from the triggering element
2. Since the textarea has `name="long_text"`, HTMX includes `long_text=<actual_value>` in the POST data
3. The backend receives the data as form-encoded: `long_text=<actual_text_content>`
4. The backend parses it correctly (thanks to PR #339's dual format support)
5. The actual text content is saved to the database

## Benefits of This Approach

1. ✅ **Simpler**: Uses standard HTML form attributes
2. ✅ **More Reliable**: No JavaScript context issues
3. ✅ **HTMX Best Practice**: Recommended approach for simple value passing
4. ✅ **Consistent**: Follows standard form handling patterns
5. ✅ **No Breaking Changes**: All existing tests still pass

## Testing

### Test Results

All existing tests pass:
```
test_ajax_update_line_form_encoded_data ... ok
test_ajax_update_line_long_text ... ok
test_ajax_update_line_multiple_fields ... ok
test_ajax_update_line_other_document_types ... ok
test_ajax_update_line_quantity_and_price ... ok

Ran 5 tests in 3.157s
OK
```

### Manual Testing Recommended

To verify the fix works in production:
1. Navigate to a sales document (e.g., `/auftragsverwaltung/documents/invoice/5/`)
2. Find a line item with a long text field
3. Edit the long text content
4. Tab out or wait for the auto-save
5. Verify the text is saved correctly (not as "undefined")
6. Refresh the page and confirm the text persists

## Files Modified

1. **templates/auftragsverwaltung/documents/detail.html**: 
   - Added `name="long_text"` attribute to textarea
   - Removed `hx-vals='js:{"long_text": this.value}'` attribute

## Technical Notes

### Why Use `name` Instead of `hx-vals`?

**`name` attribute approach (✅ Used in this fix):**
- Browser/HTMX automatically includes the value
- No JavaScript evaluation needed
- Works reliably across all scenarios
- Standard HTML form practice

**`hx-vals` approach (❌ Problematic):**
- Requires JavaScript evaluation
- `this` context can be unreliable
- More complex and error-prone
- Only needed for computed values or transformations

### When to Use Each Approach

**Use `name` attribute when:**
- Sending simple field values as-is
- The field is a standard form input
- You want reliability and simplicity

**Use `hx-vals='js:{...}'` when:**
- You need to transform the value (e.g., `parseFloat()`, `parseInt()`)
- You need to send computed values
- You need to combine multiple fields into one value
- The `this` context is guaranteed to be correct

### Compatibility Notes

This fix is compatible with:
- The form-encoded data parsing added in PR #339
- All existing JSON-based test cases
- The HTMX triggers (`change, keyup changed delay:500ms`)
- All other line update functionality

## Related Issues and PRs

- Issue #338: Original bug report
- Issue #336, #337: Related issues
- PR #339: Fixed JSON parsing error (prerequisite for this fix)

## Conclusion

The fix is minimal (changing one line), reliable, and follows HTMX best practices. By using the standard `name` attribute instead of JavaScript evaluation, we ensure the textarea value is always correctly captured and sent to the server, regardless of the trigger context or timing.
