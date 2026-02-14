# SalesDocumentLine Langtext Quill Editor Implementation

**Issue**: #409 - SalesDocument Erfassung SalesDocumentsLine Langtext als HTML mit Quill

**Date**: 2026-02-14

**Status**: ✅ Complete

## Summary

This implementation adds a Quill-based rich text editor modal for editing the `long_text` field of `SalesDocumentLine` objects, along with UX improvements to the position list display.

## Features Implemented

### A) Modal-Based Langtext Editing with Quill

#### User Interface
- **Edit Button**: Each position in the list now has a small edit icon button (📝) to open the Quill editor modal
- **Quill Editor**: Light-Toolbar configuration with:
  - Bold, Italic, Underline formatting
  - Ordered and unordered lists
  - Clean formatting tool
- **Modal Actions**:
  - **Abbrechen (Cancel)**: Closes modal without saving changes
  - **Speichern (Save)**: Persists HTML content and updates preview

#### Technical Implementation
- Modal uses existing `#longtextEditorModal` structure
- Quill editor is initialized on first use and reused for all lines
- JavaScript data store (`lineDataStore`) maintains HTML content for each line
- HTML content is loaded via `.root.innerHTML` (not plain text)
- Empty state detection uses `getText()` for robust handling

#### Data Flow
```
1. User clicks edit button
2. JavaScript loads HTML from lineDataStore
3. Quill displays formatted content
4. User edits content
5. On Save:
   - Get HTML via quillEditor.root.innerHTML
   - Send to server via AJAX
   - Server sanitizes HTML
   - Returns success
   - Update lineDataStore and preview
   - Close modal
```

### B) 2-Line Preview in Position List

#### CSS Implementation
```css
.long-text-preview {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
    min-height: 2.8rem; /* 2 lines * 1.4 line-height */
}
```

#### Features
- Preview shows plain text version (HTML tags stripped)
- Maximum 2 lines visible
- Ellipsis for overflow
- Empty state shows "(kein Langtext)" in italics

### C) Position List Header

#### Structure
```html
<div class="positions-header">
    <div>#</div>
    <div class="positions-header-fields">
        <div>Artikel/Beschreibung</div>
        <div>Menge / Einheit / Preis</div>
        <div>Rabatt</div>
        <div>Betrag</div>
    </div>
    <div></div> <!-- Spacer for delete button -->
</div>
```

#### Visual Design
- Grid layout matching position structure
- Tertiary background color for distinction
- Font weight 600 for emphasis
- Rounded top corners (6px)

## Backend Changes

### HTML Sanitization

#### Location
- `auftragsverwaltung/views.py`
  - `ajax_update_line()` - Line 808
  - `ajax_add_line()` - Line 708

#### Implementation
```python
from .utils import sanitize_html

# In ajax_update_line
if 'long_text' in data:
    line.long_text = sanitize_html(data['long_text'])

# In ajax_add_line
long_text=sanitize_html(long_text) if long_text else '',
```

#### Sanitizer Configuration
Uses existing `sanitize_html()` utility from `auftragsverwaltung/utils.py`:

**Allowed Tags**:
- Text formatting: `p`, `br`, `strong`, `em`, `u`
- Lists: `ul`, `ol`, `li`
- Links: `a` (with href, target, rel attributes)

