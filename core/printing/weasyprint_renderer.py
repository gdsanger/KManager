"""
WeasyPrint PDF Renderer

Infrastructure adapter for WeasyPrint rendering engine.
"""

from typing import Optional
import logging

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    # Allow imports to succeed even if WeasyPrint is not installed
    # This allows the module to be imported during migrations, etc.
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
            raise ImportError(
                "WeasyPrint is not installed. "
                "Install it with: pip install weasyprint"
            )
        
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
