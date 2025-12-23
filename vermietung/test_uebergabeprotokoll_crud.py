"""
Tests for Uebergabeprotokoll (Handover Protocol) CRUD functionality in the user area.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, Uebergabeprotokoll
from vermietung.forms import UebergabeprotokollForm


class UebergabeprotokollCRUDTestCase(TestCase):
    """Test case for Uebergabeprotokoll CRUD operations in the user area."""
    
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
        
        # Create a regular user without Vermietung access
        self.regular_user = User.objects.create_user(
            username='regularuser',
            password='testpass123',
            is_staff=False
        )
        
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
        
        # Create test contract
        self.vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Create test protocol
        self.protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            zaehlerstand_strom=Decimal('1000.00'),
            zaehlerstand_gas=Decimal('500.00'),
            zaehlerstand_wasser=Decimal('200.00'),
            anzahl_schluessel=2,
            bemerkungen='Alles in Ordnung',
            person_vermieter='Hans Schmidt',
            person_mieter='Max Mustermann'
        )
        
        self.client = Client()
    
    def test_list_view_requires_vermietung_access(self):
        """Test that list view requires Vermietung group membership."""
        # Not logged in - should redirect to login
        response = self.client.get(reverse('vermietung:uebergabeprotokoll_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Regular user without Vermietung access - should redirect to login
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('vermietung:uebergabeprotokoll_list'))
        self.assertEqual(response.status_code, 302)  # Redirect (user_passes_test behavior)
        
        # User with Vermietung access - should succeed
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:uebergabeprotokoll_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_list_view_displays_protokolle(self):
        """Test that list view displays all protokolle."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:uebergabeprotokoll_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Übergabeprotokolle')
        self.assertContains(response, self.vertrag.vertragsnummer)
        self.assertContains(response, self.mietobjekt.name)
    
    def test_list_view_search(self):
        """Test that list view search works correctly."""
        self.client.login(username='testuser', password='testpass123')
        
        # Search by vertrag number
        response = self.client.get(
            reverse('vermietung:uebergabeprotokoll_list'),
            {'q': self.vertrag.vertragsnummer}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vertrag.vertragsnummer)
        
        # Search by non-existent term
        response = self.client.get(
            reverse('vermietung:uebergabeprotokoll_list'),
            {'q': 'nonexistent'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.vertrag.vertragsnummer)
    
    def test_list_view_typ_filter(self):
        """Test that list view typ filter works correctly."""
        self.client.login(username='testuser', password='testpass123')
        
        # Filter by EINZUG
        response = self.client.get(
            reverse('vermietung:uebergabeprotokoll_list'),
            {'typ': 'EINZUG'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Einzug')
        
        # Filter by AUSZUG (should be empty)
        response = self.client.get(
            reverse('vermietung:uebergabeprotokoll_list'),
            {'typ': 'AUSZUG'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.vertrag.vertragsnummer)
    
    def test_detail_view(self):
        """Test that detail view displays protokoll data."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:uebergabeprotokoll_detail', args=[self.protokoll.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.protokoll.vertrag.vertragsnummer)
        self.assertContains(response, self.protokoll.mietobjekt.name)
        self.assertContains(response, 'Einzug')
        self.assertContains(response, str(self.protokoll.anzahl_schluessel))
    
    def test_create_view_get(self):
        """Test that create view displays form."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:uebergabeprotokoll_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neues Übergabeprotokoll')
        self.assertIsInstance(response.context['form'], UebergabeprotokollForm)
    
    def test_create_view_post_valid(self):
        """Test creating a new protokoll with valid data."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'vertrag': self.vertrag.pk,
            'mietobjekt': self.mietobjekt.pk,
            'typ': 'AUSZUG',
            'uebergabetag': '2024-12-31',
            'zaehlerstand_strom': '1500.00',
            'zaehlerstand_gas': '600.00',
            'zaehlerstand_wasser': '250.00',
            'anzahl_schluessel': 2,
            'bemerkungen': 'Test bemerkungen',
            'person_vermieter': 'Test Vermieter',
            'person_mieter': 'Test Mieter',
        }
        
        response = self.client.post(
            reverse('vermietung:uebergabeprotokoll_create'),
            data
        )
        
        # Should redirect to detail view
        self.assertEqual(response.status_code, 302)
        
        # Check that protokoll was created
        new_protokoll = Uebergabeprotokoll.objects.get(typ='AUSZUG')
        self.assertEqual(new_protokoll.vertrag, self.vertrag)
        self.assertEqual(new_protokoll.anzahl_schluessel, 2)
    
    def test_create_from_vertrag_view(self):
        """Test creating protokoll from vertrag (guided flow)."""
        self.client.login(username='testuser', password='testpass123')
        
        # GET - should pre-fill vertrag and mietobjekt
        response = self.client.get(
            reverse('vermietung:uebergabeprotokoll_create_from_vertrag', args=[self.vertrag.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vertrag.vertragsnummer)
        form = response.context['form']
        # Check that vertrag field is initialized with the correct value
        self.assertEqual(form.fields['vertrag'].initial, self.vertrag)
        self.assertEqual(form.fields['mietobjekt'].initial, self.vertrag.mietobjekt)
        
        # POST - create protokoll
        data = {
            'vertrag': self.vertrag.pk,
            'mietobjekt': self.mietobjekt.pk,
            'typ': 'EINZUG',
            'uebergabetag': '2024-01-02',
            'anzahl_schluessel': 3,
        }
        
        response = self.client.post(
            reverse('vermietung:uebergabeprotokoll_create_from_vertrag', args=[self.vertrag.pk]),
            data
        )
        
        # Should redirect to detail view
        self.assertEqual(response.status_code, 302)
        
        # Check that protokoll was created
        self.assertEqual(Uebergabeprotokoll.objects.filter(typ='EINZUG').count(), 2)
    
    def test_edit_view_get(self):
        """Test that edit view displays form with existing data."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:uebergabeprotokoll_edit', args=[self.protokoll.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Übergabeprotokoll bearbeiten')
        form = response.context['form']
        self.assertEqual(form.instance, self.protokoll)
    
    def test_edit_view_post_valid(self):
        """Test editing a protokoll with valid data."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'vertrag': self.vertrag.pk,
            'mietobjekt': self.mietobjekt.pk,
            'typ': 'EINZUG',
            'uebergabetag': '2024-01-01',
            'zaehlerstand_strom': '2000.00',  # Changed
            'anzahl_schluessel': 3,  # Changed
            'bemerkungen': 'Updated bemerkungen',
            'person_vermieter': 'Hans Schmidt',
            'person_mieter': 'Max Mustermann',
        }
        
        response = self.client.post(
            reverse('vermietung:uebergabeprotokoll_edit', args=[self.protokoll.pk]),
            data
        )
        
        # Should redirect to detail view
        self.assertEqual(response.status_code, 302)
        
        # Check that protokoll was updated
        self.protokoll.refresh_from_db()
        self.assertEqual(self.protokoll.zaehlerstand_strom, Decimal('2000.00'))
        self.assertEqual(self.protokoll.anzahl_schluessel, 3)
    
    def test_delete_view(self):
        """Test deleting a protokoll."""
        self.client.login(username='testuser', password='testpass123')
        
        # Count before delete
        count_before = Uebergabeprotokoll.objects.count()
        
        response = self.client.post(
            reverse('vermietung:uebergabeprotokoll_delete', args=[self.protokoll.pk])
        )
        
        # Should redirect to list view
        self.assertEqual(response.status_code, 302)
        
        # Check that protokoll was deleted
        self.assertEqual(Uebergabeprotokoll.objects.count(), count_before - 1)
        self.assertFalse(Uebergabeprotokoll.objects.filter(pk=self.protokoll.pk).exists())
    
    def test_validation_mietobjekt_must_match_vertrag(self):
        """Test that mietobjekt must match the vertrag's mietobjekt."""
        # Create another mietobjekt
        mietobjekt2 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Anderes Büro',
            standort=self.standort,
            mietpreis=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            verfuegbar=True
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'vertrag': self.vertrag.pk,
            'mietobjekt': mietobjekt2.pk,  # Wrong mietobjekt
            'typ': 'EINZUG',
            'uebergabetag': '2024-01-01',
            'anzahl_schluessel': 2,
        }
        
        response = self.client.post(
            reverse('vermietung:uebergabeprotokoll_create'),
            data
        )
        
        # Should not create protokoll
        self.assertEqual(response.status_code, 200)  # Re-render form with error
        self.assertFormError(
            response.context['form'],
            'mietobjekt',
            'Das Mietobjekt muss zum Vertrag passen. Der Vertrag ist für "Büro 1".'
        )
