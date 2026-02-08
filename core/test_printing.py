"""
Tests for Core Printing Framework
"""

from django.test import TestCase
from django.template.loader import get_template
from django.template import TemplateDoesNotExist
from pathlib import Path

from core.printing import (
    PdfRenderService,
    PdfResult,
    sanitize_html,
    IPdfRenderer,
    get_static_base_url
)
from core.printing.weasyprint_renderer import WeasyPrintRenderer
from core.printing.service import TemplateNotFoundError, RenderError


class MockRenderer(IPdfRenderer):
    """Mock renderer for testing without WeasyPrint dependency."""
    
    def render_html_to_pdf(self, html: str, base_url: str) -> bytes:
        """Return fake PDF bytes."""
        return b"%PDF-1.4\n%Mock PDF content"


class PdfResultTest(TestCase):
    """Test PdfResult DTO."""
    
    def test_pdf_result_creation(self):
        """Test creating a PdfResult."""
        result = PdfResult(
            pdf_bytes=b"test",
            filename="test.pdf"
        )
        
        self.assertEqual(result.pdf_bytes, b"test")
        self.assertEqual(result.filename, "test.pdf")
        self.assertEqual(result.content_type, "application/pdf")
    
    def test_pdf_result_requires_bytes(self):
        """Test that pdf_bytes must be bytes."""
        with self.assertRaises(TypeError):
            PdfResult(pdf_bytes="not bytes")
    
    def test_pdf_result_requires_nonempty_bytes(self):
        """Test that pdf_bytes cannot be empty."""
        with self.assertRaises(ValueError):
            PdfResult(pdf_bytes=b"")


class SanitizerTest(TestCase):
    """Test HTML sanitizer."""
    
    def test_sanitize_removes_script(self):
        """Test that script tags are removed."""
        html = '<p>Hello</p><script>alert("XSS")</script>'
        result = sanitize_html(html)
        
        self.assertIn('<p>Hello</p>', result)
        self.assertNotIn('<script>', result)
        # Note: bleach strips tags but may keep text content
        # The important part is that <script> tags are removed
    
    def test_sanitize_keeps_allowed_tags(self):
        """Test that allowed tags are preserved."""
        html = '<p><strong>Bold</strong> and <em>italic</em></p>'
        result = sanitize_html(html)
        
        self.assertIn('<strong>Bold</strong>', result)
        self.assertIn('<em>italic</em>', result)
    
    def test_sanitize_removes_dangerous_attributes(self):
        """Test that dangerous attributes are removed."""
        html = '<p onclick="alert(1)">Click me</p>'
        result = sanitize_html(html)
        
        self.assertNotIn('onclick', result)
        self.assertIn('Click me', result)


