"""
Tests for Customer (Kunde) CRUD functionality in the user area.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.forms import AdresseKundeForm


class KundeCRUDTestCase(TestCase):
    """Test case for Customer CRUD operations in the user area."""
    
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
        
        # Create test customers
        self.kunde1 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com',
            telefon='0123456789'
        )
        
        self.kunde2 = Adresse.objects.create(
            adressen_type='KUNDE',
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
        
        # Create a non-customer address (should not appear in customer list)
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant GmbH',
            strasse='Lieferstrasse 3',
            plz='11111',
            ort='Lieferstadt',
            land='Deutschland'
        )
        
        self.client = Client()
    
    def test_kunde_list_requires_authentication(self):
        """Test that kunde_list view requires authentication."""
        response = self.client.get(reverse('vermietung:kunde_list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_kunde_list_requires_vermietung_access(self):
        """Test that kunde_list view requires Vermietung access."""
        # Login as regular user without Vermietung access
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('vermietung:kunde_list'))
        # Should redirect to login (permission denied)
        self.assertEqual(response.status_code, 302)
    
    def test_kunde_list_shows_only_kunden(self):
        """Test that kunde_list view shows only KUNDE addresses."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:kunde_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        self.assertContains(response, 'John Doe')
        # Should not contain the Lieferant
        self.assertNotContains(response, 'Lieferant GmbH')
    
    def test_kunde_list_search(self):
        """Test that kunde_list search functionality works."""
        self.client.login(username='testuser', password='testpass123')
        
        # Search by name
        response = self.client.get(reverse('vermietung:kunde_list'), {'q': 'Max'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        self.assertNotContains(response, 'John Doe')
        
        # Search by email
        response = self.client.get(reverse('vermietung:kunde_list'), {'q': 'musterfirma.de'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')
        self.assertNotContains(response, 'Max Mustermann')
        
        # Search by city
        response = self.client.get(reverse('vermietung:kunde_list'), {'q': 'Musterstadt'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
    
    def test_kunde_list_pagination(self):
        """Test that kunde_list pagination works."""
        # Create more customers to test pagination
        for i in range(25):
            Adresse.objects.create(
                adressen_type='KUNDE',
                name=f'Kunde {i}',
                strasse=f'Strasse {i}',
                plz='12345',
                ort='Stadt',
                land='Deutschland'
            )
        
        self.client.login(username='testuser', password='testpass123')
        
        # First page
        response = self.client.get(reverse('vermietung:kunde_list'))
        self.assertEqual(response.status_code, 200)
        # Should have 20 customers per page (2 existing + 18 from the loop)
        self.assertEqual(len(response.context['page_obj']), 20)
        
        # Second page
        response = self.client.get(reverse('vermietung:kunde_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        # Should have remaining customers
        self.assertEqual(len(response.context['page_obj']), 7)
    
    def test_kunde_detail_view(self):
        """Test that kunde_detail view shows customer details."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:kunde_detail', kwargs={'pk': self.kunde1.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        self.assertContains(response, 'Musterstrasse 1')
        self.assertContains(response, '12345')
        self.assertContains(response, 'Musterstadt')
        self.assertContains(response, 'max@example.com')
    
    def test_kunde_detail_only_shows_kunden(self):
        """Test that kunde_detail view only shows KUNDE addresses."""
        self.client.login(username='testuser', password='testpass123')
        # Try to access Lieferant through kunde_detail
        response = self.client.get(reverse('vermietung:kunde_detail', kwargs={'pk': self.lieferant.pk}))
        
        # Should return 404 as it's not a KUNDE
        self.assertEqual(response.status_code, 404)
    
    def test_kunde_create_view(self):
        """Test that kunde_create view works."""
        self.client.login(username='testuser', password='testpass123')
        
        # GET request
        response = self.client.get(reverse('vermietung:kunde_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neuer Kunde')
        
        # POST request with valid data
        kunde_data = {
            'name': 'Test Kunde',
            'strasse': 'Teststrasse 123',
            'plz': '99999',
            'ort': 'Testort',
            'land': 'Deutschland',
            'email': 'test@example.com',
            'telefon': '0123456789'
        }
        response = self.client.post(reverse('vermietung:kunde_create'), kunde_data)
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify kunde was created
        kunde = Adresse.objects.get(name='Test Kunde')
        self.assertEqual(kunde.adressen_type, 'KUNDE')
        self.assertEqual(kunde.email, 'test@example.com')
    
    def test_kunde_edit_view(self):
        """Test that kunde_edit view works."""
        self.client.login(username='testuser', password='testpass123')
        
        # GET request
        response = self.client.get(reverse('vermietung:kunde_edit', kwargs={'pk': self.kunde1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Max Mustermann')
        
        # POST request with updated data
        updated_data = {
            'name': 'Max Mustermann Updated',
            'strasse': 'Neue Strasse 456',
            'plz': '12345',
            'ort': 'Musterstadt',
            'land': 'Deutschland',
            'email': 'max.updated@example.com'
        }
        response = self.client.post(
            reverse('vermietung:kunde_edit', kwargs={'pk': self.kunde1.pk}),
            updated_data
        )
        
        # Should redirect to detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify kunde was updated
        self.kunde1.refresh_from_db()
        self.assertEqual(self.kunde1.name, 'Max Mustermann Updated')
        self.assertEqual(self.kunde1.strasse, 'Neue Strasse 456')
        self.assertEqual(self.kunde1.email, 'max.updated@example.com')
        # adressen_type should still be KUNDE
        self.assertEqual(self.kunde1.adressen_type, 'KUNDE')
    
    def test_kunde_edit_only_edits_kunden(self):
        """Test that kunde_edit view only edits KUNDE addresses."""
        self.client.login(username='testuser', password='testpass123')
        
        # Try to edit Lieferant through kunde_edit
        response = self.client.get(reverse('vermietung:kunde_edit', kwargs={'pk': self.lieferant.pk}))
        
        # Should return 404 as it's not a KUNDE
        self.assertEqual(response.status_code, 404)
    
    def test_kunde_delete_view(self):
        """Test that kunde_delete view works."""
        self.client.login(username='testuser', password='testpass123')
        
        # POST request to delete
        kunde_pk = self.kunde1.pk
        response = self.client.post(reverse('vermietung:kunde_delete', kwargs={'pk': kunde_pk}))
        
        # Should redirect to list page
        self.assertEqual(response.status_code, 302)
        self.assertIn('kunde', response.url)
        
        # Verify kunde was deleted
        self.assertFalse(Adresse.objects.filter(pk=kunde_pk).exists())
    
    def test_kunde_delete_only_deletes_kunden(self):
        """Test that kunde_delete view only deletes KUNDE addresses."""
        self.client.login(username='testuser', password='testpass123')
        
        lieferant_pk = self.lieferant.pk
        # Try to delete Lieferant through kunde_delete
        response = self.client.post(reverse('vermietung:kunde_delete', kwargs={'pk': lieferant_pk}))
        
        # Should return 404 as it's not a KUNDE
        self.assertEqual(response.status_code, 404)
        
        # Verify Lieferant was not deleted
        self.assertTrue(Adresse.objects.filter(pk=lieferant_pk).exists())
    
    def test_kunde_delete_requires_post(self):
        """Test that kunde_delete view requires POST method."""
        self.client.login(username='testuser', password='testpass123')
        
        # GET request should not be allowed
        response = self.client.get(reverse('vermietung:kunde_delete', kwargs={'pk': self.kunde1.pk}))
        
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
        
        # Verify kunde was not deleted
        self.assertTrue(Adresse.objects.filter(pk=self.kunde1.pk).exists())


class AdresseKundeFormTestCase(TestCase):
    """Test case for AdresseKundeForm."""
    
    def test_form_saves_with_kunde_type(self):
        """Test that form automatically sets adressen_type to KUNDE."""
        form_data = {
            'name': 'Form Test Kunde',
            'strasse': 'Formstrasse 1',
            'plz': '11111',
            'ort': 'Formstadt',
            'land': 'Deutschland'
        }
        form = AdresseKundeForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        kunde = form.save()
        
        # Verify adressen_type is KUNDE
        self.assertEqual(kunde.adressen_type, 'KUNDE')
    
    def test_form_validates_required_fields(self):
        """Test that form validates required fields."""
        # Missing required fields
        form_data = {
            'name': 'Test',
            # Missing strasse, plz, ort, land
        }
        form = AdresseKundeForm(data=form_data)
        
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
            'name': 'Form Test Kunde',
            'strasse': 'Formstrasse 1',
            'plz': '11111',
            'ort': 'Formstadt',
            'land': 'Deutschland',
            'telefon': '0123456789',
            'mobil': '0987654321',
            'email': 'optional@example.com',
            'bemerkung': 'Optional bemerkung'
        }
        form = AdresseKundeForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        kunde = form.save()
        
        self.assertEqual(kunde.firma, 'Optional Firma')
        self.assertEqual(kunde.anrede, 'FRAU')
        self.assertEqual(kunde.telefon, '0123456789')
        self.assertEqual(kunde.mobil, '0987654321')
        self.assertEqual(kunde.email, 'optional@example.com')
        self.assertEqual(kunde.bemerkung, 'Optional bemerkung')
    
    def test_form_updates_existing_kunde(self):
        """Test that form can update existing kunde without changing type."""
        # Create a kunde
        kunde = Adresse.objects.create(
            adressen_type='KUNDE',
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
        form = AdresseKundeForm(data=form_data, instance=kunde)
        
        self.assertTrue(form.is_valid())
        updated_kunde = form.save()
        
        # Verify updates
        self.assertEqual(updated_kunde.name, 'Updated Name')
        self.assertEqual(updated_kunde.strasse, 'Updated Strasse')
        # adressen_type should still be KUNDE
        self.assertEqual(updated_kunde.adressen_type, 'KUNDE')
    
    def test_form_with_tax_fields(self):
        """Test that form accepts and saves tax and accounting fields."""
        form_data = {
            'name': 'Tax Test Kunde',
            'strasse': 'Steuerstrasse 1',
            'plz': '11111',
            'ort': 'Steuerstadt',
            'land': 'Deutschland',
            'country_code': 'DE',
            'vat_id': 'DE123456789',
            'is_eu': True,
            'is_business': True,
            'debitor_number': 'DEB-2024-001'
        }
        form = AdresseKundeForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        kunde = form.save()
        
        self.assertEqual(kunde.country_code, 'DE')
        self.assertEqual(kunde.vat_id, 'DE123456789')
        self.assertTrue(kunde.is_eu)
        self.assertTrue(kunde.is_business)
        self.assertEqual(kunde.debitor_number, 'DEB-2024-001')
    
    def test_form_tax_fields_optional(self):
        """Test that tax and accounting fields are optional."""
        form_data = {
            'name': 'Simple Kunde',
            'strasse': 'Einfachstrasse 1',
            'plz': '11111',
            'ort': 'Einfachstadt',
            'land': 'Deutschland',
            # Checkboxes: False when not provided in form data
            'is_business': True,  # Explicitly set
            'is_eu': False,  # Explicitly set
        }
        form = AdresseKundeForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        kunde = form.save()
        
        # Should have values as set
        self.assertEqual(kunde.country_code, 'DE')  # default
        self.assertFalse(kunde.is_eu)
        self.assertTrue(kunde.is_business)
