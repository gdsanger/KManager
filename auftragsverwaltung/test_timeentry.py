"""
Tests for TimeEntry model

Tests the time tracking functionality for billable services, ensuring:
- TimeEntry model validations
- Duration must be > 0
- Order must be of type ORDER
- Order customer must match customer
- Order company must match company
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import (
    DocumentType,
    SalesDocument,
    TimeEntry,
)
from core.models import Mandant, Adresse


class TimeEntryModelTestCase(TestCase):
    """Test TimeEntry model"""
    
    def setUp(self):
        """Set up test data"""
        # Create company (Mandant)
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        
        # Create another company for cross-company validation tests
        self.other_company = Mandant.objects.create(
            name="Other Company",
            adresse="Other Street 1",
            plz="54321",
            ort="Other City"
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Germany",
            adressen_type="KUNDE"
        )
        
        # Create another customer for cross-customer validation tests
        self.other_customer = Adresse.objects.create(
            name="Other Customer",
            strasse="Other Street 1",
            plz="12345",
            ort="Other City",
            land="Germany",
            adressen_type="KUNDE"
        )
        
        # Create document types
        self.order_doc_type, _ = DocumentType.objects.get_or_create(
            key="order",
            defaults={
                "name": "Auftrag",
                "prefix": "AB",
                "is_active": True
            }
        )
        
        self.quote_doc_type, _ = DocumentType.objects.get_or_create(
            key="quote",
            defaults={
                "name": "Angebot",
                "prefix": "AN",
                "is_active": True
            }
        )
        
        # Create order
        self.order = SalesDocument.objects.create(
            company=self.company,
            document_type=self.order_doc_type,
            customer=self.customer,
            number="AB26-00001",
            status="DRAFT",
            issue_date=date.today(),
            subject="Test Order"
        )
        
        # Create quote (wrong document type for time entry)
        self.quote = SalesDocument.objects.create(
            company=self.company,
            document_type=self.quote_doc_type,
            customer=self.customer,
            number="AN26-00001",
            status="DRAFT",
            issue_date=date.today(),
            subject="Test Quote"
        )
        
        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass"
        )
    
    def test_timeentry_creation(self):
        """Test basic time entry creation"""
        timeentry = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=120,
            description="Test work",
            is_travel_cost=False,
            is_billed=False
        )
        
        self.assertEqual(timeentry.company, self.company)
        self.assertEqual(timeentry.customer, self.customer)
        self.assertEqual(timeentry.order, self.order)
        self.assertEqual(timeentry.performed_by, self.user)
        self.assertEqual(timeentry.duration_minutes, 120)
        self.assertEqual(timeentry.description, "Test work")
        self.assertFalse(timeentry.is_travel_cost)
        self.assertFalse(timeentry.is_billed)
        self.assertIsNone(timeentry.billed_at)
    
    def test_duration_minutes_positive_validation(self):
        """Test that duration_minutes must be > 0"""
        timeentry = TimeEntry(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=0,  # Invalid: must be > 0
            description="Test work"
        )
        
        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()
        
        self.assertIn('duration_minutes', cm.exception.error_dict)
    
    def test_duration_minutes_negative_validation(self):
        """Test that duration_minutes cannot be negative"""
        timeentry = TimeEntry(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=-30,  # Invalid: negative
            description="Test work"
        )
        
        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()
        
        self.assertIn('duration_minutes', cm.exception.error_dict)
    
    def test_order_type_validation(self):
        """Test that order must be of type ORDER"""
        timeentry = TimeEntry(
            company=self.company,
            customer=self.customer,
            order=self.quote,  # Invalid: quote instead of order
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Test work"
        )
        
        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()
        
        self.assertIn('order', cm.exception.error_dict)
        self.assertIn('ORDER', str(cm.exception.error_dict['order']))
    
    def test_order_customer_match_validation(self):
        """Test that order.customer must match customer"""
        # Create order with different customer
        other_order = SalesDocument.objects.create(
            company=self.company,
            document_type=self.order_doc_type,
            customer=self.other_customer,  # Different customer
            number="AB26-00002",
            status="DRAFT",
            issue_date=date.today(),
            subject="Other Order"
        )
        
        timeentry = TimeEntry(
            company=self.company,
            customer=self.customer,  # Different from order's customer
            order=other_order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Test work"
        )
        
        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()
        
        # Should have errors for both order and customer fields
        self.assertTrue(
            'order' in cm.exception.error_dict or 'customer' in cm.exception.error_dict
        )
    
    def test_order_company_match_validation(self):
        """Test that order.company must match company"""
        # Create order with different company
        other_order = SalesDocument.objects.create(
            company=self.other_company,  # Different company
            document_type=self.order_doc_type,
            customer=self.customer,
            number="AB26-00003",
            status="DRAFT",
            issue_date=date.today(),
            subject="Other Company Order"
        )
        
        timeentry = TimeEntry(
            company=self.company,  # Different from order's company
            customer=self.customer,
            order=other_order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Test work"
        )
        
        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()
        
        # Should have errors for order or company fields
        self.assertTrue(
            'order' in cm.exception.error_dict or 'company' in cm.exception.error_dict
        )
    
    def test_get_duration_hours(self):
        """Test get_duration_hours() method"""
        timeentry = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=90,
            description="Test work"
        )
        
        # 90 minutes = 1.5 hours
        self.assertEqual(timeentry.get_duration_hours(), Decimal('1.5'))
        
        # Test with exactly 60 minutes
        timeentry.duration_minutes = 60
        self.assertEqual(timeentry.get_duration_hours(), Decimal('1'))
        
        # Test with 120 minutes
        timeentry.duration_minutes = 120
        self.assertEqual(timeentry.get_duration_hours(), Decimal('2'))
    
    def test_default_values(self):
        """Test default values for flags"""
        timeentry = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Test work"
        )
        
        # Check defaults
        self.assertFalse(timeentry.is_travel_cost)
        self.assertFalse(timeentry.is_billed)
        self.assertIsNone(timeentry.billed_at)
    
    def test_ordering(self):
        """Test that time entries are ordered by -service_date, -created_at"""
        # Create multiple time entries with different dates
        entry1 = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date(2026, 1, 1),
            duration_minutes=60,
            description="Entry 1"
        )
        
        entry2 = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date(2026, 1, 3),
            duration_minutes=60,
            description="Entry 2"
        )
        
        entry3 = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date(2026, 1, 2),
            duration_minutes=60,
            description="Entry 3"
        )
        
        # Get all entries in default order
        entries = list(TimeEntry.objects.all())
        
        # Should be ordered by -service_date (most recent first)
        self.assertEqual(entries[0].id, entry2.id)  # 2026-01-03
        self.assertEqual(entries[1].id, entry3.id)  # 2026-01-02
        self.assertEqual(entries[2].id, entry1.id)  # 2026-01-01
    
    def test_str_representation(self):
        """Test string representation of TimeEntry"""
        timeentry = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date(2026, 2, 9),
            duration_minutes=120,
            description="Test work"
        )
        
        str_repr = str(timeentry)
        self.assertIn("2026-02-09", str_repr)
        self.assertIn(self.customer.name, str_repr)
        self.assertIn("120", str_repr)
