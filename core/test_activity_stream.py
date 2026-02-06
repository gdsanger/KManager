"""
Tests for Activity model and ActivityStreamService
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from core.models import Activity, Mandant
from core.services.activity_stream import ActivityStreamService


class ActivityModelTestCase(TestCase):
    """Test Activity model functionality"""
    
    def setUp(self):
        """Create test data"""
        self.company = Mandant.objects.create(
            name='Test Company',
            adresse='Teststraße 1',
            plz='12345',
            ort='Teststadt'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    def test_create_activity_minimal(self):
        """Test creating activity with minimal required fields"""
        activity = Activity.objects.create(
            company=self.company,
            domain='RENTAL',
            activity_type='TEST_ACTION',
            title='Test Activity',
            target_url='/test/123'
        )
        
        self.assertEqual(activity.company, self.company)
        self.assertEqual(activity.domain, 'RENTAL')
        self.assertEqual(activity.activity_type, 'TEST_ACTION')
        self.assertEqual(activity.title, 'Test Activity')
        self.assertEqual(activity.target_url, '/test/123')
        self.assertEqual(activity.severity, 'INFO')  # Default
        self.assertIsNone(activity.description)  # Nullable
        self.assertIsNone(activity.actor)  # Nullable
        self.assertIsNotNone(activity.created_at)
    
    def test_create_activity_all_fields(self):
        """Test creating activity with all fields"""
        activity = Activity.objects.create(
            company=self.company,
            domain='ORDER',
            activity_type='INVOICE_CREATED',
            title='Rechnung erstellt',
            description='Rechnung #12345 wurde erfolgreich erstellt',
            target_url='/auftragsverwaltung/documents/123',
            actor=self.user,
            severity='WARNING'
        )
        
        self.assertEqual(activity.company, self.company)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.activity_type, 'INVOICE_CREATED')
        self.assertEqual(activity.title, 'Rechnung erstellt')
        self.assertEqual(activity.description, 'Rechnung #12345 wurde erfolgreich erstellt')
        self.assertEqual(activity.target_url, '/auftragsverwaltung/documents/123')
        self.assertEqual(activity.actor, self.user)
        self.assertEqual(activity.severity, 'WARNING')
    
    def test_activity_str(self):
        """Test Activity __str__ method"""
        activity = Activity.objects.create(
            company=self.company,
            domain='FINANCE',
            activity_type='PAYMENT_RECEIVED',
            title='Zahlung eingegangen',
            target_url='/finance/payments/456'
        )
        
        expected = f"{self.company.name} - Finanzen: Zahlung eingegangen"
        self.assertEqual(str(activity), expected)
    
    def test_activity_ordering(self):
        """Test that activities are ordered by created_at DESC"""
        # Create activities with slight time differences
        activity1 = Activity.objects.create(
            company=self.company,
            domain='RENTAL',
            activity_type='TEST_1',
            title='First',
            target_url='/test/1'
        )
        
        activity2 = Activity.objects.create(
            company=self.company,
            domain='RENTAL',
            activity_type='TEST_2',
            title='Second',
            target_url='/test/2'
        )
        
        activity3 = Activity.objects.create(
            company=self.company,
            domain='RENTAL',
            activity_type='TEST_3',
            title='Third',
            target_url='/test/3'
        )
        
        # Retrieve all activities
        activities = list(Activity.objects.all())
        
        # Should be ordered newest first
        self.assertEqual(activities[0], activity3)
        self.assertEqual(activities[1], activity2)
        self.assertEqual(activities[2], activity1)


class ActivityStreamServiceTestCase(TestCase):
    """Test ActivityStreamService functionality"""
    
    def setUp(self):
        """Create test data"""
        self.company1 = Mandant.objects.create(
            name='Company 1',
            adresse='Straße 1',
            plz='11111',
            ort='Stadt 1'
        )
        self.company2 = Mandant.objects.create(
            name='Company 2',
            adresse='Straße 2',
            plz='22222',
            ort='Stadt 2'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    def test_add_minimal(self):
        """Test adding activity with minimal parameters"""
        activity = ActivityStreamService.add(
            company=self.company1,
            domain='RENTAL',
            activity_type='CONTRACT_CREATED',
            title='Vertrag erstellt',
            target_url='/vermietung/contracts/1'
        )
        
        self.assertIsInstance(activity, Activity)
        self.assertEqual(activity.company, self.company1)
        self.assertEqual(activity.domain, 'RENTAL')
        self.assertEqual(activity.activity_type, 'CONTRACT_CREATED')
        self.assertEqual(activity.title, 'Vertrag erstellt')
        self.assertEqual(activity.target_url, '/vermietung/contracts/1')
        self.assertEqual(activity.severity, 'INFO')
        self.assertIsNone(activity.description)
        self.assertIsNone(activity.actor)
    
    def test_add_all_parameters(self):
        """Test adding activity with all parameters"""
        activity = ActivityStreamService.add(
            company=self.company1,
            domain='ORDER',
            activity_type='INVOICE_CREATED',
            title='Rechnung erstellt',
            target_url='/auftragsverwaltung/documents/123',
            description='Rechnung für Projekt XYZ',
            actor=self.user,
            severity='WARNING'
        )
        
        self.assertIsInstance(activity, Activity)
        self.assertEqual(activity.company, self.company1)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.activity_type, 'INVOICE_CREATED')
        self.assertEqual(activity.title, 'Rechnung erstellt')
        self.assertEqual(activity.target_url, '/auftragsverwaltung/documents/123')
        self.assertEqual(activity.description, 'Rechnung für Projekt XYZ')
        self.assertEqual(activity.actor, self.user)
        self.assertEqual(activity.severity, 'WARNING')
    
    def test_add_invalid_domain(self):
        """Test adding activity with invalid domain raises ValueError"""
        with self.assertRaises(ValueError) as context:
            ActivityStreamService.add(
                company=self.company1,
                domain='INVALID_DOMAIN',
                activity_type='TEST',
                title='Test',
                target_url='/test'
            )
        
        self.assertIn('Invalid domain', str(context.exception))
    
    def test_add_invalid_severity(self):
        """Test adding activity with invalid severity raises ValueError"""
        with self.assertRaises(ValueError) as context:
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type='TEST',
                title='Test',
                target_url='/test',
                severity='INVALID_SEVERITY'
            )
        
        self.assertIn('Invalid severity', str(context.exception))
    
    def test_latest_default(self):
        """Test latest() with default parameters"""
        # Create 25 activities
        for i in range(25):
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type=f'TEST_{i}',
                title=f'Activity {i}',
                target_url=f'/test/{i}'
            )
        
        # Get latest (default n=20)
        activities = ActivityStreamService.latest()
        
        self.assertEqual(len(activities), 20)
        # Should be ordered newest first
        self.assertEqual(activities[0].activity_type, 'TEST_24')
        self.assertEqual(activities[19].activity_type, 'TEST_5')
    
    def test_latest_with_limit(self):
        """Test latest() with custom limit"""
        # Create 30 activities
        for i in range(30):
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type=f'TEST_{i}',
                title=f'Activity {i}',
                target_url=f'/test/{i}'
            )
        
        # Get latest 10
        activities = ActivityStreamService.latest(n=10)
        
        self.assertEqual(len(activities), 10)
        self.assertEqual(activities[0].activity_type, 'TEST_29')
        self.assertEqual(activities[9].activity_type, 'TEST_20')
    
    def test_latest_filter_by_company(self):
        """Test latest() filtered by company"""
        # Create activities for company1
        for i in range(5):
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type=f'COMPANY1_{i}',
                title=f'Company 1 Activity {i}',
                target_url=f'/test/{i}'
            )
        
        # Create activities for company2
        for i in range(5):
            ActivityStreamService.add(
                company=self.company2,
                domain='RENTAL',
                activity_type=f'COMPANY2_{i}',
                title=f'Company 2 Activity {i}',
                target_url=f'/test/{i}'
            )
        
        # Get activities for company1 only
        activities = ActivityStreamService.latest(company=self.company1)
        
        self.assertEqual(len(activities), 5)
        for activity in activities:
            self.assertEqual(activity.company, self.company1)
    
    def test_latest_filter_by_domain(self):
        """Test latest() filtered by domain"""
        # Create RENTAL activities
        for i in range(3):
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type=f'RENTAL_{i}',
                title=f'Rental Activity {i}',
                target_url=f'/rental/{i}'
            )
        
        # Create ORDER activities
        for i in range(4):
            ActivityStreamService.add(
                company=self.company1,
                domain='ORDER',
                activity_type=f'ORDER_{i}',
                title=f'Order Activity {i}',
                target_url=f'/order/{i}'
            )
        
        # Create FINANCE activities
        for i in range(2):
            ActivityStreamService.add(
                company=self.company1,
                domain='FINANCE',
                activity_type=f'FINANCE_{i}',
                title=f'Finance Activity {i}',
                target_url=f'/finance/{i}'
            )
        
        # Filter by RENTAL
        rental_activities = ActivityStreamService.latest(domain='RENTAL')
        self.assertEqual(len(rental_activities), 3)
        for activity in rental_activities:
            self.assertEqual(activity.domain, 'RENTAL')
        
        # Filter by ORDER
        order_activities = ActivityStreamService.latest(domain='ORDER')
        self.assertEqual(len(order_activities), 4)
        for activity in order_activities:
            self.assertEqual(activity.domain, 'ORDER')
    
    def test_latest_filter_by_since(self):
        """Test latest() filtered by since datetime"""
        from django.utils import timezone
        
        # Get the current time
        now = timezone.now()
        
        # Create an old activity with a past timestamp
        # We need to temporarily save it with a past created_at
        old_activity = Activity(
            company=self.company1,
            domain='RENTAL',
            activity_type='OLD',
            title='Old Activity',
            target_url='/old'
        )
        old_activity.save()
        # Manually update created_at to 2 hours ago using queryset update
        Activity.objects.filter(id=old_activity.id).update(
            created_at=now - timedelta(hours=2)
        )
        
        # Create recent activities (simulated as just created)
        for i in range(5):
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type=f'RECENT_{i}',
                title=f'Recent Activity {i}',
                target_url=f'/recent/{i}'
            )
        
        # Filter to only get activities from last hour
        one_hour_ago = now - timedelta(hours=1)
        recent_activities = list(ActivityStreamService.latest(since=one_hour_ago))
        
        # Should only get the 5 recent ones, not the old one
        self.assertEqual(len(recent_activities), 5)
        activity_types = [a.activity_type for a in recent_activities]
        self.assertNotIn('OLD', activity_types)
    
    def test_latest_combined_filters(self):
        """Test latest() with multiple filters combined"""
        # Create various activities
        # Company 1, RENTAL, recent
        for i in range(3):
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type=f'C1_RENTAL_{i}',
                title='Activity',
                target_url='/test'
            )
        
        # Company 1, ORDER, recent
        for i in range(2):
            ActivityStreamService.add(
                company=self.company1,
                domain='ORDER',
                activity_type=f'C1_ORDER_{i}',
                title='Activity',
                target_url='/test'
            )
        
        # Company 2, RENTAL, recent
        for i in range(4):
            ActivityStreamService.add(
                company=self.company2,
                domain='RENTAL',
                activity_type=f'C2_RENTAL_{i}',
                title='Activity',
                target_url='/test'
            )
        
        # Filter: company1 + RENTAL + limit 2
        activities = ActivityStreamService.latest(
            n=2,
            company=self.company1,
            domain='RENTAL'
        )
        
        self.assertEqual(len(activities), 2)
        for activity in activities:
            self.assertEqual(activity.company, self.company1)
            self.assertEqual(activity.domain, 'RENTAL')
    
    def test_latest_ordering(self):
        """Test that latest() returns activities ordered by created_at DESC"""
        # Create activities with identifiable order
        for i in range(5):
            ActivityStreamService.add(
                company=self.company1,
                domain='RENTAL',
                activity_type=f'ACTIVITY_{i}',
                title=f'Activity {i}',
                target_url=f'/test/{i}'
            )
        
        activities = list(ActivityStreamService.latest(n=5))
        
        # Should be in reverse order (newest first)
        self.assertEqual(activities[0].activity_type, 'ACTIVITY_4')
        self.assertEqual(activities[1].activity_type, 'ACTIVITY_3')
        self.assertEqual(activities[2].activity_type, 'ACTIVITY_2')
        self.assertEqual(activities[3].activity_type, 'ACTIVITY_1')
        self.assertEqual(activities[4].activity_type, 'ACTIVITY_0')
