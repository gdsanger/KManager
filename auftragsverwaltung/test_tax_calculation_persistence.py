"""
Regression tests for tax calculation persistence issue #601

Tests that tax calculations are properly persisted to the database after save operations,
without requiring manual tax rate changes in the UI.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import (
    SalesDocument, SalesDocumentLine, DocumentType, NumberRange,
    Contract, ContractLine
)
from auftragsverwaltung.services.document_calculation import DocumentCalculationService
from auftragsverwaltung.services.contract_billing import ContractBillingService
from core.models import Mandant, Adresse, TaxRate, PaymentTerm

User = get_user_model()


class SalesDocumentTaxPersistenceTestCase(TestCase):
    """Test tax calculation persistence for SalesDocument"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test company
        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='DE123456789'
        )

        # Create test customer
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer',
            anrede='Herr',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland'
        )

        # Create test tax rates
        self.tax_rate_19 = TaxRate.objects.create(
            code='STANDARD',
            name='Standard-Steuersatz 19%',
            rate=Decimal('0.19'),
            is_active=True
        )

        self.tax_rate_7 = TaxRate.objects.create(
            code='REDUCED',
            name='Ermäßigter Steuersatz 7%',
            rate=Decimal('0.07'),
            is_active=True
        )

        # Create payment term
        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto',
            net_days=14,
            is_default=False
        )

        # Create document type for Invoice
        self.doc_type_invoice, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'RE',
                'is_invoice': True,
                'is_active': True
            }
        )

        # Create number range for invoice
        NumberRange.objects.get_or_create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type_invoice,
            defaults={
                'reset_policy': 'YEARLY',
                'format': '{prefix}{yy}-{seq:05d}'
            }
        )

    def test_tax_calculation_persists_after_recalculate(self):
        """
        Test that tax values are properly persisted when recalculate(persist=True) is called

        This is the core regression test for issue #601.
        """
        # Create a sales document
        document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            number='RE-TEST-001',
            status='DRAFT',
            customer=self.customer,
            payment_term=self.payment_term,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )

        # Create lines with 19% tax rate (like in the bug report)
        # Line 1: 2 items × 100.00 = 200.00 net
        line1 = SalesDocumentLine.objects.create(
            document=document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description='Test Item 1',
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19,
            # Note: line_net, line_tax, line_gross default to 0.00
        )

        # Line 2: 3 items × 50.00 = 150.00 net
        line2 = SalesDocumentLine.objects.create(
            document=document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            description='Test Item 2',
            quantity=Decimal('3.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate_19,
            # Note: line_net, line_tax, line_gross default to 0.00
        )

        # At this point, line totals in DB are 0.00 (the bug!)
        line1.refresh_from_db()
        line2.refresh_from_db()
        self.assertEqual(line1.line_net, Decimal('0.00'))
        self.assertEqual(line1.line_tax, Decimal('0.00'))
        self.assertEqual(line1.line_gross, Decimal('0.00'))

        # Call recalculate with persist=True (this is what views do)
        result = DocumentCalculationService.recalculate(document, persist=True)

        # Verify document totals
        document.refresh_from_db()
        self.assertEqual(result.total_net, Decimal('350.00'))  # 200 + 150
        self.assertEqual(result.total_tax, Decimal('66.50'))   # 350 * 0.19
        self.assertEqual(result.total_gross, Decimal('416.50'))  # 350 + 66.50

        self.assertEqual(document.total_net, Decimal('350.00'))
        self.assertEqual(document.total_tax, Decimal('66.50'))
        self.assertEqual(document.total_gross, Decimal('416.50'))

        # THE CRITICAL TEST: Verify line totals are persisted to DB
        line1.refresh_from_db()
        line2.refresh_from_db()

        # Line 1: 2 × 100.00 = 200.00 net, 200.00 × 0.19 = 38.00 tax
        self.assertEqual(line1.line_net, Decimal('200.00'))
        self.assertEqual(line1.line_tax, Decimal('38.00'))
        self.assertEqual(line1.line_gross, Decimal('238.00'))

        # Line 2: 3 × 50.00 = 150.00 net, 150.00 × 0.19 = 28.50 tax
        self.assertEqual(line2.line_net, Decimal('150.00'))
        self.assertEqual(line2.line_tax, Decimal('28.50'))
        self.assertEqual(line2.line_gross, Decimal('178.50'))

    def test_tax_calculation_with_multiple_tax_rates(self):
        """Test that mixed tax rates (19% and 7%) are properly persisted"""
        # Create a sales document
        document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            number='RE-TEST-002',
            status='DRAFT',
            customer=self.customer,
            issue_date=date.today(),
        )

        # Create lines with different tax rates
        # Line 1: 19% tax rate
        line1 = SalesDocumentLine.objects.create(
            document=document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description='Standard Rate Item',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19,
        )

        # Line 2: 7% tax rate
        line2 = SalesDocumentLine.objects.create(
            document=document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            description='Reduced Rate Item',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_7,
        )

        # Recalculate and persist
        DocumentCalculationService.recalculate(document, persist=True)

        # Verify line totals are persisted correctly
        line1.refresh_from_db()
        line2.refresh_from_db()

        # Line 1: 100.00 net, 100.00 × 0.19 = 19.00 tax
        self.assertEqual(line1.line_net, Decimal('100.00'))
        self.assertEqual(line1.line_tax, Decimal('19.00'))
        self.assertEqual(line1.line_gross, Decimal('119.00'))

        # Line 2: 100.00 net, 100.00 × 0.07 = 7.00 tax
        self.assertEqual(line2.line_net, Decimal('100.00'))
        self.assertEqual(line2.line_tax, Decimal('7.00'))
        self.assertEqual(line2.line_gross, Decimal('107.00'))

        # Verify document totals
        document.refresh_from_db()
        self.assertEqual(document.total_net, Decimal('200.00'))  # 100 + 100
        self.assertEqual(document.total_tax, Decimal('26.00'))   # 19 + 7
        self.assertEqual(document.total_gross, Decimal('226.00'))  # 200 + 26


