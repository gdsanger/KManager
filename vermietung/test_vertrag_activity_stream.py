"""
Tests for ActivityStream integration in Vertrag (Rental Contract) views.

This module tests that ActivityStream events are correctly created when:
1. A Vertrag is created
2. Status is changed (via edit)
3. Contract is ended (end date set)
4. Contract is cancelled
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta

from core.models import Adresse, Mandant, Activity
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt

User = get_user_model()


class VertragActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Vertrag operations."""
    
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
        
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
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
    
    def test_contract_created_event(self):
        """Test that creating a Vertrag generates a contract.created event."""
        # Count initial activities in stream
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.created'
        ).count()
        
        # Create vertrag via POST
        response = self.client.post(
            reverse('vermietung:vertrag_create'),
            {
                'mieter': self.kunde.pk,
                'start': date.today().isoformat(),
                'miete': '500.00',
                'kaution': '1500.00',
                'status': 'active',
                'umsatzsteuer_satz': '19',
                'auto_total': 'on',
                'mandant': self.mandant.pk,
                # VertragsObjekt formset data
                'vertragsobjekte-TOTAL_FORMS': '1',
                'vertragsobjekte-INITIAL_FORMS': '0',
                'vertragsobjekte-MIN_NUM_FORMS': '0',
                'vertragsobjekte-MAX_NUM_FORMS': '1000',
                'vertragsobjekte-0-mietobjekt': self.mietobjekt.pk,
                'vertragsobjekte-0-anzahl': '1',
                'vertragsobjekte-0-preis': '500.00',
                'vertragsobjekte-0-status': 'AKTIV',
                'vertragsobjekte-0-status': 'AKTIV',
            }
        )
        
        # If not redirect, check errors
        if response.status_code != 302:
            print("Form errors:", response.context.get('form').errors if hasattr(response, 'context') and response.context.get('form') else 'No form')
            print("Formset errors:", response.context.get('formset').errors if hasattr(response, 'context') and response.context.get('formset') else 'No formset')
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Vertrag:', event.title)
        self.assertIn('Max Mustermann', event.description)
        self.assertIn('Aktiv', event.description)
        self.assertTrue(event.target_url.startswith('/vermietung/vertraege/'))
        self.assertEqual(event.severity, 'INFO')
    
    def test_status_changed_event(self):
        """Test that changing status via edit generates a contract.status_changed event."""
        # Create vertrag
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Create VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=1,
            preis=Decimal('500.00')
        )
        
        # Count initial status_changed events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).count()
        
        # Update status via edit view
        response = self.client.post(
            reverse('vermietung:vertrag_edit', args=[vertrag.pk]),
            {
                'mieter': self.kunde.pk,
                'start': date.today().isoformat(),
                'miete': '500.00',
                'kaution': '1500.00',
                'status': 'draft',  # Changed from 'active' to 'draft'
                'umsatzsteuer_satz': '19',
                'auto_total': 'on',
                'mandant': self.mandant.pk,
                # VertragsObjekt formset data
                'vertragsobjekte-TOTAL_FORMS': '1',
                'vertragsobjekte-INITIAL_FORMS': '1',
                'vertragsobjekte-MIN_NUM_FORMS': '0',
                'vertragsobjekte-MAX_NUM_FORMS': '1000',
                'vertragsobjekte-0-id': VertragsObjekt.objects.get(vertrag=vertrag).pk,
                'vertragsobjekte-0-vertrag': vertrag.pk,
                'vertragsobjekte-0-mietobjekt': self.mietobjekt.pk,
                'vertragsobjekte-0-anzahl': '1',
                'vertragsobjekte-0-preis': '500.00',
                'vertragsobjekte-0-status': 'AKTIV',
            }
        )
        
        # If not redirect, print errors
        if response.status_code != 302:
            print("Form errors:", response.context.get('form').errors if hasattr(response, 'context') and response.context.get('form') else 'No form')
            print("Formset errors:", response.context.get('formset').errors if hasattr(response, 'context') and response.context.get('formset') else 'No formset')
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Aktiv', event.description)
        self.assertIn('Entwurf', event.description)
        self.assertIn('→', event.description)
    
    def test_contract_ended_event(self):
        """Test that ending a contract generates a contract.ended event."""
        # Create vertrag
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date.today() - timedelta(days=30),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Count initial ended events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.ended'
        ).count()
        
        # Set end date
        end_date = date.today() + timedelta(days=30)
        response = self.client.post(
            reverse('vermietung:vertrag_end', args=[vertrag.pk]),
            {'ende': end_date.isoformat()}
        )
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.ended'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.user)
        self.assertIn('beendet', event.description)
        self.assertIn(end_date.strftime('%d.%m.%Y'), event.description)
    
    def test_contract_ended_with_status_change_event(self):
        """Test that ending a contract in the past also logs status change in description."""
        # Create vertrag
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date.today() - timedelta(days=60),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Set end date in the past (should trigger status change to 'ended')
        end_date = date.today() - timedelta(days=1)
        response = self.client.post(
            reverse('vermietung:vertrag_end', args=[vertrag.pk]),
            {'ende': end_date.isoformat()}
        )
        
        # Get the event
        event = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.ended'
        ).latest('created_at')
        
        # Verify event includes status change information
        self.assertIn('Status:', event.description)
        self.assertIn('Aktiv', event.description)
        self.assertIn('Beendet', event.description)
    
    def test_contract_cancelled_event(self):
        """Test that cancelling a contract generates a contract.cancelled event."""
        # Create vertrag
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Count initial cancelled events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.cancelled'
        ).count()
        
        # Cancel the contract
        response = self.client.post(
            reverse('vermietung:vertrag_cancel', args=[vertrag.pk])
        )
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.cancelled'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.severity, 'WARNING')
        self.assertIn('storniert', event.description)
        self.assertIn('Aktiv', event.description)
        self.assertIn('Storniert', event.description)
    
    def test_no_event_when_status_unchanged(self):
        """Test that no status_changed event is created when status doesn't change."""
        # Create vertrag
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Create VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            anzahl=1,
            preis=Decimal('500.00')
        )
        
        # Count initial events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).count()
        
        # Update vertrag without changing status
        response = self.client.post(
            reverse('vermietung:vertrag_edit', args=[vertrag.pk]),
            {
                'mieter': self.kunde.pk,
                'start': date.today().isoformat(),
                'miete': '600.00',  # Changed miete
                'kaution': '1800.00',  # Changed kaution
                'status': 'active',  # Same status
                'umsatzsteuer_satz': '19',
                'auto_total': 'on',
                'mandant': self.mandant.pk,
                # VertragsObjekt formset data
                'vertragsobjekte-TOTAL_FORMS': '1',
                'vertragsobjekte-INITIAL_FORMS': '1',
                'vertragsobjekte-MIN_NUM_FORMS': '0',
                'vertragsobjekte-MAX_NUM_FORMS': '1000',
                'vertragsobjekte-0-id': VertragsObjekt.objects.get(vertrag=vertrag).pk,
                'vertragsobjekte-0-vertrag': vertrag.pk,
                'vertragsobjekte-0-mietobjekt': self.mietobjekt.pk,
                'vertragsobjekte-0-anzahl': '1',
                'vertragsobjekte-0-preis': '600.00',
                'vertragsobjekte-0-status': 'AKTIV',
            }
        )
        
        # Verify no new status_changed event was created
        status_changed = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).count()
        
        self.assertEqual(status_changed, initial_count)
    
    def test_event_has_valid_target_url(self):
        """Test that all events have a valid target_url pointing to the contract."""
        # Create vertrag via POST to trigger creation event
        response = self.client.post(
            reverse('vermietung:vertrag_create'),
            {
                'mieter': self.kunde.pk,
                'start': date.today().isoformat(),
                'miete': '500.00',
                'kaution': '1500.00',
                'status': 'active',
                'umsatzsteuer_satz': '19',
                'auto_total': 'on',
                'mandant': self.mandant.pk,
                # VertragsObjekt formset data
                'vertragsobjekte-TOTAL_FORMS': '1',
                'vertragsobjekte-INITIAL_FORMS': '0',
                'vertragsobjekte-MIN_NUM_FORMS': '0',
                'vertragsobjekte-MAX_NUM_FORMS': '1000',
                'vertragsobjekte-0-mietobjekt': self.mietobjekt.pk,
                'vertragsobjekte-0-anzahl': '1',
                'vertragsobjekte-0-preis': '500.00',
                'vertragsobjekte-0-status': 'AKTIV',
            }
        )
        
        # Should have created successfully
        self.assertEqual(response.status_code, 302)
        
        # Get the created vertrag
        vertrag = Vertrag.objects.filter(mieter=self.kunde).latest('id')
        
        # Get the event
        event = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.created'
        ).latest('created_at')
        
        # Verify target_url is valid and points to vertrag
        self.assertTrue(event.target_url)
        self.assertIn(f'/vermietung/vertraege/{vertrag.pk}/', event.target_url)
    
    def test_event_without_mandant_uses_fallback(self):
        """Test that attempting to create event without mandant uses fallback."""
        # Create vertrag without mandant
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active',
            mandant=None  # No mandant
        )
        
        # Try to cancel (should still work with fallback to first mandant)
        response = self.client.post(
            reverse('vermietung:vertrag_cancel', args=[vertrag.pk])
        )
        
        # Verify contract was still cancelled
        vertrag.refresh_from_db()
        self.assertEqual(vertrag.status, 'cancelled')
        
        # Verify event was created using fallback mandant
        event = Activity.objects.filter(
            activity_type='contract.cancelled'
        ).latest('created_at')
        self.assertEqual(event.company, self.mandant)  # Should use fallback
