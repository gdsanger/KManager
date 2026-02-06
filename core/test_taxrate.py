"""
Tests for TaxRate model
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from core.models import TaxRate


class TaxRateModelTestCase(TestCase):
    """Test TaxRate model"""
    
    def test_create_taxrate(self):
        """Test creating a tax rate"""
        taxrate = TaxRate.objects.create(
            code="VAT",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
        
        self.assertIsNotNone(taxrate.pk)
        self.assertEqual(taxrate.code, "VAT")
        self.assertEqual(taxrate.name, "Standard VAT")
        self.assertEqual(taxrate.rate, Decimal("0.19"))
        self.assertTrue(taxrate.is_active)
    
    def test_rate_validation_negative(self):
        """Test that rate cannot be negative"""
        taxrate = TaxRate(
            code="NEGATIVE",
            name="Negative Rate",
            rate=Decimal("-0.05")
        )
        
        with self.assertRaises(ValidationError) as context:
            taxrate.clean()
        
        self.assertIn('rate', context.exception.message_dict)
        self.assertIn('negativ', str(context.exception))
    
    def test_rate_validation_greater_than_one(self):
        """Test that rate cannot be greater than 1"""
        taxrate = TaxRate(
            code="TOOHIGH",
            name="Too High Rate",
            rate=Decimal("1.5")
        )
        
        with self.assertRaises(ValidationError) as context:
            taxrate.clean()
        
        self.assertIn('rate', context.exception.message_dict)
        self.assertIn('größer als 1', str(context.exception))
    
    def test_rate_validation_zero(self):
        """Test that rate of 0 is allowed"""
        taxrate = TaxRate.objects.create(
            code="ZERO",
            name="Zero Rate",
            rate=Decimal("0")
        )
        taxrate.full_clean()  # Should not raise
        
        self.assertEqual(taxrate.rate, Decimal("0"))
    
    def test_rate_validation_one(self):
        """Test that rate of 1 is allowed"""
        taxrate = TaxRate.objects.create(
            code="ONE",
            name="One Hundred Percent",
            rate=Decimal("1")
        )
        taxrate.full_clean()  # Should not raise
        
        self.assertEqual(taxrate.rate, Decimal("1"))
    
    def test_code_uniqueness_case_insensitive(self):
        """Test that code must be unique (case-insensitive)"""
        # Create first tax rate with uppercase code
        TaxRate.objects.create(
            code="VAT",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
        
        # Try to create second tax rate with lowercase code
        # Should fail due to case-insensitive uniqueness
        with self.assertRaises(IntegrityError):
            TaxRate.objects.create(
                code="vat",
                name="Another VAT",
                rate=Decimal("0.20")
            )
    
    def test_code_uniqueness_mixed_case(self):
        """Test case-insensitive uniqueness with mixed case"""
        from django.db import transaction
        
        # Create first tax rate
        TaxRate.objects.create(
            code="Reduced",
            name="Reduced Rate",
            rate=Decimal("0.07")
        )
        
        # Try with different case variations
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                TaxRate.objects.create(
                    code="REDUCED",
                    name="Another Reduced",
                    rate=Decimal("0.07")
                )
        
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                TaxRate.objects.create(
                    code="reduced",
                    name="Yet Another Reduced",
                    rate=Decimal("0.07")
                )
    
    def test_str_representation(self):
        """Test string representation of TaxRate"""
        taxrate = TaxRate.objects.create(
            code="VAT19",
            name="Standard VAT 19%",
            rate=Decimal("0.19")
        )
        
        expected = "VAT19: Standard VAT 19% (19.00%)"
        self.assertEqual(str(taxrate), expected)
    
    def test_str_representation_with_different_rates(self):
        """Test string representation with various rate formats"""
        taxrate1 = TaxRate.objects.create(
            code="VAT7",
            name="Reduced VAT",
            rate=Decimal("0.07")
        )
        self.assertEqual(str(taxrate1), "VAT7: Reduced VAT (7.00%)")
        
        taxrate2 = TaxRate.objects.create(
            code="ZERO",
            name="Zero Rate",
            rate=Decimal("0")
        )
        self.assertEqual(str(taxrate2), "ZERO: Zero Rate (0.00%)")
    
    def test_is_active_default(self):
        """Test that is_active defaults to True"""
        taxrate = TaxRate.objects.create(
            code="DEFAULT",
            name="Default Active",
            rate=Decimal("0.19")
        )
        
        self.assertTrue(taxrate.is_active)
    
    def test_is_active_can_be_set_false(self):
        """Test that is_active can be set to False"""
        taxrate = TaxRate.objects.create(
            code="INACTIVE",
            name="Inactive Rate",
            rate=Decimal("0.19"),
            is_active=False
        )
        
        self.assertFalse(taxrate.is_active)
    
    def test_ordering(self):
        """Test that TaxRates are ordered by code"""
        TaxRate.objects.create(code="ZERO", name="Zero", rate=Decimal("0"))
        TaxRate.objects.create(code="VAT", name="VAT", rate=Decimal("0.19"))
        TaxRate.objects.create(code="REDUCED", name="Reduced", rate=Decimal("0.07"))
        
        taxrates = list(TaxRate.objects.all())
        
        self.assertEqual(taxrates[0].code, "REDUCED")
        self.assertEqual(taxrates[1].code, "VAT")
        self.assertEqual(taxrates[2].code, "ZERO")
    
    def test_rate_precision(self):
        """Test that rate can store up to 4 decimal places"""
        taxrate = TaxRate.objects.create(
            code="PRECISE",
            name="Precise Rate",
            rate=Decimal("0.1234")
        )
        
        self.assertEqual(taxrate.rate, Decimal("0.1234"))
    
    def test_update_taxrate(self):
        """Test updating a tax rate"""
        taxrate = TaxRate.objects.create(
            code="UPDATE",
            name="Original Name",
            rate=Decimal("0.19")
        )
        
        # Update the tax rate
        taxrate.name = "Updated Name"
        taxrate.rate = Decimal("0.20")
        taxrate.is_active = False
        taxrate.save()
        
        # Reload from database
        taxrate.refresh_from_db()
        
        self.assertEqual(taxrate.name, "Updated Name")
        self.assertEqual(taxrate.rate, Decimal("0.20"))
        self.assertFalse(taxrate.is_active)
    
    def test_deactivate_instead_of_delete(self):
        """Test that tax rates should be deactivated instead of deleted"""
        taxrate = TaxRate.objects.create(
            code="DEACTIVATE",
            name="To Deactivate",
            rate=Decimal("0.19"),
            is_active=True
        )
        
        # Deactivate instead of delete
        taxrate.is_active = False
        taxrate.save()
        
        # Tax rate should still exist
        self.assertTrue(TaxRate.objects.filter(code="DEACTIVATE").exists())
        
        # But it should be inactive
        taxrate.refresh_from_db()
        self.assertFalse(taxrate.is_active)
