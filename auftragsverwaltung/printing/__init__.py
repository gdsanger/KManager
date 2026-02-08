"""
Printing module for auftragsverwaltung.

Provides context builders and utilities for PDF generation.
"""

from .context import SalesDocumentInvoiceContextBuilder

__all__ = [
    'SalesDocumentInvoiceContextBuilder',
]
