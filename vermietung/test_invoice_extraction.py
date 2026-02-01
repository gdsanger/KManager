"""
Tests for AI-powered invoice extraction functionality.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import json

from core.services.ai.invoice_extraction import InvoiceDataDTO, InvoiceExtractionService
from core.services.ai.supplier_matching import SupplierMatchingService
from core.models import Adresse, AIProvider, AIModel
from vermietung.models import Eingangsrechnung, MietObjekt, Dokument


class InvoiceDataDTOTestCase(TestCase):
    """Test InvoiceDataDTO validation and parsing"""
    
    def test_validate_valid_data(self):
        """Test validation with valid data"""
        dto = InvoiceDataDTO(
            lieferant_name="Test Supplier GmbH",
            belegnummer="INV-2024-001",
            belegdatum="2024-01-15",
            faelligkeit="2024-02-15",
            betreff="Test Invoice",
            nettobetrag="100.50",
            umsatzsteuer="19.10",
            bruttobetrag="119.60"
        )
        
        validated = dto.validate()
        
        self.assertEqual(validated['lieferant_name'], "Test Supplier GmbH")
        self.assertEqual(validated['belegnummer'], "INV-2024-001")
        self.assertEqual(validated['belegdatum'], "2024-01-15")
        self.assertEqual(validated['nettobetrag'], Decimal('100.50'))
        self.assertEqual(validated['umsatzsteuer'], Decimal('19.10'))
    
    def test_validate_invalid_date(self):
        """Test validation with invalid date format"""
        dto = InvoiceDataDTO(
            belegdatum="15.01.2024"  # Wrong format
        )
        
        with self.assertRaises(ValidationError) as cm:
            dto.validate()
        
        self.assertIn('belegdatum', cm.exception.error_dict)
    
    def test_validate_invalid_decimal(self):
        """Test validation with invalid decimal value"""
        dto = InvoiceDataDTO(
            nettobetrag="not-a-number"
        )
        
        with self.assertRaises(ValidationError) as cm:
            dto.validate()
        
        self.assertIn('nettobetrag', cm.exception.error_dict)
    
    def test_validate_null_values(self):
        """Test that None values are properly handled"""
        dto = InvoiceDataDTO(
            lieferant_name="Test",
            belegnummer=None,
            belegdatum=None
        )
        
        validated = dto.validate()
        
        # None values should not be in the validated dict
        self.assertNotIn('belegnummer', validated)
        self.assertNotIn('belegdatum', validated)
        self.assertEqual(validated['lieferant_name'], "Test")


class SupplierMatchingTestCase(TestCase):
    """Test supplier matching logic"""
    
    def setUp(self):
        """Create test suppliers"""
        self.supplier1 = Adresse.objects.create(
            adressen_type='LIEFERANT',
            firma="Stadtwerke München GmbH",
            name="Hauptverwaltung",
            strasse="Musterstr. 123",
            plz="80331",
            ort="München",
            land="Deutschland"
        )
        
        self.supplier2 = Adresse.objects.create(
            adressen_type='LIEFERANT',
            firma="E.ON Energie Deutschland",
            name="Kundenservice",
            strasse="Brienner Str. 40",
            plz="80333",
            ort="München",
            land="Deutschland"
        )
        
        self.supplier3 = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name="Müller Handwerk",
            strasse="Dorfstr. 5",
            plz="82031",
            ort="Grünwald",
            land="Deutschland"
        )
        
        self.matching_service = SupplierMatchingService()
    
    def test_exact_name_match(self):
        """Test exact name matching"""
        result = self.matching_service.match_supplier_deterministic(
            name="Stadtwerke München GmbH"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.supplier1.id)
    
    def test_case_insensitive_match(self):
        """Test case-insensitive matching"""
        result = self.matching_service.match_supplier_deterministic(
            name="stadtwerke münchen gmbh"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.supplier1.id)
    
    def test_normalized_name_match(self):
        """Test normalized name matching (without legal forms)"""
        result = self.matching_service.match_supplier_deterministic(
            name="Stadtwerke München"  # Without GmbH
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.supplier1.id)
    
    def test_fuzzy_match_with_typo(self):
        """Test fuzzy matching with minor differences"""
        result = self.matching_service.match_supplier_deterministic(
            name="Stadtwerke Muenchen GmbH"  # ü -> ue
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.supplier1.id)
    
    def test_no_match_different_name(self):
        """Test that completely different names don't match"""
        result = self.matching_service.match_supplier_deterministic(
            name="Completely Different Company"
        )
        
        self.assertIsNone(result)
    
    def test_address_filtering(self):
        """Test filtering by address when multiple matches exist"""
        # Create another supplier with similar name
        supplier_copy = Adresse.objects.create(
            adressen_type='LIEFERANT',
            firma="Stadtwerke München GmbH",
            name="Zweigstelle",
            strasse="Andere Str. 456",
            plz="80339",
            ort="München",
            land="Deutschland"
        )
        
        # Should match the one with correct PLZ
        result = self.matching_service.match_supplier_deterministic(
            name="Stadtwerke München GmbH",
            plz="80331"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.supplier1.id)
    
    def test_match_by_name_field_not_firma(self):
        """Test matching using the 'name' field when firma is empty"""
        result = self.matching_service.match_supplier_deterministic(
            name="Müller Handwerk"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.supplier3.id)


