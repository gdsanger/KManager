"""
Context Builder for Sales Document Invoice PDF

Provides stable, DTO-like context for invoice PDF rendering.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import List, Optional, Dict, Any
from auftragsverwaltung.services.document_calculation import DocumentCalculationService
from auftragsverwaltung.services.tax_determination import TaxDeterminationService
from auftragsverwaltung.utils import sanitize_html


@dataclass
class CompanyContext:
    """Company information for invoice header"""
    name: str
    address_lines: List[str]
    logo_url: Optional[str]
    tax_number: str
    vat_id: str
    bank_info: Optional[Dict[str, str]]


@dataclass
class CustomerContext:
    """Customer information for invoice"""
    name: str
    address_lines: List[str]
    country_code: str
    vat_id: Optional[str]


@dataclass
class DocumentContext:
    """Document metadata"""
    number: str
    subject: str
    issue_date: str
    due_date: Optional[str]
    payment_term_text: str
    header_html: str
    footer_html: str


@dataclass
class LineContext:
    """Single line item in the invoice"""
    pos: int
    qty: str
    unit: str
    short_text: str
    long_text: str
    unit_price_net: str
    discount_percent: str
    net: str
    tax_rate: str
    tax: str
    gross: str


@dataclass
class TotalsContext:
    """Tax split and total amounts"""
    net_0: str
    net_7: str
    net_19: str
    tax_0: str
    tax_7: str
    tax_19: str
    tax_total: str
    gross_total: str
    net_total: str


@dataclass
class TaxNotesContext:
    """Tax-related notes and hints"""
    reverse_charge_text: Optional[str]
    export_text: Optional[str]


class SalesDocumentInvoiceContextBuilder:
    """
    Builds a stable, DTO-like context for invoice PDF rendering.
    
    Avoids passing model objects directly to templates to ensure
    stability and prevent template errors if models change.
    """
    
    def __init__(self, sales_document):
        """
        Initialize context builder with a sales document.
        
        Args:
            sales_document: SalesDocument instance
        """
        self.document = sales_document
        self.company = sales_document.company
        self.customer = sales_document.customer
    
    def build(self) -> Dict[str, Any]:
        """
        Build complete context for invoice rendering.
        
        Returns:
            Dictionary with all context data
        """
        return {
            'company': self._build_company_context(),
            'customer': self._build_customer_context(),
            'doc': self._build_document_context(),
            'lines': self._build_lines_context(),
            'totals': self._build_totals_context(),
            'tax_notes': self._build_tax_notes_context(),
        }
    
    def _build_company_context(self) -> Dict[str, Any]:
        """Build company/sender information"""
        address_lines = []
        if self.company.adresse:
            address_lines.append(self.company.adresse)
        if self.company.plz and self.company.ort:
            address_lines.append(f"{self.company.plz} {self.company.ort}")
        if self.company.land:
            address_lines.append(self.company.land)
        
        bank_info = None
        if self.company.kreditinstitut or self.company.iban:
            bank_info = {
                'bank_name': self.company.kreditinstitut or '',
                'iban': self.company.iban or '',
                'bic': self.company.bic or '',
                'account_holder': self.company.kontoinhaber or '',
            }
        
        context = CompanyContext(
            name=self.company.name or '',
            address_lines=address_lines,
            logo_url=None,  # Not implemented yet
            tax_number=self.company.steuernummer or '',
            vat_id=self.company.ust_id_nr or '',
            bank_info=bank_info,
        )
        
        return asdict(context)
    
    def _build_customer_context(self) -> Dict[str, Any]:
        """Build customer address block"""
        if not self.customer:
            # Fallback for documents without customer
            context = CustomerContext(
                name='',
                address_lines=[],
                country_code='',
                vat_id=None,
            )
            return asdict(context)
        
        address_lines = []
        
        # Company name if business customer
        if self.customer.firma:
            address_lines.append(self.customer.firma)
        
        # Personal name
        if self.customer.name:
            address_lines.append(self.customer.name)
        
        # Street
        if self.customer.strasse:
            address_lines.append(self.customer.strasse)
        
        # ZIP and city
        if self.customer.plz and self.customer.ort:
            address_lines.append(f"{self.customer.plz} {self.customer.ort}")
        
        # Country
        if self.customer.land:
            address_lines.append(self.customer.land)
        
        context = CustomerContext(
            name=self.customer.firma or self.customer.name or '',
            address_lines=address_lines,
            country_code=self.customer.country_code or 'DE',
            vat_id=self.customer.vat_id,
        )
        
        return asdict(context)
    
    def _build_document_context(self) -> Dict[str, Any]:
        """Build document metadata"""
        # Format dates
        issue_date_str = self.document.issue_date.strftime('%d.%m.%Y') if self.document.issue_date else ''
        due_date_str = self.document.due_date.strftime('%d.%m.%Y') if self.document.due_date else None
        
        # Sanitize HTML fields
        header_html = sanitize_html(self.document.header_text) if self.document.header_text else ''
        footer_html = sanitize_html(self.document.footer_text) if self.document.footer_text else ''
        
        context = DocumentContext(
            number=self.document.number or '',
            subject=self.document.subject or '',
            issue_date=issue_date_str,
            due_date=due_date_str,
            payment_term_text=self.document.payment_term_text or '',
            header_html=header_html,
            footer_html=footer_html,
        )
        
        return asdict(context)
    
    def _build_lines_context(self) -> List[Dict[str, Any]]:
        """Build line items with calculations"""
        lines = []
        
        # Get all lines ordered by position
        document_lines = self.document.lines.select_related('tax_rate', 'unit').order_by('position_no')
        
        for line in document_lines:
            # Skip lines not included in totals
            if not line.is_included_in_totals():
                continue
            
            # Calculate line totals
            line_net, line_tax, line_gross = DocumentCalculationService.calculate_line_totals(line)
            
            # Build short text (combine short_text_1 and short_text_2)
            short_text_parts = []
            if line.short_text_1:
                short_text_parts.append(line.short_text_1)
            if line.short_text_2:
                short_text_parts.append(line.short_text_2)
            short_text = ' '.join(short_text_parts) if short_text_parts else line.description
            
            # Format discount
            discount_percent = f"{line.discount}%" if line.discount and line.discount > 0 else ''
            
            line_context = LineContext(
                pos=line.position_no,
                qty=self._format_quantity(line.quantity),
                unit=line.unit.code if line.unit else '',
                short_text=short_text,
                long_text=line.long_text or '',
                unit_price_net=self._format_currency(line.unit_price_net),
                discount_percent=discount_percent,
                net=self._format_currency(line_net),
                tax_rate=self._format_percentage(line.tax_rate.rate),
                tax=self._format_currency(line_tax),
                gross=self._format_currency(line_gross),
            )
            
            lines.append(asdict(line_context))
        
        return lines
    
    def _build_totals_context(self) -> Dict[str, Any]:
        """Build tax-split totals"""
        # Initialize tax buckets
        net_by_rate = {
            Decimal('0.00'): Decimal('0.00'),
            Decimal('0.07'): Decimal('0.00'),
            Decimal('0.19'): Decimal('0.00'),
        }
        tax_by_rate = {
            Decimal('0.00'): Decimal('0.00'),
            Decimal('0.07'): Decimal('0.00'),
            Decimal('0.19'): Decimal('0.00'),
        }
        
        # Get all lines ordered by position
        document_lines = self.document.lines.select_related('tax_rate').order_by('position_no')
        
        for line in document_lines:
            # Skip lines not included in totals
            if not line.is_included_in_totals():
                continue
            
            # Calculate line totals
            line_net, line_tax, line_gross = DocumentCalculationService.calculate_line_totals(line)
            
            # Add to appropriate bucket
            rate = line.tax_rate.rate
            if rate not in net_by_rate:
                # For rates other than 0%, 7%, 19%, we'll add them to the closest bucket or ignore
                # For MVP, we'll just add to existing buckets or skip
                continue
            
            net_by_rate[rate] += line_net
            tax_by_rate[rate] += line_tax
        
        # Calculate totals
        total_net = sum(net_by_rate.values())
        total_tax = sum(tax_by_rate.values())
        total_gross = total_net + total_tax
        
        context = TotalsContext(
            net_0=self._format_currency(net_by_rate[Decimal('0.00')]),
            net_7=self._format_currency(net_by_rate[Decimal('0.07')]),
            net_19=self._format_currency(net_by_rate[Decimal('0.19')]),
            tax_0=self._format_currency(tax_by_rate[Decimal('0.00')]),
            tax_7=self._format_currency(tax_by_rate[Decimal('0.07')]),
            tax_19=self._format_currency(tax_by_rate[Decimal('0.19')]),
            tax_total=self._format_currency(total_tax),
            gross_total=self._format_currency(total_gross),
            net_total=self._format_currency(total_net),
        )
        
        return asdict(context)
    
    def _build_tax_notes_context(self) -> Dict[str, Any]:
        """Build tax notes (reverse charge, export, etc.)"""
        reverse_charge_text = None
        export_text = None
        
        if not self.customer:
            context = TaxNotesContext(
                reverse_charge_text=None,
                export_text=None,
            )
            return asdict(context)
        
        # Determine tax scenario
        tax_label = TaxDeterminationService.get_tax_label(
            self.customer,
            None,  # We don't need item_tax_rate here, just customer analysis
        )
        
        if 'Reverse Charge' in tax_label:
            reverse_charge_text = (
                "Steuerschuldnerschaft des Leistungsempfängers gemäß § 13b UStG. "
                "Die Umsatzsteuer schuldet der Leistungsempfänger."
            )
        elif 'Export' in tax_label or 'Nicht-EU' in tax_label:
            export_text = (
                "Steuerfreie Ausfuhrlieferung gemäß § 4 Nr. 1a UStG in Verbindung mit § 6 UStG."
            )
        
        context = TaxNotesContext(
            reverse_charge_text=reverse_charge_text,
            export_text=export_text,
        )
        
        return asdict(context)
    
    def _format_currency(self, amount: Decimal) -> str:
        """
        Format currency amount in German number format.
        
        Converts from: 1234.56 (Decimal internal format)
        To: 1.234,56 (German display format with thousands separator and decimal comma)
        """
        return f"{amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    def _format_percentage(self, rate: Decimal) -> str:
        """Format percentage"""
        percentage = (rate * 100).quantize(Decimal('0.01'))
        return f"{percentage}%"
    
    def _format_quantity(self, qty: Decimal) -> str:
        """Format quantity (remove trailing zeros)"""
        # Normalize to remove trailing zeros
        normalized = qty.normalize()
        return str(normalized)
