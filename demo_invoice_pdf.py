"""
Demo script for Invoice PDF Generation

Creates test data and generates a sample invoice PDF to demonstrate the feature.
Run with: python manage.py shell < demo_invoice_pdf.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
django.setup()

from core.models import Mandant, TaxRate, PaymentTerm, Item, Adresse, Unit
from auftragsverwaltung.models import DocumentType, SalesDocument, SalesDocumentLine
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from core.services.reporting import ReportService
from datetime import date
from decimal import Decimal


def create_demo_invoice():
    """Create a demo invoice with test data"""
    
    print("=" * 80)
    print("Demo: Invoice PDF Generation")
    print("=" * 80)
    
    # 1. Get or create Company
    print("\n1. Setting up Company...")
    company, _ = Mandant.objects.get_or_create(
        name='Demo GmbH',
        defaults={
            'adresse': 'Musterstraße 123',
            'plz': '10115',
            'ort': 'Berlin',
            'land': 'Deutschland',
            'steuernummer': '12/345/67890',
            'ust_id_nr': 'DE123456789',
            'kreditinstitut': 'Berliner Sparkasse',
            'iban': 'DE89370400440532013000',
            'bic': 'COBADEFFXXX',
            'kontoinhaber': 'Demo GmbH',
            'telefon': '+49 30 12345678',
            'email': 'info@demo-gmbh.de'
        }
    )
    print(f"   ✓ Company: {company.name}")
    
    # 2. Get or create Customer
    print("\n2. Setting up Customer...")
    customer, _ = Adresse.objects.get_or_create(
        firma='Kunden AG',
        name='Max Mustermann',
        defaults={
            'adressen_type': 'KUNDE',
            'strasse': 'Kundenweg 42',
            'plz': '20095',
            'ort': 'Hamburg',
            'land': 'Deutschland',
            'country_code': 'DE',
            'vat_id': 'DE987654321',
            'is_business': True,
            'is_eu': False,
            'email': 'max.mustermann@kunden-ag.de'
        }
    )
    print(f"   ✓ Customer: {customer.firma}")
    
    # 3. Get or create Document Type
    print("\n3. Setting up Document Type...")
    doc_type, _ = DocumentType.objects.get_or_create(
        key='invoice',
        defaults={
            'name': 'Rechnung',
            'prefix': 'R',
            'is_invoice': True,
            'requires_due_date': True,
            'is_active': True
        }
    )
    print(f"   ✓ Document Type: {doc_type.name}")
    
    # 4. Get or create Tax Rates
    print("\n4. Setting up Tax Rates...")
    tax_19, _ = TaxRate.objects.get_or_create(
        code='19%',
        defaults={
            'rate': Decimal('0.19'),
            'is_active': True
        }
    )
    tax_7, _ = TaxRate.objects.get_or_create(
        code='7%',
        defaults={
            'rate': Decimal('0.07'),
            'is_active': True
        }
    )
    print(f"   ✓ Tax Rates: 19%, 7%")
    
    # 5. Get or create Unit
    print("\n5. Setting up Unit...")
    unit, _ = Unit.objects.get_or_create(
        code='Stk',
        defaults={
            'name': 'Stück',
            'is_active': True
        }
    )
    print(f"   ✓ Unit: {unit.name}")
    
    # 6. Get or create Payment Term
    print("\n6. Setting up Payment Term...")
    payment_term, _ = PaymentTerm.objects.get_or_create(
        name='14 Tage netto',
        defaults={
            'net_days': 14,
            'is_default': True
        }
    )
    print(f"   ✓ Payment Term: {payment_term.name}")
    
    # 7. Create Invoice Document
    print("\n7. Creating Invoice Document...")
    invoice = SalesDocument.objects.create(
        company=company,
        document_type=doc_type,
        customer=customer,
        number='R26-DEMO-001',
        status='OPEN',
        issue_date=date(2026, 2, 8),
        due_date=date(2026, 2, 22),
        subject='Demo Rechnung - Invoice PDF Feature',
        header_text='<p>Vielen Dank für Ihren Auftrag. Wir erlauben uns, Ihnen folgende Leistungen in Rechnung zu stellen:</p>',
        footer_text='<p><strong>Zahlungsinformationen:</strong><br/>Bitte überweisen Sie den Betrag unter Angabe der Rechnungsnummer auf unser Konto.</p><p>Bei Fragen stehen wir Ihnen gerne zur Verfügung.</p>',
        payment_term_text='Zahlbar innerhalb von 14 Tagen ohne Abzug.',
        payment_term=payment_term
    )
    print(f"   ✓ Invoice: {invoice.number}")
    
    # 8. Add Invoice Lines
    print("\n8. Adding Invoice Lines...")
    
    # Line 1: Software License (19% VAT)
    SalesDocumentLine.objects.create(
        document=invoice,
        position_no=1,
        line_type='NORMAL',
        is_selected=True,
        short_text_1='Software-Lizenz',
        short_text_2='Professional Edition',
        long_text='Jahres-Lizenz für 5 Benutzer, inkl. Support und Updates',
        description='Software-Lizenz Professional Edition',
        unit=unit,
        quantity=Decimal('5.0000'),
        unit_price_net=Decimal('199.00'),
        tax_rate=tax_19,
        is_discountable=True,
        discount=Decimal('0.00')
    )
    
    # Line 2: Consulting Service (19% VAT)
    SalesDocumentLine.objects.create(
        document=invoice,
        position_no=2,
        line_type='NORMAL',
        is_selected=True,
        short_text_1='Beratungsleistung',
        short_text_2='System-Integration',
        long_text='Analyse, Konzeption und Integration des Systems in die bestehende IT-Infrastruktur',
        description='Beratungsleistung System-Integration',
        unit=unit,
        quantity=Decimal('8.0000'),
        unit_price_net=Decimal('150.00'),
        tax_rate=tax_19,
        is_discountable=True,
        discount=Decimal('0.00')
    )
    
    # Line 3: Training (7% VAT - educational service)
    SalesDocumentLine.objects.create(
        document=invoice,
        position_no=3,
        line_type='NORMAL',
        is_selected=True,
        short_text_1='Schulung',
        short_text_2='Anwender-Training',
        long_text='Ganztägiges Training für bis zu 10 Teilnehmer, inkl. Schulungsunterlagen',
        description='Schulung Anwender-Training',
        unit=unit,
        quantity=Decimal('1.0000'),
        unit_price_net=Decimal('890.00'),
        tax_rate=tax_7,
        is_discountable=True,
        discount=Decimal('0.00')
    )
    
    # Line 4: Support Package (19% VAT)
    SalesDocumentLine.objects.create(
        document=invoice,
        position_no=4,
        line_type='NORMAL',
        is_selected=True,
        short_text_1='Support-Paket',
        short_text_2='Premium Support',
        long_text='24/7 Support mit garantierter Reaktionszeit von 2 Stunden',
        description='Support-Paket Premium Support',
        unit=unit,
        quantity=Decimal('12.0000'),
        unit_price_net=Decimal('89.00'),
        tax_rate=tax_19,
        is_discountable=True,
        discount=Decimal('0.00')
    )
    
    print(f"   ✓ Added 4 invoice lines")
    
    # 9. Calculate totals
    print("\n9. Calculating Totals...")
    from auftragsverwaltung.services import DocumentCalculationService
    result = DocumentCalculationService.recalculate(invoice, persist=True)
    print(f"   ✓ Total Net:   {result.total_net} EUR")
    print(f"   ✓ Total Tax:   {result.total_tax} EUR")
    print(f"   ✓ Total Gross: {result.total_gross} EUR")
    
    # 10. Generate PDF
    print("\n10. Generating PDF...")
    builder = SalesDocumentInvoiceContextBuilder(invoice)
    context = builder.build()
    pdf_bytes = ReportService.render('invoice.v1', context)
    
    # Save PDF to file
    output_path = '/tmp/demo_invoice.pdf'
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    print(f"   ✓ PDF generated: {output_path}")
    print(f"   ✓ PDF size: {len(pdf_bytes):,} bytes")
    
    print("\n" + "=" * 80)
    print("Demo completed successfully!")
    print("=" * 80)
    print(f"\nInvoice ID: {invoice.pk}")
    print(f"Invoice Number: {invoice.number}")
    print(f"PDF Location: {output_path}")
    print(f"\nTo view the PDF, open: {output_path}")
    print(f"To download via endpoint: /auftragsverwaltung/documents/{invoice.pk}/pdf/")
    print("\n")
    
    return invoice


if __name__ == '__main__':
    invoice = create_demo_invoice()
