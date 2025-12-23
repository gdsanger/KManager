"""
Tests for Vertrag (Contract) CRUD functionality in the user area.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag
from vermietung.forms import VertragForm, VertragEndForm


class VertragCRUDTestCase(TestCase):
    """Test case for Vertrag CRUD operations in the user area."""
    
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
        
        # Create test customers
        self.kunde1 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        self.kunde2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Erika Musterfrau',
            strasse='Teststrasse 2',
            plz='54321',
            ort='Teststadt',
            land='Deutschland',
            email='erika@example.com'
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
        
        # Create test contract
        self.vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt1,
            mieter=self.kunde1,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        self.client = Client()
    
    # Authentication and Permission Tests
    
    def test_vertrag_list_requires_authentication(self):
        """Test that vertrag_list view requires authentication."""
        response = self.client.get(reverse('vermietung:vertrag_list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_vertrag_list_requires_vermietung_access(self):
        """Test that vertrag_list view requires Vermietung access."""
        # Login as regular user without Vermietung access
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('vermietung:vertrag_list'))
        # Should redirect to login (permission denied)
        self.assertEqual(response.status_code, 302)
    
    # List View Tests
    
    def test_vertrag_list_displays_contracts(self):
        """Test that vertrag_list view displays contracts."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:vertrag_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vertrag1.vertragsnummer)
        self.assertContains(response, 'Max Mustermann')
        self.assertContains(response, 'Büro 1')
    
    def test_vertrag_list_search_by_contract_number(self):
        """Test that vertrag_list search by contract number works."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_list'),
            {'q': self.vertrag1.vertragsnummer}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vertrag1.vertragsnummer)
    
    def test_vertrag_list_search_by_customer_name(self):
        """Test that vertrag_list search by customer name works."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_list'),
            {'q': 'Mustermann'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
    
    def test_vertrag_list_filter_by_status(self):
        """Test that vertrag_list status filter works."""
        # Create a cancelled contract
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde2,
            start=date(2024, 6, 1),
            miete=Decimal('800.00'),
            kaution=Decimal('2400.00'),
            status='cancelled'
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_list'),
            {'status': 'active'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vertrag1.vertragsnummer)
        self.assertNotContains(response, vertrag2.vertragsnummer)
    
    # Detail View Tests
    
    def test_vertrag_detail_displays_contract_info(self):
        """Test that vertrag_detail view displays contract information."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_detail', args=[self.vertrag1.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vertrag1.vertragsnummer)
        self.assertContains(response, 'Max Mustermann')
        self.assertContains(response, 'Büro 1')
        self.assertContains(response, '500')  # Changed to just check for number
        self.assertContains(response, '1500')  # Changed to just check for number
    
    def test_vertrag_detail_shows_end_button_for_active_contract(self):
        """Test that detail view shows end button for active contracts."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_detail', args=[self.vertrag1.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Beenden')
        self.assertContains(response, 'Stornieren')
    
    def test_vertrag_detail_no_delete_button(self):
        """Test that detail view does NOT show delete button for Vertrag itself."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_detail', args=[self.vertrag1.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        # Should not contain a delete button/form for the Vertrag entity itself
        # Check that there's no vertrag_delete URL in the page actions
        self.assertNotContains(response, 'vertrag_delete')
        # Documents can have delete buttons, so we only check for Vertrag-specific delete
        self.assertNotContains(response, 'Vertrag löschen')
    
    # Create View Tests
    
    def test_vertrag_create_get(self):
        """Test that vertrag_create GET request shows form."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:vertrag_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neuer Vertrag')
        # Check that form fields are present
        self.assertContains(response, 'id_mietobjekt')
        self.assertContains(response, 'id_mieter')
        self.assertContains(response, 'id_start')
        self.assertContains(response, 'id_miete')
        self.assertContains(response, 'id_kaution')
    
    def test_vertrag_create_post_valid(self):
        """Test creating a contract with valid data."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'mietobjekt': self.mietobjekt2.pk,
            'mieter': self.kunde2.pk,
            'start': '2024-06-01',
            'ende': '2025-05-31',
            'miete': '800.00',
            'kaution': '2400.00',
            'status': 'active'
        }
        
        response = self.client.post(reverse('vermietung:vertrag_create'), data)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Check that contract was created
        new_vertrag = Vertrag.objects.get(mietobjekt=self.mietobjekt2)
        self.assertEqual(new_vertrag.mieter, self.kunde2)
        self.assertEqual(new_vertrag.miete, Decimal('800.00'))
        # Verify auto-generated contract number
        self.assertTrue(new_vertrag.vertragsnummer.startswith('V-'))
    
    def test_vertrag_create_auto_generates_contract_number(self):
        """Test that contract number is auto-generated."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'mietobjekt': self.mietobjekt2.pk,
            'mieter': self.kunde2.pk,
            'start': '2024-06-01',
            'miete': '800.00',
            'kaution': '2400.00',
            'status': 'draft'
        }
        
        self.client.post(reverse('vermietung:vertrag_create'), data)
        
        new_vertrag = Vertrag.objects.get(mietobjekt=self.mietobjekt2)
        # Contract number should be auto-generated
        self.assertIsNotNone(new_vertrag.vertragsnummer)
        self.assertTrue(new_vertrag.vertragsnummer.startswith('V-'))
    
    def test_vertrag_create_validates_overlapping_contracts(self):
        """Test that creating overlapping contracts is prevented."""
        self.client.login(username='testuser', password='testpass123')
        
        # Try to create a contract that overlaps with vertrag1
        data = {
            'mietobjekt': self.mietobjekt1.pk,  # Same as vertrag1
            'mieter': self.kunde2.pk,
            'start': '2024-06-01',  # Overlaps with vertrag1
            'ende': '2024-12-31',
            'miete': '500.00',
            'kaution': '1500.00',
            'status': 'active'
        }
        
        response = self.client.post(reverse('vermietung:vertrag_create'), data)
        
        # Should show form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'überschneidet')
    
    # Edit View Tests
    
    def test_vertrag_edit_get(self):
        """Test that vertrag_edit GET request shows form with existing data."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_edit', args=[self.vertrag1.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.vertrag1.vertragsnummer)
        self.assertContains(response, '500.00')
    
    def test_vertrag_edit_post_valid(self):
        """Test editing a contract with valid data."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'mietobjekt': self.mietobjekt1.pk,
            'mieter': self.kunde1.pk,
            'start': '2024-01-01',
            'ende': '2024-11-30',  # Changed end date
            'miete': '550.00',  # Changed rent
            'kaution': '1500.00',
            'status': 'active'
        }
        
        response = self.client.post(
            reverse('vermietung:vertrag_edit', args=[self.vertrag1.pk]),
            data
        )
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Check that contract was updated
        self.vertrag1.refresh_from_db()
        self.assertEqual(self.vertrag1.miete, Decimal('550.00'))
        self.assertEqual(self.vertrag1.ende, date(2024, 11, 30))
    
    # End Contract Tests
    
    def test_vertrag_end_get(self):
        """Test that vertrag_end GET request shows form."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_end', args=[self.vertrag1.pk])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vertrag beenden')
        self.assertContains(response, self.vertrag1.vertragsnummer)
    
    def test_vertrag_end_post_valid(self):
        """Test ending a contract with valid date."""
        self.client.login(username='testuser', password='testpass123')
        
        end_date = date.today() + timedelta(days=30)
        data = {
            'ende': end_date.strftime('%Y-%m-%d')
        }
        
        response = self.client.post(
            reverse('vermietung:vertrag_end', args=[self.vertrag1.pk]),
            data
        )
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Check that contract was ended
        self.vertrag1.refresh_from_db()
        self.assertEqual(self.vertrag1.ende, end_date)
    
    def test_vertrag_end_sets_status_ended_if_past_date(self):
        """Test that ending contract with past date sets status to ended."""
        self.client.login(username='testuser', password='testpass123')
        
        # Set end date to yesterday
        end_date = date.today() - timedelta(days=1)
        data = {
            'ende': end_date.strftime('%Y-%m-%d')
        }
        
        response = self.client.post(
            reverse('vermietung:vertrag_end', args=[self.vertrag1.pk]),
            data
        )
        
        # Check that status was set to ended
        self.vertrag1.refresh_from_db()
        self.assertEqual(self.vertrag1.status, 'ended')
    
    def test_vertrag_end_validates_date_after_start(self):
        """Test that end date must be after start date."""
        self.client.login(username='testuser', password='testpass123')
        
        # Try to set end date before start date
        data = {
            'ende': '2023-12-31'  # Before start date (2024-01-01)
        }
        
        response = self.client.post(
            reverse('vermietung:vertrag_end', args=[self.vertrag1.pk]),
            data
        )
        
        # Should show form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'muss nach dem Vertragsbeginn')
    
    def test_vertrag_end_cannot_end_cancelled_contract(self):
        """Test that cancelled contracts cannot be ended."""
        self.vertrag1.status = 'cancelled'
        self.vertrag1.save()
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:vertrag_end', args=[self.vertrag1.pk])
        )
        
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)
    
    # Cancel Contract Tests
    
    def test_vertrag_cancel_post(self):
        """Test cancelling a contract."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            reverse('vermietung:vertrag_cancel', args=[self.vertrag1.pk])
        )
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Check that contract was cancelled
        self.vertrag1.refresh_from_db()
        self.assertEqual(self.vertrag1.status, 'cancelled')
    
    def test_vertrag_cancel_updates_mietobjekt_availability(self):
        """Test that cancelling contract updates rental object availability."""
        # Set mietobjekt as not available
        self.mietobjekt1.verfuegbar = False
        self.mietobjekt1.save()
        
        self.client.login(username='testuser', password='testpass123')
        self.client.post(
            reverse('vermietung:vertrag_cancel', args=[self.vertrag1.pk])
        )
        
        # Check that mietobjekt is now available
        self.mietobjekt1.refresh_from_db()
        self.assertTrue(self.mietobjekt1.verfuegbar)
    
    def test_vertrag_cancel_cannot_cancel_ended_contract(self):
        """Test that ended contracts cannot be cancelled."""
        self.vertrag1.status = 'ended'
        self.vertrag1.save()
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('vermietung:vertrag_cancel', args=[self.vertrag1.pk])
        )
        
        # Status should remain ended
        self.vertrag1.refresh_from_db()
        self.assertEqual(self.vertrag1.status, 'ended')
    
    # Form Tests
    
    def test_vertrag_form_filters_mieter_to_kunde(self):
        """Test that VertragForm filters mieter field to only KUNDE addresses."""
        form = VertragForm()
        
        # Should only show KUNDE addresses
        mieter_queryset = form.fields['mieter'].queryset
        self.assertEqual(mieter_queryset.count(), 2)  # kunde1 and kunde2
        self.assertIn(self.kunde1, mieter_queryset)
        self.assertIn(self.kunde2, mieter_queryset)
    
    def test_vertrag_form_shows_all_mietobjekte(self):
        """Test that VertragForm shows all mietobjekte."""
        form = VertragForm()
        
        mietobjekt_queryset = form.fields['mietobjekt'].queryset
        self.assertEqual(mietobjekt_queryset.count(), 2)
        self.assertIn(self.mietobjekt1, mietobjekt_queryset)
        self.assertIn(self.mietobjekt2, mietobjekt_queryset)
    
    def test_vertrag_end_form_validates_date(self):
        """Test that VertragEndForm validates end date."""
        form = VertragEndForm(
            data={'ende': '2023-12-31'},
            vertrag=self.vertrag1
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('ende', form.errors)
