"""
Tests for SalesDocument create view to ensure NoReverseMatch error is fixed.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from auftragsverwaltung.models import DocumentType, TaxRate
from core.models import Mandant


class SalesDocumentCreateTestCase(TestCase):
    """Test case for SalesDocument create view"""
    
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
        
        # Create tax rate (required for document creation)
        self.tax_rate = TaxRate.objects.create(
            code='19%',
            rate=19.0,
            is_active=True
        )
        
        # Create client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_document_create_view_renders_without_error(self):
        """
        Test that the document create view renders successfully without NoReverseMatch error.
        This was the main bug: template tried to use document.pk before document was saved.
        """
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)
        
        # Should render successfully (status 200, not 500 error)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auftragsverwaltung/documents/detail.html')
    
    def test_document_create_context_has_document_none(self):
        """Test that context includes document=None for create view"""
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)
        
        # Context should have document set to None
        self.assertIn('document', response.context)
        self.assertIsNone(response.context['document'])
    
    def test_document_create_context_has_empty_lines(self):
        """Test that context includes empty lines list for create view"""
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)
        
        # Context should have empty lines list
        self.assertIn('lines', response.context)
        self.assertEqual(response.context['lines'], [])
    
    def test_document_create_context_has_is_create_flag(self):
        """Test that context includes is_create=True flag"""
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)
        
        # Context should have is_create flag set to True
        self.assertIn('is_create', response.context)
        self.assertTrue(response.context['is_create'])
    
    def test_document_create_for_different_types(self):
        """Test that create view works for different document types"""
        doc_types = ['quote', 'invoice', 'delivery', 'order']
        
        for doc_key in doc_types:
            with self.subTest(doc_key=doc_key):
                url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': doc_key})
                response = self.client.get(url)
                
                # Should render successfully for all document types
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'auftragsverwaltung/documents/detail.html')
    
    def test_add_position_button_disabled_in_create_mode(self):
        """Test that 'Position hinzufügen' button is disabled in create mode"""
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)
        
        # Button should be disabled with class btn-secondary
        self.assertContains(response, 'btn-secondary')
        self.assertContains(response, 'disabled')
        self.assertContains(response, 'Bitte speichern Sie das Dokument zuerst')
    
    def test_create_view_requires_login(self):
        """Test that login is required to access create view"""
        self.client.logout()
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'quote'})
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_create_view_with_invalid_doc_type(self):
        """Test that invalid document type returns 404"""
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'invalid_type'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
