"""
Tests for issue: Fehlerhafte Anzeige von Buchungen und Verfügbarkeiten bei Mietobjekten

This test verifies the fix for the bug where a MietObjekt with 1 available unit
and 1 rented unit showed 2 booked units instead of 1.

The bug was that when a Vertrag was created with the legacy mietobjekt field,
it automatically created a VertragsObjekt entry (for backward compatibility),
but then get_active_units_count() counted BOTH the VertragsObjekt AND the legacy
relationship, causing double counting.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from core.models import Adresse, Mandant
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt


class TestBookedUnitsDisplayBug(TestCase):
    """Test case for booked units display bug."""
    
    def setUp(self):
        """Set up test data."""
        # Create mandant
        self.mandant = Mandant.objects.create(
            name="Test Mandant",
            adresse="Teststr. 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland"
        )
        
        # Create location (Standort)
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Test Standort',
            strasse='Teststraße 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create customer (Kunde)
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Kundenstr. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create MietObjekt with only 1 available unit
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Container',
            type='CONTAINER',
            beschreibung='Test container with 1 unit',
            standort=self.standort,
            mietpreis=100.00,
            verfuegbare_einheiten=1,  # Only 1 unit available
            mandant=self.mandant
        )
    
    def test_single_unit_rented_via_legacy_field(self):
        """
        Test that when a MietObjekt with 1 unit is rented via legacy field,
        it correctly shows 1 booked unit (not 2).
        
        This test verifies the fix for the double-counting bug.
        """
        # Create a contract using the legacy mietobjekt field
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,  # Using legacy field
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=100.00,
            kaution=300.00,
            status='active'
        )
        
        # The save() method automatically creates a VertragsObjekt entry
        # for backward compatibility
        
        # Check that VertragsObjekt was created
        vertragsobjekte_count = VertragsObjekt.objects.filter(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt
        ).count()
        self.assertEqual(vertragsobjekte_count, 1)
        
        # Verify the fix: should return 1, not 2
        active_units = self.mietobjekt.get_active_units_count()
        self.assertEqual(active_units, 1, 
                        f"Expected 1 booked unit, but got {active_units}. "
                        f"The fix should prevent double-counting.")
        
        # Check available units
        available_units = self.mietobjekt.get_available_units_count()
        self.assertEqual(available_units, 0,
                        f"Expected 0 available units, but got {available_units}")
    
    def test_single_unit_rented_via_vertragsobjekt(self):
        """
        Test that when a contract is created via VertragsObjekt (without legacy field),
        the count is correct.
        """
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Create contract WITHOUT legacy mietobjekt field
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=100.00,
            kaution=300.00,
            status='active'
        )
        
        # Create VertragsObjekt with anzahl=1
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=1,
            preis=100.00
        )
        
        # Check active units count
        active_units = self.mietobjekt.get_active_units_count()
        self.assertEqual(active_units, 1)
        
        # Check available units
        available_units = self.mietobjekt.get_available_units_count()
        self.assertEqual(available_units, 0)
