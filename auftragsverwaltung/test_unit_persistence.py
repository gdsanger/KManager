"""
Test for issue #563: Unit field persistence in positions

This test verifies that:
1. The unit field is saved correctly when updating a position
2. The unit field is displayed correctly on page reload in the edit view
3. The unit field is displayed correctly in PDF preview
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
from core.models import Mandant, Adresse, TaxRate, PaymentTerm, Unit
from auftragsverwaltung.printing.context import SalesDocumentInvoiceContextBuilder

User = get_user_model()


class UnitPersistenceTestCase(TestCase):
    """Test that unit field is persisted and displayed correctly"""

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

        # Create document type for Quote
        self.doc_type_quote, _ = DocumentType.objects.get_or_create(
            key='quote',
            defaults={
                'name': 'Angebot',
                'prefix': 'AN',
                'is_invoice': False,
                'is_active': True
            }
        )

        # Create number range for quote
        NumberRange.objects.create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type_quote,
            reset_policy='YEARLY',
            format='{prefix}{yy}-{seq:05d}'
        )

        # Create test units
        self.unit_stk = Unit.objects.create(
            code='STK',
            name='Stück',
            symbol='Stk.'
        )

        self.unit_lfm = Unit.objects.create(
            code='LFM',
            name='Laufender Meter',
            symbol='lfm'
        )

        # Create test sales document (quote)
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_quote,
            number='AN-2024-1001',
            status='DRAFT',
            customer=self.customer,
            payment_term=self.payment_term,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )

        # Create test line without unit initially
        self.line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Test Position',
            short_text_2='',
            long_text='Test long text',
            description='Test Position',
            quantity=Decimal('5.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('500.00'),
            line_tax=Decimal('95.00'),
            line_gross=Decimal('595.00'),
            unit=None  # Initially no unit
        )

    def test_unit_saved_via_ajax(self):
        """Test that unit is saved when updated via AJAX"""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line.pk})

        # Update unit via AJAX
        response = self.client.post(
            url,
            data={'unit_id': self.unit_stk.pk}
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))

        # Verify unit was saved to database
        self.line.refresh_from_db()
        self.assertEqual(self.line.unit, self.unit_stk)
        self.assertEqual(self.line.unit.symbol, 'Stk.')

    def test_unit_displayed_in_detail_view(self):
        """Test that unit is displayed correctly in detail view after page reload"""
        # Set unit on the line
        self.line.unit = self.unit_stk
        self.line.save()

        # Get the detail view
        url = reverse('auftragsverwaltung:document_detail',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that the unit is in context
        lines = response.context['lines']
        line_from_context = None
        for line in lines:
            if line.pk == self.line.pk:
                line_from_context = line
                break

        self.assertIsNotNone(line_from_context, "Line should be in context")
        self.assertEqual(line_from_context.unit, self.unit_stk)

        # Check that the HTML contains the selected unit
        content = response.content.decode('utf-8')
        # Look for the selected option in the unit dropdown
        self.assertIn(f'<option value="{self.unit_stk.pk}" selected>', content)

    def test_unit_displayed_in_pdf_context(self):
        """Test that unit is included in PDF rendering context"""
        # Set unit on the line
        self.line.unit = self.unit_lfm
        self.line.save()

        # Build PDF context
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(self.document)

        # Check that lines include unit information
        self.assertIn('lines', context)
        self.assertTrue(len(context['lines']) > 0)

        line_context = context['lines'][0]
        self.assertIn('unit', line_context)
        self.assertEqual(line_context['unit'], 'lfm')  # Should be the symbol

    def test_unit_change_via_ajax(self):
        """Test changing unit from one to another via AJAX"""
        # Start with one unit
        self.line.unit = self.unit_stk
        self.line.save()

        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line.pk})

        # Change to different unit
        response = self.client.post(
            url,
            data={'unit_id': self.unit_lfm.pk}
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))

        # Verify unit was changed
        self.line.refresh_from_db()
        self.assertEqual(self.line.unit, self.unit_lfm)
        self.assertEqual(response_data['line']['unit_id'], self.unit_lfm.pk)
        self.assertEqual(response_data['line']['unit_symbol'], 'lfm')

    def test_unit_change_accepts_unit_key(self):
        """Ensure backend accepts both unit_id and unit keys from requests"""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line.pk})

        response = self.client.post(
            url,
            data={'unit': self.unit_lfm.pk}
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))

        self.line.refresh_from_db()
        self.assertEqual(self.line.unit, self.unit_lfm)
        self.assertEqual(data['line']['unit_id'], self.unit_lfm.pk)
        self.assertEqual(data['line']['unit_symbol'], self.unit_lfm.symbol)

    def test_unit_cleared_via_ajax(self):
        """Test clearing unit (setting to None) via AJAX"""
        # Start with a unit
        self.line.unit = self.unit_stk
        self.line.save()

        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line.pk})

        # Clear unit by sending empty string
        response = self.client.post(
            url,
            data={'unit_id': ''}
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))

        # Verify unit was cleared
        self.line.refresh_from_db()
        self.assertIsNone(self.line.unit)
        self.assertIsNone(response_data['line']['unit_id'])
        self.assertEqual(response_data['line']['unit_symbol'], '')

    def test_unit_persisted_when_creating_line(self):
        """Test that unit provided during line creation is saved and rendered"""
        url = reverse(
            'auftragsverwaltung:ajax_add_line',
            kwargs={'doc_key': 'quote', 'pk': self.document.pk}
        )

        payload = {
            'short_text_1': 'Neue Position',
            'short_text_2': '',
            'long_text': '',
            'quantity': 2.5,
            'unit_price_net': 10.00,
            'unit_id': self.unit_lfm.pk,
            'tax_rate_id': self.tax_rate.pk,
            'line_type': 'NORMAL'
        }

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))

        line_id = data['line_id']
        created_line = SalesDocumentLine.objects.get(pk=line_id)
        self.assertEqual(created_line.unit, self.unit_lfm)

        detail_url = reverse(
            'auftragsverwaltung:document_detail',
            kwargs={'doc_key': 'quote', 'pk': self.document.pk}
        )
        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, 200)
        content = detail_response.content.decode('utf-8')
        self.assertIn(f'data-line-id=\"{line_id}\"', content)
        self.assertIn(f'<option value=\"{self.unit_lfm.pk}\" selected>', content)

        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(self.document)
        units = [line['unit'] for line in context.get('lines', [])]
        self.assertIn(self.unit_lfm.symbol, units)

    def test_unit_select_has_name_attribute(self):
        """Detail view should render unit select with name for HTMX payloads"""
        self.line.unit = self.unit_stk
        self.line.save()

        detail_url = reverse(
            'auftragsverwaltung:document_detail',
            kwargs={'doc_key': 'quote', 'pk': self.document.pk}
        )
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('class="form-select form-select-sm line-unit"', content)
        self.assertIn('name="unit_id"', content)
