"""
Integration test for issue #563: Unit field in position management

This test verifies the complete workflow:
1. Create a document with a position
2. Update the unit via AJAX
3. Reload the detail page and verify unit is displayed
4. Generate PDF preview and verify unit is shown
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
from core.printing import PdfRenderService

User = get_user_model()


class UnitIntegrationTestCase(TestCase):
    """Integration test for full unit workflow"""

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

    def test_full_unit_workflow(self):
        """
        Integration test for complete unit workflow:
        1. Update unit via AJAX
        2. Verify persistence in database
        3. Reload detail page and verify unit is shown in dropdown
        4. Generate PDF context and verify unit is included
        """
        # Step 1: Update unit via AJAX
        ajax_url = reverse('auftragsverwaltung:ajax_update_line',
                          kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line.pk})

        response = self.client.post(ajax_url, data={'unit_id': self.unit_stk.pk})
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))
        self.assertEqual(response_data['line']['unit_id'], self.unit_stk.pk)
        self.assertEqual(response_data['line']['unit_symbol'], 'Stk.')

        # Step 2: Verify persistence in database
        self.line.refresh_from_db()
        self.assertEqual(self.line.unit, self.unit_stk)

        # Step 3: Reload detail page and verify unit is shown
        detail_url = reverse('auftragsverwaltung:document_detail',
                            kwargs={'doc_key': 'quote', 'pk': self.document.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

        # Check that unit is in context and accessible without additional queries
        lines = response.context['lines']
        line_from_context = [l for l in lines if l.pk == self.line.pk][0]
        self.assertEqual(line_from_context.unit, self.unit_stk)

        # Check HTML contains the selected unit
        content = response.content.decode('utf-8')
        # Look for selected option with unit pk
        self.assertIn(f'value="{self.unit_stk.pk}" selected', content)
        self.assertIn(self.unit_stk.code, content)

        # Step 4: Generate PDF context and verify unit is included
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(self.document)

        self.assertIn('lines', context)
        self.assertEqual(len(context['lines']), 1)

        line_context = context['lines'][0]
        self.assertIn('unit', line_context)
        self.assertEqual(line_context['unit'], 'Stk.')  # Symbol, not code
        self.assertEqual(line_context['qty'], Decimal('5.0000'))
        self.assertEqual(line_context['short_text'], 'Test Position')

    def test_unit_change_workflow(self):
        """
        Test changing unit from one to another and verify in all contexts
        """
        # Set initial unit
        self.line.unit = self.unit_stk
        self.line.save()

        # Change to different unit via AJAX
        ajax_url = reverse('auftragsverwaltung:ajax_update_line',
                          kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line.pk})

        response = self.client.post(ajax_url, data={'unit_id': self.unit_lfm.pk})
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)
        self.assertEqual(response_data['line']['unit_id'], self.unit_lfm.pk)
        self.assertEqual(response_data['line']['unit_symbol'], 'lfm')

        # Verify in database
        self.line.refresh_from_db()
        self.assertEqual(self.line.unit, self.unit_lfm)

        # Verify in detail view
        detail_url = reverse('auftragsverwaltung:document_detail',
                            kwargs={'doc_key': 'quote', 'pk': self.document.pk})
        response = self.client.get(detail_url)
        content = response.content.decode('utf-8')
        self.assertIn(f'value="{self.unit_lfm.pk}" selected', content)

        # Verify in PDF context
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(self.document)
        self.assertEqual(context['lines'][0]['unit'], 'lfm')

    def test_unit_cleared_workflow(self):
        """
        Test clearing unit (setting to None) and verify in all contexts
        """
        # Set initial unit
        self.line.unit = self.unit_stk
        self.line.save()

        # Clear unit via AJAX
        ajax_url = reverse('auftragsverwaltung:ajax_update_line',
                          kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line.pk})

        response = self.client.post(ajax_url, data={'unit_id': ''})
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)
        self.assertIsNone(response_data['line']['unit_id'])
        self.assertEqual(response_data['line']['unit_symbol'], '')

        # Verify in database
        self.line.refresh_from_db()
        self.assertIsNone(self.line.unit)

        # Verify in detail view - unit field should be accessible
        detail_url = reverse('auftragsverwaltung:document_detail',
                            kwargs={'doc_key': 'quote', 'pk': self.document.pk})
        response = self.client.get(detail_url)
        lines = response.context['lines']
        line_from_context = [l for l in lines if l.pk == self.line.pk][0]
        # Unit should be None in the context
        self.assertIsNone(line_from_context.unit)

        # Verify in PDF context - unit should be empty string
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(self.document)
        self.assertEqual(context['lines'][0]['unit'], '')

    def test_multiple_lines_different_units(self):
        """
        Test multiple positions with different units
        """
        # Create second line with different unit
        line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Position 2',
            short_text_2='',
            long_text='',
            description='Position 2',
            quantity=Decimal('10.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('500.00'),
            line_tax=Decimal('95.00'),
            line_gross=Decimal('595.00'),
            unit=self.unit_lfm  # Different unit
        )

        # Set unit for first line
        self.line.unit = self.unit_stk
        self.line.save()

        # Verify in detail view
        detail_url = reverse('auftragsverwaltung:document_detail',
                            kwargs={'doc_key': 'quote', 'pk': self.document.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

        # Check both units are in context
        lines = list(response.context['lines'])
        self.assertEqual(len(lines), 2)

        line1_ctx = [l for l in lines if l.pk == self.line.pk][0]
        line2_ctx = [l for l in lines if l.pk == line2.pk][0]

        self.assertEqual(line1_ctx.unit, self.unit_stk)
        self.assertEqual(line2_ctx.unit, self.unit_lfm)

        # Verify in PDF context
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(self.document)

        self.assertEqual(len(context['lines']), 2)
        self.assertEqual(context['lines'][0]['unit'], 'Stk.')
        self.assertEqual(context['lines'][1]['unit'], 'lfm')
