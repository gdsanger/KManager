"""
Tests for Invoice PDF generation (ContextBuilder, Template, and Download Endpoint)
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import SalesDocument, DocumentType, SalesDocumentLine
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from core.models import Mandant, Adresse, TaxRate, PaymentTerm, Unit, Item
from core.services.reporting import ReportService


class SalesDocumentInvoiceContextBuilderTestCase(TestCase):
    """Test case for SalesDocumentInvoiceContextBuilder"""
    
    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Hauptstrasse 1',
            plz='10115',
            ort='Berlin',
            land='Deutschland',
            steuernummer='12/345/67890',
            ust_id_nr='DE123456789',
            kreditinstitut='Sparkasse Berlin',
            iban='DE89370400440532013000',
            bic='COBADEFFXXX',
            kontoinhaber='Test GmbH'
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstrasse 5',
            plz='20095',
            ort='Hamburg',
            land='Deutschland',
            country_code='DE',
            vat_id='DE987654321',
            is_business=True,
            is_eu=False
        )
        
        # Get or create document type
        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'R',
                'is_invoice': True,
                'requires_due_date': True,
                'is_active': True
            }
        )
        
        # Get or create tax rates
        self.tax_19, _ = TaxRate.objects.get_or_create(
            code='19%',
            defaults={
                'rate': Decimal('0.19'),
                'is_active': True
            }
        )
        self.tax_7, _ = TaxRate.objects.get_or_create(
            code='7%',
            defaults={
                'rate': Decimal('0.07'),
                'is_active': True
            }
        )
        self.tax_0, _ = TaxRate.objects.get_or_create(
            code='ZERO',
            defaults={
                'rate': Decimal('0.00'),
                'is_active': True
            }
        )
        
        # Get or create unit
        self.unit, _ = Unit.objects.get_or_create(
            code='Stk',
            defaults={
                'name': 'Stück',
                'is_active': True
            }
        )
        
        # Create payment term
        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto',
            net_days=14,
            is_default=True
        )
        
        # Create sales document
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00001',
            status='OPEN',
            issue_date=date(2026, 2, 1),
            due_date=date(2026, 2, 15),
            subject='Test Rechnung',
            header_text='<p>Vielen Dank für Ihren Auftrag.</p>',
            footer_text='<p>Mit freundlichen Grüßen</p>',
            payment_term_text='Zahlbar innerhalb von 14 Tagen ohne Abzug.',
            payment_term=self.payment_term,
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )
        
        # Create document lines
        self.line1 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Produkt A',
            short_text_2='Variante 1',
            long_text='Detaillierte Beschreibung des Produkts A',
            description='Produkt A Variante 1',
            unit=self.unit,
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_19,
            is_discountable=True,
            discount=Decimal('0.00')
        )
        
        self.line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Service B',
            description='Service B',
            unit=self.unit,
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_7,
            is_discountable=True,
            discount=Decimal('0.00')
        )
    
    def test_build_company_context(self):
        """Test that company context is built correctly"""
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        company = context['company']
        self.assertEqual(company['name'], 'Test GmbH')
        self.assertEqual(len(company['address_lines']), 3)
        self.assertIn('Hauptstrasse 1', company['address_lines'])
        self.assertEqual(company['tax_number'], '12/345/67890')
        self.assertEqual(company['vat_id'], 'DE123456789')
        self.assertIsNotNone(company['bank_info'])
        self.assertEqual(company['bank_info']['iban'], 'DE89370400440532013000')
    
    def test_build_customer_context(self):
        """Test that customer context is built correctly"""
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        customer = context['customer']
        self.assertEqual(customer['name'], 'Kunde GmbH')
        self.assertIn('Kunde GmbH', customer['address_lines'])
        self.assertIn('Max Mustermann', customer['address_lines'])
        self.assertIn('Kundenstrasse 5', customer['address_lines'])
        self.assertEqual(customer['country_code'], 'DE')
        self.assertEqual(customer['vat_id'], 'DE987654321')
    
    def test_build_document_context(self):
        """Test that document context is built correctly"""
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        doc = context['doc']
        self.assertEqual(doc['number'], 'R26-00001')
        self.assertEqual(doc['subject'], 'Test Rechnung')
        self.assertEqual(doc['issue_date'], '01.02.2026')
        self.assertEqual(doc['due_date'], '15.02.2026')
        self.assertIn('Vielen Dank', doc['header_html'])
        self.assertIn('freundlichen Grüßen', doc['footer_html'])
    
    def test_build_lines_context(self):
        """Test that lines context is built correctly"""
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        lines = context['lines']
        self.assertEqual(len(lines), 2)
        
        # Check first line
        line1 = lines[0]
        self.assertEqual(line1['pos'], 1)
        self.assertEqual(line1['qty'], '2')
        self.assertIn(line1['unit'].upper(), ['STK', 'Stk'])  # Case insensitive check
        self.assertIn('Produkt A', line1['short_text'])
        self.assertIn('Variante 1', line1['short_text'])
        self.assertEqual(line1['long_text'], 'Detaillierte Beschreibung des Produkts A')
        self.assertEqual(line1['tax_rate'], '19.00%')
        
        # Check second line
        line2 = lines[1]
        self.assertEqual(line2['pos'], 2)
        self.assertEqual(line2['qty'], '1')
        self.assertEqual(line2['tax_rate'], '7.00%')
    
    def test_build_totals_context(self):
        """Test that totals context is built correctly with tax splits"""
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        totals = context['totals']
        # Note: German number format (comma as decimal separator)
        self.assertIn(',', totals['net_19'])
        self.assertIn(',', totals['net_7'])
        self.assertIn(',', totals['tax_total'])
        self.assertIn(',', totals['gross_total'])
    
    def test_build_tax_notes_context_domestic(self):
        """Test that tax notes are built correctly for domestic customer"""
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        tax_notes = context['tax_notes']
        # Domestic customer should not have special tax notes
        self.assertIsNone(tax_notes['reverse_charge_text'])
        self.assertIsNone(tax_notes['export_text'])
    
    def test_build_tax_notes_context_eu_b2b(self):
        """Test that tax notes include reverse charge for EU B2B customer"""
        # Update customer to be EU B2B
        self.customer.country_code = 'FR'
        self.customer.is_eu = True
        self.customer.is_business = True
        self.customer.vat_id = 'FR12345678901'
        self.customer.save()
        
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        tax_notes = context['tax_notes']
        # EU B2B customer should have reverse charge note
        self.assertIsNotNone(tax_notes['reverse_charge_text'])
        self.assertIn('13b UStG', tax_notes['reverse_charge_text'])
    
    def test_context_without_customer(self):
        """Test that context builder works without customer"""
        # Create document without customer
        doc_no_customer = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=None,
            number='R26-00002',
            status='DRAFT',
            issue_date=date(2026, 2, 1),
            subject='Test ohne Kunde'
        )
        
        builder = SalesDocumentInvoiceContextBuilder(doc_no_customer)
        context = builder.build()
        
        # Should not raise error
        self.assertIsNotNone(context)
        self.assertEqual(context['customer']['name'], '')
        self.assertEqual(context['customer']['address_lines'], [])


class InvoicePDFDownloadTestCase(TestCase):
    """Test case for invoice PDF download endpoint"""
    
    def setUp(self):
        """Set up test data and client"""
        # Create user for authentication
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        
        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Hauptstrasse 1',
            plz='10115',
            ort='Berlin',
            land='Deutschland',
            steuernummer='12/345/67890',
            ust_id_nr='DE123456789'
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstrasse 5',
            plz='20095',
            ort='Hamburg',
            land='Deutschland',
            country_code='DE'
        )
        
        # Get or create document types
        self.doc_type_invoice, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'R',
                'is_invoice': True,
                'is_active': True
            }
        )
        
        self.doc_type_quote, _ = DocumentType.objects.get_or_create(
            key='quote',
            defaults={
                'name': 'Angebot',
                'prefix': 'A',
                'is_invoice': False,
                'is_active': True
            }
        )
        
        # Get or create tax rate
        self.tax_19, _ = TaxRate.objects.get_or_create(
            code='19%',
            defaults={
                'rate': Decimal('0.19'),
                'is_active': True
            }
        )
        
        # Get or create unit
        self.unit, _ = Unit.objects.get_or_create(
            code='Stk',
            defaults={
                'name': 'Stück',
                'is_active': True
            }
        )
        
        # Create invoice document
        self.invoice = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            customer=self.customer,
            number='R26-00001',
            status='OPEN',
            issue_date=date(2026, 2, 1),
            due_date=date(2026, 2, 15),
            subject='Test Rechnung'
        )
        
        # Add a line to the invoice
        SalesDocumentLine.objects.create(
            document=self.invoice,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description='Test Product',
            unit=self.unit,
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_19
        )
        
        # Create quote document (non-invoice)
        self.quote = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_quote,
            customer=self.customer,
            number='A26-00001',
            status='DRAFT',
            issue_date=date(2026, 2, 1),
            subject='Test Angebot'
        )
        
        # Create client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_pdf_download_requires_authentication(self):
        """Test that PDF download requires authentication"""
        # Logout
        self.client.logout()
        
        url = reverse('auftragsverwaltung:document_pdf_download', kwargs={'pk': self.invoice.pk})
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_pdf_download_invoice_success(self):
        """Test successful PDF download for invoice"""
        url = reverse('auftragsverwaltung:document_pdf_download', kwargs={'pk': self.invoice.pk})
        response = self.client.get(url)
        
        # Should return PDF successfully
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('Rechnung_R26-00001.pdf', response['Content-Disposition'])
        
        # PDF should have content
        self.assertGreater(len(response.content), 0)
        
        # PDF should start with PDF magic bytes
        self.assertTrue(response.content.startswith(b'%PDF'))
    
    def test_pdf_download_non_invoice_forbidden(self):
        """Test that PDF download is forbidden for non-invoice documents"""
        url = reverse('auftragsverwaltung:document_pdf_download', kwargs={'pk': self.quote.pk})
        response = self.client.get(url)
        
        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
    
    def test_pdf_download_nonexistent_document_404(self):
        """Test that PDF download returns 404 for non-existent document"""
        url = reverse('auftragsverwaltung:document_pdf_download', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        # Should return 404 Not Found
        self.assertEqual(response.status_code, 404)
    
    def test_pdf_filename_generation(self):
        """Test that PDF filename is generated correctly"""
        url = reverse('auftragsverwaltung:document_pdf_download', kwargs={'pk': self.invoice.pk})
        response = self.client.get(url)
        
        # Check filename in Content-Disposition header
        self.assertIn('filename=', response['Content-Disposition'])
        self.assertIn('Rechnung_R26-00001.pdf', response['Content-Disposition'])
    
    def test_pdf_rendering_with_multiple_lines(self):
        """Test PDF rendering with multiple lines (smoke test for multi-page)"""
        # Add many lines to test pagination
        for i in range(2, 30):
            SalesDocumentLine.objects.create(
                document=self.invoice,
                position_no=i,
                line_type='NORMAL',
                is_selected=True,
                description=f'Product {i}',
                unit=self.unit,
                quantity=Decimal('1.0000'),
                unit_price_net=Decimal('10.00'),
                tax_rate=self.tax_19
            )
        
        url = reverse('auftragsverwaltung:document_pdf_download', kwargs={'pk': self.invoice.pk})
        response = self.client.get(url)
        
        # Should still render successfully
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Multi-page PDF should be larger
        self.assertGreater(len(response.content), 5000)


class InvoiceTemplateIntegrationTestCase(TestCase):
    """Integration test for the complete PDF generation pipeline"""
    
    def setUp(self):
        """Set up minimal test data"""
        # Create company
        self.company = Mandant.objects.create(
            name='Integration Test GmbH',
            adresse='Teststr. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Get or create document type
        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'R',
                'is_invoice': True,
                'is_active': True
            }
        )
        
        # Get or create tax rate
        self.tax_19, _ = TaxRate.objects.get_or_create(
            code='19%',
            defaults={
                'rate': Decimal('0.19'),
                'is_active': True
            }
        )
        
        # Get or create unit
        self.unit, _ = Unit.objects.get_or_create(
            code='Stk',
            defaults={
                'name': 'Stück',
                'is_active': True
            }
        )
        
        # Create document
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            number='R26-TEST',
            status='OPEN',
            issue_date=date(2026, 2, 1)
        )
        
        # Add line
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description='Test',
            unit=self.unit,
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_19
        )
    
    def test_full_pdf_generation_pipeline(self):
        """Test the complete pipeline: ContextBuilder -> Template -> PDF"""
        # Build context
        builder = SalesDocumentInvoiceContextBuilder(self.document)
        context = builder.build()
        
        # Render PDF
        pdf_bytes = ReportService.render('invoice.v1', context)
        
        # Verify PDF is valid
        self.assertIsNotNone(pdf_bytes)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 100)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
