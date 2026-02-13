"""
Tests for Aktivitaet form HTML sanitization.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from vermietung.forms import AktivitaetForm

User = get_user_model()


class AktivitaetFormSanitizationTest(TestCase):
    """Test case for Aktivitaet form HTML sanitization"""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a user for form tests
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_sanitize_allowed_tags(self):
        """Test that allowed tags are preserved in beschreibung"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '<p>Test paragraph</p><strong>Bold</strong><em>Italic</em>',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['beschreibung'],
            '<p>Test paragraph</p><strong>Bold</strong><em>Italic</em>'
        )
    
    def test_sanitize_removes_script_tags(self):
        """Test that script tags are removed from beschreibung"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '<p>Safe content</p><script>alert("XSS")</script>',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        # Script tags should be stripped
        self.assertNotIn('<script>', form.cleaned_data['beschreibung'])
        self.assertIn('<p>Safe content</p>', form.cleaned_data['beschreibung'])
    
    def test_sanitize_removes_onclick_handlers(self):
        """Test that onclick and other dangerous attributes are removed"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '<a href="https://example.com" onclick="alert(1)">Link</a>',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        # onclick should be removed
        self.assertNotIn('onclick', form.cleaned_data['beschreibung'])
        self.assertIn('href="https://example.com"', form.cleaned_data['beschreibung'])
    
    def test_sanitize_preserves_images(self):
        """Test that img tags with src attribute are preserved"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '<p>Image:</p><img src="/media/image.jpg" alt="Test Image">',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        # img tags should be preserved
        self.assertIn('<img', form.cleaned_data['beschreibung'])
        self.assertIn('src="/media/image.jpg"', form.cleaned_data['beschreibung'])
    
    def test_sanitize_removes_img_onerror(self):
        """Test that onerror handlers in img tags are removed"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '<img src="image.jpg" onerror="alert(1)">',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        # onerror should be removed but img should remain
        self.assertIn('<img', form.cleaned_data['beschreibung'])
        self.assertNotIn('onerror', form.cleaned_data['beschreibung'])
    
    def test_sanitize_preserves_lists(self):
        """Test that ul/ol/li tags are preserved"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '<ul><li>Item 1</li><li>Item 2</li></ul>',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['beschreibung'],
            '<ul><li>Item 1</li><li>Item 2</li></ul>'
        )
    
    def test_sanitize_plain_text_preserved(self):
        """Test that plain text without HTML is preserved"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': 'Just plain text description',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['beschreibung'],
            'Just plain text description'
        )
    
    def test_sanitize_empty_beschreibung(self):
        """Test that empty beschreibung is handled correctly"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['beschreibung'], '')
    
    def test_sanitize_complex_html_with_images(self):
        """Test sanitization of complex HTML with images and formatting"""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': '''
            <p>Introduction paragraph</p>
            <ul>
                <li>First <strong>bold</strong> item</li>
                <li>Second <em>italic</em> item</li>
            </ul>
            <img src="/media/screenshot.png" alt="Screenshot">
            <p>More content with <u>underline</u></p>
            ''',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid())
        beschreibung = form.cleaned_data['beschreibung']
        
        # Check that all allowed tags are present
        self.assertIn('<p>Introduction paragraph</p>', beschreibung)
        self.assertIn('<ul>', beschreibung)
        self.assertIn('<li>', beschreibung)
        self.assertIn('<strong>bold</strong>', beschreibung)
        self.assertIn('<em>italic</em>', beschreibung)
        self.assertIn('<img', beschreibung)
        self.assertIn('src="/media/screenshot.png"', beschreibung)
        self.assertIn('<u>underline</u>', beschreibung)
