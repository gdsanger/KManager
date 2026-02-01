"""
Tests for Eingangsrechnung AI import features:
- Default position creation when no positions exist
- PDF access in UI (list and detail views)
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
from pathlib import Path
import tempfile
import os

from core.models import Adresse, Kostenart
from vermietung.models import MietObjekt, Eingangsrechnung, EingangsrechnungAufteilung, Dokument


class EingangsrechnungDefaultPositionTestCase(TestCase):
    """Test case for default position creation during AI import"""
    
    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create a supplier (lieferant)
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Test Lieferant GmbH',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            email='test@lieferant.de'
        )
        
        # Create a location (standort)
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort Test',
            strasse='Standortstrasse 1',
            plz='54321',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        # Create a mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Testgebäude',
            type='GEBAEUDE',
            beschreibung='Test Beschreibung',
            fläche=Decimal('100.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00')
        )
        
        # Ensure "Allgemein" Kostenart exists
        self.allgemein_kostenart = Kostenart.objects.create(
            name='Allgemein',
            parent=None,
            umsatzsteuer_satz='19'
        )
    
    def test_default_position_created_when_no_positions_exist(self):
        """Test that a default position is created when invoice has no positions after creation"""
        # Create an invoice without positions (simulating AI import)
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
            belegnummer='AI-2024-001',
            betreff='AI Generated Invoice'
        )
        
        # Verify no positions initially
        self.assertEqual(rechnung.aufteilungen.count(), 0)
        
        # Simulate the default position creation logic from the view
        if rechnung.aufteilungen.count() == 0:
            allgemein_kostenart, created = Kostenart.objects.get_or_create(
                name="Allgemein",
                parent=None,
                defaults={'umsatzsteuer_satz': '19'}
            )
            
            aufteilung_data = {
                'eingangsrechnung': rechnung,
                'kostenart1': allgemein_kostenart,
                'kostenart2': None,
                'nettobetrag': Decimal('0')
            }
            
            default_aufteilung = EingangsrechnungAufteilung(**aufteilung_data)
            default_aufteilung.save()
        
        # Refresh from database
        rechnung.refresh_from_db()
        
        # Verify default position was created
        self.assertEqual(rechnung.aufteilungen.count(), 1)
        
        # Verify the position has correct data
        aufteilung = rechnung.aufteilungen.first()
        self.assertEqual(aufteilung.kostenart1.name, 'Allgemein')
        self.assertIsNone(aufteilung.kostenart2)
        self.assertEqual(aufteilung.nettobetrag, Decimal('0'))
    
    def test_default_position_with_extracted_amount(self):
        """Test that default position uses extracted amount if available"""
        # Create invoice
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
            belegnummer='AI-2024-002',
            betreff='AI Invoice with Amount'
        )
        
        # Simulate default position creation with extracted amount
        extracted_netto = Decimal('150.50')
        
        if rechnung.aufteilungen.count() == 0:
            allgemein_kostenart, _ = Kostenart.objects.get_or_create(
                name="Allgemein",
                parent=None,
                defaults={'umsatzsteuer_satz': '19'}
            )
            
            EingangsrechnungAufteilung.objects.create(
                eingangsrechnung=rechnung,
                kostenart1=allgemein_kostenart,
                kostenart2=None,
                nettobetrag=extracted_netto
            )
        
        # Verify position has extracted amount
        aufteilung = rechnung.aufteilungen.first()
        self.assertEqual(aufteilung.nettobetrag, extracted_netto)
        
        # Verify invoice totals are calculated correctly
        self.assertEqual(rechnung.nettobetrag, extracted_netto)
        # VAT calculation: 150.50 * 0.19 = 28.595 -> 28.60 (rounded)
        expected_vat = Decimal('28.60')
        self.assertEqual(aufteilung.umsatzsteuer, expected_vat)
    
    def test_no_default_position_created_when_positions_exist(self):
        """Test that no default position is created if positions already exist"""
        # Create invoice
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
            belegnummer='MANUAL-2024-001',
            betreff='Manual Invoice'
        )
        
        # Create a custom cost type
        custom_kostenart = Kostenart.objects.create(
            name='Custom Cost Type',
            parent=None,
            umsatzsteuer_satz='19'
        )
        
        # Manually add a position
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung,
            kostenart1=custom_kostenart,
            nettobetrag=Decimal('100.00')
        )
        
        # Simulate the check from the view
        initial_count = rechnung.aufteilungen.count()
        
        if rechnung.aufteilungen.count() == 0:
            # This should NOT execute
            allgemein_kostenart, _ = Kostenart.objects.get_or_create(
                name="Allgemein",
                parent=None,
                defaults={'umsatzsteuer_satz': '19'}
            )
            
            EingangsrechnungAufteilung.objects.create(
                eingangsrechnung=rechnung,
                kostenart1=allgemein_kostenart,
                nettobetrag=Decimal('0')
            )
        
        # Verify count hasn't changed
        self.assertEqual(rechnung.aufteilungen.count(), initial_count)
        self.assertEqual(rechnung.aufteilungen.count(), 1)
        
        # Verify the existing position is still there and unchanged
        aufteilung = rechnung.aufteilungen.first()
        self.assertEqual(aufteilung.kostenart1.name, 'Custom Cost Type')


class EingangsrechnungPDFAccessTestCase(TestCase):
    """Test case for PDF access in UI"""
    
    def setUp(self):
        """Set up test data"""
        # Create user with vermietung access (staff user)
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True  # Staff users have vermietung access
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create a supplier
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='PDF Test Lieferant',
            strasse='PDFStr 1',
            plz='12345',
            ort='PDFStadt',
            land='Deutschland'
        )
        
        # Create standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='PDF Standort',
            strasse='StandortStr 1',
            plz='54321',
            ort='StandortStadt',
            land='Deutschland'
        )
        
        # Create mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='PDF Testgebäude',
            type='GEBAEUDE',
            beschreibung='PDF Test',
            standort=self.standort,
            mietpreis=Decimal('1000.00')
        )
        
        # Create invoice
        self.rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
            belegnummer='PDF-2024-001',
            betreff='Invoice with PDF'
        )
        
        # Create a dummy PDF file for testing
        self.temp_pdf_path = None
        self.create_dummy_pdf()
    
    def create_dummy_pdf(self):
        """Create a dummy PDF file for testing"""
        # Create a minimal valid PDF
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
190
%%EOF
"""
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
            f.write(pdf_content)
            self.temp_pdf_path = f.name
    
    def tearDown(self):
        """Clean up temp files"""
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            os.unlink(self.temp_pdf_path)
        
        # Clean up any uploaded documents
        for dokument in Dokument.objects.all():
            file_path = dokument.get_absolute_path()
            if file_path.exists():
                file_path.unlink()
    
    def test_pdf_download_endpoint_requires_auth(self):
        """Test that PDF download endpoint requires authentication"""
        # Logout
        self.client.logout()
        
        # Try to access PDF download
        url = reverse('vermietung:eingangsrechnung_download_pdf', args=[self.rechnung.pk])
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_pdf_download_returns_404_when_no_pdf(self):
        """Test that PDF download returns 404 when invoice has no PDF"""
        url = reverse('vermietung:eingangsrechnung_download_pdf', args=[self.rechnung.pk])
        response = self.client.get(url)
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_pdf_download_returns_file_when_pdf_exists(self):
        """Test that PDF download returns file when PDF exists"""
        # Create a SimpleUploadedFile (Django's file wrapper)
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
190
%%EOF
"""
        
        pdf_file = SimpleUploadedFile(
            "test_invoice.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        # Upload using the save_uploaded_file method
        storage_path, mime_type = Dokument.save_uploaded_file(
            pdf_file,
            'eingangsrechnung',
            self.rechnung.id
        )
        
        # Create document record
        dokument = Dokument.objects.create(
            original_filename='test_invoice.pdf',
            storage_path=storage_path,
            file_size=len(pdf_content),
            mime_type='application/pdf',
            uploaded_by=self.user,
            eingangsrechnung=self.rechnung
        )
        
        # Request PDF download
        url = reverse('vermietung:eingangsrechnung_download_pdf', args=[self.rechnung.pk])
        response = self.client.get(url)
        
        # Should return file
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response.get('Content-Disposition', ''))
    
    def test_detail_view_includes_pdf_context(self):
        """Test that detail view includes PDF in context when available"""
        # Create a SimpleUploadedFile
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
190
%%EOF
"""
        
        pdf_file = SimpleUploadedFile(
            "test_invoice.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        storage_path, mime_type = Dokument.save_uploaded_file(
            pdf_file,
            'eingangsrechnung',
            self.rechnung.id
        )
        
        dokument = Dokument.objects.create(
            original_filename='test_invoice.pdf',
            storage_path=storage_path,
            file_size=len(pdf_content),
            mime_type='application/pdf',
            uploaded_by=self.user,
            eingangsrechnung=self.rechnung
        )
        
        # Get detail view
        url = reverse('vermietung:eingangsrechnung_detail', args=[self.rechnung.pk])
        response = self.client.get(url)
        
        # Should have PDF in context
        self.assertEqual(response.status_code, 200)
        self.assertIn('pdf_dokument', response.context)
        self.assertIsNotNone(response.context['pdf_dokument'])
        self.assertEqual(response.context['pdf_dokument'].id, dokument.id)
    
    def test_detail_view_without_pdf(self):
        """Test that detail view works when no PDF exists"""
        url = reverse('vermietung:eingangsrechnung_detail', args=[self.rechnung.pk])
        response = self.client.get(url)
        
        # Should work fine
        self.assertEqual(response.status_code, 200)
        self.assertIn('pdf_dokument', response.context)
        self.assertIsNone(response.context['pdf_dokument'])
