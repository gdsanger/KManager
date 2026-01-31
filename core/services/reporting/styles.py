"""
Common PDF styles for reports

Provides consistent styling across all reports.
"""
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.units import cm


def get_default_styles():
    """
    Get default report styles.
    
    Returns:
        StyleSheet with predefined styles for reports
    """
    styles = getSampleStyleSheet()
    
    # Header style
    styles.add(ParagraphStyle(
        name='ReportHeader',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_LEFT,
    ))
    
    # Subheader style
    styles.add(ParagraphStyle(
        name='ReportSubHeader',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        spaceBefore=10,
        alignment=TA_LEFT,
    ))
    
    # Body text style
    styles.add(ParagraphStyle(
        name='ReportBody',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=6,
        alignment=TA_LEFT,
    ))
    
    # Footer style
    styles.add(ParagraphStyle(
        name='ReportFooter',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
    ))
    
    # Table header style
    styles.add(ParagraphStyle(
        name='TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.white,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
    ))
    
    # Table cell style
    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#1a1a1a'),
        alignment=TA_LEFT,
    ))
    
    return styles


def get_table_style():
    """
    Get default table style for reports.
    
    Returns:
        TableStyle with common formatting
    """
    from reportlab.platypus import TableStyle
    
    return TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ])
