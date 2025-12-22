"""
Tests for the recalc_availability management command.
"""

from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from io import StringIO
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag


class RecalcAvailabilityCommandTest(TestCase):
    """Tests for the recalc_availability management command."""
    
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
        
        # Create rental objects
        self.mietobjekt1 = MietObjekt.objects.create(
            name='Garage 1',
            type='GEBAEUDE',
            beschreibung='Eine schöne Garage',
            fläche=20.00,
            standort=self.standort,
            mietpreis=150.00,
            verfuegbar=True
        )
        
        self.mietobjekt2 = MietObjekt.objects.create(
            name='Garage 2',
            type='GEBAEUDE',
            beschreibung='Noch eine Garage',
            fläche=25.00,
            standort=self.standort,
            mietpreis=200.00,
            verfuegbar=True
        )
    
    def test_recalc_all_no_contracts(self):
        """Test recalculating with no contracts (all should stay available)."""
        out = StringIO()
        call_command('recalc_availability', stdout=out)
        
        # Both should still be available
        self.mietobjekt1.refresh_from_db()
        self.mietobjekt2.refresh_from_db()
        self.assertTrue(self.mietobjekt1.verfuegbar)
        self.assertTrue(self.mietobjekt2.verfuegbar)
        
        # Check output
        output = out.getvalue()
        self.assertIn('2 MietObjekt', output)
    
    def test_recalc_all_with_active_contract(self):
        """Test recalculating with an active contract."""
        # Create active contract for first MietObjekt
        yesterday = timezone.now().date() - timedelta(days=1)
        Vertrag.objects.create(
            mietobjekt=self.mietobjekt1,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Manually set to available (simulate inconsistent state)
        MietObjekt.objects.filter(pk=self.mietobjekt1.pk).update(verfuegbar=True)
        
        # Recalculate
        out = StringIO()
        call_command('recalc_availability', stdout=out)
        
        # First should be unavailable, second available
        self.mietobjekt1.refresh_from_db()
        self.mietobjekt2.refresh_from_db()
        self.assertFalse(self.mietobjekt1.verfuegbar)
        self.assertTrue(self.mietobjekt2.verfuegbar)
        
        # Check that one was updated
        output = out.getvalue()
        self.assertIn('1 of 2', output)
        self.assertIn('Garage 1', output)
    
    def test_recalc_specific_mietobjekt(self):
        """Test recalculating a specific MietObjekt."""
        # Create active contract for first MietObjekt
        yesterday = timezone.now().date() - timedelta(days=1)
        Vertrag.objects.create(
            mietobjekt=self.mietobjekt1,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Manually set to available (simulate inconsistent state)
        MietObjekt.objects.filter(pk=self.mietobjekt1.pk).update(verfuegbar=True)
        
        # Recalculate only first MietObjekt
        out = StringIO()
        call_command('recalc_availability', mietobjekt_id=self.mietobjekt1.pk, stdout=out)
        
        # First should be updated
        self.mietobjekt1.refresh_from_db()
        self.assertFalse(self.mietobjekt1.verfuegbar)
        
        # Check output
        output = out.getvalue()
        self.assertIn('Garage 1', output)
        self.assertIn('nicht verfügbar', output)
    
    def test_recalc_nonexistent_mietobjekt(self):
        """Test recalculating with a non-existent MietObjekt ID."""
        out = StringIO()
        call_command('recalc_availability', mietobjekt_id=9999, stdout=out)
        
        # Should show error message
        output = out.getvalue()
        self.assertIn('does not exist', output)
    
    def test_recalc_with_ended_contract(self):
        """Test recalculating with an ended contract."""
        # Create ended contract
        two_months_ago = timezone.now().date() - timedelta(days=60)
        last_month = timezone.now().date() - timedelta(days=30)
        Vertrag.objects.create(
            mietobjekt=self.mietobjekt1,
            mieter=self.kunde,
            start=two_months_ago,
            ende=last_month,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Manually set to unavailable (simulate inconsistent state)
        MietObjekt.objects.filter(pk=self.mietobjekt1.pk).update(verfuegbar=False)
        
        # Recalculate
        out = StringIO()
        call_command('recalc_availability', stdout=out)
        
        # Should be available (contract has ended)
        self.mietobjekt1.refresh_from_db()
        self.assertTrue(self.mietobjekt1.verfuegbar)
        
        # Check that one was updated
        output = out.getvalue()
        self.assertIn('1 of 2', output)
