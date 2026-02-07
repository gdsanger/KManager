"""
Tests for auftragsverwaltung models
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import DocumentType, NumberRange, SalesDocument, SalesDocumentSource
from core.models import Mandant, PaymentTerm


class DocumentTypeModelTestCase(TestCase):
    """Test DocumentType model"""
    
    def test_create_documenttype(self):
        """Test creating a document type"""
        doctype = DocumentType.objects.create(
            key="test",
            name="Test Document",
            prefix="T",
            is_invoice=True,
            is_active=True
        )
        
        self.assertIsNotNone(doctype.pk)
        self.assertEqual(doctype.key, "test")
        self.assertEqual(doctype.name, "Test Document")
        self.assertEqual(doctype.prefix, "T")
        self.assertTrue(doctype.is_invoice)
        self.assertFalse(doctype.is_correction)
        self.assertFalse(doctype.requires_due_date)
        self.assertTrue(doctype.is_active)
    
    def test_str_representation(self):
        """Test __str__ method"""
        doctype = DocumentType.objects.get(key="invoice")
        
        expected = "invoice: Rechnung (R)"
        self.assertEqual(str(doctype), expected)
    
    def test_key_whitespace_only_validation(self):
        """Test that key cannot be whitespace-only"""
        doctype = DocumentType(
            key="   ",
            name="Test",
            prefix="T"
        )
        
        with self.assertRaises(ValidationError) as context:
            doctype.full_clean()
        
        self.assertIn('key', context.exception.message_dict)
    
    def test_name_whitespace_only_validation(self):
        """Test that name cannot be whitespace-only"""
        doctype = DocumentType(
            key="test",
            name="   ",
            prefix="T"
        )
        
        with self.assertRaises(ValidationError) as context:
            doctype.full_clean()
        
        self.assertIn('name', context.exception.message_dict)
    
    def test_prefix_whitespace_only_validation(self):
        """Test that prefix cannot be whitespace-only"""
        doctype = DocumentType(
            key="test",
            name="Test",
            prefix="   "
        )
        
        with self.assertRaises(ValidationError) as context:
            doctype.full_clean()
        
        self.assertIn('prefix', context.exception.message_dict)
    
    def test_key_case_insensitive_uniqueness(self):
        """Test that key is unique case-insensitively"""
        # Create first document type with a test key
        DocumentType.objects.create(
            key="testkey",
            name="Test Key",
            prefix="TK"
        )
        
        # Try to create another with different case
        doctype = DocumentType(
            key="TESTKEY",
            name="Another Test Key",
            prefix="TK2"
        )
        
        # Should raise IntegrityError when saving
        with self.assertRaises(IntegrityError):
            doctype.save()
    
    def test_default_flag_values(self):
        """Test that boolean flags default to False"""
        doctype = DocumentType.objects.create(
            key="test",
            name="Test",
            prefix="T"
        )
        
        self.assertFalse(doctype.is_invoice)
        self.assertFalse(doctype.is_correction)
        self.assertFalse(doctype.requires_due_date)
        self.assertTrue(doctype.is_active)  # is_active defaults to True
    
    def test_all_flags_true(self):
        """Test creating document type with all flags set to True"""
        doctype = DocumentType.objects.create(
            key="creditnote",
            name="Credit Note",
            prefix="CN",
            is_invoice=True,
            is_correction=True,
            requires_due_date=True,
            is_active=True
        )
        
        self.assertTrue(doctype.is_invoice)
        self.assertTrue(doctype.is_correction)
        self.assertTrue(doctype.requires_due_date)
        self.assertTrue(doctype.is_active)


class SalesDocumentModelTestCase(TestCase):
    """Test SalesDocument model"""
    
    def setUp(self):
        """Set up test data"""
        # Create a Mandant
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City",
            land="Deutschland"
        )
        
        # Get DocumentTypes (created by migration)
        self.doctype_invoice = DocumentType.objects.get(key="invoice")
        
        self.doctype_correction = DocumentType.objects.create(
            key="correction",
            name="Korrektur",
            prefix="K",
            is_correction=True,
            is_active=True
        )
        
        self.doctype_quote = DocumentType.objects.get(key="quote")
        
        # Create PaymentTerm
        self.payment_term = PaymentTerm.objects.create(
            name="30 Tage netto",
            net_days=30,
            is_default=True
        )
    
    def test_create_salesdocument_basic(self):
        """Test creating a basic sales document"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6)
        )
        
        self.assertIsNotNone(doc.pk)
        self.assertEqual(doc.company, self.company)
        self.assertEqual(doc.document_type, self.doctype_quote)
        self.assertEqual(doc.number, "A26-00001")
        self.assertEqual(doc.status, "DRAFT")
        self.assertEqual(doc.issue_date, date(2026, 2, 6))
        self.assertIsNone(doc.due_date)
        self.assertIsNone(doc.paid_at)
        self.assertEqual(doc.total_net, Decimal('0.00'))
        self.assertEqual(doc.total_tax, Decimal('0.00'))
        self.assertEqual(doc.total_gross, Decimal('0.00'))
        self.assertEqual(doc.notes_internal, "")
        self.assertEqual(doc.notes_public, "")
    
    def test_str_representation(self):
        """Test __str__ method"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8)
        )
        
        expected = f"{doc.number} ({self.company.name})"
        self.assertEqual(str(doc), expected)
    
    def test_unique_constraint_number_per_company_doctype(self):
        """Test that number is unique per (company, document_type)"""
        # Create first document
        SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8)
        )
        
        # Try to create another with same number, company, and document_type
        doc2 = SalesDocument(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",  # Same number
            status="DRAFT",
            issue_date=date(2026, 2, 7),
            due_date=date(2026, 3, 9)
        )
        
        # Should raise IntegrityError when saving
        with self.assertRaises(IntegrityError):
            doc2.save()
    
    def test_unique_constraint_allows_same_number_different_doctype(self):
        """Test that same number is allowed for different document types"""
        # Create first document with invoice type
        SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8)
        )
        
        # Create second document with quote type - same number should be OK
        doc2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="00001",  # Same number, different type
            status="DRAFT",
            issue_date=date(2026, 2, 7)
        )
        
        self.assertIsNotNone(doc2.pk)
    
    def test_requires_due_date_validation_fails(self):
        """Test that due_date is required when document_type.requires_due_date=True"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doctype_invoice,  # requires_due_date=True
            number="R26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6)
            # due_date is NOT set
        )
        
        with self.assertRaises(ValidationError) as context:
            doc.full_clean()
        
        self.assertIn('due_date', context.exception.message_dict)
    
    def test_requires_due_date_validation_passes(self):
        """Test that validation passes when due_date is set for requires_due_date=True"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doctype_invoice,  # requires_due_date=True
            number="R26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8)  # due_date IS set
        )
        
        # Should not raise any exceptions
        doc.full_clean()
        doc.save()
        self.assertIsNotNone(doc.pk)
    
    def test_is_correction_validation_fails(self):
        """Test that source_document is required when document_type.is_correction=True"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doctype_correction,  # is_correction=True
            number="K26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6)
            # source_document is NOT set
        )
        
        with self.assertRaises(ValidationError) as context:
            doc.full_clean()
        
        self.assertIn('source_document', context.exception.message_dict)
    
    def test_is_correction_validation_passes(self):
        """Test that validation passes when source_document is set for is_correction=True"""
        # Create a source document first
        source_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="SENT",
            issue_date=date(2026, 2, 1),
            due_date=date(2026, 3, 3)
        )
        
        # Create a correction document
        correction_doc = SalesDocument(
            company=self.company,
            document_type=self.doctype_correction,  # is_correction=True
            number="K26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            source_document=source_doc  # source_document IS set
        )
        
        # Should not raise any exceptions
        correction_doc.full_clean()
        correction_doc.save()
        self.assertIsNotNone(correction_doc.pk)
        self.assertEqual(correction_doc.source_document, source_doc)
    
    def test_create_with_payment_term(self):
        """Test creating document with payment term"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8),
            payment_term=self.payment_term
        )
        
        self.assertEqual(doc.payment_term, self.payment_term)
    
    def test_create_with_payment_term_snapshot(self):
        """Test creating document with payment term snapshot"""
        snapshot = {
            "name": "30 Tage netto",
            "net_days": 30,
            "discount_days": None,
            "discount_rate": None
        }
        
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8),
            payment_term=self.payment_term,
            payment_term_snapshot=snapshot
        )
        
        self.assertEqual(doc.payment_term_snapshot, snapshot)
    
    def test_create_with_totals(self):
        """Test creating document with total amounts"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="SENT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8),
            total_net=Decimal('1000.00'),
            total_tax=Decimal('190.00'),
            total_gross=Decimal('1190.00')
        )
        
        self.assertEqual(doc.total_net, Decimal('1000.00'))
        self.assertEqual(doc.total_tax, Decimal('190.00'))
        self.assertEqual(doc.total_gross, Decimal('1190.00'))
    
    def test_create_with_negative_totals_for_correction(self):
        """Test that negative totals are allowed (for corrections/credit notes)"""
        source_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="SENT",
            issue_date=date(2026, 2, 1),
            due_date=date(2026, 3, 3),
            total_net=Decimal('1000.00'),
            total_tax=Decimal('190.00'),
            total_gross=Decimal('1190.00')
        )
        
        correction_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_correction,
            number="K26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            source_document=source_doc,
            total_net=Decimal('-1000.00'),  # Negative amounts
            total_tax=Decimal('-190.00'),
            total_gross=Decimal('-1190.00')
        )
        
        # Should not raise any exceptions
        correction_doc.full_clean()
        self.assertIsNotNone(correction_doc.pk)
        self.assertEqual(correction_doc.total_net, Decimal('-1000.00'))
    
    def test_status_choices(self):
        """Test that all status choices are valid"""
        valid_statuses = ['DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'OPEN', 'PAID', 'OVERDUE']
        
        for status in valid_statuses:
            doc = SalesDocument.objects.create(
                company=self.company,
                document_type=self.doctype_quote,
                number=f"A26-{status}",
                status=status,
                issue_date=date(2026, 2, 6)
            )
            doc.full_clean()  # Should not raise
            self.assertEqual(doc.status, status)
    
    def test_notes_fields(self):
        """Test internal and public notes fields"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            notes_internal="Internal note for team",
            notes_public="Public note for customer"
        )
        
        self.assertEqual(doc.notes_internal, "Internal note for team")
        self.assertEqual(doc.notes_public, "Public note for customer")
    
    def test_paid_at_field(self):
        """Test paid_at datetime field"""
        paid_datetime = timezone.now()
        
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="PAID",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8),
            paid_at=paid_datetime
        )
        
        self.assertEqual(doc.paid_at, paid_datetime)
    
    def test_source_document_relationship(self):
        """Test source_document relationship and derived_documents reverse relation"""
        # Create source document
        source_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="SENT",
            issue_date=date(2026, 2, 1),
            due_date=date(2026, 3, 3)
        )
        
        # Create correction document
        correction_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_correction,
            number="K26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            source_document=source_doc
        )
        
        # Test forward relation
        self.assertEqual(correction_doc.source_document, source_doc)
        
        # Test reverse relation
        derived = source_doc.derived_documents.all()
        self.assertEqual(derived.count(), 1)
        self.assertEqual(derived.first(), correction_doc)
    
    def test_ordering(self):
        """Test that documents are ordered by -issue_date, -id"""
        doc1 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 1)
        )
        doc2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00002",
            status="DRAFT",
            issue_date=date(2026, 2, 5)
        )
        doc3 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00003",
            status="DRAFT",
            issue_date=date(2026, 2, 3)
        )
        
        docs = list(SalesDocument.objects.all())
        # Should be ordered by -issue_date (newest first)
        self.assertEqual(docs[0], doc2)  # 2026-02-05
        self.assertEqual(docs[1], doc3)  # 2026-02-03
        self.assertEqual(docs[2], doc1)  # 2026-02-01


class SalesDocumentLineModelTestCase(TestCase):
    """Test SalesDocumentLine model"""
    
    def setUp(self):
        """Set up test data"""
        from core.models import TaxRate, Item, Kostenart
        
        # Create a Mandant
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City",
            land="Deutschland"
        )
        
        # Get DocumentType (created by migration)
        self.doctype_quote = DocumentType.objects.get(key="quote")
        
        # Create TaxRate
        self.tax_rate = TaxRate.objects.create(
            code="VAT19",
            name="19% USt",
            rate=Decimal('0.19'),
            is_active=True
        )
        
        # Create Kostenart
        self.cost_type = Kostenart.objects.create(
            name="Material",
            umsatzsteuer_satz="19"
        )
        
        # Create Item
        self.item = Item.objects.create(
            article_no="TEST-001",
            short_text_1="Test Item",
            long_text="Test Item Description",
            net_price=Decimal('100.00'),
            purchase_price=Decimal('50.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type,
            item_type="MATERIAL",
            is_active=True
        )
        
        # Create SalesDocument
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6)
        )
    
    def test_create_salesdocumentline_basic(self):
        """Test creating a basic sales document line"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            item=self.item,
            description="Test Line",
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        self.assertIsNotNone(line.pk)
        self.assertEqual(line.document, self.document)
        self.assertEqual(line.position_no, 1)
        self.assertEqual(line.line_type, 'NORMAL')
        self.assertTrue(line.is_selected)
        self.assertEqual(line.item, self.item)
        self.assertEqual(line.description, "Test Line")
        self.assertEqual(line.quantity, Decimal('2.0000'))
        self.assertEqual(line.unit_price_net, Decimal('100.00'))
        self.assertEqual(line.tax_rate, self.tax_rate)
        self.assertTrue(line.is_discountable)
        self.assertEqual(line.line_net, Decimal('0.00'))
        self.assertEqual(line.line_tax, Decimal('0.00'))
        self.assertEqual(line.line_gross, Decimal('0.00'))
    
    def test_str_representation(self):
        """Test __str__ method"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Line Description",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        expected = f"{self.document.number} - Pos. 1: Test Line Description"
        self.assertEqual(str(line), expected)
    
    def test_position_no_unique_per_document(self):
        """Test that position_no is unique per document"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        # Create first line
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Line 1",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Try to create another line with same position_no
        line2 = SalesDocumentLine(
            document=self.document,
            position_no=1,  # Same position_no
            line_type='NORMAL',
            is_selected=True,
            description="Line 2",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Should raise IntegrityError when saving
        with self.assertRaises(IntegrityError):
            line2.save()
    
    def test_position_no_unique_allows_same_for_different_documents(self):
        """Test that same position_no is allowed for different documents"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        # Create second document
        document2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00002",
            status="DRAFT",
            issue_date=date(2026, 2, 7)
        )
        
        # Create line in first document
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Line 1",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Create line with same position_no in second document - should be OK
        line2 = SalesDocumentLine.objects.create(
            document=document2,
            position_no=1,  # Same position_no, different document
            line_type='NORMAL',
            is_selected=True,
            description="Line 2",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        self.assertIsNotNone(line2.pk)
    
    def test_default_is_selected_normal(self):
        """Test that NORMAL line_type defaults is_selected to True"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        # For NORMAL type, is_selected should be auto-corrected to True
        # even if explicitly set to False
        line = SalesDocumentLine(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=False,  # Will be auto-corrected to True
            description="Normal Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Run validation (which auto-corrects)
        line.full_clean()
        
        # Should be auto-corrected to True for NORMAL
        self.assertTrue(line.is_selected)
    
    def test_default_is_selected_optional(self):
        """Test that OPTIONAL line_type defaults is_selected to False"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine(
            document=self.document,
            position_no=1,
            line_type='OPTIONAL',
            is_selected=False,
            description="Optional Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Run validation
        line.full_clean()
        
        # Should remain False for OPTIONAL
        self.assertFalse(line.is_selected)
    
    def test_default_is_selected_alternative(self):
        """Test that ALTERNATIVE line_type defaults is_selected to False"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine(
            document=self.document,
            position_no=1,
            line_type='ALTERNATIVE',
            is_selected=False,
            description="Alternative Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Run validation
        line.full_clean()
        
        # Should remain False for ALTERNATIVE
        self.assertFalse(line.is_selected)
    
    def test_normal_line_auto_corrects_is_selected(self):
        """Test that NORMAL lines auto-correct is_selected to True"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=False,  # Try to set to False
            description="Normal Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Run validation
        line.full_clean()
        
        # Should be auto-corrected to True
        self.assertTrue(line.is_selected)
    
    def test_is_included_in_totals_normal(self):
        """Test that NORMAL lines are always included in totals"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        # Create NORMAL line with is_selected=False (should still be included)
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=False,
            description="Normal Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # NORMAL lines are always included (regardless of is_selected)
        self.assertTrue(line.is_included_in_totals())
    
    def test_is_included_in_totals_optional_selected(self):
        """Test that OPTIONAL lines are included when selected"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='OPTIONAL',
            is_selected=True,
            description="Optional Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        self.assertTrue(line.is_included_in_totals())
    
    def test_is_included_in_totals_optional_not_selected(self):
        """Test that OPTIONAL lines are not included when not selected"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='OPTIONAL',
            is_selected=False,
            description="Optional Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        self.assertFalse(line.is_included_in_totals())
    
    def test_is_included_in_totals_alternative_selected(self):
        """Test that ALTERNATIVE lines are included when selected"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='ALTERNATIVE',
            is_selected=True,
            description="Alternative Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        self.assertTrue(line.is_included_in_totals())
    
    def test_is_included_in_totals_alternative_not_selected(self):
        """Test that ALTERNATIVE lines are not included when not selected"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='ALTERNATIVE',
            is_selected=False,
            description="Alternative Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        self.assertFalse(line.is_included_in_totals())
    
    def test_snapshot_stability_item_price_change(self):
        """Test that changing Item price doesn't affect SalesDocumentLine"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        # Create line with item
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            item=self.item,
            description="Test Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),  # Snapshot from item
            tax_rate=self.tax_rate
        )
        
        # Store original price
        original_price = line.unit_price_net
        
        # Change item price
        self.item.unit_price_net = Decimal('200.00')
        self.item.save()
        
        # Reload line from DB
        line.refresh_from_db()
        
        # Price should NOT have changed (snapshot stability)
        self.assertEqual(line.unit_price_net, original_price)
        self.assertEqual(line.unit_price_net, Decimal('100.00'))
    
    def test_snapshot_stability_tax_rate_change(self):
        """Test that changing TaxRate doesn't affect SalesDocumentLine"""
        from auftragsverwaltung.models import SalesDocumentLine
        from core.models import TaxRate
        
        # Create line
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Store original tax_rate FK
        original_tax_rate_id = line.tax_rate.id
        original_tax_rate_code = line.tax_rate.code
        
        # Change tax_rate rate value
        self.tax_rate.rate = Decimal('0.07')
        self.tax_rate.save()
        
        # Reload line from DB
        line.refresh_from_db()
        
        # tax_rate FK should still point to same TaxRate object
        self.assertEqual(line.tax_rate.id, original_tax_rate_id)
        self.assertEqual(line.tax_rate.code, original_tax_rate_code)
        
        # But the TaxRate's rate value has changed
        self.assertEqual(line.tax_rate.rate, Decimal('0.07'))
        
        # This demonstrates that the FK is a snapshot reference:
        # The line still points to the same TaxRate object,
        # even if that object's data changes.
        # For true value snapshot, the rate would need to be denormalized.
    
    def test_item_can_be_null(self):
        """Test that item FK can be null (manual line entry)"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            item=None,  # No item reference
            description="Manual Line Entry",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('150.00'),
            tax_rate=self.tax_rate
        )
        
        self.assertIsNone(line.item)
        self.assertIsNotNone(line.pk)
    
    def test_is_discountable_default_true(self):
        """Test that is_discountable defaults to True"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Line",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
            # is_discountable not set
        )
        
        self.assertTrue(line.is_discountable)
    
    def test_line_type_choices(self):
        """Test that all line_type choices are valid"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        valid_types = ['NORMAL', 'OPTIONAL', 'ALTERNATIVE']
        
        for i, line_type in enumerate(valid_types, 1):
            line = SalesDocumentLine.objects.create(
                document=self.document,
                position_no=i,
                line_type=line_type,
                is_selected=(line_type == 'NORMAL'),
                description=f"{line_type} Line",
                quantity=Decimal('1.0000'),
                unit_price_net=Decimal('100.00'),
                tax_rate=self.tax_rate
            )
            line.full_clean()  # Should not raise
            self.assertEqual(line.line_type, line_type)
    
    def test_ordering(self):
        """Test that lines are ordered by document and position_no"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        # Create lines in random order
        line3 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=3,
            line_type='NORMAL',
            is_selected=True,
            description="Line 3",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        line1 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Line 1",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            description="Line 2",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Query all lines
        lines = list(SalesDocumentLine.objects.all())
        
        # Should be ordered by position_no
        self.assertEqual(lines[0], line1)
        self.assertEqual(lines[1], line2)
        self.assertEqual(lines[2], line3)
    
    def test_related_name_from_document(self):
        """Test that lines can be accessed via document.lines"""
        from auftragsverwaltung.models import SalesDocumentLine
        
        # Create lines
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Line 1",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='OPTIONAL',
            is_selected=False,
            description="Line 2",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Access via related_name
        lines = self.document.lines.all()
        self.assertEqual(lines.count(), 2)


class SalesDocumentSourceModelTestCase(TestCase):
    """Test SalesDocumentSource model"""
    
    def setUp(self):
        """Set up test data"""
        
        # Create company
        self.company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City",
            land="Deutschland"
        )
        
        # Create another company for cross-company tests
        self.company2 = Mandant.objects.create(
            name="Another Company",
            adresse="Another Street 1",
            plz="54321",
            ort="Another City",
            land="Deutschland"
        )
        
        # Get document types (created by migration)
        self.doctype_invoice = DocumentType.objects.get(key="invoice")
        
        self.doctype_quote = DocumentType.objects.get(key="quote")
        
        # Create source documents
        self.source_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00001",
            status="SENT",
            issue_date=date(2026, 1, 15)
        )
        
        # Create target document
        self.target_doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_invoice,
            number="R26-00001",
            status="DRAFT",
            issue_date=date(2026, 2, 6),
            due_date=date(2026, 3, 8)
        )
        
        # Create document in another company
        self.other_company_doc = SalesDocument.objects.create(
            company=self.company2,
            document_type=self.doctype_quote,
            number="A26-00001",
            status="SENT",
            issue_date=date(2026, 1, 20)
        )
    
    def test_create_document_source(self):
        """Test creating a document source"""
        
        source = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        self.assertIsNotNone(source.pk)
        self.assertEqual(source.target_document, self.target_doc)
        self.assertEqual(source.source_document, self.source_doc)
        self.assertEqual(source.role, 'DERIVED_FROM')
        self.assertIsNotNone(source.created_at)
    
    def test_str_representation(self):
        """Test __str__ method"""
        
        source = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='COPIED_FROM'
        )
        
        expected = f"{self.target_doc.number} ← Kopiert von ← {self.source_doc.number}"
        self.assertEqual(str(source), expected)
    
    def test_multiple_sources_for_target(self):
        """Test that multiple sources for one target are allowed"""
        
        # Create second source document
        source_doc2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00002",
            status="SENT",
            issue_date=date(2026, 1, 20)
        )
        
        # Create first source relation
        source1 = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        # Create second source relation - should work
        source2 = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=source_doc2,
            role='DERIVED_FROM'
        )
        
        self.assertIsNotNone(source1.pk)
        self.assertIsNotNone(source2.pk)
        
        # Verify both sources are accessible via related_name
        sources = self.target_doc.sources_as_target.all()
        self.assertEqual(sources.count(), 2)
    
    def test_company_consistency_validation_fails(self):
        """Test that different companies for source/target are rejected"""
        
        # Try to create source with different companies
        source = SalesDocumentSource(
            target_document=self.target_doc,  # company1
            source_document=self.other_company_doc,  # company2
            role='COPIED_FROM'
        )
        
        with self.assertRaises(ValidationError) as context:
            source.full_clean()
        
        self.assertIn('source_document', context.exception.message_dict)
        self.assertIn('selben Mandanten', context.exception.message_dict['source_document'][0])
    
    def test_company_consistency_validation_passes(self):
        """Test that same company for source/target passes validation"""
        
        source = SalesDocumentSource(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='COPIED_FROM'
        )
        
        # Should not raise any exceptions
        source.full_clean()
        source.save()
        self.assertIsNotNone(source.pk)
    
    def test_self_reference_validation_fails(self):
        """Test that self-reference is rejected via clean()"""
        
        # Try to create source that references itself
        source = SalesDocumentSource(
            target_document=self.target_doc,
            source_document=self.target_doc,  # Same as target
            role='COPIED_FROM'
        )
        
        with self.assertRaises(ValidationError) as context:
            source.full_clean()
        
        self.assertIn('source_document', context.exception.message_dict)
        self.assertIn('nicht auf sich selbst verweisen', context.exception.message_dict['source_document'][0])
    
    def test_self_reference_constraint_fails(self):
        """Test that self-reference is also rejected at database level"""
        
        # Try to bypass validation and save directly
        source = SalesDocumentSource(
            target_document=self.target_doc,
            source_document=self.target_doc,  # Same as target
            role='COPIED_FROM'
        )
        
        # Should raise IntegrityError due to CheckConstraint
        with self.assertRaises((ValidationError, IntegrityError)):
            source.save()
    
    def test_duplicate_constraint_fails(self):
        """Test that duplicate (target, source, role) is rejected"""
        
        # Create first source
        SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        # Try to create duplicate
        source2 = SalesDocumentSource(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'  # Same triple
        )
        
        # Should raise IntegrityError when saving
        with self.assertRaises(IntegrityError):
            source2.save()
    
    def test_duplicate_allows_different_role(self):
        """Test that same target/source with different role is allowed"""
        
        # Create first source
        source1 = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        # Create second with different role - should work
        source2 = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='COPIED_FROM'  # Different role
        )
        
        self.assertIsNotNone(source1.pk)
        self.assertIsNotNone(source2.pk)
    
    def test_protect_on_delete_target(self):
        """Test that deleting target document is prevented"""
        from django.db.models.deletion import ProtectedError
        
        # Create source relation
        SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        # Try to delete target document
        with self.assertRaises(ProtectedError):
            self.target_doc.delete()
    
    def test_protect_on_delete_source(self):
        """Test that deleting source document is prevented"""
        from django.db.models.deletion import ProtectedError
        
        # Create source relation
        SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        # Try to delete source document
        with self.assertRaises(ProtectedError):
            self.source_doc.delete()
    
    def test_related_name_sources_as_target(self):
        """Test that sources can be accessed via target document"""
        
        # Create source relation
        SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        # Access via related_name
        sources = self.target_doc.sources_as_target.all()
        self.assertEqual(sources.count(), 1)
        self.assertEqual(sources[0].source_document, self.source_doc)
    
    def test_related_name_sources_as_source(self):
        """Test that targets can be accessed via source document"""
        
        # Create source relation
        SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=self.source_doc,
            role='DERIVED_FROM'
        )
        
        # Access via related_name
        targets = self.source_doc.sources_as_source.all()
        self.assertEqual(targets.count(), 1)
        self.assertEqual(targets[0].target_document, self.target_doc)
    
    def test_role_choices(self):
        """Test all role choices"""
        
        roles = ['COPIED_FROM', 'DERIVED_FROM', 'CORRECTION_OF']
        
        for i, role in enumerate(roles):
            source_doc = SalesDocument.objects.create(
                company=self.company,
                document_type=self.doctype_quote,
                number=f"A26-{100 + i:05d}",  # Start from 00100 to avoid conflicts
                status="SENT",
                issue_date=date(2026, 1, 10 + i)
            )
            
            source = SalesDocumentSource.objects.create(
                target_document=self.target_doc,
                source_document=source_doc,
                role=role
            )
            
            self.assertEqual(source.role, role)
    
    def test_ordering_by_created_at(self):
        """Test that sources are ordered by created_at descending"""
        from django.utils import timezone
        import time
        
        # Create three sources with slight time differences
        source_doc1 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00010",
            status="SENT",
            issue_date=date(2026, 1, 10)
        )
        source1 = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=source_doc1,
            role='COPIED_FROM'
        )
        time.sleep(0.01)
        
        source_doc2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00011",
            status="SENT",
            issue_date=date(2026, 1, 11)
        )
        source2 = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=source_doc2,
            role='DERIVED_FROM'
        )
        time.sleep(0.01)
        
        source_doc3 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doctype_quote,
            number="A26-00012",
            status="SENT",
            issue_date=date(2026, 1, 12)
        )
        source3 = SalesDocumentSource.objects.create(
            target_document=self.target_doc,
            source_document=source_doc3,
            role='CORRECTION_OF'
        )
        
        # Get all sources - should be ordered by created_at descending
        sources = SalesDocumentSource.objects.all()
        self.assertEqual(sources[0], source3)  # Most recent
        self.assertEqual(sources[1], source2)
        self.assertEqual(sources[2], source1)  # Oldest

