"""
Tests for HTML sanitization utility functions.
"""

from django.test import TestCase
from auftragsverwaltung.utils import sanitize_html


class SanitizeHTMLTestCase(TestCase):
    """Test case for HTML sanitization"""
    
    def test_sanitize_allowed_tags(self):
        """Test that allowed tags are preserved"""
        html = '<p>Test paragraph</p><strong>Bold</strong><em>Italic</em>'
        result = sanitize_html(html)
        self.assertEqual(result, '<p>Test paragraph</p><strong>Bold</strong><em>Italic</em>')
    
    def test_sanitize_removes_script_tags(self):
        """Test that script tags are removed"""
        html = '<p>Safe content</p><script>alert("XSS")</script>'
        result = sanitize_html(html)
        self.assertEqual(result, '<p>Safe content</p>alert("XSS")')
    
    def test_sanitize_removes_dangerous_tags(self):
        """Test that dangerous HTML tags are removed"""
        html = '<p>Test</p><iframe src="evil.com"></iframe>'
        result = sanitize_html(html)
        self.assertEqual(result, '<p>Test</p>')
    
    def test_sanitize_preserves_lists(self):
        """Test that ul/ol/li tags are preserved"""
        html = '<ul><li>Item 1</li><li>Item 2</li></ul>'
        result = sanitize_html(html)
        self.assertEqual(result, '<ul><li>Item 1</li><li>Item 2</li></ul>')
    
    def test_sanitize_preserves_links_with_href(self):
        """Test that links with href attribute are preserved"""
        html = '<a href="https://example.com">Link</a>'
        result = sanitize_html(html)
        self.assertEqual(result, '<a href="https://example.com">Link</a>')
    
    def test_sanitize_removes_onclick_from_links(self):
        """Test that onclick and other dangerous attributes are removed"""
        html = '<a href="https://example.com" onclick="alert(1)">Link</a>'
        result = sanitize_html(html)
        self.assertEqual(result, '<a href="https://example.com">Link</a>')
    
    def test_sanitize_preserves_target_and_rel_in_links(self):
        """Test that target and rel attributes in links are preserved"""
        html = '<a href="https://example.com" target="_blank" rel="noopener">Link</a>'
        result = sanitize_html(html)
        # Check that all attributes are present (order may vary)
        self.assertIn('href="https://example.com"', result)
        self.assertIn('target="_blank"', result)
        self.assertIn('rel="noopener"', result)
        self.assertIn('>Link</a>', result)
    
    def test_sanitize_preserves_underline(self):
        """Test that underline tag is preserved"""
        html = '<p>This is <u>underlined</u> text</p>'
        result = sanitize_html(html)
        self.assertEqual(result, '<p>This is <u>underlined</u> text</p>')
    
    def test_sanitize_preserves_line_breaks(self):
        """Test that br tags are preserved"""
        html = 'Line 1<br>Line 2<br>Line 3'
        result = sanitize_html(html)
        self.assertEqual(result, 'Line 1<br>Line 2<br>Line 3')
    
    def test_sanitize_removes_style_tags(self):
        """Test that style tags are removed"""
        html = '<p>Content</p><style>body { color: red; }</style>'
        result = sanitize_html(html)
        self.assertEqual(result, '<p>Content</p>body { color: red; }')
    
    def test_sanitize_removes_style_attributes(self):
        """Test that style attributes are removed"""
        html = '<p style="color: red;">Styled paragraph</p>'
        result = sanitize_html(html)
        self.assertEqual(result, '<p>Styled paragraph</p>')
    
    def test_sanitize_complex_nested_structure(self):
        """Test sanitization of complex nested HTML"""
        html = '''
        <p>Introduction paragraph</p>
        <ul>
            <li>First <strong>bold</strong> item</li>
            <li>Second <em>italic</em> item</li>
            <li>Third item with <a href="https://example.com">link</a></li>
        </ul>
        <p>More content with <u>underline</u> and <br> line break</p>
        '''
        result = sanitize_html(html)
        # Check that all allowed tags are present
        self.assertIn('<p>Introduction paragraph</p>', result)
        self.assertIn('<ul>', result)
        self.assertIn('<li>', result)
        self.assertIn('<strong>bold</strong>', result)
        self.assertIn('<em>italic</em>', result)
        self.assertIn('<a href="https://example.com">link</a>', result)
        self.assertIn('<u>underline</u>', result)
        self.assertIn('<br>', result)
    
    def test_sanitize_empty_string(self):
        """Test that empty string is handled correctly"""
        html = ''
        result = sanitize_html(html)
        self.assertEqual(result, '')
    
    def test_sanitize_plain_text(self):
        """Test that plain text without HTML is preserved"""
        html = 'Just plain text'
        result = sanitize_html(html)
        self.assertEqual(result, 'Just plain text')
    
    def test_sanitize_removes_img_tags(self):
        """Test that img tags are removed (not in allowlist)"""
        html = '<p>Text</p><img src="image.jpg" alt="Image">'
        result = sanitize_html(html)
        self.assertEqual(result, '<p>Text</p>')
    
    def test_sanitize_removes_table_tags(self):
        """Test that table tags are removed (not in allowlist)"""
        html = '<table><tr><td>Cell</td></tr></table>'
        result = sanitize_html(html)
        self.assertEqual(result, 'Cell')
    
    def test_sanitize_ordered_list(self):
        """Test that ordered lists are preserved"""
        html = '<ol><li>First</li><li>Second</li><li>Third</li></ol>'
        result = sanitize_html(html)
        self.assertEqual(result, '<ol><li>First</li><li>Second</li><li>Third</li></ol>')
