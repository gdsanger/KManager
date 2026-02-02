"""
Tests for AdresseKontakt model and CRUD operations.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from core.models import Adresse, AdresseKontakt


class AdresseKontaktModelTestCase(TestCase):
    """Test AdresseKontakt model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.adresse = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststraße 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
    
    def test_create_kontakt_telefon(self):
        """Test creating a TELEFON contact"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='TELEFON',
            name='Max Mustermann',
            position='Geschäftsführer',
            kontakt='+49 123 456789'
        )
        self.assertEqual(kontakt.adresse, self.adresse)
        self.assertEqual(kontakt.type, 'TELEFON')
        self.assertEqual(kontakt.name, 'Max Mustermann')
        self.assertEqual(kontakt.position, 'Geschäftsführer')
        self.assertEqual(kontakt.kontakt, '+49 123 456789')
    
    def test_create_kontakt_email(self):
        """Test creating an EMAIL contact"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='EMAIL',
            kontakt='test@example.com'
        )
        self.assertEqual(kontakt.type, 'EMAIL')
        self.assertEqual(kontakt.kontakt, 'test@example.com')
    
    def test_kontakt_email_validation(self):
        """Test email validation for EMAIL type contacts"""
        kontakt = AdresseKontakt(
            adresse=self.adresse,
            type='EMAIL',
            kontakt='invalid-email'
        )
        with self.assertRaises(ValidationError) as context:
            kontakt.full_clean()
        self.assertIn('kontakt', context.exception.message_dict)
    
    def test_kontakt_email_validation_valid(self):
        """Test that valid email passes validation"""
        kontakt = AdresseKontakt(
            adresse=self.adresse,
            type='EMAIL',
            kontakt='valid@example.com'
        )
        try:
            kontakt.full_clean()
        except ValidationError:
            self.fail('Valid email should not raise ValidationError')
    
    def test_kontakt_str_with_name(self):
        """Test __str__ method with name"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='TELEFON',
            name='Max Mustermann',
            kontakt='+49 123 456789'
        )
        expected = 'Telefon: Max Mustermann (+49 123 456789)'
        self.assertEqual(str(kontakt), expected)
    
    def test_kontakt_str_without_name(self):
        """Test __str__ method without name"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='EMAIL',
            kontakt='test@example.com'
        )
        expected = 'E-Mail: test@example.com'
        self.assertEqual(str(kontakt), expected)
    
    def test_kontakt_cascade_delete(self):
        """Test that contacts are deleted when address is deleted"""
        kontakt1 = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='TELEFON',
            kontakt='+49 123 456789'
        )
        kontakt2 = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='EMAIL',
            kontakt='test@example.com'
        )
        
        self.assertEqual(AdresseKontakt.objects.count(), 2)
        
        # Delete address
        self.adresse.delete()
        
        # Verify contacts are also deleted
        self.assertEqual(AdresseKontakt.objects.count(), 0)
    
    def test_kontakt_ordering(self):
        """Test that contacts are ordered by type and name"""
        kontakt1 = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='MOBIL',
            name='Z Person',
            kontakt='+49 111'
        )
        kontakt2 = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='EMAIL',
            name='A Person',
            kontakt='a@test.com'
        )
        kontakt3 = AdresseKontakt.objects.create(
            adresse=self.adresse,
            type='EMAIL',
            name='B Person',
            kontakt='b@test.com'
        )
        
        kontakte = list(AdresseKontakt.objects.all())
        # Should be ordered by type (EMAIL before MOBIL), then by name
        self.assertEqual(kontakte[0], kontakt2)  # EMAIL, A Person
        self.assertEqual(kontakte[1], kontakt3)  # EMAIL, B Person
        self.assertEqual(kontakte[2], kontakt1)  # MOBIL, Z Person


