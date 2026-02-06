"""
Tests for SalesDocument list view with django-tables2 and django-filter.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from auftragsverwaltung.models import SalesDocument, DocumentType
from core.models import Mandant


class SalesDocumentListViewTestCase(TestCase):
    """Test case for SalesDocument list view with django-tables2"""
    
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
        
        # Get document types (created by migration)
        self.doc_type_quote = DocumentType.objects.get(key='quote')
        self.doc_type_invoice = DocumentType.objects.get(key='invoice')
        self.doc_type_delivery = DocumentType.objects.get(key='delivery')
        
        # Create test sales documents
        self.doc1 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_quote,
            number='AN-2024-001',
            status='DRAFT',
            issue_date=timezone.now().date(),
            subject='Test Quote 1',
            total_gross=Decimal('1000.00')
        )
        
        self.doc2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_quote,
            number='AN-2024-002',
            status='SENT',
            issue_date=timezone.now().date() - timezone.timedelta(days=1),
            subject='Test Quote 2',
            total_gross=Decimal('2000.00')
        )
        
        self.doc3 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            number='R-2024-001',
            status='OPEN',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=14),
            subject='Test Invoice 1',
            total_gross=Decimal('5000.00')
        )
        
        # Create client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_document_list_view_loads(self):
        """Test that the document list view loads successfully"""
        url = reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auftragsverwaltung/documents/list.html')
        self.assertIn('table', response.context)
        self.assertIn('filter', response.context)
        self.assertIn('document_type', response.context)
    
    def test_convenience_urls(self):
        """Test convenience URLs for different document types"""
        convenience_urls = {
            'auftragsverwaltung:quotes': 'quote',
            'auftragsverwaltung:invoices': 'invoice',
            'auftragsverwaltung:deliveries': 'delivery',
        }
        
        for url_name, doc_key in convenience_urls.items():
            url = reverse(url_name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed to load {url_name}")
            self.assertEqual(response.context['doc_key'], doc_key)
    
    def test_document_list_filters_by_type(self):
        """Test that documents are filtered by document type"""
        # Check quotes (should show 2 quotes)
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)
        table = response.context['table']
        self.assertEqual(len(table.data), 2)
        
        # Check invoices (should show 1 invoice)
        url = reverse('auftragsverwaltung:invoices')
        response = self.client.get(url)
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
    
    def test_search_filter(self):
        """Test the full-text search filter"""
        url = reverse('auftragsverwaltung:quotes')
        
        # Search by number
        response = self.client.get(url, {'q': 'AN-2024-001'})
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
        self.assertEqual(table.data.data[0].number, 'AN-2024-001')
        
        # Search by subject
        response = self.client.get(url, {'q': 'Quote 2'})
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
        self.assertEqual(table.data.data[0].subject, 'Test Quote 2')
    
    def test_status_filter(self):
        """Test the status filter"""
        url = reverse('auftragsverwaltung:quotes')
        
        # Filter by DRAFT status
        response = self.client.get(url, {'status': 'DRAFT'})
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
        self.assertEqual(table.data.data[0].status, 'DRAFT')
        
        # Filter by SENT status
        response = self.client.get(url, {'status': 'SENT'})
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
        self.assertEqual(table.data.data[0].status, 'SENT')
    
    def test_date_range_filter(self):
        """Test date range filtering"""
        url = reverse('auftragsverwaltung:quotes')
        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)
        
        # Filter from today (should get doc1 only)
        response = self.client.get(url, {
            'issue_date_from': today.isoformat()
        })
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
        self.assertEqual(table.data.data[0].number, 'AN-2024-001')
        
        # Filter until yesterday (should get doc2 only)
        response = self.client.get(url, {
            'issue_date_to': yesterday.isoformat()
        })
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
        self.assertEqual(table.data.data[0].number, 'AN-2024-002')
    
    def test_pagination(self):
        """Test that pagination works correctly"""
        # Create more documents to test pagination
        for i in range(30):
            SalesDocument.objects.create(
                company=self.company,
                document_type=self.doc_type_quote,
                number=f'AN-2024-{i+100:03d}',
                status='DRAFT',
                issue_date=timezone.now().date(),
                subject=f'Test Quote {i+100}',
                total_gross=Decimal('100.00')
            )
        
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)
        
        # Should have pagination (25 per page by default)
        table = response.context['table']
        self.assertTrue(table.paginator.num_pages > 1)
        self.assertEqual(len(table.page.object_list), 25)
    
    def test_default_ordering(self):
        """Test that default ordering is by issue_date descending"""
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)
        
        table = response.context['table']
        # doc1 is newer (today), doc2 is older (yesterday)
        # Default ordering should be -issue_date (newest first)
        self.assertEqual(table.data.data[0].number, 'AN-2024-001')
        self.assertEqual(table.data.data[1].number, 'AN-2024-002')
    
    def test_login_required(self):
        """Test that login is required to access the view"""
        self.client.logout()
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_invalid_document_type(self):
        """Test that invalid document type returns 404"""
        url = reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'invalid_type'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_subject_field_in_table(self):
        """Test that subject field is visible in the table"""
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url)
        
        # Check that response contains subject values
        self.assertContains(response, 'Test Quote 1')
        self.assertContains(response, 'Test Quote 2')
    
    def test_subject_field_searchable(self):
        """Test that subject field is searchable via q filter"""
        url = reverse('auftragsverwaltung:quotes')
        response = self.client.get(url, {'subject': 'Quote 1'})
        
        table = response.context['table']
        self.assertEqual(len(table.data), 1)
        self.assertIn('Quote 1', table.data.data[0].subject)
