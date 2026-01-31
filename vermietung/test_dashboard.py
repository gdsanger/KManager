"""
Tests for Vermietung Dashboard functionality.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, Aktivitaet


class DashboardTestCase(TestCase):
    """Test case for Vermietung Dashboard."""
    
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
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Hauptstadt',
            land='Deutschland'
        )
        
        # Create test customers
        self.kunde1 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland'
        )
        
        self.kunde2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Anna Schmidt',
            strasse='Testweg 2',
            plz='54321',
            ort='Testort',
            land='Deutschland'
        )
        
        # Create test mietobjekte
        self.mietobjekt1 = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Büroraum im EG',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            verfuegbar=True
        )
        
        self.mietobjekt2 = MietObjekt.objects.create(
            name='Lager 1',
            type='RAUM',
            beschreibung='Lagerraum',
            standort=self.standort,
            mietpreis=Decimal('300.00'),
            verfuegbar=False
        )
        
        self.mietobjekt3 = MietObjekt.objects.create(
            name='Garage 1',
            type='STELLPLATZ',
            beschreibung='Stellplatz',
            standort=self.standort,
            mietpreis=Decimal('100.00'),
            verfuegbar=True
        )
        
        # Login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_dashboard_displays_kpis(self):
        """Test that dashboard displays KPIs correctly."""
        # Create some contracts
        today = timezone.now().date()
        
        # Active contract (currently active)
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde1,
            start=today - timedelta(days=30),
            ende=today + timedelta(days=30),
            miete=Decimal('300.00'),
            kaution=Decimal('900.00'),
            status='active'
        )
        
        # Ended contract
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt1,
            mieter=self.kunde2,
            start=today - timedelta(days=100),
            ende=today - timedelta(days=10),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='ended'
        )
        
        # Create some activities
        Aktivitaet.objects.create(
            titel='Offene Aktivität 1',
            status='OFFEN',
            vertrag=vertrag1
        )
        Aktivitaet.objects.create(
            titel='Offene Aktivität 2',
            status='OFFEN',
            kunde=self.kunde1
        )
        Aktivitaet.objects.create(
            titel='Erledigte Aktivität',
            status='ERLEDIGT',
            kunde=self.kunde2
        )
        
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gebäude Dashboard')
        
        # Check KPIs
        self.assertEqual(response.context['total_mietobjekte'], 3)
        # verfuegbare_einheiten_gesamt is sum of all available units across all objects
        # mietobjekt1: 1 unit (default), mietobjekt2: 0 units (has active contract), mietobjekt3: 1 unit (default)
        self.assertEqual(response.context['verfuegbare_einheiten_gesamt'], 2)
        self.assertEqual(response.context['active_vertraege'], 1)  # Only vertrag1
        self.assertEqual(response.context['offene_aktivitaeten'], 2)  # Two open activities
        self.assertEqual(response.context['total_kunden'], 2)
    
    def test_dashboard_shows_recent_contracts(self):
        """Test that dashboard shows recently created contracts."""
        today = timezone.now().date()
        
        # Create multiple contracts
        contracts = []
        for i in range(5):
            kunde = Adresse.objects.create(
                adressen_type='KUNDE',
                name=f'Test Kunde {i}',
                strasse='Teststr 1',
                plz='12345',
                ort='Testort',
                land='Deutschland'
            )
            
            mietobjekt = MietObjekt.objects.create(
                name=f'Objekt {i}',
                type='RAUM',
                beschreibung='Test',
                standort=self.standort,
                mietpreis=Decimal('100.00'),
                verfuegbar=False
            )
            
            vertrag = Vertrag.objects.create(
                mietobjekt=mietobjekt,
                mieter=kunde,
                start=today,
                miete=Decimal('100.00'),
                kaution=Decimal('300.00'),
                status='active'
            )
            contracts.append(vertrag)
        
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('recent_vertraege', response.context)
        
        # Should show up to 10 recent contracts
        recent_contracts = response.context['recent_vertraege']
        self.assertEqual(len(recent_contracts), 5)
        
        # Check that contracts are ordered by ID (most recent first)
        self.assertEqual(recent_contracts[0].vertragsnummer, contracts[-1].vertragsnummer)
    
    def test_dashboard_shows_expiring_contracts(self):
        """Test that dashboard shows contracts expiring soon."""
        today = timezone.now().date()
        
        # Contract expiring in 30 days
        vertrag_expiring = Vertrag.objects.create(
            mietobjekt=self.mietobjekt1,
            mieter=self.kunde1,
            start=today - timedelta(days=60),
            ende=today + timedelta(days=30),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        
        # Contract expiring in 90 days (should not show)
        vertrag_not_expiring = Vertrag.objects.create(
            mietobjekt=self.mietobjekt3,
            mieter=self.kunde2,
            start=today,
            ende=today + timedelta(days=90),
            miete=Decimal('100.00'),
            kaution=Decimal('300.00'),
            status='active'
        )
        
        # Contract without end date (should not show)
        mietobjekt4 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=Decimal('200.00'),
            verfuegbar=False
        )
        
        vertrag_no_end = Vertrag.objects.create(
            mietobjekt=mietobjekt4,
            mieter=self.kunde1,
            start=today,
            miete=Decimal('200.00'),
            kaution=Decimal('600.00'),
            status='active'
        )
        
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('expiring_vertraege', response.context)
        
        expiring_contracts = response.context['expiring_vertraege']
        self.assertEqual(len(expiring_contracts), 1)
        self.assertEqual(expiring_contracts[0].vertragsnummer, vertrag_expiring.vertragsnummer)
    
    def test_dashboard_requires_vermietung_access(self):
        """Test that dashboard requires Vermietung group membership."""
        # Create a user without Vermietung access
        regular_user = User.objects.create_user(
            username='regularuser',
            password='testpass123',
            is_staff=False
        )
        
        # Try to access as regular user
        self.client.logout()
        self.client.login(username='regularuser', password='testpass123')
        
        response = self.client.get(reverse('vermietung:home'))
        
        # Should redirect to forbidden page or login
        self.assertNotEqual(response.status_code, 200)
    
    def test_dashboard_kpi_cards_have_links(self):
        """Test that KPI cards have working links."""
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        
        # Check for links in response
        self.assertContains(response, 'href="%s"' % reverse('vermietung:mietobjekt_list'))
        # Updated: Link now points to #verfuegbare-einheiten anchor instead of filter
        self.assertContains(response, 'href="#verfuegbare-einheiten"')
        self.assertContains(response, 'href="%s?status=active"' % reverse('vermietung:vertrag_list'))
        self.assertContains(response, 'href="%s?status=OFFEN"' % reverse('vermietung:aktivitaet_list'))
        self.assertContains(response, 'href="%s"' % reverse('vermietung:kunde_list'))
    
    def test_dashboard_offene_aktivitaeten_kpi_counts_correctly(self):
        """Test that offene_aktivitaeten KPI counts OFFEN and IN_BEARBEITUNG, but not ERLEDIGT or ABGEBROCHEN."""
        # Create activities with different statuses
        Aktivitaet.objects.create(
            titel='Offene Aktivität',
            status='OFFEN',
            kunde=self.kunde1
        )
        Aktivitaet.objects.create(
            titel='In Bearbeitung Aktivität',
            status='IN_BEARBEITUNG',
            kunde=self.kunde1
        )
        Aktivitaet.objects.create(
            titel='Erledigte Aktivität',
            status='ERLEDIGT',
            kunde=self.kunde1
        )
        Aktivitaet.objects.create(
            titel='Abgebrochene Aktivität',
            status='ABGEBROCHEN',
            kunde=self.kunde1
        )
        
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        # Should count only OFFEN (1) and IN_BEARBEITUNG (1) = 2 total
        # Should NOT count ERLEDIGT or ABGEBROCHEN
        self.assertEqual(response.context['offene_aktivitaeten'], 2)
    
    def test_dashboard_displays_verfuegbare_einheiten(self):
        """Test that dashboard displays total available rental units correctly."""
        from vermietung.models import VertragsObjekt
        
        # Create rental objects with different unit counts
        mietobjekt_with_3_units = MietObjekt.objects.create(
            name='Container',
            type='CONTAINER',
            beschreibung='Container mit 3 Einheiten',
            standort=self.standort,
            mietpreis=Decimal('100.00'),
            verfuegbare_einheiten=3,
            verfuegbar=True
        )
        
        mietobjekt_with_5_units = MietObjekt.objects.create(
            name='Lagerraum',
            type='RAUM',
            beschreibung='Lagerraum mit 5 Einheiten',
            standort=self.standort,
            mietpreis=Decimal('150.00'),
            verfuegbare_einheiten=5,
            verfuegbar=True
        )
        
        # Create active contract that rents 2 units of the container
        today = timezone.now().date()
        vertrag = Vertrag.objects.create(
            mieter=self.kunde1,
            start=today - timedelta(days=10),
            ende=None,
            miete=Decimal('200.00'),
            kaution=Decimal('600.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=mietobjekt_with_3_units,
            anzahl=2,
            preis=Decimal('100.00')
        )
        
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        
        # Total available units should be:
        # mietobjekt1 (1 default) + mietobjekt2 (1 default, no active contract in this test) + mietobjekt3 (1 default)
        # + mietobjekt_with_3_units (3 - 2 booked = 1) + mietobjekt_with_5_units (5)
        # = 1 + 1 + 1 + 1 + 5 = 9
        expected_available = 9
        
        self.assertEqual(response.context['verfuegbare_einheiten_gesamt'], expected_available)
    
    def test_dashboard_shows_mietobjekte_mit_einheiten_table(self):
        """Test that dashboard shows the breakdown of available units per MietObjekt."""
        from vermietung.models import VertragsObjekt
        
        # Create rental object with multiple units
        mietobjekt_multi = MietObjekt.objects.create(
            name='Multi Unit Container',
            type='CONTAINER',
            beschreibung='Container mit mehreren Einheiten',
            standort=self.standort,
            mietpreis=Decimal('100.00'),
            verfuegbare_einheiten=5,
            verfuegbar=True
        )
        
        # Create active contract that rents 3 units
        today = timezone.now().date()
        vertrag = Vertrag.objects.create(
            mieter=self.kunde1,
            start=today - timedelta(days=10),
            ende=None,
            miete=Decimal('300.00'),
            kaution=Decimal('900.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=mietobjekt_multi,
            anzahl=3,
            preis=Decimal('100.00')
        )
        
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('mietobjekte_mit_einheiten', response.context)
        
        # Find the multi-unit object in the list
        mietobjekte_list = response.context['mietobjekte_mit_einheiten']
        multi_item = next(
            (item for item in mietobjekte_list if item['objekt'].id == mietobjekt_multi.id),
            None
        )
        
        self.assertIsNotNone(multi_item)
        self.assertEqual(multi_item['gesamt_einheiten'], 5)
        self.assertEqual(multi_item['gebuchte_einheiten'], 3)
        self.assertEqual(multi_item['verfuegbare_einheiten'], 2)
    
    def test_dashboard_sorts_mietobjekte_by_available_units(self):
        """Test that dashboard sorts rental objects by available units (descending)."""
        # Create objects with different availability
        obj_with_5_available = MietObjekt.objects.create(
            name='Most Available',
            type='RAUM',
            beschreibung='5 verfügbare Einheiten',
            standort=self.standort,
            mietpreis=Decimal('100.00'),
            verfuegbare_einheiten=5,
            verfuegbar=True
        )
        
        obj_with_0_available = MietObjekt.objects.create(
            name='None Available',
            type='RAUM',
            beschreibung='0 verfügbare Einheiten',
            standort=self.standort,
            mietpreis=Decimal('100.00'),
            verfuegbare_einheiten=1,
            verfuegbar=False
        )
        
        # Rent the single unit
        from vermietung.models import VertragsObjekt
        today = timezone.now().date()
        vertrag = Vertrag.objects.create(
            mieter=self.kunde1,
            start=today,
            ende=None,
            miete=Decimal('100.00'),
            kaution=Decimal('300.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=obj_with_0_available,
            anzahl=1,
            preis=Decimal('100.00')
        )
        
        response = self.client.get(reverse('vermietung:home'))
        
        self.assertEqual(response.status_code, 200)
        mietobjekte_list = response.context['mietobjekte_mit_einheiten']
        
        # First object should have the most available units
        self.assertEqual(mietobjekte_list[0]['objekt'].id, obj_with_5_available.id)
        self.assertEqual(mietobjekte_list[0]['verfuegbare_einheiten'], 5)
