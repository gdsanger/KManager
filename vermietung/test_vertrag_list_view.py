"""
Tests for Vertrag list view with edge cases (contracts without mietobjekt).
Tests issue #449: NoReverseMatch error for contracts without mietobjekt.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from decimal import Decimal
from datetime import date
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag


class VertragListViewTestCase(TestCase):
    """Test case for Vertrag list view with edge cases."""
    
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
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_vertrag_list_with_mietobjekt(self):
        """Test that contract list displays correctly with valid mietobjekt."""
        # Create contract with mietobjekt
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Request list page
        response = self.client.get(reverse('vermietung:vertrag_list'))
        
        # Should return 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Should contain the mietobjekt name
        self.assertContains(response, 'Büro 1')
        
        # Should contain the kunde name
        self.assertContains(response, 'Max Mustermann')
        
        # Should contain links to mietobjekt
        self.assertContains(
            response,
            reverse('vermietung:mietobjekt_detail', args=[self.mietobjekt.pk])
        )
    
    def test_vertrag_list_without_mietobjekt(self):
        """Test that contract list displays correctly without mietobjekt (null/None)."""
        # Create contract WITHOUT mietobjekt
        vertrag = Vertrag.objects.create(
            mietobjekt=None,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Request list page - should not raise NoReverseMatch
        response = self.client.get(reverse('vermietung:vertrag_list'))
        
        # Should return 200 OK (not 500 error)
        self.assertEqual(response.status_code, 200)
        
        # Should contain the kunde name
        self.assertContains(response, 'Max Mustermann')
        
        # Should contain placeholder for missing mietobjekt
        self.assertContains(response, '—')
        
        # Should NOT contain a link to mietobjekt_detail (because there is none)
        self.assertNotContains(response, 'mietobjekt_detail')
    
    def test_vertrag_list_mixed_contracts(self):
        """Test that contract list handles mix of contracts with and without mietobjekt."""
        # Create contract with mietobjekt
        vertrag_with = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Create second customer
        kunde2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Erika Musterfrau',
            strasse='Teststrasse 2',
            plz='54321',
            ort='Teststadt',
            land='Deutschland',
            email='erika@example.com'
        )
        
        # Create contract without mietobjekt
        vertrag_without = Vertrag.objects.create(
            mietobjekt=None,
            mieter=kunde2,
            start=date(2024, 2, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            status='draft'
        )
        
        # Request list page
        response = self.client.get(reverse('vermietung:vertrag_list'))
        
        # Should return 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Should contain both contracts
        self.assertContains(response, 'Max Mustermann')
        self.assertContains(response, 'Erika Musterfrau')
        
        # Should contain mietobjekt for first contract
        self.assertContains(response, 'Büro 1')
        
        # Should contain at least one placeholder
        self.assertContains(response, '—')
