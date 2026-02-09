#!/usr/bin/env python
"""
Manual test script to verify PDF preview feature.

This script sets up test data and provides instructions for manually testing
the PDF preview functionality.
"""

import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.test_settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django to use file-based SQLite instead of in-memory
from django.conf import settings
settings.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(os.path.dirname(__file__), 'test_db.sqlite3'),
    }
}

django.setup()

from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType
from core.models import Mandant, Adresse, Item, TaxRate, Unit

def setup_test_data():
    """Set up test data for manual testing"""
    
    print("Setting up test database and data...")
    
    # Run migrations
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)
    
    # Create test user
    if not User.objects.filter(username='admin').exists():
        user = User.objects.create_superuser('admin', 'admin@test.de', 'admin')
        print(f"✓ Created superuser: admin / admin")
    else:
        print("✓ Superuser already exists")
    
    # Create company
    company, created = Mandant.objects.get_or_create(
        name='Test GmbH',
        defaults={
            'adresse': 'Teststraße 1',
            'plz': '12345',
            'ort': 'Berlin',
            'land': 'Deutschland',
            'steuernummer': '12/345/67890',
            'ust_id_nr': 'DE123456789',
            'kreditinstitut': 'Test Bank',
            'iban': 'DE89370400440532013000',
            'bic': 'COBADEFFXXX',
            'telefon': '030-12345678',
            'email': 'info@test.de'
        }
    )
    print(f"✓ Company: {company.name}")
    
    # Create customer
    customer, created = Adresse.objects.get_or_create(
        firma='Kunde GmbH',
        defaults={
            'name': 'Max Mustermann',
            'strasse': 'Kundenstraße 10',
            'plz': '54321',
            'ort': 'Hamburg',
            'land': 'Deutschland',
        }
    )
    print(f"✓ Customer: {customer.firma}")
    
    # Create document types
    doc_types = [
        {'key': 'rechnung', 'name': 'Rechnung', 'prefix': 'R', 'is_invoice': True},
        {'key': 'angebot', 'name': 'Angebot', 'prefix': 'A', 'is_invoice': False},
        {'key': 'auftrag', 'name': 'Auftrag', 'prefix': 'AB', 'is_invoice': False},
    ]
    
    for dt_data in doc_types:
        dt, created = DocumentType.objects.get_or_create(
            key=dt_data['key'],
            defaults=dt_data
        )
        if created:
            print(f"✓ Created document type: {dt.name}")
    
    # Create tax rates
    tax_19, created = TaxRate.objects.get_or_create(
        code='normal',
        defaults={'name': 'Normal 19%', 'rate': Decimal('0.19')}
    )
    
    # Create unit
    unit, created = Unit.objects.get_or_create(
        code='STK',
        defaults={'name': 'Stück', 'symbol': 'Stk'}
    )
    
    # Create test documents
    doc_type_rechnung = DocumentType.objects.get(key='rechnung')
    
    if not SalesDocument.objects.exists():
        document = SalesDocument.objects.create(
            company=company,
            document_type=doc_type_rechnung,
            customer=customer,
            number='R26-00001',
            status='OPEN',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            subject='Test Rechnung für PDF Voransicht',
            header_text='<p>Vielen Dank für Ihren Auftrag.</p>',
            footer_text='<p>Bitte überweisen Sie den Betrag innerhalb von 14 Tagen.</p>',
            payment_term_text='Zahlbar innerhalb von 14 Tagen ohne Abzug.',
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )
        
        # Create line
        SalesDocumentLine.objects.create(
            document=document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Test Artikel',
            long_text='Beschreibung für Test Artikel',
            description='Test Artikel',
            unit=unit,
            quantity=Decimal('1.00'),
            unit_price_net=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00'),
            tax_rate=tax_19
        )
        
        print(f"✓ Created test document: {document.number}")
        print(f"  - Document ID: {document.id}")
        print(f"  - Document Type: {document.document_type.name}")
    else:
        document = SalesDocument.objects.first()
        print(f"✓ Test document already exists: {document.number} (ID: {document.id})")
    
    print("\n" + "="*60)
    print("MANUAL TEST INSTRUCTIONS")
    print("="*60)
    print(f"\n1. Start the development server:")
    print(f"   python manage.py runserver --settings=kmanager.test_settings")
    print(f"\n2. Login with:")
    print(f"   Username: admin")
    print(f"   Password: admin")
    print(f"\n3. Navigate to the document detail view:")
    print(f"   http://localhost:8000/auftragsverwaltung/documents/rechnung/{document.id}/")
    print(f"\n4. Look for the 'PDF voransehen' button in the page actions")
    print(f"\n5. Click the button and verify:")
    print(f"   - PDF opens in a new tab")
    print(f"   - PDF displays correctly")
    print(f"   - Filename is: {document.document_type.name}_{document.id}.pdf")
    print(f"   - No changes to the document (status, number, etc.)")
    print("\n" + "="*60)

if __name__ == '__main__':
    setup_test_data()
