"""
Tests for MietObjekt (Rental Object) CRUD functionality in the user area.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag
from vermietung.forms import MietObjektForm
from decimal import Decimal


class MietObjektCRUDTestCase(TestCase):
    """Test case for MietObjekt CRUD operations in the user area."""
    
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
        
        # Create test standorte (locations)
        self.standort1 = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort Berlin',
            strasse='Berliner Str. 1',
            plz='10115',
            ort='Berlin',
            land='Deutschland'
        )
        
        self.standort2 = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort Hamburg',
            strasse='Hamburger Str. 2',
            plz='20095',
            ort='Hamburg',
            land='Deutschland'
        )
        
        # Create test MietObjekte
        self.objekt1 = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Modernes Büro im Zentrum',
            fläche=Decimal('50.00'),
            standort=self.standort1,
            mietpreis=Decimal('1000.00'),
            nebenkosten=Decimal('200.00'),
            verfuegbar=True
        )
        
        self.objekt2 = MietObjekt.objects.create(
            name='Lager 1',
            type='CONTAINER',
            beschreibung='Großes Lager',
            fläche=Decimal('200.00'),
            höhe=Decimal('3.50'),
            standort=self.standort2,
            mietpreis=Decimal('500.00'),
            verfuegbar=False
        )
        
        # Create test kunde for contracts
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Mieter',
            strasse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        self.client = Client()
    
    def test_mietobjekt_list_requires_authentication(self):
        """Test that mietobjekt list requires authentication."""
        response = self.client.get(reverse('vermietung:mietobjekt_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_mietobjekt_list_requires_vermietung_permission(self):
        """Test that mietobjekt list requires Vermietung group membership."""
        self.client.login(username='regularuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_list'))
        # User without Vermietung access is redirected to login page (302) or gets forbidden (403)
        self.assertIn(response.status_code, [302, 403])
    
    def test_mietobjekt_list_success(self):
        """Test that mietobjekt list shows objects for authorized users."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Büro 1')
        self.assertContains(response, 'Lager 1')
    
    def test_mietobjekt_list_search(self):
        """Test that search filters work correctly."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_list'), {'q': 'Büro'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Büro 1')
        self.assertNotContains(response, 'Lager 1')
    
    def test_mietobjekt_list_type_filter(self):
        """Test that type filter works correctly."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_list'), {'type': 'RAUM'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Büro 1')
        self.assertNotContains(response, 'Lager 1')
    
    def test_mietobjekt_list_verfuegbar_filter(self):
        """Test that availability filter works correctly."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_list'), {'verfuegbar': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Büro 1')
        self.assertNotContains(response, 'Lager 1')
    
    def test_mietobjekt_list_standort_filter(self):
        """Test that location filter works correctly."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_list'), {'standort': str(self.standort1.id)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Büro 1')
        self.assertNotContains(response, 'Lager 1')
    
    def test_mietobjekt_detail_success(self):
        """Test that mietobjekt detail shows all information."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.objekt1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Büro 1')
        self.assertContains(response, 'Modernes Büro im Zentrum')
        self.assertContains(response, '1000')  # Changed from '1000.00' to match template rendering
        self.assertContains(response, 'Berlin')
    
    def test_mietobjekt_create_get(self):
        """Test that create form is displayed correctly."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_create'))
        self.assertEqual(response.status_code, 200)
        # Note: "Neues Mietobjekt" button text kept as singular (used for badge)
        self.assertContains(response, 'Neues Mietobjekt')
        self.assertIsInstance(response.context['form'], MietObjektForm)
    
    def test_mietobjekt_create_post_success(self):
        """Test that creating a new mietobjekt works correctly."""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Test Objekt',
            'type': 'GEBAEUDE',
            'beschreibung': 'Test Beschreibung',
            'fläche': '100.00',
            'standort': self.standort1.id,
            'mietpreis': '2000.00',
            'nebenkosten': '300.00',
            'kaution': '6000.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True
        }
        response = self.client.post(reverse('vermietung:mietobjekt_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that object was created
        objekt = MietObjekt.objects.get(name='Test Objekt')
        self.assertEqual(objekt.type, 'GEBAEUDE')
        self.assertEqual(objekt.mietpreis, Decimal('2000.00'))
    
    def test_mietobjekt_create_post_validation_error(self):
        """Test that validation errors are displayed correctly."""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': '',  # Missing required field
            'type': 'GEBAEUDE',
            'beschreibung': 'Test',
            'standort': self.standort1.id,
            'mietpreis': '1000.00'
        }
        response = self.client.post(reverse('vermietung:mietobjekt_create'), data)
        self.assertEqual(response.status_code, 200)  # Form redisplayed with errors
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors)
    
    def test_mietobjekt_edit_get(self):
        """Test that edit form is displayed correctly with existing data."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.objekt1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Büro 1')
        self.assertIsInstance(response.context['form'], MietObjektForm)
    
    def test_mietobjekt_edit_post_success(self):
        """Test that editing a mietobjekt works correctly."""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Büro 1 Updated',
            'type': 'RAUM',
            'beschreibung': 'Updated description',
            'fläche': '55.00',
            'standort': self.standort1.id,
            'mietpreis': '1100.00',
            'nebenkosten': '250.00',
            'kaution': '3300.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True
        }
        response = self.client.post(reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.objekt1.pk}), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that object was updated
        self.objekt1.refresh_from_db()
        self.assertEqual(self.objekt1.name, 'Büro 1 Updated')
        self.assertEqual(self.objekt1.mietpreis, Decimal('1100.00'))
    
    def test_mietobjekt_delete_success(self):
        """Test that deleting a mietobjekt without contracts works."""
        self.client.login(username='testuser', password='testpass123')
        objekt_id = self.objekt1.pk
        response = self.client.post(reverse('vermietung:mietobjekt_delete', kwargs={'pk': objekt_id}))
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that object was deleted
        with self.assertRaises(MietObjekt.DoesNotExist):
            MietObjekt.objects.get(pk=objekt_id)
    
    def test_mietobjekt_delete_with_active_contract_fails(self):
        """Test that deleting a mietobjekt with active contracts is prevented."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create an active contract for the object
        from datetime import date, timedelta
        contract = Vertrag.objects.create(
            mietobjekt=self.objekt1,
            mieter=self.kunde,
            start=date.today() - timedelta(days=30),
            ende=date.today() + timedelta(days=30),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active'
        )
        
        response = self.client.post(reverse('vermietung:mietobjekt_delete', kwargs={'pk': self.objekt1.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect to detail page
        
        # Check that object was NOT deleted
        self.assertTrue(MietObjekt.objects.filter(pk=self.objekt1.pk).exists())
    
    def test_mietobjekt_form_standort_queryset(self):
        """Test that standort field only shows STANDORT addresses."""
        form = MietObjektForm()
        standort_queryset = form.fields['standort'].queryset
        
        # Should only include STANDORT addresses
        self.assertEqual(standort_queryset.count(), 2)
        self.assertTrue(all(addr.adressen_type == 'STANDORT' for addr in standort_queryset))
    
    def test_mietobjekt_detail_shows_related_contracts(self):
        """Test that detail page shows related contracts."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a contract for the object
        from datetime import date, timedelta
        contract = Vertrag.objects.create(
            mietobjekt=self.objekt1,
            mieter=self.kunde,
            start=date.today() - timedelta(days=30),
            ende=date.today() + timedelta(days=30),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active'
        )
        
        response = self.client.get(reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.objekt1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, contract.vertragsnummer)
        self.assertContains(response, 'Test Mieter')
    
    def test_is_mietobjekt_field_default_value(self):
        """Test that is_mietobjekt field has default value True."""
        objekt = MietObjekt.objects.create(
            name='Test Objekt',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort1,
            mietpreis=Decimal('1000.00')
        )
        self.assertTrue(objekt.is_mietobjekt)
    
    def test_is_mietobjekt_field_in_form(self):
        """Test that is_mietobjekt field is included in the form."""
        form = MietObjektForm()
        self.assertIn('is_mietobjekt', form.fields)
        self.assertEqual(form.fields['is_mietobjekt'].label, 'Mietobjekt')
    
    def test_mietobjekt_edit_toggle_is_mietobjekt_to_false(self):
        """Test toggling is_mietobjekt from True to False."""
        self.client.login(username='testuser', password='testpass123')
        
        # Verify initial value is True
        self.assertTrue(self.objekt1.is_mietobjekt)
        
        data = {
            'name': self.objekt1.name,
            'type': self.objekt1.type,
            'beschreibung': self.objekt1.beschreibung,
            'fläche': str(self.objekt1.fläche),
            'standort': self.objekt1.standort.id,
            'mietpreis': str(self.objekt1.mietpreis),
            'nebenkosten': str(self.objekt1.nebenkosten),
            'verfuegbare_einheiten': '1',
            'verfuegbar': True,
            'is_mietobjekt': False  # Toggle to False
        }
        response = self.client.post(reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.objekt1.pk}), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that field was updated
        self.objekt1.refresh_from_db()
        self.assertFalse(self.objekt1.is_mietobjekt)
    
    def test_mietobjekt_edit_toggle_is_mietobjekt_to_true(self):
        """Test toggling is_mietobjekt from False to True."""
        self.client.login(username='testuser', password='testpass123')
        
        # Set initial value to False
        self.objekt1.is_mietobjekt = False
        self.objekt1.save()
        
        data = {
            'name': self.objekt1.name,
            'type': self.objekt1.type,
            'beschreibung': self.objekt1.beschreibung,
            'fläche': str(self.objekt1.fläche),
            'standort': self.objekt1.standort.id,
            'mietpreis': str(self.objekt1.mietpreis),
            'nebenkosten': str(self.objekt1.nebenkosten),
            'verfuegbare_einheiten': '1',
            'verfuegbar': True,
            'is_mietobjekt': True  # Toggle to True
        }
        response = self.client.post(reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.objekt1.pk}), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that field was updated
        self.objekt1.refresh_from_db()
        self.assertTrue(self.objekt1.is_mietobjekt)
    
    def test_mietobjekt_create_with_is_mietobjekt_false(self):
        """Test creating a new mietobjekt with is_mietobjekt set to False."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'New Object',
            'type': 'RAUM',
            'beschreibung': 'Test description',
            'fläche': '30.00',
            'standort': self.standort1.id,
            'mietpreis': '800.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True,
            'is_mietobjekt': False
        }
        response = self.client.post(reverse('vermietung:mietobjekt_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that object was created with correct value
        new_objekt = MietObjekt.objects.get(name='New Object')
        self.assertFalse(new_objekt.is_mietobjekt)
    
    def test_mietobjekt_form_displays_is_mietobjekt_checkbox(self):
        """Test that the form template displays the is_mietobjekt checkbox."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.objekt1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'is_mietobjekt')
        self.assertContains(response, 'Mietobjekt')
    
    def test_mietobjekt_list_shows_badge_when_is_mietobjekt_true(self):
        """Test that list view shows Mietobjekt badge when is_mietobjekt is True."""
        self.client.login(username='testuser', password='testpass123')
        # Ensure objekt1 has is_mietobjekt=True
        self.objekt1.is_mietobjekt = True
        self.objekt1.save()
        
        response = self.client.get(reverse('vermietung:mietobjekt_list'))
        self.assertEqual(response.status_code, 200)
        # Check that badge appears for this object
        self.assertContains(response, 'badge bg-secondary ms-2">Mietobjekt</span>')
    
    def test_mietobjekt_list_hides_badge_when_is_mietobjekt_false(self):
        """Test that list view does not show Mietobjekt badge when is_mietobjekt is False."""
        self.client.login(username='testuser', password='testpass123')
        # Set is_mietobjekt to False for both objects
        self.objekt1.is_mietobjekt = False
        self.objekt1.save()
        self.objekt2.is_mietobjekt = False
        self.objekt2.save()
        
        response = self.client.get(reverse('vermietung:mietobjekt_list'))
        self.assertEqual(response.status_code, 200)
        # Check that badge does NOT appear
        self.assertNotContains(response, 'badge bg-secondary ms-2">Mietobjekt</span>')
    
    def test_mietobjekt_detail_shows_badge_when_is_mietobjekt_true(self):
        """Test that detail view shows Mietobjekt badge when is_mietobjekt is True."""
        self.client.login(username='testuser', password='testpass123')
        # Ensure objekt1 has is_mietobjekt=True
        self.objekt1.is_mietobjekt = True
        self.objekt1.save()
        
        response = self.client.get(reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.objekt1.pk}))
        self.assertEqual(response.status_code, 200)
        # Check that badge appears in page title
        self.assertContains(response, 'badge bg-secondary ms-2">Mietobjekt</span>')
    
    def test_mietobjekt_detail_hides_badge_when_is_mietobjekt_false(self):
        """Test that detail view does not show Mietobjekt badge when is_mietobjekt is False."""
        self.client.login(username='testuser', password='testpass123')
        # Set is_mietobjekt to False
        self.objekt1.is_mietobjekt = False
        self.objekt1.save()
        
        response = self.client.get(reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.objekt1.pk}))
        self.assertEqual(response.status_code, 200)
        # Check that badge does NOT appear in page title
        self.assertNotContains(response, 'badge bg-secondary ms-2">Mietobjekt</span>')

