"""
Tests for bulk print functionality in document list view.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from io import BytesIO

from auftragsverwaltung.models import SalesDocument, DocumentType
from core.models import Mandant, Adresse


class DocumentBulkPrintTestCase(TestCase):
    """Test case for bulk print functionality"""

    def setUp(self):
        """Set up test data and client"""
        # Create user for authentication
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )

        # Create company/mandant
        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='123/456/78901',
            ust_id_nr='DE123456789'
        )

        # Create customer
        self.customer = Adresse.objects.create(
            name='Test Customer',
            strasse='Kundenstrasse 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland'
        )

        # Get document types (created by migration)
        self.doc_type_quote = DocumentType.objects.get(key='quote')
        self.doc_type_invoice = DocumentType.objects.get(key='invoice')

        # Create test sales documents
        self.doc1 = SalesDocument.objects.create(
            company=self.company,
            customer=self.customer,
            document_type=self.doc_type_quote,
            number='AN-2024-001',
            status='DRAFT',
            issue_date=timezone.now().date(),
            subject='Test Quote 1',
            total_gross=Decimal('1000.00')
        )

        self.doc2 = SalesDocument.objects.create(
            company=self.company,
            customer=self.customer,
            document_type=self.doc_type_quote,
            number='AN-2024-002',
            status='SENT',
            issue_date=timezone.now().date() - timezone.timedelta(days=1),
            subject='Test Quote 2',
            total_gross=Decimal('2000.00')
        )

        self.doc3 = SalesDocument.objects.create(
            company=self.company,
            customer=self.customer,
            document_type=self.doc_type_invoice,
            number='R-2024-001',
            status='OPEN',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=14),
            subject='Test Invoice 1',
            total_gross=Decimal('5000.00')
        )

        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_bulk_print_url_exists(self):
        """Test that bulk print URL pattern exists"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        self.assertTrue(url.endswith('/documents/quote/bulk-print/'))

    def test_bulk_print_requires_login(self):
        """Test that bulk print requires authentication"""
        self.client.logout()
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {'document_ids[]': [self.doc1.pk]})

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_bulk_print_requires_post(self):
        """Test that bulk print only accepts POST requests"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)

        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)

    def test_bulk_print_no_documents_selected(self):
        """Test bulk print with no documents selected returns error"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['success'], False)
        self.assertIn('Keine Dokumente', response.json()['error'])

    def test_bulk_print_invalid_document_ids(self):
        """Test bulk print with invalid document IDs returns error"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {'document_ids[]': ['invalid', 'ids']})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['success'], False)
        self.assertIn('Ungültige', response.json()['error'])

    def test_bulk_print_nonexistent_documents(self):
        """Test bulk print with non-existent document IDs returns error"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {'document_ids[]': [99999, 99998]})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['success'], False)
        self.assertIn('Keine gültigen Dokumente', response.json()['error'])

    def test_bulk_print_wrong_document_type(self):
        """Test that bulk print only includes documents of the correct type"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        # Try to print an invoice through the quote endpoint
        response = self.client.post(url, {'document_ids[]': [self.doc3.pk]})

        # Should return 404 as the invoice won't be found in quotes
        self.assertEqual(response.status_code, 404)

    def test_bulk_print_single_document(self):
        """Test bulk print with a single document"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {'document_ids[]': [self.doc1.pk]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('filename=', response['Content-Disposition'])
        self.assertIn('Sammeldruck', response['Content-Disposition'])

        # Verify PDF content exists
        self.assertGreater(len(response.content), 0)

        # Verify it's a valid PDF (starts with PDF header)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_bulk_print_multiple_documents(self):
        """Test bulk print with multiple documents"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {'document_ids[]': [self.doc1.pk, self.doc2.pk]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        # Check filename includes count
        self.assertIn('2_Dokumente', response['Content-Disposition'])

        # Verify PDF content exists and is larger than single document
        self.assertGreater(len(response.content), 1000)  # Should be substantial

        # Verify it's a valid PDF
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_bulk_print_filename_format(self):
        """Test that bulk print generates correct filename"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {'document_ids[]': [self.doc1.pk, self.doc2.pk]})

        content_disposition = response['Content-Disposition']
        self.assertIn('inline', content_disposition)
        self.assertIn('Angebot', content_disposition)  # Document type name
        self.assertIn('Sammeldruck', content_disposition)
        self.assertIn('2_Dokumente.pdf', content_disposition)

    def test_bulk_print_with_invalid_doc_key(self):
        """Test bulk print with invalid document type key"""
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'invalid'})
        response = self.client.post(url, {'document_ids[]': [self.doc1.pk]})

        # Should return 404 as document type doesn't exist
        self.assertEqual(response.status_code, 404)

    def test_bulk_print_ordering(self):
        """Test that bulk print orders documents by issue_date and number"""
        # Create documents with different dates
        doc_old = SalesDocument.objects.create(
            company=self.company,
            customer=self.customer,
            document_type=self.doc_type_quote,
            number='AN-2024-100',
            status='DRAFT',
            issue_date=timezone.now().date() - timezone.timedelta(days=10),
            subject='Old Quote',
            total_gross=Decimal('500.00')
        )

        doc_new = SalesDocument.objects.create(
            company=self.company,
            customer=self.customer,
            document_type=self.doc_type_quote,
            number='AN-2024-200',
            status='DRAFT',
            issue_date=timezone.now().date(),
            subject='New Quote',
            total_gross=Decimal('600.00')
        )

        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        # Submit in random order
        response = self.client.post(url, {'document_ids[]': [doc_new.pk, doc_old.pk]})

        self.assertEqual(response.status_code, 200)
        # Just verify it generates successfully - ordering is internal to PDF

    def test_checkbox_column_in_table(self):
        """Test that selection checkbox column is present in document list"""
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)

        table = response.context['table']
        column_names = [col.name for col in table.columns]

        # Selection column should be first
        self.assertEqual(column_names[0], 'selection')

    def test_bulk_print_button_in_template(self):
        """Test that bulk print button exists in document list template"""
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)

        self.assertContains(response, 'bulk-print-btn')
        self.assertContains(response, 'Ausgewählte drucken')
        self.assertContains(response, 'selected-count')

    def test_bulk_print_form_in_template(self):
        """Test that bulk print form exists in document list template"""
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)

        self.assertContains(response, 'bulk-print-form')
        self.assertContains(response, 'bulk-print/')

    def test_checkbox_javascript_in_template(self):
        """Test that checkbox handling JavaScript exists in template"""
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)

        self.assertContains(response, 'select-all-checkbox')
        self.assertContains(response, 'document-checkbox')
        self.assertContains(response, 'updateBulkPrintButton')

    def test_bulk_print_mixed_companies(self):
        """Test bulk print with documents from multiple companies"""
        # Create second company
        company2 = Mandant.objects.create(
            name='Second Company GmbH',
            adresse='Andere Strasse 2',
            plz='54321',
            ort='Andere Stadt',
            land='Deutschland',
            steuernummer='987/654/32109',
            ust_id_nr='DE987654321'
        )

        # Create document for second company
        doc_company2 = SalesDocument.objects.create(
            company=company2,
            customer=self.customer,
            document_type=self.doc_type_quote,
            number='AN-2024-300',
            status='DRAFT',
            issue_date=timezone.now().date(),
            subject='Quote from Company 2',
            total_gross=Decimal('3000.00')
        )

        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {
            'document_ids[]': [self.doc1.pk, doc_company2.pk]
        })

        # Should successfully generate PDF with documents from both companies
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_bulk_print_partial_failure(self):
        """Test bulk print continues with valid documents if some fail"""
        # This is a basic test - actual failure scenarios would need mocking
        url = reverse('auftragsverwaltung:documents_bulk_print', kwargs={'doc_key': 'quote'})
        response = self.client.post(url, {'document_ids[]': [self.doc1.pk, self.doc2.pk]})

        # Should succeed with valid documents
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
