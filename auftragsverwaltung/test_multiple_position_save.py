"""
Test for issue #359: Fehler bei SalesDocument - Speichern von Positionen

This test reproduces the bug where changes to multiple positions are only saved
for the last position, while other positions return HTTP 200 but data is not saved.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date
import json

from auftragsverwaltung.models import (
    SalesDocument, SalesDocumentLine, DocumentType, NumberRange
)
from core.models import Mandant, Adresse, TaxRate, PaymentTerm, Item

User = get_user_model()


class MultiplePositionSaveTestCase(TestCase):
    """Test that multiple position updates are all saved correctly"""
    
    def setUp(self):
        """Set up test data with multiple positions"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test company
        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='DE123456789'
        )
        
        # Create test customer
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer',
            anrede='Herr',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland'
        )
        
        # Create test tax rate
        self.tax_rate = TaxRate.objects.create(
            code='STANDARD',
            name='Standard-Steuersatz',
            rate=Decimal('0.19'),
            is_active=True
        )
        
        # Create payment term
        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto',
            net_days=14,
            is_default=False
        )
        
        # Create document type for Invoice
        self.doc_type_invoice, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'RE',
                'is_invoice': True,
                'is_active': True
            }
        )
        
        # Create number range for invoice
        NumberRange.objects.create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY',
            format='{prefix}{yy}-{seq:05d}'
        )
        
        # Create test sales document (invoice)
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            number='RE-2024-1001',
            status='DRAFT',
            customer=self.customer,
            payment_term=self.payment_term,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )
        
        # Create THREE test lines to reproduce the issue
        self.line1 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Position 1',
            short_text_2='',
            long_text='Original text for position 1',
            description='Position 1',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00')
        )
        
        self.line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Position 2',
            short_text_2='',
            long_text='Original text for position 2',
            description='Position 2',
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('200.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('400.00'),
            line_tax=Decimal('76.00'),
            line_gross=Decimal('476.00')
        )
        
        self.line3 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=3,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Position 3',
            short_text_2='',
            long_text='Original text for position 3',
            description='Position 3',
            quantity=Decimal('3.0000'),
            unit_price_net=Decimal('300.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('900.00'),
            line_tax=Decimal('171.00'),
            line_gross=Decimal('1071.00')
        )
    
    def test_multiple_positions_long_text_updates(self):
        """Test that long_text updates are saved for all positions, not just the last one"""
        # Update Position 1 long_text
        url1 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line1.pk})
        response1 = self.client.post(
            url1,
            data=json.dumps({'long_text': 'Updated text for position 1'}),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)
        
        # Update Position 2 long_text
        url2 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line2.pk})
        response2 = self.client.post(
            url2,
            data=json.dumps({'long_text': 'Updated text for position 2'}),
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)
        
        # Update Position 3 long_text
        url3 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line3.pk})
        response3 = self.client.post(
            url3,
            data=json.dumps({'long_text': 'Updated text for position 3'}),
            content_type='application/json'
        )
        self.assertEqual(response3.status_code, 200)
        
        # Verify all positions were saved correctly in database
        self.line1.refresh_from_db()
        self.line2.refresh_from_db()
        self.line3.refresh_from_db()
        
        self.assertEqual(self.line1.long_text, 'Updated text for position 1',
                        "Position 1 long_text should be saved")
        self.assertEqual(self.line2.long_text, 'Updated text for position 2',
                        "Position 2 long_text should be saved")
        self.assertEqual(self.line3.long_text, 'Updated text for position 3',
                        "Position 3 long_text should be saved")
    
    def test_multiple_positions_short_text_updates(self):
        """Test that short_text updates are saved for all positions"""
        # Update all three positions with different short texts
        url1 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line1.pk})
        self.client.post(url1, data=json.dumps({'short_text_1': 'Updated Position 1'}),
                        content_type='application/json')
        
        url2 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line2.pk})
        self.client.post(url2, data=json.dumps({'short_text_1': 'Updated Position 2'}),
                        content_type='application/json')
        
        url3 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line3.pk})
        self.client.post(url3, data=json.dumps({'short_text_1': 'Updated Position 3'}),
                        content_type='application/json')
        
        # Verify all positions were saved
        self.line1.refresh_from_db()
        self.line2.refresh_from_db()
        self.line3.refresh_from_db()
        
        self.assertEqual(self.line1.short_text_1, 'Updated Position 1')
        self.assertEqual(self.line2.short_text_1, 'Updated Position 2')
        self.assertEqual(self.line3.short_text_1, 'Updated Position 3')
    
    def test_multiple_positions_quantity_and_price_updates(self):
        """Test that quantity and price updates are saved for all positions"""
        # Update all three positions with different quantities and prices
        url1 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line1.pk})
        self.client.post(url1, data=json.dumps({'quantity': '5.0000', 'unit_price_net': '50.00'}),
                        content_type='application/json')
        
        url2 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line2.pk})
        self.client.post(url2, data=json.dumps({'quantity': '10.0000', 'unit_price_net': '25.00'}),
                        content_type='application/json')
        
        url3 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line3.pk})
        self.client.post(url3, data=json.dumps({'quantity': '15.0000', 'unit_price_net': '10.00'}),
                        content_type='application/json')
        
        # Verify all positions were saved
        self.line1.refresh_from_db()
        self.line2.refresh_from_db()
        self.line3.refresh_from_db()
        
        self.assertEqual(self.line1.quantity, Decimal('5.0000'))
        self.assertEqual(self.line1.unit_price_net, Decimal('50.00'))
        
        self.assertEqual(self.line2.quantity, Decimal('10.0000'))
        self.assertEqual(self.line2.unit_price_net, Decimal('25.00'))
        
        self.assertEqual(self.line3.quantity, Decimal('15.0000'))
        self.assertEqual(self.line3.unit_price_net, Decimal('10.00'))
