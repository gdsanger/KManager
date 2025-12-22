from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag


class VertragModelTest(TestCase):
    """Tests for the Vertrag (Contract) model."""
    
    def setUp(self):
        """Set up test data for all tests."""
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
        
        # Create a non-customer address
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant GmbH',
            strasse='Lieferstrasse 2',
            plz='54321',
            ort='Lieferstadt',
            land='Deutschland'
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
            mietpreis=150.00,
            verfuegbar=True
        )
        
        # Create another rental object
        self.mietobjekt2 = MietObjekt.objects.create(
            name='Garage 2',
            type='GEBAEUDE',
            beschreibung='Noch eine Garage',
            fläche=25.00,
            standort=self.standort,
            mietpreis=200.00,
            verfuegbar=True
        )
    
    def test_vertragsnummer_auto_generation(self):
        """Test that contract numbers are auto-generated in the correct format."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        self.assertEqual(vertrag.vertragsnummer, 'V-00001')
    
    def test_vertragsnummer_sequential(self):
        """Test that contract numbers are generated sequentially."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde,
            start=date(2025, 1, 1),
            ende=date(2025, 12, 31),
            miete=200.00,
            kaution=600.00
        )
        self.assertEqual(vertrag1.vertragsnummer, 'V-00001')
        self.assertEqual(vertrag2.vertragsnummer, 'V-00002')
    
    def test_vertragsnummer_unique(self):
        """Test that contract numbers are unique."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        # Try to create a second contract - should get a different number
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde,
            start=date(2025, 1, 1),
            miete=200.00,
            kaution=600.00
        )
        self.assertNotEqual(vertrag1.vertragsnummer, vertrag2.vertragsnummer)
    
    def test_start_is_required(self):
        """Test that start date is required."""
        with self.assertRaises(ValidationError):
            vertrag = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                # start is missing
                miete=150.00,
                kaution=450.00
            )
            vertrag.full_clean()
    
    def test_ende_is_optional(self):
        """Test that ende (end date) is optional (NULL allowed)."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            # ende is None (optional)
            miete=150.00,
            kaution=450.00
        )
        self.assertIsNone(vertrag.ende)
        self.assertEqual(vertrag.vertragsnummer, 'V-00001')
    
    def test_ende_must_be_after_start(self):
        """Test that ende must be greater than start if set."""
        with self.assertRaises(ValidationError) as context:
            vertrag = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2024, 12, 31),
                ende=date(2024, 1, 1),  # ende before start
                miete=150.00,
                kaution=450.00
            )
            vertrag.full_clean()
        
        self.assertIn('ende', context.exception.error_dict)
    
    def test_ende_equal_to_start_invalid(self):
        """Test that ende equal to start is invalid."""
        with self.assertRaises(ValidationError) as context:
            vertrag = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2024, 1, 1),
                ende=date(2024, 1, 1),  # same as start
                miete=150.00,
                kaution=450.00
            )
            vertrag.full_clean()
        
        self.assertIn('ende', context.exception.error_dict)
    
    def test_mieter_relationship(self):
        """Test the relationship between Vertrag and Adresse (Mieter)."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        self.assertEqual(vertrag.mieter, self.kunde)
        self.assertEqual(vertrag.mieter.adressen_type, 'KUNDE')
    
    def test_mietobjekt_relationship(self):
        """Test the relationship between Vertrag and MietObjekt."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        self.assertEqual(vertrag.mietobjekt, self.mietobjekt)
        # Test reverse relationship
        self.assertIn(vertrag, self.mietobjekt.vertraege.all())
    
    def test_multiple_contracts_for_same_mietobjekt(self):
        """Test that a MietObjekt can have multiple contracts (history)."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=160.00,
            kaution=480.00
        )
        contracts = self.mietobjekt.vertraege.all()
        self.assertEqual(contracts.count(), 2)
        self.assertIn(vertrag1, contracts)
        self.assertIn(vertrag2, contracts)
    
    def test_overlapping_contracts_with_end_dates(self):
        """Test that overlapping contracts are prevented."""
        # Create first contract
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Try to create overlapping contract
        with self.assertRaises(ValidationError):
            vertrag2 = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2024, 6, 1),  # overlaps with vertrag1
                ende=date(2025, 6, 1),
                miete=150.00,
                kaution=450.00
            )
            vertrag2.save()
    
    def test_open_ended_contract_blocks_future_contracts(self):
        """Test that an open-ended contract (ende=NULL) blocks future contracts."""
        # Create open-ended contract
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            # ende is None (open-ended)
            miete=150.00,
            kaution=450.00
        )
        
        # Try to create a contract starting after the open-ended one
        with self.assertRaises(ValidationError):
            vertrag2 = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2025, 1, 1),
                ende=date(2025, 12, 31),
                miete=150.00,
                kaution=450.00
            )
            vertrag2.save()
    
    def test_non_overlapping_contracts_allowed(self):
        """Test that non-overlapping (adjacent) contracts are allowed."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Create adjacent/non-overlapping contract (starts day after first ends)
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=160.00,
            kaution=480.00
        )
        
        self.assertEqual(Vertrag.objects.filter(mietobjekt=self.mietobjekt).count(), 2)
    
    def test_different_mietobjekt_no_conflict(self):
        """Test that contracts for different MietObjekt don't conflict."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Same dates but different MietObjekt - should be allowed
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=200.00,
            kaution=600.00
        )
        
        self.assertEqual(Vertrag.objects.count(), 2)
    
    def test_decimal_fields_miete_kaution(self):
        """Test that miete and kaution are decimal fields."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.50,
            kaution=451.50
        )
        self.assertEqual(float(vertrag.miete), 150.50)
        self.assertEqual(float(vertrag.kaution), 451.50)
    
    def test_str_representation(self):
        """Test the string representation of Vertrag."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        expected = f"V-00001 - Garage 1 (Max Mustermann)"
        self.assertEqual(str(vertrag), expected)
    
    def test_open_ended_after_finished_contract(self):
        """Test that an open-ended contract can be created after a finished contract."""
        # Create a contract that has ended
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Create an open-ended contract starting after the first one ends
        # This should be allowed
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),  # Starts after vertrag1 ends
            ende=None,  # Open-ended
            miete=160.00,
            kaution=480.00
        )
        
        self.assertEqual(Vertrag.objects.filter(mietobjekt=self.mietobjekt).count(), 2)
        self.assertIsNone(vertrag2.ende)
