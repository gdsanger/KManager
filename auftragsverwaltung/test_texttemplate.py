"""
Tests for TextTemplate model and CRUD views.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.db import IntegrityError
from auftragsverwaltung.models import TextTemplate
from core.models import Mandant


class TextTemplateModelTestCase(TestCase):
    """Test case for TextTemplate model"""
    
    def setUp(self):
        """Set up test data"""
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
    
    def test_create_header_template(self):
        """Test creating a header text template"""
        template = TextTemplate.objects.create(
            company=self.company,
            key='standard_header',
            title='Standard Kopftext',
            type='HEADER',
            content='Sehr geehrte Damen und Herren,\n\nvielen Dank für Ihre Anfrage.',
            is_active=True,
            sort_order=0
        )
        
        self.assertEqual(template.company, self.company)
        self.assertEqual(template.key, 'standard_header')
        self.assertEqual(template.title, 'Standard Kopftext')
        self.assertEqual(template.type, 'HEADER')
        self.assertTrue(template.is_active)
        self.assertEqual(template.sort_order, 0)
    
    def test_create_footer_template(self):
        """Test creating a footer text template"""
        template = TextTemplate.objects.create(
            company=self.company,
            key='standard_footer',
            title='Standard Fußtext',
            type='FOOTER',
            content='Mit freundlichen Grüßen\nIhr Team',
            is_active=True
        )
        
        self.assertEqual(template.type, 'FOOTER')
        self.assertEqual(template.get_type_display(), 'Fußtext')
    
    def test_create_both_template(self):
        """Test creating a template for both header and footer"""
        template = TextTemplate.objects.create(
            company=self.company,
            key='universal',
            title='Universal Text',
            type='BOTH',
            content='Universeller Text',
            is_active=True
        )
        
        self.assertEqual(template.type, 'BOTH')
        self.assertEqual(template.get_type_display(), 'Kopf- und Fußtext')
    
    def test_unique_constraint(self):
        """Test that company+key must be unique"""
        # Create first template
        TextTemplate.objects.create(
            company=self.company,
            key='duplicate_key',
            title='First Template',
            type='HEADER',
            content='First content'
        )
        
        # Try to create second template with same company+key
        with self.assertRaises(IntegrityError):
            TextTemplate.objects.create(
                company=self.company,
                key='duplicate_key',
                title='Second Template',
                type='FOOTER',
                content='Second content'
            )
    
    def test_ordering(self):
        """Test that templates are ordered by type, sort_order, title"""
        # Create templates in random order
        t3 = TextTemplate.objects.create(
            company=self.company,
            key='footer_2',
            title='Z Footer',
            type='FOOTER',
            content='Footer 2',
            sort_order=10
        )
        
        t1 = TextTemplate.objects.create(
            company=self.company,
            key='header_1',
            title='A Header',
            type='HEADER',
            content='Header 1',
            sort_order=0
        )
        
        t2 = TextTemplate.objects.create(
            company=self.company,
            key='header_2',
            title='B Header',
            type='HEADER',
            content='Header 2',
            sort_order=5
        )
        
        # Get all templates in default order
        templates = list(TextTemplate.objects.all())
        
        # Should be ordered by type (FOOTER, HEADER), then sort_order, then title
        # FOOTER first, then HEADER
        self.assertEqual(templates[0].id, t3.id)  # FOOTER, sort_order=10
        self.assertEqual(templates[1].id, t1.id)  # HEADER, sort_order=0
        self.assertEqual(templates[2].id, t2.id)  # HEADER, sort_order=5
    
    def test_str_representation(self):
        """Test string representation of template"""
        template = TextTemplate.objects.create(
            company=self.company,
            key='test',
            title='Test Template',
            type='HEADER',
            content='Test content'
        )
        
        self.assertEqual(str(template), 'Test Template (Kopftext)')
    
    def test_inactive_template(self):
        """Test creating an inactive template"""
        template = TextTemplate.objects.create(
            company=self.company,
            key='inactive',
            title='Inactive Template',
            type='HEADER',
            content='Inactive content',
            is_active=False
        )
        
        self.assertFalse(template.is_active)


class TextTemplateViewTestCase(TestCase):
    """Test case for TextTemplate CRUD views"""
    
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
        
        # Create test template
        self.template = TextTemplate.objects.create(
            company=self.company,
            key='test_header',
            title='Test Header',
            type='HEADER',
            content='Test header content',
            is_active=True,
            sort_order=0
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_texttemplate_list_view(self):
        """Test that list view loads successfully"""
        url = reverse('auftragsverwaltung:texttemplate_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Textbausteine')
        self.assertContains(response, 'Test Header')
    
    def test_texttemplate_create_view_get(self):
        """Test that create view loads successfully"""
        url = reverse('auftragsverwaltung:texttemplate_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Textbaustein erstellen')
    
    def test_texttemplate_create_view_post(self):
        """Test creating a template via POST"""
        url = reverse('auftragsverwaltung:texttemplate_create')
        data = {
            'key': 'new_template',
            'title': 'New Template',
            'type': 'FOOTER',
            'content': 'New template content',
            'is_active': 'on',
            'sort_order': '10'
        }
        
        response = self.client.post(url, data)
        
        # Should redirect to list view
        self.assertEqual(response.status_code, 302)
        
        # Check template was created
        template = TextTemplate.objects.get(key='new_template')
        self.assertEqual(template.title, 'New Template')
        self.assertEqual(template.type, 'FOOTER')
        self.assertEqual(template.content, 'New template content')
        self.assertTrue(template.is_active)
        self.assertEqual(template.sort_order, 10)
    
    def test_texttemplate_update_view_get(self):
        """Test that update view loads successfully"""
        url = reverse('auftragsverwaltung:texttemplate_update', kwargs={'pk': self.template.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Textbaustein bearbeiten')
        self.assertContains(response, 'Test Header')
    
    def test_texttemplate_update_view_post(self):
        """Test updating a template via POST"""
        url = reverse('auftragsverwaltung:texttemplate_update', kwargs={'pk': self.template.pk})
        data = {
            'key': 'test_header',
            'title': 'Updated Header',
            'type': 'HEADER',
            'content': 'Updated content',
            'is_active': 'on',
            'sort_order': '5'
        }
        
        response = self.client.post(url, data)
        
        # Should redirect to list view
        self.assertEqual(response.status_code, 302)
        
        # Check template was updated
        self.template.refresh_from_db()
        self.assertEqual(self.template.title, 'Updated Header')
        self.assertEqual(self.template.content, 'Updated content')
        self.assertEqual(self.template.sort_order, 5)
    
    def test_texttemplate_delete_view_get(self):
        """Test that delete confirmation view loads successfully"""
        url = reverse('auftragsverwaltung:texttemplate_delete', kwargs={'pk': self.template.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Textbaustein löschen')
        self.assertContains(response, 'Test Header')
    
    def test_texttemplate_delete_view_post(self):
        """Test deleting a template via POST"""
        url = reverse('auftragsverwaltung:texttemplate_delete', kwargs={'pk': self.template.pk})
        response = self.client.post(url)
        
        # Should redirect to list view
        self.assertEqual(response.status_code, 302)
        
        # Check template was deleted
        self.assertFalse(TextTemplate.objects.filter(pk=self.template.pk).exists())
    
    def test_list_view_requires_login(self):
        """Test that list view requires authentication"""
        self.client.logout()
        url = reverse('auftragsverwaltung:texttemplate_list')
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
