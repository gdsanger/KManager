"""
PDF Render Service

Core service for rendering HTML templates to PDF.
"""

from typing import Optional
import logging
from pathlib import Path

from django.template.loader import render_to_string
from django.conf import settings

from .interfaces import IPdfRenderer
from .dto import PdfResult
from .weasyprint_renderer import WeasyPrintRenderer
from .sanitizer import sanitize_html

logger = logging.getLogger(__name__)


class PdfRenderServiceError(Exception):
    """Base exception for PDF render service errors"""
    pass


class TemplateNotFoundError(PdfRenderServiceError):
    """Template not found"""
    pass


class RenderError(PdfRenderServiceError):
    """Error during rendering"""
    pass


class PdfRenderService:
    """
    Core service for PDF report generation.
    
    Provides a clean pipeline:
    1. Template loading (name provided by caller)
    2. HTML rendering via Django templates
    3. PDF rendering via IPdfRenderer
    4. Result delivery (bytes + metadata)
    
    Note: No document-type specific logic - that belongs in calling modules.
    """
    
    def __init__(self, renderer: Optional[IPdfRenderer] = None):
        """
        Initialize PDF render service.
        
        Args:
            renderer: PDF renderer implementation. If None, uses default WeasyPrint renderer.
        """
        self._renderer = renderer or self._get_default_renderer()
    
    def _get_default_renderer(self) -> IPdfRenderer:
        """Get default PDF renderer based on settings."""
        # For now, always use WeasyPrint
        # In the future, this could read from settings.PDF_RENDERER
        return WeasyPrintRenderer()
    
    def render(
        self,
        template_name: str,
        context: dict,
        *,
        base_url: str,
        filename: Optional[str] = None,
        sanitize: bool = False
    ) -> PdfResult:
        """
        Render template to PDF.
        
        Args:
            template_name: Django template path (e.g., 'printing/invoice.html')
            context: Template context dictionary
            base_url: Base URL for resolving static assets
            filename: Optional filename for the PDF
            sanitize: Whether to sanitize HTML content before rendering
            
        Returns:
            PdfResult with PDF bytes and metadata
            
        Raises:
            TemplateNotFoundError: If template doesn't exist
            RenderError: If rendering fails
        """
        try:
            # 1. Render HTML via Django template
            logger.debug(f"Rendering template: {template_name}")
            html = render_to_string(template_name, context)
            
            # 2. Optional sanitization
            if sanitize:
                logger.debug("Sanitizing HTML content")
                html = sanitize_html(html)
            
            # 3. Render PDF
            logger.debug(f"Rendering PDF with base_url: {base_url}")
            pdf_bytes = self._renderer.render_html_to_pdf(html, base_url)
            
            # 4. Create result
            result = PdfResult(
                pdf_bytes=pdf_bytes,
                filename=filename
            )
            
            logger.info(
                f"Successfully rendered PDF: {filename or 'unnamed'} "
                f"({len(pdf_bytes)} bytes)"
            )
            
            return result
            
        except Exception as e:
            if "TemplateDoesNotExist" in str(type(e).__name__):
                raise TemplateNotFoundError(
                    f"Template not found: {template_name}"
                ) from e
            else:
                raise RenderError(
                    f"Failed to render PDF: {e}"
                ) from e
