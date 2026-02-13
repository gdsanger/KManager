"""
Test to verify that the "Anlegen" button appears on the aktivitaet create page.
This test validates the fix for the issue where the save button was missing.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class AktivitaetCreateButtonTest(TestCase):
    """Test that the Anlegen button appears on the create page"""
    
    def setUp(self):
        """Set up test user and client"""
        # Create a Mandant (required for some features)
        from core.models import Mandant
        self.mandant = Mandant.objects.create(
            name='Test Mandant',
            adresse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True  # Grant vermietung access
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_anlegen_button_appears_on_create_page(self):
        """Test that the 'Anlegen' button is visible on the create page"""
        url = reverse('vermietung:aktivitaet_create')
        response = self.client.get(url)
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Check that the template is correct
        self.assertTemplateUsed(response, 'vermietung/aktivitaeten/form.html')
        
        # Check that is_create is True in the context
        self.assertTrue(response.context['is_create'])
        
        # Convert response content to string for checking
        content = response.content.decode('utf-8')
        
        # Check that the "Anlegen" button text appears
        self.assertIn('Anlegen', content, 
                     "'Anlegen' button text should appear on create page")
        
        # Check that there's a submit button
        self.assertIn('type="submit"', content,
                     "Submit button should be present")
        
        # Check that the primary button class is used
        self.assertIn('btn btn-primary', content,
                     "Primary button class should be present")
        
        # Check that the "Abbrechen" button is also present
        self.assertIn('Abbrechen', content,
                     "'Abbrechen' button should be present")
    
    def test_hidden_forms_not_present_in_create_mode(self):
        """Test that edit-only elements are hidden in create mode"""
        url = reverse('vermietung:aktivitaet_create')
        response = self.client.get(url)
        
        content = response.content.decode('utf-8')
        
        # These elements should NOT appear in create mode
        self.assertNotIn('deleteForm', content,
                        "Delete form should be hidden in create mode")
        self.assertNotIn('assignModal', content,
                        "Assignment modal should be hidden in create mode")
        self.assertNotIn('Löschen', content,
                        "Delete button should not appear in create mode")
    
    def test_attachments_info_appears_in_create_mode(self):
        """Test that the attachment info message appears in create mode"""
        url = reverse('vermietung:aktivitaet_create')
        response = self.client.get(url)
        
        content = response.content.decode('utf-8')
        
        # Check that the info about attachments appears
        self.assertIn('Hinweis zu Anhängen', content,
                     "Attachment info should appear in create mode")
    
    def test_delete_button_appears_in_edit_mode(self):
        """Test that the delete button appears in edit mode but not in create mode"""
        # First create an activity
        from vermietung.models import Aktivitaet
        from datetime import date, timedelta
        
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test description',
            status='OFFEN',
            prioritaet='NORMAL',
            faellig_am=date.today() + timedelta(days=7),
            ersteller=self.user
        )
        
        # Test edit page - delete button should appear
        edit_url = reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk])
        edit_response = self.client.get(edit_url)
        edit_content = edit_response.content.decode('utf-8')
        
        self.assertIn('Löschen', edit_content,
                     "Delete button should appear in edit mode")
        self.assertIn('deleteForm', edit_content,
                     "Delete form should be present in edit mode")
        
        # Test create page - delete button should NOT appear (this is the primary test for this)
        create_url = reverse('vermietung:aktivitaet_create')
        create_response = self.client.get(create_url)
        create_content = create_response.content.decode('utf-8')
        
        self.assertNotIn('deleteForm', create_content,
                        "Delete form should not be present in create mode")
