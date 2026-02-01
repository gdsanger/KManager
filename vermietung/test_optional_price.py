"""
Tests for optional mietpreis field in MietObjekt.
Tests the requirements from issue #219 - making price field optional.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.models import MietObjekt
from vermietung.forms import MietObjektForm
from decimal import Decimal


class MietObjektOptionalPriceTestCase(TestCase):
    """Test case for optional mietpreis field in MietObjekt."""
    
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
        
        # Create test standort (location)
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Teststandort',
            strasse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        self.client = Client()
    
    def test_create_mietobjekt_without_price_model(self):
        """
        TC1: Test that MietObjekt can be created without a price at model level.
        """
        objekt = MietObjekt.objects.create(
            name='Hauptobjekt ohne Preis',
            type='GEBAEUDE',
            beschreibung='Hauptgebäude ohne eigenen Mietpreis',
            standort=self.standort,
            mietpreis=None  # Explicitly set to None
        )
        
        self.assertIsNone(objekt.mietpreis)
        self.assertEqual(objekt.name, 'Hauptobjekt ohne Preis')
        # Verify object was saved correctly
        saved_objekt = MietObjekt.objects.get(pk=objekt.pk)
        self.assertIsNone(saved_objekt.mietpreis)
    
    def test_create_mietobjekt_with_price_model(self):
        """
        TC2: Test that MietObjekt can still be created with a price.
        """
        objekt = MietObjekt.objects.create(
            name='Objekt mit Preis',
            type='RAUM',
            beschreibung='Objekt mit Mietpreis',
            standort=self.standort,
            mietpreis=Decimal('1500.00')
        )
        
        self.assertEqual(objekt.mietpreis, Decimal('1500.00'))
        # Verify object was saved correctly
        saved_objekt = MietObjekt.objects.get(pk=objekt.pk)
        self.assertEqual(saved_objekt.mietpreis, Decimal('1500.00'))
    
    def test_qm_mietpreis_with_none_price(self):
        """
        Test that qm_mietpreis property handles None price correctly.
        """
        objekt = MietObjekt.objects.create(
            name='Objekt ohne Preis',
            type='GEBAEUDE',
            beschreibung='Test',
            standort=self.standort,
            fläche=Decimal('100.00'),
            mietpreis=None
        )
        
        # qm_mietpreis should return None when mietpreis is None
        self.assertIsNone(objekt.qm_mietpreis)
    
    def test_qm_mietpreis_with_price(self):
        """
        Test that qm_mietpreis property still works correctly with a price.
        """
        objekt = MietObjekt.objects.create(
            name='Objekt mit Preis',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort,
            fläche=Decimal('50.00'),
            mietpreis=Decimal('1000.00')
        )
        
        # qm_mietpreis should calculate correctly
        self.assertEqual(objekt.qm_mietpreis, Decimal('20.00'))
    
    def test_form_validation_without_price(self):
        """
        TC1 (Form): Test that MietObjektForm validates successfully without price.
        """
        form_data = {
            'name': 'Test Hauptobjekt',
            'type': 'GEBAEUDE',
            'beschreibung': 'Hauptobjekt ohne Preis',
            'standort': self.standort.pk,
            # mietpreis is intentionally omitted
            'verfuegbare_einheiten': 1,
            'verfuegbar': True,
            'is_mietobjekt': True,
        }
        
        form = MietObjektForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Save the form and check the object
        objekt = form.save()
        self.assertIsNone(objekt.mietpreis)
    
    def test_form_validation_with_price(self):
        """
        TC2 (Form): Test that MietObjektForm validates successfully with price.
        """
        form_data = {
            'name': 'Test Objekt',
            'type': 'RAUM',
            'beschreibung': 'Objekt mit Preis',
            'standort': self.standort.pk,
            'mietpreis': '1500.00',
            'verfuegbare_einheiten': 1,
            'verfuegbar': True,
            'is_mietobjekt': True,
        }
        
        form = MietObjektForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Save the form and check the object
        objekt = form.save()
        self.assertEqual(objekt.mietpreis, Decimal('1500.00'))
    
    def test_form_validation_with_invalid_price(self):
        """
        TC3: Test that MietObjektForm rejects invalid price values.
        """
        form_data = {
            'name': 'Test Objekt',
            'type': 'RAUM',
            'beschreibung': 'Objekt mit ungültigem Preis',
            'standort': self.standort.pk,
            'mietpreis': 'invalid',
            'verfuegbare_einheiten': 1,
            'verfuegbar': True,
            'is_mietobjekt': True,
        }
        
        form = MietObjektForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('mietpreis', form.errors)
    
    def test_create_view_without_price(self):
        """
        TC1 (View): Test creating MietObjekt via view without price.
        """
        self.client.login(username='testuser', password='testpass123')
        
        post_data = {
            'name': 'Hauptobjekt Web',
            'type': 'GEBAEUDE',
            'beschreibung': 'Hauptobjekt ohne Preis über Web-Interface',
            'standort': self.standort.pk,
            # mietpreis is intentionally omitted
            'verfuegbare_einheiten': 1,
            'verfuegbar': True,
            'is_mietobjekt': True,
        }
        
        response = self.client.post(reverse('vermietung:mietobjekt_create'), data=post_data)
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        # Check that object was created
        objekt = MietObjekt.objects.get(name='Hauptobjekt Web')
        self.assertIsNone(objekt.mietpreis)
    
    def test_edit_view_remove_price(self):
        """
        TC4: Test that price can be removed from existing MietObjekt via edit view.
        """
        # Create an object with a price
        objekt = MietObjekt.objects.create(
            name='Objekt zum Bearbeiten',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=Decimal('1000.00')
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Edit to remove price
        post_data = {
            'name': 'Objekt zum Bearbeiten',
            'type': 'RAUM',
            'beschreibung': 'Test',
            'standort': self.standort.pk,
            'mietpreis': '',  # Empty string to remove price
            'verfuegbare_einheiten': 1,
            'verfuegbar': True,
            'is_mietobjekt': True,
        }
        
        response = self.client.post(
            reverse('vermietung:mietobjekt_edit', kwargs={'pk': objekt.pk}),
            data=post_data
        )
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        # Check that price was removed
        objekt.refresh_from_db()
        self.assertIsNone(objekt.mietpreis)
    
    def test_list_view_displays_none_price(self):
        """
        TC5: Test that list view displays objects without price correctly.
        """
        # Create object without price
        MietObjekt.objects.create(
            name='Objekt ohne Preis',
            type='GEBAEUDE',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=None
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_list'))
        
        self.assertEqual(response.status_code, 200)
        # Should not cause any errors
        self.assertContains(response, 'Objekt ohne Preis')
        # Should display em-dash or similar placeholder
        self.assertContains(response, '—')
    
    def test_detail_view_displays_none_price(self):
        """
        TC3: Test that detail view displays object without price correctly.
        """
        objekt = MietObjekt.objects.create(
            name='Objekt ohne Preis Detail',
            type='GEBAEUDE',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=None
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_detail', kwargs={'pk': objekt.pk}))
        
        self.assertEqual(response.status_code, 200)
        # Should not cause any errors
        self.assertContains(response, 'Objekt ohne Preis Detail')
        # Should display em-dash or similar placeholder for price
        self.assertContains(response, '—')
    
    def test_hierarchical_object_without_price(self):
        """
        Test creating a hierarchical structure with parent object without price.
        This is the main use case from issue #219.
        """
        # Create parent object (main building) without price
        parent = MietObjekt.objects.create(
            name='Katzensteinstr. 2 Komplett',
            type='GEBAEUDE',
            beschreibung='Hauptgebäude',
            standort=self.standort,
            mietpreis=None,  # Main building has no own price
            is_mietobjekt=True
        )
        
        # Create child object (apartment) with price
        child = MietObjekt.objects.create(
            name='Einliegerwohnung',
            type='RAUM',
            beschreibung='Wohnung im Erdgeschoss',
            standort=self.standort,
            mietpreis=Decimal('800.00'),
            parent=parent,
            is_mietobjekt=True
        )
        
        # Verify structure
        self.assertIsNone(parent.mietpreis)
        self.assertEqual(child.mietpreis, Decimal('800.00'))
        self.assertEqual(child.parent, parent)
