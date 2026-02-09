# Issue #359 Fix: Fehler bei SalesDocument - Speichern von Positionen

## Problem Statement

When working with multiple positions in a SalesDocument, changes were only saved for the last position. Other positions would return HTTP 200 but the data was not actually persisted to the database.

**Symptoms:**
- Multiple positions in a document
- Changes made to Kurztext (short text), Artikelauswahl (article selection), Menge (quantity), and Langtext/Beschreibung (long text/description)
- Only the last position's changes were saved to the database
- Other positions returned HTTP 200 but data was not saved
- Data appeared to be stored somewhere (in memory) but not in the database

## Root Cause Analysis

The issue was caused by a **missing `hx-vals` attribute** on the `long_text` textarea field in the document detail template.

### Technical Details

**Location:** `templates/auftragsverwaltung/documents/detail.html` (lines 459-466)

**Before (Broken):**
```html
<textarea class="form-control form-control-sm line-long-text" 
          name="long_text"
          rows="2" 
          placeholder="Langtext"
          hx-post="{% url 'auftragsverwaltung:ajax_update_line' doc_key document.pk line.pk %}"
          hx-trigger="change, keyup changed delay:500ms"
          hx-swap="none">{{ line.long_text }}</textarea>
```

**After (Fixed):**
```html
<textarea class="form-control form-control-sm line-long-text" 
          name="long_text"
          rows="2" 
          placeholder="Langtext"
          hx-post="{% url 'auftragsverwaltung:ajax_update_line' doc_key document.pk line.pk %}"
          hx-trigger="change, keyup changed delay:500ms"
          hx-vals='js:{"long_text": this.value}'
          hx-swap="none">{{ line.long_text }}</textarea>
```

### Why This Caused the Issue

1. **Without `hx-vals`**: HTMX sends **all form fields** via form-encoded data when the textarea changes
2. **With multiple positions**: When you have 3 positions on the page, all their textareas with `name="long_text"` get submitted together
3. **Data confusion**: The form data contains multiple `long_text` fields, causing the wrong values to be processed for each position
4. **Last position works**: The last position's data happens to be the final value in the form submission, so it gets saved correctly

### Comparison with Other Fields

All other fields (quantity, unit_price_net, short_text_1, etc.) already had `hx-vals` attributes:

```html
<!-- Short text 1 - CORRECT -->
<input ... hx-vals='js:{"short_text_1": this.value}' ...>

<!-- Quantity - CORRECT -->
<input ... hx-vals='js:{"quantity": parseFloat(this.value) || 0}' ...>

<!-- Unit price - CORRECT -->
<input ... hx-vals='js:{"unit_price_net": parseFloat(this.value) || 0}' ...>

<!-- Long text - WAS MISSING -->
<textarea ... hx-post="..." ...>
```

## Solution

### 1. Template Fix (Primary Issue)

**File:** `templates/auftragsverwaltung/documents/detail.html`

Added the missing `hx-vals` attribute to the long_text textarea:

```html
hx-vals='js:{"long_text": this.value}'
```

This ensures HTMX sends **only the long_text value** in the correct format, matching the behavior of all other fields.

### 2. View Enhancement (Secondary Enhancement)

**File:** `auftragsverwaltung/views.py`

Added support for `item_id` field in the `ajax_update_line` view to properly handle article selection:

```python
# Update fields
if 'item_id' in data:
    item_id = normalize_foreign_key_id(data['item_id'])
    if item_id is not None:
        line.item = get_object_or_404(Item, pk=item_id)
    else:
        line.item = None
```

This was discovered during analysis - the JavaScript code (lines 1732-1740 in detail.html) sends item_id when an article is selected via autocomplete, but the view wasn't handling it.

**Updated Response:**
```python
'line': {
    'id': line.pk,
    'item_id': line.item.pk if line.item else None,  # NEW
    'short_text_1': line.short_text_1,
    ...
}
```

### 3. Tests (Verification)

**File:** `auftragsverwaltung/test_multiple_position_save.py`

Created comprehensive tests to verify the fix:

- `test_multiple_positions_long_text_updates`: Validates that long_text updates are saved for all positions
- `test_multiple_positions_short_text_updates`: Validates that short_text updates work correctly
- `test_multiple_positions_quantity_and_price_updates`: Validates quantity and price updates

**Test Results:**
- All 3 new tests pass
- All 7 existing tests in `test_ajax_line_update` pass
- All 10 tests in `test_document_calculation` pass
- **Total: 20 tests pass with 0 failures**

## Impact

### Before the Fix
- Users editing multiple positions would lose data
- Only the last position's changes would be saved
- Confusion about where data was being stored
- Potential data loss for users

### After the Fix
- All position updates are saved correctly to the database
- Each position maintains its own data independently
- Article selection properly links items to positions
- Consistent behavior across all document types (invoices, quotes, orders)

## Security

**CodeQL Analysis:** ✅ No security vulnerabilities found

## Files Changed

1. `templates/auftragsverwaltung/documents/detail.html` - Added `hx-vals` to long_text textarea
2. `auftragsverwaltung/views.py` - Added item_id handling and updated response
3. `auftragsverwaltung/test_multiple_position_save.py` - New comprehensive test file

## Verification Steps

To verify the fix works:

1. Create a SalesDocument (invoice, quote, or order)
2. Add 3+ positions to the document
3. Edit different fields in each position:
   - Position 1: Change long_text to "Text 1"
   - Position 2: Change long_text to "Text 2"  
   - Position 3: Change long_text to "Text 3"
4. Verify in the database that all three positions have the correct long_text values
5. Repeat with other fields (quantity, price, short_text)

## Related Documentation

- Issue #337: Previous fix for AJAX line updates
- `SALESDOCUMENT_POSITION_IMPROVEMENTS.md`: Position entry redesign documentation
- `SALESDOCUMENT_DETAILVIEW_IMPLEMENTATION.md`: Detail view implementation guide

## Conclusion

This fix resolves a critical bug that was causing data loss when users edited multiple positions in a document. The root cause was a simple missing attribute that caused HTMX to send malformed data. The fix is minimal, focused, and thoroughly tested.
