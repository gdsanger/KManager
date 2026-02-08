"""
Utility functions for the printing framework.
"""

from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.finders import find as find_static


def get_static_base_url() -> str:
    """
    Get the base URL for static assets for PDF generation.
    
    This function handles both development and production scenarios:
    - In development: Uses Django's static file finders to locate files in app directories
    - In production: Uses STATIC_ROOT if collectstatic has been run
    
    The function specifically searches for 'printing/print.css' to determine the correct
    static directory for the printing framework. This ensures that the printing module's
    static files (CSS, images, fonts) are accessible during PDF generation.
    
    Returns:
        str: File URL pointing to the static files directory
        
    Note:
        For WeasyPrint to properly resolve static files referenced in templates,
        it needs a base_url that points to a directory where all static files
        are accessible. This function provides that URL.
        
    Raises:
        No exceptions raised. Falls back to BASE_DIR/static if print.css not found.
    """
    # Check if STATIC_ROOT is configured and exists (production setup)
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        static_root_path = Path(static_root)
        if static_root_path.exists():
            # In production with collectstatic run
            return f'file://{static_root_path.resolve()}/'
    
    # In development, we need to handle multiple static directories
    # Try to find a common static file to determine which directory to use
    # First, try to find the print.css in app-specific static directories
    print_css_path = find_static('printing/print.css')
    if print_css_path:
        # Get the parent directory that contains the 'printing' folder
        # e.g., /path/to/core/static/printing/print.css -> /path/to/core/static/
        print_css_path = Path(print_css_path)
        static_dir = print_css_path.parent.parent
        return f'file://{static_dir.resolve()}/'
    
    # Fallback: use first STATICFILES_DIRS entry
    staticfiles_dirs = getattr(settings, 'STATICFILES_DIRS', [])
    if staticfiles_dirs:
        return f'file://{Path(staticfiles_dirs[0]).resolve()}/'
    
    # Last resort: use BASE_DIR/static
    return f'file://{(settings.BASE_DIR / "static").resolve()}/'
