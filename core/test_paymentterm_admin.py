"""
Tests for PaymentTerm admin interface
"""
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from core.admin import PaymentTermAdmin
from core.models import PaymentTerm
from decimal import Decimal


class PaymentTermAdminTestCase(TestCase):
    """Test PaymentTerm admin interface"""
    
    def setUp(self):
        """Set up test data"""
        self.site = AdminSite()
        self.admin = PaymentTermAdmin(PaymentTerm, self.site)
        self.factory = RequestFactory()
        
        # Create a superuser for admin access
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='password'
        )
        
        # Create some test payment terms
        self.payment_term1 = PaymentTerm.objects.create(
            name="Net 30 days",
            net_days=30,
            is_default=True
        )
        self.payment_term2 = PaymentTerm.objects.create(
            name="2% 10 days, net 30 days",
            discount_days=10,
            discount_rate=Decimal("0.02"),
            net_days=30,
            is_default=False
        )
    
    def test_changelist_loads_without_error(self):
        """Test that the admin changelist loads without ProgrammingError
        
        This test verifies that there's no attempt to filter by company_id
        which doesn't exist in the PaymentTerm model (it's global).
        """
        request = self.factory.get('/admin/core/paymentterm/')
        request.user = self.user
        
        # Get queryset - this would fail with ProgrammingError if company filter is applied
        queryset = self.admin.get_queryset(request)
        
        # Verify we get all payment terms
        self.assertEqual(queryset.count(), 2)
        self.assertIn(self.payment_term1, queryset)
        self.assertIn(self.payment_term2, queryset)
    
    def test_list_display(self):
        """Test that list_display is configured correctly"""
        self.assertIn('name', self.admin.list_display)
        self.assertIn('discount_info', self.admin.list_display)
        self.assertIn('net_days', self.admin.list_display)
        self.assertIn('is_default', self.admin.list_display)
        
        # Ensure 'company' is NOT in list_display (it doesn't exist)
        self.assertNotIn('company', self.admin.list_display)
    
    def test_list_filter(self):
        """Test that list_filter doesn't include company"""
        # list_filter should only have is_default, not company
        self.assertEqual(self.admin.list_filter, ('is_default',))
    
    def test_search_fields(self):
        """Test that search_fields doesn't include company relations"""
        # search_fields should only have name, not company relations
        self.assertEqual(self.admin.search_fields, ('name',))
    
    def test_discount_info_display(self):
        """Test discount_info display method"""
        # With discount
        discount_info = self.admin.discount_info(self.payment_term2)
        self.assertIn('2.00%', discount_info)
        self.assertIn('10', discount_info)
        
        # Without discount
        discount_info = self.admin.discount_info(self.payment_term1)
        self.assertEqual(discount_info, '-')
    
    def test_queryset_has_no_company_filter(self):
        """Test that the queryset doesn't attempt to filter by company
        
        This is the core test to prevent the ProgrammingError mentioned in the issue.
        The test verifies that get_queryset() executes successfully without errors.
        """
        request = self.factory.get('/admin/core/paymentterm/')
        request.user = self.user
        
        # Get the queryset - this will raise an exception if it tries to access
        # non-existent company_id column
        queryset = self.admin.get_queryset(request)
        
        # Verify we can iterate over results without error
        list(queryset)
        
        # Verify we get the expected payment terms
        self.assertEqual(queryset.count(), 2)
