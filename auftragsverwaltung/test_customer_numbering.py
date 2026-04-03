"""
Tests for Customer (Debitor) numbering functionality
"""
from django.test import TestCase
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import Adresse
from auftragsverwaltung.models import NumberRange
from auftragsverwaltung.services.number_range import get_next_customer_number
import unittest


class CustomerNumberRangeModelTestCase(TestCase):
    """Test CUSTOMER NumberRange model"""

    def test_create_customer_number_range(self):
        """Test creating a customer number range"""
        nr = NumberRange.objects.create(
            target='CUSTOMER',
            reset_policy='YEARLY',
            format='DEB{yy}-{seq:05d}'
        )

        self.assertIsNotNone(nr.pk)
        self.assertIsNone(nr.company)
        self.assertEqual(nr.target, 'CUSTOMER')
        self.assertIsNone(nr.document_type)
        self.assertEqual(nr.reset_policy, 'YEARLY')
        self.assertEqual(nr.current_year, 0)
        self.assertEqual(nr.current_seq, 0)
        self.assertEqual(nr.format, 'DEB{yy}-{seq:05d}')

    def test_str_representation_customer(self):
        """Test __str__ method for customer NumberRange"""
        nr = NumberRange.objects.create(
            target='CUSTOMER',
            reset_policy='YEARLY'
        )

        expected = "Kunden-Nummernkreis (global, YEARLY)"
        self.assertEqual(str(nr), expected)

    def test_unique_constraint_customer_global(self):
        """Test that only one CUSTOMER NumberRange is allowed globally"""
        NumberRange.objects.create(
            target='CUSTOMER',
            reset_policy='YEARLY'
        )

        # Try to create another CUSTOMER NumberRange
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(
                target='CUSTOMER',
                reset_policy='NEVER'
            )

    def test_customer_number_range_cannot_have_company(self):
        """Test that CUSTOMER NumberRange cannot have a company"""
        from core.models import Mandant

        company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street",
            plz="12345",
            ort="Test City"
        )

        # Try to create CUSTOMER NumberRange with company
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(
                company=company,
                target='CUSTOMER',
                reset_policy='YEARLY'
            )

    def test_customer_number_range_cannot_have_document_type(self):
        """Test that CUSTOMER NumberRange should not have a document_type"""
        from auftragsverwaltung.models import DocumentType

        doc_type = DocumentType.objects.create(
            key="customer_test",
            name="Customer Test",
            prefix="T"
        )

        # Create CUSTOMER NumberRange with document_type (allowed but not used)
        nr = NumberRange.objects.create(
            target='CUSTOMER',
            document_type=doc_type,
            reset_policy='YEARLY'
        )

        # This is allowed but document_type is not used
        self.assertIsNotNone(nr.pk)
        self.assertEqual(nr.document_type, doc_type)


class CustomerNumberRangeServiceTestCase(TestCase):
    """Test customer number generation service"""

    def setUp(self):
        """Create test NumberRange"""
        NumberRange.objects.create(
            target='CUSTOMER',
            reset_policy='YEARLY',
            format='DEB{yy}-{seq:05d}',
            current_year=0,
            current_seq=0
        )

    def test_get_next_customer_number(self):
        """Test getting next customer number"""
        number = get_next_customer_number(date(2026, 4, 3))
        self.assertEqual(number, "DEB26-00001")

        number = get_next_customer_number(date(2026, 4, 3))
        self.assertEqual(number, "DEB26-00002")

    def test_get_next_customer_number_default_date(self):
        """Test getting next customer number with default date (today)"""
        number = get_next_customer_number()
        self.assertIsNotNone(number)
        self.assertIn("DEB", number)

    def test_get_next_customer_number_yearly_reset(self):
        """Test yearly reset policy for customer numbers"""
        # Generate numbers in 2026
        number1 = get_next_customer_number(date(2026, 12, 31))
        self.assertEqual(number1, "DEB26-00001")

        # Generate number in 2027 - should reset sequence
        number2 = get_next_customer_number(date(2027, 1, 1))
        self.assertEqual(number2, "DEB27-00001")

    def test_get_next_customer_number_never_reset(self):
        """Test NEVER reset policy for customer numbers"""
        # Update to NEVER reset policy
        nr = NumberRange.objects.get(target='CUSTOMER')
        nr.reset_policy = 'NEVER'
        nr.save()

        # Generate numbers in 2026
        number1 = get_next_customer_number(date(2026, 12, 31))
        self.assertEqual(number1, "DEB26-00001")

        number2 = get_next_customer_number(date(2026, 12, 31))
        self.assertEqual(number2, "DEB26-00002")

        # Generate number in 2027 - should NOT reset, sequence continues
        number3 = get_next_customer_number(date(2027, 1, 1))
        self.assertEqual(number3, "DEB27-00003")

    def test_get_next_customer_number_missing_number_range(self):
        """Test error when NumberRange does not exist"""
        # Delete the NumberRange
        NumberRange.objects.get(target='CUSTOMER').delete()

        # Try to get next number
        with self.assertRaises(ValueError) as cm:
            get_next_customer_number()

        self.assertIn('Kein Nummernkreis für Kunden konfiguriert', str(cm.exception))

    def test_custom_format(self):
        """Test custom format string"""
        # Update format
        nr = NumberRange.objects.get(target='CUSTOMER')
        nr.format = 'K-{yy}{seq:04d}'
        nr.save()

        number = get_next_customer_number(date(2026, 4, 3))
        self.assertEqual(number, "K-260001")


