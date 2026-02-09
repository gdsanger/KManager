"""
Tests for Aktivitaet filter and privacy functionality.
Tests the URL-based filter (responsible|created|all) and privat flag enforcement.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date, timedelta
from vermietung.models import Aktivitaet

User = get_user_model()


class AktivitaetFilterTest(TestCase):
    """Tests for the Aktivitaet filter functionality in Kanban view."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create users
        self.user_a = User.objects.create_user(
            username='user_a',
            password='testpass123',
            email='user_a@example.com',
            is_staff=True
        )
        self.user_b = User.objects.create_user(
            username='user_b',
            password='testpass123',
            email='user_b@example.com',
            is_staff=True
        )
        self.user_c = User.objects.create_user(
            username='user_c',
            password='testpass123',
            email='user_c@example.com',
            is_staff=True
        )
        
        # Create client and login as user_a
        self.client = Client()
        self.client.login(username='user_a', password='testpass123')
        
        # Create test activities
        # Activity 1: Created by A, assigned to B, privat=False
        self.activity_1 = Aktivitaet.objects.create(
            titel='Activity 1',
            beschreibung='Created by A, assigned to B, public',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_a,
            assigned_user=self.user_b,
            privat=False
        )
        
        # Activity 2: Created by A, assigned to A, privat=False
        self.activity_2 = Aktivitaet.objects.create(
            titel='Activity 2',
            beschreibung='Created by A, assigned to A, public',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_a,
            assigned_user=self.user_a,
            privat=False
        )
        
        # Activity 3: Created by B, assigned to A, privat=False
        self.activity_3 = Aktivitaet.objects.create(
            titel='Activity 3',
            beschreibung='Created by B, assigned to A, public',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_b,
            assigned_user=self.user_a,
            privat=False
        )
        
        # Activity 4: Created by B, assigned to C, privat=False
        self.activity_4 = Aktivitaet.objects.create(
            titel='Activity 4',
            beschreibung='Created by B, assigned to C, public',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_b,
            assigned_user=self.user_c,
            privat=False
        )
    
    def test_kanban_default_filter_responsible(self):
        """Test that default filter (no parameter) shows activities where user is assigned_user."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban'))
        self.assertEqual(response.status_code, 200)
        
        # User A should see activities where they are assigned_user: Activity 2, 3
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        self.assertIn(self.activity_2.id, aktivitaeten_ids)
        self.assertIn(self.activity_3.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_1.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_4.id, aktivitaeten_ids)
        
        # Check filter_mode in context
        self.assertEqual(response.context['filter_mode'], 'responsible')
    
    def test_kanban_filter_responsible_explicit(self):
        """Test filter=responsible shows activities where user is assigned_user."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=responsible')
        self.assertEqual(response.status_code, 200)
        
        # User A should see activities where they are assigned_user: Activity 2, 3
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        self.assertIn(self.activity_2.id, aktivitaeten_ids)
        self.assertIn(self.activity_3.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_1.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_4.id, aktivitaeten_ids)
        
        self.assertEqual(response.context['filter_mode'], 'responsible')
    
    def test_kanban_filter_created(self):
        """Test filter=created shows activities where user is ersteller."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=created')
        self.assertEqual(response.status_code, 200)
        
        # User A should see activities where they are ersteller: Activity 1, 2
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        self.assertIn(self.activity_1.id, aktivitaeten_ids)
        self.assertIn(self.activity_2.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_3.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_4.id, aktivitaeten_ids)
        
        self.assertEqual(response.context['filter_mode'], 'created')
    
    def test_kanban_filter_all(self):
        """Test filter=all shows all activities (with privacy rules)."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=all')
        self.assertEqual(response.status_code, 200)
        
        # User A should see all public activities: Activity 1, 2, 3, 4
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        self.assertIn(self.activity_1.id, aktivitaeten_ids)
        self.assertIn(self.activity_2.id, aktivitaeten_ids)
        self.assertIn(self.activity_3.id, aktivitaeten_ids)
        self.assertIn(self.activity_4.id, aktivitaeten_ids)
        
        self.assertEqual(response.context['filter_mode'], 'all')
    
    def test_kanban_filter_invalid_fallback(self):
        """Test that invalid filter parameter falls back to 'responsible'."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=invalid')
        self.assertEqual(response.status_code, 200)
        
        # Should behave like 'responsible'
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        self.assertIn(self.activity_2.id, aktivitaeten_ids)
        self.assertIn(self.activity_3.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_1.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_4.id, aktivitaeten_ids)
        
        self.assertEqual(response.context['filter_mode'], 'responsible')
    
    def test_kanban_filter_with_null_ersteller(self):
        """Test that activities with NULL ersteller don't appear in 'created' filter."""
        # Create activity with no ersteller
        activity_no_creator = Aktivitaet.objects.create(
            titel='Activity without creator',
            beschreibung='No ersteller set',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=None,  # Explicitly NULL
            assigned_user=self.user_a,
            privat=False
        )
        
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=created')
        self.assertEqual(response.status_code, 200)
        
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        # Activity without ersteller should NOT appear
        self.assertNotIn(activity_no_creator.id, aktivitaeten_ids)
        
        # But it SHOULD appear in 'responsible' filter since assigned_user is set
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=responsible')
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        self.assertIn(activity_no_creator.id, aktivitaeten_ids)
    
    def test_kanban_filter_with_null_assigned_user(self):
        """Test that activities with NULL assigned_user don't appear in 'responsible' filter."""
        # Create activity with no assigned_user
        activity_no_assignee = Aktivitaet.objects.create(
            titel='Activity without assignee',
            beschreibung='No assigned_user set',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_a,
            assigned_user=None,  # Explicitly NULL
            privat=False
        )
        
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=responsible')
        self.assertEqual(response.status_code, 200)
        
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        # Activity without assigned_user should NOT appear
        self.assertNotIn(activity_no_assignee.id, aktivitaeten_ids)
        
        # But it SHOULD appear in 'created' filter since ersteller is set
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=created')
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        self.assertIn(activity_no_assignee.id, aktivitaeten_ids)


