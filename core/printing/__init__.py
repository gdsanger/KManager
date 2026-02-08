"""
Core Printing Framework

Provides modular, extensible PDF generation from HTML templates using WeasyPrint.
"""

from .interfaces import IPdfRenderer, IContextBuilder
from .dto import PdfResult
from .service import PdfRenderService
from .sanitizer import sanitize_html

__all__ = [
    'IPdfRenderer',
    'IContextBuilder',
    'PdfResult',
    'PdfRenderService',
    'sanitize_html',
]
