"""
Tests for HTMX cost_type_2 options endpoint
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Kostenart


class CostType2OptionsViewTestCase(TestCase):
    """Test the HTMX endpoint for cost_type_2 options"""
    
    def setUp(self):
        """Set up test data"""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create client
        self.client = Client()
        
        # Create Hauptkostenarten (main cost types)
        self.hauptkostenart1 = Kostenart.objects.create(name="Personal")
        self.hauptkostenart2 = Kostenart.objects.create(name="Material")
        
        # Create Unterkostenarten (sub cost types)
        self.unterkostenart1_1 = Kostenart.objects.create(
            name="Gehälter",
            parent=self.hauptkostenart1
        )
        self.unterkostenart1_2 = Kostenart.objects.create(
            name="Sozialversicherung",
            parent=self.hauptkostenart1
        )
        self.unterkostenart2_1 = Kostenart.objects.create(
            name="Rohstoffe",
            parent=self.hauptkostenart2
        )
    
    def test_requires_login(self):
        """Test that the endpoint requires authentication"""
        url = reverse('cost_type_2_options')
        
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_returns_empty_options_when_no_cost_type_1(self):
        """Test that endpoint returns empty options when no cost_type_1 is provided"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('cost_type_2_options')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Should contain the wrapper div
        self.assertContains(response, 'id="cost-type-2-wrapper"')
        
        # Should have disabled attribute
        content = response.content.decode('utf-8')
        self.assertIn('disabled', content)
    
    def test_returns_filtered_options_for_hauptkostenart1(self):
        """Test that endpoint returns filtered options for hauptkostenart1"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('cost_type_2_options')
        response = self.client.get(url, {'cost_type_1': self.hauptkostenart1.pk})
        
        self.assertEqual(response.status_code, 200)
        
        # Should contain the wrapper div
        self.assertContains(response, 'id="cost-type-2-wrapper"')
        
        # Should contain options for children of hauptkostenart1
        self.assertContains(response, 'Gehälter')
        self.assertContains(response, 'Sozialversicherung')
        
        # Should NOT contain children of hauptkostenart2
        self.assertNotContains(response, 'Rohstoffe')
        
        # Should NOT be disabled
        self.assertNotContains(response, 'disabled')
    
    def test_returns_filtered_options_for_hauptkostenart2(self):
        """Test that endpoint returns filtered options for hauptkostenart2"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('cost_type_2_options')
        response = self.client.get(url, {'cost_type_1': self.hauptkostenart2.pk})
        
        self.assertEqual(response.status_code, 200)
        
        # Should contain the wrapper div
        self.assertContains(response, 'id="cost-type-2-wrapper"')
        
        # Should contain options for children of hauptkostenart2
        self.assertContains(response, 'Rohstoffe')
        
        # Should NOT contain children of hauptkostenart1
        self.assertNotContains(response, 'Gehälter')
        self.assertNotContains(response, 'Sozialversicherung')
    
    def test_handles_invalid_cost_type_1_id(self):
        """Test that endpoint handles invalid cost_type_1 ID gracefully"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('cost_type_2_options')
        response = self.client.get(url, {'cost_type_1': 'invalid'})
        
        self.assertEqual(response.status_code, 200)
        
        # Should return empty options (same as no cost_type_1)
        self.assertContains(response, 'id="cost-type-2-wrapper"')
        
        # Should have disabled attribute
        content = response.content.decode('utf-8')
        self.assertIn('disabled', content)
    
    def test_handles_nonexistent_cost_type_1_id(self):
        """Test that endpoint handles non-existent cost_type_1 ID gracefully"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('cost_type_2_options')
        response = self.client.get(url, {'cost_type_1': 99999})
        
        self.assertEqual(response.status_code, 200)
        
        # Should return empty options
        self.assertContains(response, 'id="cost-type-2-wrapper"')
    
    def test_returns_html_partial_not_full_page(self):
        """Test that endpoint returns HTML partial, not a full page"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('cost_type_2_options')
        response = self.client.get(url, {'cost_type_1': self.hauptkostenart1.pk})
        
        self.assertEqual(response.status_code, 200)
        
        # Should contain the wrapper div
        self.assertContains(response, 'id="cost-type-2-wrapper"')
        
        # Should NOT contain full page elements like <html>, <head>, <body>
        self.assertNotContains(response, '<html')
        self.assertNotContains(response, '<head>')
        self.assertNotContains(response, '<body>')
    
    def test_includes_label_and_help_text(self):
        """Test that the partial includes label and help text"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('cost_type_2_options')
        response = self.client.get(url, {'cost_type_1': self.hauptkostenart1.pk})
        
        self.assertEqual(response.status_code, 200)
        
        # Should contain label
        self.assertContains(response, 'Kostenart 2')
        
        # Should contain the select element
        self.assertContains(response, '<select')
