"""
Tests for Mandant logo upload functionality
"""
import os
import tempfile
from io import BytesIO
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.models import User
from PIL import Image
from core.models import Mandant
from core.forms import MandantForm


class MandantLogoUploadTestCase(TestCase):
    """Test Mandant logo upload functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create a test Mandant
        self.mandant = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 123",
            plz="12345",
            ort="Test City",
            land="Deutschland"
        )
        
        # Set up client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test media directory
        self.test_media_dir = os.path.join(settings.MEDIA_ROOT, 'mandants')
        os.makedirs(self.test_media_dir, exist_ok=True)
    
    def tearDown(self):
        """Clean up test files"""
        # Clean up any uploaded files
        if self.mandant.logo_path:
            logo_path = os.path.join(settings.MEDIA_ROOT, self.mandant.logo_path)
            if os.path.exists(logo_path):
                os.remove(logo_path)
        
        # Clean up test directory if empty
        if os.path.exists(self.test_media_dir) and not os.listdir(self.test_media_dir):
            os.rmdir(self.test_media_dir)
    
    def create_test_image(self, format='PNG', ext='png'):
        """Create a test image file"""
        file = BytesIO()
        image = Image.new('RGB', (100, 100), color='red')
        image.save(file, format=format)
        file.seek(0)
        return SimpleUploadedFile(
            f'test_logo.{ext}',
            file.read(),
            content_type=f'image/{ext}'
        )
    
    def test_form_accepts_jpg(self):
        """Test that form accepts .jpg files"""
        logo = self.create_test_image(format='JPEG', ext='jpg')
        form = MandantForm(
            data={
                'name': 'Test',
                'adresse': 'Test St',
                'plz': '12345',
                'ort': 'City',
                'land': 'DE'
            },
            files={'logo': logo}
        )
        
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNotNone(form.cleaned_data.get('logo'))
    
    def test_form_accepts_png(self):
        """Test that form accepts .png files"""
        logo = self.create_test_image(format='PNG', ext='png')
        form = MandantForm(
            data={
                'name': 'Test',
                'adresse': 'Test St',
                'plz': '12345',
                'ort': 'City',
                'land': 'DE'
            },
            files={'logo': logo}
        )
        
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNotNone(form.cleaned_data.get('logo'))
    
    def test_form_accepts_gif(self):
        """Test that form accepts .gif files"""
        logo = self.create_test_image(format='GIF', ext='gif')
        form = MandantForm(
            data={
                'name': 'Test',
                'adresse': 'Test St',
                'plz': '12345',
                'ort': 'City',
                'land': 'DE'
            },
            files={'logo': logo}
        )
        
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNotNone(form.cleaned_data.get('logo'))
    
    def test_form_rejects_webp(self):
        """Test that form rejects .webp files"""
        # Create a fake webp file (just renaming is enough for extension test)
        logo = SimpleUploadedFile(
            'test_logo.webp',
            b'fake webp content',
            content_type='image/webp'
        )
        
        form = MandantForm(
            data={
                'name': 'Test',
                'adresse': 'Test St',
                'plz': '12345',
                'ort': 'City',
                'land': 'DE'
            },
            files={'logo': logo}
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('logo', form.errors)
        self.assertIn('webp', str(form.errors['logo']).lower())
    
    def test_form_rejects_invalid_extension(self):
        """Test that form rejects invalid file extensions"""
        logo = SimpleUploadedFile(
            'test_logo.txt',
            b'not an image',
            content_type='text/plain'
        )
        
        form = MandantForm(
            data={
                'name': 'Test',
                'adresse': 'Test St',
                'plz': '12345',
                'ort': 'City',
                'land': 'DE'
            },
            files={'logo': logo}
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('logo', form.errors)
    
    def test_form_rejects_large_file(self):
        """Test that form rejects files larger than 5MB"""
        # Create a large file (over 5MB)
        large_content = b'x' * (6 * 1024 * 1024)  # 6MB
        logo = SimpleUploadedFile(
            'large_logo.jpg',
            large_content,
            content_type='image/jpeg'
        )
        
        form = MandantForm(
            data={
                'name': 'Test',
                'adresse': 'Test St',
                'plz': '12345',
                'ort': 'City',
                'land': 'DE'
            },
            files={'logo': logo}
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('logo', form.errors)
        self.assertIn('5MB', str(form.errors['logo']))
    
    def test_upload_logo_in_edit_view(self):
        """Test uploading logo through edit view"""
        logo = self.create_test_image(format='PNG', ext='png')
        
        response = self.client.post(
            reverse('mandant_edit', args=[self.mandant.pk]),
            data={
                'name': self.mandant.name,
                'adresse': self.mandant.adresse,
                'plz': self.mandant.plz,
                'ort': self.mandant.ort,
                'land': self.mandant.land,
                'logo': logo
            },
            follow=True
        )
        
        # Refresh mandant from database
        self.mandant.refresh_from_db()
        
        # Check that logo_path was set
        self.assertIsNotNone(self.mandant.logo_path)
        self.assertTrue(self.mandant.logo_path.startswith('mandants/'))
        
        # Check that file exists
        logo_full_path = os.path.join(settings.MEDIA_ROOT, self.mandant.logo_path)
        self.assertTrue(os.path.exists(logo_full_path))
    
    def test_upload_logo_in_detail_view(self):
        """Test uploading logo through detail view"""
        logo = self.create_test_image(format='PNG', ext='png')
        
        response = self.client.post(
            reverse('mandant_detail', args=[self.mandant.pk]),
            data={'logo': logo},
            follow=True
        )
        
        # Refresh mandant from database
        self.mandant.refresh_from_db()
        
        # Check that logo_path was set
        self.assertIsNotNone(self.mandant.logo_path)
        self.assertTrue(self.mandant.logo_path.startswith('mandants/'))
        
        # Check that file exists
        logo_full_path = os.path.join(settings.MEDIA_ROOT, self.mandant.logo_path)
        self.assertTrue(os.path.exists(logo_full_path))
    
    def test_replace_logo_deletes_old_file(self):
        """Test that uploading a new logo deletes the old file"""
        # Upload first logo
        logo1 = self.create_test_image(format='PNG', ext='png')
        self.client.post(
            reverse('mandant_edit', args=[self.mandant.pk]),
            data={
                'name': self.mandant.name,
                'adresse': self.mandant.adresse,
                'plz': self.mandant.plz,
                'ort': self.mandant.ort,
                'land': self.mandant.land,
                'logo': logo1
            }
        )
        
        self.mandant.refresh_from_db()
        old_logo_path = self.mandant.logo_path
        old_logo_full_path = os.path.join(settings.MEDIA_ROOT, old_logo_path)
        
        # Verify first logo exists
        self.assertTrue(os.path.exists(old_logo_full_path))
        
        # Upload second logo
        logo2 = self.create_test_image(format='JPEG', ext='jpg')
        self.client.post(
            reverse('mandant_edit', args=[self.mandant.pk]),
            data={
                'name': self.mandant.name,
                'adresse': self.mandant.adresse,
                'plz': self.mandant.plz,
                'ort': self.mandant.ort,
                'land': self.mandant.land,
                'logo': logo2
            }
        )
        
        self.mandant.refresh_from_db()
        
        # Check that old file was deleted
        self.assertFalse(os.path.exists(old_logo_full_path))
        
        # Check that new file exists
        new_logo_full_path = os.path.join(settings.MEDIA_ROOT, self.mandant.logo_path)
        self.assertTrue(os.path.exists(new_logo_full_path))
    
    def test_delete_logo(self):
        """Test deleting logo through detail view"""
        # First upload a logo
        logo = self.create_test_image(format='PNG', ext='png')
        self.client.post(
            reverse('mandant_detail', args=[self.mandant.pk]),
            data={'logo': logo}
        )
        
        self.mandant.refresh_from_db()
        logo_path = self.mandant.logo_path
        logo_full_path = os.path.join(settings.MEDIA_ROOT, logo_path)
        
        # Verify logo exists
        self.assertTrue(os.path.exists(logo_full_path))
        
        # Delete logo
        self.client.post(
            reverse('mandant_detail', args=[self.mandant.pk]),
            data={'delete_logo': '1'}
        )
        
        self.mandant.refresh_from_db()
        
        # Check that logo_path was cleared
        self.assertEqual(self.mandant.logo_path, '')
        
        # Check that file was deleted
        self.assertFalse(os.path.exists(logo_full_path))
    
    def test_mandant_stores_relative_path(self):
        """Test that Mandant stores relative path, not absolute"""
        logo = self.create_test_image(format='PNG', ext='png')
        
        self.client.post(
            reverse('mandant_edit', args=[self.mandant.pk]),
            data={
                'name': self.mandant.name,
                'adresse': self.mandant.adresse,
                'plz': self.mandant.plz,
                'ort': self.mandant.ort,
                'land': self.mandant.land,
                'logo': logo
            }
        )
        
        self.mandant.refresh_from_db()
        
        # Check that logo_path is relative (doesn't start with /)
        self.assertFalse(self.mandant.logo_path.startswith('/'))
        
        # Check that it doesn't contain MEDIA_ROOT
        self.assertNotIn(str(settings.MEDIA_ROOT), self.mandant.logo_path)
    
    def test_mandant_delete_removes_logo_file(self):
        """Test that deleting Mandant also deletes logo file"""
        # Upload a logo
        logo = self.create_test_image(format='PNG', ext='png')
        self.client.post(
            reverse('mandant_edit', args=[self.mandant.pk]),
            data={
                'name': self.mandant.name,
                'adresse': self.mandant.adresse,
                'plz': self.mandant.plz,
                'ort': self.mandant.ort,
                'land': self.mandant.land,
                'logo': logo
            }
        )
        
        self.mandant.refresh_from_db()
        logo_full_path = os.path.join(settings.MEDIA_ROOT, self.mandant.logo_path)
        
        # Verify logo exists
        self.assertTrue(os.path.exists(logo_full_path))
        
        # Delete Mandant
        self.client.post(reverse('mandant_delete', args=[self.mandant.pk]))
        
        # Check that file was deleted
        self.assertFalse(os.path.exists(logo_full_path))
