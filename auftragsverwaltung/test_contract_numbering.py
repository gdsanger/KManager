"""
Tests for Contract numbering functionality
"""
from django.test import TestCase
from django.db import IntegrityError, transaction, connection
from django.core.exceptions import ValidationError
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import Mandant, Adresse, PaymentTerm
from auftragsverwaltung.models import DocumentType, NumberRange, Contract
from auftragsverwaltung.services.number_range import get_next_contract_number
import unittest


class ContractNumberRangeModelTestCase(TestCase):
    """Test Contract NumberRange model"""
    
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
    
    def test_create_contract_number_range(self):
        """Test creating a contract number range"""
        nr = NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        self.assertIsNotNone(nr.pk)
        self.assertEqual(nr.company, self.company1)
        self.assertEqual(nr.target, 'CONTRACT')
        self.assertIsNone(nr.document_type)
        self.assertEqual(nr.reset_policy, 'YEARLY')
        self.assertEqual(nr.current_year, 0)
        self.assertEqual(nr.current_seq, 0)
        self.assertEqual(nr.format, 'V{yy}-{seq:05d}')
    
    def test_str_representation_contract(self):
        """Test __str__ method for contract NumberRange"""
        nr = NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY'
        )
        
        expected = "Test Company 1 - Vertrag (YEARLY)"
        self.assertEqual(str(nr), expected)
    
    def test_unique_constraint_contract_per_company(self):
        """Test that only one contract NumberRange per company is allowed"""
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY'
        )
        
        # Try to create another contract NumberRange for same company
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(
                company=self.company1,
                target='CONTRACT',
                reset_policy='NEVER'
            )
    
    def test_different_companies_can_have_contract_number_ranges(self):
        """Test that different companies can have their own contract NumberRanges"""
        nr1 = NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY'
        )
        nr2 = NumberRange.objects.create(
            company=self.company2,
            target='CONTRACT',
            reset_policy='YEARLY'
        )
        
        self.assertIsNotNone(nr1.pk)
        self.assertIsNotNone(nr2.pk)
        self.assertNotEqual(nr1.pk, nr2.pk)
    
    def test_contract_and_document_number_ranges_coexist(self):
        """Test that contract and document NumberRanges can coexist for same company"""
        doc_type = DocumentType.objects.create(
            key="contract_test_invoice",
            name="Contract Test Invoice",
            prefix="R"
        )
        
        nr_doc = NumberRange.objects.create(
            company=self.company1,
            target='DOCUMENT',
            document_type=doc_type,
            reset_policy='YEARLY'
        )
        nr_contract = NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY'
        )
        
        self.assertIsNotNone(nr_doc.pk)
        self.assertIsNotNone(nr_contract.pk)
        self.assertNotEqual(nr_doc.pk, nr_contract.pk)


