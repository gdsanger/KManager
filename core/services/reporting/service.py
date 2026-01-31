"""
Core Report Service

Provides generic infrastructure for PDF report generation, versioning and storage.
"""
import hashlib
import io
from typing import Optional, Dict, Any

from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate

from core.models import ReportDocument
from core.services.base import ServiceError
from .registry import get_template
from .canvas import NumberedCanvas


class ReportServiceError(ServiceError):
    """Base exception for report service errors"""
    pass


class TemplateNotFoundError(ReportServiceError):
    """Template not found in registry"""
    pass


class ReportRenderError(ReportServiceError):
    """Error during report rendering"""
    pass


class ReportService:
    """
    Core service for PDF report generation and storage.
    
    Provides:
    - PDF rendering using ReportLab
    - Template registry integration
    - Versioning and context snapshots
    - Reproducible generation
    """
    
    @staticmethod
    def render(report_key: str, context: dict) -> bytes:
        """
        Render a report to PDF bytes.
        
        Args:
            report_key: Report type identifier (e.g., 'change.v1')
            context: Serializable dictionary with report data
            
        Returns:
            PDF file as bytes
            
        Raises:
            TemplateNotFoundError: If report_key is not registered
            ReportRenderError: If rendering fails
        """
        try:
            # Get template from registry
            template = get_template(report_key)
        except KeyError as e:
            raise TemplateNotFoundError(str(e)) from e
        
        try:
            # Create PDF in memory
            buffer = io.BytesIO()
            
            # Create document with A4 page size
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2*72,  # 2cm in points
                leftMargin=2*72,
                topMargin=2.5*72,
                bottomMargin=2.5*72,
            )
            
            # Build story (content) using template
            story = template.build_story(context)
            
            # Determine header/footer callback
            if hasattr(template, 'draw_header_footer'):
                # Custom header/footer from template
                def on_page(canvas, doc):
                    template.draw_header_footer(canvas, doc, context)
                doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
            else:
                # Use numbered canvas for standard page numbers
                numbered_canvas = NumberedCanvas()
                doc.build(story, onFirstPage=numbered_canvas, onLaterPages=numbered_canvas)
            
            # Get PDF bytes
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            return pdf_bytes
            
        except Exception as e:
            raise ReportRenderError(f"Failed to render report '{report_key}': {str(e)}") from e
    
    @staticmethod
    def generate_and_store(
        report_key: str,
        object_type: str,
        object_id: str | int,
        context: dict,
        metadata: Optional[dict] = None,
        created_by: Optional[User] = None,
    ) -> ReportDocument:
        """
        Generate a report and store it with context snapshot.
        
        Args:
            report_key: Report type identifier (e.g., 'change.v1')
            object_type: Type of related object (e.g., 'change', 'invoice')
            object_id: ID of related object
            context: Serializable dictionary with report data
            metadata: Optional additional metadata
            created_by: User who created the report
            
        Returns:
            ReportDocument instance
            
        Raises:
            TemplateNotFoundError: If report_key is not registered
            ReportRenderError: If rendering fails
        """
        # Render PDF
        pdf_bytes = ReportService.render(report_key, context)
        
        # Calculate SHA256 hash for integrity
        sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
        
        # Create filename
        filename = f"{report_key}_{object_type}_{object_id}.pdf"
        
        # Create ReportDocument
        report = ReportDocument(
            report_key=report_key,
            object_type=object_type,
            object_id=str(object_id),
            context_json=context,
            template_version=report_key,  # Use report_key as version for now
            sha256=sha256_hash,
            metadata=metadata or {},
            created_by=created_by,
        )
        
        # Save PDF file
        report.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
        
        # Save model instance
        report.save()
        
        return report
