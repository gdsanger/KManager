"""
Tests for Adresse (Generic Address) CRUD functionality in the user area.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.forms import AdresseForm


class AdresseCRUDTestCase(TestCase):
    """Test case for Adresse CRUD operations in the user area."""
    
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
        
        # Create test addresses
        self.adresse1 = Adresse.objects.create(
            adressen_type='Adresse',
            name='Erika Mustermann',
            firma='Musterfirma GmbH',
            anrede='FRAU',
            strasse='Musterstrasse 10',
            plz='12345',
            ort='Berlin',
            land='Deutschland',
            email='erika@muster.de',
            telefon='030123456',
            mobil='0151234567'
        )
        
        self.adresse2 = Adresse.objects.create(
            adressen_type='Adresse',
            name='Hans Schmidt',
            strasse='Testweg 20',
            plz='80331',
            ort='München',
            land='Deutschland',
            email='hans@test.de'
        )
        
        # Create a non-adresse address (should not appear in adresse list)
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Kundenstrasse 1',
            plz='11111',
            ort='Hamburg',
            land='Deutschland'
        )
        
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Lager Nord',
            strasse='Nordstrasse 10',
            plz='22222',
            ort='Bremen',
            land='Deutschland'
        )
        
        self.client = Client()
    
    def test_adresse_list_requires_authentication(self):
        """Test that adresse_list view requires authentication."""
        response = self.client.get(reverse('vermietung:adresse_list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_adresse_list_requires_vermietung_access(self):
        """Test that adresse_list view requires Vermietung access."""
        # Login as regular user without Vermietung access
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_list'))
        # Should redirect to login (permission denied)
        self.assertEqual(response.status_code, 302)
    
    def test_adresse_list_shows_only_adressen(self):
        """Test that adresse_list view shows only Adresse type addresses."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Erika Mustermann')
        self.assertContains(response, 'Hans Schmidt')
        # Should not contain KUNDE or STANDORT
        self.assertNotContains(response, 'Max Mustermann')
        self.assertNotContains(response, 'Lager Nord')
    
    def test_adresse_list_search(self):
        """Test that adresse_list search functionality works."""
        self.client.login(username='testuser', password='testpass123')
        
        # Search by name
        response = self.client.get(reverse('vermietung:adresse_list'), {'q': 'Erika'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Erika Mustermann')
        self.assertNotContains(response, 'Hans Schmidt')
        
        # Search by city
        response = self.client.get(reverse('vermietung:adresse_list'), {'q': 'München'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hans Schmidt')
        self.assertNotContains(response, 'Erika Mustermann')
        
        # Search by email
        response = self.client.get(reverse('vermietung:adresse_list'), {'q': 'erika@muster.de'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Erika Mustermann')
        
        # Search with no results
        response = self.client.get(reverse('vermietung:adresse_list'), {'q': 'Nonexistent'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Keine Adressen gefunden')
    
    def test_adresse_list_pagination(self):
        """Test that adresse_list pagination works."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create more addresses to trigger pagination (20 per page)
        for i in range(25):
            Adresse.objects.create(
                adressen_type='Adresse',
                name=f'Test Adresse {i}',
                strasse=f'Teststrasse {i}',
                plz='12345',
                ort='Berlin',
                land='Deutschland'
            )
        
        # First page
        response = self.client.get(reverse('vermietung:adresse_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Seite 1 von 2')
        
        # Second page
        response = self.client.get(reverse('vermietung:adresse_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Seite 2 von 2')
    
    def test_adresse_detail_requires_authentication(self):
        """Test that adresse_detail view requires authentication."""
        response = self.client.get(reverse('vermietung:adresse_detail', args=[self.adresse1.pk]))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_adresse_detail_shows_correct_data(self):
        """Test that adresse_detail view shows correct address data."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_detail', args=[self.adresse1.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Erika Mustermann')
        self.assertContains(response, 'Musterfirma GmbH')
        self.assertContains(response, 'Musterstrasse 10')
        self.assertContains(response, 'erika@muster.de')
    
    def test_adresse_detail_only_shows_adresse_type(self):
        """Test that adresse_detail view returns 404 for non-Adresse types."""
        self.client.login(username='testuser', password='testpass123')
        
        # Try to access a KUNDE via adresse_detail
        response = self.client.get(reverse('vermietung:adresse_detail', args=[self.kunde.pk]))
        self.assertEqual(response.status_code, 404)
        
        # Try to access a STANDORT via adresse_detail
        response = self.client.get(reverse('vermietung:adresse_detail', args=[self.standort.pk]))
        self.assertEqual(response.status_code, 404)
    
    def test_adresse_create_requires_authentication(self):
        """Test that adresse_create view requires authentication."""
        response = self.client.get(reverse('vermietung:adresse_create'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_adresse_create_get(self):
        """Test that adresse_create view displays form."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neue Adresse')
        self.assertIsInstance(response.context['form'], AdresseForm)
    
    def test_adresse_create_post_valid(self):
        """Test creating a new address with valid data."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'New Test Person',
            'firma': 'Test Company',
            'strasse': 'Teststrasse 123',
            'plz': '54321',
            'ort': 'Frankfurt',
            'land': 'Deutschland',
            'email': 'new@test.de',
            'telefon': '069123456'
        }
        
        response = self.client.post(reverse('vermietung:adresse_create'), data)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify address was created
        adresse = Adresse.objects.get(name='New Test Person')
        self.assertEqual(adresse.adressen_type, 'Adresse')
        self.assertEqual(adresse.firma, 'Test Company')
        self.assertEqual(adresse.ort, 'Frankfurt')
        
        # Should redirect to detail page
        self.assertRedirects(response, reverse('vermietung:adresse_detail', args=[adresse.pk]))
    
    def test_adresse_create_post_invalid(self):
        """Test creating a new address with invalid data."""
        self.client.login(username='testuser', password='testpass123')
        
        # Missing required fields
        data = {
            'name': 'Incomplete Address',
            # Missing strasse, plz, ort, land
        }
        
        response = self.client.post(reverse('vermietung:adresse_create'), data)
        
        # Should stay on form page
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'strasse', 'Dieses Feld ist erforderlich.')
    
    def test_adresse_edit_requires_authentication(self):
        """Test that adresse_edit view requires authentication."""
        response = self.client.get(reverse('vermietung:adresse_edit', args=[self.adresse1.pk]))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_adresse_edit_get(self):
        """Test that adresse_edit view displays form with existing data."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_edit', args=[self.adresse1.pk]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adresse bearbeiten')
        self.assertIsInstance(response.context['form'], AdresseForm)
        self.assertEqual(response.context['form'].instance, self.adresse1)
    
    def test_adresse_edit_post_valid(self):
        """Test editing an address with valid data."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'Updated Name',
            'firma': 'Updated Company',
            'strasse': self.adresse1.strasse,
            'plz': self.adresse1.plz,
            'ort': 'Updated City',
            'land': self.adresse1.land,
            'email': 'updated@test.de'
        }
        
        response = self.client.post(reverse('vermietung:adresse_edit', args=[self.adresse1.pk]), data)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('vermietung:adresse_detail', args=[self.adresse1.pk]))
        
        # Verify address was updated
        self.adresse1.refresh_from_db()
        self.assertEqual(self.adresse1.name, 'Updated Name')
        self.assertEqual(self.adresse1.firma, 'Updated Company')
        self.assertEqual(self.adresse1.ort, 'Updated City')
        self.assertEqual(self.adresse1.email, 'updated@test.de')
        # Type should still be Adresse
        self.assertEqual(self.adresse1.adressen_type, 'Adresse')
    
    def test_adresse_delete_requires_authentication(self):
        """Test that adresse_delete view requires authentication."""
        response = self.client.post(reverse('vermietung:adresse_delete', args=[self.adresse1.pk]))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_adresse_delete_requires_post(self):
        """Test that adresse_delete view requires POST method."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_delete', args=[self.adresse1.pk]))
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
    
    def test_adresse_delete_success(self):
        """Test successfully deleting an address."""
        self.client.login(username='testuser', password='testpass123')
        
        adresse_pk = self.adresse1.pk
        response = self.client.post(reverse('vermietung:adresse_delete', args=[adresse_pk]))
        
        # Should redirect to list page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('vermietung:adresse_list'))
        
        # Verify address was deleted
        self.assertFalse(Adresse.objects.filter(pk=adresse_pk).exists())
    
    def test_form_sets_adressen_type_to_adresse(self):
        """Test that AdresseForm always sets adressen_type to 'Adresse'."""
        form = AdresseForm(data={
            'name': 'Form Test',
            'strasse': 'Formstrasse 1',
            'plz': '11111',
            'ort': 'Test City',
            'land': 'Deutschland'
        })
        
        self.assertTrue(form.is_valid())
        adresse = form.save()
        self.assertEqual(adresse.adressen_type, 'Adresse')
