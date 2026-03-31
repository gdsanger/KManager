"""
Tests for Invoice Finalization (Echtdruck) and Email Sending
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from decimal import Decimal

from core.models import Mandant, Adresse, MailTemplate, SmtpSettings
from auftragsverwaltung.models import SalesDocument, DocumentType, SalesDocumentLine
from auftragsverwaltung.services.invoice_finalization import finalize_invoice
from auftragsverwaltung.services.invoice_email import send_invoice_email, InvoiceEmailError


User = get_user_model()


class InvoiceFinalizationTestCase(TestCase):
    """Test invoice finalization (Echtdruck) service"""

    def setUp(self):
        """Create test data"""
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Deutschland",
            invoice_email="customer@example.com"
        )
        self.doc_type_invoice = DocumentType.objects.get(key="invoice")

        # Create a draft invoice without number
        self.invoice = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            customer=self.customer,
            status='DRAFT',
            issue_date=timezone.now().date(),
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )

    def test_finalize_assigns_number_when_missing(self):
        """Test that finalize assigns a number when invoice has no number"""
        # Invoice has no number initially
        self.assertFalse(self.invoice.number)
        self.assertEqual(self.invoice.status, 'DRAFT')

        # Finalize
        invoice, was_modified = finalize_invoice(self.invoice)

        # Should assign number and set status
        self.assertTrue(invoice.number)
        self.assertEqual(invoice.status, 'SENT')
        self.assertTrue(was_modified)

    def test_finalize_is_idempotent(self):
        """Test that finalize doesn't change number on subsequent calls"""
        # First finalization
        invoice, was_modified1 = finalize_invoice(self.invoice)
        first_number = invoice.number

        self.assertTrue(first_number)
        self.assertTrue(was_modified1)

        # Second finalization (idempotent)
        invoice, was_modified2 = finalize_invoice(invoice)

        # Number should remain the same
        self.assertEqual(invoice.number, first_number)
        self.assertFalse(was_modified2)

    def test_finalize_sets_status_to_sent(self):
        """Test that finalize sets status to SENT"""
        invoice, _ = finalize_invoice(self.invoice)
        self.assertEqual(invoice.status, 'SENT')

    def test_finalize_with_existing_number(self):
        """Test finalize with invoice that already has a number"""
        # Manually set a number
        self.invoice.number = 'R26-00099'
        self.invoice.save()

        # Finalize
        invoice, was_modified = finalize_invoice(self.invoice)

        # Should keep the existing number
        self.assertEqual(invoice.number, 'R26-00099')
        self.assertTrue(was_modified)  # Status changed

    def test_finalize_fails_for_non_invoice(self):
        """Test that finalize raises error for non-invoice documents"""
        # Create a quote (not an invoice)
        doc_type_quote = DocumentType.objects.get(key="quote")
        quote = SalesDocument.objects.create(
            company=self.company,
            document_type=doc_type_quote,
            customer=self.customer,
            status='DRAFT',
            issue_date=timezone.now().date()
        )

        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            finalize_invoice(quote)

        self.assertIn('not an invoice', str(cm.exception))


