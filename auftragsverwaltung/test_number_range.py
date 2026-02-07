"""
Tests for NumberRange model and service
"""
from django.test import TestCase
from django.db import IntegrityError, transaction, connection
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import Mandant
from auftragsverwaltung.models import DocumentType, NumberRange
from auftragsverwaltung.services.number_range import get_next_number
import unittest


class NumberRangeModelTestCase(TestCase):
    """Test NumberRange model"""
    
    def setUp(self):
        """Create test data"""
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
        self.doc_type_invoice = DocumentType.objects.get(key="invoice")
        self.doc_type_quote = DocumentType.objects.get(key="quote")
    
    def test_create_number_range(self):
        """Test creating a number range"""
        nr = NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY'
        )
        
        self.assertIsNotNone(nr.pk)
        self.assertEqual(nr.company, self.company1)
        self.assertEqual(nr.document_type, self.doc_type_invoice)
        self.assertEqual(nr.reset_policy, 'YEARLY')
        self.assertEqual(nr.current_year, 0)
        self.assertEqual(nr.current_seq, 0)
        self.assertEqual(nr.format, '{prefix}{yy}-{seq:05d}')
    
    def test_str_representation(self):
        """Test __str__ method"""
        nr = NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY'
        )
        
        expected = "Test Company 1 - Rechnung (YEARLY)"
        self.assertEqual(str(nr), expected)
    
    def test_unique_constraint_company_document_type(self):
        """Test that only one NumberRange per company+document_type is allowed"""
        NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY'
        )
        
        # Try to create another with same company+document_type
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(
                company=self.company1,
                document_type=self.doc_type_invoice,
                reset_policy='NEVER'
            )
    
    def test_different_companies_can_have_same_document_type(self):
        """Test that different companies can have NumberRanges for the same document type"""
        nr1 = NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY'
        )
        nr2 = NumberRange.objects.create(
            company=self.company2,
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY'
        )
        
        self.assertIsNotNone(nr1.pk)
        self.assertIsNotNone(nr2.pk)
        self.assertNotEqual(nr1.pk, nr2.pk)
    
    def test_same_company_different_document_types(self):
        """Test that same company can have NumberRanges for different document types"""
        nr1 = NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY'
        )
        nr2 = NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_quote,
            reset_policy='YEARLY'
        )
        
        self.assertIsNotNone(nr1.pk)
        self.assertIsNotNone(nr2.pk)
        self.assertNotEqual(nr1.pk, nr2.pk)


class NumberRangeServiceTestCase(TestCase):
    """Test NumberRange service"""
    
    def setUp(self):
        """Create test data"""
        self.company1 = Mandant.objects.create(
            name="Test Company 1",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.doc_type_invoice = DocumentType.objects.get(key="invoice")
        self.doc_type_quote = DocumentType.objects.get(key="quote")
    
    def test_get_next_number_auto_creates_number_range(self):
        """Test that get_next_number auto-creates a NumberRange if it doesn't exist"""
        # Verify no NumberRange exists
        self.assertEqual(NumberRange.objects.count(), 0)
        
        # Get first number
        number = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 15))
        
        # Verify NumberRange was created
        self.assertEqual(NumberRange.objects.count(), 1)
        nr = NumberRange.objects.first()
        self.assertEqual(nr.company, self.company1)
        self.assertEqual(nr.document_type, self.doc_type_invoice)
        self.assertEqual(nr.current_year, 26)
        self.assertEqual(nr.current_seq, 1)
    
    def test_get_next_number_format(self):
        """Test that get_next_number returns correctly formatted number"""
        number = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 15))
        self.assertEqual(number, "R26-00001")
        
        number = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 16))
        self.assertEqual(number, "R26-00002")
    
    def test_get_next_number_sequential(self):
        """Test that get_next_number generates sequential numbers"""
        numbers = []
        for i in range(5):
            number = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 15))
            numbers.append(number)
        
        self.assertEqual(numbers, [
            "R26-00001",
            "R26-00002",
            "R26-00003",
            "R26-00004",
            "R26-00005"
        ])
    
    def test_yearly_reset_on_year_change(self):
        """Test that YEARLY reset policy resets sequence on year change"""
        # Generate numbers in 2025
        number1 = get_next_number(self.company1, self.doc_type_invoice, date(2025, 12, 31))
        number2 = get_next_number(self.company1, self.doc_type_invoice, date(2025, 12, 31))
        
        self.assertEqual(number1, "R25-00001")
        self.assertEqual(number2, "R25-00002")
        
        # Generate number in 2026 (year change)
        number3 = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 1))
        
        # Should reset to 1
        self.assertEqual(number3, "R26-00001")
        
        # Continue in 2026
        number4 = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 2))
        self.assertEqual(number4, "R26-00002")
    
    def test_never_reset_policy(self):
        """Test that NEVER reset policy does not reset sequence on year change"""
        # Create NumberRange with NEVER policy
        NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_invoice,
            reset_policy='NEVER',
            current_year=25,
            current_seq=0
        )
        
        # Generate numbers in 2025
        number1 = get_next_number(self.company1, self.doc_type_invoice, date(2025, 12, 31))
        number2 = get_next_number(self.company1, self.doc_type_invoice, date(2025, 12, 31))
        
        self.assertEqual(number1, "R25-00001")
        self.assertEqual(number2, "R25-00002")
        
        # Generate number in 2026 (year change)
        # With NEVER policy, sequence continues but year changes in format
        number3 = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 1))
        
        # Sequence should NOT reset (continues to 3)
        self.assertEqual(number3, "R26-00003")
        
        # Continue in 2026
        number4 = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 2))
        self.assertEqual(number4, "R26-00004")
    
    def test_different_document_types_independent_sequences(self):
        """Test that different document types have independent sequences"""
        # Invoice numbers
        inv1 = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 15))
        inv2 = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 16))
        
        # Quote numbers
        quote1 = get_next_number(self.company1, self.doc_type_quote, date(2026, 1, 15))
        quote2 = get_next_number(self.company1, self.doc_type_quote, date(2026, 1, 16))
        
        # Invoice numbers with prefix "R"
        self.assertEqual(inv1, "R26-00001")
        self.assertEqual(inv2, "R26-00002")
        
        # Quote numbers with prefix "AN" (as per migration)
        self.assertEqual(quote1, "AN26-00001")
        self.assertEqual(quote2, "AN26-00002")
    
    def test_custom_format_string(self):
        """Test that custom format strings are respected"""
        # Create NumberRange with custom format
        NumberRange.objects.create(
            company=self.company1,
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY',
            format='{prefix}-{yy}/{seq:04d}',
            current_year=26,
            current_seq=0
        )
        
        number = get_next_number(self.company1, self.doc_type_invoice, date(2026, 1, 15))
        self.assertEqual(number, "R-26/0001")
    
    def test_handles_datetime_object(self):
        """Test that get_next_number handles datetime.datetime objects"""
        from datetime import datetime
        
        # Pass datetime instead of date
        number = get_next_number(
            self.company1,
            self.doc_type_invoice,
            datetime(2026, 1, 15, 10, 30, 0)
        )
        self.assertEqual(number, "R26-00001")
    
    def test_default_to_today(self):
        """Test that get_next_number defaults to today if no date is provided"""
        from datetime import date
        
        number = get_next_number(self.company1, self.doc_type_invoice)
        
        # Should use current year
        current_yy = date.today().year % 100
        expected_prefix = f"R{current_yy:02d}-00001"
        self.assertEqual(number, expected_prefix)


