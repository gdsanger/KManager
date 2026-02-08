"""
Tests for PDF invoice generation.

Tests the SalesDocument PDF rendering functionality including context builder
and PDF download endpoint.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from core.models import Mandant, Adresse, Item, TaxRate, Unit
from core.printing import PdfRenderService


class SalesDocumentInvoiceContextBuilderTest(TestCase):
    """Tests for SalesDocumentInvoiceContextBuilder"""
    
    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland',
            steuernummer='12/345/67890',
            ust_id_nr='DE123456789',
            kreditinstitut='Test Bank',
            iban='DE89370400440532013000',
            bic='COBADEFFXXX',
            telefon='030-12345678',
            email='info@test.de'
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            land='Deutschland',
            country_code='DE',
            is_eu=False,
            is_business=True,
            vat_id='DE987654321'
        )
        
        # Create document type
        self.doc_type = DocumentType.objects.create(
            key='rechnung',
            name='Rechnung',
            prefix='R',
            is_invoice=True,
            requires_due_date=True
        )
        
        # Create tax rates
        self.tax_19 = TaxRate.objects.create(code='normal', name='Normal 19%', rate=Decimal('0.19'))
        self.tax_7 = TaxRate.objects.create(code='reduced', name='Ermäßigt 7%', rate=Decimal('0.07'))
        self.tax_0 = TaxRate.objects.create(code='zero', name='Steuerfrei 0%', rate=Decimal('0.00'))
        
        # Create unit
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')
        
        # Create document
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00001',
            status='OPEN',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            subject='Test Rechnung',
            header_text='<p>Vielen Dank für Ihren Auftrag.</p>',
            footer_text='<p>Bitte überweisen Sie den Betrag innerhalb von 14 Tagen.</p>',
            payment_term_text='Zahlbar innerhalb von 14 Tagen ohne Abzug.',
            total_net=Decimal('1000.00'),
            total_tax=Decimal('190.00'),
            total_gross=Decimal('1190.00')
        )
        
        # Create lines
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Artikel 1',
            long_text='Beschreibung Artikel 1',
            description='Artikel 1',
            unit=self.unit,
            quantity=Decimal('10.00'),
            unit_price_net=Decimal('50.00'),
            discount=Decimal('0.00'),
            line_net=Decimal('500.00'),
            line_tax=Decimal('95.00'),
            line_gross=Decimal('595.00'),
            tax_rate=self.tax_19
        )
        
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Artikel 2',
            description='Artikel 2',
            unit=self.unit,
            quantity=Decimal('5.00'),
            unit_price_net=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_net=Decimal('500.00'),
            line_tax=Decimal('95.00'),
            line_gross=Decimal('595.00'),
            tax_rate=self.tax_19
        )
    
    def test_build_context_company(self):
        """Test company context building"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        self.assertIn('company', context)
        company_ctx = context['company']
        
        self.assertEqual(company_ctx['name'], 'Test GmbH')
        self.assertEqual(company_ctx['tax_number'], '12/345/67890')
        self.assertEqual(company_ctx['vat_id'], 'DE123456789')
        self.assertIn('Teststraße 1', company_ctx['address_lines'])
        self.assertIn('12345 Berlin', company_ctx['address_lines'])
        self.assertIsNotNone(company_ctx['bank_info'])
    
    def test_build_context_customer(self):
        """Test customer context building"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        self.assertIn('customer', context)
        customer_ctx = context['customer']
        
        self.assertEqual(customer_ctx['name'], 'Kunde GmbH')
        self.assertEqual(customer_ctx['vat_id'], 'DE987654321')
        self.assertEqual(customer_ctx['country_code'], 'DE')
        self.assertIn('Kunde GmbH', customer_ctx['address_lines'])
        self.assertIn('Kundenstraße 10', customer_ctx['address_lines'])
    
    def test_build_context_document(self):
        """Test document context building"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        self.assertIn('doc', context)
        doc_ctx = context['doc']
        
        self.assertEqual(doc_ctx['number'], 'R26-00001')
        self.assertEqual(doc_ctx['subject'], 'Test Rechnung')
        self.assertEqual(doc_ctx['issue_date'], date.today())
        self.assertEqual(doc_ctx['due_date'], date.today() + timedelta(days=14))
        self.assertIn('Vielen Dank', doc_ctx['header_html'])
        self.assertIn('überweisen', doc_ctx['footer_html'])
    
    def test_build_context_lines(self):
        """Test lines context building"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        self.assertIn('lines', context)
        lines = context['lines']
        
        self.assertEqual(len(lines), 2)
        
        # Check first line
        line1 = lines[0]
        self.assertEqual(line1['pos'], 1)
        self.assertEqual(line1['qty'], Decimal('10.00'))
        self.assertEqual(line1['unit'], 'Stk')
        self.assertEqual(line1['short_text'], 'Artikel 1')
        self.assertEqual(line1['unit_price_net'], Decimal('50.00'))
        self.assertEqual(line1['net'], Decimal('500.00'))
    
    def test_build_context_totals(self):
        """Test totals context building with tax splits"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        self.assertIn('totals', context)
        totals = context['totals']
        
        # All lines are 19% tax
        self.assertEqual(totals['net_19'], Decimal('1000.00'))
        self.assertEqual(totals['net_7'], Decimal('0.00'))
        self.assertEqual(totals['net_0'], Decimal('0.00'))
        self.assertEqual(totals['net_total'], Decimal('1000.00'))
        self.assertEqual(totals['tax_total'], Decimal('190.00'))
        self.assertEqual(totals['gross_total'], Decimal('1190.00'))
    
    def test_build_context_tax_notes_no_special_case(self):
        """Test tax notes for normal domestic customer"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        self.assertIn('tax_notes', context)
        tax_notes = context['tax_notes']
        
        # No special tax notes for domestic customer
        self.assertIsNone(tax_notes['reverse_charge_text'])
        self.assertIsNone(tax_notes['export_text'])
    
    def test_build_context_tax_notes_reverse_charge(self):
        """Test tax notes for EU reverse charge"""
        # Update customer to EU business with VAT ID
        self.customer.country_code = 'FR'
        self.customer.is_eu = True
        self.customer.is_business = True
        self.customer.vat_id = 'FR12345678901'
        self.customer.save()
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        tax_notes = context['tax_notes']
        
        # Should have reverse charge text
        self.assertIsNotNone(tax_notes['reverse_charge_text'])
        self.assertIn('Reverse Charge', tax_notes['reverse_charge_text'])
        self.assertIsNone(tax_notes['export_text'])
    
    def test_build_context_tax_notes_export(self):
        """Test tax notes for export (third country)"""
        # Update customer to non-EU
        self.customer.country_code = 'US'
        self.customer.is_eu = False
        self.customer.save()
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        tax_notes = context['tax_notes']
        
        # Should have export text
        self.assertIsNotNone(tax_notes['export_text'])
        self.assertIn('Ausfuhrlieferung', tax_notes['export_text'])
        self.assertIsNone(tax_notes['reverse_charge_text'])
    
    def test_get_template_name(self):
        """Test template name retrieval"""
        builder = SalesDocumentInvoiceContextBuilder()
        template_name = builder.get_template_name(self.document)
        
        self.assertEqual(template_name, 'printing/orders/invoice.html')


class DocumentPdfViewTest(TestCase):
    """Tests for document PDF download endpoint"""
    
    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        
        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin'
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            land='Deutschland'
        )
        
        # Create document type
        self.doc_type = DocumentType.objects.create(
            key='rechnung',
            name='Rechnung',
            prefix='R',
            is_invoice=True
        )
        
        # Create tax rate
        self.tax_19 = TaxRate.objects.create(code='normal', name='Normal 19%', rate=Decimal('0.19'))
        
        # Create unit
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')
        
        # Create document
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00001',
            status='OPEN',
            issue_date=date.today(),
            subject='Test Rechnung',
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )
        
        # Create at least one line
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Test Artikel',
            description='Test Artikel',
            unit=self.unit,
            quantity=Decimal('1.00'),
            unit_price_net=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00'),
            tax_rate=self.tax_19
        )
    
    def test_pdf_endpoint_requires_login(self):
        """Test that PDF endpoint requires authentication"""
        url = reverse('auftragsverwaltung:document_pdf', kwargs={'pk': self.document.pk})
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_pdf_endpoint_generates_pdf(self):
        """Test that PDF endpoint generates a valid PDF"""
        self.client.login(username='testuser', password='testpass')
        url = reverse('auftragsverwaltung:document_pdf', kwargs={'pk': self.document.pk})
        
        response = self.client.get(url)
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should have PDF content type
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Should have content disposition
        self.assertIn('filename=', response['Content-Disposition'])
        self.assertIn('Rechnung_R26-00001.pdf', response['Content-Disposition'])
        
        # Should have PDF content (check magic bytes)
        content = b''.join(response.streaming_content) if hasattr(response, 'streaming_content') else response.content
        self.assertTrue(len(content) > 0)
        self.assertTrue(content.startswith(b'%PDF'))
    
    def test_pdf_endpoint_404_for_invalid_document(self):
        """Test that PDF endpoint returns 404 for non-existent document"""
        self.client.login(username='testuser', password='testpass')
        url = reverse('auftragsverwaltung:document_pdf', kwargs={'pk': 99999})
        
        response = self.client.get(url)
        
        # Should return 404
        self.assertEqual(response.status_code, 404)


class MultiPagePdfTest(TestCase):
    """Tests for multi-page PDF generation"""
    
    def setUp(self):
        """Set up test data for multi-page PDF"""
        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin'
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            land='Deutschland'
        )
        
        # Create document type
        self.doc_type = DocumentType.objects.create(
            key='rechnung',
            name='Rechnung',
            prefix='R',
            is_invoice=True
        )
        
        # Create tax rate
        self.tax_19 = TaxRate.objects.create(code='normal', name='Normal 19%', rate=Decimal('0.19'))
        
        # Create unit
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')
        
        # Create document with many lines
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00002',
            status='OPEN',
            issue_date=date.today(),
            subject='Multi-Page Test Rechnung',
            total_net=Decimal('5000.00'),
            total_tax=Decimal('950.00'),
            total_gross=Decimal('5950.00')
        )
        
        # Create 50 lines to force multi-page PDF
        for i in range(1, 51):
            SalesDocumentLine.objects.create(
                document=self.document,
                position_no=i,
                line_type='NORMAL',
                is_selected=True,
                short_text_1=f'Artikel {i}',
                long_text=f'Detaillierte Beschreibung für Artikel {i}. Dies ist ein längerer Text um sicherzustellen, dass mehrere Seiten benötigt werden.',
                description=f'Artikel {i}',
                unit=self.unit,
                quantity=Decimal('1.00'),
                unit_price_net=Decimal('100.00'),
                discount=Decimal('0.00'),
                line_net=Decimal('100.00'),
                line_tax=Decimal('19.00'),
                line_gross=Decimal('119.00'),
                tax_rate=self.tax_19
            )
    
    def test_multi_page_pdf_generation(self):
        """Test that multi-page PDF is generated without errors"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        # Should have 50 lines
        self.assertEqual(len(context['lines']), 50)
        
        # Generate PDF
        pdf_service = PdfRenderService()
        static_root = settings.BASE_DIR / 'static'
        base_url = f'file://{static_root}/'
        
        result = pdf_service.render(
            template_name='printing/orders/invoice.html',
            context=context,
            base_url=base_url,
            filename='test-multi-page.pdf'
        )
        
        # Should have PDF bytes
        self.assertIsNotNone(result.pdf_bytes)
        self.assertGreater(len(result.pdf_bytes), 1000)  # Should be substantial
        
        # Should be valid PDF (check magic bytes)
        self.assertTrue(result.pdf_bytes.startswith(b'%PDF'))
