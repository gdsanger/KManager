from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.conf import settings
from datetime import date
from pathlib import Path
import tempfile
import shutil

from core.models import Adresse
from vermietung.models import (
    MietObjekt, Vertrag, Uebergabeprotokoll, Dokument,
    validate_file_size, validate_file_type, MAX_FILE_SIZE
)


User = get_user_model()


class DokumentModelTest(TestCase):
    """Tests for the Dokument model."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create temporary directory for test files
        self.test_media_root = tempfile.mkdtemp()
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create a customer address
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
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
        
        # Create a contract
        self.vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=100.00,
            kaution=200.00,
            status='active'
        )
        
        # Create a handover protocol
        self.protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2
        )
    
    def tearDown(self):
        """Clean up test files."""
        # Remove test media directory
        if Path(self.test_media_root).exists():
            shutil.rmtree(self.test_media_root)
    
    def test_dokument_requires_exactly_one_target_entity(self):
        """Test that a document must be linked to exactly one entity."""
        # Test: No entity linked
        dokument = Dokument(
            original_filename='test.pdf',
            storage_path='test/1/test.pdf',
            file_size=1000,
            mime_type='application/pdf'
        )
        with self.assertRaises(ValidationError) as context:
            dokument.full_clean()
        self.assertIn('genau einem Zielobjekt', str(context.exception))
        
        # Test: Multiple entities linked
        dokument = Dokument(
            original_filename='test.pdf',
            storage_path='test/1/test.pdf',
            file_size=1000,
            mime_type='application/pdf',
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt
        )
        with self.assertRaises(ValidationError) as context:
            dokument.full_clean()
        self.assertIn('nur einem einzigen Zielobjekt', str(context.exception))
    
    def test_dokument_creation_with_vertrag(self):
        """Test creating a document linked to a Vertrag."""
        dokument = Dokument.objects.create(
            original_filename='vertrag.pdf',
            storage_path='vertrag/1/vertrag.pdf',
            file_size=1000,
            mime_type='application/pdf',
            vertrag=self.vertrag,
            uploaded_by=self.user
        )
        
        self.assertEqual(dokument.vertrag, self.vertrag)
        self.assertIsNone(dokument.mietobjekt)
        self.assertIsNone(dokument.adresse)
        self.assertIsNone(dokument.uebergabeprotokoll)
        self.assertEqual(dokument.get_entity_type(), 'vertrag')
        self.assertEqual(dokument.get_entity_id(), self.vertrag.id)
    
    def test_dokument_creation_with_mietobjekt(self):
        """Test creating a document linked to a MietObjekt."""
        dokument = Dokument.objects.create(
            original_filename='objekt.jpg',
            storage_path='mietobjekt/1/objekt.jpg',
            file_size=2000,
            mime_type='image/jpeg',
            mietobjekt=self.mietobjekt,
            uploaded_by=self.user
        )
        
        self.assertIsNone(dokument.vertrag)
        self.assertEqual(dokument.mietobjekt, self.mietobjekt)
        self.assertIsNone(dokument.adresse)
        self.assertIsNone(dokument.uebergabeprotokoll)
        self.assertEqual(dokument.get_entity_type(), 'mietobjekt')
        self.assertEqual(dokument.get_entity_id(), self.mietobjekt.id)
    
    def test_dokument_creation_with_adresse(self):
        """Test creating a document linked to an Adresse."""
        dokument = Dokument.objects.create(
            original_filename='adresse.png',
            storage_path='adresse/1/adresse.png',
            file_size=3000,
            mime_type='image/png',
            adresse=self.kunde,
            uploaded_by=self.user
        )
        
        self.assertIsNone(dokument.vertrag)
        self.assertIsNone(dokument.mietobjekt)
        self.assertEqual(dokument.adresse, self.kunde)
        self.assertIsNone(dokument.uebergabeprotokoll)
        self.assertEqual(dokument.get_entity_type(), 'adresse')
        self.assertEqual(dokument.get_entity_id(), self.kunde.id)
    
    def test_dokument_creation_with_uebergabeprotokoll(self):
        """Test creating a document linked to an Uebergabeprotokoll."""
        dokument = Dokument.objects.create(
            original_filename='protokoll.pdf',
            storage_path='uebergabeprotokoll/1/protokoll.pdf',
            file_size=4000,
            mime_type='application/pdf',
            uebergabeprotokoll=self.protokoll,
            uploaded_by=self.user
        )
        
        self.assertIsNone(dokument.vertrag)
        self.assertIsNone(dokument.mietobjekt)
        self.assertIsNone(dokument.adresse)
        self.assertEqual(dokument.uebergabeprotokoll, self.protokoll)
        self.assertEqual(dokument.get_entity_type(), 'uebergabeprotokoll')
        self.assertEqual(dokument.get_entity_id(), self.protokoll.id)
    
    def test_generate_storage_path(self):
        """Test storage path generation."""
        path = Dokument.generate_storage_path('vertrag', 123, 'test.pdf')
        self.assertEqual(path, 'vertrag/123/test.pdf')
        
        path = Dokument.generate_storage_path('mietobjekt', 456, 'image.jpg')
        self.assertEqual(path, 'mietobjekt/456/image.jpg')
    
    def test_get_entity_display(self):
        """Test entity display string."""
        dokument = Dokument.objects.create(
            original_filename='test.pdf',
            storage_path='vertrag/1/test.pdf',
            file_size=1000,
            mime_type='application/pdf',
            vertrag=self.vertrag,
            uploaded_by=self.user
        )
        
        display = dokument.get_entity_display()
        self.assertIn('Vertrag', display)
        self.assertIn(str(self.vertrag), display)
    
    def test_dokument_str_representation(self):
        """Test string representation of Dokument."""
        dokument = Dokument.objects.create(
            original_filename='test.pdf',
            storage_path='vertrag/1/test.pdf',
            file_size=1000,
            mime_type='application/pdf',
            vertrag=self.vertrag,
            uploaded_by=self.user
        )
        
        str_repr = str(dokument)
        self.assertIn('test.pdf', str_repr)
        self.assertIn('Vertrag', str_repr)


class FileValidationTest(TestCase):
    """Tests for file validation functions."""
    
    def test_validate_file_size_too_large(self):
        """Test that files larger than 10 MB are rejected."""
        # Create a mock file that's too large
        large_file = SimpleUploadedFile(
            "large.pdf",
            b"x" * (MAX_FILE_SIZE + 1),
            content_type="application/pdf"
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_file_size(large_file)
        self.assertIn('überschreitet', str(context.exception))
    
    def test_validate_file_size_acceptable(self):
        """Test that files smaller than 10 MB are accepted."""
        # Create a mock file that's small enough
        small_file = SimpleUploadedFile(
            "small.pdf",
            b"x" * 1000,
            content_type="application/pdf"
        )
        
        # Should not raise an exception
        try:
            validate_file_size(small_file)
        except ValidationError:
            self.fail("validate_file_size raised ValidationError unexpectedly")
    
    def test_validate_file_type_pdf(self):
        """Test PDF file validation."""
        # Create a minimal PDF file
        pdf_content = b'%PDF-1.4\n%\xE2\xE3\xCF\xD3\n'
        pdf_file = SimpleUploadedFile(
            "test.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        # Should not raise an exception
        try:
            validate_file_type(pdf_file)
        except ValidationError:
            self.fail("validate_file_type raised ValidationError for valid PDF")
    
    def test_validate_file_type_image(self):
        """Test image file validation."""
        # Create a minimal PNG file (PNG signature)
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00\x00\x00\x00:~\x9bU\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        png_file = SimpleUploadedFile(
            "test.png",
            png_content,
            content_type="image/png"
        )
        
        # Should not raise an exception
        try:
            validate_file_type(png_file)
        except ValidationError:
            self.fail("validate_file_type raised ValidationError for valid PNG")


class DokumentDownloadViewTest(TestCase):
    """Tests for the document download view."""
    
    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create necessary objects
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test User',
            strasse='Test Street 1',
            plz='12345',
            ort='Test City',
            land='Deutschland'
        )
        
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standort Str. 1',
            plz='11111',
            ort='Stadt',
            land='Deutschland'
        )
        
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Objekt',
            type='GEBAEUDE',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=100.00
        )
        
        self.vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=100.00,
            kaution=200.00
        )
        
        # Create a test document
        self.dokument = Dokument.objects.create(
            original_filename='test.pdf',
            storage_path='vertrag/1/test.pdf',
            file_size=100,
            mime_type='application/pdf',
            vertrag=self.vertrag,
            uploaded_by=self.user
        )
        
        self.client = Client()
    
    def test_download_requires_authentication(self):
        """Test that download view requires authentication."""
        response = self.client.get(
            f'/vermietung/dokument/{self.dokument.id}/download/'
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_download_with_authentication(self):
        """Test that authenticated users can access download view."""
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Try to download (will fail because file doesn't exist, but should pass auth)
        response = self.client.get(
            f'/vermietung/dokument/{self.dokument.id}/download/'
        )
        
        # Should either succeed (200) or return 404 if file doesn't exist
        # but should NOT redirect to login
        self.assertIn(response.status_code, [200, 404])
    
    def test_download_nonexistent_document(self):
        """Test downloading a document that doesn't exist in DB."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get('/vermietung/dokument/99999/download/')
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
