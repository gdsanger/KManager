"""
Tests for ActivityStream integration in Eingangsrechnung (Incoming Invoice) views.

This module tests that ActivityStream events are correctly created when:
1. An Eingangsrechnung is created (via form or PDF upload)
2. Status is changed (via edit)
3. Invoice is marked as paid
4. Invoice is deleted
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta

from core.models import Adresse, Mandant, Activity, Kostenart
from vermietung.models import MietObjekt, Eingangsrechnung, EingangsrechnungAufteilung

User = get_user_model()


class EingangsrechnungActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Eingangsrechnung operations."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )
        
        # Create client and login
        self.client = Client()
        self.client.force_login(self.user)
        
        # Create Mandant (company)
        self.mandant = Mandant.objects.create(
            name='Test Company',
            adresse='Test Street 1',
            plz='12345',
            ort='Test City'
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
        
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Energie AG',
            strasse='Energiestrasse 1',
            plz='54321',
            ort='Energiestadt',
            land='Deutschland',
            email='energie@example.com'
        )
        
        # Create a MietObjekt with mandant
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Kleines Büro',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbare_einheiten=1,
            mandant=self.mandant
        )
        
        # Create a Kostenart for allocations
        self.kostenart = Kostenart.objects.create(
            name='Strom',
            umsatzsteuer_satz='19'
        )
    
    def test_eingangsrechnung_created_event(self):
        """Test that creating an Eingangsrechnung generates an eingangsrechnung.created event."""
        # Count initial activities in stream
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.created'
        ).count()
        
        # Create eingangsrechnung via POST
        response = self.client.post(
            reverse('vermietung:eingangsrechnung_create'),
            {
                'lieferant': self.lieferant.pk,
                'mietobjekt': self.mietobjekt.pk,
                'belegdatum': date.today().isoformat(),
                'faelligkeit': (date.today() + timedelta(days=30)).isoformat(),
                'belegnummer': 'RE-2024-001',
                'betreff': 'Stromrechnung Januar 2024',
                'status': 'NEU',
                # Aufteilung formset data
                'aufteilungen-TOTAL_FORMS': '1',
                'aufteilungen-INITIAL_FORMS': '0',
                'aufteilungen-MIN_NUM_FORMS': '0',
                'aufteilungen-MAX_NUM_FORMS': '1000',
                'aufteilungen-0-kostenart1': self.kostenart.pk,
                'aufteilungen-0-nettobetrag': '100.00',
            }
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Eingangsrechnung:', event.title)
        self.assertIn('RE-2024-001', event.title)
        self.assertIn('Energie AG', event.description)
        self.assertIn('Neu', event.description)
        self.assertIn('EUR', event.description)
        self.assertTrue(event.target_url.startswith('/vermietung/eingangsrechnungen/'))
        self.assertEqual(event.severity, 'INFO')
    
    def test_status_changed_event(self):
        """Test that changing status via edit generates an eingangsrechnung.status_changed event."""
        # Create eingangsrechnung
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date.today(),
            faelligkeit=date.today() + timedelta(days=30),
            belegnummer='RE-2024-002',
            betreff='Gasrechnung Januar 2024',
            status='NEU'
        )
        
        # Create allocation
        aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung,
            kostenart1=self.kostenart,
            nettobetrag=Decimal('200.00')
        )
        
        # Count initial status_changed events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.status_changed'
        ).count()
        
        # Update status via edit view
        response = self.client.post(
            reverse('vermietung:eingangsrechnung_edit', args=[rechnung.pk]),
            {
                'lieferant': self.lieferant.pk,
                'mietobjekt': self.mietobjekt.pk,
                'belegdatum': date.today().isoformat(),
                'faelligkeit': (date.today() + timedelta(days=30)).isoformat(),
                'belegnummer': 'RE-2024-002',
                'betreff': 'Gasrechnung Januar 2024',
                'status': 'OFFEN',  # Changed from 'NEU' to 'OFFEN'
                # Aufteilung formset data
                'aufteilungen-TOTAL_FORMS': '1',
                'aufteilungen-INITIAL_FORMS': '1',
                'aufteilungen-MIN_NUM_FORMS': '0',
                'aufteilungen-MAX_NUM_FORMS': '1000',
                'aufteilungen-0-id': aufteilung.pk,
                'aufteilungen-0-eingangsrechnung': rechnung.pk,
                'aufteilungen-0-kostenart1': self.kostenart.pk,
                'aufteilungen-0-nettobetrag': '200.00',
            }
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.status_changed'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('RE-2024-002', event.title)
        self.assertIn('Neu', event.description)
        self.assertIn('Offen', event.description)
        self.assertIn('Status geändert', event.description)
        self.assertEqual(event.severity, 'INFO')
    
    def test_update_without_status_change_event(self):
        """Test that editing without status change generates an eingangsrechnung.updated event."""
        # Create eingangsrechnung
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date.today(),
            faelligkeit=date.today() + timedelta(days=30),
            belegnummer='RE-2024-003',
            betreff='Wasserrechnung Januar 2024',
            status='OFFEN'
        )
        
        # Create allocation
        aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung,
            kostenart1=self.kostenart,
            nettobetrag=Decimal('50.00')
        )
        
        # Count initial updated events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.updated'
        ).count()
        
        # Update betreff but not status
        response = self.client.post(
            reverse('vermietung:eingangsrechnung_edit', args=[rechnung.pk]),
            {
                'lieferant': self.lieferant.pk,
                'mietobjekt': self.mietobjekt.pk,
                'belegdatum': date.today().isoformat(),
                'faelligkeit': (date.today() + timedelta(days=30)).isoformat(),
                'belegnummer': 'RE-2024-003',
                'betreff': 'Wasserrechnung Januar 2024 (aktualisiert)',  # Changed
                'status': 'OFFEN',  # Same status
                # Aufteilung formset data
                'aufteilungen-TOTAL_FORMS': '1',
                'aufteilungen-INITIAL_FORMS': '1',
                'aufteilungen-MIN_NUM_FORMS': '0',
                'aufteilungen-MAX_NUM_FORMS': '1000',
                'aufteilungen-0-id': aufteilung.pk,
                'aufteilungen-0-eingangsrechnung': rechnung.pk,
                'aufteilungen-0-kostenart1': self.kostenart.pk,
                'aufteilungen-0-nettobetrag': '50.00',
            }
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created (updated, not status_changed)
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.updated'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify NO status_changed event was created
        status_changed_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.status_changed'
        )
        self.assertEqual(status_changed_events.count(), 0)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('RE-2024-003', event.title)
        self.assertIn('aktualisiert', event.description)
        self.assertIn('EUR', event.description)
        self.assertEqual(event.severity, 'INFO')
    
    def test_mark_paid_event(self):
        """Test that marking invoice as paid generates an eingangsrechnung.paid event."""
        # Create eingangsrechnung
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date.today(),
            faelligkeit=date.today() + timedelta(days=30),
            belegnummer='RE-2024-004',
            betreff='Heizung Januar 2024',
            status='OFFEN'
        )
        
        # Create allocation
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung,
            kostenart1=self.kostenart,
            nettobetrag=Decimal('300.00')
        )
        
        # Count initial paid events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.paid'
        ).count()
        
        # Mark as paid
        zahlungsdatum = date.today()
        response = self.client.post(
            reverse('vermietung:eingangsrechnung_mark_paid', args=[rechnung.pk]),
            {
                'zahlungsdatum': zahlungsdatum.isoformat()
            }
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.paid'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('RE-2024-004', event.title)
        self.assertIn('bezahlt markiert', event.description)
        self.assertIn(zahlungsdatum.strftime('%d.%m.%Y'), event.description)
        self.assertIn('EUR', event.description)
        self.assertEqual(event.severity, 'INFO')
    
    def test_delete_event(self):
        """Test that deleting an Eingangsrechnung generates an eingangsrechnung.deleted event."""
        # Create eingangsrechnung
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date.today(),
            faelligkeit=date.today() + timedelta(days=30),
            belegnummer='RE-2024-005',
            betreff='Müllabfuhr Januar 2024',
            status='NEU'
        )
        
        # Create allocation
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung,
            kostenart1=self.kostenart,
            nettobetrag=Decimal('25.00')
        )
        
        # Count initial deleted events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.deleted'
        ).count()
        
        # Delete invoice
        response = self.client.post(
            reverse('vermietung:eingangsrechnung_delete', args=[rechnung.pk])
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify invoice is deleted
        self.assertFalse(Eingangsrechnung.objects.filter(pk=rechnung.pk).exists())
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.deleted'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('RE-2024-005', event.description)
        self.assertIn('gelöscht', event.description)
        self.assertIn('Energie AG', event.description)
        self.assertEqual(event.severity, 'INFO')
    
    def test_event_target_url_is_correct(self):
        """Test that activity stream events contain the correct target URL."""
        # Create eingangsrechnung
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date.today(),
            faelligkeit=date.today() + timedelta(days=30),
            belegnummer='RE-2024-006',
            betreff='Test URL',
            status='NEU'
        )
        
        # Create allocation
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung,
            kostenart1=self.kostenart,
            nettobetrag=Decimal('10.00')
        )
        
        # Mark as paid to generate event
        self.client.post(
            reverse('vermietung:eingangsrechnung_mark_paid', args=[rechnung.pk]),
            {'zahlungsdatum': date.today().isoformat()}
        )
        
        # Get the activity
        event = Activity.objects.filter(
            company=self.mandant,
            activity_type='eingangsrechnung.paid'
        ).latest('created_at')
        
        # Verify URL is correct
        expected_url = reverse('vermietung:eingangsrechnung_detail', args=[rechnung.pk])
        self.assertEqual(event.target_url, expected_url)
        
        # Verify URL works (returns 200)
        response = self.client.get(event.target_url)
        self.assertEqual(response.status_code, 200)
