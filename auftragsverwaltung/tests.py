"""
Tests for DocumentType model
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from auftragsverwaltung.models import DocumentType


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
