"""
Tests for price_per_sqm field in MietObjekt (Rental Object).
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from core.models import Adresse
from vermietung.models import MietObjekt
from vermietung.forms import MietObjektForm
from decimal import Decimal


class PricePerSqmModelTestCase(TestCase):
    """Test case for price_per_sqm field in MietObjekt model."""
    
    def setUp(self):
        """Set up test data."""
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Test Standort',
            strasse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
    
    def test_price_per_sqm_can_be_null(self):
        """Test that price_per_sqm can be null."""
        objekt = MietObjekt.objects.create(
            name='Test Objekt',
            type='RAUM',
            beschreibung='Test',
            fläche=Decimal('50.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            price_per_sqm=None
        )
        self.assertIsNone(objekt.price_per_sqm)
    
    def test_price_per_sqm_can_be_set(self):
        """Test that price_per_sqm can be set to a valid positive value."""
        objekt = MietObjekt.objects.create(
            name='Test Objekt',
            type='RAUM',
            beschreibung='Test',
            fläche=Decimal('50.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            price_per_sqm=Decimal('20.00')
        )
        self.assertEqual(objekt.price_per_sqm, Decimal('20.00'))
    
    def test_price_per_sqm_zero_is_valid(self):
        """Test that price_per_sqm can be zero."""
        objekt = MietObjekt.objects.create(
            name='Test Objekt',
            type='RAUM',
            beschreibung='Test',
            fläche=Decimal('50.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            price_per_sqm=Decimal('0.00')
        )
        self.assertEqual(objekt.price_per_sqm, Decimal('0.00'))
    
    def test_price_per_sqm_negative_invalid(self):
        """Test that negative price_per_sqm values are rejected."""
        objekt = MietObjekt(
            name='Test Objekt',
            type='RAUM',
            beschreibung='Test',
            fläche=Decimal('50.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            price_per_sqm=Decimal('-10.00')
        )
        with self.assertRaises(ValidationError):
            objekt.full_clean()


class PricePerSqmFormTestCase(TestCase):
    """Test case for price_per_sqm field in MietObjektForm."""
    
    def setUp(self):
        """Set up test data."""
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Test Standort',
            strasse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
    
    def test_form_includes_price_per_sqm_field(self):
        """Test that the form includes price_per_sqm field."""
        form = MietObjektForm()
        self.assertIn('price_per_sqm', form.fields)
    
    def test_form_price_per_sqm_optional(self):
        """Test that price_per_sqm is optional in the form."""
        data = {
            'name': 'Test Objekt',
            'type': 'RAUM',
            'beschreibung': 'Test',
            'fläche': '50.00',
            'standort': self.standort.id,
            'mietpreis': '1000.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True
        }
        form = MietObjektForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_form_price_per_sqm_accepts_valid_value(self):
        """Test that the form accepts valid price_per_sqm values."""
        data = {
            'name': 'Test Objekt',
            'type': 'RAUM',
            'beschreibung': 'Test',
            'fläche': '50.00',
            'standort': self.standort.id,
            'mietpreis': '1000.00',
            'price_per_sqm': '20.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True
        }
        form = MietObjektForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        objekt = form.save()
        self.assertEqual(objekt.price_per_sqm, Decimal('20.00'))
    
    def test_form_price_per_sqm_rejects_negative(self):
        """Test that the form rejects negative price_per_sqm values."""
        data = {
            'name': 'Test Objekt',
            'type': 'RAUM',
            'beschreibung': 'Test',
            'fläche': '50.00',
            'standort': self.standort.id,
            'mietpreis': '1000.00',
            'price_per_sqm': '-10.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True
        }
        form = MietObjektForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('price_per_sqm', form.errors)


class PricePerSqmViewTestCase(TestCase):
    """Test case for price_per_sqm field in MietObjekt views."""
    
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
            name='Test Standort',
            strasse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create test MietObjekt with price_per_sqm
        self.objekt_with_price_per_sqm = MietObjekt.objects.create(
            name='Büro mit €/m²',
            type='RAUM',
            beschreibung='Test Objekt',
            fläche=Decimal('50.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            price_per_sqm=Decimal('20.00'),
            verfuegbar=True
        )
        
        # Create test MietObjekt without price_per_sqm
        self.objekt_without_price_per_sqm = MietObjekt.objects.create(
            name='Büro ohne €/m²',
            type='RAUM',
            beschreibung='Test Objekt',
            fläche=Decimal('50.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            verfuegbar=True
        )
        
        self.client = Client()
    
    def test_create_mietobjekt_with_price_per_sqm(self):
        """Test creating a MietObjekt with price_per_sqm."""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Neues Büro',
            'type': 'RAUM',
            'beschreibung': 'Test',
            'fläche': '60.00',
            'standort': self.standort.id,
            'mietpreis': '1200.00',
            'price_per_sqm': '25.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True
        }
        response = self.client.post(reverse('vermietung:mietobjekt_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that object was created with price_per_sqm
        objekt = MietObjekt.objects.get(name='Neues Büro')
        self.assertEqual(objekt.price_per_sqm, Decimal('25.00'))
    
    def test_create_mietobjekt_without_price_per_sqm(self):
        """Test creating a MietObjekt without price_per_sqm."""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Neues Büro ohne Preis',
            'type': 'RAUM',
            'beschreibung': 'Test',
            'fläche': '60.00',
            'standort': self.standort.id,
            'mietpreis': '1200.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True
        }
        response = self.client.post(reverse('vermietung:mietobjekt_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that object was created without price_per_sqm
        objekt = MietObjekt.objects.get(name='Neues Büro ohne Preis')
        self.assertIsNone(objekt.price_per_sqm)
    
    def test_edit_mietobjekt_add_price_per_sqm(self):
        """Test editing a MietObjekt to add price_per_sqm."""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': self.objekt_without_price_per_sqm.name,
            'type': self.objekt_without_price_per_sqm.type,
            'beschreibung': self.objekt_without_price_per_sqm.beschreibung,
            'fläche': str(self.objekt_without_price_per_sqm.fläche),
            'standort': self.standort.id,
            'mietpreis': str(self.objekt_without_price_per_sqm.mietpreis),
            'price_per_sqm': '22.00',
            'verfuegbare_einheiten': str(self.objekt_without_price_per_sqm.verfuegbare_einheiten),
            'verfuegbar': True
        }
        response = self.client.post(
            reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.objekt_without_price_per_sqm.pk}),
            data
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that price_per_sqm was added
        self.objekt_without_price_per_sqm.refresh_from_db()
        self.assertEqual(self.objekt_without_price_per_sqm.price_per_sqm, Decimal('22.00'))
    
    def test_detail_view_displays_price_per_sqm(self):
        """Test that detail view displays price_per_sqm when set."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.objekt_with_price_per_sqm.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '20')  # price_per_sqm value
        self.assertContains(response, '€/m²')
    
    def test_detail_view_without_price_per_sqm(self):
        """Test that detail view works correctly when price_per_sqm is not set."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.objekt_without_price_per_sqm.pk})
        )
        self.assertEqual(response.status_code, 200)
        # The page should not show the price_per_sqm row if it's not set
        # But it should still render without errors
        self.assertNotContains(response, '€/m² (eingegeben):')
    
    def test_form_view_includes_price_per_sqm_field(self):
        """Test that create form includes price_per_sqm field."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_price_per_sqm')
        self.assertContains(response, '€/m²')
