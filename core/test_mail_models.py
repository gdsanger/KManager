"""
Tests for core mailing models
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import SmtpSettings, MailTemplate


class SmtpSettingsTestCase(TestCase):
    """Test SmtpSettings model"""
    
    def test_singleton_constraint(self):
        """Test that only one SmtpSettings instance can exist"""
        # Create first instance
        settings1 = SmtpSettings.objects.create(
            host='smtp.example.com',
            port=587,
            use_tls=True,
            username='user@example.com',
            password='password'
        )
        self.assertIsNotNone(settings1.pk)
        
        # Try to create second instance - should raise ValidationError
        with self.assertRaises(ValidationError):
            settings2 = SmtpSettings(
                host='smtp2.example.com',
                port=25,
                use_tls=False
            )
            settings2.save()
    
    def test_get_settings_creates_default(self):
        """Test that get_settings creates default instance if none exists"""
        self.assertEqual(SmtpSettings.objects.count(), 0)
        
        settings = SmtpSettings.get_settings()
        
        self.assertIsNotNone(settings)
        self.assertEqual(settings.host, 'localhost')
        self.assertEqual(settings.port, 587)
        self.assertFalse(settings.use_tls)
        self.assertEqual(SmtpSettings.objects.count(), 1)
    
    def test_get_settings_returns_existing(self):
        """Test that get_settings returns existing instance"""
        existing = SmtpSettings.objects.create(
            host='smtp.example.com',
            port=465,
            use_tls=True
        )
        
        settings = SmtpSettings.get_settings()
        
        self.assertEqual(settings.pk, existing.pk)
        self.assertEqual(settings.host, 'smtp.example.com')
        self.assertEqual(SmtpSettings.objects.count(), 1)


class MailTemplateTestCase(TestCase):
    """Test MailTemplate model"""
    
    def test_create_template(self):
        """Test creating a mail template"""
        template = MailTemplate.objects.create(
            key='test_template',
            subject='Test Subject',
            message='<p>Test Message</p>',
            from_address='sender@example.com',
            from_name='Test Sender',
            cc_address='cc@example.com'
        )
        
        self.assertEqual(template.key, 'test_template')
        self.assertEqual(template.subject, 'Test Subject')
        self.assertTrue(template.is_active)  # Should be active by default
        self.assertEqual(str(template), 'test_template: Test Subject')
    
    def test_unique_key_constraint(self):
        """Test that template keys must be unique"""
        MailTemplate.objects.create(
            key='duplicate_key',
            subject='First',
            message='<p>First</p>',
            from_address='sender@example.com',
            from_name='Sender'
        )
        
        # Try to create template with same key
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            MailTemplate.objects.create(
                key='duplicate_key',
                subject='Second',
                message='<p>Second</p>',
                from_address='sender2@example.com',
                from_name='Sender 2'
            )
    
    def test_cc_optional(self):
        """Test that cc_address is optional"""
        template = MailTemplate.objects.create(
            key='no_cc',
            subject='No CC',
            message='<p>Test</p>',
            from_address='sender@example.com',
            from_name='Sender'
        )
        
        self.assertEqual(template.cc_address, '')
    
    def test_is_active_default(self):
        """Test that is_active defaults to True"""
        template = MailTemplate.objects.create(
            key='active_test',
            subject='Test',
            message='<p>Test</p>',
            from_address='sender@example.com',
            from_name='Sender'
        )
        
        self.assertTrue(template.is_active)
    
    def test_timestamps(self):
        """Test that created_at and updated_at are set"""
        template = MailTemplate.objects.create(
            key='timestamp_test',
            subject='Test',
            message='<p>Test</p>',
            from_address='sender@example.com',
            from_name='Sender'
        )
        
        self.assertIsNotNone(template.created_at)
        self.assertIsNotNone(template.updated_at)
        
    def test_optional_sender_fields(self):
        """Test that from_name and from_address are optional"""
        template = MailTemplate.objects.create(
            key='minimal_template',
            subject='Test',
            message='<p>Test</p>'
        )
        
        self.assertEqual(template.from_name, '')
        self.assertEqual(template.from_address, '')
