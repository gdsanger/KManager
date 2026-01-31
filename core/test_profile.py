"""
Tests for user profile and password management functionality.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail


class UserProfileTests(TestCase):
    """Tests for user profile view and functionality."""
    
    def setUp(self):
        """Set up test users."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
    
    def test_profile_requires_login(self):
        """Test that profile page requires authentication."""
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_profile_page_accessible_when_logged_in(self):
        """Test that authenticated users can access profile page."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Benutzerprofil')
    
    def test_update_profile_information(self):
        """Test updating user profile information."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('profile'), {
            'update_profile': '',
            'username': 'testuser',
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@example.com'
        })
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertContains(response, 'Profil erfolgreich aktualisiert')
    
    def test_change_password(self):
        """Test changing user password."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('profile'), {
            'change_password': '',
            'old_password': 'testpass123',
            'new_password1': 'newpass456',
            'new_password2': 'newpass456'
        })
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass456'))
        self.assertContains(response, 'Passwort erfolgreich geändert')
        
        # Verify user is still logged in
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
    
    def test_change_password_wrong_old_password(self):
        """Test password change fails with wrong old password."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('profile'), {
            'change_password': '',
            'old_password': 'wrongpass',
            'new_password1': 'newpass456',
            'new_password2': 'newpass456'
        })
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('testpass123'))
        self.assertFalse(self.user.check_password('newpass456'))
    
    def test_change_password_mismatch(self):
        """Test password change fails when new passwords don't match."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('profile'), {
            'change_password': '',
            'old_password': 'testpass123',
            'new_password1': 'newpass456',
            'new_password2': 'differentpass789'
        })
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('testpass123'))


class PasswordResetTests(TestCase):
    """Tests for password reset functionality."""
    
    def setUp(self):
        """Set up test users."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
    
    def test_password_reset_page_accessible(self):
        """Test that password reset page is accessible to anonymous users."""
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passwort zurücksetzen')
    
    def test_password_reset_sends_email(self):
        """Test that password reset form sends an email."""
        response = self.client.post(reverse('password_reset'), {
            'email': 'test@example.com'
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Passwort zurücksetzen', mail.outbox[0].subject)
        self.assertIn(self.user.email, mail.outbox[0].to)
    
    def test_password_reset_invalid_email(self):
        """Test password reset with non-existent email still shows success page."""
        response = self.client.post(reverse('password_reset'), {
            'email': 'nonexistent@example.com'
        })
        
        # Django doesn't reveal if email exists for security
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
    
    def test_password_reset_done_page(self):
        """Test password reset done page is accessible."""
        response = self.client.get(reverse('password_reset_done'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'E-Mail gesendet')
    
    def test_password_reset_complete_page(self):
        """Test password reset complete page is accessible."""
        response = self.client.get(reverse('password_reset_complete'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passwort erfolgreich zurückgesetzt')
    
    def test_login_page_has_password_reset_link(self):
        """Test that login page contains password reset link."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passwort vergessen?')
        self.assertContains(response, reverse('password_reset'))


class HomePageTests(TestCase):
    """Tests for home page behavior based on authentication."""
    
    def setUp(self):
        """Set up test users."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_home_shows_login_for_anonymous_users(self):
        """Test that home page shows login form for unauthenticated users."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bitte melden Sie sich an')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
    
    def test_home_shows_tiles_for_authenticated_users(self):
        """Test that home page shows tiles for authenticated users."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gebäude')
        self.assertContains(response, 'Finanzen')
        self.assertNotContains(response, 'Bitte melden Sie sich an')
    
    def test_home_gebaeude_tile_has_link(self):
        """Test that Gebäude tile has proper link."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('vermietung:home'))
    
    def test_home_finanzen_tile_shown_as_coming_soon(self):
        """Test that Finanzen tile is shown as coming soon."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Bald verfügbar')


class NavigationTests(TestCase):
    """Tests for navigation updates."""
    
    def setUp(self):
        """Set up test users."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_profile_link_in_navigation_for_authenticated_users(self):
        """Test that authenticated users see profile link in navigation."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('profile'))
        self.assertContains(response, 'Profil')
    
    def test_no_profile_link_for_anonymous_users(self):
        """Test that anonymous users don't see profile link."""
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, reverse('profile'))
    
    def test_user_dropdown_shows_username(self):
        """Test that user dropdown shows the username."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'testuser')
        self.assertContains(response, 'userDropdown')