class ContractBillingTaxPersistenceTestCase(TestCase):
    """Test tax calculation persistence for Contract billing"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create test company
        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='DE123456789'
        )

        # Create test customer
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer',
            anrede='Herr',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland'
        )

        # Create test tax rate
        self.tax_rate_19 = TaxRate.objects.create(
            code='STANDARD',
            name='Standard-Steuersatz 19%',
            rate=Decimal('0.19'),
            is_active=True
        )

        # Create document type for Invoice
        self.doc_type_invoice, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'RE',
                'is_invoice': True,
                'is_active': True
            }
        )

        # Create number range for invoice
        NumberRange.objects.get_or_create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type_invoice,
            defaults={
                'reset_policy': 'YEARLY',
                'format': '{prefix}{yy}-{seq:05d}'
            }
        )

        # Create number range for contracts
        NumberRange.objects.get_or_create(
            company=self.company,
            target='CONTRACT',
            defaults={
                'reset_policy': 'YEARLY',
                'format': 'V{yy}-{seq:05d}'
            }
        )

    def test_contract_billing_persists_tax_calculations(self):
        """
        Test that invoices generated from contracts have persisted line tax totals

        This is the Contract variant of the regression test for issue #601.
        """
        # Create a contract
        contract = Contract.objects.create(
            company=self.company,
            name='Monthly Service Contract',
            customer=self.customer,
            document_type=self.doc_type_invoice,
            interval='MONTHLY',
            start_date=date.today(),
            next_run_date=date.today(),
            is_active=True,
        )

        # Create contract lines
        # Line 1: Monthly service fee
        contract_line1 = ContractLine.objects.create(
            contract=contract,
            position_no=1,
            description='Monthly Service',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('500.00'),
            tax_rate=self.tax_rate_19,
        )

        # Line 2: Additional service
        contract_line2 = ContractLine.objects.create(
            contract=contract,
            position_no=2,
            description='Additional Service',
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19,
        )

        # Run billing (this creates SalesDocument with lines)
        runs = ContractBillingService.generate_due(today=date.today())

        # Verify billing succeeded
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, 'SUCCESS')

        # Get the generated invoice
        invoice = runs[0].document
        self.assertIsNotNone(invoice)

        # Refresh from DB to ensure we're testing persisted values
        invoice.refresh_from_db()

        # Verify invoice totals
        # Line 1: 1 × 500.00 = 500.00 net, 500.00 × 0.19 = 95.00 tax
        # Line 2: 2 × 100.00 = 200.00 net, 200.00 × 0.19 = 38.00 tax
        # Total: 700.00 net, 133.00 tax, 833.00 gross
        self.assertEqual(invoice.total_net, Decimal('700.00'))
        self.assertEqual(invoice.total_tax, Decimal('133.00'))
        self.assertEqual(invoice.total_gross, Decimal('833.00'))

        # THE CRITICAL TEST: Verify line totals are persisted to DB
        lines = list(invoice.lines.order_by('position_no'))
        self.assertEqual(len(lines), 2)

        line1 = lines[0]
        self.assertEqual(line1.line_net, Decimal('500.00'))
        self.assertEqual(line1.line_tax, Decimal('95.00'))
        self.assertEqual(line1.line_gross, Decimal('595.00'))

        line2 = lines[1]
        self.assertEqual(line2.line_net, Decimal('200.00'))
        self.assertEqual(line2.line_tax, Decimal('38.00'))
        self.assertEqual(line2.line_gross, Decimal('238.00'))
