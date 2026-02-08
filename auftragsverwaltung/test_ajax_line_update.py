"""
Tests for AJAX line update endpoint to fix issue #337
Tests the ajax_update_line endpoint with various field updates including long_text
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
from core.models import Mandant, Adresse, TaxRate, PaymentTerm

User = get_user_model()


class AjaxLineUpdateTestCase(TestCase):
    """Test cases for AJAX line update endpoint"""
    
    def setUp(self):
        """Set up test data"""
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
        
        # Create or get document type for Invoice
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
        
        # Create test line
        self.line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Test Item',
            short_text_2='',
            long_text='Original long text',
            description='Test Item',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00')
        )
    
    def test_ajax_update_line_long_text(self):
        """Test updating only the long_text field (simulates HTMX textarea update)"""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line.pk})
        
        new_long_text = 'Updated long text content via HTMX'
        data = {
            'long_text': new_long_text
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Check response status
        self.assertEqual(response.status_code, 200, 
                        f"Expected 200 but got {response.status_code}. Response: {response.content}")
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'), 
                       f"Expected success=True in response. Got: {response_data}")
        self.assertIn('line', response_data)
        self.assertIn('totals', response_data)
        
        # Check that long_text was updated in response
        self.assertEqual(response_data['line']['long_text'], new_long_text)
        
        # Check that line was updated in database
        self.line.refresh_from_db()
        self.assertEqual(self.line.long_text, new_long_text)
        
        # Check that totals were recalculated and persisted
        self.document.refresh_from_db()
        self.assertEqual(self.document.total_net, Decimal('100.00'))
        self.assertEqual(self.document.total_tax, Decimal('19.00'))
        self.assertEqual(self.document.total_gross, Decimal('119.00'))
    
    def test_ajax_update_line_quantity_and_price(self):
        """Test updating quantity and unit price"""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line.pk})
        
        data = {
            'quantity': '2.5000',
            'unit_price_net': '75.00'
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Check that line was updated
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, Decimal('2.5000'))
        self.assertEqual(self.line.unit_price_net, Decimal('75.00'))
        
        # Check calculated totals
        expected_net = Decimal('187.50')  # 2.5 * 75.00
        expected_tax = Decimal('35.63')   # 187.50 * 0.19 (rounded)
        expected_gross = Decimal('223.13')  # 187.50 + 35.63
        
        self.assertEqual(response_data['line']['line_net'], str(expected_net))
        self.assertEqual(response_data['line']['line_tax'], str(expected_tax))
        self.assertEqual(response_data['line']['line_gross'], str(expected_gross))
        
        # Verify line totals are persisted in database
        self.line.refresh_from_db()
        self.assertEqual(self.line.line_net, expected_net)
        self.assertEqual(self.line.line_tax, expected_tax)
        self.assertEqual(self.line.line_gross, expected_gross)
    
    def test_ajax_update_line_multiple_fields(self):
        """Test updating multiple fields at once"""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line.pk})
        
        data = {
            'short_text_1': 'Updated Short Text',
            'long_text': 'Updated Long Text',
            'quantity': '3.0000',
            'unit_price_net': '50.00'
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Check all fields were updated
        self.line.refresh_from_db()
        self.assertEqual(self.line.short_text_1, 'Updated Short Text')
        self.assertEqual(self.line.long_text, 'Updated Long Text')
        self.assertEqual(self.line.quantity, Decimal('3.0000'))
        self.assertEqual(self.line.unit_price_net, Decimal('50.00'))
    
    def test_ajax_update_line_other_document_types(self):
        """Test that the same endpoint works for other document types (quote, order)"""
        # Create or get document type for Quote
        doc_type_quote, _ = DocumentType.objects.get_or_create(
            key='quote',
            defaults={
                'name': 'Angebot',
                'prefix': 'AN',
                'is_active': True
            }
        )
        
        # Create number range for quote
        NumberRange.objects.create(
            company=self.company,
            target='DOCUMENT',
            document_type=doc_type_quote,
            reset_policy='YEARLY',
            format='{prefix}{yy}-{seq:05d}'
        )
        
        # Create quote document
        quote_document = SalesDocument.objects.create(
            company=self.company,
            document_type=doc_type_quote,
            number='AN-2024-1001',
            status='DRAFT',
            customer=self.customer,
            payment_term=self.payment_term,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )
        
        # Create quote line
        quote_line = SalesDocumentLine.objects.create(
            document=quote_document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Quote Item',
            short_text_2='',
            long_text='Original quote long text',
            description='Quote Item',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('200.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('200.00'),
            line_tax=Decimal('38.00'),
            line_gross=Decimal('238.00')
        )
        
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': quote_document.pk, 'line_id': quote_line.pk})
        
        data = {
            'long_text': 'Updated quote long text'
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        quote_line.refresh_from_db()
        self.assertEqual(quote_line.long_text, 'Updated quote long text')
    
    def test_ajax_update_line_form_encoded_data(self):
        """Test updating with form-encoded data (simulates real HTMX hx-vals behavior)"""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line.pk})
        
        # Simulate HTMX hx-vals sending form-encoded data
        new_long_text = 'Form-encoded long text from HTMX'
        data = {
            'long_text': new_long_text
        }
        
        response = self.client.post(
            url,
            data=data,  # Send as form-encoded, not JSON
            # Do NOT set content_type='application/json' - simulate HTMX default behavior
        )
        
        # Check response status
        self.assertEqual(response.status_code, 200, 
                        f"Expected 200 but got {response.status_code}. Response: {response.content}")
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'), 
                       f"Expected success=True in response. Got: {response_data}")
        
        # Check that long_text was updated in database
        self.line.refresh_from_db()
        self.assertEqual(self.line.long_text, new_long_text)
        
        # Check that totals are correct
        self.document.refresh_from_db()
        self.assertEqual(self.document.total_net, Decimal('100.00'))
        self.assertEqual(self.document.total_tax, Decimal('19.00'))
        self.assertEqual(self.document.total_gross, Decimal('119.00'))
