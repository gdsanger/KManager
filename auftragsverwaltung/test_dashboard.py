"""
Tests for Auftragsverwaltung Dashboard/Home view
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from core.models import Mandant, Activity
from core.services.activity_stream import ActivityStreamService


class AuftragsverwaltungDashboardTestCase(TestCase):
    """Test cases for the auftragsverwaltung dashboard home view."""

    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create a test company/Mandant
        self.company = Mandant.objects.create(
            name='Test Company',
            adresse='Test Address 123',
            plz='12345',
            ort='Test City'
        )
        
        # Create the client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_dashboard_shows_all_activity_domains(self):
        """
        Test that the dashboard activity stream shows activities from all domains,
        not just ORDER domain.
        """
        # Create activities in different domains
        rental_activity = ActivityStreamService.add(
            company=self.company,
            domain='RENTAL',
            activity_type='TEST_RENTAL',
            title='Test Rental Activity',
            target_url='/vermietung/test/',
            description='Test rental activity description'
        )
        
        order_activity = ActivityStreamService.add(
            company=self.company,
            domain='ORDER',
            activity_type='TEST_ORDER',
            title='Test Order Activity',
            target_url='/auftragsverwaltung/test/',
            description='Test order activity description'
        )
        
        finance_activity = ActivityStreamService.add(
            company=self.company,
            domain='FINANCE',
            activity_type='TEST_FINANCE',
            title='Test Finance Activity',
            target_url='/finanzen/test/',
            description='Test finance activity description'
        )
        
        # Request the dashboard
        response = self.client.get('/auftragsverwaltung/')
        
        # Verify the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Verify activities are in the context
        self.assertIn('activities', response.context)
        activities_list = list(response.context['activities'])
        
        # Verify all three activities are present (showing all domains)
        activity_ids = [a.id for a in activities_list]
        self.assertIn(rental_activity.id, activity_ids, 
                     "RENTAL domain activity should be shown")
        self.assertIn(order_activity.id, activity_ids,
                     "ORDER domain activity should be shown")
        self.assertIn(finance_activity.id, activity_ids,
                     "FINANCE domain activity should be shown")
        
        # Verify the count
        self.assertEqual(len(activities_list), 3,
                        "All 3 activities from different domains should be shown")
