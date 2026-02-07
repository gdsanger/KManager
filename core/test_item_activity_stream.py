"""
Tests for ActivityStream integration in Item views
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal

from core.models import Item, ItemGroup, TaxRate, Kostenart, Mandant, Activity
from core.services.activity_stream import ActivityStreamService

User = get_user_model()


class ItemActivityStreamTestCase(TestCase):
    """Test cases for item activity stream integration"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test company
        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='DE123456789'
        )
        
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code="VAT",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
        
        # Create cost types
        self.cost_type_1 = Kostenart.objects.create(
            name="Hauptkostenart Material",
            umsatzsteuer_satz="19"
        )
        self.cost_type_2 = Kostenart.objects.create(
            name="Hauptkostenart Dienstleistung",
            umsatzsteuer_satz="19"
        )
        
        # Create main item group
        self.main_group = ItemGroup.objects.create(
            code='MAT',
            name='Material',
            group_type='MAIN'
        )
        
        # Create sub item group
        self.sub_group = ItemGroup.objects.create(
            code='MAT-BAU',
            name='Baumaterial',
            group_type='SUB',
            parent=self.main_group
        )
    
    def test_item_creation_logs_activity(self):
        """Test that creating an item logs ITEM_CREATED activity"""
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Create item via AJAX endpoint
        response = self.client.post(reverse('item_save'), {
            'article_no': 'TEST-001',
            'short_text_1': 'Test Article',
            'short_text_2': 'Second text',
            'long_text': 'Long description',
            'net_price': '100.00',
            'purchase_price': '50.00',
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.cost_type_1.pk,
            'item_type': 'MATERIAL',
            'is_active': 'on',
            'is_discountable': 'on',
        })
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify activity was logged
        activities = Activity.objects.filter(activity_type='ITEM_CREATED')
        self.assertEqual(activities.count(), 1)
        
        activity = activities.first()
        self.assertEqual(activity.company, self.company)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.activity_type, 'ITEM_CREATED')
        self.assertEqual(activity.actor, self.user)
        self.assertEqual(activity.severity, 'INFO')
        self.assertIn('TEST-001', activity.title)
        self.assertIn('Test Article', activity.description)
        self.assertIn('/items/', activity.target_url)
    
    def test_item_update_logs_activity(self):
        """Test that updating an item logs ITEM_UPDATED activity"""
        # Create an item first
        item = Item.objects.create(
            article_no='TEST-002',
            short_text_1='Original Text',
            net_price=Decimal('100.00'),
            purchase_price=Decimal('50.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type='MATERIAL'
        )
        
        # Clear existing activities
        Activity.objects.all().delete()
        
        # Update item via AJAX endpoint
        response = self.client.post(reverse('item_save'), {
            'item_id': item.pk,
            'article_no': 'TEST-002',
            'short_text_1': 'Updated Text',  # Changed
            'short_text_2': '',
            'long_text': '',
            'net_price': '100.00',
            'purchase_price': '50.00',
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.cost_type_1.pk,
            'item_type': 'MATERIAL',
            'is_active': 'on',
            'is_discountable': 'on',
        })
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify activity was logged
        activities = Activity.objects.filter(activity_type='ITEM_UPDATED')
        self.assertEqual(activities.count(), 1)
        
        activity = activities.first()
        self.assertEqual(activity.company, self.company)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.activity_type, 'ITEM_UPDATED')
        self.assertEqual(activity.actor, self.user)
        self.assertEqual(activity.severity, 'INFO')
        self.assertIn('TEST-002', activity.title)
        self.assertIn('/items/', activity.target_url)
    
    def test_item_status_change_logs_specific_activity(self):
        """Test that changing item status logs ITEM_STATUS_CHANGED activity"""
        # Create an active item first
        item = Item.objects.create(
            article_no='TEST-003',
            short_text_1='Status Test Item',
            net_price=Decimal('100.00'),
            purchase_price=Decimal('50.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type='MATERIAL',
            is_active=True
        )
        
        # Clear existing activities
        Activity.objects.all().delete()
        
        # Update item status via AJAX endpoint (deactivate)
        response = self.client.post(reverse('item_save'), {
            'item_id': item.pk,
            'article_no': 'TEST-003',
            'short_text_1': 'Status Test Item',
            'short_text_2': '',
            'long_text': '',
            'net_price': '100.00',
            'purchase_price': '50.00',
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.cost_type_1.pk,
            'item_type': 'MATERIAL',
            # Note: is_active checkbox not sent = unchecked = False
            'is_discountable': 'on',
        })
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify status change activity was logged (not generic update)
        activities = Activity.objects.filter(activity_type='ITEM_STATUS_CHANGED')
        self.assertEqual(activities.count(), 1)
        
        activity = activities.first()
        self.assertEqual(activity.company, self.company)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.activity_type, 'ITEM_STATUS_CHANGED')
        self.assertEqual(activity.actor, self.user)
        self.assertEqual(activity.severity, 'INFO')
        self.assertIn('TEST-003', activity.title)
        self.assertIn('deaktiviert', activity.description)
        self.assertIn('aktiv', activity.description)
        self.assertIn('/items/', activity.target_url)
        
        # Verify no generic ITEM_UPDATED was logged
        generic_activities = Activity.objects.filter(activity_type='ITEM_UPDATED')
        self.assertEqual(generic_activities.count(), 0)
    
    def test_item_update_without_changes_no_activity(self):
        """Test that saving an item without changes doesn't log activity"""
        # Create an item first
        item = Item.objects.create(
            article_no='TEST-004',
            short_text_1='No Change Item',
            net_price=Decimal('100.00'),
            purchase_price=Decimal('50.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type='MATERIAL'
        )
        
        # Clear existing activities
        Activity.objects.all().delete()
        
        # "Update" item with same values
        response = self.client.post(reverse('item_save'), {
            'item_id': item.pk,
            'article_no': 'TEST-004',
            'short_text_1': 'No Change Item',  # Same
            'short_text_2': '',
            'long_text': '',
            'net_price': '100.00',  # Same
            'purchase_price': '50.00',  # Same
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.cost_type_1.pk,
            'item_type': 'MATERIAL',  # Same
            'is_active': 'on',
            'is_discountable': 'on',
        })
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify NO activity was logged (no changes)
        activities = Activity.objects.all()
        self.assertEqual(activities.count(), 0)
    
    def test_activity_contains_correct_metadata(self):
        """Test that activities contain correct metadata and links"""
        # Clear existing activities
        Activity.objects.all().delete()
        
        # Create item via AJAX endpoint
        response = self.client.post(reverse('item_save'), {
            'article_no': 'META-001',
            'short_text_1': 'Metadata Test',
            'short_text_2': '',
            'long_text': '',
            'net_price': '200.00',
            'purchase_price': '100.00',
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.cost_type_1.pk,
            'item_type': 'SERVICE',
            'is_active': 'on',
            'is_discountable': 'on',
        })
        
        # Get created item
        data = response.json()
        item_id = data['item_id']
        
        # Verify activity
        activity = Activity.objects.filter(activity_type='ITEM_CREATED').first()
        self.assertIsNotNone(activity)
        
        # Check metadata fields
        self.assertEqual(activity.company, self.company)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        
        # Check target_url is clickable and points to correct item
        self.assertIn(f'selected={item_id}', activity.target_url)
        self.assertTrue(activity.target_url.startswith('/items/'))
    
    def test_item_status_activation_logs_correct_description(self):
        """Test that activating an item logs correct status description"""
        # Create an inactive item first
        item = Item.objects.create(
            article_no='TEST-005',
            short_text_1='Activation Test',
            net_price=Decimal('100.00'),
            purchase_price=Decimal('50.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type='MATERIAL',
            is_active=False
        )
        
        # Clear existing activities
        Activity.objects.all().delete()
        
        # Activate the item
        response = self.client.post(reverse('item_save'), {
            'item_id': item.pk,
            'article_no': 'TEST-005',
            'short_text_1': 'Activation Test',
            'short_text_2': '',
            'long_text': '',
            'net_price': '100.00',
            'purchase_price': '50.00',
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.cost_type_1.pk,
            'item_type': 'MATERIAL',
            'is_active': 'on',  # Activated
            'is_discountable': 'on',
        })
        
        # Check response
        self.assertEqual(response.status_code, 200)
        
        # Verify status change activity
        activity = Activity.objects.filter(activity_type='ITEM_STATUS_CHANGED').first()
        self.assertIsNotNone(activity)
        self.assertIn('aktiviert', activity.description)
        self.assertIn('inaktiv', activity.description)
