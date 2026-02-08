# WeasyPrint Import Error Fix Summary

## Problem

Users reported getting the error "WeasyPrint is not installed. Install it with: pip install weasyprint" even though WeasyPrint was correctly installed in their environment. This was occurring on Python 3.13.5 with WeasyPrint 63.1.

## Root Cause

The original code in `core/printing/weasyprint_renderer.py` was catching only `ImportError` when trying to import WeasyPrint. However, WeasyPrint can fail to import for reasons other than not being installed:

1. **Missing system dependencies**: WeasyPrint requires system libraries like Pango, Cairo, and GDK-PixBuf. If these are missing or incompatible, WeasyPrint may raise an `OSError` during import.
2. **Incompatible Python version**: Some WeasyPrint versions may have compatibility issues with specific Python versions.
3. **Corrupted installation**: The package may be installed but damaged.

When any of these issues occurred, the code would set `HTML = None` and later raise a generic "not installed" error, which was misleading and didn't help users diagnose the actual problem.

## Solution

The fix improves error handling in two ways:

### 1. Capture Specific Exceptions
Changed from catching only `ImportError` to catching both `ImportError` and `OSError`:

```python
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except (ImportError, OSError) as e:
    # Store the actual error for diagnostics
    _weasyprint_import_error = e
    HTML = None
    CSS = None
    FontConfiguration = None
```

### 2. Provide Detailed Error Messages
When initialization fails, the code now:
- Shows the actual exception type and message
- Provides context-specific hints based on the error type
- Helps users distinguish between "not installed" vs "failed to load"

**Example for ModuleNotFoundError:**
```
WeasyPrint could not be imported.
Actual error: ModuleNotFoundError: No module named 'weasyprint'
WeasyPrint is not installed. Install it with: pip install weasyprint
```

**Example for OSError (missing system dependency):**
```
WeasyPrint could not be imported.
Actual error: OSError: libpango-1.0.so.0: cannot open shared object file
WeasyPrint is installed but failed to load. This may be due to:
- Missing system dependencies (e.g., Pango, Cairo, GDK-PixBuf)
- Incompatible Python version
- Corrupted installation

Try reinstalling: pip install --force-reinstall weasyprint
```

## Testing

- All 14 existing tests pass
- Demo script successfully generates PDFs
- Error messages have been verified for both scenarios (not installed vs failed to load)
- No security issues detected by CodeQL

## Files Changed

- `core/printing/weasyprint_renderer.py`: Improved exception handling and error messaging

## Impact

Users will now get actionable error messages that help them:
1. Understand the actual problem (not just "not installed")
2. Take appropriate action based on the specific error
3. Reduce support burden from misleading error messages

## Related Issue

- Issue #344: "Exception Value: WeasyPrint is not installed. Install it with: pip install weasyprint"