class ContractNumberServiceTestCase(TestCase):
    """Test Contract number service"""
    
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
    
    def test_get_next_contract_number_raises_error_if_no_range(self):
        """Test that get_next_contract_number raises ValueError if no NumberRange exists"""
        with self.assertRaises(ValueError) as cm:
            get_next_contract_number(self.company1, date(2026, 1, 15))
        
        self.assertIn('Kein Nummernkreis für Verträge konfiguriert', str(cm.exception))
        self.assertIn('Test Company 1', str(cm.exception))
    
    def test_get_next_contract_number_format(self):
        """Test that get_next_contract_number returns correctly formatted number"""
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        number = get_next_contract_number(self.company1, date(2026, 1, 15))
        self.assertEqual(number, "V26-00001")
        
        number = get_next_contract_number(self.company1, date(2026, 1, 16))
        self.assertEqual(number, "V26-00002")
    
    def test_get_next_contract_number_sequential(self):
        """Test that get_next_contract_number generates sequential numbers"""
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        numbers = []
        for i in range(5):
            number = get_next_contract_number(self.company1, date(2026, 1, 15))
            numbers.append(number)
        
        self.assertEqual(numbers, [
            "V26-00001",
            "V26-00002",
            "V26-00003",
            "V26-00004",
            "V26-00005"
        ])
    
    def test_contract_number_yearly_reset_on_year_change(self):
        """Test that YEARLY reset policy resets sequence on year change"""
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        # Generate numbers in 2025
        number1 = get_next_contract_number(self.company1, date(2025, 12, 31))
        number2 = get_next_contract_number(self.company1, date(2025, 12, 31))
        
        self.assertEqual(number1, "V25-00001")
        self.assertEqual(number2, "V25-00002")
        
        # Generate number in 2026 (year change)
        number3 = get_next_contract_number(self.company1, date(2026, 1, 1))
        
        # Should reset to 1
        self.assertEqual(number3, "V26-00001")
        
        # Continue in 2026
        number4 = get_next_contract_number(self.company1, date(2026, 1, 2))
        self.assertEqual(number4, "V26-00002")
    
    def test_contract_number_never_reset_policy(self):
        """Test that NEVER reset policy continues sequence across years"""
        # Create contract NumberRange with NEVER reset
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='NEVER',
            format='V{yy}-{seq:05d}'
        )
        
        # Generate numbers in 2025
        number1 = get_next_contract_number(self.company1, date(2025, 12, 31))
        number2 = get_next_contract_number(self.company1, date(2025, 12, 31))
        
        self.assertEqual(number1, "V25-00001")
        self.assertEqual(number2, "V25-00002")
        
        # Generate number in 2026 (year change)
        number3 = get_next_contract_number(self.company1, date(2026, 1, 1))
        
        # Should continue sequence (not reset)
        self.assertEqual(number3, "V26-00003")
        
        # Continue in 2026
        number4 = get_next_contract_number(self.company1, date(2026, 1, 2))
        self.assertEqual(number4, "V26-00004")
    
    def test_different_companies_independent_sequences(self):
        """Test that different companies have independent contract number sequences"""
        # Create contract NumberRanges for both companies
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        NumberRange.objects.create(
            company=self.company2,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        # Generate numbers for company1
        number1 = get_next_contract_number(self.company1, date(2026, 1, 15))
        number2 = get_next_contract_number(self.company1, date(2026, 1, 15))
        
        # Generate numbers for company2
        number3 = get_next_contract_number(self.company2, date(2026, 1, 15))
        number4 = get_next_contract_number(self.company2, date(2026, 1, 15))
        
        # Both should start at 1
        self.assertEqual(number1, "V26-00001")
        self.assertEqual(number2, "V26-00002")
        self.assertEqual(number3, "V26-00001")
        self.assertEqual(number4, "V26-00002")
    
    def test_custom_format(self):
        """Test that custom format strings work correctly"""
        # Create contract NumberRange with custom format
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='CONTR-{yy}-{seq:04d}'
        )
        
        number = get_next_contract_number(self.company1, date(2026, 1, 15))
        self.assertEqual(number, "CONTR-26-0001")


