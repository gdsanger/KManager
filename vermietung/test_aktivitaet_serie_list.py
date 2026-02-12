"""
Tests for the Serie Aktivitaet (Recurring Activity) list view.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta
from core.models import Adresse, Mandant
from vermietung.models import MietObjekt, Vertrag, Aktivitaet, AktivitaetsBereich

User = get_user_model()


class AktivitaetSerieListViewTest(TestCase):
    """Tests for the recurring activities list view."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a Mandant (required for ActivityStream)
        self.mandant = Mandant.objects.create(
            name='Test Mandant',
            adresse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True  # Grant vermietung access
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123',
            email='other@example.com',
            is_staff=True
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create a category
        self.bereich = AktivitaetsBereich.objects.create(
            name='Wartung',
            beschreibung='Wartungsarbeiten'
        )
        
        # Create addresses
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Hauptstadt',
            land='Deutschland'
        )
        
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        # Create a MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Kleines Büro',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbar=True,
            mandant=self.mandant
        )
        
        # Create a Vertrag
        self.vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date.today(),
            ende=date.today() + timedelta(days=365),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active',
            mandant=self.mandant
        )
    
    def test_serie_list_view_accessible(self):
        """Test that the serie list view is accessible."""
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/aktivitaeten/serie_list.html')
    
    def test_serie_list_only_shows_series_activities(self):
        """Test that only activities with ist_serie=True are shown."""
        # Create a series activity
        serie_aktivitaet = Aktivitaet.objects.create(
            titel='Monatliche Wartung',
            beschreibung='Regelmäßige Wartung',
            status='OFFEN',
            prioritaet='NORMAL',
            faellig_am=date.today() + timedelta(days=7),
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=1,
            bereich=self.bereich
        )
        
        # Create a regular (non-series) activity
        regular_aktivitaet = Aktivitaet.objects.create(
            titel='Einmalige Aufgabe',
            beschreibung='Nur einmal',
            status='OFFEN',
            prioritaet='NORMAL',
            faellig_am=date.today() + timedelta(days=7),
            ersteller=self.user,
            ist_serie=False
        )
        
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url)
        
        # Check that only the series activity is in the context
        self.assertEqual(response.status_code, 200)
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertIn(serie_aktivitaet, page_obj)
        self.assertNotIn(regular_aktivitaet, page_obj)
    
    def test_serie_list_privacy_filter(self):
        """Test that privacy filtering works correctly."""
        # Create a public series activity
        public_aktivitaet = Aktivitaet.objects.create(
            titel='Public Serie Activity',
            status='OFFEN',
            ersteller=self.other_user,
            ist_serie=True,
            intervall_monate=1,
            privat=False
        )
        
        # Create a private series activity created by current user
        my_private_aktivitaet = Aktivitaet.objects.create(
            titel='My Private Serie Activity',
            status='OFFEN',
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=1,
            privat=True
        )
        
        # Create a private series activity by another user (should not be visible)
        other_private_aktivitaet = Aktivitaet.objects.create(
            titel='Other Private Serie Activity',
            status='OFFEN',
            ersteller=self.other_user,
            ist_serie=True,
            intervall_monate=1,
            privat=True
        )
        
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url)
        
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 2)
        self.assertIn(public_aktivitaet, page_obj)
        self.assertIn(my_private_aktivitaet, page_obj)
        self.assertNotIn(other_private_aktivitaet, page_obj)
    
    def test_serie_list_search_filter(self):
        """Test that search filtering works."""
        # Create activities with different titles
        Aktivitaet.objects.create(
            titel='Heizungswartung',
            status='OFFEN',
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=12
        )
        
        Aktivitaet.objects.create(
            titel='Treppenhausreinigung',
            status='OFFEN',
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=1
        )
        
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url, {'q': 'Heizung'})
        
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj[0].titel, 'Heizungswartung')
    
    def test_serie_list_priority_filter(self):
        """Test that priority filtering works."""
        # Create activities with different priorities
        Aktivitaet.objects.create(
            titel='High Priority Serie',
            status='OFFEN',
            prioritaet='HOCH',
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=1
        )
        
        Aktivitaet.objects.create(
            titel='Normal Priority Serie',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=1
        )
        
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url, {'prioritaet': 'HOCH'})
        
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj[0].titel, 'High Priority Serie')
    
    def test_serie_list_completed_filter(self):
        """Test that completed filter works."""
        # Create completed and open series activities
        Aktivitaet.objects.create(
            titel='Completed Serie',
            status='ERLEDIGT',
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=1
        )
        
        Aktivitaet.objects.create(
            titel='Open Serie',
            status='OFFEN',
            ersteller=self.user,
            ist_serie=True,
            intervall_monate=1
        )
        
        # Test showing only non-completed (default)
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url)
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj[0].titel, 'Open Serie')
        
        # Test showing only completed
        response = self.client.get(url, {'completed': 'true'})
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual(page_obj[0].titel, 'Completed Serie')
    
    def test_serie_list_pagination(self):
        """Test that pagination works correctly."""
        # Create 25 series activities (more than one page)
        for i in range(25):
            Aktivitaet.objects.create(
                titel=f'Serie Activity {i}',
                status='OFFEN',
                ersteller=self.user,
                ist_serie=True,
                intervall_monate=1
            )
        
        url = reverse('vermietung:aktivitaet_serie_list')
        
        # First page
        response = self.client.get(url)
        page_obj = response.context['page_obj']
        self.assertEqual(len(page_obj), 20)  # 20 items per page
        self.assertTrue(page_obj.has_next())
        self.assertFalse(page_obj.has_previous())
        
        # Second page
        response = self.client.get(url, {'page': 2})
        page_obj = response.context['page_obj']
        self.assertEqual(len(page_obj), 5)  # Remaining 5 items
        self.assertFalse(page_obj.has_next())
        self.assertTrue(page_obj.has_previous())
    
    def test_serie_list_uses_select_related(self):
        """Test that the view uses select_related to avoid N+1 queries."""
        # Create a series activity with related objects
        Aktivitaet.objects.create(
            titel='Serie with Context',
            status='OFFEN',
            ersteller=self.user,
            assigned_user=self.other_user,
            mietobjekt=self.mietobjekt,
            vertrag=self.vertrag,
            kunde=self.kunde,
            bereich=self.bereich,
            ist_serie=True,
            intervall_monate=1
        )
        
        url = reverse('vermietung:aktivitaet_serie_list')
        
        # Count queries
        from django.test import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
        
        # Check that we don't have excessive queries
        # We expect: session, user, aktivitaet query with select_related
        # The exact number may vary, but should be low (< 10)
        num_queries = len(context.captured_queries)
        self.assertLess(num_queries, 10, 
            f"Too many queries ({num_queries}). Check that select_related is used.")
    
    def test_serie_list_context_contains_expected_keys(self):
        """Test that the context contains expected keys."""
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url)
        
        self.assertIn('page_obj', response.context)
        self.assertIn('search_query', response.context)
        self.assertIn('completed_filter', response.context)
        self.assertIn('prioritaet_filter', response.context)
        self.assertIn('page_title', response.context)
        self.assertIn('view_type', response.context)
        
        self.assertEqual(response.context['page_title'], 'Serien-Aktivitäten')
        self.assertEqual(response.context['view_type'], 'serie')
    
    def test_serie_list_with_context_objects(self):
        """Test that series activities with different contexts are displayed correctly."""
        # Create series activity with Vertrag context
        serie_with_vertrag = Aktivitaet.objects.create(
            titel='Serie with Vertrag',
            status='OFFEN',
            ersteller=self.user,
            vertrag=self.vertrag,
            ist_serie=True,
            intervall_monate=1
        )
        
        # Create series activity with MietObjekt context
        serie_with_mietobjekt = Aktivitaet.objects.create(
            titel='Serie with MietObjekt',
            status='OFFEN',
            ersteller=self.user,
            mietobjekt=self.mietobjekt,
            ist_serie=True,
            intervall_monate=1
        )
        
        # Create series activity with Kunde context
        serie_with_kunde = Aktivitaet.objects.create(
            titel='Serie with Kunde',
            status='OFFEN',
            ersteller=self.user,
            kunde=self.kunde,
            ist_serie=True,
            intervall_monate=1
        )
        
        url = reverse('vermietung:aktivitaet_serie_list')
        response = self.client.get(url)
        
        page_obj = response.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 3)
        
        # All three should be present
        aktivitaet_titles = [a.titel for a in page_obj]
        self.assertIn('Serie with Vertrag', aktivitaet_titles)
        self.assertIn('Serie with MietObjekt', aktivitaet_titles)
        self.assertIn('Serie with Kunde', aktivitaet_titles)
