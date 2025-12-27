"""
Tests for multiple units and volume functionality.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt


class MultipleUnitsTest(TestCase):
    """Tests for multiple units availability management."""
    
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
        
        # Create another customer
        self.kunde2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Anna Schmidt',
            strasse='Beispielweg 5',
            plz='54321',
            ort='Beispielstadt',
            land='Deutschland',
            email='anna@example.com'
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
        
        # Create a rental object with 3 available units
        self.mietobjekt = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            fläche=10.00,
            standort=self.standort,
            mietpreis=100.00,
            verfuegbare_einheiten=3,
            verfuegbar=True
        )
    
    def test_default_verfuegbare_einheiten(self):
        """Test that default verfuegbare_einheiten is 1."""
        obj = MietObjekt.objects.create(
            name='Einzelobjekt',
            type='RAUM',
            beschreibung='Ein Raum',
            standort=self.standort,
            mietpreis=200.00
        )
        self.assertEqual(obj.verfuegbare_einheiten, 1)
    
    def test_get_active_units_count_zero(self):
        """Test that get_active_units_count returns 0 when no active contracts."""
        count = self.mietobjekt.get_active_units_count()
        self.assertEqual(count, 0)
    
    def test_get_active_units_count_single_contract(self):
        """Test get_active_units_count with a single active contract."""
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=100.00,
            kaution=300.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=2,
            preis=100.00
        )
        
        count = self.mietobjekt.get_active_units_count()
        self.assertEqual(count, 2)
    
    def test_get_active_units_count_multiple_contracts(self):
        """Test get_active_units_count with multiple active contracts."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # First contract with 1 unit
        vertrag1 = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=100.00,
            kaution=300.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag1,
            mietobjekt=self.mietobjekt,
            anzahl=1,
            preis=100.00
        )
        
        # Second contract with 2 units
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde2,
            start=yesterday,
            ende=None,
            miete=200.00,
            kaution=600.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag2,
            mietobjekt=self.mietobjekt,
            anzahl=2,
            preis=100.00
        )
        
        count = self.mietobjekt.get_active_units_count()
        self.assertEqual(count, 3)
    
    def test_has_active_contracts_with_units(self):
        """Test has_active_contracts returns True when all units are rented."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Rent all 3 units
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=300.00,
            kaution=900.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=3,
            preis=100.00
        )
        
        self.assertTrue(self.mietobjekt.has_active_contracts())
    
    def test_has_active_contracts_with_partial_units(self):
        """Test has_active_contracts returns False when some units are still available."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Rent only 2 out of 3 units
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=200.00,
            kaution=600.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=2,
            preis=100.00
        )
        
        self.assertFalse(self.mietobjekt.has_active_contracts())
    
    def test_availability_update_with_partial_units(self):
        """Test that availability is updated correctly with partial units."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Initially available
        self.assertTrue(self.mietobjekt.verfuegbar)
        
        # Rent 2 out of 3 units
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=200.00,
            kaution=600.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=2,
            preis=100.00
        )
        
        # Should still be available (1 unit left)
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
    
    def test_availability_update_with_all_units(self):
        """Test that availability becomes False when all units are rented."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Rent all 3 units
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=300.00,
            kaution=900.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=3,
            preis=100.00
        )
        
        # Should be unavailable (all units rented)
        self.mietobjekt.refresh_from_db()
        self.assertFalse(self.mietobjekt.verfuegbar)
    
    def test_validation_insufficient_units(self):
        """Test that validation fails when trying to rent more units than available."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # First rent 2 units
        vertrag1 = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=200.00,
            kaution=600.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag1,
            mietobjekt=self.mietobjekt,
            anzahl=2,
            preis=100.00
        )
        
        # Try to rent 2 more units (should fail, only 1 available)
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde2,
            start=yesterday,
            ende=None,
            miete=200.00,
            kaution=600.00,
            status='active'
        )
        
        with self.assertRaises(ValidationError) as cm:
            VertragsObjekt.objects.create(
                vertrag=vertrag2,
                mietobjekt=self.mietobjekt,
                anzahl=2,
                preis=100.00
            )
        
        self.assertIn('anzahl', cm.exception.message_dict)
        self.assertIn('Nicht genügend Einheiten verfügbar', str(cm.exception))
    
    def test_validation_exact_remaining_units(self):
        """Test that validation passes when renting exact remaining units."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # First rent 2 units
        vertrag1 = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=200.00,
            kaution=600.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag1,
            mietobjekt=self.mietobjekt,
            anzahl=2,
            preis=100.00
        )
        
        # Rent the last unit (should succeed)
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde2,
            start=yesterday,
            ende=None,
            miete=100.00,
            kaution=300.00,
            status='active'
        )
        vo = VertragsObjekt.objects.create(
            vertrag=vertrag2,
            mietobjekt=self.mietobjekt,
            anzahl=1,
            preis=100.00
        )
        
        self.assertEqual(vo.anzahl, 1)
    
    def test_draft_contracts_dont_block_units(self):
        """Test that draft contracts don't count toward active units."""
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Create draft contract with 3 units
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=300.00,
            kaution=900.00,
            status='draft'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=3,
            preis=100.00
        )
        
        # Should still show 0 active units
        count = self.mietobjekt.get_active_units_count()
        self.assertEqual(count, 0)
        
        # Should still be available
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
    
    def test_future_contracts_dont_block_units(self):
        """Test that future contracts don't count toward current active units."""
        next_month = timezone.now().date() + timedelta(days=30)
        
        # Create future contract with 3 units
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=next_month,
            ende=None,
            miete=300.00,
            kaution=900.00,
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=3,
            preis=100.00
        )
        
        # Should still show 0 active units (contract hasn't started yet)
        count = self.mietobjekt.get_active_units_count()
        self.assertEqual(count, 0)