@unittest.skipIf(
    connection.settings_dict['ENGINE'] == 'django.db.backends.sqlite3',
    "Concurrency tests are skipped on SQLite due to locking limitations"
)
class NumberRangeConcurrencyTestCase(TestCase):
    """Test NumberRange concurrency and race conditions
    
    Note: These tests are designed for production databases (PostgreSQL)
    and are skipped on SQLite due to its table-level locking limitations.
    """
    
    def setUp(self):
        """Create test data"""
        self.company1 = Mandant.objects.create(
            name="Test Company 1",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.doc_type_invoice = DocumentType.objects.get(key="invoice")
    
    def test_concurrent_number_generation(self):
        """Test that concurrent calls to get_next_number produce unique, sequential numbers"""
        num_threads = 10
        test_date = date(2026, 1, 15)
        
        def generate_number(index):
            """Function to generate a number in a thread"""
            return get_next_number(self.company1, self.doc_type_invoice, test_date)
        
        # Generate numbers concurrently
        numbers = []
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(generate_number, i) for i in range(num_threads)]
            for future in as_completed(futures):
                numbers.append(future.result())
        
        # Verify all numbers are unique
        self.assertEqual(len(numbers), len(set(numbers)), 
                        "All generated numbers should be unique")
        
        # Extract sequence numbers
        sequences = [int(num.split('-')[1]) for num in numbers]
        sequences.sort()
        
        # Verify sequences are consecutive from 1 to num_threads
        self.assertEqual(sequences, list(range(1, num_threads + 1)),
                        "Sequences should be consecutive with no gaps")
    
    def test_concurrent_access_different_document_types(self):
        """Test concurrent access with different document types"""
        doc_type_quote = DocumentType.objects.get(key="quote")
        
        num_threads = 5
        test_date = date(2026, 1, 15)
        
        def generate_invoice_number(index):
            return get_next_number(self.company1, self.doc_type_invoice, test_date)
        
        def generate_quote_number(index):
            return get_next_number(self.company1, doc_type_quote, test_date)
        
        # Generate both invoice and quote numbers concurrently
        invoice_numbers = []
        quote_numbers = []
        
        with ThreadPoolExecutor(max_workers=num_threads * 2) as executor:
            invoice_futures = [executor.submit(generate_invoice_number, i) 
                             for i in range(num_threads)]
            quote_futures = [executor.submit(generate_quote_number, i) 
                           for i in range(num_threads)]
            
            for future in as_completed(invoice_futures):
                invoice_numbers.append(future.result())
            
            for future in as_completed(quote_futures):
                quote_numbers.append(future.result())
        
        # Verify all invoice numbers are unique
        self.assertEqual(len(invoice_numbers), len(set(invoice_numbers)))
        
        # Verify all quote numbers are unique
        self.assertEqual(len(quote_numbers), len(set(quote_numbers)))
        
        # Verify correct prefixes
        for num in invoice_numbers:
            self.assertTrue(num.startswith("R26-"))
        
        for num in quote_numbers:
            self.assertTrue(num.startswith("AN26-"))
