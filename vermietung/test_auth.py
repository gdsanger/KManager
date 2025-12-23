"""
Tests for authentication and authorization in the Vermietung area.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group, AnonymousUser
from django.urls import reverse


class VermietungAuthenticationTests(TestCase):
    """Tests for authentication requirements in Vermietung area."""
    
    def setUp(self):
        """Set up test users and groups."""
        self.client = Client()
        
        # Create the Vermietung group
        self.vermietung_group = Group.objects.create(name='Vermietung')
        
        # Create test users
        self.staff_user = User.objects.create_user(
            username='staff_user',
            password='testpass123',
            is_staff=True
        )
        
        self.vermietung_user = User.objects.create_user(
            username='vermietung_user',
            password='testpass123'
        )
        self.vermietung_user.groups.add(self.vermietung_group)
        
        self.regular_user = User.objects.create_user(
            username='regular_user',
            password='testpass123'
        )
    
    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(reverse('vermietung:home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_staff_user_has_access(self):
        """Test that staff users have access to Vermietung area."""
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.get(reverse('vermietung:home'))
        self.assertEqual(response.status_code, 200)
    
    def test_vermietung_group_user_has_access(self):
        """Test that users in Vermietung group have access."""
        self.client.login(username='vermietung_user', password='testpass123')
        response = self.client.get(reverse('vermietung:home'))
        self.assertEqual(response.status_code, 200)
    
    def test_regular_user_without_permission_denied(self):
        """Test that regular users without Vermietung group are redirected to login."""
        self.client.login(username='regular_user', password='testpass123')
        response = self.client.get(reverse('vermietung:home'))
        # user_passes_test redirects to login when test fails
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_login_page_accessible_to_anonymous(self):
        """Test that login page is accessible to anonymous users."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Anmelden')
    
    def test_logout_redirects_to_home(self):
        """Test that logout redirects to home page."""
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
    
    def test_successful_login_redirects_to_home(self):
        """Test that successful login redirects to home page."""
        response = self.client.post(reverse('login'), {
            'username': 'staff_user',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
    
    def test_login_with_next_parameter(self):
        """Test that login redirects to 'next' parameter after authentication."""
        response = self.client.post(
            reverse('login') + '?next=/vermietung/',
            {
                'username': 'staff_user',
                'password': 'testpass123'
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/vermietung/')
    
    def test_failed_login_shows_error(self):
        """Test that failed login shows error message."""
        response = self.client.post(reverse('login'), {
            'username': 'staff_user',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'falsch')


class VermietungPermissionsTests(TestCase):
    """Tests for the permission checking functions."""
    
    def setUp(self):
        """Set up test users and groups."""
        from vermietung.permissions import user_has_vermietung_access
        self.check_access = user_has_vermietung_access
        
        # Create the Vermietung group
        self.vermietung_group = Group.objects.create(name='Vermietung')
        
        # Create test users
        self.staff_user = User.objects.create_user(
            username='staff_user',
            password='testpass123',
            is_staff=True
        )
        
        self.vermietung_user = User.objects.create_user(
            username='vermietung_user',
            password='testpass123'
        )
        self.vermietung_user.groups.add(self.vermietung_group)
        
        self.regular_user = User.objects.create_user(
            username='regular_user',
            password='testpass123'
        )
    
    def test_staff_user_has_access(self):
        """Test that staff users are granted access."""
        self.assertTrue(self.check_access(self.staff_user))
    
    def test_vermietung_group_user_has_access(self):
        """Test that users in Vermietung group are granted access."""
        self.assertTrue(self.check_access(self.vermietung_user))
    
    def test_regular_user_no_access(self):
        """Test that regular users without group are denied access."""
        self.assertFalse(self.check_access(self.regular_user))
    
    def test_unauthenticated_user_no_access(self):
        """Test that anonymous users are denied access."""
        anonymous = AnonymousUser()
        self.assertFalse(self.check_access(anonymous))
    
    def test_staff_user_in_group_has_access(self):
        """Test that staff users with Vermietung group also have access."""
        self.staff_user.groups.add(self.vermietung_group)
        self.assertTrue(self.check_access(self.staff_user))
    
    def test_group_name_exact_match(self):
        """Test that group name must be exactly 'Vermietung'."""
        # Create a different group
        other_group = Group.objects.create(name='OtherGroup')
        self.regular_user.groups.add(other_group)
        self.assertFalse(self.check_access(self.regular_user))


class NavigationTests(TestCase):
    """Tests for navigation links based on authentication."""
    
    def setUp(self):
        """Set up test users."""
        self.client = Client()
        self.vermietung_group = Group.objects.create(name='Vermietung')
        
        self.staff_user = User.objects.create_user(
            username='staff_user',
            password='testpass123',
            is_staff=True
        )
    
    def test_anonymous_user_sees_login_link(self):
        """Test that anonymous users see login link in navbar."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Anmelden')
        self.assertNotContains(response, 'Abmelden')
    
    def test_authenticated_user_sees_logout_link(self):
        """Test that authenticated users see logout link in navbar."""
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Abmelden')
        self.assertContains(response, 'staff_user')
        self.assertNotContains(response, 'Anmelden')
    
    def test_authenticated_user_sees_vermietung_link(self):
        """Test that authenticated users see Vermietung link in navbar."""
        self.client.login(username='staff_user', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Vermietung')
        self.assertContains(response, reverse('vermietung:home'))
