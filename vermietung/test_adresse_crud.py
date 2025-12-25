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
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com',
            telefon='0123456789'
        )
        
        self.adresse2 = Adresse.objects.create(
            adressen_type='Adresse',
            firma='Musterfirma GmbH',
            anrede='HERR',
            name='John Doe',
            strasse='Teststrasse 2',
            plz='54321',
            ort='Teststadt',
            land='Deutschland',
            email='john@musterfirma.de',
            mobil='0987654321'
        )
        
        # Create a non-Adresse address (should not appear in adresse list)
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde GmbH',
            strasse='Kundestrasse 3',
            plz='11111',
            ort='Kundestadt',
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
        """Test that adresse_list view shows only Adresse addresses."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        self.assertContains(response, 'John Doe')
        # Should not contain the Kunde
        self.assertNotContains(response, 'Kunde GmbH')
    
    def test_adresse_list_search(self):
        """Test that adresse_list search functionality works."""
        self.client.login(username='testuser', password='testpass123')
        
        # Search by name
        response = self.client.get(reverse('vermietung:adresse_list'), {'q': 'Mustermann'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        self.assertNotContains(response, 'John Doe')
        
        # Search by email
        response = self.client.get(reverse('vermietung:adresse_list'), {'q': 'john@musterfirma.de'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')
        self.assertNotContains(response, 'Max Mustermann')
        
        # Search by street
        response = self.client.get(reverse('vermietung:adresse_list'), {'q': 'Musterstrasse'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
    
    def test_adresse_list_pagination(self):
        """Test that adresse_list pagination works."""
        # Create additional addresses for pagination
        for i in range(25):
            Adresse.objects.create(
                adressen_type='Adresse',
                name=f'Test Adresse {i}',
                strasse=f'Teststrasse {i}',
                plz=f'{i:05d}',
                ort='Teststadt',
                land='Deutschland'
            )
        
        self.client.login(username='testuser', password='testpass123')
        
        # First page should have 20 items
        response = self.client.get(reverse('vermietung:adresse_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 20)
        
        # Second page should have remaining items
        response = self.client.get(reverse('vermietung:adresse_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.context['page_obj']) > 0)
    
    def test_adresse_detail_view(self):
        """Test that adresse_detail view shows correct information."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_detail', kwargs={'pk': self.adresse1.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        self.assertContains(response, 'Musterstrasse 1')
        self.assertContains(response, '12345')
        self.assertContains(response, 'Musterstadt')
        self.assertContains(response, 'Deutschland')
    
    def test_adresse_detail_requires_correct_type(self):
        """Test that adresse_detail only shows Adresse type addresses."""
        self.client.login(username='testuser', password='testpass123')
        # Try to access a KUNDE address through adresse_detail
        response = self.client.get(reverse('vermietung:adresse_detail', kwargs={'pk': self.kunde.pk}))
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_adresse_create_get(self):
        """Test that adresse_create GET request shows form."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neue Adresse')
        self.assertIsInstance(response.context['form'], AdresseForm)
    
    def test_adresse_create_post(self):
        """Test that adresse_create POST request creates a new address."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'Neue Adresse',
            'strasse': 'Neue Strasse 99',
            'plz': '99999',
            'ort': 'Neustadt',
            'land': 'Deutschland',
            'email': 'neue@example.com',
            'telefon': '0123456789'
        }
        
        response = self.client.post(reverse('vermietung:adresse_create'), data)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify address was created
        adresse = Adresse.objects.get(name='Neue Adresse')
        self.assertEqual(adresse.adressen_type, 'Adresse')
        self.assertEqual(adresse.strasse, 'Neue Strasse 99')
        self.assertEqual(adresse.plz, '99999')
        self.assertEqual(adresse.ort, 'Neustadt')
        self.assertEqual(adresse.land, 'Deutschland')
        
        # Check redirect to detail page
        self.assertRedirects(response, reverse('vermietung:adresse_detail', kwargs={'pk': adresse.pk}))
    
    def test_adresse_edit_get(self):
        """Test that adresse_edit GET request shows form with existing data."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:adresse_edit', kwargs={'pk': self.adresse1.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        self.assertIsInstance(response.context['form'], AdresseForm)
        self.assertEqual(response.context['adresse'], self.adresse1)
    
    def test_adresse_edit_post(self):
        """Test that adresse_edit POST request updates an address."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'Max Mustermann Updated',
            'strasse': 'Updated Strasse 1',
            'plz': '12345',
            'ort': 'Musterstadt',
            'land': 'Deutschland',
            'email': 'max@example.com',
            'telefon': '0123456789'
        }
        
        response = self.client.post(
            reverse('vermietung:adresse_edit', kwargs={'pk': self.adresse1.pk}),
            data
        )
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify address was updated
        self.adresse1.refresh_from_db()
        self.assertEqual(self.adresse1.name, 'Max Mustermann Updated')
        self.assertEqual(self.adresse1.strasse, 'Updated Strasse 1')
        # adressen_type should still be Adresse
        self.assertEqual(self.adresse1.adressen_type, 'Adresse')
    
    def test_adresse_delete(self):
        """Test that adresse_delete POST request deletes an address."""
        self.client.login(username='testuser', password='testpass123')
        
        # Get address count before deletion
        count_before = Adresse.objects.filter(adressen_type='Adresse').count()
        
        response = self.client.post(
            reverse('vermietung:adresse_delete', kwargs={'pk': self.adresse1.pk})
        )
        
        # Should redirect to list page
        self.assertRedirects(response, reverse('vermietung:adresse_list'))
        
        # Verify address was deleted
        count_after = Adresse.objects.filter(adressen_type='Adresse').count()
        self.assertEqual(count_after, count_before - 1)
        
        # Verify specific address is gone
        with self.assertRaises(Adresse.DoesNotExist):
            Adresse.objects.get(pk=self.adresse1.pk)


