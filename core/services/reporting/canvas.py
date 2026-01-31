"""
Canvas helpers for headers, footers, and page numbers
"""
from reportlab.lib.units import cm
from reportlab.lib import colors


def add_page_number(canvas, doc):
    """
    Add page numbers in the format 'Page X of Y' to the footer.
    
    Args:
        canvas: The canvas object
        doc: The document object
    """
    page_num = canvas.getPageNumber()
    text = f"Seite {page_num}"
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(colors.HexColor('#666666'))
    canvas.drawRightString(doc.pagesize[0] - 2*cm, 1.5*cm, text)


def draw_standard_header_footer(canvas, doc, context):
    """
    Draw standard header and footer on each page.
    
    Args:
        canvas: The canvas object
        doc: The document object
        context: Report context dictionary
    """
    canvas.saveState()
    
    # Draw header line
    canvas.setStrokeColor(colors.HexColor('#4a5568'))
    canvas.setLineWidth(1)
    canvas.line(2*cm, doc.pagesize[1] - 2*cm, doc.pagesize[0] - 2*cm, doc.pagesize[1] - 2*cm)
    
    # Draw footer line
    canvas.line(2*cm, 2*cm, doc.pagesize[0] - 2*cm, 2*cm)
    
    # Add page number
    add_page_number(canvas, doc)
    
    # Add report title in footer if available
    if 'report_title' in context:
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(2*cm, 1.5*cm, context['report_title'])
    
    canvas.restoreState()


class NumberedCanvas:
    """
    Canvas wrapper that tracks page numbers for 'Page X of Y' formatting.
    
    This is used as a two-pass approach:
    1. First pass: Generate PDF and count pages
    2. Second pass: Generate PDF with correct page numbers
    """
    def __init__(self):
        self.page_count = 0
    
    def __call__(self, canvas, doc):
        """Called for each page during PDF generation"""
        self.page_count = max(self.page_count, canvas.getPageNumber())
        
        canvas.saveState()
        
        # Draw header line
        canvas.setStrokeColor(colors.HexColor('#4a5568'))
        canvas.setLineWidth(1)
        canvas.line(2*cm, doc.pagesize[1] - 2*cm, doc.pagesize[0] - 2*cm, doc.pagesize[1] - 2*cm)
        
        # Draw footer line
        canvas.line(2*cm, 2*cm, doc.pagesize[0] - 2*cm, 2*cm)
        
        # Add page number "Page X of Y"
        page_num = canvas.getPageNumber()
        text = f"Seite {page_num} von {self.page_count}"
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawRightString(doc.pagesize[0] - 2*cm, 1.5*cm, text)
        
        canvas.restoreState()
