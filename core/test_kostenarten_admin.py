"""
Tests for Kostenarten admin interface
"""
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from core.models import Kostenart
from core.admin import KostenartAdmin, UnterkostenartInline


User = get_user_model()


class KostenartAdminTestCase(TestCase):
    """Test Kostenart admin interface"""
    
    def setUp(self):
        """Set up test data"""
        self.site = AdminSite()
        self.admin = KostenartAdmin(Kostenart, self.site)
        
        # Create test user
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )
    
    def test_admin_list_display(self):
        """Test that admin list display includes correct fields"""
        self.assertEqual(
            self.admin.list_display,
            ('name', 'parent', 'is_hauptkostenart')
        )
    
    def test_admin_list_filter(self):
        """Test that admin can filter by parent"""
        self.assertEqual(self.admin.list_filter, ('parent',))
    
    def test_admin_search_fields(self):
        """Test that admin can search by name"""
        self.assertEqual(self.admin.search_fields, ('name',))
    
    def test_get_queryset_only_shows_hauptkostenarten(self):
        """Test that admin queryset only shows main cost types"""
        # Create test data
        haupt1 = Kostenart.objects.create(name="Personal")
        haupt2 = Kostenart.objects.create(name="Material")
        unter1 = Kostenart.objects.create(name="Gehälter", parent=haupt1)
        unter2 = Kostenart.objects.create(name="Rohstoffe", parent=haupt2)
        
        # Get queryset from admin
        request = RequestFactory().get('/admin/core/kostenart/')
        request.user = self.user
        
        qs = self.admin.get_queryset(request)
        
        # Should only contain Hauptkostenarten
        self.assertEqual(qs.count(), 2)
        self.assertIn(haupt1, qs)
        self.assertIn(haupt2, qs)
        self.assertNotIn(unter1, qs)
        self.assertNotIn(unter2, qs)
    
    def test_has_delete_permission_hauptkostenart_with_children(self):
        """Test that Hauptkostenart with children cannot be deleted via admin"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        Kostenart.objects.create(name="Gehälter", parent=hauptkostenart)
        
        request = RequestFactory().get('/admin/core/kostenart/')
        request.user = self.user
        
        has_permission = self.admin.has_delete_permission(request, hauptkostenart)
        
        self.assertFalse(has_permission)
    
    def test_has_delete_permission_hauptkostenart_without_children(self):
        """Test that Hauptkostenart without children can be deleted via admin"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        
        request = RequestFactory().get('/admin/core/kostenart/')
        request.user = self.user
        
        has_permission = self.admin.has_delete_permission(request, hauptkostenart)
        
        self.assertTrue(has_permission)
    
    def test_has_delete_permission_no_object(self):
        """Test delete permission when no object is provided"""
        request = RequestFactory().get('/admin/core/kostenart/')
        request.user = self.user
        
        # Should return True when no object is specified (for bulk actions)
        has_permission = self.admin.has_delete_permission(request, None)
        
        self.assertTrue(has_permission)
    
    def test_inline_admin_configured(self):
        """Test that inline admin for Unterkostenarten is configured"""
        self.assertEqual(len(self.admin.inlines), 1)
        
        self.assertEqual(self.admin.inlines[0], UnterkostenartInline)
