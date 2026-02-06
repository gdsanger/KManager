"""
Tests for PaymentTermTextService

Tests the automatic payment term text generation including:
- Payment terms without discount (net only)
- Payment terms with discount (Skonto)
- Due date calculation
"""
from django.test import TestCase
from datetime import date
from decimal import Decimal

from core.models import PaymentTerm
from auftragsverwaltung.services.payment_term_text import PaymentTermTextService


class PaymentTermTextServiceTest(TestCase):
    """Test suite for PaymentTermTextService"""
    
    def test_generate_text_without_discount(self):
        """Test: Generate text for payment term without discount"""
        # Create payment term: 14 days net, no discount
        payment_term = PaymentTerm(
            name='14 Tage netto',
            net_days=14,
            discount_days=None,
            discount_rate=None
        )
        
        issue_date = date(2026, 9, 1)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        # Expected: "Zahlbar innerhalb 14 Tagen (bis 15.09.2026) netto."
        self.assertIn('Zahlbar innerhalb 14 Tagen', text)
        self.assertIn('(bis 15.09.2026)', text)
        self.assertIn('netto.', text)
        self.assertNotIn('Skonto', text)
    
    def test_generate_text_with_discount(self):
        """Test: Generate text for payment term with discount (Skonto)"""
        # Create payment term: 2% discount in 10 days, net 30 days
        payment_term = PaymentTerm(
            name='2% Skonto 10 Tage, netto 30 Tage',
            net_days=30,
            discount_days=10,
            discount_rate=Decimal('0.02')
        )
        
        issue_date = date(2026, 9, 1)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        # Expected: "Zahlbar innerhalb 10 Tagen (bis 11.09.2026) mit 2% Skonto, 
        #            spätestens innerhalb 30 Tagen (bis 01.10.2026) netto."
        self.assertIn('Zahlbar innerhalb 10 Tagen', text)
        self.assertIn('(bis 11.09.2026)', text)
        self.assertIn('mit 2% Skonto', text)
        self.assertIn('spätestens innerhalb 30 Tagen', text)
        self.assertIn('(bis 01.10.2026)', text)
        self.assertIn('netto.', text)
    
    def test_generate_text_none_payment_term(self):
        """Test: Generate text when payment term is None"""
        issue_date = date(2026, 9, 1)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=None,
            issue_date=issue_date
        )
        
        self.assertEqual(text, "")
    
    def test_calculate_due_date(self):
        """Test: Calculate due date from payment term and issue date"""
        payment_term = PaymentTerm(
            name='14 Tage netto',
            net_days=14
        )
        
        issue_date = date(2026, 9, 1)
        
        due_date = PaymentTermTextService.calculate_due_date(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        self.assertEqual(due_date, date(2026, 9, 15))
    
    def test_calculate_due_date_none_payment_term(self):
        """Test: Calculate due date when payment term is None"""
        issue_date = date(2026, 9, 1)
        
        due_date = PaymentTermTextService.calculate_due_date(
            payment_term=None,
            issue_date=issue_date
        )
        
        self.assertEqual(due_date, issue_date)
    
    def test_discount_percentage_formatting(self):
        """Test: Discount percentage is formatted correctly"""
        # Test with 2.5% discount
        payment_term = PaymentTerm(
            name='2.5% Skonto',
            net_days=30,
            discount_days=10,
            discount_rate=Decimal('0.025')
        )
        
        issue_date = date(2026, 9, 1)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        self.assertIn('mit 2.5% Skonto', text)
    
    def test_discount_percentage_whole_number(self):
        """Test: Discount percentage without decimals for whole numbers"""
        # Test with 3% discount (should show as "3%" not "3.0%")
        payment_term = PaymentTerm(
            name='3% Skonto',
            net_days=30,
            discount_days=10,
            discount_rate=Decimal('0.03')
        )
        
        issue_date = date(2026, 9, 1)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        self.assertIn('mit 3% Skonto', text)
        self.assertNotIn('3.0%', text)
    
    def test_dates_across_month_boundary(self):
        """Test: Dates calculated correctly across month boundaries"""
        payment_term = PaymentTerm(
            name='30 Tage netto',
            net_days=30
        )
        
        # Issue date: January 15
        issue_date = date(2026, 1, 15)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        # Due date should be February 14
        self.assertIn('(bis 14.02.2026)', text)
    
    def test_dates_across_year_boundary(self):
        """Test: Dates calculated correctly across year boundaries"""
        payment_term = PaymentTerm(
            name='30 Tage netto',
            net_days=30
        )
        
        # Issue date: December 15
        issue_date = date(2026, 12, 15)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        # Due date should be January 14, 2027
        self.assertIn('(bis 14.01.2027)', text)
    
    def test_real_world_example_net_14(self):
        """Test: Real-world example - 14 days net"""
        payment_term = PaymentTerm(
            name='14 Tage netto',
            net_days=14
        )
        
        issue_date = date(2026, 9, 1)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        expected = "Zahlbar innerhalb 14 Tagen (bis 15.09.2026) netto."
        self.assertEqual(text, expected)
    
    def test_real_world_example_skonto(self):
        """Test: Real-world example - 2% Skonto in 10 days, net 30 days"""
        payment_term = PaymentTerm(
            name='2% Skonto 10 Tage, netto 30 Tage',
            net_days=30,
            discount_days=10,
            discount_rate=Decimal('0.02')
        )
        
        issue_date = date(2026, 9, 1)
        
        text = PaymentTermTextService.generate_payment_term_text(
            payment_term=payment_term,
            issue_date=issue_date
        )
        
        expected = (
            "Zahlbar innerhalb 10 Tagen (bis 11.09.2026) mit 2% Skonto, "
            "spätestens innerhalb 30 Tagen (bis 01.10.2026) netto."
        )
        self.assertEqual(text, expected)
