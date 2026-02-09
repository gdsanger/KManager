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
        self.assertIn('Ausfuhr', tax_notes['export_text'])
        self.assertIsNone(tax_notes['reverse_charge_text'])
    
    def test_build_context_company_logo_url_not_set(self):
        """Test company context with no logo"""
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        
        company_ctx = context['company']
        
        # No logo should result in None
        self.assertIsNone(company_ctx['logo_url'])
    
    def test_build_context_company_logo_url_with_logo(self):
        """Test company context with logo file"""
        import os
        from io import BytesIO
        from PIL import Image
        
        # Create a test logo file
        test_logo_dir = os.path.join(settings.MEDIA_ROOT, 'mandants')
        os.makedirs(test_logo_dir, exist_ok=True)
        
        logo_filename = 'test_logo.png'
        logo_relative_path = os.path.join('mandants', logo_filename)
        logo_full_path = os.path.join(settings.MEDIA_ROOT, logo_relative_path)
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(logo_full_path, 'PNG')
        
        try:
            # Set logo path on company
            self.company.logo_path = logo_relative_path
            self.company.save()
            
            # Build context
            builder = SalesDocumentInvoiceContextBuilder()
            context = builder.build_context(self.document)
            
            company_ctx = context['company']
            
            # Logo URL should be set as file:// URL for WeasyPrint
            self.assertIsNotNone(company_ctx['logo_url'])
            self.assertTrue(company_ctx['logo_url'].startswith('file://'))
            self.assertIn(logo_relative_path, company_ctx['logo_url'])
        
        finally:
            # Clean up test file
            if os.path.exists(logo_full_path):
                os.remove(logo_full_path)
            if os.path.exists(test_logo_dir) and not os.listdir(test_logo_dir):
                os.rmdir(test_logo_dir)
    
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


class DocumentPreviewViewTest(TestCase):
    """Tests for document PDF preview endpoint (read-only, no side effects)"""
    
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
    
    def test_preview_endpoint_requires_login(self):
        """Test that preview endpoint requires authentication"""
        url = reverse('auftragsverwaltung:document_preview', kwargs={'pk': self.document.pk})
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_preview_endpoint_generates_pdf(self):
        """Test that preview endpoint generates a valid PDF"""
        self.client.login(username='testuser', password='testpass')
        url = reverse('auftragsverwaltung:document_preview', kwargs={'pk': self.document.pk})
        
        response = self.client.get(url)
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should have PDF content type
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Should have inline content disposition
        self.assertIn('inline', response['Content-Disposition'])
        self.assertIn('filename=', response['Content-Disposition'])
        
        # Filename should use document type name and ID (not number)
        self.assertIn(f'{self.doc_type.name}_{self.document.id}.pdf', response['Content-Disposition'])
        
        # Should have PDF content (check magic bytes)
        content = b''.join(response.streaming_content) if hasattr(response, 'streaming_content') else response.content
        self.assertTrue(len(content) > 0)
        self.assertTrue(content.startswith(b'%PDF'))
    
    def test_preview_endpoint_404_for_invalid_document(self):
        """Test that preview endpoint returns 404 for non-existent document"""
        self.client.login(username='testuser', password='testpass')
        url = reverse('auftragsverwaltung:document_preview', kwargs={'pk': 99999})
        
        response = self.client.get(url)
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_preview_has_no_side_effects(self):
        """Test that preview does not modify the document or create snapshots"""
        self.client.login(username='testuser', password='testpass')
        
        # Store original document state
        original_status = self.document.status
        original_number = self.document.number
        original_updated_at = self.document.updated_at
        
        # Call preview endpoint
        url = reverse('auftragsverwaltung:document_preview', kwargs={'pk': self.document.pk})
        response = self.client.get(url)
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Reload document from database
        self.document.refresh_from_db()
        
        # Verify no changes to document
        self.assertEqual(self.document.status, original_status)
        self.assertEqual(self.document.number, original_number)
        self.assertEqual(self.document.updated_at, original_updated_at)
        
        # Note: This test verifies basic read-only behavior.
        # Additional checks for snapshots would require snapshot model implementation.


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


