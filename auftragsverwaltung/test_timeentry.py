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
from django.urls import reverse
from django.db.models import Sum
from django.utils.formats import number_format
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import (
    DocumentType,
    SalesDocument,
    TimeEntry,
)
from core.models import Activity, Mandant, Adresse


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


class TimeEntryViewTestCase(TestCase):
    """Test TimeEntry create/update views"""
    
    def setUp(self):
        # Company and customer setup
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Germany",
            adressen_type="KUNDE"
        )
        
        # Order document type and order
        self.order_doc_type, _ = DocumentType.objects.get_or_create(
            key="order",
            defaults={
                "name": "Auftrag",
                "prefix": "AB",
                "is_active": True
            }
        )
        self.order = SalesDocument.objects.create(
            company=self.company,
            document_type=self.order_doc_type,
            customer=self.customer,
            number="AB26-00001",
            status="DRAFT",
            issue_date=date.today(),
            subject="Test Order"
        )
        
        # User for authentication
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass"
        )
        self.client.login(username="testuser", password="testpass")
    
    def test_timeentry_create_logs_order_domain_activity(self):
        """Time entry create view logs activity using ORDER domain"""
        response = self.client.post(
            reverse('auftragsverwaltung:timeentry_create'),
            {
                'company_id': self.company.id,
                'customer_id': self.customer.id,
                'order_id': self.order.id,
                'performed_by_id': self.user.id,
                'service_date': date.today().strftime('%Y-%m-%d'),
                'duration_minutes': 75,
                'description': 'Installation work',
            },
            follow=False,
        )
        
        self.assertEqual(response.status_code, 302)
        timeentry = TimeEntry.objects.get()
        self.assertRedirects(
            response,
            reverse('auftragsverwaltung:timeentry_detail', kwargs={'pk': timeentry.pk})
        )
        
        activity = Activity.objects.order_by('-created_at').first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.activity_type, 'TIMEENTRY_CREATED')
        self.assertEqual(activity.company, self.company)
    
    def test_timeentry_update_logs_order_domain_activity(self):
        """Time entry update view logs activity using ORDER domain"""
        timeentry = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Initial work"
        )
        
        response = self.client.post(
            reverse('auftragsverwaltung:timeentry_update', kwargs={'pk': timeentry.pk}),
            {
                'company_id': self.company.id,
                'customer_id': self.customer.id,
                'order_id': self.order.id,
                'performed_by_id': self.user.id,
                'service_date': date.today().strftime('%Y-%m-%d'),
                'duration_minutes': 90,
                'description': 'Updated description',
                'is_billed': 'on',
            },
            follow=False,
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse('auftragsverwaltung:timeentry_detail', kwargs={'pk': timeentry.pk})
        )
        
        activity = Activity.objects.order_by('-created_at').first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.activity_type, 'TIMEENTRY_UPDATED')
        self.assertEqual(activity.company, self.company)
        
        timeentry.refresh_from_db()
        self.assertEqual(timeentry.duration_minutes, 90)
        self.assertEqual(timeentry.description, 'Updated description')


class TimeEntryListSummaryTestCase(TestCase):
    """Test aggregation and summary row in time entry list view"""
    
    def setUp(self):
        # Company and customer setup
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Germany",
            adressen_type="KUNDE"
        )
        
        # Order document type and order
        self.order_doc_type, _ = DocumentType.objects.get_or_create(
            key="order",
            defaults={
                "name": "Auftrag",
                "prefix": "AB",
                "is_active": True
            }
        )
        self.order = SalesDocument.objects.create(
            company=self.company,
            document_type=self.order_doc_type,
            customer=self.customer,
            number="AB26-00001",
            status="DRAFT",
            issue_date=date.today(),
            subject="Test Order"
        )
        
        # User for authentication
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass"
        )
        self.client.login(username="testuser", password="testpass")
        self.list_url = reverse('auftragsverwaltung:timeentry_list')
    
    def create_time_entry(self, duration_minutes, **kwargs):
        """Helper to create a time entry with defaults"""
        return TimeEntry.objects.create(
            company=kwargs.get('company', self.company),
            customer=kwargs.get('customer', self.customer),
            order=kwargs.get('order', self.order),
            performed_by=kwargs.get('performed_by', self.user),
            service_date=kwargs.get('service_date', date.today()),
            duration_minutes=duration_minutes,
            description=kwargs.get('description', 'Work'),
            is_travel_cost=kwargs.get('is_travel_cost', False),
            is_billed=kwargs.get('is_billed', False),
        )
    
    def test_totals_include_all_filtered_entries_across_pages(self):
        """Totals should include all filtered entries, ignoring pagination"""
        for _ in range(30):
            self.create_time_entry(10)
        
        expected_minutes = TimeEntry.objects.aggregate(total=Sum('duration_minutes'))['total'] or 0
        expected_hours = (Decimal(expected_minutes) / Decimal('60')) if expected_minutes else Decimal('0')
        formatted_hours = number_format(expected_hours, 2)
        
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_minutes'], expected_minutes)
        self.assertEqual(response.context['total_hours'], expected_hours)
        self.assertContains(response, "Gesamt")
        self.assertContains(response, f"{expected_minutes} min")
        self.assertContains(response, f"{formatted_hours} h")
        
        # Second page should show the same totals
        response_page2 = self.client.get(self.list_url, {'page': 2})
        self.assertEqual(response_page2.context['total_minutes'], expected_minutes)
        self.assertEqual(response_page2.context['total_hours'], expected_hours)
    
    def test_totals_respect_filters(self):
        """Totals should honor active filters"""
        self.create_time_entry(60, is_billed=True)
        self.create_time_entry(90, is_billed=False)
        
        response = self.client.get(self.list_url, {'is_billed': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_minutes'], 60)
        self.assertEqual(response.context['total_hours'], Decimal('1'))
        self.assertContains(response, "60 min")
        self.assertContains(response, f"{number_format(Decimal('1'), 2)} h")
    
    def test_totals_zero_when_no_results(self):
        """Totals should be zero for an empty filtered queryset"""
        self.create_time_entry(45)
        
        response = self.client.get(self.list_url, {'q': 'nomatch123'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_minutes'], 0)
        self.assertEqual(response.context['total_hours'], Decimal('0'))
        self.assertContains(response, "0 min")
        self.assertContains(response, f"{number_format(Decimal('0'), 2)} h")
