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
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate

from core.models import ReportDocument
from core.services.base import ServiceError
from .registry import get_template


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
            # Margins: 2cm on all sides (using cm units from reportlab)
            from reportlab.lib.units import cm
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2.5*cm,
                bottomMargin=2.5*cm,
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
                # Two-pass approach for "Page X of Y" numbering
                # First pass: count pages
                first_pass_buffer = io.BytesIO()
                first_pass_doc = SimpleDocTemplate(
                    first_pass_buffer,
                    pagesize=A4,
                    rightMargin=2*cm,
                    leftMargin=2*cm,
                    topMargin=2.5*cm,
                    bottomMargin=2.5*cm,
                )
                
                # Simple canvas for first pass (just count pages)
                page_count = [0]  # Use list to allow modification in closure
                def count_pages(canvas, doc):
                    page_count[0] = max(page_count[0], canvas.getPageNumber())
                
                first_pass_doc.build(story, onFirstPage=count_pages, onLaterPages=count_pages)
                
                # Second pass: render with correct page numbers
                # Rebuild story as it was consumed in first pass
                story = template.build_story(context)
                
                def on_page_with_total(canvas, doc):
                    canvas.saveState()
                    # Draw header line
                    canvas.setStrokeColor(colors.HexColor('#4a5568'))
                    canvas.setLineWidth(1)
                    canvas.line(2*cm, doc.pagesize[1] - 2*cm, doc.pagesize[0] - 2*cm, doc.pagesize[1] - 2*cm)
                    # Draw footer line
                    canvas.line(2*cm, 2*cm, doc.pagesize[0] - 2*cm, 2*cm)
                    # Add page number
                    page_num = canvas.getPageNumber()
                    text = f"Seite {page_num} von {page_count[0]}"
                    canvas.setFont('Helvetica', 9)
                    canvas.setFillColor(colors.HexColor('#666666'))
                    canvas.drawRightString(doc.pagesize[0] - 2*cm, 1.5*cm, text)
                    canvas.restoreState()
                
                doc.build(story, onFirstPage=on_page_with_total, onLaterPages=on_page_with_total)
            
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