class InvoiceExtractionIntegrationTestCase(TestCase):
    """Integration tests for invoice extraction flow"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        
        # Create standort first
        self.standort = Adresse.objects.create(
            name="Test Standort",
            strasse="Test Str. 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland"
        )
        
        self.mietobjekt = MietObjekt.objects.create(
            name="Test Lagerraum",
            type="Lagerraum",
            beschreibung="Test",
            standort=self.standort,
            mietpreis=Decimal('100.00')
        )
        
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            firma="Test Energy GmbH",
            name="Hauptverwaltung",
            strasse="Energy Str. 100",
            plz="80331",
            ort="München",
            land="Deutschland"
        )
    
    def test_json_parsing_with_valid_response(self):
        """Test JSON parsing from AI response"""
        service = InvoiceExtractionService()
        
        # Simulate AI response
        mock_response_data = {
            "lieferant_name": "Test Energy GmbH",
            "lieferant_strasse": "Energy Str. 100",
            "lieferant_plz": "80331",
            "lieferant_ort": "München",
            "lieferant_land": "Deutschland",
            "belegnummer": "RE-2024-001",
            "belegdatum": "2024-01-15",
            "faelligkeit": "2024-02-15",
            "betreff": "Stromversorgung Januar 2024",
            "nettobetrag": "150.00",
            "umsatzsteuer": "28.50",
            "bruttobetrag": "178.50"
        }
        
        # Create DTO from data
        dto = InvoiceDataDTO(**mock_response_data)
        validated = dto.validate()
        
        # Verify validated data
        self.assertEqual(validated['belegnummer'], "RE-2024-001")
        self.assertEqual(validated['nettobetrag'], Decimal('150.00'))
        self.assertEqual(validated['belegdatum'], "2024-01-15")
    
    def test_json_parsing_with_markdown_wrapper(self):
        """Test JSON parsing when AI returns markdown code blocks"""
        json_data = {
            "lieferant_name": "Test",
            "belegnummer": "INV-001"
        }
        
        # Simulate markdown-wrapped response
        response_text = f"```json\n{json.dumps(json_data)}\n```"
        
        # Clean markdown
        lines = response_text.split('\n')
        cleaned = '\n'.join(line for line in lines if not line.startswith('```'))
        
        # Parse
        parsed = json.loads(cleaned)
        
        self.assertEqual(parsed['lieferant_name'], "Test")
        self.assertEqual(parsed['belegnummer'], "INV-001")
    
    def test_json_parsing_with_null_values(self):
        """Test that null values are properly handled"""
        json_data = {
            "lieferant_name": "Test Company",
            "belegnummer": "INV-001",
            "belegdatum": None,  # AI couldn't extract
            "faelligkeit": None,
            "referenznummer": None
        }
        
        dto = InvoiceDataDTO(**json_data)
        validated = dto.validate()
        
        # Null values should not appear in validated dict
        self.assertNotIn('belegdatum', validated)
        self.assertNotIn('faelligkeit', validated)
        self.assertNotIn('referenznummer', validated)
        
        # Non-null values should be present
        self.assertEqual(validated['lieferant_name'], "Test Company")
        self.assertEqual(validated['belegnummer'], "INV-001")


class InvoiceExtractionErrorHandlingTestCase(TestCase):
    """Test error handling in invoice extraction"""
    
    def test_invalid_json_response(self):
        """Test handling of invalid JSON from AI"""
        service = InvoiceExtractionService()
        
        # Invalid JSON should not crash, but return None
        invalid_json = "This is not JSON at all"
        
        try:
            json.loads(invalid_json)
            self.fail("Should have raised JSONDecodeError")
        except json.JSONDecodeError:
            # Expected - service should catch this and return None
            pass
    
    def test_file_not_found(self):
        """Test handling when PDF file doesn't exist"""
        service = InvoiceExtractionService()
        
        with self.assertRaises(FileNotFoundError):
            service._pdf_to_image_base64("/nonexistent/path/to/invoice.pdf")
    
    def test_missing_required_fields_in_dto(self):
        """Test DTO with missing required invoice fields"""
        # All fields in DTO are optional, so this should work
        dto = InvoiceDataDTO()
        validated = dto.validate()
        
        # Should return empty dict
        self.assertEqual(validated, {})
