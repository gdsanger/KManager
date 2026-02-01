"""
Tests for Kostenarten views in UserUI.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from core.models import Kostenart
from vermietung.models import Eingangsrechnung, EingangsrechnungAufteilung, MietObjekt
from core.models import Adresse


class KostenartenViewsTestCase(TestCase):
    """Test Kostenarten CRUD views"""
    
    def setUp(self):
        """Set up test data"""
        # Create user with Vermietung access
        self.user = User.objects.create_user(username='testuser', password='test123')
        group, _ = Group.objects.get_or_create(name='Vermietung')
        self.user.groups.add(group)
        
        # Create Hauptkostenarten
        self.hauptkostenart1 = Kostenart.objects.create(name='Personal', umsatzsteuer_satz='19')
        self.hauptkostenart2 = Kostenart.objects.create(name='Material', umsatzsteuer_satz='19')
        
        # Create Unterkostenarten
        self.unterkostenart1 = Kostenart.objects.create(
            name='Gehälter', 
            parent=self.hauptkostenart1,
            umsatzsteuer_satz='19'
        )
        self.unterkostenart2 = Kostenart.objects.create(
            name='Rohstoffe', 
            parent=self.hauptkostenart2,
            umsatzsteuer_satz='19'
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='test123')
    
    def test_kostenarten_list_requires_authentication(self):
        """Test that kostenarten list requires authentication"""
        self.client.logout()
        response = self.client.get(reverse('vermietung:kostenarten_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_kostenarten_list_view(self):
        """Test kostenarten list view displays all Hauptkostenarten"""
        response = self.client.get(reverse('vermietung:kostenarten_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Personal')
        self.assertContains(response, 'Material')
        self.assertContains(response, 'Gehälter')
        self.assertContains(response, 'Rohstoffe')
    
    def test_kostenarten_list_with_selection(self):
        """Test kostenarten list with selected item"""
        response = self.client.get(
            reverse('vermietung:kostenarten_list') + f'?selected={self.hauptkostenart1.pk}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Personal')
        # Check that selected kostenart is in context
        self.assertEqual(response.context['selected_kostenart'], self.hauptkostenart1)
    
    def test_kostenarten_create_hauptkostenart(self):
        """Test creating a new Hauptkostenart"""
        response = self.client.post(reverse('vermietung:kostenarten_create'), {
            'name': 'Verwaltung',
            'umsatzsteuer_satz': '19',
        })
        self.assertEqual(response.status_code, 302)
        # Check that it was created
        self.assertTrue(Kostenart.objects.filter(name='Verwaltung').exists())
        new_kostenart = Kostenart.objects.get(name='Verwaltung')
        self.assertTrue(new_kostenart.is_hauptkostenart())
    
    def test_kostenarten_create_unterkostenart(self):
        """Test creating a new Unterkostenart"""
        response = self.client.post(
            reverse('vermietung:kostenarten_create') + f'?parent={self.hauptkostenart1.pk}',
            {
                'name': 'Sozialversicherung',
                'parent': self.hauptkostenart1.pk,
                'umsatzsteuer_satz': '19',
            }
        )
        self.assertEqual(response.status_code, 302)
        # Check that it was created
        self.assertTrue(Kostenart.objects.filter(name='Sozialversicherung').exists())
        new_kostenart = Kostenart.objects.get(name='Sozialversicherung')
        self.assertFalse(new_kostenart.is_hauptkostenart())
        self.assertEqual(new_kostenart.parent, self.hauptkostenart1)
    
    def test_kostenarten_edit(self):
        """Test editing a Kostenart"""
        response = self.client.post(
            reverse('vermietung:kostenarten_edit', args=[self.hauptkostenart1.pk]),
            {
                'name': 'Personal (updated)',
                'umsatzsteuer_satz': '7',
            }
        )
        self.assertEqual(response.status_code, 302)
        # Check that it was updated
        self.hauptkostenart1.refresh_from_db()
        self.assertEqual(self.hauptkostenart1.name, 'Personal (updated)')
        self.assertEqual(self.hauptkostenart1.umsatzsteuer_satz, '7')
    
    def test_kostenarten_delete_without_usage(self):
        """Test deleting a Kostenart without usage"""
        # Delete Unterkostenart first
        response = self.client.post(
            reverse('vermietung:kostenarten_delete', args=[self.unterkostenart1.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Kostenart.objects.filter(pk=self.unterkostenart1.pk).exists())
    
    def test_kostenarten_delete_with_usage_prevented(self):
        """Test that deleting a Kostenart with usage is prevented"""
        # Create an Eingangsrechnung that uses this Kostenart
        lieferant = Adresse.objects.create(
            name='Test Lieferant',
            adressen_type='LIEFERANT',
            strasse='Test Str.',
            plz='12345',
            ort='Test',
            land='Deutschland'
        )
        mietobjekt = MietObjekt.objects.create(
            name='Test Objekt',
            standort=lieferant,
            mietpreis=1000,
            type='WOHNUNG'
        )
        rechnung = Eingangsrechnung.objects.create(
            belegnummer='TEST-001',
            lieferant=lieferant,
            mietobjekt=mietobjekt,
            belegdatum='2026-01-01',
            faelligkeit='2026-01-31',
            betreff='Test'
        )
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung,
            kostenart1=self.hauptkostenart1,
            nettobetrag=100
        )
        
        # Try to delete
        response = self.client.post(
            reverse('vermietung:kostenarten_delete', args=[self.hauptkostenart1.pk])
        )
        self.assertEqual(response.status_code, 302)
        # Check that it was NOT deleted
        self.assertTrue(Kostenart.objects.filter(pk=self.hauptkostenart1.pk).exists())
    
    def test_kostenarten_delete_with_children_requires_reparent(self):
        """Test that deleting a Hauptkostenart with children requires re-parenting"""
        # Try to delete without providing new_parent
        response = self.client.post(
            reverse('vermietung:kostenarten_delete', args=[self.hauptkostenart1.pk])
        )
        self.assertEqual(response.status_code, 302)
        # Check that it was NOT deleted
        self.assertTrue(Kostenart.objects.filter(pk=self.hauptkostenart1.pk).exists())
        
        # Now try with new_parent
        response = self.client.post(
            reverse('vermietung:kostenarten_delete', args=[self.hauptkostenart1.pk]),
            {'new_parent': self.hauptkostenart2.pk}
        )
        self.assertEqual(response.status_code, 302)
        # Check that children were re-parented
        self.unterkostenart1.refresh_from_db()
        self.assertEqual(self.unterkostenart1.parent, self.hauptkostenart2)
        # Check that parent was deleted
        self.assertFalse(Kostenart.objects.filter(pk=self.hauptkostenart1.pk).exists())
