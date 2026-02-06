"""
Tests for Adresse model tax and accounting fields.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import Adresse


class AdresseTaxFieldsTestCase(TestCase):
    """Test case for Adresse tax and accounting fields."""
    
    def test_country_code_validation_uppercase(self):
        """Test that country_code is normalized to uppercase."""
        adresse = Adresse(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            country_code='de'  # lowercase
        )
        adresse.full_clean()  # This triggers clean()
        self.assertEqual(adresse.country_code, 'DE')
    
    def test_country_code_validation_length(self):
        """Test that country_code must be exactly 2 characters."""
        adresse = Adresse(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            country_code='DEU'  # 3 characters - invalid
        )
        with self.assertRaises(ValidationError) as context:
            adresse.full_clean()
        
        self.assertIn('country_code', context.exception.message_dict)
    
    def test_country_code_validation_whitespace(self):
        """Test that country_code whitespace is trimmed on save."""
        adresse = Adresse(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            country_code=' AT '  # with whitespace
        )
        # Save should normalize it
        adresse.save()
        adresse.refresh_from_db()
        self.assertEqual(adresse.country_code, 'AT')
    
    def test_vat_id_normalization_uppercase(self):
        """Test that vat_id is normalized to uppercase."""
        adresse = Adresse(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            vat_id='de123456789'  # lowercase
        )
        adresse.full_clean()
        self.assertEqual(adresse.vat_id, 'DE123456789')
    
    def test_vat_id_normalization_whitespace(self):
        """Test that vat_id whitespace is trimmed."""
        adresse = Adresse(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            vat_id=' DE123456789 '  # with whitespace
        )
        adresse.full_clean()
        self.assertEqual(adresse.vat_id, 'DE123456789')
    
    def test_vat_id_optional(self):
        """Test that vat_id is optional."""
        adresse = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            vat_id=None
        )
        self.assertIsNone(adresse.vat_id)
        
        # Also test empty string
        adresse2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde 2',
            strasse='Teststrasse 2',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            vat_id=''
        )
        self.assertEqual(adresse2.vat_id, '')
    
    def test_is_eu_default_false(self):
        """Test that is_eu defaults to False."""
        adresse = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        self.assertFalse(adresse.is_eu)
    
    def test_is_business_default_true(self):
        """Test that is_business defaults to True."""
        adresse = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        self.assertTrue(adresse.is_business)
    
    def test_debitor_number_optional(self):
        """Test that debitor_number is optional."""
        adresse = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            debitor_number=None
        )
        self.assertIsNone(adresse.debitor_number)
    
    def test_all_tax_fields_together(self):
        """Test creating address with all tax and accounting fields."""
        adresse = Adresse.objects.create(
            adressen_type='KUNDE',
            firma='Test GmbH',
            name='Test Manager',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            country_code='DE',
            vat_id='DE123456789',
            is_eu=True,
            is_business=True,
            debitor_number='DEB-2024-001'
        )
        
        self.assertEqual(adresse.country_code, 'DE')
        self.assertEqual(adresse.vat_id, 'DE123456789')
        self.assertTrue(adresse.is_eu)
        self.assertTrue(adresse.is_business)
        self.assertEqual(adresse.debitor_number, 'DEB-2024-001')
    
    def test_country_code_default_value(self):
        """Test that country_code has a default value of 'DE'."""
        adresse = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        self.assertEqual(adresse.country_code, 'DE')