class AdresseFormTestCase(TestCase):
    """Test case for AdresseForm."""
    
    def test_form_sets_adressen_type(self):
        """Test that form automatically sets adressen_type to Adresse."""
        form = AdresseForm(data={
            'name': 'Test Adresse',
            'strasse': 'Test Strasse 1',
            'plz': '12345',
            'ort': 'Test City',
            'land': 'Germany'
        })
        
        self.assertTrue(form.is_valid())
        adresse = form.save()
        
        # Verify adressen_type is Adresse
        self.assertEqual(adresse.adressen_type, 'Adresse')
    
    def test_form_edit_maintains_adressen_type(self):
        """Test that editing an address maintains adressen_type as Adresse."""
        # Create an address
        adresse = Adresse.objects.create(
            adressen_type='Adresse',
            name='Original Name',
            strasse='Original Strasse',
            plz='12345',
            ort='Original City',
            land='Germany'
        )
        
        # Edit using form
        form = AdresseForm(instance=adresse, data={
            'name': 'Updated Name',
            'strasse': 'Updated Strasse',
            'plz': '54321',
            'ort': 'Updated City',
            'land': 'Germany'
        })
        
        self.assertTrue(form.is_valid())
        updated_adresse = form.save()
        
        # Verify name was updated
        self.assertEqual(updated_adresse.name, 'Updated Name')
        
        # adressen_type should still be Adresse
        self.assertEqual(updated_adresse.adressen_type, 'Adresse')
    
    def test_form_required_fields(self):
        """Test that form validates required fields."""
        # Missing required fields
        form = AdresseForm(data={})
        self.assertFalse(form.is_valid())
        
        # Check that required fields are in errors
        self.assertIn('name', form.errors)
        self.assertIn('strasse', form.errors)
        self.assertIn('plz', form.errors)
        self.assertIn('ort', form.errors)
        self.assertIn('land', form.errors)
    
    def test_form_optional_fields(self):
        """Test that optional fields work correctly."""
        form = AdresseForm(data={
            'name': 'Test Adresse',
            'strasse': 'Test Strasse 1',
            'plz': '12345',
            'ort': 'Test City',
            'land': 'Germany',
            'firma': 'Test Company',
            'anrede': 'HERR',
            'email': 'test@example.com',
            'telefon': '123456',
            'mobil': '654321',
            'bemerkung': 'Test note'
        })
        
        self.assertTrue(form.is_valid())
        adresse = form.save()
        
        self.assertEqual(adresse.firma, 'Test Company')
        self.assertEqual(adresse.anrede, 'HERR')
        self.assertEqual(adresse.email, 'test@example.com')
        self.assertEqual(adresse.telefon, '123456')
        self.assertEqual(adresse.mobil, '654321')
        self.assertEqual(adresse.bemerkung, 'Test note')
