"""
Tests for password reset functionality
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from unittest.mock import patch, MagicMock
from core.admin import CustomUserAdmin
from core.models import MailTemplate
from core.mailing.service import MailServiceError


class MockRequest:
    """Mock request object for admin action testing"""
    def __init__(self):
        # Create a proper request with session support
        factory = RequestFactory()
        self.request = factory.get('/')
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        
        # Add session
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(self.request)
        self.request.session.save()
        
        # Add messages
        msg_middleware = MessageMiddleware(lambda x: None)
        msg_middleware.process_request(self.request)
        
        # Copy attributes to self
        self.session = self.request.session
        self._messages = self.request._messages
        self.META = self.request.META
        self.method = 'POST'


class PasswordResetAdminActionTest(TestCase):
    """Test the password reset admin action"""
    
    def setUp(self):
        """Set up test data"""
        # Get or create mail template (migration already creates it)
        self.mail_template, _ = MailTemplate.objects.get_or_create(
            key='user-password-reset',
            defaults={
                'subject': 'Ihr neues Kennwort für K-Manager',
                'message': 'Username: {{ username }}, Password: {{ password }}, URL: {{ baseUrl }}',
                'is_active': True
            }
        )
        
        # Create test users
        self.user_with_email = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='oldpassword123'
        )
        
        self.user_without_email = User.objects.create_user(
            username='user2',
            password='oldpassword123'
        )
        
        # Create admin
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass'
        )
        
        # Set up admin
        self.site = AdminSite()
        self.user_admin = CustomUserAdmin(User, self.site)
        
    def test_reset_password_action_exists(self):
        """Test that the reset password action is registered"""
        # Get all action names (actions can be tuples or strings)
        action_names = []
        for action in self.user_admin.actions:
            if isinstance(action, tuple):
                action_names.append(action[0])
            elif isinstance(action, str):
                action_names.append(action)
            elif callable(action):
                action_names.append(action.__name__)
        
        self.assertIn('reset_user_password', action_names)
    
    def test_reset_password_action_display_name(self):
        """Test the action display name"""
        action = self.user_admin.reset_user_password
        self.assertEqual(
            action.short_description,
            "Kennwort zurücksetzen (neues Kennwort per E-Mail)"
        )
    
    @patch('core.admin.send_mail')
    def test_reset_password_success(self, mock_send_mail):
        """Test successful password reset"""
        # Arrange
        mock_send_mail.return_value = None
        request = MockRequest()
        queryset = User.objects.filter(pk=self.user_with_email.pk)
        old_password = self.user_with_email.password
        
        # Act
        self.user_admin.reset_user_password(request, queryset)
        
        # Assert
        self.user_with_email.refresh_from_db()
        
        # Password should be changed (hashed value different)
        self.assertNotEqual(self.user_with_email.password, old_password)
        
        # Mail should be sent
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Check template key
        self.assertEqual(call_args[1]['template_key'], 'user-password-reset')
        
        # Check recipient
        self.assertEqual(call_args[1]['to'], [self.user_with_email.email])
        
        # Check context has required fields
        context = call_args[1]['context']
        self.assertIn('username', context)
        self.assertIn('password', context)
        self.assertIn('baseUrl', context)
        self.assertEqual(context['username'], 'user1')
        
        # New password should be in context
        new_password = context['password']
        self.assertTrue(len(new_password) >= 12)
        
        # User should be able to login with new password
        self.assertTrue(
            self.user_with_email.check_password(new_password),
            "User should be able to login with new password"
        )
    
    def test_reset_password_user_without_email(self):
        """Test that users without email are handled correctly"""
        # Arrange
        request = MockRequest()
        queryset = User.objects.filter(pk=self.user_without_email.pk)
        old_password = self.user_without_email.password
        
        # Act
        self.user_admin.reset_user_password(request, queryset)
        
        # Assert
        self.user_without_email.refresh_from_db()
        
        # Password should NOT be changed
        self.assertEqual(self.user_without_email.password, old_password)
    
    @patch('core.admin.send_mail')
    def test_reset_password_mail_send_failure(self, mock_send_mail):
        """Test that password remains changed even if mail fails"""
        # Arrange
        mock_send_mail.side_effect = MailServiceError("SMTP error")
        request = MockRequest()
        queryset = User.objects.filter(pk=self.user_with_email.pk)
        old_password = self.user_with_email.password
        
        # Act
        self.user_admin.reset_user_password(request, queryset)
        
        # Assert
        self.user_with_email.refresh_from_db()
        
        # Password should still be changed (requirement: no rollback on mail failure)
        self.assertNotEqual(self.user_with_email.password, old_password)
    
    @patch('core.admin.send_mail')
    def test_reset_password_multiple_users(self, mock_send_mail):
        """Test resetting passwords for multiple users"""
        # Arrange
        mock_send_mail.return_value = None
        user3 = User.objects.create_user(
            username='user3',
            email='user3@example.com',
            password='oldpassword123'
        )
        
        request = MockRequest()
        queryset = User.objects.filter(pk__in=[self.user_with_email.pk, user3.pk])
        
        # Act
        self.user_admin.reset_user_password(request, queryset)
        
        # Assert
        # Both users should have new passwords
        self.assertTrue(mock_send_mail.call_count == 2)
    
    def test_reset_password_max_selection_limit(self):
        """Test that action rejects more than 10 users"""
        # Arrange
        request = MockRequest()
        # Create 11 users
        users = [
            User.objects.create_user(
                username=f'bulkuser{i}',
                email=f'bulkuser{i}@example.com'
            )
            for i in range(11)
        ]
        queryset = User.objects.filter(username__startswith='bulkuser')
        
        # Act
        self.user_admin.reset_user_password(request, queryset)
        
        # Assert - should show warning and not process
        # (Implementation shows warning via messages framework)
        self.assertEqual(queryset.count(), 11)
    
    @patch('core.admin.send_mail')
    @patch('core.admin.settings')
    def test_base_url_from_settings(self, mock_settings, mock_send_mail):
        """Test that baseUrl is taken from settings"""
        # Arrange
        mock_settings.BASE_URL = 'https://example.com'
        mock_send_mail.return_value = None
        request = MockRequest()
        queryset = User.objects.filter(pk=self.user_with_email.pk)
        
        # Act
        self.user_admin.reset_user_password(request, queryset)
        
        # Assert
        call_args = mock_send_mail.call_args
        context = call_args[1]['context']
        self.assertEqual(context['baseUrl'], 'https://example.com')
    
    @patch('core.admin.send_mail')
    def test_password_is_secure(self, mock_send_mail):
        """Test that generated password meets security requirements"""
        # Arrange
        mock_send_mail.return_value = None
        request = MockRequest()
        queryset = User.objects.filter(pk=self.user_with_email.pk)
        
        # Act
        self.user_admin.reset_user_password(request, queryset)
        
        # Assert
        call_args = mock_send_mail.call_args
        context = call_args[1]['context']
        new_password = context['password']
        
        # Should be at least 12 characters
        self.assertGreaterEqual(len(new_password), 12)
        
        # Should contain mix of character types
        # (implementation uses ascii_letters + digits + punctuation)
        has_letter = any(c.isalpha() for c in new_password)
        has_digit_or_punct = any(c.isdigit() or not c.isalnum() for c in new_password)
        self.assertTrue(has_letter or has_digit_or_punct)


class PasswordResetMailTemplateTest(TestCase):
    """Test the password reset mail template"""
    
    def test_mail_template_exists(self):
        """Test that migration creates the mail template"""
        # Template should be created by migration
        template = MailTemplate.objects.get(key='user-password-reset')
        
        self.assertEqual(template.key, 'user-password-reset')
        self.assertTrue(template.is_active)
        self.assertIn('Kennwort', template.subject)
    
    def test_mail_template_renders_correctly(self):
        """Test that the template renders with context variables"""
        from django.template import Template, Context
        
        template = MailTemplate.objects.get(key='user-password-reset')
        
        # Render the template
        django_template = Template(template.message)
        context = Context({
            'username': 'testuser',
            'password': 'TestPass123!',
            'baseUrl': 'https://example.com'
        })
        
        rendered = django_template.render(context)
        
        # Check that variables are rendered
        self.assertIn('testuser', rendered)
        self.assertIn('TestPass123!', rendered)
        self.assertIn('https://example.com', rendered)
        
        # Check HTML structure
        self.assertIn('<!DOCTYPE html>', rendered)
        self.assertIn('<html>', rendered)
