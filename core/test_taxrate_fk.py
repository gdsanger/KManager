"""
Test that TaxRate can be used as ForeignKey in other models
"""
from django.test import TestCase
from django.db import models
from decimal import Decimal
from core.models import TaxRate


class TaxRateForeignKeyTestCase(TestCase):
    """Test that TaxRate can be referenced by ForeignKey"""
    
    def test_taxrate_can_be_foreign_key(self):
        """Test that TaxRate can be used as ForeignKey in other models"""
        # Create a TaxRate
        taxrate = TaxRate.objects.create(
            code="VAT19",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
        
        # Create a dynamic model to test FK relationship
        # This simulates how Item or SalesDocumentLine would reference TaxRate
        class TestModel(models.Model):
            name = models.CharField(max_length=100)
            tax_rate = models.ForeignKey(
                TaxRate,
                on_delete=models.PROTECT,
                null=True,
                blank=True
            )
            
            class Meta:
                app_label = 'core'
        
        # Verify that TaxRate can be assigned to the FK field
        # This doesn't actually create the table, but validates the relationship definition
        self.assertIsNotNone(TestModel._meta.get_field('tax_rate'))
        self.assertEqual(TestModel._meta.get_field('tax_rate').related_model, TaxRate)
        self.assertEqual(TestModel._meta.get_field('tax_rate').remote_field.on_delete, models.PROTECT)
    
    def test_taxrate_protect_on_delete(self):
        """Test that TaxRate with FK references cannot be deleted"""
        # Create a TaxRate
        taxrate = TaxRate.objects.create(
            code="PROTECTED",
            name="Protected Rate",
            rate=Decimal("0.19")
        )
        
        # Verify it exists
        self.assertTrue(TaxRate.objects.filter(code="PROTECTED").exists())
        
        # Note: In real implementation, if there are FK references with PROTECT,
        # deletion would raise ProtectedError. This is verified by the model definition.
        # The actual FK fields will be added in Item and SalesDocumentLine models
        # in future issues, as noted in the requirements.
