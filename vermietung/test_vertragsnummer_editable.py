"""
Tests for Vertragsnummer editability feature.
Tests that vertragsnummer can be manually set or auto-generated,
and that uniqueness is enforced globally.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag


class VertragsnummerEditableTestCase(TestCase):
    """Test case for vertragsnummer editability."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create test standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Hauptstadt',
            land='Deutschland'
        )
        
        # Create test customer
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        # Create test mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Kleines Büro',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbar=True
        )
    
    def test_create_contract_without_vertragsnummer_auto_generates(self):
        """Test that creating a contract without vertragsnummer auto-generates one."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Should auto-generate vertragsnummer
        self.assertIsNotNone(vertrag.vertragsnummer)
        self.assertTrue(vertrag.vertragsnummer.startswith('V-'))
        self.assertEqual(len(vertrag.vertragsnummer), 7)  # V-00001
    
    def test_create_contract_with_custom_vertragsnummer(self):
        """Test that creating a contract with a custom vertragsnummer uses it."""
        custom_number = '2026-0001'
        vertrag = Vertrag.objects.create(
            vertragsnummer=custom_number,
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Should use the custom vertragsnummer
        self.assertEqual(vertrag.vertragsnummer, custom_number)
    
    def test_create_contract_with_empty_string_vertragsnummer_auto_generates(self):
        """Test that creating a contract with empty string vertragsnummer auto-generates one."""
        vertrag = Vertrag.objects.create(
            vertragsnummer='',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Should auto-generate vertragsnummer when empty string is provided
        self.assertIsNotNone(vertrag.vertragsnummer)
        self.assertTrue(vertrag.vertragsnummer.startswith('V-'))
        self.assertNotEqual(vertrag.vertragsnummer, '')
    
    def test_update_contract_preserves_vertragsnummer(self):
        """Test that updating a contract does not regenerate vertragsnummer."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        original_number = vertrag.vertragsnummer
        
        # Update the contract
        vertrag.miete = Decimal('600.00')
        vertrag.save()
        
        # Vertragsnummer should not change
        self.assertEqual(vertrag.vertragsnummer, original_number)
    
    def test_update_contract_can_change_vertragsnummer(self):
        """Test that updating a contract can change its vertragsnummer."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        original_number = vertrag.vertragsnummer
        new_number = '2026-0100'
        
        # Update vertragsnummer
        vertrag.vertragsnummer = new_number
        vertrag.save()
        
        # Vertragsnummer should be updated
        vertrag.refresh_from_db()
        self.assertEqual(vertrag.vertragsnummer, new_number)
        self.assertNotEqual(vertrag.vertragsnummer, original_number)
    
    def test_duplicate_vertragsnummer_raises_integrity_error(self):
        """Test that duplicate vertragsnummer is rejected."""
        # Create first contract
        vertrag1 = Vertrag.objects.create(
            vertragsnummer='TEST-001',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Create second mietobjekt for second contract
        mietobjekt2 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Großes Büro',
            standort=self.standort,
            mietpreis=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            verfuegbar=True
        )
        
        # Try to create second contract with same vertragsnummer
        # Django raises ValidationError (via full_clean) before IntegrityError
        with self.assertRaises((IntegrityError, ValidationError)):
            Vertrag.objects.create(
                vertragsnummer='TEST-001',  # Same as vertrag1
                mietobjekt=mietobjekt2,
                mieter=self.kunde,
                start=date(2024, 1, 1),
                ende=date(2024, 12, 31),
                miete=Decimal('800.00'),
                kaution=Decimal('2400.00'),
                status='active'
            )
    
    def test_update_to_duplicate_vertragsnummer_raises_integrity_error(self):
        """Test that updating to a duplicate vertragsnummer is rejected."""
        # Create first contract
        vertrag1 = Vertrag.objects.create(
            vertragsnummer='TEST-001',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Create second mietobjekt and contract
        mietobjekt2 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Großes Büro',
            standort=self.standort,
            mietpreis=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            verfuegbar=True
        )
        
        vertrag2 = Vertrag.objects.create(
            vertragsnummer='TEST-002',
            mietobjekt=mietobjekt2,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            status='active'
        )
        
        # Try to update vertrag2 to have same number as vertrag1
        # Django raises ValidationError (via full_clean) before IntegrityError
        with self.assertRaises((IntegrityError, ValidationError)):
            vertrag2.vertragsnummer = 'TEST-001'
            vertrag2.save()
    
    def test_sequential_auto_generation(self):
        """Test that auto-generated vertragsnummern are sequential."""
        # Create first contract
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Create second mietobjekt
        mietobjekt2 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Großes Büro',
            standort=self.standort,
            mietpreis=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            verfuegbar=True
        )
        
        # Create second contract
        vertrag2 = Vertrag.objects.create(
            mietobjekt=mietobjekt2,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            status='active'
        )
        
        # Extract numbers from vertragsnummern
        num1 = int(vertrag1.vertragsnummer.split('-')[1])
        num2 = int(vertrag2.vertragsnummer.split('-')[1])
        
        # Second number should be one more than first
        self.assertEqual(num2, num1 + 1)
    
    def test_mixed_auto_and_manual_vertragsnummern(self):
        """Test creating contracts with both auto and manual vertragsnummern."""
        # Create contract with auto-generated number
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Create second mietobjekt
        mietobjekt2 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Großes Büro',
            standort=self.standort,
            mietpreis=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            verfuegbar=True
        )
        
        # Create contract with manual number
        vertrag2 = Vertrag.objects.create(
            vertragsnummer='2026-0001',
            mietobjekt=mietobjekt2,
            mieter=self.kunde,
            start=date(2024, 2, 1),
            miete=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            status='active'
        )
        
        # Create third mietobjekt
        mietobjekt3 = MietObjekt.objects.create(
            name='Büro 3',
            type='RAUM',
            beschreibung='Mittleres Büro',
            standort=self.standort,
            mietpreis=Decimal('650.00'),
            kaution=Decimal('1950.00'),
            verfuegbar=True
        )
        
        # Create contract with auto-generated number again
        vertrag3 = Vertrag.objects.create(
            mietobjekt=mietobjekt3,
            mieter=self.kunde,
            start=date(2024, 3, 1),
            miete=Decimal('650.00'),
            kaution=Decimal('1950.00'),
            status='active'
        )
        
        # Verify all have unique numbers
        numbers = [vertrag1.vertragsnummer, vertrag2.vertragsnummer, vertrag3.vertragsnummer]
        self.assertEqual(len(numbers), len(set(numbers)))  # All unique
        
        # Verify second one has manual number
        self.assertEqual(vertrag2.vertragsnummer, '2026-0001')
        
        # Verify first and third have auto-generated format
        self.assertTrue(vertrag1.vertragsnummer.startswith('V-'))
        self.assertTrue(vertrag3.vertragsnummer.startswith('V-'))
