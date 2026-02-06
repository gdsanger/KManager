"""
Tests for DocumentCalculationService

Tests the calculation service for sales documents, ensuring:
- Deterministic calculation
- Correct handling of line types (NORMAL, OPTIONAL, ALTERNATIVE)
- Proper decimal rounding (HALF_UP, 2 decimal places)
- Correct multi-tax-rate handling
- Reproducibility
"""
from django.test import TestCase
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import (
    DocumentType,
    SalesDocument,
    SalesDocumentLine
)
from auftragsverwaltung.services import DocumentCalculationService, TotalsResult
from core.models import Mandant, TaxRate


class DocumentCalculationServiceTestCase(TestCase):
    """Test DocumentCalculationService"""
    
    def setUp(self):
        """Set up test data"""
        # Create company (Mandant)
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        
        # Create document type
        self.doc_type = DocumentType.objects.create(
            key="invoice",
            name="Invoice",
            prefix="INV",
            is_invoice=True,
            is_active=True
        )
        
        # Create tax rates
        self.tax_rate_19 = TaxRate.objects.create(
            code="VAT_19",
            name="19% VAT",
            rate=Decimal('0.19'),
            is_active=True
        )
        
        self.tax_rate_7 = TaxRate.objects.create(
            code="VAT_7",
            name="7% VAT",
            rate=Decimal('0.07'),
            is_active=True
        )
        
        # Create a sales document
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            number="INV-001",
            status="DRAFT",
            issue_date=date(2026, 1, 15)
        )
    
    def test_only_normal_lines_same_tax_rate(self):
        """Test calculation with only NORMAL lines and same tax rate"""
        # Create two NORMAL lines
        line1 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Item 1",
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19
        )
        
        line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            description="Item 2",
            quantity=Decimal('3.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Calculate totals
        result = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # Expected values:
        # Line 1: net=200.00, tax=38.00, gross=238.00
        # Line 2: net=150.00, tax=28.50, gross=178.50
        # Total: net=350.00, tax=66.50, gross=416.50
        
        self.assertEqual(result.total_net, Decimal('350.00'))
        self.assertEqual(result.total_tax, Decimal('66.50'))
        self.assertEqual(result.total_gross, Decimal('416.50'))
        
        # Check that document fields are updated (in-memory)
        self.assertEqual(self.document.total_net, Decimal('350.00'))
        self.assertEqual(self.document.total_tax, Decimal('66.50'))
        self.assertEqual(self.document.total_gross, Decimal('416.50'))
    
    def test_mixed_line_types(self):
        """Test calculation with mixed line types (NORMAL, OPTIONAL, ALTERNATIVE)"""
        # Create NORMAL line (always included)
        line1 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Normal Item",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Create OPTIONAL line (selected, should be included)
        line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='OPTIONAL',
            is_selected=True,
            description="Optional Item (selected)",
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Create OPTIONAL line (not selected, should NOT be included)
        line3 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=3,
            line_type='OPTIONAL',
            is_selected=False,
            description="Optional Item (not selected)",
            quantity=Decimal('5.0000'),
            unit_price_net=Decimal('200.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Create ALTERNATIVE line (selected, should be included)
        line4 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=4,
            line_type='ALTERNATIVE',
            is_selected=True,
            description="Alternative Item (selected)",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('75.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Create ALTERNATIVE line (not selected, should NOT be included)
        line5 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=5,
            line_type='ALTERNATIVE',
            is_selected=False,
            description="Alternative Item (not selected)",
            quantity=Decimal('10.0000'),
            unit_price_net=Decimal('300.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Calculate totals
        result = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # Expected values (only line1, line2, line4):
        # Line 1: net=100.00, tax=19.00, gross=119.00
        # Line 2: net=100.00, tax=19.00, gross=119.00
        # Line 4: net=75.00, tax=14.25, gross=89.25
        # Total: net=275.00, tax=52.25, gross=327.25
        
        self.assertEqual(result.total_net, Decimal('275.00'))
        self.assertEqual(result.total_tax, Decimal('52.25'))
        self.assertEqual(result.total_gross, Decimal('327.25'))
    
    def test_multiple_tax_rates(self):
        """Test calculation with multiple tax rates in same document"""
        # Line with 19% tax
        line1 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Item with 19% VAT",
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Line with 7% tax
        line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            description="Item with 7% VAT",
            quantity=Decimal('3.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate_7
        )
        
        # Calculate totals
        result = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # Expected values:
        # Line 1: net=200.00, tax=38.00 (200*0.19), gross=238.00
        # Line 2: net=150.00, tax=10.50 (150*0.07), gross=160.50
        # Total: net=350.00, tax=48.50, gross=398.50
        
        self.assertEqual(result.total_net, Decimal('350.00'))
        self.assertEqual(result.total_tax, Decimal('48.50'))
        self.assertEqual(result.total_gross, Decimal('398.50'))
    
    def test_reproducibility(self):
        """Test that service produces same results for same inputs"""
        # Create a line
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Item",
            quantity=Decimal('2.5000'),
            unit_price_net=Decimal('99.99'),
            tax_rate=self.tax_rate_19
        )
        
        # Calculate twice
        result1 = DocumentCalculationService.recalculate(self.document, persist=False)
        result2 = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # Results should be identical
        self.assertEqual(result1.total_net, result2.total_net)
        self.assertEqual(result1.total_tax, result2.total_tax)
        self.assertEqual(result1.total_gross, result2.total_gross)
        
        # Expected values:
        # net = 2.5 * 99.99 = 249.975 -> round(HALF_UP) = 249.98
        # tax = 249.98 * 0.19 = 47.4962 -> round(HALF_UP) = 47.50
        # gross = 249.98 + 47.50 = 297.48
        
        self.assertEqual(result1.total_net, Decimal('249.98'))
        self.assertEqual(result1.total_tax, Decimal('47.50'))
        self.assertEqual(result1.total_gross, Decimal('297.48'))
    
    def test_rounding_half_up(self):
        """Test that HALF_UP rounding is applied correctly"""
        # Create a line that requires rounding
        # Use 3 * 33.33 = 99.99, then tax calculation will need rounding
        # Or use a quantity that results in rounding: 2.5 * 10.01 = 25.025 -> 25.03 (HALF_UP)
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Rounding Test",
            quantity=Decimal('2.5000'),
            unit_price_net=Decimal('10.01'),
            tax_rate=self.tax_rate_19
        )
        
        # Calculate totals
        result = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # Expected values with HALF_UP rounding:
        # net = 2.5 * 10.01 = 25.025 -> round(HALF_UP) = 25.03 (0.005 rounds up)
        # tax = 25.03 * 0.19 = 4.7557 -> round(HALF_UP) = 4.76
        # gross = 25.03 + 4.76 = 29.79
        
        self.assertEqual(result.total_net, Decimal('25.03'))
        self.assertEqual(result.total_tax, Decimal('4.76'))
        self.assertEqual(result.total_gross, Decimal('29.79'))
    
    def test_persist_true(self):
        """Test that persist=True saves totals to database"""
        # Create a line
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Item",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Calculate with persist=True
        result = DocumentCalculationService.recalculate(self.document, persist=True)
        
        # Reload document from database
        self.document.refresh_from_db()
        
        # Check that values are persisted
        self.assertEqual(self.document.total_net, Decimal('100.00'))
        self.assertEqual(self.document.total_tax, Decimal('19.00'))
        self.assertEqual(self.document.total_gross, Decimal('119.00'))
    
    def test_persist_false_does_not_save(self):
        """Test that persist=False does not save totals to database"""
        # Create a line
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Item",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Store initial values
        initial_net = self.document.total_net
        initial_tax = self.document.total_tax
        initial_gross = self.document.total_gross
        
        # Calculate with persist=False (default)
        result = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # Reload document from database
        self.document.refresh_from_db()
        
        # Check that values are NOT persisted to DB
        self.assertEqual(self.document.total_net, initial_net)
        self.assertEqual(self.document.total_tax, initial_tax)
        self.assertEqual(self.document.total_gross, initial_gross)
    
    def test_empty_document(self):
        """Test calculation with no lines"""
        # Calculate totals for empty document
        result = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # All totals should be zero
        self.assertEqual(result.total_net, Decimal('0.00'))
        self.assertEqual(result.total_tax, Decimal('0.00'))
        self.assertEqual(result.total_gross, Decimal('0.00'))
    
    def test_normal_line_always_included_regardless_of_is_selected(self):
        """Test that NORMAL lines are included even if is_selected=False"""
        # Create NORMAL line with is_selected=False
        # Note: Model.clean() auto-corrects this, but we test the service logic
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=False,  # Should still be included!
            description="Normal Item",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19
        )
        
        # Force is_selected to False (bypassing model validation for this test)
        SalesDocumentLine.objects.filter(pk=line.pk).update(is_selected=False)
        line.refresh_from_db()
        
        # Calculate totals
        result = DocumentCalculationService.recalculate(self.document, persist=False)
        
        # Line should be included because it's NORMAL type
        self.assertEqual(result.total_net, Decimal('100.00'))
        self.assertEqual(result.total_tax, Decimal('19.00'))
        self.assertEqual(result.total_gross, Decimal('119.00'))
    
    def test_totals_result_dataclass(self):
        """Test that TotalsResult dataclass works correctly"""
        # Create result manually
        result = TotalsResult(
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00')
        )
        
        # Check attributes
        self.assertEqual(result.total_net, Decimal('100.00'))
        self.assertEqual(result.total_tax, Decimal('19.00'))
        self.assertEqual(result.total_gross, Decimal('119.00'))
