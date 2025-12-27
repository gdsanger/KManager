"""
Tests for default email sender in MailTemplateForm
"""
from django.test import TestCase
from core.forms import MailTemplateForm
from core.models import MailTemplate


class MailTemplateFormDefaultsTestCase(TestCase):
    """Test default values in MailTemplateForm"""
    
    def test_new_template_has_default_sender(self):
        """Test that new templates get default sender values"""
        # Create form for new template (no instance)
        form = MailTemplateForm()
        
        # Check that default values are set
        self.assertEqual(
            form.fields['from_address'].initial,
            'noreply@ebner-vermietung.de'
        )
        self.assertEqual(
            form.fields['from_name'].initial,
            'Domus Notification Manager'
        )
    
    def test_existing_template_keeps_values(self):
        """Test that existing templates don't get default values overridden"""
        # Create an existing template
        existing_template = MailTemplate.objects.create(
            key='existing_template',
            subject='Test Subject',
            message_html='<p>Test</p>',
            from_address='custom@example.com',
            from_name='Custom Sender'
        )
        
        # Create form for existing template
        form = MailTemplateForm(instance=existing_template)
        
        # Defaults should NOT be applied (initial should be None for existing)
        self.assertIsNone(form.fields['from_address'].initial)
        self.assertIsNone(form.fields['from_name'].initial)
        
        # But the instance values should be preserved
        self.assertEqual(form.instance.from_address, 'custom@example.com')
        self.assertEqual(form.instance.from_name, 'Custom Sender')
    
    def test_form_validation_with_defaults(self):
        """Test that form can be saved with default values"""
        form_data = {
            'key': 'test_template',
            'subject': 'Test Subject',
            'message_html': '<p>Test message</p>',
            'from_address': 'noreply@ebner-vermietung.de',
            'from_name': 'Domus Notification Manager',
            'cc_copy_to': ''
        }
        
        form = MailTemplateForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Save the form
        template = form.save()
        
        # Verify the template was saved with correct values
        self.assertEqual(template.from_address, 'noreply@ebner-vermietung.de')
        self.assertEqual(template.from_name, 'Domus Notification Manager')
    
    def test_defaults_can_be_overridden(self):
        """Test that users can override default values"""
        form_data = {
            'key': 'custom_template',
            'subject': 'Custom Subject',
            'message_html': '<p>Custom message</p>',
            'from_address': 'different@example.com',
            'from_name': 'Different Sender',
            'cc_copy_to': ''
        }
        
        form = MailTemplateForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Save the form
        template = form.save()
        
        # Verify custom values were used
        self.assertEqual(template.from_address, 'different@example.com')
        self.assertEqual(template.from_name, 'Different Sender')
