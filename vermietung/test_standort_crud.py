"""
Tests for Standort (Location) CRUD functionality in the user area.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.forms import AdresseStandortForm
from vermietung.models import MietObjekt


class StandortCRUDTestCase(TestCase):
    """Test case for Standort CRUD operations in the user area."""
    
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
        
        # Create test locations
        self.standort1 = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Lager Nord',
            strasse='Nordstrasse 10',
            plz='12345',
            ort='Hamburg',
            land='Deutschland',
            email='nord@lager.de',
            telefon='040123456'
        )
        
        self.standort2 = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Lager Süd',
            strasse='Südstrasse 20',
            plz='80331',
            ort='München',
            land='Deutschland',
            email='sued@lager.de'
        )
        
        # Create a non-standort address (should not appear in standort list)
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Kundenstrasse 1',
            plz='11111',
            ort='Berlin',
            land='Deutschland'
        )
        
        self.client = Client()
    
    def test_standort_list_requires_authentication(self):
        """Test that standort_list view requires authentication."""
        response = self.client.get(reverse('vermietung:standort_list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_standort_list_requires_vermietung_access(self):
        """Test that standort_list view requires Vermietung access."""
        # Login as regular user without Vermietung access
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('vermietung:standort_list'))
        # Should redirect to login (permission denied)
        self.assertEqual(response.status_code, 302)
    
    def test_standort_list_shows_only_standorte(self):
        """Test that standort_list view shows only STANDORT addresses."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:standort_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lager Nord')
        self.assertContains(response, 'Lager Süd')
        # Should not contain the KUNDE
        self.assertNotContains(response, 'Max Mustermann')
    
    def test_standort_list_search(self):
        """Test that standort_list search functionality works."""
        self.client.login(username='testuser', password='testpass123')
        
        # Search by name
        response = self.client.get(reverse('vermietung:standort_list'), {'q': 'Nord'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lager Nord')
        self.assertNotContains(response, 'Lager Süd')
        
        # Search by city
        response = self.client.get(reverse('vermietung:standort_list'), {'q': 'München'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lager Süd')
        self.assertNotContains(response, 'Lager Nord')
    
    def test_standort_list_pagination(self):
        """Test that standort_list pagination works."""
        # Create many standorte to test pagination
        for i in range(25):
            Adresse.objects.create(
                adressen_type='STANDORT',
                name=f'Lager {i}',
                strasse=f'Strasse {i}',
                plz='12345',
                ort='Stadt',
                land='Deutschland'
            )
        
        self.client.login(username='testuser', password='testpass123')
        
        # First page should have 20 items (default page size)
        response = self.client.get(reverse('vermietung:standort_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 20)
        
        # Second page should have remaining items
        response = self.client.get(reverse('vermietung:standort_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        # 25 created + 2 from setUp = 27 total, so page 2 should have 7
        self.assertEqual(len(response.context['page_obj']), 7)
    
    def test_standort_detail_view(self):
        """Test standort detail view."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:standort_detail', args=[self.standort1.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lager Nord')
        self.assertContains(response, 'Nordstrasse 10')
        self.assertContains(response, 'Hamburg')
    
    def test_standort_detail_requires_standort_type(self):
        """Test that standort detail view requires STANDORT type."""
        self.client.login(username='testuser', password='testpass123')
        # Try to access a KUNDE as if it were a STANDORT
        response = self.client.get(reverse('vermietung:standort_detail', args=[self.kunde.pk]))
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_standort_create_form_display(self):
        """Test standort create form displays correctly."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:standort_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neuer Standort')
        self.assertIsInstance(response.context['form'], AdresseStandortForm)
    
    def test_standort_create_success(self):
        """Test creating a new standort."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'Lager West',
            'strasse': 'Weststrasse 30',
            'plz': '50667',
            'ort': 'Köln',
            'land': 'Deutschland',
            'telefon': '0221123456',
            'email': 'west@lager.de',
            'bemerkung': 'Neues Lager im Westen'
        }
        
        response = self.client.post(reverse('vermietung:standort_create'), data)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Check standort was created
        standort = Adresse.objects.get(name='Lager West')
        self.assertEqual(standort.adressen_type, 'STANDORT')
        self.assertEqual(standort.ort, 'Köln')
        
        # Should redirect to detail page
        self.assertRedirects(response, reverse('vermietung:standort_detail', args=[standort.pk]))
    
    def test_standort_create_validation(self):
        """Test standort create form validation."""
        self.client.login(username='testuser', password='testpass123')
        
        # Submit form with missing required fields
        data = {
            'name': 'Lager West',
            # Missing strasse, plz, ort, land
        }
        
        response = self.client.post(reverse('vermietung:standort_create'), data)
        
        # Should not redirect (form errors)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'strasse', 'Dieses Feld ist erforderlich.')
    
    def test_standort_edit_form_display(self):
        """Test standort edit form displays correctly."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:standort_edit', args=[self.standort1.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Standort bearbeiten')
        self.assertIsInstance(response.context['form'], AdresseStandortForm)
        self.assertEqual(response.context['standort'], self.standort1)
    
    def test_standort_edit_success(self):
        """Test editing an existing standort."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'Lager Nord (aktualisiert)',
            'strasse': 'Nordstrasse 10',
            'plz': '12345',
            'ort': 'Hamburg',
            'land': 'Deutschland',
            'telefon': '040999999',
            'email': 'nord-neu@lager.de',
            'bemerkung': 'Aktualisiert'
        }
        
        response = self.client.post(
            reverse('vermietung:standort_edit', args=[self.standort1.pk]),
            data
        )
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('vermietung:standort_detail', args=[self.standort1.pk]))
        
        # Check standort was updated
        self.standort1.refresh_from_db()
        self.assertEqual(self.standort1.name, 'Lager Nord (aktualisiert)')
        self.assertEqual(self.standort1.telefon, '040999999')
        self.assertEqual(self.standort1.adressen_type, 'STANDORT')  # Type should remain STANDORT
    
    def test_standort_delete_success(self):
        """Test deleting a standort without mietobjekte."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(reverse('vermietung:standort_delete', args=[self.standort1.pk]))
        
        # Should redirect to list page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('vermietung:standort_list'))
        
        # Check standort was deleted
        self.assertFalse(Adresse.objects.filter(pk=self.standort1.pk).exists())
    
    def test_standort_delete_with_mietobjekte_fails(self):
        """Test that standort with mietobjekte cannot be deleted."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a mietobjekt at this standort
        mietobjekt = MietObjekt.objects.create(
            name='Test Objekt',
            type='LAGER',
            beschreibung='Test',
            standort=self.standort1,
            mietpreis=1000.00
        )
        
        response = self.client.post(reverse('vermietung:standort_delete', args=[self.standort1.pk]))
        
        # Should redirect back to detail page (not list)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('vermietung:standort_detail', args=[self.standort1.pk]))
        
        # Check standort was NOT deleted
        self.assertTrue(Adresse.objects.filter(pk=self.standort1.pk).exists())
    
    def test_standort_form_sets_type_to_standort(self):
        """Test that AdresseStandortForm always sets adressen_type to STANDORT."""
        form_data = {
            'name': 'Test Standort',
            'strasse': 'Test Strasse',
            'plz': '12345',
            'ort': 'Test Ort',
            'land': 'Deutschland'
        }
        
        form = AdresseStandortForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        standort = form.save()
        self.assertEqual(standort.adressen_type, 'STANDORT')
