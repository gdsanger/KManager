"""
Script to create basic test data for SalesDocument DetailView testing
"""
from core.models import Mandant, TaxRate, PaymentTerm, Item, Adresse, Kostenart
from auftragsverwaltung.models import DocumentType, SalesDocument, SalesDocumentLine
from datetime import date
from decimal import Decimal


def setup_test_data():
    """Create test data for manual testing"""
    
    # 1. Create Mandant (Company)
    company, created = Mandant.objects.get_or_create(
        name='Testfirma GmbH',
        defaults={
            'strasse': 'Teststraße 1',
            'plz': '12345',
            'ort': 'Berlin',
            'land': 'Deutschland',
            'email': 'info@testfirma.de',
        }
    )
    print(f"Company: {company.name} ({'created' if created else 'exists'})")
    
    # 2. Create Tax Rates
    tax_19, created = TaxRate.objects.get_or_create(
        code='VAT',
        defaults={
            'name': 'Standard VAT 19%',
            'rate': Decimal('0.19'),
            'is_active': True
        }
    )
    print(f"Tax Rate 19%: {tax_19.code} ({'created' if created else 'exists'})")
    
    tax_7, created = TaxRate.objects.get_or_create(
        code='REDUCED',
        defaults={
            'name': 'Reduced VAT 7%',
            'rate': Decimal('0.07'),
            'is_active': True
        }
    )
    print(f"Tax Rate 7%: {tax_7.code} ({'created' if created else 'exists'})")
    
    tax_0, created = TaxRate.objects.get_or_create(
        code='ZERO',
        defaults={
            'name': 'Zero VAT 0%',
            'rate': Decimal('0.00'),
            'is_active': True
        }
    )
    print(f"Tax Rate 0%: {tax_0.code} ({'created' if created else 'exists'})")
    
    # 3. Create Payment Terms
    pt_14, created = PaymentTerm.objects.get_or_create(
        name='14 Tage netto',
        defaults={
            'net_days': 14,
            'is_default': True
        }
    )
    print(f"Payment Term 14 days: {pt_14.name} ({'created' if created else 'exists'})")
    
    pt_skonto, created = PaymentTerm.objects.get_or_create(
        name='2% Skonto 10 Tage, netto 30 Tage',
        defaults={
            'net_days': 30,
            'discount_days': 10,
            'discount_rate': Decimal('0.02'),
            'is_default': False
        }
    )
    print(f"Payment Term Skonto: {pt_skonto.name} ({'created' if created else 'exists'})")
    
    # 4. Create Kostenarten (Cost Types) for Items
    kostenart_1, created = Kostenart.objects.get_or_create(
        name='Verkauf',
        defaults={
            'umsatzsteuer_satz': '19',
        }
    )
    print(f"Kostenart: {kostenart_1.name} ({'created' if created else 'exists'})")
    
    # 5. Create Items
    item_1, created = Item.objects.get_or_create(
        article_no='ART-001',
        defaults={
            'short_text_1': 'Beratungsleistung Stunde',
            'short_text_2': 'Consulting Hour',
            'long_text': 'Professionelle Beratungsleistung pro Stunde',
            'net_price': Decimal('100.00'),
            'purchase_price': Decimal('50.00'),
            'tax_rate': tax_19,
            'cost_type_1': kostenart_1,
            'item_type': 'SERVICE',
            'is_discountable': True,
            'is_active': True
        }
    )
    print(f"Item 1: {item_1.article_no} ({'created' if created else 'exists'})")
    
    item_2, created = Item.objects.get_or_create(
        article_no='ART-002',
        defaults={
            'short_text_1': 'Software Lizenz',
            'short_text_2': 'Software License',
            'long_text': 'Jahreslizenz für Premium Software',
            'net_price': Decimal('299.00'),
            'purchase_price': Decimal('150.00'),
            'tax_rate': tax_19,
            'cost_type_1': kostenart_1,
            'item_type': 'SERVICE',
            'is_discountable': True,
            'is_active': True
        }
    )
    print(f"Item 2: {item_2.article_no} ({'created' if created else 'exists'})")
    
    item_3, created = Item.objects.get_or_create(
        article_no='ART-003',
        defaults={
            'short_text_1': 'Büromaterial Paket',
            'short_text_2': 'Office Supplies Package',
            'long_text': 'Komplettpaket Büromaterial',
            'net_price': Decimal('49.90'),
            'purchase_price': Decimal('25.00'),
            'tax_rate': tax_19,
            'cost_type_1': kostenart_1,
            'item_type': 'MATERIAL',
            'is_discountable': True,
            'is_active': True
        }
    )
    print(f"Item 3: {item_3.article_no} ({'created' if created else 'exists'})")
    
    # 6. Create Customers
    customer_de, created = Adresse.objects.get_or_create(
        name='Mustermann',
        strasse='Musterstraße 123',
        defaults={
            'adressen_type': 'KUNDE',
            'firma': 'Muster GmbH',
            'anrede': 'HERR',
            'plz': '10115',
            'ort': 'Berlin',
            'land': 'Deutschland',
            'country_code': 'DE',
            'email': 'max@musterfirma.de',
            'is_business': True,
            'is_eu': True,
        }
    )
    print(f"Customer DE: {customer_de.full_name()} ({'created' if created else 'exists'})")
    
    customer_eu, created = Adresse.objects.get_or_create(
        name='Dupont',
        strasse='Rue de Paris 1',
        defaults={
            'adressen_type': 'KUNDE',
            'firma': 'French Company SARL',
            'anrede': 'HERR',
            'plz': '75001',
            'ort': 'Paris',
            'land': 'France',
            'country_code': 'FR',
            'email': 'contact@frenchcompany.fr',
            'vat_id': 'FR12345678901',
            'is_business': True,
            'is_eu': True,
        }
    )
    print(f"Customer EU: {customer_eu.full_name()} ({'created' if created else 'exists'})")
    
    customer_us, created = Adresse.objects.get_or_create(
        name='Smith',
        strasse='Main Street 100',
        defaults={
            'adressen_type': 'KUNDE',
            'firma': 'US Corporation Inc.',
            'anrede': 'HERR',
            'plz': '10001',
            'ort': 'New York',
            'land': 'USA',
            'country_code': 'US',
            'email': 'contact@uscorp.com',
            'is_business': True,
            'is_eu': False,
        }
    )
    print(f"Customer US: {customer_us.full_name()} ({'created' if created else 'exists'})")
    
    print("\n✓ Test data created successfully!")
    print(f"\nYou can now create sales documents at:")
    print(f"  - http://localhost:8000/auftragsverwaltung/documents/quote/create/")
    print(f"  - http://localhost:8000/auftragsverwaltung/documents/invoice/create/")


if __name__ == '__main__':
    setup_test_data()
