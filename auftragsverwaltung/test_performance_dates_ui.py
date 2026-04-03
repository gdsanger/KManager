"""
Tests for Performance Date UI integration

These tests verify that performance_date_from and performance_date_to fields
are properly handled in the document create and update views.
"""

from datetime import date
from django.test import TestCase, Client
from django.contrib.auth.models import User
from core.models import Mandant, Adresse
from auftragsverwaltung.models import DocumentType, SalesDocument


class PerformanceDateUITest(TestCase):
    """Test suite for performance date fields in the user interface"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Test Street 1',
            plz='12345',
            ort='Test City',
            land='Deutschland'
        )

        # Create customer
        self.customer = Adresse.objects.create(
            name='Test Customer',
            adressen_type='KUNDE'
        )

        # Create document type (or get existing one from migration)
        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'is_active': True
            }
        )

    def test_document_create_with_performance_dates(self):
        """Test creating a document with performance_date_from and performance_date_to"""
        response = self.client.post(
            f'/auftragsverwaltung/documents/{self.doc_type.key}/create/',
            {
                'company_id': self.company.pk,
                'subject': 'Test Invoice',
                'issue_date': '2026-04-01',
                'performance_date_from': '2026-03-01',
                'performance_date_to': '2026-03-31',
                'customer_id': self.customer.pk,
            }
        )

        # Should redirect to detail page on success
        self.assertEqual(response.status_code, 302)

        # Verify document was created with performance dates
        doc = SalesDocument.objects.get(subject='Test Invoice')
        self.assertEqual(doc.performance_date_from, date(2026, 3, 1))
        self.assertEqual(doc.performance_date_to, date(2026, 3, 31))

    def test_document_create_with_performance_date_from_only(self):
        """Test creating a document with only performance_date_from (single day)"""
        response = self.client.post(
            f'/auftragsverwaltung/documents/{self.doc_type.key}/create/',
            {
                'company_id': self.company.pk,
                'subject': 'Test Invoice Single Day',
                'issue_date': '2026-04-01',
                'performance_date_from': '2026-03-15',
                'customer_id': self.customer.pk,
            }
        )

        self.assertEqual(response.status_code, 302)

        doc = SalesDocument.objects.get(subject='Test Invoice Single Day')
        self.assertEqual(doc.performance_date_from, date(2026, 3, 15))
        self.assertIsNone(doc.performance_date_to)

    def test_document_create_without_performance_dates(self):
        """Test creating a document without performance dates (optional fields)"""
        response = self.client.post(
            f'/auftragsverwaltung/documents/{self.doc_type.key}/create/',
            {
                'company_id': self.company.pk,
                'subject': 'Test Invoice No Dates',
                'issue_date': '2026-04-01',
                'customer_id': self.customer.pk,
            }
        )

        self.assertEqual(response.status_code, 302)

        doc = SalesDocument.objects.get(subject='Test Invoice No Dates')
        self.assertIsNone(doc.performance_date_from)
        self.assertIsNone(doc.performance_date_to)

    def test_document_update_with_performance_dates(self):
        """Test updating a document to add performance dates"""
        # Create document without performance dates
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            number='INV-001',
            subject='Test Update',
            issue_date=date(2026, 4, 1),
            customer=self.customer,
            status='DRAFT'
        )

        # Update with performance dates
        response = self.client.post(
            f'/auftragsverwaltung/documents/{self.doc_type.key}/{doc.pk}/update/',
            {
                'subject': 'Test Update',
                'issue_date': '2026-04-01',
                'performance_date_from': '2026-03-01',
                'performance_date_to': '2026-03-31',
                'customer_id': self.customer.pk,
                'status': 'DRAFT',
            }
        )

        self.assertEqual(response.status_code, 302)

        doc.refresh_from_db()
        self.assertEqual(doc.performance_date_from, date(2026, 3, 1))
        self.assertEqual(doc.performance_date_to, date(2026, 3, 31))

    def test_document_update_clear_performance_dates(self):
        """Test updating a document to clear performance dates"""
        # Create document with performance dates
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            number='INV-002',
            subject='Test Clear',
            issue_date=date(2026, 4, 1),
            customer=self.customer,
            performance_date_from=date(2026, 3, 1),
            performance_date_to=date(2026, 3, 31),
            status='DRAFT'
        )

        # Update without performance dates (should clear them)
        response = self.client.post(
            f'/auftragsverwaltung/documents/{self.doc_type.key}/{doc.pk}/update/',
            {
                'subject': 'Test Clear',
                'issue_date': '2026-04-01',
                'customer_id': self.customer.pk,
                'status': 'DRAFT',
            }
        )

        self.assertEqual(response.status_code, 302)

        doc.refresh_from_db()
        self.assertIsNone(doc.performance_date_from)
        self.assertIsNone(doc.performance_date_to)
