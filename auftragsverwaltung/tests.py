"""
Tests for auftragsverwaltung models
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import DocumentType, NumberRange, SalesDocument
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
        doctype = DocumentType.objects.create(
            key="invoice",
            name="Invoice",
            prefix="INV"
        )
        
        expected = "invoice: Invoice (INV)"
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
        # Create first document type
        DocumentType.objects.create(
            key="invoice",
            name="Invoice",
            prefix="INV"
        )
        
        # Try to create another with different case
        doctype = DocumentType(
            key="INVOICE",
            name="Another Invoice",
            prefix="INV2"
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
        
        # Create DocumentTypes
        self.doctype_invoice = DocumentType.objects.create(
            key="invoice",
            name="Rechnung",
            prefix="R",
            is_invoice=True,
            requires_due_date=True,
            is_active=True
        )
        
        self.doctype_correction = DocumentType.objects.create(
            key="correction",
            name="Korrektur",
            prefix="K",
            is_correction=True,
            is_active=True
        )
        
        self.doctype_quote = DocumentType.objects.create(
            key="quote",
            name="Angebot",
            prefix="A",
            is_active=True
        )
        
        # Create PaymentTerm
        self.payment_term = PaymentTerm.objects.create(
            company=self.company,
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
        
        expected = f"R{doc.number} ({self.company.name})"
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
