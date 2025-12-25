"""
Tests for Supplier (Lieferant) CRUD functionality in the user area.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.forms import AdresseLieferantForm


class LieferantCRUDTestCase(TestCase):
    """Test case for Supplier CRUD operations in the user area."""
    
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
        
        # Create test suppliers
        self.lieferant1 = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant Eins',
            strasse='Lieferstrasse 1',
            plz='12345',
            ort='Lieferstadt',
            land='Deutschland',
            email='lieferant1@example.com',
            telefon='0123456789'
        )
        
        self.lieferant2 = Adresse.objects.create(
            adressen_type='LIEFERANT',
            firma='Lieferant GmbH',
            anrede='HERR',
            name='Hans Müller',
            strasse='Teststrasse 2',
            plz='54321',
            ort='Teststadt',
            land='Deutschland',
            email='hans@lieferant.de',
            mobil='0987654321'
        )
        
        # Create a non-supplier address (should not appear in supplier list)
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde GmbH',
            strasse='Kundestrasse 3',
            plz='11111',
            ort='Kundestadt',
            land='Deutschland'
        )
        
        self.client = Client()
    
    def test_lieferant_list_requires_authentication(self):
        """Test that lieferant_list view requires authentication."""
        response = self.client.get(reverse('vermietung:lieferant_list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_lieferant_list_requires_vermietung_access(self):
        """Test that lieferant_list view requires Vermietung access."""
        # Login as regular user without Vermietung access
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('vermietung:lieferant_list'))
        # Should redirect to login (permission denied)
        self.assertEqual(response.status_code, 302)
    
    def test_lieferant_list_shows_only_lieferanten(self):
        """Test that lieferant_list view shows only LIEFERANT addresses."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:lieferant_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lieferant Eins')
        self.assertContains(response, 'Hans Müller')
        # Should not contain the Kunde
        self.assertNotContains(response, 'Kunde GmbH')
    
    def test_lieferant_list_search(self):
        """Test that lieferant_list search functionality works."""
        self.client.login(username='testuser', password='testpass123')
        
        # Search by name
        response = self.client.get(reverse('vermietung:lieferant_list'), {'q': 'Eins'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lieferant Eins')
        self.assertNotContains(response, 'Hans Müller')
        
        # Search by email
        response = self.client.get(reverse('vermietung:lieferant_list'), {'q': 'hans@lieferant.de'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hans Müller')
        self.assertNotContains(response, 'Lieferant Eins')
        
        # Search by city
        response = self.client.get(reverse('vermietung:lieferant_list'), {'q': 'Lieferstadt'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lieferant Eins')
    
    def test_lieferant_list_pagination(self):
        """Test that lieferant_list pagination works."""
        # Create more suppliers to test pagination
        for i in range(25):
            Adresse.objects.create(
                adressen_type='LIEFERANT',
                name=f'Lieferant {i}',
                strasse=f'Strasse {i}',
                plz='12345',
                ort='Stadt',
                land='Deutschland'
            )
        
        self.client.login(username='testuser', password='testpass123')
        
        # First page
        response = self.client.get(reverse('vermietung:lieferant_list'))
        self.assertEqual(response.status_code, 200)
        # Should have 20 suppliers per page (2 existing + 18 from the loop)
        self.assertEqual(len(response.context['page_obj']), 20)
        
        # Second page
        response = self.client.get(reverse('vermietung:lieferant_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        # Should have remaining suppliers
        self.assertEqual(len(response.context['page_obj']), 7)
    
    def test_lieferant_detail_view(self):
        """Test that lieferant_detail view shows supplier details."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:lieferant_detail', kwargs={'pk': self.lieferant1.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lieferant Eins')
        self.assertContains(response, 'Lieferstrasse 1')
        self.assertContains(response, '12345')
        self.assertContains(response, 'Lieferstadt')
        self.assertContains(response, 'lieferant1@example.com')
    
    def test_lieferant_detail_only_shows_lieferanten(self):
        """Test that lieferant_detail view only shows LIEFERANT addresses."""
        self.client.login(username='testuser', password='testpass123')
        # Try to access Kunde through lieferant_detail
        response = self.client.get(reverse('vermietung:lieferant_detail', kwargs={'pk': self.kunde.pk}))
        
        # Should return 404 as it's not a LIEFERANT
        self.assertEqual(response.status_code, 404)
    
    def test_lieferant_create_view(self):
        """Test that lieferant_create view works."""
        self.client.login(username='testuser', password='testpass123')
        
        # GET request
        response = self.client.get(reverse('vermietung:lieferant_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neuer Lieferant')
        
        # POST request with valid data
        lieferant_data = {
            'name': 'Test Lieferant',
            'strasse': 'Teststrasse 123',
            'plz': '99999',
            'ort': 'Testort',
            'land': 'Deutschland',
            'email': 'test@example.com',
            'telefon': '0123456789'
        }
        response = self.client.post(reverse('vermietung:lieferant_create'), lieferant_data)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify lieferant was created
        lieferant = Adresse.objects.get(name='Test Lieferant')
        self.assertEqual(lieferant.adressen_type, 'LIEFERANT')
        self.assertEqual(lieferant.email, 'test@example.com')
    
    def test_lieferant_edit_view(self):
        """Test that lieferant_edit view works."""
        self.client.login(username='testuser', password='testpass123')
        
        # GET request
        response = self.client.get(reverse('vermietung:lieferant_edit', kwargs={'pk': self.lieferant1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lieferant Eins')
        
        # POST request with updated data
        updated_data = {
            'name': 'Lieferant Eins Updated',
            'strasse': 'Neue Strasse 456',
            'plz': '12345',
            'ort': 'Lieferstadt',
            'land': 'Deutschland',
            'email': 'updated@example.com'
        }
        response = self.client.post(
            reverse('vermietung:lieferant_edit', kwargs={'pk': self.lieferant1.pk}),
            updated_data
        )
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify lieferant was updated
        self.lieferant1.refresh_from_db()
        self.assertEqual(self.lieferant1.name, 'Lieferant Eins Updated')
        self.assertEqual(self.lieferant1.strasse, 'Neue Strasse 456')
        self.assertEqual(self.lieferant1.email, 'updated@example.com')
        # adressen_type should still be LIEFERANT
        self.assertEqual(self.lieferant1.adressen_type, 'LIEFERANT')
    
    def test_lieferant_edit_only_edits_lieferanten(self):
        """Test that lieferant_edit view only edits LIEFERANT addresses."""
        self.client.login(username='testuser', password='testpass123')
        
        # Try to edit Kunde through lieferant_edit
        response = self.client.get(reverse('vermietung:lieferant_edit', kwargs={'pk': self.kunde.pk}))
        
        # Should return 404 as it's not a LIEFERANT
        self.assertEqual(response.status_code, 404)
    
    def test_lieferant_delete_view(self):
        """Test that lieferant_delete view works."""
        self.client.login(username='testuser', password='testpass123')
        
        # POST request to delete
        lieferant_pk = self.lieferant1.pk
        response = self.client.post(reverse('vermietung:lieferant_delete', kwargs={'pk': lieferant_pk}))
        
        # Should redirect to list page
        self.assertEqual(response.status_code, 302)
        self.assertIn('lieferant', response.url)
        
        # Verify lieferant was deleted
        self.assertFalse(Adresse.objects.filter(pk=lieferant_pk).exists())
    
    def test_lieferant_delete_only_deletes_lieferanten(self):
        """Test that lieferant_delete view only deletes LIEFERANT addresses."""
        self.client.login(username='testuser', password='testpass123')
        
        kunde_pk = self.kunde.pk
        # Try to delete Kunde through lieferant_delete
        response = self.client.post(reverse('vermietung:lieferant_delete', kwargs={'pk': kunde_pk}))
        
        # Should return 404 as it's not a LIEFERANT
        self.assertEqual(response.status_code, 404)
        
        # Verify Kunde was not deleted
        self.assertTrue(Adresse.objects.filter(pk=kunde_pk).exists())
    
    def test_lieferant_delete_requires_post(self):
        """Test that lieferant_delete view requires POST method."""
        self.client.login(username='testuser', password='testpass123')
        
        # GET request should not be allowed
        response = self.client.get(reverse('vermietung:lieferant_delete', kwargs={'pk': self.lieferant1.pk}))
        
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
        
        # Verify lieferant was not deleted
        self.assertTrue(Adresse.objects.filter(pk=self.lieferant1.pk).exists())


class AdresseLieferantFormTestCase(TestCase):
    """Test case for AdresseLieferantForm."""
    
    def test_form_saves_with_lieferant_type(self):
        """Test that form automatically sets adressen_type to LIEFERANT."""
        form_data = {
            'name': 'Form Test Lieferant',
            'strasse': 'Formstrasse 1',
            'plz': '11111',
            'ort': 'Formstadt',
            'land': 'Deutschland'
        }
        form = AdresseLieferantForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        lieferant = form.save()
        
        # Verify adressen_type is LIEFERANT
        self.assertEqual(lieferant.adressen_type, 'LIEFERANT')
    
    def test_form_validates_required_fields(self):
        """Test that form validates required fields."""
        # Missing required fields
        form_data = {
            'name': 'Test',
            # Missing strasse, plz, ort, land
        }
        form = AdresseLieferantForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('strasse', form.errors)
        self.assertIn('plz', form.errors)
        self.assertIn('ort', form.errors)
        self.assertIn('land', form.errors)
    
    def test_form_accepts_optional_fields(self):
        """Test that form accepts optional fields."""
        form_data = {
            'firma': 'Optional Firma',
            'anrede': 'FRAU',
            'name': 'Form Test Lieferant',
            'strasse': 'Formstrasse 1',
            'plz': '11111',
            'ort': 'Formstadt',
            'land': 'Deutschland',
            'telefon': '0123456789',
            'mobil': '0987654321',
            'email': 'optional@example.com',
            'bemerkung': 'Optional bemerkung'
        }
        form = AdresseLieferantForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        lieferant = form.save()
        
        self.assertEqual(lieferant.firma, 'Optional Firma')
        self.assertEqual(lieferant.anrede, 'FRAU')
        self.assertEqual(lieferant.telefon, '0123456789')
        self.assertEqual(lieferant.mobil, '0987654321')
        self.assertEqual(lieferant.email, 'optional@example.com')
        self.assertEqual(lieferant.bemerkung, 'Optional bemerkung')
    
    def test_form_updates_existing_lieferant(self):
        """Test that form can update existing lieferant without changing type."""
        # Create a lieferant
        lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Original Name',
            strasse='Original Strasse',
            plz='11111',
            ort='Original Ort',
            land='Deutschland'
        )
        
        # Update using form
        form_data = {
            'name': 'Updated Name',
            'strasse': 'Updated Strasse',
            'plz': '22222',
            'ort': 'Updated Ort',
            'land': 'Deutschland'
        }
        form = AdresseLieferantForm(data=form_data, instance=lieferant)
        
        self.assertTrue(form.is_valid())
        updated_lieferant = form.save()
        
        # Verify updates
        self.assertEqual(updated_lieferant.name, 'Updated Name')
        self.assertEqual(updated_lieferant.strasse, 'Updated Strasse')
        # adressen_type should still be LIEFERANT
        self.assertEqual(updated_lieferant.adressen_type, 'LIEFERANT')
