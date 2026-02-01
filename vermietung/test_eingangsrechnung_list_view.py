"""
Tests for Eingangsrechnung list view with django-tables2 and django-filter.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from core.models import Adresse, Kostenart
from vermietung.models import MietObjekt, Eingangsrechnung


class EingangsrechnungListViewTestCase(TestCase):
    """Test case for Eingangsrechnung list view with django-tables2"""
    
    def setUp(self):
        """Set up test data and client"""
        # Create user for authentication with staff privileges
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True  # Required for vermietung access
        )
        
        # Create supplier
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Test Lieferant GmbH',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            email='test@lieferant.de'
        )
        
        # Create location
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort Test',
            strasse='Standortstrasse 1',
            plz='54321',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        # Create mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Testgebäude',
            type='GEBAEUDE',
            beschreibung='Test Beschreibung',
            fläche=Decimal('100.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00')
        )
        
        # Create test invoices
        self.rechnung1 = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
            belegnummer='RE-2024-001',
            betreff='Test Rechnung 1',
            status='NEU',
            umlagefaehig=True
        )
        
        self.rechnung2 = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
            belegnummer='RE-2024-002',
            betreff='Test Rechnung 2',
            status='OFFEN',
            umlagefaehig=False
        )
        
        # Create client
        self.client = Client()
        
    def test_list_view_requires_authentication(self):
        """Test that list view requires authentication"""
        response = self.client.get(reverse('vermietung:eingangsrechnung_list'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        
    def test_list_view_displays_invoices(self):
        """Test that list view displays invoices"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vermietung:eingangsrechnung_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('table', response.context)
        self.assertIn('filter', response.context)
        
        # Check that both invoices are in the table data
        table = response.context['table']
        invoice_count = len(list(table.rows))
        self.assertEqual(invoice_count, 2)
        
    def test_list_view_search_filter(self):
        """Test that search filter works"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:eingangsrechnung_list'),
            {'q': 'RE-2024-001'}
        )
        
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        invoice_count = len(list(table.rows))
        self.assertEqual(invoice_count, 1)
        
    def test_list_view_status_filter(self):
        """Test that status filter works"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:eingangsrechnung_list'),
            {'status': 'OFFEN'}
        )
        
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        invoice_count = len(list(table.rows))
        self.assertEqual(invoice_count, 1)
        
    def test_list_view_mietobjekt_filter(self):
        """Test that mietobjekt filter works"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:eingangsrechnung_list'),
            {'mietobjekt': str(self.mietobjekt.pk)}
        )
        
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        invoice_count = len(list(table.rows))
        self.assertEqual(invoice_count, 2)
        
    def test_list_view_umlagefaehig_filter(self):
        """Test that umlagefaehig filter works"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('vermietung:eingangsrechnung_list'),
            {'umlagefaehig': 'true'}
        )
        
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        invoice_count = len(list(table.rows))
        self.assertEqual(invoice_count, 1)
        
    def test_list_view_pagination(self):
        """Test that pagination works"""
        # Create more invoices to test pagination
        for i in range(3, 25):
            Eingangsrechnung.objects.create(
                lieferant=self.lieferant,
                mietobjekt=self.mietobjekt,
                belegdatum=timezone.now().date(),
                faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
                belegnummer=f'RE-2024-{i:03d}',
                betreff=f'Test Rechnung {i}',
                status='NEU'
            )
        
        self.client.login(username='testuser', password='testpass123')
        
        # First page
        response = self.client.get(reverse('vermietung:eingangsrechnung_list'))
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        self.assertTrue(table.page.has_next())
        
        # Second page
        response = self.client.get(
            reverse('vermietung:eingangsrechnung_list'),
            {'page': '2'}
        )
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        self.assertTrue(table.page.has_previous())
