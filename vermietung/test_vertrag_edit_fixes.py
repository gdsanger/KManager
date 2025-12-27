"""
Tests for Vertrag edit fixes - verifying date field display and availability check fixes.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from datetime import date
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt
from vermietung.forms import VertragForm


class VertragEditFixesTestCase(TestCase):
    """Test case for verifying fixes to contract edit functionality."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a user with Vermietung access
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=False
        )
        # Create Vermietung group and add user to it
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
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
        self.kunde1 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        # Create test mietobjekte
        self.mietobjekt1 = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Kleines Büro',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbar=True
        )
        
        self.mietobjekt2 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Großes Büro',
            standort=self.standort,
            mietpreis=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            verfuegbar=True
        )
        
        # Create test contract with VertragsObjekt
        self.vertrag1 = Vertrag.objects.create(
            mieter=self.kunde1,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        # Add mietobjekt1 to the contract via VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=self.vertrag1,
            mietobjekt=self.mietobjekt1
        )
        # Update availability
        self.vertrag1.update_mietobjekte_availability()
        
    def test_date_fields_show_values_when_editing(self):
        """Test Fix 1: Date fields should display values when editing a contract."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(
            reverse('vermietung:vertrag_edit', args=[self.vertrag1.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the form contains the date values in YYYY-MM-DD format
        # The HTML input type="date" requires this format
        self.assertContains(response, '2024-01-01')
        self.assertContains(response, '2024-12-31')
        
    def test_form_date_widget_has_correct_format(self):
        """Test that the VertragForm date widgets have the correct format attribute."""
        form = VertragForm(instance=self.vertrag1)
        
        # Check that start and ende widgets have format specified
        start_widget = form.fields['start'].widget
        ende_widget = form.fields['ende'].widget
        
        # DateInput widgets should have format set to '%Y-%m-%d'
        self.assertEqual(start_widget.format, '%Y-%m-%d')
        self.assertEqual(ende_widget.format, '%Y-%m-%d')
        
    def test_can_save_contract_without_changing_mietobjekte(self):
        """Test Fix 2: Should be able to save contract without changing assigned rental objects."""
        self.client.login(username='testuser', password='testpass123')
        
        # Manually mark mietobjekt1 as unavailable to simulate it being in an active contract
        MietObjekt.objects.filter(pk=self.mietobjekt1.pk).update(verfuegbar=False)
        self.mietobjekt1.refresh_from_db()
        
        # The mietobjekt should be marked as unavailable
        self.assertFalse(self.mietobjekt1.verfuegbar)
        
        # But we should still be able to save the contract with the same mietobjekt
        data = {
            'mietobjekte': [self.mietobjekt1.pk],  # Same object already assigned
            'mieter': self.kunde1.pk,
            'start': '2024-01-01',
            'ende': '2024-12-31',
            'miete': '550.00',  # Changed rent
            'kaution': '1500.00',
            'status': 'active'
        }
        
        response = self.client.post(
            reverse('vermietung:vertrag_edit', args=[self.vertrag1.pk]),
            data
        )
        
        # Should redirect to detail page (successful save)
        self.assertEqual(response.status_code, 302)
        
        # Check that contract was updated
        self.vertrag1.refresh_from_db()
        self.assertEqual(self.vertrag1.miete, Decimal('550.00'))
        
    def test_cannot_add_unavailable_mietobjekt_to_contract(self):
        """Test Fix 2: Should still prevent adding a truly unavailable rental object."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create another contract with mietobjekt2
        vertrag2 = Vertrag.objects.create(
            mieter=self.kunde1,
            start=date(2024, 3, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag2,
            mietobjekt=self.mietobjekt2
        )
        
        # Manually mark mietobjekt2 as unavailable
        MietObjekt.objects.filter(pk=self.mietobjekt2.pk).update(verfuegbar=False)
        self.mietobjekt2.refresh_from_db()
        
        # mietobjekt2 should now be unavailable
        self.assertFalse(self.mietobjekt2.verfuegbar)
        
        # Manually mark mietobjekt1 as unavailable too
        MietObjekt.objects.filter(pk=self.mietobjekt1.pk).update(verfuegbar=False)
        
        # Try to add mietobjekt2 to vertrag1 (should fail)
        data = {
            'mietobjekte': [self.mietobjekt1.pk, self.mietobjekt2.pk],  # Adding unavailable object
            'mieter': self.kunde1.pk,
            'start': '2024-01-01',
            'ende': '2024-12-31',
            'miete': '500.00',
            'kaution': '1500.00',
            'status': 'active'
        }
        
        response = self.client.post(
            reverse('vermietung:vertrag_edit', args=[self.vertrag1.pk]),
            data
        )
        
        # Should show form with error about unavailable object
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nicht verfügbar')
        self.assertContains(response, 'Büro 2')
        
    def test_form_validation_excludes_current_contract_mietobjekte(self):
        """Test that form validation excludes current contract's objects from availability check."""
        # Manually mark mietobjekt1 as unavailable to simulate it being in an active contract
        MietObjekt.objects.filter(pk=self.mietobjekt1.pk).update(verfuegbar=False)
        self.mietobjekt1.refresh_from_db()
        
        # mietobjekt1 is unavailable
        self.assertFalse(self.mietobjekt1.verfuegbar)
        
        # Create form for editing vertrag1
        data = {
            'mietobjekte': [self.mietobjekt1.pk],  # Current object
            'mieter': self.kunde1.pk,
            'start': date(2024, 1, 1),
            'ende': date(2024, 12, 31),
            'miete': Decimal('500.00'),
            'kaution': Decimal('1500.00'),
            'status': 'active'
        }
        
        form = VertragForm(data, instance=self.vertrag1)
        
        # Form should be valid because we're keeping the same object
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
