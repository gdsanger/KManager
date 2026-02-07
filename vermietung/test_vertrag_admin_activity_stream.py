"""
Tests for ActivityStream integration in Vertrag Django Admin.

This module tests that ActivityStream events are correctly created when:
1. A Vertrag is created via Django Admin
2. A Vertrag is edited via Django Admin (with status change)
3. Bulk actions are used to change status
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date

from core.models import Adresse, Mandant, Activity
from vermietung.models import MietObjekt, Vertrag

User = get_user_model()


class VertragAdminActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Vertrag Admin operations."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@example.com'
        )
        
        # Create client and login as admin
        self.client = Client()
        self.client.force_login(self.admin_user)
        
        # Create Mandant (company)
        self.mandant = Mandant.objects.create(
            name='Test Company Admin',
            adresse='Test Street 1',
            plz='12345',
            ort='Test City'
        )
        
        # Create addresses
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort Admin',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Hauptstadt',
            land='Deutschland'
        )
        
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann Admin',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max.admin@example.com'
        )
        
        # Create a MietObjekt with mandant
        self.mietobjekt = MietObjekt.objects.create(
            name='Admin Büro 1',
            type='RAUM',
            beschreibung='Admin Test Büro',
            standort=self.standort,
            mietpreis=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            verfuegbare_einheiten=1,
            mandant=self.mandant
        )
    
    def test_admin_create_contract_generates_event(self):
        """Test that creating a Vertrag via Django Admin generates a contract.created event."""
        # Count initial activities
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.created'
        ).count()
        
        # Create vertrag via Django Admin (vertragsnummer limited to 10 chars)
        response = self.client.post(
            reverse('admin:vermietung_vertrag_add'),
            {
                'vertragsnummer': 'ADM-001',
                'mietobjekt': self.mietobjekt.pk,
                'mieter': self.kunde.pk,
                'start': date.today().isoformat(),
                'miete': '600.00',
                'kaution': '1800.00',
                'status': 'active',
                'mandant': self.mandant.pk,
                '_save': 'Save',
            },
            follow=True
        )
        
        # Verify contract was created
        self.assertEqual(response.status_code, 200)
        vertrag = Vertrag.objects.filter(vertragsnummer='ADM-001').first()
        self.assertIsNotNone(vertrag)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.admin_user)
        self.assertIn('ADM-001', event.title)
        self.assertIn('Max Mustermann Admin', event.description)
        self.assertIn('via Admin', event.description)
        self.assertEqual(event.severity, 'INFO')
    
    def test_admin_edit_status_change_generates_event(self):
        """Test that changing status via Django Admin generates a contract.status_changed event."""
        # Create vertrag (shorter vertragsnummer, max 10 chars)
        vertrag = Vertrag.objects.create(
            vertragsnummer='ADM-002',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Count initial status_changed events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).count()
        
        # Update status via Django Admin
        response = self.client.post(
            reverse('admin:vermietung_vertrag_change', args=[vertrag.pk]),
            {
                'vertragsnummer': 'ADM-002',
                'mietobjekt': self.mietobjekt.pk,
                'mieter': self.kunde.pk,
                'start': date.today().isoformat(),
                'miete': '600.00',
                'kaution': '1800.00',
                'status': 'draft',  # Changed from 'active' to 'draft'
                'mandant': self.mandant.pk,
                '_save': 'Save',
            },
            follow=True
        )
        
        # Verify status was changed
        self.assertEqual(response.status_code, 200)
        vertrag.refresh_from_db()
        self.assertEqual(vertrag.status, 'draft')
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.admin_user)
        self.assertIn('Aktiv', event.description)
        self.assertIn('Entwurf', event.description)
        self.assertIn('→', event.description)
        self.assertIn('via Admin', event.description)
    
    def test_admin_bulk_action_mark_as_ended_generates_events(self):
        """Test that bulk action to mark contracts as ended generates events."""
        # Create additional MietObjekt for second contract
        mietobjekt2 = MietObjekt.objects.create(
            name='Admin Büro 2',
            type='RAUM',
            beschreibung='Admin Test Büro 2',
            standort=self.standort,
            mietpreis=Decimal('700.00'),
            kaution=Decimal('2100.00'),
            verfuegbare_einheiten=1,
            mandant=self.mandant
        )
        
        # Create multiple contracts with different MietObjekte
        vertrag1 = Vertrag.objects.create(
            vertragsnummer='BULK-001',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            status='active',
            mandant=self.mandant
        )
        
        vertrag2 = Vertrag.objects.create(
            vertragsnummer='BULK-002',
            mietobjekt=mietobjekt2,  # Different MietObjekt
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('700.00'),
            kaution=Decimal('2100.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Count initial events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).count()
        
        # Execute bulk action via Django Admin
        response = self.client.post(
            reverse('admin:vermietung_vertrag_changelist'),
            {
                'action': 'mark_as_ended',
                '_selected_action': [vertrag1.pk, vertrag2.pk],
            },
            follow=True
        )
        
        # Verify contracts were updated
        self.assertEqual(response.status_code, 200)
        vertrag1.refresh_from_db()
        vertrag2.refresh_from_db()
        self.assertEqual(vertrag1.status, 'ended')
        self.assertEqual(vertrag2.status, 'ended')
        
        # Verify stream events were created for both contracts
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).order_by('created_at')
        
        self.assertEqual(stream_events.count(), initial_count + 2)
        
        # Verify both events have correct details
        recent_events = stream_events[initial_count:]
        for event in recent_events:
            self.assertEqual(event.actor, self.admin_user)
            self.assertIn('Aktiv', event.description)
            self.assertIn('Beendet', event.description)
            self.assertIn('via Admin Bulk Action', event.description)
    
    def test_admin_bulk_action_mark_as_cancelled_generates_events(self):
        """Test that bulk action to cancel contracts generates contract.cancelled events."""
        # Create contract
        vertrag = Vertrag.objects.create(
            vertragsnummer='CANCEL-01',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Count initial cancelled events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.cancelled'
        ).count()
        
        # Execute bulk cancel action
        response = self.client.post(
            reverse('admin:vermietung_vertrag_changelist'),
            {
                'action': 'mark_as_cancelled',
                '_selected_action': [vertrag.pk],
            },
            follow=True
        )
        
        # Verify contract was cancelled
        self.assertEqual(response.status_code, 200)
        vertrag.refresh_from_db()
        self.assertEqual(vertrag.status, 'cancelled')
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.cancelled'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.admin_user)
        self.assertEqual(event.severity, 'WARNING')
        self.assertIn('storniert', event.description)
        self.assertIn('via Admin Bulk Action', event.description)
    
    def test_admin_edit_without_status_change_no_event(self):
        """Test that editing a contract without changing status doesn't create status_changed event."""
        # Create vertrag
        vertrag = Vertrag.objects.create(
            vertragsnummer='NO-STAT-01',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            status='active',
            mandant=self.mandant
        )
        
        # Count initial status_changed events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).count()
        
        # Update miete but not status via Django Admin
        response = self.client.post(
            reverse('admin:vermietung_vertrag_change', args=[vertrag.pk]),
            {
                'vertragsnummer': 'NO-STAT-01',
                'mietobjekt': self.mietobjekt.pk,
                'mieter': self.kunde.pk,
                'start': date.today().isoformat(),
                'miete': '700.00',  # Changed miete
                'kaution': '1800.00',
                'status': 'active',  # Same status
                'mandant': self.mandant.pk,
                '_save': 'Save',
            },
            follow=True
        )
        
        # Verify no new status_changed event was created
        status_changed = Activity.objects.filter(
            company=self.mandant,
            activity_type='contract.status_changed'
        ).count()
        
        self.assertEqual(status_changed, initial_count)
