#!/usr/bin/env python
"""
Manual test script for PDF invoice generation.

Creates test data and generates sample PDFs to verify the implementation.
"""

import os
import sys
from pathlib import Path
from decimal import Decimal
from datetime import date, timedelta

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
import django
django.setup()

from django.conf import settings
from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from core.models import Mandant, Adresse, TaxRate, Unit
from core.printing import PdfRenderService


def create_test_data():
    """Create test data for PDF generation."""
    print("Creating test data...")
    
    # Get or create company
    company, _ = Mandant.objects.get_or_create(
        name='KManager Demo GmbH',
        defaults={
            'adresse': 'Musterstraße 123',
            'plz': '10115',
            'ort': 'Berlin',
            'land': 'Deutschland',
            'steuernummer': '12/345/67890',
            'ust_id_nr': 'DE123456789',
            'geschaeftsfuehrer': 'Max Mustermann, Dr. Erika Musterfrau',
            'handelsregister': 'HRB 12345 B, Amtsgericht Berlin-Charlottenburg',
            'kreditinstitut': 'Demo Bank',
            'iban': 'DE89370400440532013000',
            'bic': 'COBADEFFXXX',
            'kontoinhaber': 'KManager Demo GmbH',
            'telefon': '030-12345678',
            'fax': '030-12345679',
            'email': 'info@kmanager-demo.de',
            'internet': 'https://www.kmanager-demo.de'
        }
    )
    
    # Get or create customer
    customer, _ = Adresse.objects.get_or_create(
        firma='Mustermann GmbH',
        defaults={
            'name': 'Max Mustermann',
            'strasse': 'Kundenweg 42',
            'plz': '20095',
            'ort': 'Hamburg',
            'land': 'Deutschland',
            'country_code': 'DE',
            'is_eu': False,
            'is_business': True,
            'vat_id': 'DE987654321'
        }
    )
    
    # Get or create document type
    doc_type, _ = DocumentType.objects.get_or_create(
        key='rechnung',
        defaults={
            'name': 'Rechnung',
            'prefix': 'R',
            'is_invoice': True,
            'requires_due_date': True
        }
    )
    
    # Get or create tax rates
    tax_19, _ = TaxRate.objects.get_or_create(
        code='VAT_19',
        defaults={'name': 'Umsatzsteuer 19%', 'rate': Decimal('0.19')}
    )
    tax_7, _ = TaxRate.objects.get_or_create(
        code='VAT_7',
        defaults={'name': 'Umsatzsteuer 7%', 'rate': Decimal('0.07')}
    )
    
    # Get or create unit
    unit, _ = Unit.objects.get_or_create(
        code='STK',
        defaults={'name': 'Stück', 'symbol': 'Stk'}
    )
    
    print("✓ Test data created/verified")
    
    return company, customer, doc_type, tax_19, tax_7, unit


def create_simple_invoice(company, customer, doc_type, tax_19, unit):
    """Create a simple single-page invoice."""
    print("\nCreating simple invoice...")
    
    # Create document
    document = SalesDocument.objects.create(
        company=company,
        document_type=doc_type,
        customer=customer,
        number='R26-TEST-001',
        status='OPEN',
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        subject='Dienstleistungen Januar 2026',
        header_text='<p>Vielen Dank für Ihren Auftrag. Wir berechnen Ihnen wie folgt:</p>',
        footer_text='<p>Bitte überweisen Sie den Betrag innerhalb von 14 Tagen auf unser Konto. Vielen Dank!</p>',
        payment_term_text='Zahlbar innerhalb von 14 Tagen ohne Abzug.',
        total_net=Decimal('1000.00'),
        total_tax=Decimal('190.00'),
        total_gross=Decimal('1190.00')
    )
    
    # Create lines
    SalesDocumentLine.objects.create(
        document=document,
        position_no=1,
        line_type='NORMAL',
        is_selected=True,
        short_text_1='Softwareentwicklung',
        long_text='Entwicklung und Implementierung neuer Features gemäß Pflichtenheft',
        description='Softwareentwicklung',
        unit=unit,
        quantity=Decimal('40.00'),
        unit_price_net=Decimal('25.00'),
        discount=Decimal('0.00'),
        line_net=Decimal('1000.00'),
        line_tax=Decimal('190.00'),
        line_gross=Decimal('1190.00'),
        tax_rate=tax_19
    )
    
    print(f"✓ Created simple invoice: {document.number}")
    return document