class InvoiceEmailServiceTestCase(TestCase):
    """Test invoice email sending service"""

    def setUp(self):
        """Create test data"""
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Deutschland",
            invoice_email="customer@example.com"
        )
        self.doc_type_invoice = DocumentType.objects.get(key="invoice")

        # Create invoice
        self.invoice = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            customer=self.customer,
            status='DRAFT',
            issue_date=timezone.now().date(),
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )

        # Create SMTP settings
        SmtpSettings.objects.create(
            host='localhost',
            port=1025,
            use_tls=False
        )

        # Get or create mail template (migration may have created it)
        template, _ = MailTemplate.objects.get_or_create(
            key='invoice-sent',
            defaults={
                'subject': 'Rechnung {{ invoice_number }}',
                'message': '<p>Test</p>',
                'from_address': 'accounting@company.de',
                'is_active': True
            }
        )
        # Update from_address if it was created by migration
        if not template.from_address:
            template.from_address = 'accounting@company.de'
            template.save()

    @patch('auftragsverwaltung.services.invoice_email.PdfRenderService')
    @patch('core.mailing.service.smtplib.SMTP')
    def test_send_to_customer(self, mock_smtp, mock_pdf_service):
        """Test sending invoice to customer"""
        # Mock PDF generation
        mock_pdf_instance = MagicMock()
        mock_pdf_instance.render.return_value = MagicMock(
            pdf_bytes=b'fake-pdf-content',
            filename='Rechnung_R26-00001.pdf'
        )
        mock_pdf_service.return_value = mock_pdf_instance

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Send email
        result = send_invoice_email(
            invoice=self.invoice,
            to_customer=True,
            to_internal=False
        )

        # Check result
        self.assertTrue(result['success'])
        self.assertIn('customer@example.com', result['recipients'])

        # Verify SMTP was called with customer email
        self.assertTrue(mock_server.sendmail.called)
        args = mock_server.sendmail.call_args[0]
        self.assertIn('customer@example.com', args[1])

    @patch('auftragsverwaltung.services.invoice_email.PdfRenderService')
    @patch('core.mailing.service.smtplib.SMTP')
    def test_send_to_customer_and_internal(self, mock_smtp, mock_pdf_service):
        """Test sending to both customer and internal accounting"""
        # Mock PDF generation
        mock_pdf_instance = MagicMock()
        mock_pdf_instance.render.return_value = MagicMock(
            pdf_bytes=b'fake-pdf-content',
            filename='Rechnung_R26-00001.pdf'
        )
        mock_pdf_service.return_value = mock_pdf_instance

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Send email
        result = send_invoice_email(
            invoice=self.invoice,
            to_customer=True,
            to_internal=True
        )

        # Check result
        self.assertTrue(result['success'])
        self.assertIn('customer@example.com', result['recipients'])
        self.assertIn('accounting@company.de', result['recipients'])

        # Verify SMTP recipients include both
        args = mock_server.sendmail.call_args[0]
        recipients = args[1]
        self.assertIn('customer@example.com', recipients)
        self.assertIn('accounting@company.de', recipients)

    @patch('auftragsverwaltung.services.invoice_email.PdfRenderService')
    @patch('core.mailing.service.smtplib.SMTP')
    def test_send_only_internal(self, mock_smtp, mock_pdf_service):
        """Test sending only to internal (print scenario)"""
        # Mock PDF generation
        mock_pdf_instance = MagicMock()
        mock_pdf_instance.render.return_value = MagicMock(
            pdf_bytes=b'fake-pdf-content',
            filename='Rechnung_R26-00001.pdf'
        )
        mock_pdf_service.return_value = mock_pdf_instance

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Send email
        result = send_invoice_email(
            invoice=self.invoice,
            to_customer=False,
            to_internal=True
        )

        # Check result
        self.assertTrue(result['success'])
        self.assertNotIn('customer@example.com', result['recipients'])
        self.assertIn('accounting@company.de', result['recipients'])

    def test_send_without_customer_email_fails(self):
        """Test that sending fails when customer has no invoice_email"""
        # Remove customer email
        self.customer.invoice_email = None
        self.customer.save()

        # Should raise error
        with self.assertRaises(InvoiceEmailError) as cm:
            send_invoice_email(
                invoice=self.invoice,
                to_customer=True,
                to_internal=False
            )

        self.assertIn('keine Rechnungs-E-Mail-Adresse', str(cm.exception))

    @patch('auftragsverwaltung.services.invoice_email.PdfRenderService')
    @patch('core.mailing.service.smtplib.SMTP')
    def test_email_subject_contains_all_parts(self, mock_smtp, mock_pdf_service):
        """Test that email subject contains invoice number, net, gross, customer"""
        # Mock PDF generation
        mock_pdf_instance = MagicMock()
        mock_pdf_instance.render.return_value = MagicMock(
            pdf_bytes=b'fake-pdf-content',
            filename='Rechnung_R26-00001.pdf'
        )
        mock_pdf_service.return_value = mock_pdf_instance

        # Mock SMTP to capture message
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Send email (this also finalizes, which assigns a number)
        send_invoice_email(
            invoice=self.invoice,
            to_customer=True,
            to_internal=False
        )

        # Reload invoice to get the assigned number
        self.invoice.refresh_from_db()

        # Get the mail template to check subject format
        template = MailTemplate.objects.get(key='invoice-sent')

        # Subject should contain placeholders for all required parts
        self.assertIn('invoice_number', template.subject)
        self.assertIn('amount_net', template.subject)
        self.assertIn('amount_gross', template.subject)
        self.assertIn('customer_name', template.subject)

    @patch('auftragsverwaltung.services.invoice_email.PdfRenderService')
    @patch('core.mailing.service.smtplib.SMTP')
    def test_pdf_attachment_is_included(self, mock_smtp, mock_pdf_service):
        """Test that PDF is attached to email"""
        # Mock PDF generation
        mock_pdf_instance = MagicMock()
        mock_pdf_instance.render.return_value = MagicMock(
            pdf_bytes=b'fake-pdf-content',
            filename='Rechnung_R26-00001.pdf'
        )
        mock_pdf_service.return_value = mock_pdf_instance

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Send email
        send_invoice_email(
            invoice=self.invoice,
            to_customer=True,
            to_internal=False
        )

        # Verify PDF service was called
        self.assertTrue(mock_pdf_instance.render.called)

        # Verify sendmail was called (email was sent)
        self.assertTrue(mock_server.sendmail.called)

    @patch('auftragsverwaltung.services.invoice_email.PdfRenderService')
    @patch('core.mailing.service.smtplib.SMTP')
    def test_send_finalizes_invoice_if_needed(self, mock_smtp, mock_pdf_service):
        """Test that sending email also finalizes invoice (assigns number)"""
        # Mock PDF generation
        mock_pdf_instance = MagicMock()
        mock_pdf_instance.render.return_value = MagicMock(
            pdf_bytes=b'fake-pdf-content',
            filename='Rechnung_R26-00001.pdf'
        )
        mock_pdf_service.return_value = mock_pdf_instance

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Invoice has no number initially
        self.assertFalse(self.invoice.number)

        # Send email
        send_invoice_email(
            invoice=self.invoice,
            to_customer=True,
            to_internal=False
        )

        # Reload invoice
        self.invoice.refresh_from_db()

        # Should now have a number and status SENT
        self.assertTrue(self.invoice.number)
        self.assertEqual(self.invoice.status, 'SENT')


