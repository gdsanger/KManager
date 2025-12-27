"""
Tests for VertragsObjekt model and n:m relationship between Vertrag and MietObjekt.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt


class VertragsObjektModelTest(TestCase):
    """Tests for VertragsObjekt model functionality."""
    
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
        
        # Create a location address
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstrasse 3',
            plz='11111',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        # Create multiple rental objects
        self.mietobjekt1 = MietObjekt.objects.create(
            name='Wohnung 1',
            type='RAUM',
            beschreibung='Kleine Wohnung',
            fläche=50.00,
            standort=self.standort,
            mietpreis=500.00,
            kaution=1500.00,
            verfuegbar=True
        )
        
        self.mietobjekt2 = MietObjekt.objects.create(
            name='Stellplatz 1',
            type='STELLPLATZ',
            beschreibung='Parkplatz',
            fläche=12.00,
            standort=self.standort,
            mietpreis=50.00,
            kaution=150.00,
            verfuegbar=True
        )
        
        self.mietobjekt3 = MietObjekt.objects.create(
            name='Keller 1',
            type='RAUM',
            beschreibung='Kellerraum',
            fläche=10.00,
            standort=self.standort,
            mietpreis=30.00,
            kaution=90.00,
            verfuegbar=True
        )
    
    def test_create_vertrag_with_single_mietobjekt(self):
        """Test creating a contract with a single rental object."""
        # Create contract
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Add mietobjekt via VertragsObjekt
        vertragsobjekt = VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt1
        )
        
        # Verify relationship
        self.assertEqual(vertrag.vertragsobjekte.count(), 1)
        self.assertEqual(vertrag.get_mietobjekte().count(), 1)
        self.assertIn(self.mietobjekt1, vertrag.get_mietobjekte())
    
    def test_create_vertrag_with_multiple_mietobjekte(self):
        """Test creating a contract with multiple rental objects."""
        # Create contract
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('580.00'),
            kaution=Decimal('1740.00'),
            status='active'
        )
        
        # Add multiple mietobjekte
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt1)
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt2)
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt3)
        
        # Verify relationships
        self.assertEqual(vertrag.vertragsobjekte.count(), 3)
        self.assertEqual(vertrag.get_mietobjekte().count(), 3)
        self.assertIn(self.mietobjekt1, vertrag.get_mietobjekte())
        self.assertIn(self.mietobjekt2, vertrag.get_mietobjekte())
        self.assertIn(self.mietobjekt3, vertrag.get_mietobjekte())
    
    def test_duplicate_mietobjekt_in_same_vertrag_fails(self):
        """Test that adding the same mietobjekt twice to a contract fails."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Add mietobjekt once
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt1)
        
        # Try to add same mietobjekt again - should fail due to unique_together
        with self.assertRaises(Exception):  # IntegrityError
            VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt1)
    
    def test_mietobjekt_in_two_active_contracts_fails(self):
        """Test that a mietobjekt cannot be in two active contracts at the same time."""
        today = timezone.now().date()
        
        # Create first active contract
        vertrag1 = Vertrag.objects.create(
            mieter=self.kunde,
            start=today - timedelta(days=10),
            ende=None,  # Open-ended
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        VertragsObjekt.objects.create(vertrag=vertrag1, mietobjekt=self.mietobjekt1)
        
        # Try to create second active contract with same mietobjekt
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde,
            start=today,
            ende=None,
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Should raise ValidationError when trying to add same mietobjekt
        with self.assertRaises(ValidationError) as context:
            VertragsObjekt.objects.create(vertrag=vertrag2, mietobjekt=self.mietobjekt1)
        
        # Error message should mention insufficient units
        self.assertIn('Nicht genügend Einheiten verfügbar', str(context.exception))
    
    def test_mietobjekt_in_ended_and_new_contract_succeeds(self):
        """Test that a mietobjekt can be in an ended contract and a new contract."""
        today = timezone.now().date()
        
        # Create ended contract
        vertrag1 = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='ended'
        )
        VertragsObjekt.objects.create(vertrag=vertrag1, mietobjekt=self.mietobjekt1)
        
        # Create new active contract with same mietobjekt - should succeed
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde,
            start=today,
            ende=None,
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        vertragsobjekt2 = VertragsObjekt.objects.create(
            vertrag=vertrag2,
            mietobjekt=self.mietobjekt1
        )
        
        # Should succeed
        self.assertEqual(vertragsobjekt2.mietobjekt, self.mietobjekt1)
    
    def test_mietobjekt_in_draft_and_active_contract_succeeds(self):
        """Test that a mietobjekt can be in a draft contract and an active contract."""
        today = timezone.now().date()
        
        # Create draft contract
        vertrag1 = Vertrag.objects.create(
            mieter=self.kunde,
            start=today,
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='draft'
        )
        VertragsObjekt.objects.create(vertrag=vertrag1, mietobjekt=self.mietobjekt1)
        
        # Create active contract with same mietobjekt - should succeed
        # because draft contracts don't affect availability
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde,
            start=today,
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        vertragsobjekt2 = VertragsObjekt.objects.create(
            vertrag=vertrag2,
            mietobjekt=self.mietobjekt1
        )
        
        # Should succeed
        self.assertEqual(vertragsobjekt2.mietobjekt, self.mietobjekt1)
    
    def test_availability_update_with_multiple_objects(self):
        """Test that availability is correctly updated when contract has multiple objects."""
        today = timezone.now().date()
        
        # All objects should be available initially
        self.assertTrue(self.mietobjekt1.verfuegbar)
        self.assertTrue(self.mietobjekt2.verfuegbar)
        self.assertTrue(self.mietobjekt3.verfuegbar)
        
        # Create active contract with multiple objects
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=today - timedelta(days=1),
            ende=None,
            miete=Decimal('580.00'),
            kaution=Decimal('1740.00'),
            status='active'
        )
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt1)
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt2)
        
        # Update availability
        self.mietobjekt1.update_availability()
        self.mietobjekt2.update_availability()
        self.mietobjekt3.update_availability()
        
        # Objects in contract should be unavailable
        self.mietobjekt1.refresh_from_db()
        self.mietobjekt2.refresh_from_db()
        self.mietobjekt3.refresh_from_db()
        
        self.assertFalse(self.mietobjekt1.verfuegbar)
        self.assertFalse(self.mietobjekt2.verfuegbar)
        self.assertTrue(self.mietobjekt3.verfuegbar)  # Not in contract
    
    def test_vertrag_str_with_multiple_objects(self):
        """Test string representation of Vertrag with multiple objects."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=Decimal('580.00'),
            kaution=Decimal('1740.00'),
            status='active'
        )
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt1)
        VertragsObjekt.objects.create(vertrag=vertrag, mietobjekt=self.mietobjekt2)
        
        # Should show first object + count of additional objects
        vertrag_str = str(vertrag)
        self.assertIn('Wohnung 1', vertrag_str)
        self.assertIn('+1 weitere', vertrag_str)
    
    def test_mietobjekt_historical_contracts(self):
        """Test that a mietobjekt can have multiple contracts over time (history)."""
        # Create three contracts over time
        vertrag1 = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2022, 1, 1),
            ende=date(2022, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='ended'
        )
        VertragsObjekt.objects.create(vertrag=vertrag1, mietobjekt=self.mietobjekt1)
        
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='ended'
        )
        VertragsObjekt.objects.create(vertrag=vertrag2, mietobjekt=self.mietobjekt1)
        
        vertrag3 = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        VertragsObjekt.objects.create(vertrag=vertrag3, mietobjekt=self.mietobjekt1)
        
        # Verify mietobjekt has three contracts in history
        contracts_count = VertragsObjekt.objects.filter(
            mietobjekt=self.mietobjekt1
        ).count()
        self.assertEqual(contracts_count, 3)
