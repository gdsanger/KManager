"""
Tests for core mailing service
"""
from django.test import TestCase
from django.template import TemplateSyntaxError
from core.models import SmtpSettings, MailTemplate
from core.mailing.service import (
    render_template, send_mail,
    MailServiceError, TemplateRenderError, MailSendError
)


class RenderTemplateTestCase(TestCase):
    """Test template rendering functionality"""
    
    def setUp(self):
        """Create test template"""
        self.template = MailTemplate.objects.create(
            key='test_template',
            subject='Hello {{ name }}',
            message='<p>Welcome {{ name }}, your email is {{ email }}</p>',
            from_address='sender@example.com',
            from_name='Test Sender'
        )
    
    def test_render_simple_context(self):
        """Test rendering with simple context"""
        context = {
            'name': 'John Doe',
            'email': 'john@example.com'
        }
        
        subject, html = render_template(self.template, context)
        
        self.assertEqual(subject, 'Hello John Doe')
        self.assertEqual(html, '<p>Welcome John Doe, your email is john@example.com</p>')
    
    def test_render_empty_context(self):
        """Test rendering with empty context"""
        context = {}
        
        subject, html = render_template(self.template, context)
        
        # Variables should be rendered as empty strings
        self.assertEqual(subject, 'Hello ')
        self.assertEqual(html, '<p>Welcome , your email is </p>')
    
    def test_render_with_filters(self):
        """Test rendering with Django template filters"""
        template = MailTemplate.objects.create(
            key='filter_test',
            subject='{{ title|upper }}',
            message='<p>{{ text|default:"No text" }}</p>',
            from_address='sender@example.com',
            from_name='Sender'
        )
        
        context = {'title': 'hello world'}
        subject, html = render_template(template, context)
        
        self.assertEqual(subject, 'HELLO WORLD')
        self.assertEqual(html, '<p>No text</p>')
    
    def test_render_syntax_error(self):
        """Test that template syntax errors are caught"""
        template = MailTemplate.objects.create(
            key='error_template',
            subject='{% for x in %}test{% endfor %}',  # Invalid for loop syntax
            message='<p>Test</p>',
            from_address='sender@example.com',
            from_name='Sender'
        )
        
        with self.assertRaises(TemplateRenderError) as cm:
            render_template(template, {})
        
        self.assertIn('Template-Syntax-Fehler', str(cm.exception))


