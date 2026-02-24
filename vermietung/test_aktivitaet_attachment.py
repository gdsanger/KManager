from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.urls import reverse
from pathlib import Path
import json
import tempfile
import shutil
import io

from core.models import Adresse
from vermietung.models import (
    Aktivitaet, AktivitaetAttachment,
    validate_attachment_file_size, validate_attachment_file_type, 
    MAX_ATTACHMENT_FILE_SIZE
)


User = get_user_model()


class AktivitaetAttachmentModelTest(TestCase):
    """Tests for the AktivitaetAttachment model."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create temporary directory for test files
        self.test_media_root = tempfile.mkdtemp()
        # Override settings for testing
        settings.VERMIETUNG_DOCUMENTS_ROOT = Path(self.test_media_root)
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        
        # Create a test activity
        self.aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test description',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user
        )
    
    def tearDown(self):
        """Clean up test files."""
        # Remove test media directory
        if Path(self.test_media_root).exists():
            shutil.rmtree(self.test_media_root)
    
    def create_test_file(self, filename='test.txt', content=b'Test content', content_type='text/plain'):
        """Helper to create a test file."""
        return SimpleUploadedFile(filename, content, content_type=content_type)
    
    def test_generate_storage_path(self):
        """Test storage path generation."""
        storage_path = AktivitaetAttachment.generate_storage_path(
            self.aktivitaet.pk, 
            'test.txt'
        )
        
        self.assertIn(f'aktivitaet/{self.aktivitaet.pk}/attachments/', storage_path)
        self.assertIn('test.txt', storage_path)
    
    def test_save_uploaded_file(self):
        """Test saving an uploaded file."""
        uploaded_file = self.create_test_file('test.txt')
        
        attachment = AktivitaetAttachment.save_uploaded_file(
            uploaded_file,
            self.aktivitaet.pk,
            self.user
        )
        
        # Check database record
        self.assertEqual(attachment.aktivitaet, self.aktivitaet)
        self.assertEqual(attachment.original_filename, 'test.txt')
        self.assertEqual(attachment.mime_type, 'text/plain')
        self.assertEqual(attachment.uploaded_by, self.user)
        
        # Check file was saved
        file_path = attachment.get_absolute_path()
        self.assertTrue(file_path.exists())
        
        # Check file content
        with open(file_path, 'rb') as f:
            self.assertEqual(f.read(), b'Test content')
    
    def test_save_uploaded_pdf(self):
        """Test saving a PDF file."""
        # Create a minimal PDF file
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF'
        uploaded_file = self.create_test_file('test.pdf', pdf_content, 'application/pdf')
        
        attachment = AktivitaetAttachment.save_uploaded_file(
            uploaded_file,
            self.aktivitaet.pk,
            self.user
        )
        
        self.assertEqual(attachment.original_filename, 'test.pdf')
        self.assertIn('pdf', attachment.mime_type.lower())
    
    def test_delete_removes_file(self):
        """Test that deleting attachment also removes file from filesystem."""
        uploaded_file = self.create_test_file('test.txt')
        attachment = AktivitaetAttachment.save_uploaded_file(
            uploaded_file,
            self.aktivitaet.pk,
            self.user
        )
        
        file_path = attachment.get_absolute_path()
        self.assertTrue(file_path.exists())
        
        # Delete attachment
        attachment.delete()
        
        # Check file was removed
        self.assertFalse(file_path.exists())
    
    def test_validate_file_size_valid(self):
        """Test file size validation with valid file."""
        # Create a small file (< 5 MB)
        small_file = self.create_test_file('small.txt', b'x' * 1024)
        
        # Should not raise error
        try:
            validate_attachment_file_size(small_file)
        except ValidationError:
            self.fail('validate_attachment_file_size raised ValidationError unexpectedly')
    
    def test_validate_file_size_too_large(self):
        """Test file size validation with file that's too large."""
        # Create a file larger than 5 MB
        large_content = b'x' * (MAX_ATTACHMENT_FILE_SIZE + 1)
        large_file = self.create_test_file('large.txt', large_content)
        
        # Should raise ValidationError
        with self.assertRaises(ValidationError) as cm:
            validate_attachment_file_size(large_file)
        
        self.assertIn('überschreitet', str(cm.exception))
    
    def test_validate_blocked_extension_exe(self):
        """Test that .exe files are blocked."""
        exe_file = self.create_test_file('malware.exe', b'MZ\x90\x00')
        
        with self.assertRaises(ValidationError) as cm:
            validate_attachment_file_type(exe_file)
        
        self.assertIn('nicht erlaubt', str(cm.exception))
    
    def test_validate_blocked_extension_js(self):
        """Test that .js files are blocked."""
        js_file = self.create_test_file('script.js', b'alert("XSS")')
        
        with self.assertRaises(ValidationError) as cm:
            validate_attachment_file_type(js_file)
        
        self.assertIn('nicht erlaubt', str(cm.exception))
    
    def test_validate_blocked_extension_bat(self):
        """Test that .bat files are blocked."""
        bat_file = self.create_test_file('script.bat', b'@echo off\ndel /q *.*')
        
        with self.assertRaises(ValidationError) as cm:
            validate_attachment_file_type(bat_file)
        
        self.assertIn('nicht erlaubt', str(cm.exception))
    
    def test_validate_allowed_text_file(self):
        """Test that text files are allowed."""
        text_file = self.create_test_file('document.txt', b'Hello world')
        
        try:
            mime_type = validate_attachment_file_type(text_file)
            self.assertEqual(mime_type, 'text/plain')
        except ValidationError:
            self.fail('validate_attachment_file_type raised ValidationError for valid text file')


