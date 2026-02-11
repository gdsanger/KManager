"""
Tests for Aktivitaet Kanban Drag & Drop functionality.

Tests cover:
1. Status update with permissions
2. Status update without permissions (403)
3. 7-day filter for "Erledigt" column
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from vermietung.models import Aktivitaet
from core.models import Adresse

User = get_user_model()


class AktivitaetKanbanDragDropTest(TestCase):
    """Tests for Kanban drag & drop status updates and 7-day filter."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a Mandant (required for ActivityStream)
        from core.models import Mandant
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
            is_staff=True  # Grant vermietung access
        )
        self.assigned_user = User.objects.create_user(
            username='assigneduser',
            password='testpass123',
            email='assigned@example.com',
            is_staff=True  # Grant vermietung access
        )
        
        # Create client and login as main test user
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_status_update_by_ersteller(self):
        """Test that ersteller can update activity status."""
        # Create activity where testuser is ersteller
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            status='OFFEN',
            ersteller=self.user
        )
        
        # Update status
        url = reverse('vermietung:aktivitaet_update_status', kwargs={'pk': aktivitaet.pk})
        response = self.client.post(url, {'status': 'IN_BEARBEITUNG'})
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify status was changed
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.status, 'IN_BEARBEITUNG')
    
    def test_status_update_by_assigned_user(self):
        """Test that assigned_user can update activity status."""
        # Create activity where testuser is assigned_user
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            status='OFFEN',
            ersteller=self.other_user,
            assigned_user=self.user
        )
        
        # Update status
        url = reverse('vermietung:aktivitaet_update_status', kwargs={'pk': aktivitaet.pk})
        response = self.client.post(url, {'status': 'ERLEDIGT'})
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify status was changed
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.status, 'ERLEDIGT')
    
    def test_status_update_permission_denied(self):
        """Test that user without permission cannot update activity status."""
        # Create activity where testuser is neither ersteller nor assigned_user
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            status='OFFEN',
            ersteller=self.other_user,
            assigned_user=self.assigned_user
        )
        
        # Try to update status
        url = reverse('vermietung:aktivitaet_update_status', kwargs={'pk': aktivitaet.pk})
        response = self.client.post(url, {'status': 'IN_BEARBEITUNG'})
        
        # Check response
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Berechtigung', data['error'])
        
        # Verify status was NOT changed
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.status, 'OFFEN')
    
    def test_status_update_invalid_status(self):
        """Test that invalid status is rejected."""
        # Create activity where testuser is ersteller
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            status='OFFEN',
            ersteller=self.user
        )
        
        # Try to update with invalid status
        url = reverse('vermietung:aktivitaet_update_status', kwargs={'pk': aktivitaet.pk})
        response = self.client.post(url, {'status': 'INVALID_STATUS'})
        
        # Check response
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Ungültiger Status', data['error'])
        
        # Verify status was NOT changed
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.status, 'OFFEN')
    
    def test_kanban_erledigt_filter_last_7_days(self):
        """Test that Erledigt column only shows activities from last 7 days."""
        now = timezone.now()
        
        # Create completed activity from 3 days ago (should be visible)
        aktivitaet_recent = Aktivitaet.objects.create(
            titel='Recent Completed',
            status='ERLEDIGT',
            ersteller=self.user,
            assigned_user=self.user
        )
        # Manually update updated_at using queryset update to bypass auto_now
        Aktivitaet.objects.filter(pk=aktivitaet_recent.pk).update(
            updated_at=now - timedelta(days=3)
        )
        aktivitaet_recent.refresh_from_db()
        
        # Create completed activity from 6.5 days ago (should be visible - within boundary)
        aktivitaet_boundary = Aktivitaet.objects.create(
            titel='Boundary Completed',
            status='ERLEDIGT',
            ersteller=self.user,
            assigned_user=self.user
        )
        # Manually update updated_at using queryset update to bypass auto_now
        Aktivitaet.objects.filter(pk=aktivitaet_boundary.pk).update(
            updated_at=now - timedelta(days=6, hours=12)
        )
        aktivitaet_boundary.refresh_from_db()
        
        # Create completed activity from 10 days ago (should NOT be visible)
        aktivitaet_old = Aktivitaet.objects.create(
            titel='Old Completed',
            status='ERLEDIGT',
            ersteller=self.user,
            assigned_user=self.user
        )
        # Manually update updated_at using queryset update to bypass auto_now
        Aktivitaet.objects.filter(pk=aktivitaet_old.pk).update(
            updated_at=now - timedelta(days=10)
        )
        aktivitaet_old.refresh_from_db()
        
        # Get Kanban view with filter=responsible (shows activities where user is assigned_user)
        url = reverse('vermietung:aktivitaet_kanban') + '?filter=responsible'
        response = self.client.get(url)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        aktivitaeten_erledigt = response.context['aktivitaeten_erledigt']
        
        # Verify only recent and boundary activities are shown
        self.assertIn(aktivitaet_recent, aktivitaeten_erledigt)
        self.assertIn(aktivitaet_boundary, aktivitaeten_erledigt)
        self.assertNotIn(aktivitaet_old, aktivitaeten_erledigt)
    
    def test_kanban_erledigt_filter_excludes_other_statuses(self):
        """Test that Erledigt column only shows ERLEDIGT status."""
        # Create activities with different statuses
        aktivitaet_offen = Aktivitaet.objects.create(
            titel='Open Activity',
            status='OFFEN',
            ersteller=self.user,
            assigned_user=self.user
        )
        
        aktivitaet_in_bearbeitung = Aktivitaet.objects.create(
            titel='In Progress Activity',
            status='IN_BEARBEITUNG',
            ersteller=self.user,
            assigned_user=self.user
        )
        
        aktivitaet_erledigt = Aktivitaet.objects.create(
            titel='Completed Activity',
            status='ERLEDIGT',
            ersteller=self.user,
            assigned_user=self.user
        )
        
        # Get Kanban view
        url = reverse('vermietung:aktivitaet_kanban') + '?filter=responsible'
        response = self.client.get(url)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        
        # Verify each column contains only correct status
        aktivitaeten_offen = response.context['aktivitaeten_offen']
        aktivitaeten_in_bearbeitung = response.context['aktivitaeten_in_bearbeitung']
        aktivitaeten_erledigt = response.context['aktivitaeten_erledigt']
        
        self.assertIn(aktivitaet_offen, aktivitaeten_offen)
        self.assertNotIn(aktivitaet_offen, aktivitaeten_erledigt)
        
        self.assertIn(aktivitaet_in_bearbeitung, aktivitaeten_in_bearbeitung)
        self.assertNotIn(aktivitaet_in_bearbeitung, aktivitaeten_erledigt)
        
        self.assertIn(aktivitaet_erledigt, aktivitaeten_erledigt)
        self.assertNotIn(aktivitaet_erledigt, aktivitaeten_offen)
    
    def test_status_update_requires_post(self):
        """Test that status update requires POST method."""
        # Create activity where testuser is ersteller
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aktivität',
            status='OFFEN',
            ersteller=self.user
        )
        
        # Try GET request
        url = reverse('vermietung:aktivitaet_update_status', kwargs={'pk': aktivitaet.pk})
        response = self.client.get(url)
        
        # Check response - should be 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
        
        # Verify status was NOT changed
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.status, 'OFFEN')
    
    def test_kanban_view_shows_hint_text(self):
        """Test that Kanban view shows drag & drop hint text."""
        url = reverse('vermietung:aktivitaet_kanban')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that hint text is in response
        self.assertContains(response, 'Tipp:')
        self.assertContains(response, 'Drag &amp; Drop')
        self.assertContains(response, 'Aufgaben können per Drag &amp; Drop')