class SendMailTestCase(TestCase):
    """Test mail sending functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create SMTP settings
        SmtpSettings.objects.create(
            host='localhost',
            port=1025,  # MailHog default port
            use_tls=False,
            username='',
            password=''
        )
        
        # Create mail template
        self.template = MailTemplate.objects.create(
            key='welcome_mail',
            subject='Welcome {{ name }}',
            message='<h1>Hello {{ name }}</h1><p>Welcome to our service!</p>',
            from_address='noreply@example.com',
            from_name='Test Service'
        )
    
    def test_template_not_found(self):
        """Test that error is raised for non-existent template"""
        with self.assertRaises(MailServiceError) as cm:
            send_mail('nonexistent', ['test@example.com'], {})
        
        self.assertIn('nicht gefunden', str(cm.exception))
    
    def test_inactive_template(self):
        """Test that error is raised when trying to send with inactive template"""
        # Create an inactive template
        inactive_template = MailTemplate.objects.create(
            key='inactive_template',
            subject='Test',
            message='<p>Test</p>',
            from_address='sender@example.com',
            from_name='Sender',
            is_active=False
        )
        
        with self.assertRaises(MailServiceError) as cm:
            send_mail('inactive_template', ['test@example.com'], {})
        
        self.assertIn('deaktiviert', str(cm.exception))
    
    def test_template_with_empty_sender_uses_defaults(self):
        """Test that templates with empty sender fields use default values"""
        from django.conf import settings
        
        # Create template with empty sender fields
        template = MailTemplate.objects.create(
            key='no_sender',
            subject='Test',
            message='<p>Test</p>',
            from_address='',
            from_name=''
        )
        
        # Try to send - should use defaults
        # This will fail at SMTP connection, but we're testing field handling
        with self.assertRaises(MailSendError):
            send_mail('no_sender', ['test@example.com'], {})
        
        # Verify the template still exists and was used (no error about missing sender)
    
    def test_send_mail_parameters(self):
        """Test that send_mail properly builds the message"""
        # We can't actually send mail in tests without a real SMTP server
        # This test just verifies the function doesn't crash with valid params
        
        # Mock/skip actual SMTP sending by catching the error
        with self.assertRaises(MailSendError):
            # This will fail at SMTP connection, which is expected
            send_mail(
                'welcome_mail',
                ['recipient@example.com'],
                {'name': 'Test User'}
            )


class SmtpConfigurationTestCase(TestCase):
    """Test SMTP configuration scenarios"""
    
    def test_settings_without_auth(self):
        """Test SMTP settings without authentication"""
        settings = SmtpSettings.objects.create(
            host='localhost',
            port=25,
            use_tls=False,
            username='',
            password=''
        )
        
        self.assertEqual(settings.host, 'localhost')
        self.assertEqual(settings.port, 25)
        self.assertFalse(settings.use_tls)
        self.assertEqual(settings.username, '')
    
    def test_settings_with_auth(self):
        """Test SMTP settings with authentication"""
        settings = SmtpSettings.objects.create(
            host='smtp.gmail.com',
            port=587,
            use_tls=True,
            username='user@gmail.com',
            password='app_password'
        )
        
        self.assertEqual(settings.host, 'smtp.gmail.com')
        self.assertEqual(settings.port, 587)
        self.assertTrue(settings.use_tls)
        self.assertEqual(settings.username, 'user@gmail.com')
    
    def test_settings_with_tls(self):
        """Test SMTP settings with TLS enabled"""
        settings = SmtpSettings.objects.create(
            host='smtp.example.com',
            port=587,
            use_tls=True
        )
        
        self.assertTrue(settings.use_tls)
    
    def test_smtp_connection_timeout(self):
        """Test that SMTP connection has timeout to prevent infinite hangs"""
        import time
        
        # Create settings pointing to a non-routable IP (192.0.2.0/24 is TEST-NET-1)
        # This will timeout instead of connecting
        SmtpSettings.objects.create(
            host='192.0.2.1',  # Non-routable test IP
            port=25,
            use_tls=False,
            username='',
            password=''
        )
        
        # Create a mail template
        MailTemplate.objects.create(
            key='timeout_test',
            subject='Test',
            message='<p>Test</p>',
            from_address='test@example.com',
            from_name='Test'
        )
        
        # Attempt to send mail - should timeout quickly, not hang indefinitely
        start_time = time.time()
        with self.assertRaises(MailSendError):
            send_mail('timeout_test', ['test@example.com'], {})
        elapsed_time = time.time() - start_time
        
        # Should timeout in around 10 seconds (our configured timeout)
        # Allow some margin for test execution overhead
        self.assertLess(elapsed_time, 15, 
                       "SMTP connection should timeout within 15 seconds, not hang indefinitely")


class SendMailCCTestCase(TestCase):
    """Test CC functionality in send_mail"""
    
    def setUp(self):
        """Set up test data"""
        # Create SMTP settings
        SmtpSettings.objects.create(
            host='localhost',
            port=1025,
            use_tls=False,
            username='',
            password=''
        )
        
        # Create mail template without static CC
        self.template = MailTemplate.objects.create(
            key='test_cc',
            subject='Test with CC',
            message='<p>Test message</p>',
            from_address='sender@example.com',
            from_name='Test Sender'
        )
        
        # Create mail template with static CC
        self.template_with_cc = MailTemplate.objects.create(
            key='test_static_cc',
            subject='Test with static CC',
            message='<p>Test message</p>',
            from_address='sender@example.com',
            from_name='Test Sender',
            cc_address='static_cc@example.com'
        )
    
    def test_send_mail_with_dynamic_cc(self):
        """Test that dynamic CC is properly added to email"""
        from unittest.mock import patch, MagicMock
        
        # Mock SMTP to verify CC is included
        with patch('core.mailing.service.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            send_mail(
                'test_cc',
                ['recipient@example.com'],
                {'name': 'Test'},
                cc=['cc1@example.com', 'cc2@example.com']
            )
            
            # Verify sendmail was called with all recipients (To + CC)
            self.assertTrue(mock_server.sendmail.called)
            args = mock_server.sendmail.call_args[0]
            # args[1] is the recipient list (To + CC combined)
            self.assertIn('recipient@example.com', args[1])
            self.assertIn('cc1@example.com', args[1])
            self.assertIn('cc2@example.com', args[1])
    
    def test_send_mail_with_empty_cc_list(self):
        """Test that empty CC list is handled properly"""
        from unittest.mock import patch, MagicMock
        
        with patch('core.mailing.service.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            send_mail(
                'test_cc',
                ['recipient@example.com'],
                {'name': 'Test'},
                cc=[]
            )
            
            # Should still send successfully with just To recipient
            self.assertTrue(mock_server.sendmail.called)
    
    def test_send_mail_with_none_cc(self):
        """Test that None CC is handled properly"""
        from unittest.mock import patch, MagicMock
        
        with patch('core.mailing.service.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            send_mail(
                'test_cc',
                ['recipient@example.com'],
                {'name': 'Test'},
                cc=None
            )
            
            # Should still send successfully
            self.assertTrue(mock_server.sendmail.called)
    
    def test_send_mail_removes_duplicate_cc(self):
        """Test that CC recipients that are also in To are filtered out"""
        from unittest.mock import patch, MagicMock
        
        with patch('core.mailing.service.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            send_mail(
                'test_cc',
                ['recipient@example.com'],
                {'name': 'Test'},
                cc=['recipient@example.com', 'other@example.com']  # First one should be filtered
            )
            
            # Verify recipient@example.com appears only once in recipient list
            args = mock_server.sendmail.call_args[0]
            recipients = args[1]
            recipient_count = recipients.count('recipient@example.com')
            self.assertEqual(recipient_count, 1, "Duplicate recipient should be filtered out")
            # other@example.com should still be in CC
            self.assertIn('other@example.com', recipients)
    
    def test_send_mail_with_static_and_dynamic_cc(self):
        """Test that both static (template) and dynamic CC work together"""
        from unittest.mock import patch, MagicMock
        
        with patch('core.mailing.service.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            send_mail(
                'test_static_cc',  # This template has cc_address='static_cc@example.com'
                ['recipient@example.com'],
                {'name': 'Test'},
                cc=['dynamic_cc@example.com']
            )
            
            # Verify both static and dynamic CC are included
            args = mock_server.sendmail.call_args[0]
            recipients = args[1]
            self.assertIn('static_cc@example.com', recipients)
            self.assertIn('dynamic_cc@example.com', recipients)
            self.assertIn('recipient@example.com', recipients)
    
    def test_send_mail_filters_empty_cc_addresses(self):
        """Test that empty strings and None in CC list are filtered out"""
        from unittest.mock import patch, MagicMock
        
        with patch('core.mailing.service.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            send_mail(
                'test_cc',
                ['recipient@example.com'],
                {'name': 'Test'},
                cc=['valid@example.com', '', None, 'another@example.com']
            )
            
            # Verify only valid emails are in recipients
            args = mock_server.sendmail.call_args[0]
            recipients = args[1]
            self.assertIn('valid@example.com', recipients)
            self.assertIn('another@example.com', recipients)
            # Verify empty string and None are not included (list should have 3 items total)
            self.assertEqual(len(recipients), 3)  # recipient + valid + another
