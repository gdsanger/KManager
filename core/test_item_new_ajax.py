"""
Tests for item_new_ajax view
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import ItemGroup, TaxRate, Kostenart
from decimal import Decimal


class ItemNewAjaxViewTestCase(TestCase):
    """Test the item_new_ajax view"""
    
    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code="VAT",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
        
        # Create cost type
        self.cost_type = Kostenart.objects.create(
            name="Hauptkostenart Material",
            umsatzsteuer_satz="19"
        )
        
        # Create item groups
        self.main_group = ItemGroup.objects.create(
            code="MG001",
            name="Main Group 1",
            group_type="MAIN"
        )
        self.sub_group = ItemGroup.objects.create(
            code="SG001",
            name="Sub Group 1",
            group_type="SUB",
            parent=self.main_group
        )
    
    def test_item_new_ajax_without_group(self):
        """Test loading new item form without group preselection"""
        url = reverse('item_new_ajax')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIsNone(response.context['item'])
        
    def test_item_new_ajax_with_group(self):
        """Test loading new item form with group preselection"""
        url = reverse('item_new_ajax') + f'?group={self.sub_group.pk}'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIsNone(response.context['item'])
        
        # Check that the form has the group preselected
        form = response.context['form']
        self.assertEqual(form.initial.get('item_group'), self.sub_group)
    
    def test_item_new_ajax_with_invalid_group(self):
        """Test loading new item form with invalid group ID"""
        url = reverse('item_new_ajax') + '?group=999999'
        response = self.client.get(url)
        
        # Should still return 200, but without group preselection
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        
        # Form should not have group preselected
        form = response.context['form']
        self.assertIsNone(form.initial.get('item_group'))
    
    def test_item_new_ajax_requires_authentication(self):
        """Test that the view requires authentication"""
        self.client.logout()
        url = reverse('item_new_ajax')
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
