"""
Core Printing Framework

Provides modular, extensible PDF generation from HTML templates using WeasyPrint.
"""

from .interfaces import IPdfRenderer, IContextBuilder
from .dto import PdfResult
from .service import PdfRenderService
from .sanitizer import sanitize_html
from .utils import get_static_base_url

__all__ = [
    'IPdfRenderer',
    'IContextBuilder',
    'PdfResult',
    'PdfRenderService',
    'sanitize_html',
    'get_static_base_url',
]
