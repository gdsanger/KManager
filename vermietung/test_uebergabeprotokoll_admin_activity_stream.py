"""
Tests for ActivityStream integration in Uebergabeprotokoll Django Admin.

This module tests that ActivityStream events are correctly created when:
1. An Uebergabeprotokoll is created via Django Admin
2. An Uebergabeprotokoll is edited via Django Admin (with meaningful changes)
3. No event is created when editing without meaningful changes
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta

from core.models import Adresse, Mandant, Activity
from vermietung.models import MietObjekt, Vertrag, Uebergabeprotokoll

User = get_user_model()


class UebergabeprotokollAdminActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Uebergabeprotokoll Admin operations."""
    
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
        
        # Create a Vertrag
        self.vertrag = Vertrag.objects.create(
            vertragsnummer='V-001-ADM',
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date.today(),
            miete=Decimal('600.00'),
            kaution=Decimal('1800.00'),
            status='active',
            mandant=self.mandant
        )
    
    def test_admin_create_handover_generates_event(self):
        """Test that creating an Uebergabeprotokoll via Django Admin generates a handover.created event."""
        # Count initial activities
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.created'
        ).count()
        
        # Create uebergabeprotokoll via Django Admin
        response = self.client.post(
            reverse('admin:vermietung_uebergabeprotokoll_add'),
            {
                'vertrag': self.vertrag.pk,
                'mietobjekt': self.mietobjekt.pk,
                'typ': 'EINZUG',
                'uebergabetag': date.today().isoformat(),
                'anzahl_schluessel': 2,
                'person_vermieter': 'Hans Meier',
                'person_mieter': 'Max Mustermann',
                '_save': 'Save',
            },
            follow=True
        )
        
        # Verify the handover protocol was created
        self.assertEqual(response.status_code, 200)
        
        # Verify activity was created
        final_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.created'
        ).count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Get the created activity
        activity = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.created'
        ).latest('created_at')
        
        # Verify activity properties
        self.assertEqual(activity.domain, 'RENTAL')
        self.assertEqual(activity.actor, self.admin_user)
        self.assertEqual(activity.severity, 'INFO')
        self.assertIn('Übergabeprotokoll', activity.title)
        self.assertIn('via Admin', activity.description)
        self.assertIn('Einzug', activity.description)
        self.assertIsNotNone(activity.target_url)
    
    def test_admin_edit_handover_with_typ_change_generates_event(self):
        """Test that editing an Uebergabeprotokoll via Django Admin with typ change generates a handover.updated event."""
        # Create initial handover protocol
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date.today(),
            anzahl_schluessel=2,
            person_vermieter='Hans Meier',
            person_mieter='Max Mustermann'
        )
        
        # Count initial activities
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).count()
        
        # Edit handover protocol via Django Admin - change typ
        response = self.client.post(
            reverse('admin:vermietung_uebergabeprotokoll_change', args=[protokoll.pk]),
            {
                'vertrag': self.vertrag.pk,
                'mietobjekt': self.mietobjekt.pk,
                'typ': 'AUSZUG',  # Changed from EINZUG
                'uebergabetag': date.today().isoformat(),
                'anzahl_schluessel': 2,
                'person_vermieter': 'Hans Meier',
                'person_mieter': 'Max Mustermann',
                '_save': 'Save',
            },
            follow=True
        )
        
        # Verify update succeeded
        self.assertEqual(response.status_code, 200)
        
        # Verify activity was created
        final_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Get the created activity
        activity = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).latest('created_at')
        
        # Verify activity properties
        self.assertEqual(activity.domain, 'RENTAL')
        self.assertEqual(activity.actor, self.admin_user)
        self.assertEqual(activity.severity, 'INFO')
        self.assertIn('Übergabeprotokoll aktualisiert', activity.description)
        self.assertIn('Typ:', activity.description)
        self.assertIn('Einzug', activity.description)
        self.assertIn('Auszug', activity.description)
        self.assertIn('via Admin', activity.description)
    
    def test_admin_edit_handover_with_date_change_generates_event(self):
        """Test that editing an Uebergabeprotokoll via Django Admin with date change generates a handover.updated event."""
        # Create initial handover protocol
        old_date = date.today()
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=old_date,
            anzahl_schluessel=2,
            person_vermieter='Hans Meier',
            person_mieter='Max Mustermann'
        )
        
        # Count initial activities
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).count()
        
        # Edit handover protocol via Django Admin - change date
        new_date = old_date + timedelta(days=7)
        response = self.client.post(
            reverse('admin:vermietung_uebergabeprotokoll_change', args=[protokoll.pk]),
            {
                'vertrag': self.vertrag.pk,
                'mietobjekt': self.mietobjekt.pk,
                'typ': 'EINZUG',
                'uebergabetag': new_date.isoformat(),  # Changed date
                'anzahl_schluessel': 2,
                'person_vermieter': 'Hans Meier',
                'person_mieter': 'Max Mustermann',
                '_save': 'Save',
            },
            follow=True
        )
        
        # Verify update succeeded
        self.assertEqual(response.status_code, 200)
        
        # Verify activity was created
        final_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Get the created activity
        activity = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).latest('created_at')
        
        # Verify activity properties
        self.assertEqual(activity.domain, 'RENTAL')
        self.assertEqual(activity.actor, self.admin_user)
        self.assertEqual(activity.severity, 'INFO')
        self.assertIn('Übergabeprotokoll aktualisiert', activity.description)
        self.assertIn('Datum:', activity.description)
        self.assertIn(old_date.strftime('%d.%m.%Y'), activity.description)
        self.assertIn(new_date.strftime('%d.%m.%Y'), activity.description)
        self.assertIn('via Admin', activity.description)
    
    def test_admin_edit_handover_without_meaningful_change_no_event(self):
        """Test that editing an Uebergabeprotokoll via Django Admin without meaningful changes does NOT generate an event."""
        # Create initial handover protocol
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date.today(),
            anzahl_schluessel=2,
            person_vermieter='Hans Meier',
            person_mieter='Max Mustermann'
        )
        
        # Count initial activities
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).count()
        
        # Edit handover protocol via Django Admin - only change non-tracked field
        response = self.client.post(
            reverse('admin:vermietung_uebergabeprotokoll_change', args=[protokoll.pk]),
            {
                'vertrag': self.vertrag.pk,
                'mietobjekt': self.mietobjekt.pk,
                'typ': 'EINZUG',  # Same
                'uebergabetag': date.today().isoformat(),  # Same
                'anzahl_schluessel': 3,  # Changed but not tracked
                'person_vermieter': 'Hans Meier',
                'person_mieter': 'Max Mustermann',
                '_save': 'Save',
            },
            follow=True
        )
        
        # Verify update succeeded
        self.assertEqual(response.status_code, 200)
        
        # Verify NO activity was created
        final_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='handover.updated'
        ).count()
        self.assertEqual(final_count, initial_count)  # No change