class InvoiceViewsTestCase(TestCase):
    """Test invoice finalization and email views"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Deutschland",
            invoice_email="customer@example.com"
        )
        self.doc_type_invoice = DocumentType.objects.get(key="invoice")

        self.invoice = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            customer=self.customer,
            status='DRAFT',
            issue_date=timezone.now().date(),
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )

        # Create mail template and SMTP settings
        SmtpSettings.objects.create(
            host='localhost',
            port=1025,
            use_tls=False
        )
        template, _ = MailTemplate.objects.get_or_create(
            key='invoice-sent',
            defaults={
                'subject': 'Rechnung {{ invoice_number }}',
                'message': '<p>Test</p>',
                'from_address': 'accounting@company.de',
                'is_active': True
            }
        )
        # Update from_address if it was created by migration
        if not template.from_address:
            template.from_address = 'accounting@company.de'
            template.save()

    def test_invoice_finalize_view(self):
        """Test invoice finalize view assigns number and sets status"""
        url = reverse('auftragsverwaltung:invoice_finalize', kwargs={'pk': self.invoice.pk})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertTrue(data['was_modified'])
        self.assertTrue(data['invoice_number'])
        self.assertEqual(data['status'], 'SENT')

    def test_invoice_finalize_is_idempotent_via_view(self):
        """Test that calling finalize view twice doesn't change number"""
        url = reverse('auftragsverwaltung:invoice_finalize', kwargs={'pk': self.invoice.pk})

        # First call
        response1 = self.client.post(url)
        data1 = response1.json()
        first_number = data1['invoice_number']

        # Second call
        response2 = self.client.post(url)
        data2 = response2.json()

        self.assertEqual(data2['invoice_number'], first_number)
        self.assertFalse(data2['was_modified'])

    @patch('auftragsverwaltung.services.invoice_email.send_invoice_email')
    def test_invoice_send_email_view(self, mock_send_email):
        """Test invoice send email view"""
        # Mock the service (import from services not views)
        mock_send_email.return_value = {
            'success': True,
            'recipients': ['customer@example.com', 'accounting@company.de']
        }

        url = reverse('auftragsverwaltung:invoice_send_email', kwargs={'pk': self.invoice.pk})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertIn('customer@example.com', data['recipients'])
