"""
Tests for Auftragsverwaltung Dashboard functionality.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Mandant


class DashboardTestCase(TestCase):
    """Test case for Auftragsverwaltung Dashboard."""

    def setUp(self):
        """Set up test data for all tests."""
        # Create a user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )

        # Create a company (Mandant)
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City",
            land="Deutschland"
        )

        # Get document types (created by migration)
        self.doctype_invoice = DocumentType.objects.get(key="invoice")
        self.doctype_quote = DocumentType.objects.get(key="quote")

        # Login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_dashboard_open_documents_have_clickable_links(self):
        """Test that open sales documents have clickable Nummer and Betreff fields."""
        # Create some open documents
        doc1 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            subject="Test Invoice 1",
            status="SENT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8),
            total_net=Decimal('1000.00'),
            total_tax=Decimal('190.00'),
            total_gross=Decimal('1190.00')
        )

        doc2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00001",
            subject="Test Quote 1",
            status="DRAFT",
            issue_date=date(2026, 2, 7),
            total_net=Decimal('500.00'),
            total_tax=Decimal('95.00'),
            total_gross=Decimal('595.00')
        )

        response = self.client.get(reverse('auftragsverwaltung:home'))

        self.assertEqual(response.status_code, 200)

        # Check that the response contains links to document details
        # For doc1 (invoice)
        expected_url_doc1 = reverse('auftragsverwaltung:document_detail',
                                    kwargs={'doc_key': 'invoice', 'pk': doc1.pk})
        self.assertContains(response, f'href="{expected_url_doc1}"')

        # Check that Nummer is wrapped in a link
        self.assertContains(response, f'<a href="{expected_url_doc1}">{doc1.number}</a>')

        # Check that Betreff is wrapped in a link
        self.assertContains(response, f'<a href="{expected_url_doc1}">{doc1.subject}</a>')

        # For doc2 (quote)
        expected_url_doc2 = reverse('auftragsverwaltung:document_detail',
                                    kwargs={'doc_key': 'quote', 'pk': doc2.pk})
        self.assertContains(response, f'href="{expected_url_doc2}"')
        self.assertContains(response, f'<a href="{expected_url_doc2}">{doc2.number}</a>')
        self.assertContains(response, f'<a href="{expected_url_doc2}">{doc2.subject}</a>')

    def test_dashboard_latest_documents_have_clickable_links(self):
        """Test that latest 10 documents have clickable Nummer and Betreff fields."""
        # Create some documents with different statuses
        doc1 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00010",
            subject="Recent Invoice",
            status="PAID",
            issue_date=date(2026, 2, 15),
            due_date=date(2026, 3, 17),
            total_net=Decimal('2000.00'),
            total_tax=Decimal('380.00'),
            total_gross=Decimal('2380.00')
        )

        response = self.client.get(reverse('auftragsverwaltung:home'))

        self.assertEqual(response.status_code, 200)

        # Check that the response contains links to document details in "Letzte 10 Dokumente"
        expected_url = reverse('auftragsverwaltung:document_detail',
                              kwargs={'doc_key': 'invoice', 'pk': doc1.pk})

        # Should appear in the latest documents section
        self.assertContains(response, f'href="{expected_url}"')
        self.assertContains(response, f'<a href="{expected_url}">{doc1.number}</a>')
        self.assertContains(response, f'<a href="{expected_url}">{doc1.subject}</a>')

    def test_dashboard_links_use_document_type_key(self):
        """Test that links correctly use the document_type.key for URL construction."""
        # Create documents with different document types
        invoice_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00020",
            subject="Invoice Test",
            status="SENT",
            issue_date=date(2026, 2, 20),
            due_date=date(2026, 3, 22),
            total_net=Decimal('1500.00'),
            total_tax=Decimal('285.00'),
            total_gross=Decimal('1785.00')
        )

        quote_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00020",
            subject="Quote Test",
            status="DRAFT",
            issue_date=date(2026, 2, 21),
            total_net=Decimal('750.00'),
            total_tax=Decimal('142.50'),
            total_gross=Decimal('892.50')
        )

        response = self.client.get(reverse('auftragsverwaltung:home'))

        self.assertEqual(response.status_code, 200)

        # Verify that invoice uses 'invoice' key
        invoice_url = reverse('auftragsverwaltung:document_detail',
                             kwargs={'doc_key': 'invoice', 'pk': invoice_doc.pk})
        self.assertContains(response, invoice_url)

        # Verify that quote uses 'quote' key
        quote_url = reverse('auftragsverwaltung:document_detail',
                           kwargs={'doc_key': 'quote', 'pk': quote_doc.pk})
        self.assertContains(response, quote_url)

    def test_dashboard_empty_lists_no_links(self):
        """Test that dashboard handles empty document lists gracefully."""
        response = self.client.get(reverse('auftragsverwaltung:home'))

        self.assertEqual(response.status_code, 200)

        # Should display messages for empty lists
        self.assertContains(response, 'Keine offenen Dokumente vorhanden')
        self.assertContains(response, 'Keine Dokumente vorhanden')