class GenericTemplateDocumentTypeTest(TestCase):
    """Tests for generic invoice.html template with dynamic document type heading"""
    
    def setUp(self):
        """Set up test data for multiple document types"""
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
        
        # Create multiple document types
        self.doc_type_invoice = DocumentType.objects.create(
            key='rechnung',
            name='Rechnung',
            prefix='R',
            is_invoice=True
        )
        
        self.doc_type_quote = DocumentType.objects.create(
            key='angebot',
            name='Angebot',
            prefix='A',
            is_invoice=False
        )
        
        self.doc_type_order = DocumentType.objects.create(
            key='auftrag',
            name='Auftragsbestätigung',
            prefix='AB',
            is_invoice=False
        )
        
        # Create tax rate
        self.tax_19 = TaxRate.objects.create(code='normal', name='Normal 19%', rate=Decimal('0.19'))
        
        # Create unit
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')
    
    def _create_document(self, doc_type, number_suffix):
        """Helper to create a test document with a given document type"""
        document = SalesDocument.objects.create(
            company=self.company,
            document_type=doc_type,
            customer=self.customer,
            number=f'{doc_type.prefix}26-{number_suffix:05d}',
            status='OPEN',
            issue_date=date.today(),
            subject=f'Test {doc_type.name}',
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )
        
        # Create at least one line
        SalesDocumentLine.objects.create(
            document=document,
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
        
        return document
    
    def test_context_includes_document_type_name_for_invoice(self):
        """Test that context includes document_type_name for invoice"""
        document = self._create_document(self.doc_type_invoice, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        self.assertIn('doc', context)
        self.assertIn('document_type_name', context['doc'])
        self.assertEqual(context['doc']['document_type_name'], 'Rechnung')
    
    def test_context_includes_document_type_name_for_quote(self):
        """Test that context includes document_type_name for quote"""
        document = self._create_document(self.doc_type_quote, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        self.assertIn('doc', context)
        self.assertIn('document_type_name', context['doc'])
        self.assertEqual(context['doc']['document_type_name'], 'Angebot')
    
    def test_context_includes_document_type_name_for_order(self):
        """Test that context includes document_type_name for order confirmation"""
        document = self._create_document(self.doc_type_order, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        self.assertIn('doc', context)
        self.assertIn('document_type_name', context['doc'])
        self.assertEqual(context['doc']['document_type_name'], 'Auftragsbestätigung')
    
    def test_html_output_contains_correct_heading_for_invoice(self):
        """Test that rendered HTML contains correct heading for invoice"""
        document = self._create_document(self.doc_type_invoice, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        # Render template to HTML
        from django.template.loader import render_to_string
        html = render_to_string('printing/orders/invoice.html', context)
        
        # Check that heading is present
        self.assertIn('<h1>Rechnung</h1>', html)
        # Ensure old hardcoded heading is not duplicated
        self.assertEqual(html.count('<h1>Rechnung</h1>'), 1)
    
    def test_html_output_contains_correct_heading_for_quote(self):
        """Test that rendered HTML contains correct heading for quote"""
        document = self._create_document(self.doc_type_quote, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        # Render template to HTML
        from django.template.loader import render_to_string
        html = render_to_string('printing/orders/invoice.html', context)
        
        # Check that heading is present and correct
        self.assertIn('<h1>Angebot</h1>', html)
        # Ensure invoice heading is NOT present
        self.assertNotIn('<h1>Rechnung</h1>', html)
    
    def test_html_output_contains_correct_heading_for_order(self):
        """Test that rendered HTML contains correct heading for order confirmation"""
        document = self._create_document(self.doc_type_order, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        # Render template to HTML
        from django.template.loader import render_to_string
        html = render_to_string('printing/orders/invoice.html', context)
        
        # Check that heading is present and correct
        self.assertIn('<h1>Auftragsbestätigung</h1>', html)
        # Ensure invoice heading is NOT present
        self.assertNotIn('<h1>Rechnung</h1>', html)
    
    def test_fallback_to_key_when_name_is_empty(self):
        """Test fallback to key when name is empty"""
        # Create a document type with empty name
        doc_type_no_name = DocumentType.objects.create(
            key='special',
            name='',  # Empty name
            prefix='SP',
            is_invoice=False
        )
        
        document = self._create_document(doc_type_no_name, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        # Should fall back to key
        self.assertEqual(context['doc']['document_type_name'], 'special')
    
    def test_fallback_to_key_when_name_is_whitespace(self):
        """Test fallback to key when name is only whitespace"""
        # Create a document type with whitespace-only name
        doc_type_whitespace_name = DocumentType.objects.create(
            key='whitespace',
            name='   ',  # Whitespace only
            prefix='WS',
            is_invoice=False
        )
        
        document = self._create_document(doc_type_whitespace_name, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        # Should fall back to key
        self.assertEqual(context['doc']['document_type_name'], 'whitespace')
    
    def test_fallback_to_dokument_when_name_and_key_are_empty(self):
        """Test fallback to 'Dokument' when both name and key are problematic"""
        # Create a document type with empty name and key
        # Note: This scenario is unlikely in practice due to model validation,
        # but we test the fallback logic
        doc_type_empty = DocumentType.objects.create(
            key='k',
            name='',
            prefix='X',
            is_invoice=False
        )
        # Manually set empty key to test fallback (bypassing validation)
        doc_type_empty.key = ''
        doc_type_empty.save(update_fields=['key'])
        
        document = self._create_document(doc_type_empty, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(document)
        
        # Should fall back to "Dokument"
        self.assertEqual(context['doc']['document_type_name'], 'Dokument')
    
    def test_fallback_when_document_type_is_none(self):
        """Test fallback to 'Dokument' when document_type is None"""
        # Create a document without document_type
        # This requires bypassing the NOT NULL constraint, so we'll use a mock
        from unittest.mock import Mock
        
        # Create a mock document with None document_type
        mock_document = Mock()
        mock_document.document_type = None
        mock_document.number = 'TEST-001'
        mock_document.subject = ''
        mock_document.issue_date = date.today()
        mock_document.due_date = None
        mock_document.payment_term_text = ''
        mock_document.header_text = ''
        mock_document.footer_text = ''
        mock_document.reference_number = ''
        mock_document.notes_public = ''
        
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder._build_document_context(mock_document)
        
        # Should fall back to "Dokument"
        self.assertEqual(context['document_type_name'], 'Dokument')
    
    def test_no_exception_with_missing_attributes(self):
        """Test that no exception is raised when attributes are missing"""
        from unittest.mock import Mock
        
        # Create a mock document with missing attributes
        mock_document = Mock()
        mock_document.document_type = Mock()
        # Don't set name or key attributes
        del mock_document.document_type.name
        del mock_document.document_type.key
        mock_document.number = 'TEST-001'
        mock_document.subject = ''
        mock_document.issue_date = date.today()
        mock_document.due_date = None
        mock_document.payment_term_text = ''
        mock_document.header_text = ''
        mock_document.footer_text = ''
        mock_document.reference_number = ''
        mock_document.notes_public = ''
        
        builder = SalesDocumentInvoiceContextBuilder()
        
        # Should not raise exception
        try:
            context = builder._build_document_context(mock_document)
            # Should fall back to "Dokument"
            self.assertEqual(context['document_type_name'], 'Dokument')
        except Exception as e:
            self.fail(f"Expected no exception, but got: {e}")
    
    def test_pdf_generation_for_different_document_types(self):
        """Test that PDF generation works for different document types"""
        # Test invoice
        invoice_doc = self._create_document(self.doc_type_invoice, 1)
        
        builder = SalesDocumentInvoiceContextBuilder()
        context_invoice = builder.build_context(invoice_doc)
        
        pdf_service = PdfRenderService()
        static_root = settings.BASE_DIR / 'static'
        base_url = f'file://{static_root}/'
        
        result_invoice = pdf_service.render(
            template_name='printing/orders/invoice.html',
            context=context_invoice,
            base_url=base_url,
            filename='test-invoice.pdf'
        )
        
        # Should generate valid PDF
        self.assertIsNotNone(result_invoice.pdf_bytes)
        self.assertTrue(result_invoice.pdf_bytes.startswith(b'%PDF'))
        
        # Test quote
        quote_doc = self._create_document(self.doc_type_quote, 2)
        
        context_quote = builder.build_context(quote_doc)
        
        result_quote = pdf_service.render(
            template_name='printing/orders/invoice.html',
            context=context_quote,
            base_url=base_url,
            filename='test-quote.pdf'
        )
        
        # Should generate valid PDF
        self.assertIsNotNone(result_quote.pdf_bytes)
        self.assertTrue(result_quote.pdf_bytes.startswith(b'%PDF'))
        
        # PDFs should be different (different content)
        self.assertNotEqual(result_invoice.pdf_bytes, result_quote.pdf_bytes)
