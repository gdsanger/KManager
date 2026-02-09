"""
Context builders for SalesDocument PDF rendering.

Builds stable, DTO-like contexts for invoice templates.
"""

from decimal import Decimal
from typing import Any, Optional
from core.printing.interfaces import IContextBuilder


class SalesDocumentInvoiceContextBuilder(IContextBuilder):
    """
    Context builder for SalesDocument invoice PDFs.
    
    Builds a stable, DTO-like render context suitable for invoice templates.
    No model objects are passed directly to templates.
    """
    
    def build_context(self, obj: Any, *, company: Any = None) -> dict:
        """
        Build template context from SalesDocument.
        
        Args:
            obj: SalesDocument instance
            company: Optional Mandant instance (defaults to obj.company)
            
        Returns:
            Template context dictionary with company, customer, doc, lines, totals, tax_notes
        """
        from auftragsverwaltung.models import SalesDocument
        
        if not isinstance(obj, SalesDocument):
            raise ValueError(f"Expected SalesDocument, got {type(obj)}")
        
        document = obj
        company = company or document.company
        
        # Build context sections
        context = {
            'company': self._build_company_context(company),
            'customer': self._build_customer_context(document.customer) if document.customer else None,
            'doc': self._build_document_context(document),
            'lines': self._build_lines_context(document),
            'totals': self._build_totals_context(document),
            'tax_notes': self._build_tax_notes(document),
        }
        
        return context
    
    def get_template_name(self, obj: Any) -> str:
        """
        Get template name for document type.
        
        Args:
            obj: SalesDocument instance
            
        Returns:
            Template name/path
        """
        return 'printing/orders/invoice.html'
    
    def _build_company_context(self, company) -> dict:
        """Build company/letterhead context."""
        from django.conf import settings
        import os
        
        address_lines = []
        if company.adresse:
            address_lines.append(company.adresse)
        if company.plz and company.ort:
            address_lines.append(f"{company.plz} {company.ort}")
        if company.land:
            address_lines.append(company.land)
        
        # Bank info (optional)
        bank_info = []
        if company.kreditinstitut:
            bank_info.append(f"Bank: {company.kreditinstitut}")
        if company.iban:
            bank_info.append(f"IBAN: {company.iban}")
        if company.bic:
            bank_info.append(f"BIC: {company.bic}")
        if company.kontoinhaber and company.kontoinhaber != company.name:
            bank_info.append(f"Kontoinhaber: {company.kontoinhaber}")
        
        # Logo URL - construct absolute file path for WeasyPrint
        logo_url = None
        if company.logo_path:
            # WeasyPrint needs an absolute file path or URL
            logo_file_path = os.path.join(settings.MEDIA_ROOT, company.logo_path)
            if os.path.exists(logo_file_path):
                # Use file:// URL for WeasyPrint
                logo_url = f"file://{logo_file_path}"
        
        return {
            'name': company.name,
            'address_lines': address_lines,
            'logo_url': logo_url,
            'tax_number': company.steuernummer or '',
            'vat_id': company.ust_id_nr or '',
            'bank_info': bank_info if bank_info else None,
            'phone': company.telefon or '',
            'fax': company.fax or '',
            'email': company.email or '',
            'internet': company.internet or '',
        }
    
    def _build_customer_context(self, customer) -> dict:
        """Build customer address block context."""
        address_lines = []
        
        # Company name or personal name
        if customer.firma:
            address_lines.append(customer.firma)
        if customer.name:
            if customer.anrede:
                address_lines.append(f"{customer.get_anrede_display()} {customer.name}")
            else:
                address_lines.append(customer.name)
        
        # Street address
        if customer.strasse:
            address_lines.append(customer.strasse)
        
        # City/ZIP
        if customer.plz and customer.ort:
            address_lines.append(f"{customer.plz} {customer.ort}")
        
        # Country (only if not default)
        if customer.land and customer.land.upper() not in ['DEUTSCHLAND', 'GERMANY', 'DE']:
            address_lines.append(customer.land)
        
        return {
            'name': customer.firma or customer.name,
            'address_lines': address_lines,
            'country_code': customer.country_code or 'DE',
            'vat_id': customer.vat_id or '',
        }
    
    def _build_document_context(self, document) -> dict:
        """Build document metadata context."""
        return {
            'number': document.number,
            'subject': document.subject or '',
            'issue_date': document.issue_date,
            'due_date': document.due_date,
            'paymentterm_text': document.payment_term_text or '',
            'header_html': document.header_text or '',
            'footer_html': document.footer_text or '',
            'reference_number': document.reference_number or '',
            'notes_public': document.notes_public or '',
        }
    
    def _build_lines_context(self, document) -> list:
        """Build lines context for positions table."""
        lines = []
        
        for line in document.lines.select_related('tax_rate', 'unit').order_by('position_no'):
            # Only include NORMAL lines or selected OPTIONAL/ALTERNATIVE lines
            if line.line_type == 'NORMAL' or line.is_selected:
                lines.append({
                    'pos': line.position_no,
                    'qty': line.quantity,
                    'unit': line.unit.symbol if line.unit else '',
                    'short_text': line.short_text_1 or '',
                    'long_text': line.long_text or '',
                    'unit_price_net': line.unit_price_net,
                    'discount_percent': line.discount,
                    'net': line.line_net,
                    'tax_rate': line.tax_rate.rate,
                    'tax': line.line_tax,
                    'gross': line.line_gross,
                })
        
        return lines
    
    def _build_totals_context(self, document) -> dict:
        """Build totals context with tax splits."""
        # Calculate tax splits (0%, 7%, 19%)
        lines = document.lines.select_related('tax_rate').order_by('position_no')
        
        net_0 = Decimal('0.00')
        net_7 = Decimal('0.00')
        net_19 = Decimal('0.00')
        tax_0 = Decimal('0.00')
        tax_7 = Decimal('0.00')
        tax_19 = Decimal('0.00')
        
        for line in lines:
            # Only include NORMAL lines or selected OPTIONAL/ALTERNATIVE lines
            if line.line_type == 'NORMAL' or line.is_selected:
                rate = line.tax_rate.rate
                
                if rate == Decimal('0.00'):
                    net_0 += line.line_net
                    tax_0 += line.line_tax
                elif rate == Decimal('0.07'):
                    net_7 += line.line_net
                    tax_7 += line.line_tax
                elif rate == Decimal('0.19'):
                    net_19 += line.line_net
                    tax_19 += line.line_tax
        
        return {
            'net_0': net_0,
            'net_7': net_7,
            'net_19': net_19,
            'tax_0': tax_0,
            'tax_7': tax_7,
            'tax_19': tax_19,
            'tax_total': document.total_tax,
            'net_total': document.total_net,
            'gross_total': document.total_gross,
        }
    
    def _build_tax_notes(self, document) -> dict:
        """
        Build tax notes context for EU/reverse charge.
        
        Note: This only provides display hints. No recalculation happens here.
        """
        customer = document.customer
        tax_notes = {
            'reverse_charge_text': None,
            'export_text': None,
        }
        
        if not customer:
            return tax_notes
        
        # EU reverse charge logic
        if customer.is_eu and customer.country_code != 'DE' and customer.is_business and customer.vat_id:
            tax_notes['reverse_charge_text'] = (
                'Steuerschuldnerschaft des Leistungsempfängers (Reverse Charge) gemäß Art. 196 MwStSystRL. '
                'Die Umsatzsteuer ist vom Leistungsempfänger zu entrichten.'
            )
        
        # Export/third country
        if not customer.is_eu and customer.country_code != 'DE':
            tax_notes['export_text'] = (
                'Steuerfreie Ausfuhrlieferung gemäß § 4 Nr. 1a i.V.m. § 6 UStG.'
            )
        
        return tax_notes