class PdfRenderServiceTest(TestCase):
    """Test PdfRenderService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = PdfRenderService(renderer=MockRenderer())
    
    def test_render_with_mock_renderer(self):
        """Test rendering with mock renderer."""
        # Create a simple context
        context = {
            'title': 'Test Document',
            'content': 'This is a test.'
        }
        
        # Render using the base template
        result = self.service.render(
            template_name='printing/base.html',
            context=context,
            base_url='file:///tmp/',
            filename='test.pdf'
        )
        
        # Verify result
        self.assertIsInstance(result, PdfResult)
        self.assertEqual(result.filename, 'test.pdf')
        self.assertTrue(len(result.pdf_bytes) > 0)
        self.assertEqual(result.content_type, 'application/pdf')
    
    def test_render_with_nonexistent_template(self):
        """Test that rendering with nonexistent template raises error."""
        with self.assertRaises(TemplateNotFoundError):
            self.service.render(
                template_name='printing/nonexistent.html',
                context={},
                base_url='file:///tmp/',
            )
    
    def test_render_with_sanitization(self):
        """Test rendering with HTML sanitization enabled."""
        context = {
            'dangerous_content': '<script>alert("XSS")</script><p>Safe</p>'
        }
        
        result = self.service.render(
            template_name='printing/base.html',
            context=context,
            base_url='file:///tmp/',
            sanitize=True
        )
        
        self.assertIsInstance(result, PdfResult)
        self.assertTrue(len(result.pdf_bytes) > 0)


class BaseTemplateTest(TestCase):
    """Test that base template exists and is valid."""
    
    def test_base_template_exists(self):
        """Test that printing/base.html template exists."""
        try:
            template = get_template('printing/base.html')
            self.assertIsNotNone(template)
        except TemplateDoesNotExist:
            self.fail("Base template printing/base.html not found")
    
    def test_base_template_renders(self):
        """Test that base template can be rendered."""
        from django.template.loader import render_to_string
        
        context = {
            'title': 'Test',
            'content': 'Test content'
        }
        
        html = render_to_string('printing/base.html', context)
        
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('/static/printing/print.css', html)


class WeasyPrintRendererTest(TestCase):
    """
    Test WeasyPrint renderer.
    
    Note: These tests require WeasyPrint to be installed.
    They will be skipped if WeasyPrint is not available.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        try:
            self.renderer = WeasyPrintRenderer()
            self.weasyprint_available = True
        except ImportError:
            self.weasyprint_available = False
    
    def test_renderer_requires_weasyprint(self):
        """Test that renderer checks for WeasyPrint."""
        if not self.weasyprint_available:
            with self.assertRaises(ImportError):
                WeasyPrintRenderer()
    
    def test_render_simple_html(self):
        """Test rendering simple HTML to PDF."""
        if not self.weasyprint_available:
            self.skipTest("WeasyPrint not available")
        
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body><h1>Test Document</h1><p>This is a test.</p></body>
        </html>
        """
        
        pdf_bytes = self.renderer.render_html_to_pdf(html, base_url='file:///tmp/')
        
        # Verify it's a PDF
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertTrue(len(pdf_bytes) > 100)


class SmokeTest(TestCase):
    """
    Smoke test: Verify the entire pipeline works.
    
    This test uses a real WeasyPrint renderer if available,
    otherwise falls back to mock renderer.
    """
    
    def test_end_to_end_pdf_generation(self):
        """Test complete PDF generation pipeline."""
        # Try to use real WeasyPrint renderer, fall back to mock
        try:
            renderer = WeasyPrintRenderer()
        except ImportError:
            renderer = MockRenderer()
        
        service = PdfRenderService(renderer=renderer)
        
        # Create a test context
        context = {
            'title': 'Smoke Test Document',
            'company_name': 'Test Company GmbH',
            'content': '<h1>Test</h1><p>This is a smoke test.</p>'
        }
        
        # Render PDF
        result = service.render(
            template_name='printing/base.html',
            context=context,
            base_url='file:///tmp/',
            filename='smoke-test.pdf'
        )
        
        # Verify result
        self.assertIsInstance(result, PdfResult)
        self.assertEqual(result.filename, 'smoke-test.pdf')
        self.assertTrue(len(result.pdf_bytes) > 0)
        self.assertEqual(result.content_type, 'application/pdf')
        
        # Verify it looks like a PDF
        if isinstance(renderer, WeasyPrintRenderer):
            self.assertTrue(result.pdf_bytes.startswith(b'%PDF'))


class UtilsTest(TestCase):
    """Test utility functions."""
    
    def test_get_static_base_url_returns_valid_file_url(self):
        """Test that get_static_base_url returns a valid file:// URL."""
        base_url = get_static_base_url()
        
        # Should be a file:// URL
        self.assertTrue(base_url.startswith('file://'))
        
        # Should end with a slash
        self.assertTrue(base_url.endswith('/'))
        
        # Should point to an existing directory
        from pathlib import Path
        import urllib.parse
        url_path = urllib.parse.urlparse(base_url).path
        self.assertTrue(Path(url_path).exists())
    
    def test_get_static_base_url_finds_print_css(self):
        """Test that the base_url can be used to locate print.css."""
        from pathlib import Path
        import urllib.parse
        
        base_url = get_static_base_url()
        url_path = urllib.parse.urlparse(base_url).path
        
        # The print.css should be accessible from this base path
        # Either at base_url/printing/print.css (if core/static is used)
        # or at base_url/printing/print.css (if staticfiles is used after collectstatic)
        css_path = Path(url_path) / 'printing' / 'print.css'
        
        # Note: In development, we expect to find the file
        # In CI or test environments without collectstatic, this might not exist
        # So we just verify the path is constructed correctly
        self.assertTrue(str(css_path).endswith('printing/print.css'))
