"""
WeasyPrint PDF Renderer

Infrastructure adapter for WeasyPrint rendering engine.
"""

from typing import Optional
import logging

# Store the import error for better diagnostics
_weasyprint_import_error = None

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except Exception as e:
    # Allow imports to succeed even if WeasyPrint is not installed
    # This allows the module to be imported during migrations, etc.
    # Store the actual error for better diagnostics
    _weasyprint_import_error = e
    HTML = None
    CSS = None
    FontConfiguration = None

from .interfaces import IPdfRenderer

logger = logging.getLogger(__name__)


class WeasyPrintRenderer(IPdfRenderer):
    """
    PDF renderer using WeasyPrint engine.
    
    Converts HTML to PDF with support for:
    - CSS Paged Media (@page rules)
    - Static assets (images, fonts, CSS)
    - Running headers/footers
    - Page counters
    """
    
    def __init__(self, additional_css: Optional[str] = None):
        """
        Initialize WeasyPrint renderer.
        
        Args:
            additional_css: Optional additional CSS to apply
        """
        if HTML is None:
            # Provide detailed error message with the actual import error
            error_msg = "WeasyPrint could not be imported."
            
            if _weasyprint_import_error is not None:
                # Include the actual error that occurred
                error_msg += f"\n\nActual error: {type(_weasyprint_import_error).__name__}: {_weasyprint_import_error}"
                
                # Add helpful hints based on error type
                if isinstance(_weasyprint_import_error, ModuleNotFoundError):
                    error_msg += "\n\nWeasyPrint is not installed. Install it with: pip install weasyprint"
                else:
                    error_msg += "\n\nWeasyPrint is installed but failed to load. This may be due to:"
                    error_msg += "\n- Missing system dependencies (e.g., Pango, Cairo, GDK-PixBuf)"
                    error_msg += "\n- Incompatible Python version"
                    error_msg += "\n- Corrupted installation"
                    error_msg += "\n\nTry reinstalling: pip install --force-reinstall weasyprint"
            else:
                error_msg += "\n\nInstall it with: pip install weasyprint"
            
            raise ImportError(error_msg)
        
        self.additional_css = additional_css
        self._font_config = FontConfiguration()
    
    def render_html_to_pdf(self, html: str, base_url: str) -> bytes:
        """
        Render HTML to PDF using WeasyPrint.
        
        Args:
            html: HTML content to render
            base_url: Base URL for resolving relative paths
            
        Returns:
            PDF content as bytes
            
        Raises:
            Exception: If rendering fails
        """
        try:
            # Create HTML document
            html_doc = HTML(string=html, base_url=base_url)
            
            # Prepare stylesheets
            stylesheets = []
            if self.additional_css:
                stylesheets.append(CSS(
                    string=self.additional_css,
                    font_config=self._font_config
                ))
            
            # Render to PDF
            pdf_bytes = html_doc.write_pdf(
                stylesheets=stylesheets,
                font_config=self._font_config
            )
            
            logger.info(
                f"Successfully rendered PDF ({len(pdf_bytes)} bytes) "
                f"from HTML ({len(html)} chars)"
            )
            
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Failed to render PDF: {e}", exc_info=True)
            raise RuntimeError(f"PDF rendering failed: {e}") from e