class VolumeCalculationTest(TestCase):
    """Tests for volume calculation functionality."""
    
    def setUp(self):
        """Set up test data for all tests."""
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstrasse 3',
            plz='11111',
            ort='Standortstadt',
            land='Deutschland'
        )
    
    def test_volumen_berechnet_with_all_dimensions(self):
        """Test that volumen_berechnet calculates correctly when all dimensions are provided."""
        obj = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            höhe=Decimal('2.5'),
            breite=Decimal('2.0'),
            tiefe=Decimal('6.0'),
            standort=self.standort,
            mietpreis=100.00
        )
        
        # Volume should be 2.5 * 2.0 * 6.0 = 30.000 m³
        expected = Decimal('30.000')
        self.assertEqual(obj.volumen_berechnet, expected)
    
    def test_volumen_berechnet_with_missing_dimension(self):
        """Test that volumen_berechnet returns None when a dimension is missing."""
        obj = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            höhe=Decimal('2.5'),
            breite=Decimal('2.0'),
            # tiefe is missing
            standort=self.standort,
            mietpreis=100.00
        )
        
        self.assertIsNone(obj.volumen_berechnet)
    
    def test_volumen_berechnet_with_zero_dimension(self):
        """Test that volumen_berechnet returns None when a dimension is zero."""
        obj = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            höhe=Decimal('2.5'),
            breite=Decimal('0'),
            tiefe=Decimal('6.0'),
            standort=self.standort,
            mietpreis=100.00
        )
        
        self.assertIsNone(obj.volumen_berechnet)
    
    def test_get_volumen_uses_calculated(self):
        """Test that get_volumen returns calculated value when volumen is not set."""
        obj = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            höhe=Decimal('2.5'),
            breite=Decimal('2.0'),
            tiefe=Decimal('6.0'),
            standort=self.standort,
            mietpreis=100.00
        )
        
        # volumen field is not set, should return calculated
        expected = Decimal('30.000')
        self.assertEqual(obj.get_volumen(), expected)
    
    def test_get_volumen_uses_override(self):
        """Test that get_volumen returns overridden value when volumen is set."""
        obj = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            höhe=Decimal('2.5'),
            breite=Decimal('2.0'),
            tiefe=Decimal('6.0'),
            standort=self.standort,
            mietpreis=100.00,
            volumen=Decimal('35.500')  # Override with a different value
        )
        
        # Should return overridden value
        self.assertEqual(obj.get_volumen(), Decimal('35.500'))
        
        # Calculated should still show the calculated value
        self.assertEqual(obj.volumen_berechnet, Decimal('30.000'))
    
    def test_volumen_precision(self):
        """Test that volumen is rounded to 3 decimal places."""
        obj = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            höhe=Decimal('2.333'),
            breite=Decimal('1.777'),
            tiefe=Decimal('5.555'),
            standort=self.standort,
            mietpreis=100.00
        )
        
        # Calculate: 2.333 * 1.777 * 5.555 = 23.035...
        result = obj.volumen_berechnet
        
        # Should be rounded to 3 decimal places
        self.assertEqual(result.as_tuple().exponent, -3)
    
    def test_volumen_override_can_be_cleared(self):
        """Test that volumen override can be cleared to use calculated value."""
        obj = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Standard Container',
            höhe=Decimal('2.5'),
            breite=Decimal('2.0'),
            tiefe=Decimal('6.0'),
            standort=self.standort,
            mietpreis=100.00,
            volumen=Decimal('35.500')
        )
        
        # Initially uses override
        self.assertEqual(obj.get_volumen(), Decimal('35.500'))
        
        # Clear override
        obj.volumen = None
        obj.save()
        
        # Should now use calculated
        self.assertEqual(obj.get_volumen(), Decimal('30.000'))