**Security**:
- Whitelist-based approach using `bleach` library
- Strips disallowed tags (doesn't escape them)
- Dangerous tags (script, iframe, etc.) are removed
- Content within removed tags is preserved

## Testing

### Test Coverage

#### File: `test_issue_377_langtext.py`

1. **test_html_content_is_sanitized**
   - Verifies HTML formatting (bold, italic, lists) is preserved
   - Confirms server-side sanitization is applied
   - Status: ✅ Pass

2. **test_dangerous_html_is_stripped**
   - Verifies script tags are removed
   - Confirms safe tags remain intact
   - Status: ✅ Pass

3. **Existing Tests** (5 tests)
   - All existing langtext tests continue to pass
   - No regression in HTMX form-encoded data handling
   - Status: ✅ Pass (5/5)

#### Test Results
```
Found 7 test(s).
Ran 7 tests in 4.434s
OK
```

### Integration Testing
- Tested with `test_ajax_line_update` (8 tests)
- All tests pass: 15/15
- No breaking changes to existing functionality

## Security Analysis

### CodeQL Results
```
Analysis Result for 'python'. Found 0 alerts:
- **python**: No alerts found.
```

### Security Measures

1. **Server-Side Sanitization**
   - All HTML content is sanitized before storage
   - Uses bleach library with whitelist approach
   - Consistent with project standards

2. **Client-Side Escaping**
   - JavaScript template data uses `escapejs` filter
   - Prevents XSS in JavaScript context
   - Safe HTML rendering in preview

3. **Content Security**
   - No inline script execution possible
   - HTML is always rendered in controlled contexts
   - Preview strips all HTML tags

## Code Quality

### Code Review Feedback Addressed

#### Round 1
1. ✅ Improved HTML escaping using proper Django filters
2. ✅ Extracted HTML stripping into reusable `stripHtmlTags()` function
3. ✅ Enhanced empty state detection using `getText()`
4. ℹ️ Template filter performance: Acceptable for use case

#### Round 2
1. ✅ Fixed variable redeclaration in save handler
2. ✅ Clarified security test comments
3. ✅ Verified `escapejs` is appropriate for JavaScript context

### Best Practices

- **Minimal Changes**: Only modified necessary files
- **Existing Patterns**: Followed project's Quill integration patterns
- **Test Coverage**: Added tests for new functionality
- **No Regression**: All existing tests pass
- **Documentation**: Comprehensive implementation guide

## Files Modified

### Templates
- `templates/auftragsverwaltung/documents/detail.html` (116 lines changed)
  - Added CSS for preview and header
  - Modified position rendering
  - Enhanced JavaScript for Quill integration

### Backend
- `auftragsverwaltung/views.py` (2 lines added)
  - Added sanitization calls

### Tests
- `auftragsverwaltung/test_issue_377_langtext.py` (51 lines added)
  - Added HTML sanitization tests

## Migration Required

❌ **No database migrations required** - Uses existing `long_text` TextField

## Performance Considerations

### Template Rendering
- `striptags` and `truncatewords` filters applied at render time
- Acceptable overhead for typical document sizes (< 100 lines)
- Future optimization: Add cached preview field if needed

### JavaScript
- Quill editor initialized once and reused
- Data store in memory for fast access
- AJAX updates only affected lines

## Compatibility

### Browser Support
- CSS line-clamp: Modern browsers (Chrome, Firefox, Safari, Edge)
- Fallback: overflow hidden + ellipsis
- Quill: Same browser support as existing implementation

### Django Compatibility
- Django 5.2.x (as per project requirements)
- No new dependencies added
- Uses standard Django template filters

## Known Limitations

1. **Preview Truncation**: Done in template (client-side)
   - No performance impact for typical use
   - Could add server-side preview field if needed

2. **Modal Edit Only**: No inline editing
   - This is by design per requirements
   - Ensures consistent HTML formatting

3. **HTML Tag Stripping**: Preview shows plain text
   - Formatting not visible in preview
   - Must open modal to see formatting

## Future Enhancements (Optional)

1. **Toolbar Extensions**
   - Add color/font options if needed
   - Add table support
   - Add image support

2. **Performance Optimization**
   - Cache plain text preview in database
   - Lazy-load Quill editor on demand
   - Paginate position list for large documents

3. **UX Improvements**
   - Show formatting indicators in preview
   - Add keyboard shortcuts for modal
   - Add autosave functionality

## Acceptance Criteria Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| 1. Positions create/edit works | ✅ | All tests pass, no regressions |
| 2. Langtext only editable via modal | ✅ | Inline textarea removed |
| 3. Max 2-line preview | ✅ | CSS line-clamp implemented |
| 4. Modal Cancel/Save work correctly | ✅ | Cancel closes without save, Save persists |
| 5. UI updates after save | ✅ | Preview refreshed via JavaScript |
| 6. Header with field labels | ✅ | Grid-based header added |
| 7. Tests present and passing | ✅ | 7/7 tests pass, no regressions |

## Conclusion

✅ **Implementation Complete**

All requirements from issue #409 have been successfully implemented:
- Modal-based Quill editor for HTML content editing
- 2-line preview with proper CSS truncation
- Position list header with field labels
- Server-side HTML sanitization
- Comprehensive test coverage
- Zero security vulnerabilities
- No breaking changes

The implementation follows project standards, maintains backward compatibility, and provides a solid foundation for future enhancements.
