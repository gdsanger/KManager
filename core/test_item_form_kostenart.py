"""
Tests for Item form with Kostenart filtering and validation
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import Item, ItemGroup, TaxRate, Kostenart
from core.forms import ItemForm


class ItemFormKostenartTestCase(TestCase):
    """Test ItemForm with Kostenart filtering and validation"""
    
    def setUp(self):
        """Set up test data"""
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code="VAT19",
            name="19%",
            rate=0.19
        )
        
        # Create item group
        self.main_group = ItemGroup.objects.create(
            code="TEST",
            name="Test Main Group",
            group_type="MAIN"
        )
        self.item_group = ItemGroup.objects.create(
            code="TESTSUB",
            name="Test Sub Group",
            group_type="SUB",
            parent=self.main_group
        )
        
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
    
    def test_cost_type_1_queryset_only_hauptkostenarten(self):
        """Test that cost_type_1 queryset only includes Hauptkostenarten"""
        form = ItemForm()
        
        cost_type_1_queryset = form.fields['cost_type_1'].queryset
        
        # Should only include Hauptkostenarten (those without parent)
        self.assertEqual(cost_type_1_queryset.count(), 2)
        self.assertIn(self.hauptkostenart1, cost_type_1_queryset)
        self.assertIn(self.hauptkostenart2, cost_type_1_queryset)
        self.assertNotIn(self.unterkostenart1_1, cost_type_1_queryset)
        self.assertNotIn(self.unterkostenart1_2, cost_type_1_queryset)
        self.assertNotIn(self.unterkostenart2_1, cost_type_1_queryset)
    
    def test_cost_type_2_queryset_empty_when_no_cost_type_1(self):
        """Test that cost_type_2 queryset is empty when no cost_type_1 selected"""
        form = ItemForm()
        
        cost_type_2_queryset = form.fields['cost_type_2'].queryset
        
        # Should be empty when no cost_type_1 is selected
        self.assertEqual(cost_type_2_queryset.count(), 0)
    
    def test_cost_type_2_queryset_filtered_by_cost_type_1_in_edit_mode(self):
        """Test that cost_type_2 queryset is filtered by cost_type_1 in edit mode"""
        # Create an item with cost_type_1
        item = Item.objects.create(
            article_no="TEST001",
            short_text_1="Test Item",
            net_price=100.00,
            purchase_price=50.00,
            tax_rate=self.tax_rate,
            cost_type_1=self.hauptkostenart1,
            cost_type_2=self.unterkostenart1_1,
            item_group=self.item_group,
            item_type='MATERIAL'
        )
        
        form = ItemForm(instance=item)
        
        cost_type_2_queryset = form.fields['cost_type_2'].queryset
        
        # Should only include children of hauptkostenart1
        self.assertEqual(cost_type_2_queryset.count(), 2)
        self.assertIn(self.unterkostenart1_1, cost_type_2_queryset)
        self.assertIn(self.unterkostenart1_2, cost_type_2_queryset)
        self.assertNotIn(self.unterkostenart2_1, cost_type_2_queryset)
    
    def test_cost_type_2_queryset_filtered_by_submitted_cost_type_1(self):
        """Test that cost_type_2 queryset is filtered when form is submitted"""
        data = {
            'cost_type_1': self.hauptkostenart2.pk,
            'article_no': 'TEST002',
        }
        
        form = ItemForm(data=data)
        
        cost_type_2_queryset = form.fields['cost_type_2'].queryset
        
        # Should only include children of hauptkostenart2
        self.assertEqual(cost_type_2_queryset.count(), 1)
        self.assertIn(self.unterkostenart2_1, cost_type_2_queryset)
        self.assertNotIn(self.unterkostenart1_1, cost_type_2_queryset)
        self.assertNotIn(self.unterkostenart1_2, cost_type_2_queryset)
    
    def test_validation_cost_type_1_must_be_hauptkostenart(self):
        """Test that cost_type_1 queryset only contains Hauptkostenarten, so Unterkostenarten cannot be selected"""
        data = {
            'article_no': 'TEST003',
            'short_text_1': 'Test Item',
            'net_price': 100.00,
            'purchase_price': 50.00,
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.unterkostenart1_1.pk,  # Using an Unterkostenart - should fail at field level
            'item_group': self.item_group.pk,
            'item_type': 'MATERIAL',
        }
        
        form = ItemForm(data=data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('cost_type_1', form.errors)
        # Django's field validation message for invalid choice
        self.assertIn('gültige Auswahl', str(form.errors['cost_type_1']))
    
    def test_validation_cost_type_2_must_be_child_of_cost_type_1(self):
        """Test that cost_type_2 must be a child of cost_type_1"""
        data = {
            'article_no': 'TEST004',
            'short_text_1': 'Test Item',
            'net_price': 100.00,
            'purchase_price': 50.00,
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.hauptkostenart1.pk,
            'cost_type_2': self.unterkostenart2_1.pk,  # Child of hauptkostenart2, not hauptkostenart1
            'item_group': self.item_group.pk,
            'item_type': 'MATERIAL',
        }
        
        form = ItemForm(data=data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('cost_type_2', form.errors)
        # Django's field validation message for invalid choice (since queryset is filtered)
        self.assertIn('gültige Auswahl', str(form.errors['cost_type_2']))
    
    def test_validation_cost_type_2_requires_cost_type_1(self):
        """Test that cost_type_2 requires cost_type_1 to be set"""
        data = {
            'article_no': 'TEST005',
            'short_text_1': 'Test Item',
            'net_price': 100.00,
            'purchase_price': 50.00,
            'tax_rate': self.tax_rate.pk,
            'cost_type_2': self.unterkostenart1_1.pk,  # Setting cost_type_2 without cost_type_1
            'item_group': self.item_group.pk,
            'item_type': 'MATERIAL',
        }
        
        form = ItemForm(data=data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('cost_type_2', form.errors)
    
    def test_valid_form_with_hauptkostenart_and_unterkostenart(self):
        """Test that form is valid with correct Hauptkostenart and Unterkostenart"""
        data = {
            'article_no': 'TEST006',
            'short_text_1': 'Test Item',
            'net_price': 100.00,
            'purchase_price': 50.00,
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.hauptkostenart1.pk,
            'cost_type_2': self.unterkostenart1_1.pk,
            'item_group': self.item_group.pk,
            'item_type': 'MATERIAL',
            'is_active': True,
        }
        
        form = ItemForm(data=data)
        
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        item = form.save()
        self.assertEqual(item.cost_type_1, self.hauptkostenart1)
        self.assertEqual(item.cost_type_2, self.unterkostenart1_1)
    
    def test_valid_form_with_only_hauptkostenart(self):
        """Test that form is valid with only Hauptkostenart (cost_type_2 optional)"""
        data = {
            'article_no': 'TEST007',
            'short_text_1': 'Test Item',
            'net_price': 100.00,
            'purchase_price': 50.00,
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.hauptkostenart1.pk,
            # cost_type_2 is not set - should be valid
            'item_group': self.item_group.pk,
            'item_type': 'MATERIAL',
            'is_active': True,
        }
        
        form = ItemForm(data=data)
        
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        item = form.save()
        self.assertEqual(item.cost_type_1, self.hauptkostenart1)
        self.assertIsNone(item.cost_type_2)
    
    def test_cost_type_2_not_required(self):
        """Test that cost_type_2 field is not required"""
        form = ItemForm()
        
        self.assertFalse(form.fields['cost_type_2'].required)
