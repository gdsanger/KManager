"""
Tests for Contract models and ContractBillingService

Tests the contract management functionality, ensuring:
- Contract model validations
- ContractLine model validations
- ContractRun uniqueness constraints
- Date advancement logic for different intervals
- Invoice generation from contracts
- Proper audit trail creation
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from auftragsverwaltung.models import (
    DocumentType,
    SalesDocument,
    SalesDocumentLine,
    Contract,
    ContractLine,
    ContractRun,
    NumberRange,
)
from auftragsverwaltung.services.contract_billing import ContractBillingService
from core.models import Mandant, Adresse, PaymentTerm, TaxRate, Kostenart, Item


class ContractModelTestCase(TestCase):
    """Test Contract model"""
    
    def setUp(self):
        """Set up test data"""
        # Create company (Mandant)
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Germany"
        )
        
        # Get document type (created by migration)
        self.doc_type = DocumentType.objects.get(key="invoice")
        
        # Create payment term
        self.payment_term = PaymentTerm.objects.create(
            name="Net 30",
            net_days=30,
            is_default=True
        )
        
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
    
    def test_contract_creation(self):
        """Test basic contract creation"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        self.assertEqual(contract.name, "Test Contract")
        self.assertEqual(contract.company, self.company)
        self.assertEqual(contract.customer, self.customer)
        self.assertEqual(contract.interval, 'MONTHLY')
        self.assertTrue(contract.is_active)
        self.assertIsNone(contract.end_date)
        self.assertIsNone(contract.last_run_date)
    
    def test_contract_end_date_validation(self):
        """Test that end_date must be >= start_date"""
        contract = Contract(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            end_date=date(2025, 12, 31),  # Before start_date
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        with self.assertRaises(ValidationError) as context:
            contract.full_clean()
        
        self.assertIn('end_date', context.exception.error_dict)
    
    def test_contract_next_run_date_validation(self):
        """Test that next_run_date must be >= start_date"""
        contract = Contract(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2025, 12, 31),  # Before start_date
            is_active=True
        )
        
        with self.assertRaises(ValidationError) as context:
            contract.full_clean()
        
        self.assertIn('next_run_date', context.exception.error_dict)
    
    def test_is_contract_active_with_is_active_false(self):
        """Test that contract is not active if is_active=False"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=False
        )
        
        self.assertFalse(contract.is_contract_active())
    
    def test_is_contract_active_with_end_date_past(self):
        """Test that contract is not active if end_date is in the past"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),  # Past
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        self.assertFalse(contract.is_contract_active())
    
    def test_is_contract_active_with_end_date_future(self):
        """Test that contract is active if end_date is in the future"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            end_date=date(2027, 12, 31),  # Future
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        self.assertTrue(contract.is_contract_active())
    
    def test_advance_next_run_date_monthly(self):
        """Test monthly interval advancement"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 15),
            next_run_date=date(2026, 1, 15),
            is_active=True
        )
        
        new_date = contract.advance_next_run_date()
        self.assertEqual(new_date, date(2026, 2, 15))
    
    def test_advance_next_run_date_quarterly(self):
        """Test quarterly interval advancement"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='QUARTERLY',
            start_date=date(2026, 1, 15),
            next_run_date=date(2026, 1, 15),
            is_active=True
        )
        
        new_date = contract.advance_next_run_date()
        self.assertEqual(new_date, date(2026, 4, 15))
    
    def test_advance_next_run_date_semi_annual(self):
        """Test semi-annual interval advancement"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='SEMI_ANNUAL',
            start_date=date(2026, 1, 15),
            next_run_date=date(2026, 1, 15),
            is_active=True
        )
        
        new_date = contract.advance_next_run_date()
        self.assertEqual(new_date, date(2026, 7, 15))
    
    def test_advance_next_run_date_annual(self):
        """Test annual interval advancement"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='ANNUAL',
            start_date=date(2026, 1, 15),
            next_run_date=date(2026, 1, 15),
            is_active=True
        )
        
        new_date = contract.advance_next_run_date()
        self.assertEqual(new_date, date(2027, 1, 15))
    
    def test_advance_next_run_date_end_of_month(self):
        """Test that advancing from Jan 31 to Feb handles missing day correctly"""
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 31),
            next_run_date=date(2026, 1, 31),
            is_active=True
        )
        
        new_date = contract.advance_next_run_date()
        # Feb 2026 has 28 days, so should be Feb 28
        self.assertEqual(new_date, date(2026, 2, 28))


class ContractLineModelTestCase(TestCase):
    """Test ContractLine model"""
    
    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Germany"
        )
        
        # Get document type (created by migration)
        self.doc_type = DocumentType.objects.get(key="invoice")
        
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code="VAT_19",
            name="19% VAT",
            rate=Decimal('0.19'),
            is_active=True
        )
        
        # Create cost types
        self.cost_type = Kostenart.objects.create(
            name="General"
        )
        self.cost_type2 = Kostenart.objects.create(
            name="Secondary"
        )
        
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        # Create contract
        self.contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
    
    def test_contract_line_creation(self):
        """Test basic contract line creation"""
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description="Test Line",
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        self.assertEqual(line.contract, self.contract)
        self.assertEqual(line.position_no, 1)
        self.assertEqual(line.quantity, Decimal('2.0000'))
        self.assertEqual(line.unit_price_net, Decimal('100.00'))
    
    def test_contract_line_unique_position_no(self):
        """Test that position_no must be unique per contract"""
        ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description="Line 1",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
        )
        
        # Try to create another line with same position_no
        with self.assertRaises(IntegrityError):
            ContractLine.objects.create(
                contract=self.contract,
                position_no=1,
                description="Line 2",
                quantity=Decimal('1.0000'),
                unit_price_net=Decimal('100.00'),
                tax_rate=self.tax_rate,
            )


class ContractRunModelTestCase(TestCase):
    """Test ContractRun model"""
    
    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Germany"
        )
        
        # Get document type (created by migration)
        self.doc_type = DocumentType.objects.get(key="invoice")
        
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        # Create contract
        self.contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
    
    def test_contract_run_creation(self):
        """Test basic contract run creation"""
        run = ContractRun.objects.create(
            contract=self.contract,
            run_date=date(2026, 1, 1),
            status='SUCCESS',
            message='Test run'
        )
        
        self.assertEqual(run.contract, self.contract)
        self.assertEqual(run.run_date, date(2026, 1, 1))
        self.assertEqual(run.status, 'SUCCESS')
        self.assertIsNotNone(run.created_at)
    
    def test_contract_run_unique_per_contract_date(self):
        """Test that only one run per contract and date is allowed"""
        ContractRun.objects.create(
            contract=self.contract,
            run_date=date(2026, 1, 1),
            status='SUCCESS',
        )
        
        # Try to create another run for same contract and date
        with self.assertRaises(IntegrityError):
            ContractRun.objects.create(
                contract=self.contract,
                run_date=date(2026, 1, 1),
                status='SUCCESS',
            )


class ContractBillingServiceTestCase(TestCase):
    """Test ContractBillingService"""
    
    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        
        # Create customer
        self.customer = Adresse.objects.create(
            name="Test Customer",
            strasse="Customer Street 1",
            plz="54321",
            ort="Customer City",
            land="Germany"
        )
        
        # Get document type (created by migration)
        self.doc_type = DocumentType.objects.get(key="invoice")
        
        # Create payment term
        self.payment_term = PaymentTerm.objects.create(
            name="Net 30",
            net_days=30,
            is_default=True
        )
        
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code="VAT_19",
            name="19% VAT",
            rate=Decimal('0.19'),
            is_active=True
        )
        
        # Create cost types
        self.cost_type = Kostenart.objects.create(
            name="General"
        )
        self.cost_type2 = Kostenart.objects.create(
            name="Secondary"
        )
        
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
    
    def test_generate_due_no_contracts(self):
        """Test generate_due with no contracts"""
        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))
        self.assertEqual(len(runs), 0)
    
    def test_generate_due_contract_not_due(self):
        """Test generate_due with contract not yet due"""
        Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 2, 1),  # Future
            is_active=True
        )
        
        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))
        self.assertEqual(len(runs), 0)
    
    def test_generate_due_contract_inactive(self):
        """Test generate_due with inactive contract"""
        Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=False  # Inactive
        )
        
        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))
        self.assertEqual(len(runs), 0)
    
    def test_generate_due_success(self):
        """Test successful invoice generation"""
        # Create contract
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        period_start = contract.next_run_date
        period_end = contract.advance_next_run_date() - timedelta(days=1)
        
        # Create contract lines
        ContractLine.objects.create(
            contract=contract,
            position_no=1,
            description="Monthly Service",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('1000.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type,
            cost_type_2=self.cost_type2,
            is_discountable=True
        )
        
        # Generate invoices
        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))
        
        # Check run
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run.status, 'SUCCESS')
        self.assertEqual(run.contract, contract)
        self.assertIsNotNone(run.document)
        
        # Check generated document
        document = run.document
        self.assertEqual(document.company, self.company)
        self.assertEqual(document.document_type, self.doc_type)
        self.assertEqual(document.status, 'DRAFT')
        self.assertEqual(document.issue_date, date(2026, 1, 1))
        self.assertEqual(document.payment_term, self.payment_term)
        self.assertEqual(document.customer, self.customer)
        expected_subject = f"{contract.name} {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}"
        self.assertEqual(document.subject, expected_subject)
        
        # Check due_date
        expected_due_date = date(2026, 1, 31)  # Jan 1 + 30 days
        self.assertEqual(document.due_date, expected_due_date)
        
        # Check document lines
        lines = document.lines.all()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line.position_no, 1)
        self.assertEqual(line.description, "Monthly Service")
        self.assertEqual(line.quantity, Decimal('1.0000'))
        self.assertEqual(line.unit_price_net, Decimal('1000.00'))
        self.assertEqual(line.tax_rate, self.tax_rate)
        self.assertEqual(line.kostenart1, self.cost_type)
        self.assertEqual(line.kostenart2, self.cost_type2)
        self.assertTrue(line.is_discountable)
        
        # Check totals (calculated by DocumentCalculationService)
        self.assertEqual(document.total_net, Decimal('1000.00'))
        self.assertEqual(document.total_tax, Decimal('190.00'))
        self.assertEqual(document.total_gross, Decimal('1190.00'))
        
        # Check contract dates updated
        contract.refresh_from_db()
        self.assertEqual(contract.last_run_date, date(2026, 1, 1))
        self.assertEqual(contract.next_run_date, date(2026, 2, 1))
    
    def test_generate_due_no_duplicate_runs(self):
        """Test that duplicate runs are prevented"""
        # Create contract
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        # Create contract line
        ContractLine.objects.create(
            contract=contract,
            position_no=1,
            description="Monthly Service",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('1000.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        # Generate invoices first time
        runs1 = ContractBillingService.generate_due(today=date(2026, 1, 1))
        self.assertEqual(len(runs1), 1)
        
        # Reset next_run_date to test duplicate prevention
        contract.next_run_date = date(2026, 1, 1)
        contract.save()
        
        # Try to generate again
        runs2 = ContractBillingService.generate_due(today=date(2026, 1, 1))
        self.assertEqual(len(runs2), 1)
        self.assertEqual(runs2[0].id, runs1[0].id)  # Same run returned
        
        # Verify only one run exists
        total_runs = ContractRun.objects.filter(contract=contract, run_date=date(2026, 1, 1)).count()
        self.assertEqual(total_runs, 1)

    def test_generate_multiple_invoices_without_auto_finalize(self):
        """Test that multiple invoices can be generated without auto_finalize (draft invoices with unique numbers)"""
        # Create contract WITHOUT auto_finalize
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True,
            auto_finalize=False  # Do NOT auto-finalize
        )

        # Create contract line
        ContractLine.objects.create(
            contract=contract,
            position_no=1,
            description="Monthly Service",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('1000.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )

        # Generate first invoice
        runs1 = ContractBillingService.generate_due(today=date(2026, 1, 1))
        self.assertEqual(len(runs1), 1)
        self.assertEqual(runs1[0].status, 'SUCCESS')
        doc1 = runs1[0].document
        self.assertEqual(doc1.status, 'DRAFT')  # Draft status
        self.assertNotEqual(doc1.number, '')  # But number IS assigned to avoid unique constraint violation
        self.assertTrue(doc1.number.startswith('R'))  # Invoice prefix

        # Generate second invoice
        runs2 = ContractBillingService.generate_due(today=date(2026, 2, 1))
        self.assertEqual(len(runs2), 1)
        self.assertEqual(runs2[0].status, 'SUCCESS')
        doc2 = runs2[0].document
        self.assertEqual(doc2.status, 'DRAFT')  # Draft status
        self.assertNotEqual(doc2.number, '')  # But number IS assigned to avoid unique constraint violation
        self.assertTrue(doc2.number.startswith('R'))  # Invoice prefix

        # Verify both documents exist with DIFFERENT numbers
        self.assertNotEqual(doc1.pk, doc2.pk)
        self.assertNotEqual(doc1.number, doc2.number)  # Different invoice numbers
        self.assertEqual(SalesDocument.objects.filter(company=self.company, document_type=self.doc_type).count(), 2)

    def test_generate_multiple_invoices_with_auto_finalize(self):
        """Test that multiple invoices can be generated WITH auto_finalize (unique numbers assigned)"""
        # Create contract WITH auto_finalize
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True,
            auto_finalize=True  # Auto-finalize to assign numbers
        )

        # Create contract line
        ContractLine.objects.create(
            contract=contract,
            position_no=1,
            description="Monthly Service",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('1000.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )

        # Generate first invoice
        runs1 = ContractBillingService.generate_due(today=date(2026, 1, 1))
        self.assertEqual(len(runs1), 1)
        self.assertEqual(runs1[0].status, 'SUCCESS')
        doc1 = runs1[0].document
        self.assertEqual(doc1.status, 'SENT')  # Finalized
        self.assertNotEqual(doc1.number, '')  # Number assigned
        self.assertTrue(doc1.number.startswith('R'))  # Invoice prefix

        # Generate second invoice
        runs2 = ContractBillingService.generate_due(today=date(2026, 2, 1))
        self.assertEqual(len(runs2), 1)
        self.assertEqual(runs2[0].status, 'SUCCESS')
        doc2 = runs2[0].document
        self.assertEqual(doc2.status, 'SENT')  # Finalized
        self.assertNotEqual(doc2.number, '')  # Number assigned
        self.assertTrue(doc2.number.startswith('R'))  # Invoice prefix

        # Verify both documents exist with DIFFERENT numbers
        self.assertNotEqual(doc1.pk, doc2.pk)
        self.assertNotEqual(doc1.number, doc2.number)  # Different invoice numbers
        self.assertEqual(SalesDocument.objects.filter(company=self.company, document_type=self.doc_type).count(), 2)

        # Verify no database constraint violation occurred
        # If there was a constraint violation, the test would have failed earlier

    def test_kurztext_fields_copied_to_sales_document_line(self):
        """Test that kurztext fields (short_text_1, short_text_2, long_text) are copied from ContractLine to SalesDocumentLine during billing run"""
        # Create contract
        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract Kurztext",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )

        # Create contract line with kurztext fields populated
        contract_line = ContractLine.objects.create(
            contract=contract,
            position_no=1,
            short_text_1="Test Kurztext 1",
            short_text_2="Test Kurztext 2",
            long_text="This is a detailed long text description for the contract line.",
            description="Monthly Service with Kurztext",
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('500.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type,
            is_discountable=True
        )

        # Generate invoice
        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))

        # Verify run success
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run.status, 'SUCCESS')
        self.assertIsNotNone(run.document)

        # Get generated document and its lines
        document = run.document
        lines = document.lines.all()
        self.assertEqual(len(lines), 1)
        sales_line = lines[0]

        # Assert that kurztext fields are copied 1:1 from ContractLine to SalesDocumentLine
        self.assertEqual(sales_line.short_text_1, contract_line.short_text_1)
        self.assertEqual(sales_line.short_text_2, contract_line.short_text_2)
        self.assertEqual(sales_line.long_text, contract_line.long_text)
        self.assertEqual(sales_line.description, contract_line.description)

        # Verify exact values
        self.assertEqual(sales_line.short_text_1, "Test Kurztext 1")
        self.assertEqual(sales_line.short_text_2, "Test Kurztext 2")
        self.assertEqual(sales_line.long_text, "This is a detailed long text description for the contract line.")
        self.assertEqual(sales_line.description, "Monthly Service with Kurztext")

    def test_generate_due_multiple_lines_full_position_data(self):
        """Regression test: a contract with several positions (different tax rates/prices)
        must produce a SalesDocument whose lines carry the full ContractLine data
        (texts, quantity, price, tax rate) and correctly calculated totals."""
        tax_rate_7 = TaxRate.objects.create(
            code="VAT_7",
            name="7% VAT",
            rate=Decimal('0.07'),
            is_active=True
        )

        contract = Contract.objects.create(
            company=self.company,
            name="Test Contract Multi-Line",
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )

        line_1 = ContractLine.objects.create(
            contract=contract,
            position_no=1,
            short_text_1="Leasingrate",
            short_text_2="Fahrzeug",
            long_text="Monatliche Leasingrate für Fahrzeug XY",
            description="Monatliche Leasingrate",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('1000.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type,
            is_discountable=True
        )
        line_2 = ContractLine.objects.create(
            contract=contract,
            position_no=2,
            short_text_1="Wartungspauschale",
            short_text_2="",
            long_text="Monatliche Wartungspauschale",
            description="Wartungspauschale",
            quantity=Decimal('3.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=tax_rate_7,
            cost_type_2=self.cost_type2,
            is_discountable=False
        )

        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))

        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run.status, 'SUCCESS')
        document = run.document

        lines = list(document.lines.order_by('position_no'))
        self.assertEqual(len(lines), 2)

        sales_line_1, sales_line_2 = lines

        self.assertEqual(sales_line_1.position_no, 1)
        self.assertEqual(sales_line_1.short_text_1, line_1.short_text_1)
        self.assertEqual(sales_line_1.short_text_2, line_1.short_text_2)
        self.assertEqual(sales_line_1.long_text, line_1.long_text)
        self.assertEqual(sales_line_1.description, line_1.description)
        self.assertEqual(sales_line_1.quantity, line_1.quantity)
        self.assertEqual(sales_line_1.unit_price_net, line_1.unit_price_net)
        self.assertEqual(sales_line_1.tax_rate, self.tax_rate)
        self.assertEqual(sales_line_1.kostenart1, self.cost_type)
        self.assertTrue(sales_line_1.is_discountable)

        self.assertEqual(sales_line_2.position_no, 2)
        self.assertEqual(sales_line_2.short_text_1, line_2.short_text_1)
        self.assertEqual(sales_line_2.long_text, line_2.long_text)
        self.assertEqual(sales_line_2.description, line_2.description)
        self.assertEqual(sales_line_2.quantity, line_2.quantity)
        self.assertEqual(sales_line_2.unit_price_net, line_2.unit_price_net)
        self.assertEqual(sales_line_2.tax_rate, tax_rate_7)
        self.assertEqual(sales_line_2.kostenart2, self.cost_type2)
        self.assertFalse(sales_line_2.is_discountable)

        # None of the position data may be empty/zero
        for sales_line in (sales_line_1, sales_line_2):
            self.assertTrue(sales_line.description)
            self.assertGreater(sales_line.unit_price_net, Decimal('0.00'))
            self.assertGreater(sales_line.quantity, Decimal('0.0000'))

        # Totals: 1x1000.00 @19% + 3x50.00 @7% = 1150.00 net, 190.00 + 10.50 tax
        self.assertEqual(document.total_net, Decimal('1150.00'))
        self.assertEqual(document.total_tax, Decimal('200.50'))
        self.assertEqual(document.total_gross, Decimal('1350.50'))

