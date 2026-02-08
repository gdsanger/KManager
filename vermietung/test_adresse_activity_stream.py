"""
Tests for ActivityStream integration in Adresse CRUD operations.

This module tests that ActivityStream events are correctly created when:
1. An Adresse (generic address) is created/updated/deleted
2. A Kunde (customer) is created/updated/deleted
3. A Standort (location) is created/updated/deleted
4. A Lieferant (supplier) is created/updated/deleted
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.auth.models import Group

from core.models import Adresse, Mandant, Activity

User = get_user_model()


class AdresseActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Adresse (generic address) operations."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )
        
        # Create Vermietung group and add user to it
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
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
    
    def test_address_created_event(self):
        """Test that creating an Adresse generates an address.created event."""
        # Count initial activities in stream
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='address.created'
        ).count()
        
        # Create adresse via POST
        response = self.client.post(
            reverse('vermietung:adresse_create'),
            {
                'name': 'Max Mustermann',
                'strasse': 'Musterstrasse 1',
                'plz': '12345',
                'ort': 'Musterstadt',
                'land': 'Deutschland',
                'email': 'max@example.com',
            }
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='address.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Adresse:', event.title)
        self.assertIn('Max Mustermann', event.title)
        self.assertIn('Musterstrasse 1', event.description)
        self.assertIn('12345', event.description)
        self.assertIn('Musterstadt', event.description)
        self.assertTrue(event.target_url.startswith('/vermietung/adressen/'))
        self.assertEqual(event.severity, 'INFO')
    
    def test_address_updated_event(self):
        """Test that updating an Adresse generates an address.updated event."""
        # Create adresse
        adresse = Adresse.objects.create(
            adressen_type='Adresse',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland'
        )
        
        # Count initial activities
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='address.updated'
        ).count()
        
        # Update adresse via POST
        response = self.client.post(
            reverse('vermietung:adresse_edit', args=[adresse.pk]),
            {
                'name': 'Max Mustermann',
                'strasse': 'Neue Strasse 99',
                'plz': '54321',
                'ort': 'Neustadt',
                'land': 'Deutschland',
            }
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='address.updated'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Adresse:', event.title)
        self.assertIn('Neue Strasse 99', event.description)
        self.assertIn('54321', event.description)
        self.assertIn('Neustadt', event.description)
        self.assertEqual(event.severity, 'INFO')
    
    def test_address_deleted_event(self):
        """Test that deleting an Adresse generates an address.deleted event."""
        # Create adresse
        adresse = Adresse.objects.create(
            adressen_type='Adresse',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland'
        )
        
        # Count initial activities
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='address.deleted'
        ).count()
        
        # Delete adresse via POST
        response = self.client.post(
            reverse('vermietung:adresse_delete', args=[adresse.pk])
        )
        
        # Check that redirect happened (success)
        self.assertEqual(response.status_code, 302)
        
        # Verify stream event was created
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='address.deleted'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        # Verify event details
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertEqual(event.actor, self.user)
        self.assertIn('Adresse:', event.title)
        self.assertIn('Musterstrasse 1', event.description)
        self.assertEqual(event.severity, 'INFO')


class KundeActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Kunde (customer) operations."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create user with Vermietung access
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
        # Create client and login
        self.client = Client()
        self.client.force_login(self.user)
        
        # Create Mandant
        self.mandant = Mandant.objects.create(
            name='Test Company',
            adresse='Test Street 1',
            plz='12345',
            ort='Test City'
        )
    
    def test_customer_created_event(self):
        """Test that creating a Kunde generates a customer.created event."""
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='customer.created'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:kunde_create'),
            {
                'name': 'Kunde GmbH',
                'strasse': 'Kundenstrasse 1',
                'plz': '12345',
                'ort': 'Kundenstadt',
                'land': 'Deutschland',
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='customer.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertIn('Kunde:', event.title)
        self.assertIn('Kundenstrasse 1', event.description)
    
    def test_customer_updated_event(self):
        """Test that updating a Kunde generates a customer.updated event."""
        kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde GmbH',
            strasse='Kundenstrasse 1',
            plz='12345',
            ort='Kundenstadt',
            land='Deutschland'
        )
        
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='customer.updated'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:kunde_edit', args=[kunde.pk]),
            {
                'name': 'Kunde GmbH',
                'strasse': 'Neue Kundenstrasse 99',
                'plz': '54321',
                'ort': 'Neustadt',
                'land': 'Deutschland',
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='customer.updated'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
    
    def test_customer_deleted_event(self):
        """Test that deleting a Kunde generates a customer.deleted event."""
        kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde GmbH',
            strasse='Kundenstrasse 1',
            plz='12345',
            ort='Kundenstadt',
            land='Deutschland'
        )
        
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='customer.deleted'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:kunde_delete', args=[kunde.pk])
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='customer.deleted'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)


class StandortActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Standort (location) operations."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create user with Vermietung access
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
        # Create client and login
        self.client = Client()
        self.client.force_login(self.user)
        
        # Create Mandant
        self.mandant = Mandant.objects.create(
            name='Test Company',
            adresse='Test Street 1',
            plz='12345',
            ort='Test City'
        )
    
    def test_location_created_event(self):
        """Test that creating a Standort generates a location.created event."""
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='location.created'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:standort_create'),
            {
                'name': 'Hauptstandort',
                'strasse': 'Standortstrasse 1',
                'plz': '12345',
                'ort': 'Standortstadt',
                'land': 'Deutschland',
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='location.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertIn('Standort:', event.title)
        self.assertIn('Standortstrasse 1', event.description)
    
    def test_location_updated_event(self):
        """Test that updating a Standort generates a location.updated event."""
        standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Standortstrasse 1',
            plz='12345',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='location.updated'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:standort_edit', args=[standort.pk]),
            {
                'name': 'Hauptstandort',
                'strasse': 'Neue Standortstrasse 99',
                'plz': '54321',
                'ort': 'Neustadt',
                'land': 'Deutschland',
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='location.updated'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
    
    def test_location_deleted_event(self):
        """Test that deleting a Standort generates a location.deleted event."""
        standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Standortstrasse 1',
            plz='12345',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='location.deleted'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:standort_delete', args=[standort.pk])
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='location.deleted'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)


class LieferantActivityStreamTest(TestCase):
    """Tests for ActivityStream integration in Lieferant (supplier) operations."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create user with Vermietung access
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
        # Create client and login
        self.client = Client()
        self.client.force_login(self.user)
        
        # Create Mandant
        self.mandant = Mandant.objects.create(
            name='Test Company',
            adresse='Test Street 1',
            plz='12345',
            ort='Test City'
        )
    
    def test_supplier_created_event(self):
        """Test that creating a Lieferant generates a supplier.created event."""
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='supplier.created'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:lieferant_create'),
            {
                'name': 'Lieferant GmbH',
                'strasse': 'Lieferantenstrasse 1',
                'plz': '12345',
                'ort': 'Lieferantenstadt',
                'land': 'Deutschland',
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='supplier.created'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
        
        event = stream_events.latest('created_at')
        self.assertEqual(event.domain, 'RENTAL')
        self.assertIn('Lieferant:', event.title)
        self.assertIn('Lieferantenstrasse 1', event.description)
    
    def test_supplier_updated_event(self):
        """Test that updating a Lieferant generates a supplier.updated event."""
        lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant GmbH',
            strasse='Lieferantenstrasse 1',
            plz='12345',
            ort='Lieferantenstadt',
            land='Deutschland'
        )
        
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='supplier.updated'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:lieferant_edit', args=[lieferant.pk]),
            {
                'name': 'Lieferant GmbH',
                'strasse': 'Neue Lieferantenstrasse 99',
                'plz': '54321',
                'ort': 'Neustadt',
                'land': 'Deutschland',
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='supplier.updated'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
    
    def test_supplier_deleted_event(self):
        """Test that deleting a Lieferant generates a supplier.deleted event."""
        lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant GmbH',
            strasse='Lieferantenstrasse 1',
            plz='12345',
            ort='Lieferantenstadt',
            land='Deutschland'
        )
        
        initial_count = Activity.objects.filter(
            company=self.mandant,
            activity_type='supplier.deleted'
        ).count()
        
        response = self.client.post(
            reverse('vermietung:lieferant_delete', args=[lieferant.pk])
        )
        
        self.assertEqual(response.status_code, 302)
        
        stream_events = Activity.objects.filter(
            company=self.mandant,
            activity_type='supplier.deleted'
        )
        self.assertEqual(stream_events.count(), initial_count + 1)