class AktivitaetPrivacyTest(TestCase):
    """Tests for the privat flag enforcement."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create users
        self.user_a = User.objects.create_user(
            username='user_a',
            password='testpass123',
            email='user_a@example.com',
            is_staff=True
        )
        self.user_b = User.objects.create_user(
            username='user_b',
            password='testpass123',
            email='user_b@example.com',
            is_staff=True
        )
        self.user_c = User.objects.create_user(
            username='user_c',
            password='testpass123',
            email='user_c@example.com',
            is_staff=True
        )
        
        # Create client
        self.client = Client()
        
        # Create test activities
        # Activity 1: Created by A, assigned to B, privat=True
        self.activity_private_1 = Aktivitaet.objects.create(
            titel='Private Activity 1',
            beschreibung='Created by A, assigned to B, private',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_a,
            assigned_user=self.user_b,
            privat=True
        )
        
        # Activity 2: Created by A, assigned to A, privat=True
        self.activity_private_2 = Aktivitaet.objects.create(
            titel='Private Activity 2',
            beschreibung='Created by A, assigned to A, private',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_a,
            assigned_user=self.user_a,
            privat=True
        )
        
        # Activity 3: Created by B, assigned to C, privat=True
        self.activity_private_3 = Aktivitaet.objects.create(
            titel='Private Activity 3',
            beschreibung='Created by B, assigned to C, private',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_b,
            assigned_user=self.user_c,
            privat=True
        )
        
        # Activity 4: Created by A, assigned to C, privat=False (for comparison)
        self.activity_public = Aktivitaet.objects.create(
            titel='Public Activity',
            beschreibung='Created by A, assigned to C, public',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user_a,
            assigned_user=self.user_c,
            privat=False
        )
    
    def test_private_activity_visible_to_creator(self):
        """Test that private activities are visible to the creator."""
        self.client.login(username='user_a', password='testpass123')
        
        # Test with filter=all
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=all')
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        # User A created activity_private_1 and activity_private_2
        self.assertIn(self.activity_private_1.id, aktivitaeten_ids)
        self.assertIn(self.activity_private_2.id, aktivitaeten_ids)
        # User A did not create activity_private_3 and is not assigned
        self.assertNotIn(self.activity_private_3.id, aktivitaeten_ids)
        # Public activity should be visible
        self.assertIn(self.activity_public.id, aktivitaeten_ids)
    
    def test_private_activity_visible_to_assigned_user(self):
        """Test that private activities are visible to the assigned user."""
        self.client.login(username='user_b', password='testpass123')
        
        # Test with filter=all
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=all')
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        # User B is assigned to activity_private_1
        self.assertIn(self.activity_private_1.id, aktivitaeten_ids)
        # User B is not assigned to or creator of activity_private_2
        self.assertNotIn(self.activity_private_2.id, aktivitaeten_ids)
        # User B created activity_private_3
        self.assertIn(self.activity_private_3.id, aktivitaeten_ids)
        # Public activity should be visible
        self.assertIn(self.activity_public.id, aktivitaeten_ids)
    
    def test_private_activity_not_visible_to_others(self):
        """Test that private activities are not visible to other users."""
        self.client.login(username='user_c', password='testpass123')
        
        # Test with filter=all
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=all')
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        # User C is not creator or assigned to activity_private_1 or activity_private_2
        self.assertNotIn(self.activity_private_1.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_private_2.id, aktivitaeten_ids)
        # User C is assigned to activity_private_3
        self.assertIn(self.activity_private_3.id, aktivitaeten_ids)
        # Public activity should be visible
        self.assertIn(self.activity_public.id, aktivitaeten_ids)
    
    def test_private_activity_in_responsible_filter(self):
        """Test privacy enforcement with filter=responsible."""
        self.client.login(username='user_c', password='testpass123')
        
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=responsible')
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        # User C is assigned to activity_private_3 (private) and activity_public (public)
        self.assertIn(self.activity_private_3.id, aktivitaeten_ids)
        self.assertIn(self.activity_public.id, aktivitaeten_ids)
        # Should not see other private activities
        self.assertNotIn(self.activity_private_1.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_private_2.id, aktivitaeten_ids)
    
    def test_private_activity_in_created_filter(self):
        """Test privacy enforcement with filter=created."""
        self.client.login(username='user_a', password='testpass123')
        
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=created')
        aktivitaeten_ids = []
        for status_key in ['aktivitaeten_offen', 'aktivitaeten_in_bearbeitung', 
                          'aktivitaeten_erledigt', 'aktivitaeten_abgebrochen']:
            aktivitaeten_ids.extend([a.id for a in response.context[status_key]])
        
        # User A created activity_private_1, activity_private_2, and activity_public
        self.assertIn(self.activity_private_1.id, aktivitaeten_ids)
        self.assertIn(self.activity_private_2.id, aktivitaeten_ids)
        self.assertIn(self.activity_public.id, aktivitaeten_ids)
        # Should not see activity_private_3 (created by B)
        self.assertNotIn(self.activity_private_3.id, aktivitaeten_ids)
    
    def test_privacy_in_list_view(self):
        """Test that privacy enforcement works in aktivitaet_list view."""
        self.client.login(username='user_c', password='testpass123')
        
        response = self.client.get(reverse('vermietung:aktivitaet_list'))
        self.assertEqual(response.status_code, 200)
        
        # Extract activity IDs from paginated results
        aktivitaeten_ids = [a.id for a in response.context['page_obj']]
        
        # User C should only see activity_private_3 (assigned) and activity_public
        self.assertIn(self.activity_private_3.id, aktivitaeten_ids)
        self.assertIn(self.activity_public.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_private_1.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_private_2.id, aktivitaeten_ids)
    
    def test_privacy_in_assigned_list_view(self):
        """Test that privacy enforcement works in aktivitaet_assigned_list view."""
        self.client.login(username='user_b', password='testpass123')
        
        response = self.client.get(reverse('vermietung:aktivitaet_assigned_list'))
        self.assertEqual(response.status_code, 200)
        
        # Extract activity IDs from paginated results
        aktivitaeten_ids = [a.id for a in response.context['page_obj']]
        
        # User B is assigned to activity_private_1 only
        self.assertIn(self.activity_private_1.id, aktivitaeten_ids)
        # Should not see other private activities
        self.assertNotIn(self.activity_private_2.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_private_3.id, aktivitaeten_ids)
    
    def test_privacy_in_created_list_view(self):
        """Test that privacy enforcement works in aktivitaet_created_list view."""
        self.client.login(username='user_b', password='testpass123')
        
        response = self.client.get(reverse('vermietung:aktivitaet_created_list'))
        self.assertEqual(response.status_code, 200)
        
        # Extract activity IDs from paginated results
        aktivitaeten_ids = [a.id for a in response.context['page_obj']]
        
        # User B created activity_private_3 only
        self.assertIn(self.activity_private_3.id, aktivitaeten_ids)
        # Should not see other private activities
        self.assertNotIn(self.activity_private_1.id, aktivitaeten_ids)
        self.assertNotIn(self.activity_private_2.id, aktivitaeten_ids)


class AktivitaetFilterUITest(TestCase):
    """Tests for the filter UI in Kanban view."""
    
    def setUp(self):
        """Set up test data for all tests."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_filter_ui_present_in_template(self):
        """Test that filter buttons are present in the template."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban'))
        self.assertEqual(response.status_code, 200)
        
        # Check for filter buttons
        self.assertContains(response, 'Verantwortlich')
        self.assertContains(response, 'Erstellt')
        self.assertContains(response, 'Alle')
    
    def test_filter_responsible_active_state(self):
        """Test that 'responsible' filter button is marked as active."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=responsible')
        self.assertEqual(response.status_code, 200)
        
        # Check that the responsible button has active class
        self.assertContains(response, 'btn-primary')
    
    def test_filter_created_active_state(self):
        """Test that 'created' filter button is marked as active."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=created')
        self.assertEqual(response.status_code, 200)
        
        # Check that filter_mode is set correctly in context
        self.assertEqual(response.context['filter_mode'], 'created')
    
    def test_filter_all_active_state(self):
        """Test that 'all' filter button is marked as active."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban') + '?filter=all')
        self.assertEqual(response.status_code, 200)
        
        # Check that filter_mode is set correctly in context
        self.assertEqual(response.context['filter_mode'], 'all')
