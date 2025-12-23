from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from datetime import date
from pathlib import Path
import tempfile
import shutil
from PIL import Image as PILImage
import io

from core.models import Adresse
from vermietung.models import (
    MietObjekt, MietObjektBild,
    validate_image_file_size, validate_image_file_type, MAX_FILE_SIZE
)


User = get_user_model()


class MietObjektBildModelTest(TestCase):
    """Tests for the MietObjektBild model."""
    
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
        
        # Create a location address
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstrasse 3',
            plz='11111',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        # Create a rental object
        self.mietobjekt = MietObjekt.objects.create(
            name='Garage 1',
            type='GEBAEUDE',
            beschreibung='Eine schöne Garage',
            fläche=20.00,
            standort=self.standort,
            mietpreis=100.00,
            verfuegbar=True
        )
    
    def tearDown(self):
        """Clean up test files."""
        # Remove test media directory
        if Path(self.test_media_root).exists():
            shutil.rmtree(self.test_media_root)
    
    def create_test_image(self, filename='test.jpg', size=(800, 600), format='JPEG'):
        """Helper to create a test image file."""
        image = PILImage.new('RGB', size, color='red')
        file = io.BytesIO()
        image.save(file, format=format)
        file.seek(0)
        return SimpleUploadedFile(filename, file.read(), content_type=f'image/{format.lower()}')
    
    def test_generate_storage_paths(self):
        """Test storage path generation."""
        original_path, thumbnail_path = MietObjektBild.generate_storage_paths(
            self.mietobjekt.pk, 
            'test.jpg'
        )
        
        self.assertIn(f'mietobjekt/{self.mietobjekt.pk}/images/', original_path)
        self.assertIn('test.jpg', original_path)
        self.assertIn('thumb_', thumbnail_path)
        self.assertIn('test.jpg', thumbnail_path)
    
    def test_save_uploaded_image(self):
        """Test saving an uploaded image with thumbnail generation."""
        uploaded_file = self.create_test_image('test.jpg')
        
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        # Check database record
        self.assertEqual(bild.mietobjekt, self.mietobjekt)
        self.assertEqual(bild.original_filename, 'test.jpg')
        self.assertEqual(bild.uploaded_by, self.user)
        self.assertEqual(bild.mime_type, 'image/jpeg')
        self.assertGreater(bild.file_size, 0)
        
        # Check files exist
        original_path = bild.get_absolute_path()
        thumbnail_path = bild.get_thumbnail_absolute_path()
        
        self.assertTrue(original_path.exists())
        self.assertTrue(thumbnail_path.exists())
        
        # Check thumbnail is actually smaller
        original_size = original_path.stat().st_size
        thumbnail_size = thumbnail_path.stat().st_size
        self.assertLess(thumbnail_size, original_size)
    
    def test_save_uploaded_png_image(self):
        """Test saving a PNG image."""
        uploaded_file = self.create_test_image('test.png', format='PNG')
        uploaded_file.content_type = 'image/png'
        
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        self.assertEqual(bild.mime_type, 'image/png')
        self.assertTrue(bild.get_absolute_path().exists())
        self.assertTrue(bild.get_thumbnail_absolute_path().exists())
    
    def test_delete_removes_files(self):
        """Test that deleting a MietObjektBild removes files from filesystem."""
        uploaded_file = self.create_test_image('test.jpg')
        
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        original_path = bild.get_absolute_path()
        thumbnail_path = bild.get_thumbnail_absolute_path()
        
        # Verify files exist
        self.assertTrue(original_path.exists())
        self.assertTrue(thumbnail_path.exists())
        
        # Delete the bild
        bild.delete()
        
        # Verify files are removed
        self.assertFalse(original_path.exists())
        self.assertFalse(thumbnail_path.exists())
    
    def test_validate_image_file_size_valid(self):
        """Test image file size validation with valid file."""
        uploaded_file = self.create_test_image('small.jpg', size=(100, 100))
        
        # Should not raise an error
        try:
            validate_image_file_size(uploaded_file)
        except ValidationError:
            self.fail("validate_image_file_size raised ValidationError unexpectedly")
    
    def test_validate_image_file_size_too_large(self):
        """Test image file size validation with too large file."""
        # Create a mock file that appears to be too large
        uploaded_file = self.create_test_image('large.jpg')
        uploaded_file.size = MAX_FILE_SIZE + 1
        
        with self.assertRaises(ValidationError) as context:
            validate_image_file_size(uploaded_file)
        
        self.assertIn('überschreitet', str(context.exception))
    
    def test_validate_image_file_type_jpeg(self):
        """Test image file type validation with JPEG."""
        uploaded_file = self.create_test_image('test.jpg', format='JPEG')
        
        mime_type = validate_image_file_type(uploaded_file)
        self.assertEqual(mime_type, 'image/jpeg')
    
    def test_validate_image_file_type_png(self):
        """Test image file type validation with PNG."""
        uploaded_file = self.create_test_image('test.png', format='PNG')
        uploaded_file.content_type = 'image/png'
        
        mime_type = validate_image_file_type(uploaded_file)
        self.assertEqual(mime_type, 'image/png')
    
    def test_validate_image_file_type_invalid(self):
        """Test image file type validation with invalid type."""
        # Create a text file
        uploaded_file = SimpleUploadedFile(
            'test.txt',
            b'This is not an image',
            content_type='text/plain'
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_image_file_type(uploaded_file)
        
        self.assertIn('nicht erlaubt', str(context.exception))
    
    def test_thumbnail_creation(self):
        """Test thumbnail creation with different image sizes."""
        uploaded_file = self.create_test_image('large.jpg', size=(2000, 1500))
        
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        # Open and check thumbnail dimensions
        thumbnail_path = bild.get_thumbnail_absolute_path()
        with PILImage.open(thumbnail_path) as img:
            # Thumbnail should be max 300x300, maintaining aspect ratio
            self.assertLessEqual(img.width, 300)
            self.assertLessEqual(img.height, 300)


class MietObjektBildViewTest(TestCase):
    """Tests for MietObjektBild views."""
    
    def setUp(self):
        """Set up test data."""
        self.test_media_root = tempfile.mkdtemp()
        settings.VERMIETUNG_DOCUMENTS_ROOT = Path(self.test_media_root)
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        
        self.non_staff_user = User.objects.create_user(
            username='normaluser',
            password='testpass123',
            is_staff=False
        )
        
        # Create Vermietung group and add non_staff_user
        from django.contrib.auth.models import Group
        vermietung_group = Group.objects.create(name='Vermietung')
        self.non_staff_user.groups.add(vermietung_group)
        
        # Create location and mietobjekt
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstrasse 3',
            plz='11111',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        self.mietobjekt = MietObjekt.objects.create(
            name='Garage 1',
            type='GEBAEUDE',
            beschreibung='Eine schöne Garage',
            standort=self.standort,
            mietpreis=100.00,
        )
        
        self.client = Client()
    
    def tearDown(self):
        """Clean up."""
        if Path(self.test_media_root).exists():
            shutil.rmtree(self.test_media_root)
    
    def create_test_image(self, filename='test.jpg', size=(800, 600), format='JPEG'):
        """Helper to create a test image file."""
        image = PILImage.new('RGB', size, color='blue')
        file = io.BytesIO()
        image.save(file, format=format)
        file.seek(0)
        return SimpleUploadedFile(filename, file.read(), content_type=f'image/{format.lower()}')
    
    def test_mietobjekt_detail_includes_bilder(self):
        """Test that mietobjekt detail view includes images."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a test image
        uploaded_file = self.create_test_image('test.jpg')
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        url = reverse('vermietung:mietobjekt_detail', args=[self.mietobjekt.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('bilder_page_obj', response.context)
        self.assertEqual(response.context['bilder_page_obj'].paginator.count, 1)
    
    def test_upload_single_image(self):
        """Test uploading a single image."""
        self.client.login(username='testuser', password='testpass123')
        
        image_file = self.create_test_image('upload_test.jpg')
        
        url = reverse('vermietung:mietobjekt_bild_upload', args=[self.mietobjekt.pk])
        response = self.client.post(url, {
            'bilder': image_file
        })
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Check image was created
        self.assertEqual(MietObjektBild.objects.count(), 1)
        bild = MietObjektBild.objects.first()
        self.assertEqual(bild.original_filename, 'upload_test.jpg')
        self.assertEqual(bild.mietobjekt, self.mietobjekt)
    
    def test_upload_multiple_images(self):
        """Test uploading multiple images at once."""
        self.client.login(username='testuser', password='testpass123')
        
        image1 = self.create_test_image('image1.jpg')
        image2 = self.create_test_image('image2.jpg')
        image3 = self.create_test_image('image3.png', format='PNG')
        image3.content_type = 'image/png'
        
        url = reverse('vermietung:mietobjekt_bild_upload', args=[self.mietobjekt.pk])
        response = self.client.post(url, {
            'bilder': [image1, image2, image3]
        })
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Check all images were created
        self.assertEqual(MietObjektBild.objects.count(), 3)
        filenames = list(MietObjektBild.objects.values_list('original_filename', flat=True))
        self.assertIn('image1.jpg', filenames)
        self.assertIn('image2.jpg', filenames)
        self.assertIn('image3.png', filenames)
    
    def test_upload_requires_authentication(self):
        """Test that image upload requires authentication."""
        # Not logged in
        url = reverse('vermietung:mietobjekt_bild_upload', args=[self.mietobjekt.pk])
        response = self.client.post(url, {})
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_upload_requires_vermietung_access(self):
        """Test that image upload requires vermietung access."""
        # Create user without vermietung access
        user_no_access = User.objects.create_user(
            username='noaccess',
            password='testpass123'
        )
        self.client.login(username='noaccess', password='testpass123')
        
        url = reverse('vermietung:mietobjekt_bild_upload', args=[self.mietobjekt.pk])
        response = self.client.post(url, {})
        
        # Should be forbidden or redirect to login
        self.assertIn(response.status_code, [302, 403])
    
    def test_serve_thumbnail(self):
        """Test serving thumbnail image."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create image
        uploaded_file = self.create_test_image('serve_test.jpg')
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        url = reverse('vermietung:mietobjekt_bild_thumbnail', args=[bild.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
    
    def test_serve_original(self):
        """Test serving original image."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create image
        uploaded_file = self.create_test_image('original_test.jpg')
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        url = reverse('vermietung:mietobjekt_bild_original', args=[bild.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
    
    def test_serve_requires_authentication(self):
        """Test that serving images requires authentication."""
        # Create image
        uploaded_file = self.create_test_image('auth_test.jpg')
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        # Try to access without login
        url = reverse('vermietung:mietobjekt_bild_thumbnail', args=[bild.pk])
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_delete_image(self):
        """Test deleting an image."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create image
        uploaded_file = self.create_test_image('delete_test.jpg')
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        original_path = bild.get_absolute_path()
        thumbnail_path = bild.get_thumbnail_absolute_path()
        
        # Verify files exist
        self.assertTrue(original_path.exists())
        self.assertTrue(thumbnail_path.exists())
        
        # Delete via view
        url = reverse('vermietung:mietobjekt_bild_delete', args=[bild.pk])
        response = self.client.post(url)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Check image was deleted
        self.assertEqual(MietObjektBild.objects.count(), 0)
        
        # Check files were removed
        self.assertFalse(original_path.exists())
        self.assertFalse(thumbnail_path.exists())
    
    def test_delete_requires_post(self):
        """Test that delete requires POST method."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create image
        uploaded_file = self.create_test_image('delete_get_test.jpg')
        bild = MietObjektBild.save_uploaded_image(
            uploaded_file,
            self.mietobjekt.pk,
            self.user
        )
        
        # Try DELETE with GET
        url = reverse('vermietung:mietobjekt_bild_delete', args=[bild.pk])
        response = self.client.get(url)
        
        # Should not be allowed
        self.assertEqual(response.status_code, 405)
        
        # Image should still exist
        self.assertEqual(MietObjektBild.objects.count(), 1)
    
    def test_non_staff_with_vermietung_group_can_upload(self):
        """Test that non-staff users in Vermietung group can upload images."""
        self.client.login(username='normaluser', password='testpass123')
        
        image_file = self.create_test_image('group_test.jpg')
        
        url = reverse('vermietung:mietobjekt_bild_upload', args=[self.mietobjekt.pk])
        response = self.client.post(url, {
            'bilder': image_file
        })
        
        # Should succeed
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MietObjektBild.objects.count(), 1)
