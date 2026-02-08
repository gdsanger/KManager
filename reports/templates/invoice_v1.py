"""
Invoice PDF Template v1

ReportLab-based template for rendering sales invoices.
Supports multi-page layout with repeating headers.
"""
from reportlab.platypus import (
    Paragraph, Spacer, Table, PageBreak, KeepTogether
)
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

from core.services.reporting.registry import register_template
from core.services.reporting.styles import get_default_styles


@register_template('invoice.v1')
class InvoiceTemplateV1:
    """
    Invoice template version 1.
    
    Expected context structure:
    {
        'company': {
            'name': str,
            'address_lines': list[str],
            'tax_number': str,
            'vat_id': str,
            'bank_info': {
                'bank_name': str,
                'iban': str,
                'bic': str,
                'account_holder': str,
            } or None
        },
        'customer': {
            'name': str,
            'address_lines': list[str],
            'country_code': str,
            'vat_id': str or None,
        },
        'doc': {
            'number': str,
            'subject': str,
            'issue_date': str,
            'due_date': str or None,
            'payment_term_text': str,
            'header_html': str,
            'footer_html': str,
        },
        'lines': list[{
            'pos': int,
            'qty': str,
            'unit': str,
            'short_text': str,
            'long_text': str,
            'unit_price_net': str,
            'discount_percent': str,
            'net': str,
            'tax_rate': str,
            'tax': str,
            'gross': str,
        }],
        'totals': {
            'net_0': str,
            'net_7': str,
            'net_19': str,
            'tax_0': str,
            'tax_7': str,
            'tax_19': str,
            'tax_total': str,
            'gross_total': str,
            'net_total': str,
        },
        'tax_notes': {
            'reverse_charge_text': str or None,
            'export_text': str or None,
        }
    }
    """
    
    def build_story(self, context):
        """
        Build the invoice content as a list of Flowables.
        
        Args:
            context: Dictionary with invoice data
            
        Returns:
            List of ReportLab Flowable objects
        """
        story = []
        styles = get_default_styles()
        
        # Custom styles for invoice
        invoice_styles = self._get_invoice_styles(styles)
        
        # Company header (sender)
        story.extend(self._build_company_header(context, invoice_styles))
        
        # Address block
        story.extend(self._build_address_block(context, invoice_styles))
        
        # Document metadata
        story.extend(self._build_document_header(context, invoice_styles))
        
        # Header text from document
        if context['doc'].get('header_html'):
            story.extend(self._build_header_text(context, invoice_styles))
        
        # Line items table
        story.extend(self._build_lines_table(context, invoice_styles))
        
        # Totals section
        story.extend(self._build_totals_section(context, invoice_styles))
        
        # Tax notes
        story.extend(self._build_tax_notes(context, invoice_styles))
        
        # Footer text from document
        if context['doc'].get('footer_html'):
            story.extend(self._build_footer_text(context, invoice_styles))
        
        # Payment terms
        if context['doc'].get('payment_term_text'):
            story.extend(self._build_payment_terms(context, invoice_styles))
        
        return story
    
    def _get_invoice_styles(self, base_styles):
        """Create custom styles for invoice"""
        styles = {}
        
        styles['CompanyHeader'] = ParagraphStyle(
            name='CompanyHeader',
            parent=base_styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            alignment=TA_LEFT,
        )
        
        styles['InvoiceTitle'] = ParagraphStyle(
            name='InvoiceTitle',
            parent=base_styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=8,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
        )
        
        styles['AddressBlock'] = ParagraphStyle(
            name='AddressBlock',
            parent=base_styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=TA_LEFT,
            leading=14,
        )
        
        styles['MetaLabel'] = ParagraphStyle(
            name='MetaLabel',
            parent=base_styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#666666'),
            alignment=TA_LEFT,
        )
        
        styles['MetaValue'] = ParagraphStyle(
            name='MetaValue',
            parent=base_styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
        )
        
        styles['BodyText'] = ParagraphStyle(
            name='BodyText',
            parent=base_styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=TA_LEFT,
            spaceAfter=6,
        )
        
        styles['TaxNote'] = ParagraphStyle(
            name='TaxNote',
            parent=base_styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            alignment=TA_LEFT,
            spaceAfter=4,
            leftIndent=10,
        )
        
        return styles
    
    def _build_company_header(self, context, styles):
        """Build company header (small, at the top)"""
        elements = []
        company = context.get('company', {})
        
        # Company name and address in small font
        header_text = company.get('name', '')
        if company.get('address_lines'):
            header_text += ' · ' + ' · '.join(company['address_lines'])
        
        elements.append(Paragraph(header_text, styles['CompanyHeader']))
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _build_address_block(self, context, styles):
        """Build customer address block"""
        elements = []
        customer = context.get('customer', {})
        
        # Address lines
        if customer.get('address_lines'):
            address_html = '<br/>'.join(customer['address_lines'])
            elements.append(Paragraph(address_html, styles['AddressBlock']))
        
        elements.append(Spacer(1, 1*cm))
        
        return elements
    
    def _build_document_header(self, context, styles):
        """Build document header with metadata"""
        elements = []
        doc = context.get('doc', {})
        
        # Invoice title
        title = f"Rechnung {doc.get('number', '')}"
        elements.append(Paragraph(title, styles['InvoiceTitle']))
        elements.append(Spacer(1, 0.3*cm))
        
        # Metadata table (2 columns)
        meta_data = []
        
        # Issue date
        if doc.get('issue_date'):
            meta_data.append([
                Paragraph('Rechnungsdatum:', styles['MetaLabel']),
                Paragraph(doc['issue_date'], styles['MetaValue']),
            ])
        
        # Due date
        if doc.get('due_date'):
            meta_data.append([
                Paragraph('Fälligkeitsdatum:', styles['MetaLabel']),
                Paragraph(doc['due_date'], styles['MetaValue']),
            ])
        
        # Customer VAT ID
        customer = context.get('customer', {})
        if customer.get('vat_id'):
            meta_data.append([
                Paragraph('USt-IdNr. Kunde:', styles['MetaLabel']),
                Paragraph(customer['vat_id'], styles['MetaValue']),
            ])
        
        # Subject
        if doc.get('subject'):
            meta_data.append([
                Paragraph('Betreff:', styles['MetaLabel']),
                Paragraph(doc['subject'], styles['MetaValue']),
            ])
        
        if meta_data:
            meta_table = Table(meta_data, colWidths=[4*cm, 10*cm])
            meta_table.setStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ])
            elements.append(meta_table)
        
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _build_header_text(self, context, styles):
        """Build header text from document"""
        elements = []
        doc = context.get('doc', {})
        
        # Note: header_html is already sanitized in context builder
        header_html = doc.get('header_html', '')
        if header_html:
            elements.append(Paragraph(header_html, styles['BodyText']))
            elements.append(Spacer(1, 0.3*cm))
        
        return elements
    
    def _build_lines_table(self, context, styles):
        """Build line items table with repeating header"""
        elements = []
        lines = context.get('lines', [])
        
        if not lines:
            return elements
        
        # Table header
        header_row = [
            Paragraph('<b>Pos.</b>', styles['BodyText']),
            Paragraph('<b>Menge</b>', styles['BodyText']),
            Paragraph('<b>Einheit</b>', styles['BodyText']),
            Paragraph('<b>Beschreibung</b>', styles['BodyText']),
            Paragraph('<b>Einzelpreis</b>', styles['BodyText']),
            Paragraph('<b>MwSt.</b>', styles['BodyText']),
            Paragraph('<b>Gesamt</b>', styles['BodyText']),
        ]
        
        # Build table data
        table_data = [header_row]
        
        for line in lines:
            # Main row
            row = [
                Paragraph(str(line['pos']), styles['BodyText']),
                Paragraph(line['qty'], styles['BodyText']),
                Paragraph(line['unit'], styles['BodyText']),
                Paragraph(line['short_text'], styles['BodyText']),
                Paragraph(line['unit_price_net'], styles['BodyText']),
                Paragraph(line['tax_rate'], styles['BodyText']),
                Paragraph(line['net'], styles['BodyText']),
            ]
            table_data.append(row)
            
            # Long text row (if present)
            if line.get('long_text'):
                long_text_row = [
                    '',
                    '',
                    '',
                    Paragraph(f"<i>{line['long_text']}</i>", styles['BodyText']),
                    '',
                    '',
                    '',
                ]
                table_data.append(long_text_row)
        
        # Create table
        table = Table(
            table_data,
            colWidths=[1*cm, 1.5*cm, 1.5*cm, 7*cm, 2.5*cm, 1.5*cm, 2*cm],
            repeatRows=1  # Repeat header on each page
        )
        
        # Table style
        table_style = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('ALIGN', (0, 0), (2, 0), 'LEFT'),
            ('ALIGN', (3, 0), (3, 0), 'LEFT'),
            ('ALIGN', (4, 0), (-1, 0), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Data rows
            ('ALIGN', (0, 1), (2, -1), 'LEFT'),
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),
            ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            
            # Grid
            ('GRID', (0, 0), (-1, 0), 0.5, colors.HexColor('#cccccc')),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#666666')),
        ]
        
        table.setStyle(table_style)
        
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _build_totals_section(self, context, styles):
        """Build tax splits and totals"""
        elements = []
        totals = context.get('totals', {})
        
        # Build totals table (right-aligned)
        totals_data = []
        
        # Tax splits (only show non-zero amounts)
        if totals.get('net_19') and totals['net_19'] != '0,00':
            totals_data.append([
                Paragraph('Netto 19% MwSt.:', styles['MetaLabel']),
                Paragraph(totals['net_19'] + ' €', styles['MetaValue']),
            ])
            totals_data.append([
                Paragraph('MwSt. 19%:', styles['MetaLabel']),
                Paragraph(totals['tax_19'] + ' €', styles['MetaValue']),
            ])
        
        if totals.get('net_7') and totals['net_7'] != '0,00':
            totals_data.append([
                Paragraph('Netto 7% MwSt.:', styles['MetaLabel']),
                Paragraph(totals['net_7'] + ' €', styles['MetaValue']),
            ])
            totals_data.append([
                Paragraph('MwSt. 7%:', styles['MetaLabel']),
                Paragraph(totals['tax_7'] + ' €', styles['MetaValue']),
            ])
        
        if totals.get('net_0') and totals['net_0'] != '0,00':
            totals_data.append([
                Paragraph('Netto 0% MwSt.:', styles['MetaLabel']),
                Paragraph(totals['net_0'] + ' €', styles['MetaValue']),
            ])
        
        # Separator
        if totals_data:
            totals_data.append([
                Paragraph('', styles['MetaLabel']),
                Paragraph('', styles['MetaValue']),
            ])
        
        # Total net
        totals_data.append([
            Paragraph('<b>Summe Netto:</b>', styles['MetaValue']),
            Paragraph('<b>' + totals.get('net_total', '0,00') + ' €</b>', styles['MetaValue']),
        ])
        
        # Total tax
        totals_data.append([
            Paragraph('<b>Summe MwSt.:</b>', styles['MetaValue']),
            Paragraph('<b>' + totals.get('tax_total', '0,00') + ' €</b>', styles['MetaValue']),
        ])
        
        # Separator
        totals_data.append([
            Paragraph('', styles['MetaLabel']),
            Paragraph('', styles['MetaValue']),
        ])
        
        # Total gross (highlighted)
        totals_data.append([
            Paragraph('<b>Rechnungsbetrag:</b>', styles['InvoiceTitle']),
            Paragraph('<b>' + totals.get('gross_total', '0,00') + ' €</b>', styles['InvoiceTitle']),
        ])
        
        # Create table (right-aligned on page)
        totals_table = Table(totals_data, colWidths=[8*cm, 4*cm], hAlign='RIGHT')
        totals_table.setStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            # Line above total
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#666666')),
            ('TOPPADDING', (0, -1), (-1, -1), 6),
        ])
        
        elements.append(totals_table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _build_tax_notes(self, context, styles):
        """Build tax notes (reverse charge, export)"""
        elements = []
        tax_notes = context.get('tax_notes', {})
        
        if tax_notes.get('reverse_charge_text'):
            elements.append(Paragraph(
                '<b>Hinweis:</b> ' + tax_notes['reverse_charge_text'],
                styles['TaxNote']
            ))
        
        if tax_notes.get('export_text'):
            elements.append(Paragraph(
                '<b>Hinweis:</b> ' + tax_notes['export_text'],
                styles['TaxNote']
            ))
        
        if elements:
            elements.append(Spacer(1, 0.3*cm))
        
        return elements
    
    def _build_footer_text(self, context, styles):
        """Build footer text from document"""
        elements = []
        doc = context.get('doc', {})
        
        # Note: footer_html is already sanitized in context builder
        footer_html = doc.get('footer_html', '')
        if footer_html:
            elements.append(Spacer(1, 0.5*cm))
            elements.append(Paragraph(footer_html, styles['BodyText']))
        
        return elements
    
    def _build_payment_terms(self, context, styles):
        """Build payment terms section"""
        elements = []
        doc = context.get('doc', {})
        
        payment_text = doc.get('payment_term_text', '')
        if payment_text:
            elements.append(Spacer(1, 0.3*cm))
            elements.append(Paragraph(
                '<b>Zahlungsbedingungen:</b>',
                styles['MetaValue']
            ))
            elements.append(Paragraph(payment_text, styles['BodyText']))
        
        return elements
    
    def draw_header_footer(self, canvas, doc, context):
        """
        Draw custom header and footer on each page.
        
        Args:
            canvas: ReportLab canvas
            doc: Document object
            context: Invoice context
        """
        canvas.saveState()
        
        # Get page size
        page_width, page_height = doc.pagesize
        
        # Draw footer
        self._draw_footer(canvas, doc, context, page_width, page_height)
        
        canvas.restoreState()
    
    def _draw_footer(self, canvas, doc, context, page_width, page_height):
        """Draw footer with company info and page numbers"""
        company = context.get('company', {})
        
        # Footer line
        canvas.setStrokeColor(colors.HexColor('#cccccc'))
        canvas.setLineWidth(0.5)
        canvas.line(2*cm, 2.5*cm, page_width - 2*cm, 2.5*cm)
        
        # Company info in footer (3 columns)
        footer_y = 2*cm
        footer_font_size = 7
        canvas.setFont('Helvetica', footer_font_size)
        canvas.setFillColor(colors.HexColor('#666666'))
        
        # Column 1: Company and address
        footer_text = company.get('name', '')
        if company.get('address_lines'):
            footer_text += ' | ' + ', '.join(company['address_lines'][:2])
        canvas.drawString(2*cm, footer_y, footer_text)
        
        # Column 2: Tax info
        tax_info = []
        if company.get('tax_number'):
            tax_info.append(f"Steuernr.: {company['tax_number']}")
        if company.get('vat_id'):
            tax_info.append(f"USt-IdNr.: {company['vat_id']}")
        if tax_info:
            canvas.drawString(2*cm, footer_y - 0.35*cm, ' | '.join(tax_info))
        
        # Column 3: Bank info
        bank_info = company.get('bank_info')
        if bank_info and bank_info.get('iban'):
            bank_text = f"IBAN: {bank_info['iban']}"
            if bank_info.get('bic'):
                bank_text += f" | BIC: {bank_info['bic']}"
            canvas.drawString(2*cm, footer_y - 0.7*cm, bank_text)
        
        # Page numbers (right-aligned)
        page_num = canvas.getPageNumber()
        page_text = f"Seite {page_num}"
        canvas.drawRightString(page_width - 2*cm, footer_y, page_text)
