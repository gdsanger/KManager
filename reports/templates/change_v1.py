"""
Change Report Template v1

Example report template demonstrating the Core Report Service.
"""
from reportlab.platypus import Paragraph, Spacer, Table
from reportlab.lib.units import cm

from core.services.reporting.registry import register_template
from core.services.reporting.styles import get_default_styles, get_table_style
from core.services.reporting.canvas import draw_standard_header_footer


@register_template('change.v1')
class ChangeReportV1:
    """
    Change report template version 1.
    
    Expected context keys:
    - title: str - Report title
    - change_id: str - Change identifier
    - date: str - Change date
    - description: str - Change description
    - items: list[dict] - List of change items with keys: position, description, status
    """
    
    def build_story(self, context):
        """
        Build the report content (story) as a list of Flowables.
        
        Args:
            context: Dictionary with report data
            
        Returns:
            List of ReportLab Flowable objects
        """
        story = []
        styles = get_default_styles()
        
        # Title
        title = context.get('title', 'Change Report')
        story.append(Paragraph(title, styles['ReportHeader']))
        story.append(Spacer(1, 0.5*cm))
        
        # Change metadata
        change_id = context.get('change_id', 'N/A')
        date = context.get('date', 'N/A')
        
        story.append(Paragraph(f"<b>Change ID:</b> {change_id}", styles['ReportBody']))
        story.append(Paragraph(f"<b>Datum:</b> {date}", styles['ReportBody']))
        story.append(Spacer(1, 0.3*cm))
        
        # Description
        description = context.get('description', '')
        if description:
            story.append(Paragraph("<b>Beschreibung:</b>", styles['ReportSubHeader']))
            story.append(Paragraph(description, styles['ReportBody']))
            story.append(Spacer(1, 0.5*cm))
        
        # Items table
        items = context.get('items', [])
        if items:
            story.append(Paragraph("<b>Änderungen:</b>", styles['ReportSubHeader']))
            story.append(Spacer(1, 0.2*cm))
            
            # Build table data
            table_data = [['Pos.', 'Beschreibung', 'Status']]
            for item in items:
                table_data.append([
                    str(item.get('position', '')),
                    item.get('description', ''),
                    item.get('status', ''),
                ])
            
            # Create table
            table = Table(table_data, colWidths=[2*cm, 10*cm, 3*cm], repeatRows=1)
            table.setStyle(get_table_style())
            
            story.append(table)
            story.append(Spacer(1, 0.5*cm))
        
        # Additional notes
        notes = context.get('notes', '')
        if notes:
            story.append(Paragraph("<b>Bemerkungen:</b>", styles['ReportSubHeader']))
            story.append(Paragraph(notes, styles['ReportBody']))
        
        return story
    
    def draw_header_footer(self, canvas, doc, context):
        """
        Draw custom header and footer on each page.
        
        Args:
            canvas: ReportLab canvas
            doc: Document object
            context: Report context
        """
        # Use standard header/footer with report title
        title = context.get('title', 'Change Report')
        footer_context = {'report_title': title}
        draw_standard_header_footer(canvas, doc, footer_context)