class AktivitaetAttachmentViewTest(TestCase):
    """Tests for the AktivitaetAttachment views."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create temporary directory for test files
        self.test_media_root = tempfile.mkdtemp()
        settings.VERMIETUNG_DOCUMENTS_ROOT = Path(self.test_media_root)
        
        # Create a test user with Vermietung permission
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        
        # Create Vermietung group and add user
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
        # Create a test activity
        self.aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test description',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def tearDown(self):
        """Clean up test files."""
        if Path(self.test_media_root).exists():
            shutil.rmtree(self.test_media_root)
    
    def create_test_file(self, filename='test.txt', content=b'Test content'):
        """Helper to create a test file."""
        return SimpleUploadedFile(filename, content, content_type='text/plain')
    
    def test_upload_single_attachment(self):
        """Test uploading a single attachment."""
        uploaded_file = self.create_test_file('test.txt')
        
        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload', args=[self.aktivitaet.pk]),
            {'attachments': uploaded_file}
        )
        
        # Should redirect to edit page
        self.assertEqual(response.status_code, 302)
        
        # Check attachment was created
        self.assertEqual(self.aktivitaet.attachments.count(), 1)
        attachment = self.aktivitaet.attachments.first()
        self.assertEqual(attachment.original_filename, 'test.txt')
    
    def test_upload_multiple_attachments(self):
        """Test uploading multiple attachments."""
        file1 = self.create_test_file('test1.txt', b'Content 1')
        file2 = self.create_test_file('test2.txt', b'Content 2')
        
        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload', args=[self.aktivitaet.pk]),
            {'attachments': [file1, file2]}
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.aktivitaet.attachments.count(), 2)
    
    def test_upload_requires_authentication(self):
        """Test that upload requires authentication."""
        self.client.logout()
        
        uploaded_file = self.create_test_file('test.txt')
        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload', args=[self.aktivitaet.pk]),
            {'attachments': uploaded_file}
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)
    
    def test_serve_attachment(self):
        """Test serving an attachment."""
        # Create attachment
        uploaded_file = self.create_test_file('test.txt', b'Test content')
        attachment = AktivitaetAttachment.save_uploaded_file(
            uploaded_file,
            self.aktivitaet.pk,
            self.user
        )
        
        # Serve attachment
        response = self.client.get(
            reverse('vermietung:aktivitaet_attachment_serve', args=[attachment.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
    
    def test_serve_requires_authentication(self):
        """Test that serving requires authentication."""
        uploaded_file = self.create_test_file('test.txt')
        attachment = AktivitaetAttachment.save_uploaded_file(
            uploaded_file,
            self.aktivitaet.pk,
            self.user
        )
        
        self.client.logout()
        
        response = self.client.get(
            reverse('vermietung:aktivitaet_attachment_serve', args=[attachment.pk])
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)
    
    def test_delete_attachment(self):
        """Test deleting an attachment."""
        # Create attachment
        uploaded_file = self.create_test_file('test.txt')
        attachment = AktivitaetAttachment.save_uploaded_file(
            uploaded_file,
            self.aktivitaet.pk,
            self.user
        )
        
        attachment_id = attachment.pk
        file_path = attachment.get_absolute_path()
        
        # Delete attachment
        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_delete', args=[attachment_id])
        )
        
        # Should redirect to edit page
        self.assertEqual(response.status_code, 302)
        
        # Check attachment was deleted
        self.assertEqual(AktivitaetAttachment.objects.filter(pk=attachment_id).count(), 0)
        
        # Check file was removed
        self.assertFalse(file_path.exists())
    
    def test_delete_requires_post(self):
        """Test that delete requires POST method."""
        uploaded_file = self.create_test_file('test.txt')
        attachment = AktivitaetAttachment.save_uploaded_file(
            uploaded_file,
            self.aktivitaet.pk,
            self.user
        )
        
        # Try GET request
        response = self.client.get(
            reverse('vermietung:aktivitaet_attachment_delete', args=[attachment.pk])
        )
        
        # Should not be allowed
        self.assertEqual(response.status_code, 405)
    
    def test_upload_file_too_large(self):
        """Test uploading a file that's too large."""
        # Create a file larger than 5 MB
        large_content = b'x' * (MAX_ATTACHMENT_FILE_SIZE + 1)
        large_file = SimpleUploadedFile('large.txt', large_content, content_type='text/plain')
        
        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload', args=[self.aktivitaet.pk]),
            {'attachments': large_file}
        )
        
        # Should redirect but with error
        self.assertEqual(response.status_code, 302)
        
        # No attachment should be created
        self.assertEqual(self.aktivitaet.attachments.count(), 0)
    
    def test_upload_blocked_file_type(self):
        """Test uploading a blocked file type."""
        exe_file = SimpleUploadedFile('malware.exe', b'MZ\x90\x00', content_type='application/x-msdownload')
        
        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload', args=[self.aktivitaet.pk]),
            {'attachments': exe_file}
        )
        
        # Should redirect but with error
        self.assertEqual(response.status_code, 302)
        
        # No attachment should be created
        self.assertEqual(self.aktivitaet.attachments.count(), 0)

    def test_upload_api_inline_image(self):
        """Test uploading an inline image via the API endpoint (e.g. from drag-and-drop)."""
        # Minimal 1x1 PNG image bytes
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
            b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
            b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        image_file = SimpleUploadedFile('inline-image.png', png_bytes, content_type='image/png')

        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload_api', args=[self.aktivitaet.pk]),
            {'file': image_file},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('url', data)
        self.assertIn('attachment_id', data)
        self.assertEqual(self.aktivitaet.attachments.count(), 1)

    def test_upload_api_requires_file(self):
        """Test that the API endpoint returns error when no file is provided."""
        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload_api', args=[self.aktivitaet.pk]),
            {},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_upload_api_requires_authentication(self):
        """Test that the API endpoint requires authentication."""
        # Log out the user
        self.client.logout()

        png_bytes = b'\x89PNG\r\n\x1a\n'
        image_file = SimpleUploadedFile('test.png', png_bytes, content_type='image/png')

        response = self.client.post(
            reverse('vermietung:aktivitaet_attachment_upload_api', args=[self.aktivitaet.pk]),
            {'file': image_file},
        )

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)
