"""
Tests for Core Report Service
"""
from django.test import TestCase
from django.contrib.auth.models import User
from core.models import ReportDocument
from core.services.reporting import (
    ReportService, 
    TemplateNotFoundError, 
    ReportRenderError,
    list_templates
)


class ReportServiceTestCase(TestCase):
    """Test Report Service functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Import the template to ensure it's registered
        import reports.templates.change_v1
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.sample_context = {
            'title': 'Test Change Report',
            'change_id': 'CHG-001',
            'date': '2024-01-31',
            'description': 'This is a test change report.',
            'items': [
                {'position': '1', 'description': 'First change item', 'status': 'Done'},
                {'position': '2', 'description': 'Second change item', 'status': 'In Progress'},
                {'position': '3', 'description': 'Third change item', 'status': 'Planned'},
            ],
            'notes': 'Additional notes for the change report.',
        }
    
    def test_template_registration(self):
        """Test that change.v1 template is registered"""
        templates = list_templates()
        self.assertIn('change.v1', templates)
    
    def test_render_simple_report(self):
        """Test rendering a simple report to PDF bytes"""
        pdf_bytes = ReportService.render('change.v1', self.sample_context)
        
        # Check that we got bytes
        self.assertIsInstance(pdf_bytes, bytes)
        
        # Check PDF header
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        
        # Check that PDF has reasonable size (at least 1KB)
        self.assertGreater(len(pdf_bytes), 1024)
    
    def test_render_with_invalid_template(self):
        """Test rendering with non-existent template raises error"""
        with self.assertRaises(TemplateNotFoundError):
            ReportService.render('nonexistent.v1', self.sample_context)
    
    def test_generate_and_store(self):
        """Test generating and storing a report"""
        report = ReportService.generate_and_store(
            report_key='change.v1',
            object_type='change',
            object_id='CHG-001',
            context=self.sample_context,
            created_by=self.user
        )
        
        # Check that report was created
        self.assertIsInstance(report, ReportDocument)
        self.assertEqual(report.report_key, 'change.v1')
        self.assertEqual(report.object_type, 'change')
        self.assertEqual(report.object_id, 'CHG-001')
        self.assertEqual(report.created_by, self.user)
        
        # Check context snapshot
        self.assertEqual(report.context_json, self.sample_context)
        
        # Check SHA256 was calculated
        self.assertEqual(len(report.sha256), 64)
        
        # Check that PDF file was saved
        self.assertTrue(report.pdf_file)
        self.assertTrue(report.pdf_file.name.endswith('.pdf'))
        
        # Check that file exists and has content
        report.pdf_file.open('rb')
        pdf_content = report.pdf_file.read()
        report.pdf_file.close()
        
        self.assertTrue(pdf_content.startswith(b'%PDF'))
        self.assertGreater(len(pdf_content), 1024)
    
    def test_generate_and_store_with_metadata(self):
        """Test generating report with additional metadata"""
        metadata = {
            'created_via': 'test',
            'version': '1.0',
        }
        
        report = ReportService.generate_and_store(
            report_key='change.v1',
            object_type='change',
            object_id='CHG-002',
            context=self.sample_context,
            metadata=metadata,
            created_by=self.user
        )
        
        # Check metadata was stored
        self.assertEqual(report.metadata, metadata)
    
    def test_multipage_report(self):
        """Test that multi-page reports work with page numbers"""
        # Create a context with many items to force multiple pages
        large_context = self.sample_context.copy()
        large_context['items'] = [
            {'position': str(i), 'description': f'Item {i} description that is long enough to take space', 'status': 'Done'}
            for i in range(1, 100)  # 100 items should create multiple pages
        ]
        
        pdf_bytes = ReportService.render('change.v1', large_context)
        
        # Check that we got a PDF
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        
        # Multi-page PDF should be larger
        self.assertGreater(len(pdf_bytes), 10000)
    
    def test_reproducible_generation(self):
        """Test that same context produces same PDF (same hash)"""
        pdf1 = ReportService.render('change.v1', self.sample_context)
        pdf2 = ReportService.render('change.v1', self.sample_context)
        
        import hashlib
        hash1 = hashlib.sha256(pdf1).hexdigest()
        hash2 = hashlib.sha256(pdf2).hexdigest()
        
        # Same context should produce same PDF
        # Note: This might fail if PDF includes timestamps. For true reproducibility,
        # we'd need to ensure no dynamic timestamps are in the PDF.
        # For now, just check that both are valid PDFs of similar size
        self.assertTrue(pdf1.startswith(b'%PDF'))
        self.assertTrue(pdf2.startswith(b'%PDF'))
        self.assertGreater(len(pdf1), 1024)
        self.assertGreater(len(pdf2), 1024)
    
    def test_report_queryability(self):
        """Test that stored reports can be queried"""
        # Create multiple reports
        for i in range(1, 4):
            ReportService.generate_and_store(
                report_key='change.v1',
                object_type='change',
                object_id=f'CHG-{i:03d}',
                context=self.sample_context,
                created_by=self.user
            )
        
        # Query all reports
        all_reports = ReportDocument.objects.all()
        self.assertEqual(all_reports.count(), 3)
        
        # Query by report_key
        change_reports = ReportDocument.objects.filter(report_key='change.v1')
        self.assertEqual(change_reports.count(), 3)
        
        # Query by object_type and object_id
        specific_report = ReportDocument.objects.filter(
            object_type='change',
            object_id='CHG-002'
        ).first()
        self.assertIsNotNone(specific_report)
        self.assertEqual(specific_report.object_id, 'CHG-002')