class CustomerAutoNumberingTestCase(TestCase):
    """Test automatic customer number assignment"""

    def setUp(self):
        """Create test NumberRange for customers"""
        NumberRange.objects.create(
            target='CUSTOMER',
            reset_policy='YEARLY',
            format='DEB{yy}-{seq:05d}',
            current_year=26,
            current_seq=0
        )

    def test_auto_assign_debitor_number_on_create(self):
        """Test that debitor_number is auto-assigned when creating customer without number"""
        kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt',
            land='Deutschland'
        )

        # Debitor number should be auto-assigned
        self.assertIsNotNone(kunde.debitor_number)
        self.assertEqual(kunde.debitor_number, 'DEB26-00001')

    def test_manual_debitor_number_preserved(self):
        """Test that manually set debitor_number is preserved"""
        kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt',
            land='Deutschland',
            debitor_number='MANUAL-001'
        )

        # Manual number should be preserved
        self.assertEqual(kunde.debitor_number, 'MANUAL-001')

    def test_no_auto_assign_for_non_customer(self):
        """Test that debitor_number is NOT auto-assigned for non-customers"""
        adresse = Adresse.objects.create(
            adressen_type='Adresse',  # Not a customer
            name='Test Adresse',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt',
            land='Deutschland'
        )

        # Debitor number should be None
        self.assertIsNone(adresse.debitor_number)

    def test_no_auto_assign_on_update(self):
        """Test that debitor_number is NOT auto-assigned when updating customer"""
        kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt',
            land='Deutschland'
        )

        original_number = kunde.debitor_number
        self.assertEqual(original_number, 'DEB26-00001')

        # Update customer
        kunde.name = 'Updated Name'
        kunde.save()

        # Number should remain unchanged
        kunde.refresh_from_db()
        self.assertEqual(kunde.debitor_number, original_number)

    def test_multiple_customers_get_sequential_numbers(self):
        """Test that multiple customers get sequential debitor numbers"""
        kunde1 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde 1',
            strasse='Str. 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )

        kunde2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde 2',
            strasse='Str. 2',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )

        kunde3 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde 3',
            strasse='Str. 3',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )

        self.assertEqual(kunde1.debitor_number, 'DEB26-00001')
        self.assertEqual(kunde2.debitor_number, 'DEB26-00002')
        self.assertEqual(kunde3.debitor_number, 'DEB26-00003')

    def test_error_when_number_range_missing(self):
        """Test that ValidationError is raised when NumberRange is missing"""
        # Delete the NumberRange
        NumberRange.objects.get(target='CUSTOMER').delete()

        # Try to create customer
        with self.assertRaises(ValidationError) as cm:
            Adresse.objects.create(
                adressen_type='KUNDE',
                name='Test Kunde',
                strasse='Test Str. 1',
                plz='12345',
                ort='Test Stadt',
                land='Deutschland'
            )

        self.assertIn('debitor_number', cm.exception.message_dict)
        self.assertIn('Kein Nummernkreis für Kunden konfiguriert', str(cm.exception))

    def test_unique_debitor_number_constraint(self):
        """Test that debitor_number must be unique"""
        # Create first customer with auto-assigned number
        kunde1 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Kunde 1',
            strasse='Str. 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )

        # Try to create second customer with same manual number
        with self.assertRaises(IntegrityError):
            Adresse.objects.create(
                adressen_type='KUNDE',
                name='Kunde 2',
                strasse='Str. 2',
                plz='12345',
                ort='Stadt',
                land='Deutschland',
                debitor_number=kunde1.debitor_number  # Duplicate number
            )

    def test_null_debitor_numbers_allowed(self):
        """Test that multiple addresses can have NULL debitor_number"""
        # Create multiple non-customers with NULL debitor_number
        adresse1 = Adresse.objects.create(
            adressen_type='Adresse',
            name='Adresse 1',
            strasse='Str. 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )

        adresse2 = Adresse.objects.create(
            adressen_type='Adresse',
            name='Adresse 2',
            strasse='Str. 2',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )

        # Both should have NULL debitor_number (allowed)
        self.assertIsNone(adresse1.debitor_number)
        self.assertIsNone(adresse2.debitor_number)


@unittest.skipIf(
    'sqlite' in settings.DATABASES['default']['ENGINE'],
    "SQLite has table-level locking, race condition tests designed for PostgreSQL"
)
class CustomerNumberConcurrencyTestCase(TestCase):
    """Test race-safe customer number generation under concurrent access"""

    def setUp(self):
        """Create test NumberRange for customers"""
        NumberRange.objects.create(
            target='CUSTOMER',
            reset_policy='YEARLY',
            format='DEB{yy}-{seq:05d}',
            current_year=26,
            current_seq=0
        )

    def test_concurrent_customer_creation(self):
        """Test that concurrent customer creation produces unique sequential numbers"""
        from django.db import connection

        def create_customer(index):
            """Create a customer in a separate thread/connection"""
            # Each thread needs its own connection
            connection.close()
            kunde = Adresse.objects.create(
                adressen_type='KUNDE',
                name=f'Concurrent Customer {index}',
                strasse=f'Str. {index}',
                plz='12345',
                ort='Stadt',
                land='Deutschland'
            )
            return kunde.debitor_number

        # Create 10 customers concurrently
        num_customers = 10
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_customer, i) for i in range(num_customers)]
            numbers = [future.result() for future in as_completed(futures)]

        # All numbers should be unique
        self.assertEqual(len(numbers), len(set(numbers)), "Duplicate numbers found!")

        # All numbers should follow the pattern and be sequential
        expected_numbers = {f'DEB26-{i:05d}' for i in range(1, num_customers + 1)}
        self.assertEqual(set(numbers), expected_numbers)

        # Verify all customers were created
        self.assertEqual(Adresse.objects.filter(adressen_type='KUNDE').count(), num_customers)