class ContractModelNumberingTestCase(TestCase):
    """Test Contract model auto-numbering"""
    
    def setUp(self):
        """Create test data"""
        self.company1 = Mandant.objects.create(
            name="Test Company 1",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street",
            plz="54321",
            ort="Customer City",
            land="DE"
        )
        self.doc_type = DocumentType.objects.create(
            key="contract_invoice",
            name="Contract Invoice",
            prefix="R"
        )
        self.payment_term = PaymentTerm.objects.create(
            name="Net 30",
            net_days=30
        )
        
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company1,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
    
    def test_contract_auto_assigns_number_on_create(self):
        """Test that contract automatically gets number on creation"""
        contract = Contract.objects.create(
            company=self.company1,
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            name="Test Contract",
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 2, 1)
        )
        
        self.assertIsNotNone(contract.number)
        self.assertEqual(contract.number, "V26-00001")
    
    def test_contract_sequential_numbering(self):
        """Test that multiple contracts get sequential numbers"""
        contracts = []
        for i in range(3):
            contract = Contract.objects.create(
                company=self.company1,
                customer=self.customer,
                document_type=self.doc_type,
                payment_term=self.payment_term,
                name=f"Test Contract {i+1}",
                interval='MONTHLY',
                start_date=date(2026, 1, 1),
                next_run_date=date(2026, 2, 1)
            )
            contracts.append(contract.number)
        
        self.assertEqual(contracts, ["V26-00001", "V26-00002", "V26-00003"])
    
    def test_contract_manual_number_not_overwritten(self):
        """Test that manually set number is not overwritten"""
        contract = Contract.objects.create(
            company=self.company1,
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            name="Test Contract",
            number="MANUAL-001",  # Manually set number
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 2, 1)
        )
        
        self.assertEqual(contract.number, "MANUAL-001")
    
    def test_contract_number_unique_per_company(self):
        """Test that contract number is unique per company"""
        # Create first contract
        Contract.objects.create(
            company=self.company1,
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            name="Test Contract 1",
            number="V26-00001",
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 2, 1)
        )
        
        # Try to create another contract with same number and company
        with self.assertRaises(IntegrityError):
            Contract.objects.create(
                company=self.company1,
                customer=self.customer,
                document_type=self.doc_type,
                payment_term=self.payment_term,
                name="Test Contract 2",
                number="V26-00001",  # Duplicate number
                interval='MONTHLY',
                start_date=date(2026, 1, 1),
                next_run_date=date(2026, 2, 1)
            )
    
    def test_contract_same_number_different_companies(self):
        """Test that same number can exist for different companies"""
        company2 = Mandant.objects.create(
            name="Test Company 2",
            adresse="Test Street 2",
            plz="54321",
            ort="Test City 2"
        )
        
        # Create NumberRange for company2
        NumberRange.objects.create(
            company=company2,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        # Create contract for company1
        contract1 = Contract.objects.create(
            company=self.company1,
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            name="Test Contract 1",
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 2, 1)
        )
        
        # Create contract for company2 (should get same number)
        contract2 = Contract.objects.create(
            company=company2,
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            name="Test Contract 2",
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 2, 1)
        )
        
        # Both should have same number but different companies
        self.assertEqual(contract1.number, "V26-00001")
        self.assertEqual(contract2.number, "V26-00001")
        self.assertNotEqual(contract1.company, contract2.company)
    
    def test_contract_no_number_range_raises_error(self):
        """Test that creating contract without NumberRange raises ValidationError"""
        company_no_range = Mandant.objects.create(
            name="Company No Range",
            adresse="Test Street",
            plz="12345",
            ort="Test City"
        )
        
        with self.assertRaises(ValidationError) as cm:
            Contract.objects.create(
                company=company_no_range,
                customer=self.customer,
                document_type=self.doc_type,
                payment_term=self.payment_term,
                name="Test Contract",
                interval='MONTHLY',
                start_date=date(2026, 1, 1),
                next_run_date=date(2026, 2, 1)
            )
        
        self.assertIn('Kein Nummernkreis für Verträge konfiguriert', str(cm.exception))


@unittest.skipUnless(
    connection.vendor == 'postgresql',
    'Concurrency tests require PostgreSQL'
)
class ContractNumberConcurrencyTestCase(TestCase):
    """Test Contract number concurrency (race conditions)"""
    
    def setUp(self):
        """Create test data"""
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street",
            plz="12345",
            ort="Test City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street",
            plz="54321",
            ort="Customer City",
            land="DE"
        )
        self.doc_type = DocumentType.objects.create(
            key="concurrency_invoice",
            name="Concurrency Invoice",
            prefix="R"
        )
        self.payment_term = PaymentTerm.objects.create(
            name="Net 30",
            net_days=30
        )
        
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
    
    def test_concurrent_contract_number_generation(self):
        """Test that concurrent contract number generation produces unique numbers"""
        def create_contract(index):
            """Create a contract and return its number"""
            from django.db import connection
            # Close old connection to force new one per thread
            connection.close()
            
            contract = Contract.objects.create(
                company=self.company,
                customer=self.customer,
                document_type=self.doc_type,
                payment_term=self.payment_term,
                name=f"Concurrent Contract {index}",
                interval='MONTHLY',
                start_date=date(2026, 1, 1),
                next_run_date=date(2026, 2, 1)
            )
            return contract.number
        
        # Generate 10 contract numbers concurrently
        num_contracts = 10
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_contract, i) for i in range(num_contracts)]
            numbers = [future.result() for future in as_completed(futures)]
        
        # All numbers should be unique
        self.assertEqual(len(numbers), num_contracts)
        self.assertEqual(len(set(numbers)), num_contracts)
        
        # All numbers should be in the correct format
        for number in numbers:
            self.assertTrue(number.startswith("V26-"))
        
        # Numbers should be sequential (though order may vary)
        expected_numbers = {f"V26-{i:05d}" for i in range(1, num_contracts + 1)}
        self.assertEqual(set(numbers), expected_numbers)
