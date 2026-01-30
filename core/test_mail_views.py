"""
Tests for core mailing views
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import SmtpSettings, MailTemplate


class SmtpSettingsViewTestCase(TestCase):
    """Test SMTP settings view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=False
        )
    
    def test_requires_login(self):
        """Test that SMTP settings requires authenticated user"""
        # Not logged in
        response = self.client.get(reverse('smtp_settings'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Regular user - should now have access
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(reverse('smtp_settings'))
        self.assertEqual(response.status_code, 200)  # Regular users can access
        
        # Staff user
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('smtp_settings'))
        self.assertEqual(response.status_code, 200)
    
    def test_get_smtp_settings(self):
        """Test GET request to SMTP settings"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('smtp_settings'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SMTP Einstellungen')
    
    def test_update_smtp_settings(self):
        """Test POST request to update SMTP settings"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'host': 'smtp.example.com',
            'port': 587,
            'use_tls': True,
            'username': 'user@example.com',
            'password': 'password123'
        }
        
        response = self.client.post(reverse('smtp_settings'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that settings were saved
        settings = SmtpSettings.get_settings()
        self.assertEqual(settings.host, 'smtp.example.com')
        self.assertEqual(settings.port, 587)
        self.assertTrue(settings.use_tls)
        self.assertEqual(settings.username, 'user@example.com')


class MailTemplateListViewTestCase(TestCase):
    """Test mail template list view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
        
        # Create test templates
        MailTemplate.objects.create(
            key='template1',
            subject='Test Subject 1',
            message='<p>Test</p>',
            from_address='sender@example.com',
            from_name='Sender'
        )
        MailTemplate.objects.create(
            key='template2',
            subject='Test Subject 2',
            message='<p>Test 2</p>',
            from_address='sender2@example.com',
            from_name='Sender 2'
        )
    
    def test_requires_login(self):
        """Test that list view requires authenticated user"""
        response = self.client.get(reverse('mailtemplate_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Regular user should have access now
        regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=False
        )
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(reverse('mailtemplate_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_list_templates(self):
        """Test listing mail templates"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'template1')
        self.assertContains(response, 'template2')
    
    def test_search_by_key(self):
        """Test searching templates by key"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_list'), {'search_key': 'template1'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'template1')
        self.assertNotContains(response, 'template2')
    
    def test_search_by_subject(self):
        """Test searching templates by subject"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_list'), {'search_subject': 'Subject 2'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'template2')
        self.assertNotContains(response, 'template1')
    
    def test_filter_by_active(self):
        """Test filtering templates by is_active status"""
        # Create an inactive template
        MailTemplate.objects.create(
            key='inactive_template',
            subject='Inactive Template',
            message='<p>Inactive</p>',
            from_address='inactive@example.com',
            from_name='Inactive',
            is_active=False
        )
        
        self.client.login(username='staff', password='testpass123')
        
        # Test filtering for active only
        response = self.client.get(reverse('mailtemplate_list'), {'filter_active': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'template1')
        self.assertNotContains(response, 'inactive_template')
        
        # Test filtering for inactive only
        response = self.client.get(reverse('mailtemplate_list'), {'filter_active': '0'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'inactive_template')
        self.assertNotContains(response, 'template1')


class MailTemplateCreateViewTestCase(TestCase):
    """Test mail template create view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
    
    def test_create_template_get(self):
        """Test GET request to create template"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neues E-Mail Template')
    
    def test_create_template_post(self):
        """Test POST request to create template"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'key': 'new_template',
            'subject': 'New Subject',
            'message': '<p>New message</p>',
            'from_address': 'new@example.com',
            'from_name': 'New Sender',
            'cc_address': 'cc@example.com',
            'is_active': True
        }
        
        response = self.client.post(reverse('mailtemplate_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that template was created
        template = MailTemplate.objects.get(key='new_template')
        self.assertEqual(template.subject, 'New Subject')
        self.assertEqual(template.from_address, 'new@example.com')
        self.assertEqual(template.cc_address, 'cc@example.com')
    
    def test_create_template_invalid_email(self):
        """Test creating template with invalid email"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'key': 'invalid_template',
            'subject': 'Subject',
            'message': '<p>Message</p>',
            'from_address': 'invalid-email',  # Invalid email
            'from_name': 'Sender'
        }
        
        response = self.client.post(reverse('mailtemplate_create'), data)
        self.assertEqual(response.status_code, 200)  # Form error, stay on page
        self.assertContains(response, 'E-Mail')
    
    def test_create_template_save_and_close(self):
        """Test creating template with 'Save & Close' button"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'key': 'new_template_close',
            'subject': 'New Subject',
            'message': '<p>New message</p>',
            'from_address': 'new@example.com',
            'from_name': 'New Sender',
            'is_active': True,
            'action': 'save_and_close'
        }
        
        response = self.client.post(reverse('mailtemplate_create'), data)
        # Should redirect to list
        self.assertRedirects(response, reverse('mailtemplate_list'))
        
        # Check that template was created
        template = MailTemplate.objects.get(key='new_template_close')
        self.assertEqual(template.subject, 'New Subject')
    
    def test_create_template_save_only(self):
        """Test creating template with 'Save' button"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'key': 'new_template_save',
            'subject': 'New Subject',
            'message': '<p>New message</p>',
            'from_address': 'new@example.com',
            'from_name': 'New Sender',
            'is_active': True,
            'action': 'save'
        }
        
        response = self.client.post(reverse('mailtemplate_create'), data)
        # Should redirect to edit page of the newly created template
        template = MailTemplate.objects.get(key='new_template_save')
        self.assertRedirects(response, reverse('mailtemplate_edit', args=[template.pk]))


class MailTemplateEditViewTestCase(TestCase):
    """Test mail template edit view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
        
        self.template = MailTemplate.objects.create(
            key='edit_template',
            subject='Original Subject',
            message='<p>Original</p>',
            from_address='original@example.com',
            from_name='Original Sender'
        )
    
    def test_edit_template_get(self):
        """Test GET request to edit template"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_edit', args=[self.template.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'edit_template')
    
    def test_edit_template_post(self):
        """Test POST request to edit template"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'key': 'edit_template',  # Key cannot be changed to maintain uniqueness
            'subject': 'Updated Subject',
            'message': '<p>Updated</p>',
            'from_address': 'updated@example.com',
            'from_name': 'Updated Sender',
            'cc_address': '',
            'is_active': True
        }
        
        response = self.client.post(reverse('mailtemplate_edit', args=[self.template.pk]), data)
        self.assertEqual(response.status_code, 302)
        
        # Reload template and check updates
        self.template.refresh_from_db()
        self.assertEqual(self.template.subject, 'Updated Subject')
        self.assertEqual(self.template.from_address, 'updated@example.com')
    
    def test_edit_template_save_and_close(self):
        """Test editing template with 'Save & Close' button"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'key': 'edit_template',
            'subject': 'Updated Subject',
            'message': '<p>Updated</p>',
            'from_address': 'updated@example.com',
            'from_name': 'Updated Sender',
            'is_active': True,
            'action': 'save_and_close'
        }
        
        response = self.client.post(reverse('mailtemplate_edit', args=[self.template.pk]), data)
        # Should redirect to list
        self.assertRedirects(response, reverse('mailtemplate_list'))
        
        # Verify template was updated
        self.template.refresh_from_db()
        self.assertEqual(self.template.subject, 'Updated Subject')
    
    def test_edit_template_save_only(self):
        """Test editing template with 'Save' button"""
        self.client.login(username='staff', password='testpass123')
        
        data = {
            'key': 'edit_template',
            'subject': 'Updated Subject',
            'message': '<p>Updated</p>',
            'from_address': 'updated@example.com',
            'from_name': 'Updated Sender',
            'is_active': True,
            'action': 'save'
        }
        
        response = self.client.post(reverse('mailtemplate_edit', args=[self.template.pk]), data)
        # Should redirect back to edit page
        self.assertRedirects(response, reverse('mailtemplate_edit', args=[self.template.pk]))
        
        # Verify template was updated
        self.template.refresh_from_db()
        self.assertEqual(self.template.subject, 'Updated Subject')


class MailTemplateDeleteViewTestCase(TestCase):
    """Test mail template delete view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
        
        self.template = MailTemplate.objects.create(
            key='delete_template',
            subject='Delete Me',
            message='<p>Delete</p>',
            from_address='delete@example.com',
            from_name='Delete Sender'
        )
    
    def test_delete_template_get(self):
        """Test GET request to delete template"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_delete', args=[self.template.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'delete_template')
    
    def test_delete_template_post(self):
        """Test POST request to delete template"""
        self.client.login(username='staff', password='testpass123')
        
        response = self.client.post(reverse('mailtemplate_delete', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)
        
        # Check that template was deleted
        self.assertFalse(MailTemplate.objects.filter(pk=self.template.pk).exists())


class MailTemplateDetailViewTestCase(TestCase):
    """Test mail template detail view"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=False
        )
        
        self.template = MailTemplate.objects.create(
            key='detail_template',
            subject='Detail Subject',
            message='<p>Detail message</p>',
            from_address='detail@example.com',
            from_name='Detail Sender'
        )
    
    def test_requires_login(self):
        """Test that detail view requires authenticated user"""
        response = self.client.get(reverse('mailtemplate_detail', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_detail_template_regular_user(self):
        """Test GET request to detail template as regular user"""
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(reverse('mailtemplate_detail', args=[self.template.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'detail_template')
        self.assertContains(response, 'Detail Subject')
        self.assertContains(response, 'Detail message')
    
    def test_detail_template_staff_user(self):
        """Test GET request to detail template as staff user"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_detail', args=[self.template.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'detail_template')
        self.assertContains(response, 'Detail Subject')
    
    def test_detail_template_not_found(self):
        """Test detail view with non-existent template"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('mailtemplate_detail', args=[99999]))
        
        self.assertEqual(response.status_code, 404)
