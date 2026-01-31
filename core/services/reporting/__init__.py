"""
Core Reporting Service

Provides generic infrastructure for PDF report generation, versioning and storage.
"""

from .service import ReportService, ReportServiceError, TemplateNotFoundError, ReportRenderError
from .registry import register_template, get_template, list_templates

__all__ = [
    "ReportService",
    "ReportServiceError",
    "TemplateNotFoundError",
    "ReportRenderError",
    "register_template",
    "get_template",
    "list_templates",
]
