"""
Tests for the automatic availability management functionality.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag


class AvailabilityManagementTest(TestCase):
    """Tests for automatic availability management based on contract status."""
    
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
    
    def test_active_contract_makes_unavailable(self):
        """Test that an active contract makes the MietObjekt unavailable."""
        # Initially available
        self.assertTrue(self.mietobjekt.verfuegbar)
        
        # Create an active contract that started yesterday
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=yesterday,
            ende=None,  # Open-ended
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Reload MietObjekt from database
        self.mietobjekt.refresh_from_db()
        
        # Should now be unavailable
        self.assertFalse(self.mietobjekt.verfuegbar)
    
    def test_ended_contract_makes_available(self):
        """Test that ending a contract makes the MietObjekt available again."""
        # Create an active contract
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Should be unavailable
        self.mietobjekt.refresh_from_db()
        self.assertFalse(self.mietobjekt.verfuegbar)
        
        # End the contract
        vertrag.status = 'ended'
        vertrag.save()
        
        # Should be available again
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
    
    def test_future_contract_keeps_available(self):
        """Test that a future contract doesn't affect current availability."""
        # Create a contract starting next month
        next_month = timezone.now().date() + timedelta(days=30)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=next_month,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Should still be available (contract hasn't started yet)
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
    
    def test_past_contract_makes_available(self):
        """Test that a contract that has ended makes the MietObjekt available."""
        # Create a contract that ended last month
        two_months_ago = timezone.now().date() - timedelta(days=60)
        last_month = timezone.now().date() - timedelta(days=30)
        
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=two_months_ago,
            ende=last_month,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Should be available (contract has ended)
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
    
    def test_draft_contract_doesnt_affect_availability(self):
        """Test that a draft contract doesn't make the MietObjekt unavailable."""
        # Create a draft contract
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='draft'
        )
        
        # Should still be available
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
    
    def test_cancelled_contract_doesnt_affect_availability(self):
        """Test that a cancelled contract doesn't make the MietObjekt unavailable."""
        # Create a cancelled contract
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='cancelled'
        )
        
        # Should still be available
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
    
    def test_is_currently_active_method(self):
        """Test the is_currently_active method."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Active contract that started yesterday
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        self.assertTrue(vertrag1.is_currently_active())
        
        # Active contract starting tomorrow (not yet active)
        # Note: Creating as draft to avoid overlap validation, then checking in-memory object
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=tomorrow,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='draft'  # Use draft to avoid overlap validation
        )
        # Check in-memory object with status changed (not saved)
        vertrag2.status = 'active'
        vertrag2.start = tomorrow  # Still in the future
        self.assertFalse(vertrag2.is_currently_active())
        
        # Ended contract (check in-memory)
        vertrag1.status = 'ended'
        self.assertFalse(vertrag1.is_currently_active())
    
    def test_no_overlap_for_non_active_contracts(self):
        """Test that overlap validation doesn't apply to non-active contracts."""
        # Create an active contract
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Create a draft contract with overlapping dates - should be allowed
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 6, 1),
            ende=date(2025, 6, 1),
            miete=150.00,
            kaution=450.00,
            status='draft'
        )
        
        # Should succeed without raising ValidationError
        self.assertEqual(Vertrag.objects.filter(mietobjekt=self.mietobjekt).count(), 2)
    
    def test_overlap_validation_for_active_contracts(self):
        """Test that overlap validation works for active contracts."""
        # Create an active contract
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Try to create another active contract with overlapping dates
        with self.assertRaises(ValidationError):
            vertrag2 = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2024, 6, 1),
                ende=date(2025, 6, 1),
                miete=150.00,
                kaution=450.00,
                status='active'
            )
            vertrag2.save()
    
    def test_update_availability_method(self):
        """Test the update_availability method on MietObjekt."""
        # Create an active contract
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Manually set to available (simulate inconsistent state)
        MietObjekt.objects.filter(pk=self.mietobjekt.pk).update(verfuegbar=True)
        
        # Recalculate
        self.mietobjekt.refresh_from_db()
        self.mietobjekt.update_availability()
        
        # Should now be unavailable
        self.assertFalse(self.mietobjekt.verfuegbar)
    
    def test_changing_contract_dates_updates_availability(self):
        """Test that changing contract dates updates availability correctly."""
        # Create a future contract
        next_month = timezone.now().date() + timedelta(days=30)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=next_month,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # Should still be available
        self.mietobjekt.refresh_from_db()
        self.assertTrue(self.mietobjekt.verfuegbar)
        
        # Change start date to yesterday
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag.start = yesterday
        vertrag.save()
        
        # Should now be unavailable
        self.mietobjekt.refresh_from_db()
        self.assertFalse(self.mietobjekt.verfuegbar)
    
    def test_multiple_mietobjekte_independent(self):
        """Test that availability updates for one MietObjekt don't affect others."""
        # Create another MietObjekt
        mietobjekt2 = MietObjekt.objects.create(
            name='Garage 2',
            type='GEBAEUDE',
            beschreibung='Noch eine Garage',
            fläche=25.00,
            standort=self.standort,
            mietpreis=200.00,
            verfuegbar=True
        )
        
        # Create active contract for first MietObjekt
        yesterday = timezone.now().date() - timedelta(days=1)
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=yesterday,
            ende=None,
            miete=150.00,
            kaution=450.00,
            status='active'
        )
        
        # First should be unavailable, second still available
        self.mietobjekt.refresh_from_db()
        mietobjekt2.refresh_from_db()
        self.assertFalse(self.mietobjekt.verfuegbar)
        self.assertTrue(mietobjekt2.verfuegbar)
