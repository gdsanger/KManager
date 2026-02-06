"""
Tests for ActivityStream integration in Aktivitaet views.

This module tests that ActivityStream events are correctly created when:
1. An Aktivitaet is created
2. Status is changed
3. Assignment is changed
4. Aktivitaet is closed/completed
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta

from core.models import Adresse, Mandant, Activity
from vermietung.models import MietObjekt, Vertrag, Aktivitaet

User = get_user_model()


class AktivitaetActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Aktivitaet operations."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )
        self.assigned_user = User.objects.create_user(
            username='assigneduser',
            password='testpass123',
            email='assigned@example.com',
            is_staff=True
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
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
            verfuegbar=True,
            mandant=self.mandant
        )
        
        # Create a Vertrag with mandant
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
    
    def test_activity_created_event(self):
        """Test that creating an Aktivitaet generates an activity.created event."""
        # Count initial activities in stream
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.created'
        ).count()
        
        # Create aktivitaet
        response = self.client.post(
            reverse('vermietung:aktivitaet_create_from_vertrag', args=[self.vertrag.pk]),
            {
                'titel': 'Test Aktivität',
                'beschreibung': 'Test Beschreibung',
                'status': 'OFFEN',
                'prioritaet': 'NORMAL',
                'ersteller': self.user.pk,
            }
        )
        
        # Check redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Test Aktivität', event.title)
        self.assertIn('Offen', event.description)
        self.assertTrue(event.target_url.startswith('/vermietung/aktivitaeten/'))
    
    def test_status_changed_event(self):
        """Test that changing status generates an activity.status_changed event."""
        # Create aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial status_changed events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.status_changed'
        ).count()
        
        # Update status via edit view
        response = self.client.post(
            reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk]),
            {
                'titel': 'Test Aktivität',
                'beschreibung': 'Test Beschreibung',
                'status': 'IN_BEARBEITUNG',
                'prioritaet': 'NORMAL',
                'ersteller': self.user.pk,
            }
        )
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.status_changed'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Offen', event.description)
        self.assertIn('In Bearbeitung', event.description)
    
    def test_activity_closed_event(self):
        """Test that marking as completed generates an activity.closed event."""
        # Create aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial closed events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.closed'
        ).count()
        
        # Mark as completed
        response = self.client.post(
            reverse('vermietung:aktivitaet_mark_completed', args=[aktivitaet.pk])
        )
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.closed'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Erledigt', event.description)
    
    def test_activity_closed_via_edit(self):
        """Test that changing status to ERLEDIGT via edit generates activity.closed event."""
        # Create aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='IN_BEARBEITUNG',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial closed events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.closed'
        ).count()
        
        # Update status to ERLEDIGT via edit view
        response = self.client.post(
            reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk]),
            {
                'titel': 'Test Aktivität',
                'beschreibung': 'Test Beschreibung',
                'status': 'ERLEDIGT',
                'prioritaet': 'NORMAL',
                'ersteller': self.user.pk,
            }
        )
        
        # Verify stream event was created (should be activity.closed, not status_changed)
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.closed'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
    
    def test_assignment_changed_event(self):
        """Test that changing assignment generates an activity.assigned event."""
        # Create aktivitaet without assignment
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial assigned events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.assigned'
        ).count()
        
        # Assign to user via edit view
        response = self.client.post(
            reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk]),
            {
                'titel': 'Test Aktivität',
                'beschreibung': 'Test Beschreibung',
                'status': 'OFFEN',
                'prioritaet': 'NORMAL',
                'assigned_user': self.assigned_user.pk,
                'ersteller': self.user.pk,
            }
        )
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.assigned'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Niemand', event.description)
        self.assertIn('assigneduser', event.description)
    
    def test_assignment_changed_via_assign_view(self):
        """Test that assigning via assign view generates an activity.assigned event."""
        # Create aktivitaet without assignment
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial assigned events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.assigned'
        ).count()
        
        # Assign via assign view
        response = self.client.post(
            reverse('vermietung:aktivitaet_assign', args=[aktivitaet.pk]),
            {'assigned_user': self.assigned_user.pk}
        )
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.assigned'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
    
    def test_status_update_via_kanban(self):
        """Test that updating status via kanban generates appropriate event."""
        # Create aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial events
        initial_status_changed = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.status_changed'
        ).count()
        
        # Update status via kanban update_status view
        response = self.client.post(
            reverse('vermietung:aktivitaet_update_status', args=[aktivitaet.pk]),
            {'status': 'IN_BEARBEITUNG'}
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.status_changed'
        )
        self.assertEqual(stream_events.count(), initial_status_changed + 1)
    
    def test_close_via_kanban(self):
        """Test that closing via kanban generates activity.closed event."""
        # Create aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='IN_BEARBEITUNG',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial closed events
        initial_closed = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.closed'
        ).count()
        
        # Update status to ERLEDIGT via kanban
        response = self.client.post(
            reverse('vermietung:aktivitaet_update_status', args=[aktivitaet.pk]),
            {'status': 'ERLEDIGT'}
        )
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.closed'
        )
        self.assertEqual(stream_events.count(), initial_closed + 1)
    
    def test_no_event_when_no_change(self):
        """Test that no event is created when nothing actually changes."""
        # Create aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            assigned_user=self.assigned_user,
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Count initial events
        initial_count = Activity.objects.filter(company=self.mandant).count()
        
        # Update without changing status or assignment
        response = self.client.post(
            reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk]),
            {
                'titel': 'Test Aktivität Updated',  # Only title changed
                'beschreibung': 'Test Beschreibung',
                'status': 'OFFEN',  # Same status
                'prioritaet': 'HOCH',  # Priority changed
                'assigned_user': self.assigned_user.pk,  # Same assignment
                'ersteller': self.user.pk,
            }
        )
        
        # Verify no new status_changed or assigned events were created
        # (Only the aktivitaet creation might have created an event earlier)
        status_changed = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.status_changed'
        ).count()
        assigned = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.assigned'
        ).count()
        
        self.assertEqual(status_changed, 0)  # No status change event
        self.assertEqual(assigned, 0)  # No assignment change event
    
    def test_activity_with_mietobjekt_context(self):
        """Test that activities with mietobjekt context get correct mandant."""
        # Create aktivitaet with mietobjekt context
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            mietobjekt=self.mietobjekt,
            ersteller=self.user
        )
        
        # Count initial events
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.status_changed'
        ).count()
        
        # Change status
        response = self.client.post(
            reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk]),
            {
                'titel': 'Test Aktivität',
                'beschreibung': 'Test Beschreibung',
                'status': 'IN_BEARBEITUNG',
                'prioritaet': 'NORMAL',
                'ersteller': self.user.pk,
            }
        )
        
        # Verify stream event was created with correct company
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.status_changed'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        event = stream_events.latest('created_at')
        self.assertEqual(event.company, self.mandant)
    
    def test_event_has_valid_target_url(self):
        """Test that all events have a valid target_url."""
        # Create aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='NORMAL',
            vertrag=self.vertrag,
            ersteller=self.user
        )
        
        # Change status
        response = self.client.post(
            reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk]),
            {
                'titel': 'Test Aktivität',
                'beschreibung': 'Test Beschreibung',
                'status': 'ERLEDIGT',
                'prioritaet': 'NORMAL',
                'ersteller': self.user.pk,
            }
        )
        
        # Get the event
        event = Activity.objects.filter(
            company=self.mandant,
            activity_type='activity.closed'
        ).latest('created_at')
        
        # Verify target_url is valid and points to aktivitaet
        self.assertTrue(event.target_url)
        self.assertIn(f'/vermietung/aktivitaeten/{aktivitaet.pk}', event.target_url)