def create_complex_invoice(company, customer, doc_type, tax_19, tax_7, unit):
    """Create a complex multi-page invoice with many lines."""
    print("\nCreating complex invoice...")
    
    # Calculate totals
    total_net = Decimal('0.00')
    total_tax = Decimal('0.00')
    
    # Create document
    document = SalesDocument.objects.create(
        company=company,
        document_type=doc_type,
        customer=customer,
        number='R26-TEST-002',
        status='OPEN',
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        subject='Umfangreiches Projekt - Abrechnung Q4/2025',
        header_text='<p>Sehr geehrte Damen und Herren,</p><p>für die erbrachten Leistungen im Rahmen des Projekts "Digital Transformation" berechnen wir Ihnen wie folgt:</p>',
        footer_text='<p>Wir bedanken uns für die gute Zusammenarbeit und freuen uns auf weitere gemeinsame Projekte.</p>',
        payment_term_text='Zahlbar innerhalb von 30 Tagen ohne Abzug.',
        total_net=Decimal('0.00'),  # Will calculate
        total_tax=Decimal('0.00'),  # Will calculate
        total_gross=Decimal('0.00')  # Will calculate
    )
    
    # Create many lines (30 lines to ensure multi-page PDF)
    services = [
        ('Projektmanagement', 'Koordination und Steuerung des Gesamtprojekts', 80, Decimal('85.00'), tax_19),
        ('Backend-Entwicklung', 'Entwicklung der serverseitigen Logik und APIs', 120, Decimal('75.00'), tax_19),
        ('Frontend-Entwicklung', 'Entwicklung der Benutzeroberfläche', 100, Decimal('70.00'), tax_19),
        ('Datenbankdesign', 'Konzeption und Implementierung der Datenbankstruktur', 40, Decimal('80.00'), tax_19),
        ('Testing & QA', 'Qualitätssicherung und Testdurchführung', 60, Decimal('65.00'), tax_19),
        ('Deployment', 'Bereitstellung und Konfiguration der Produktivumgebung', 20, Decimal('75.00'), tax_19),
        ('Dokumentation', 'Erstellung der technischen und Benutzerdokumentation', 30, Decimal('60.00'), tax_7),
        ('Schulung', 'Schulung der Mitarbeiter im Umgang mit dem System', 16, Decimal('90.00'), tax_19),
        ('Support', 'Technischer Support während der Einführungsphase', 40, Decimal('70.00'), tax_19),
        ('Hosting & Infrastruktur', 'Bereitstellung der Cloud-Infrastruktur (3 Monate)', 3, Decimal('500.00'), tax_19),
    ]
    
    pos = 1
    for short_text, long_text, hours, rate, tax_rate in services:
        # Repeat each service 3 times with slight variations
        for i in range(3):
            qty = Decimal(str(hours))
            unit_price = rate
            line_net = (qty * unit_price).quantize(Decimal('0.01'))
            line_tax = (line_net * tax_rate.rate).quantize(Decimal('0.01'))
            line_gross = (line_net + line_tax).quantize(Decimal('0.01'))
            
            total_net += line_net
            total_tax += line_tax
            
            SalesDocumentLine.objects.create(
                document=document,
                position_no=pos,
                line_type='NORMAL',
                is_selected=True,
                short_text_1=f'{short_text} - Phase {i+1}',
                long_text=long_text,
                description=f'{short_text} - Phase {i+1}',
                unit=unit,
                quantity=qty,
                unit_price_net=unit_price,
                discount=Decimal('0.00'),
                line_net=line_net,
                line_tax=line_tax,
                line_gross=line_gross,
                tax_rate=tax_rate
            )
            pos += 1
    
    # Update document totals
    total_gross = total_net + total_tax
    document.total_net = total_net
    document.total_tax = total_tax
    document.total_gross = total_gross
    document.save()
    
    print(f"✓ Created complex invoice: {document.number} ({pos-1} lines)")
    return document


def generate_pdf(document, filename):
    """Generate PDF for a document."""
    print(f"\nGenerating PDF: {filename}...")
    
    # Build context
    builder = SalesDocumentInvoiceContextBuilder()
    context = builder.build_context(document)
    template_name = builder.get_template_name(document)
    
    # Get base URL
    static_root = settings.BASE_DIR / 'static'
    base_url = f'file://{static_root}/'
    
    # Render PDF
    pdf_service = PdfRenderService()
    result = pdf_service.render(
        template_name=template_name,
        context=context,
        base_url=base_url,
        filename=filename
    )
    
    # Save to file
    output_dir = settings.BASE_DIR / 'tmp'
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / filename
    
    with open(output_path, 'wb') as f:
        f.write(result.pdf_bytes)
    
    print(f"✓ PDF generated: {output_path} ({len(result.pdf_bytes)} bytes)")
    return output_path


def main():
    """Main test function."""
    print("=" * 70)
    print("PDF Invoice Generation - Manual Test")
    print("=" * 70)
    print()
    
    # Create test data
    company, customer, doc_type, tax_19, tax_7, unit = create_test_data()
    
    # Generate simple invoice
    simple_doc = create_simple_invoice(company, customer, doc_type, tax_19, unit)
    simple_pdf = generate_pdf(simple_doc, 'test-invoice-simple.pdf')
    
    # Generate complex invoice
    complex_doc = create_complex_invoice(company, customer, doc_type, tax_19, tax_7, unit)
    complex_pdf = generate_pdf(complex_doc, 'test-invoice-complex.pdf')
    
    print()
    print("=" * 70)
    print("Test completed successfully!")
    print("=" * 70)
    print()
    print("Generated PDFs:")
    print(f"  1. Simple invoice:  {simple_pdf}")
    print(f"  2. Complex invoice: {complex_pdf}")
    print()
    print("You can view these PDFs to verify:")
    print("  - First page layout with address block")
    print("  - Table headers repeat on each page")
    print("  - Totals section with tax splits")
    print("  - Footer on every page")
    print()


if __name__ == '__main__':
    main()