class AdresseKontaktCRUDTestCase(TestCase):
    """Test CRUD operations for contacts"""
    
    def setUp(self):
        """Set up test data and authenticated user"""
        # Create user with Vermietung group
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test addresses
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststraße 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Test Lieferant',
            strasse='Lieferantenweg 1',
            plz='54321',
            ort='Lieferstadt',
            land='Deutschland'
        )
    
    def test_create_kontakt_requires_authentication(self):
        """Test that creating a contact requires authentication"""
        self.client.logout()
        url = reverse('vermietung:kontakt_create', kwargs={'adresse_pk': self.kunde.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_create_kontakt_get(self):
        """Test GET request to create contact form"""
        url = reverse('vermietung:kontakt_create', kwargs={'adresse_pk': self.kunde.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/kontakte/form.html')
        self.assertIn('form', response.context)
        self.assertEqual(response.context['adresse'], self.kunde)
        self.assertTrue(response.context['is_create'])
    
    def test_create_kontakt_post(self):
        """Test POST request to create contact"""
        url = reverse('vermietung:kontakt_create', kwargs={'adresse_pk': self.kunde.pk})
        data = {
            'type': 'TELEFON',
            'name': 'Max Mustermann',
            'position': 'Geschäftsführer',
            'kontakt': '+49 123 456789'
        }
        response = self.client.post(url, data)
        
        # Should redirect to kunde detail
        self.assertRedirects(response, reverse('vermietung:kunde_detail', kwargs={'pk': self.kunde.pk}))
        
        # Verify contact was created
        self.assertEqual(AdresseKontakt.objects.count(), 1)
        kontakt = AdresseKontakt.objects.first()
        self.assertEqual(kontakt.adresse, self.kunde)
        self.assertEqual(kontakt.type, 'TELEFON')
        self.assertEqual(kontakt.name, 'Max Mustermann')
        self.assertEqual(kontakt.position, 'Geschäftsführer')
        self.assertEqual(kontakt.kontakt, '+49 123 456789')
    
    def test_create_kontakt_email_validation(self):
        """Test that invalid email is rejected"""
        url = reverse('vermietung:kontakt_create', kwargs={'adresse_pk': self.kunde.pk})
        data = {
            'type': 'EMAIL',
            'kontakt': 'invalid-email'
        }
        response = self.client.post(url, data)
        
        # Should not redirect (form has errors)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'kontakt', 'Bitte geben Sie eine gültige E-Mail-Adresse ein.')
        
        # Verify contact was not created
        self.assertEqual(AdresseKontakt.objects.count(), 0)
    
    def test_create_kontakt_for_lieferant(self):
        """Test creating contact for LIEFERANT redirects correctly"""
        url = reverse('vermietung:kontakt_create', kwargs={'adresse_pk': self.lieferant.pk})
        data = {
            'type': 'EMAIL',
            'kontakt': 'lieferant@example.com'
        }
        response = self.client.post(url, data)
        
        # Should redirect to lieferant detail
        self.assertRedirects(response, reverse('vermietung:lieferant_detail', kwargs={'pk': self.lieferant.pk}))
    
    def test_edit_kontakt_get(self):
        """Test GET request to edit contact form"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.kunde,
            type='TELEFON',
            name='Max Mustermann',
            kontakt='+49 123 456789'
        )
        
        url = reverse('vermietung:kontakt_edit', kwargs={'pk': kontakt.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/kontakte/form.html')
        self.assertIn('form', response.context)
        self.assertEqual(response.context['kontakt'], kontakt)
        self.assertFalse(response.context['is_create'])
    
    def test_edit_kontakt_post(self):
        """Test POST request to edit contact"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.kunde,
            type='TELEFON',
            name='Max Mustermann',
            kontakt='+49 123 456789'
        )
        
        url = reverse('vermietung:kontakt_edit', kwargs={'pk': kontakt.pk})
        data = {
            'type': 'MOBIL',
            'name': 'Max Mustermann Updated',
            'position': 'CEO',
            'kontakt': '+49 987 654321'
        }
        response = self.client.post(url, data)
        
        # Should redirect to kunde detail
        self.assertRedirects(response, reverse('vermietung:kunde_detail', kwargs={'pk': self.kunde.pk}))
        
        # Verify contact was updated
        kontakt.refresh_from_db()
        self.assertEqual(kontakt.type, 'MOBIL')
        self.assertEqual(kontakt.name, 'Max Mustermann Updated')
        self.assertEqual(kontakt.position, 'CEO')
        self.assertEqual(kontakt.kontakt, '+49 987 654321')
    
    def test_delete_kontakt(self):
        """Test deleting a contact"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.kunde,
            type='TELEFON',
            kontakt='+49 123 456789'
        )
        
        url = reverse('vermietung:kontakt_delete', kwargs={'pk': kontakt.pk})
        response = self.client.post(url)
        
        # Should redirect to kunde detail
        self.assertRedirects(response, reverse('vermietung:kunde_detail', kwargs={'pk': self.kunde.pk}))
        
        # Verify contact was deleted
        self.assertEqual(AdresseKontakt.objects.count(), 0)
    
    def test_delete_kontakt_requires_post(self):
        """Test that deleting a contact requires POST method"""
        kontakt = AdresseKontakt.objects.create(
            adresse=self.kunde,
            type='TELEFON',
            kontakt='+49 123 456789'
        )
        
        url = reverse('vermietung:kontakt_delete', kwargs={'pk': kontakt.pk})
        response = self.client.get(url)
        
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
        
        # Verify contact was not deleted
        self.assertEqual(AdresseKontakt.objects.count(), 1)
    
    def test_kontakt_list_in_adresse_detail(self):
        """Test that contacts are displayed in address detail view"""
        kontakt1 = AdresseKontakt.objects.create(
            adresse=self.kunde,
            type='TELEFON',
            name='Person 1',
            kontakt='+49 111'
        )
        kontakt2 = AdresseKontakt.objects.create(
            adresse=self.kunde,
            type='EMAIL',
            name='Person 2',
            kontakt='test@example.com'
        )
        
        url = reverse('vermietung:kunde_detail', kwargs={'pk': self.kunde.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Person 1')
        self.assertContains(response, 'Person 2')
        self.assertContains(response, '+49 111')
        self.assertContains(response, 'test@example.com')
    
    def test_kontakt_required_fields(self):
        """Test that required fields are enforced"""
        url = reverse('vermietung:kontakt_create', kwargs={'adresse_pk': self.kunde.pk})
        
        # Missing type
        data = {
            'kontakt': '+49 123 456789'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'type', 'Dieses Feld ist zwingend erforderlich.')
        
        # Missing kontakt
        data = {
            'type': 'TELEFON'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'kontakt', 'Dieses Feld ist zwingend erforderlich.')
