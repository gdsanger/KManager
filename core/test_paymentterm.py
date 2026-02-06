"""
Tests for PaymentTerm model
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from decimal import Decimal
from datetime import date, datetime, timedelta
from core.models import PaymentTerm, Mandant


class PaymentTermModelTestCase(TestCase):
    """Test PaymentTerm model"""
    
    def setUp(self):
        """Create test company"""
        self.company1 = Mandant.objects.create(
            name="Test Company 1",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.company2 = Mandant.objects.create(
            name="Test Company 2",
            adresse="Test Street 2",
            plz="54321",
            ort="Test City 2"
        )
    
    def test_create_payment_term_without_discount(self):
        """Test creating a payment term without discount"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Net 30 days",
            net_days=30
        )
        
        self.assertIsNotNone(payment_term.pk)
        self.assertEqual(payment_term.company, self.company1)
        self.assertEqual(payment_term.name, "Net 30 days")
        self.assertEqual(payment_term.net_days, 30)
        self.assertIsNone(payment_term.discount_days)
        self.assertIsNone(payment_term.discount_rate)
        self.assertFalse(payment_term.is_default)
    
    def test_create_payment_term_with_discount(self):
        """Test creating a payment term with discount"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="2% 10 days, net 30 days",
            discount_days=10,
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        
        self.assertIsNotNone(payment_term.pk)
        self.assertEqual(payment_term.discount_days, 10)
        self.assertEqual(payment_term.discount_rate, Decimal("0.02"))
        self.assertEqual(payment_term.net_days, 30)
    
    def test_validation_discount_days_greater_than_net_days(self):
        """Test that discount_days cannot be greater than net_days"""
        payment_term = PaymentTerm(
            company=self.company1,
            name="Invalid discount",
            discount_days=40,
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        
        with self.assertRaises(ValidationError) as context:
            payment_term.clean()
        
        self.assertIn('discount_days', context.exception.message_dict)
        self.assertIn('größer', str(context.exception))
    
    def test_validation_discount_days_without_discount_rate(self):
        """Test that discount_days requires discount_rate"""
        payment_term = PaymentTerm(
            company=self.company1,
            name="Invalid discount",
            discount_days=10,
            net_days=30
        )
        
        with self.assertRaises(ValidationError) as context:
            payment_term.clean()
        
        self.assertIn('discount_rate', context.exception.message_dict)
        self.assertIn('Skontosatz', str(context.exception))
    
    def test_validation_discount_rate_without_discount_days(self):
        """Test that discount_rate requires discount_days"""
        payment_term = PaymentTerm(
            company=self.company1,
            name="Invalid discount",
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        
        with self.assertRaises(ValidationError) as context:
            payment_term.clean()
        
        self.assertIn('discount_days', context.exception.message_dict)
        self.assertIn('Skontofrist', str(context.exception))
    
    def test_validation_discount_rate_must_be_positive(self):
        """Test that discount_rate must be > 0"""
        payment_term = PaymentTerm(
            company=self.company1,
            name="Invalid discount",
            discount_days=10,
            discount_rate=Decimal("0"),
            net_days=30
        )
        
        with self.assertRaises(ValidationError) as context:
            payment_term.clean()
        
        self.assertIn('discount_rate', context.exception.message_dict)
        self.assertIn('größer als 0', str(context.exception))
    
    def test_validation_discount_rate_negative(self):
        """Test that discount_rate cannot be negative"""
        payment_term = PaymentTerm(
            company=self.company1,
            name="Invalid discount",
            discount_days=10,
            discount_rate=Decimal("-0.02"),
            net_days=30
        )
        
        with self.assertRaises(ValidationError) as context:
            payment_term.clean()
        
        self.assertIn('discount_rate', context.exception.message_dict)
    
    def test_validation_discount_days_equal_net_days(self):
        """Test that discount_days can equal net_days"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Same days",
            discount_days=30,
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        payment_term.full_clean()  # Should not raise
        
        self.assertEqual(payment_term.discount_days, payment_term.net_days)
    
    def test_unique_default_per_company_db_constraint(self):
        """Test that DB constraint exists to prevent multiple defaults
        
        Note: The application-level save() method normally prevents this by
        auto-deactivating the old default. This test uses bulk_create to
        bypass the save() method and test the DB constraint directly.
        """
        # Create first default
        pt1 = PaymentTerm.objects.create(
            company=self.company1,
            name="Default 1",
            net_days=30,
            is_default=True
        )
        
        # Try to create second default using raw SQL to bypass save()
        # This should fail at DB level due to unique constraint
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                # Create a payment term object but bypass save() validation
                # by using bulk_create which doesn't call save()
                PaymentTerm.objects.bulk_create([
                    PaymentTerm(
                        company=self.company1,
                        name="Default 2",
                        net_days=60,
                        is_default=True
                    )
                ])
    
    def test_auto_deactivate_old_default(self):
        """Test that setting a new default automatically deactivates the old one"""
        # Create first default
        pt1 = PaymentTerm.objects.create(
            company=self.company1,
            name="Default 1",
            net_days=30,
            is_default=True
        )
        
        # Create second payment term as default
        pt2 = PaymentTerm.objects.create(
            company=self.company1,
            name="Default 2",
            net_days=60,
            is_default=True
        )
        
        # Reload first payment term from database
        pt1.refresh_from_db()
        
        # First should no longer be default
        self.assertFalse(pt1.is_default)
        self.assertTrue(pt2.is_default)
    
    def test_auto_deactivate_old_default_on_update(self):
        """Test that updating a payment term to default deactivates the old default"""
        # Create first default
        pt1 = PaymentTerm.objects.create(
            company=self.company1,
            name="Default 1",
            net_days=30,
            is_default=True
        )
        
        # Create second payment term (not default)
        pt2 = PaymentTerm.objects.create(
            company=self.company1,
            name="Default 2",
            net_days=60,
            is_default=False
        )
        
        # Make second one default
        pt2.is_default = True
        pt2.save()
        
        # Reload first payment term from database
        pt1.refresh_from_db()
        
        # First should no longer be default
        self.assertFalse(pt1.is_default)
        self.assertTrue(pt2.is_default)
    
    def test_multiple_defaults_different_companies(self):
        """Test that different companies can each have their own default"""
        pt1 = PaymentTerm.objects.create(
            company=self.company1,
            name="Company 1 Default",
            net_days=30,
            is_default=True
        )
        
        pt2 = PaymentTerm.objects.create(
            company=self.company2,
            name="Company 2 Default",
            net_days=60,
            is_default=True
        )
        
        # Both should be default
        self.assertTrue(pt1.is_default)
        self.assertTrue(pt2.is_default)
    
    def test_get_default_returns_default(self):
        """Test get_default() returns the default payment term"""
        # Create default
        pt = PaymentTerm.objects.create(
            company=self.company1,
            name="Default",
            net_days=30,
            is_default=True
        )
        
        # Get default
        default = PaymentTerm.get_default(self.company1)
        
        self.assertEqual(default, pt)
    
    def test_get_default_returns_none_if_no_default(self):
        """Test get_default() returns None if no default exists"""
        # Create non-default
        PaymentTerm.objects.create(
            company=self.company1,
            name="Non-default",
            net_days=30,
            is_default=False
        )
        
        # Get default
        default = PaymentTerm.get_default(self.company1)
        
        self.assertIsNone(default)
    
    def test_get_default_different_companies(self):
        """Test get_default() returns correct default for each company"""
        pt1 = PaymentTerm.objects.create(
            company=self.company1,
            name="Company 1 Default",
            net_days=30,
            is_default=True
        )
        
        pt2 = PaymentTerm.objects.create(
            company=self.company2,
            name="Company 2 Default",
            net_days=60,
            is_default=True
        )
        
        # Get defaults
        default1 = PaymentTerm.get_default(self.company1)
        default2 = PaymentTerm.get_default(self.company2)
        
        self.assertEqual(default1, pt1)
        self.assertEqual(default2, pt2)
    
    def test_calculate_due_date(self):
        """Test calculate_due_date() calculation"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Net 30",
            net_days=30
        )
        
        invoice_date = date(2024, 1, 1)
        due_date = payment_term.calculate_due_date(invoice_date)
        
        expected_due_date = date(2024, 1, 31)
        self.assertEqual(due_date, expected_due_date)
    
    def test_calculate_due_date_with_datetime(self):
        """Test calculate_due_date() with datetime input"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Net 30",
            net_days=30
        )
        
        invoice_datetime = datetime(2024, 1, 1, 10, 30, 0)
        due_date = payment_term.calculate_due_date(invoice_datetime)
        
        expected_due_date = date(2024, 1, 31)
        self.assertEqual(due_date, expected_due_date)
    
    def test_calculate_discount_end_date(self):
        """Test calculate_discount_end_date() calculation"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="2% 10, net 30",
            discount_days=10,
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        
        invoice_date = date(2024, 1, 1)
        discount_end = payment_term.calculate_discount_end_date(invoice_date)
        
        expected_discount_end = date(2024, 1, 11)
        self.assertEqual(discount_end, expected_discount_end)
    
    def test_calculate_discount_end_date_no_discount(self):
        """Test calculate_discount_end_date() returns None when no discount"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Net 30",
            net_days=30
        )
        
        invoice_date = date(2024, 1, 1)
        discount_end = payment_term.calculate_discount_end_date(invoice_date)
        
        self.assertIsNone(discount_end)
    
    def test_get_discount_rate(self):
        """Test get_discount_rate() returns rate"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="2% 10, net 30",
            discount_days=10,
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        
        rate = payment_term.get_discount_rate()
        
        self.assertEqual(rate, Decimal("0.02"))
    
    def test_get_discount_rate_no_discount(self):
        """Test get_discount_rate() returns None when no discount"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Net 30",
            net_days=30
        )
        
        rate = payment_term.get_discount_rate()
        
        self.assertIsNone(rate)
    
    def test_has_discount_true(self):
        """Test has_discount() returns True when discount is active"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="2% 10, net 30",
            discount_days=10,
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        
        self.assertTrue(payment_term.has_discount())
    
    def test_has_discount_false(self):
        """Test has_discount() returns False when no discount"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Net 30",
            net_days=30
        )
        
        self.assertFalse(payment_term.has_discount())
    
    def test_str_representation_without_discount(self):
        """Test string representation without discount"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Net 30 days",
            net_days=30
        )
        
        expected = "Net 30 days (netto 30T)"
        self.assertEqual(str(payment_term), expected)
    
    def test_str_representation_with_discount(self):
        """Test string representation with discount"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="2% discount terms",
            discount_days=10,
            discount_rate=Decimal("0.02"),
            net_days=30
        )
        
        expected = "2% discount terms (2.00% 10T, netto 30T)"
        self.assertEqual(str(payment_term), expected)
    
    def test_ordering(self):
        """Test that PaymentTerms are ordered by company, then name"""
        pt1 = PaymentTerm.objects.create(
            company=self.company1,
            name="B Term",
            net_days=30
        )
        pt2 = PaymentTerm.objects.create(
            company=self.company1,
            name="A Term",
            net_days=60
        )
        pt3 = PaymentTerm.objects.create(
            company=self.company2,
            name="C Term",
            net_days=90
        )
        
        payment_terms = list(PaymentTerm.objects.all())
        
        # Should be ordered by company first, then name
        self.assertEqual(payment_terms[0], pt2)  # Company1, A Term
        self.assertEqual(payment_terms[1], pt1)  # Company1, B Term
        self.assertEqual(payment_terms[2], pt3)  # Company2, C Term
    
    def test_is_default_default_value(self):
        """Test that is_default defaults to False"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Test",
            net_days=30
        )
        
        self.assertFalse(payment_term.is_default)
    
    def test_company_cascade_protection(self):
        """Test that company cannot be deleted if it has payment terms (PROTECT)"""
        PaymentTerm.objects.create(
            company=self.company1,
            name="Test",
            net_days=30
        )
        
        # Try to delete company
        with self.assertRaises(Exception):  # Should raise ProtectedError
            self.company1.delete()
    
    def test_update_payment_term(self):
        """Test updating a payment term"""
        payment_term = PaymentTerm.objects.create(
            company=self.company1,
            name="Original",
            net_days=30
        )
        
        # Update
        payment_term.name = "Updated"
        payment_term.discount_days = 10
        payment_term.discount_rate = Decimal("0.02")
        payment_term.net_days = 60
        payment_term.save()
        
        # Reload from database
        payment_term.refresh_from_db()
        
        self.assertEqual(payment_term.name, "Updated")
        self.assertEqual(payment_term.discount_days, 10)
        self.assertEqual(payment_term.discount_rate, Decimal("0.02"))
        self.assertEqual(payment_term.net_days, 60)
