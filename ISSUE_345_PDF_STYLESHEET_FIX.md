# Issue #345: PDF Stylesheet Loading Fix

**Date:** 2026-02-08  
**Status:** ✅ RESOLVED  
**Agira Item ID:** 345

## Problem

PDF generation was failing with the following error:
```
ERROR 2026-02-08 21:32:56,991 Failed to load stylesheet at file:///static/printing/print.css: 
URLError: <urlopen error [Errno 2] No such file or directory: '/static/printing/print.css'>
```

### Affected Components
- `auftragsverwaltung/documents/1/pdf/` - PDF generation endpoint
- `core/templates/printing/base.html` - Base printing template
- `auftragsverwaltung/templates/printing/orders/invoice.html` - Invoice template

## Root Cause Analysis

Two issues were causing the stylesheet loading failure:

1. **Incorrect base_url in view code**
   - The view used `settings.BASE_DIR / 'static'` as the base URL
   - This points to the project root's `static/` directory
   - The `print.css` file is actually located in `core/static/printing/print.css`
   - Django's static files are distributed across multiple app directories

2. **Absolute path in template**
   - The template used `<link rel="stylesheet" href="/static/printing/print.css">`
   - The leading `/` makes this an absolute path from the filesystem root
   - WeasyPrint tries to load from `file:///static/printing/print.css` (literal root path)
   - Should be relative to the base_url instead

## Solution

### 1. Created Static File Finder Utility

**File:** `core/printing/utils.py`

Added `get_static_base_url()` function that:
- Uses Django's `staticfiles.finders` to locate static files in app directories
- Finds the `printing/print.css` file to determine the correct static directory
- Falls back to `STATIC_ROOT` in production (after `collectstatic`)
- Returns a proper `file://` URL for WeasyPrint

```python
def get_static_base_url() -> str:
    """
    Get the base URL for static assets for PDF generation.
    Handles both development (app-specific static dirs) and 
    production (STATIC_ROOT after collectstatic).
    """
    # Implementation details...
```

### 2. Updated View Code

**File:** `auftragsverwaltung/views.py`

Changed from:
```python
static_root = settings.BASE_DIR / 'static'
base_url = f'file://{static_root}/'
```

To:
```python
from core.printing import get_static_base_url
base_url = get_static_base_url()
```

### 3. Fixed Template Path

**File:** `core/templates/printing/base.html`

Changed from:
```html
<link rel="stylesheet" href="/static/printing/print.css">
```

To:
```html
<link rel="stylesheet" href="printing/print.css">
```

The relative path allows WeasyPrint to properly resolve it against the base_url.

### 4. Updated Demo Script

**File:** `demo_printing.py`

Also updated to use the new utility function for consistency.

## Testing

### Unit Tests
- Added 2 new tests for `get_static_base_url()` utility
- All 16 existing printing framework tests still pass
- Test verifies correct URL construction and file accessibility

### Manual Testing
- Demo script runs successfully without errors
- PDF is generated with stylesheet correctly applied
- Verified output: 12KB PDF with proper formatting

### Code Quality
- ✅ Code review completed - all feedback addressed
- ✅ Security scan completed - no vulnerabilities found

## Files Changed

1. **Core Printing Module**
   - `core/printing/utils.py` - NEW: Static file finder utility
   - `core/printing/__init__.py` - Export new utility function
   - `core/templates/printing/base.html` - Fix CSS path

2. **View Updates**
   - `auftragsverwaltung/views.py` - Use new utility

3. **Demo & Tests**
   - `demo_printing.py` - Use new utility
   - `core/test_printing.py` - Add tests for utility

## Benefits

1. **Development Environment**
   - Works without running `collectstatic`
   - Automatically finds static files in app directories
   - No manual configuration needed

2. **Production Environment**
   - Uses `STATIC_ROOT` when available
   - Compatible with standard Django deployment practices
   - Works with collected static files

3. **Maintainability**
   - Centralized logic in reusable utility function
   - Well-documented and tested
   - Follows Django best practices

## Related Documentation

- [Printing Framework Implementation](PRINTING_FRAMEWORK_IMPLEMENTATION.md)
- [Core Printing Framework](core/printing/README.md)
- [Printing Framework Docs](docs/PRINTING_FRAMEWORK.md)

## Deployment Notes

No special deployment steps required. The fix works in both:
- Development (without `collectstatic`)
- Production (with `collectstatic`)

The utility automatically detects the environment and uses the appropriate static file resolution strategy.
