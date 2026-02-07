"""
Tests for the populate_documenttypes management command.
"""

from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from auftragsverwaltung.models import DocumentType


class PopulateDocumentTypesCommandTest(TestCase):
    """Tests for the populate_documenttypes management command."""
    
    def test_command_creates_document_types_with_correct_keys(self):
        """Test that the command creates DocumentTypes with English keys."""
        # Delete all existing document types first
        DocumentType.objects.all().delete()
        
        # Run the command
        out = StringIO()
        call_command('populate_documenttypes', stdout=out)
        
        # Verify all expected document types were created with correct keys
        expected_keys = ['quote', 'order', 'invoice', 'delivery', 'credit']
        
        for key in expected_keys:
            doc_type = DocumentType.objects.get(key=key)
            self.assertIsNotNone(doc_type)
            self.assertTrue(doc_type.is_active)
        
        # Verify the count
        self.assertEqual(DocumentType.objects.count(), 5)
        
        # Verify output contains success message
        output = out.getvalue()
        self.assertIn('Created: quote', output)
        self.assertIn('Summary: Created 5, Updated 0', output)
    
    def test_command_is_idempotent(self):
        """Test that running the command multiple times doesn't create duplicates."""
        # Run the command twice
        out1 = StringIO()
        call_command('populate_documenttypes', stdout=out1)
        
        out2 = StringIO()
        call_command('populate_documenttypes', stdout=out2)
        
        # Should still have exactly 5 document types
        self.assertEqual(DocumentType.objects.count(), 5)
        
        # Second run should show updates, not creations
        output2 = out2.getvalue()
        self.assertIn('Updated:', output2)
        self.assertIn('Summary: Created 0, Updated 5', output2)
    
    def test_command_updates_existing_document_types(self):
        """Test that the command updates existing DocumentTypes."""
        # Get the existing document type (created by migration)
        doc_type = DocumentType.objects.get(key='quote')
        
        # Modify it to have old values
        doc_type.name = 'Old Name'
        doc_type.prefix = 'OLD'
        doc_type.is_active = False
        doc_type.save()
        
        # Run the command
        out = StringIO()
        call_command('populate_documenttypes', stdout=out)
        
        # Verify the document type was updated
        doc_type.refresh_from_db()
        self.assertEqual(doc_type.name, 'Angebot')
        self.assertEqual(doc_type.prefix, 'AN')
        self.assertTrue(doc_type.is_active)
        
        # Verify output
        output = out.getvalue()
        self.assertIn('Updated: quote', output)
    
    def test_document_type_keys_match_url_expectations(self):
        """Test that DocumentType keys match what URLs expect."""
        # Run the command
        call_command('populate_documenttypes', stdout=StringIO())
        
        # These are the keys used in urls.py convenience URLs
        expected_keys_from_urls = {
            'quote': 'Angebot',      # /angebote/ -> doc_key='quote'
            'order': 'Auftragsbestätigung',  # /auftraege/ -> doc_key='order'
            'invoice': 'Rechnung',   # /rechnungen/ -> doc_key='invoice'
            'delivery': 'Lieferschein',  # /lieferscheine/ -> doc_key='delivery'
            'credit': 'Gutschrift',  # /gutschriften/ -> doc_key='credit'
        }
        
        for key, expected_name in expected_keys_from_urls.items():
            doc_type = DocumentType.objects.get(key=key)
            self.assertEqual(doc_type.name, expected_name)
            self.assertTrue(doc_type.is_active)
    
    def test_invoice_document_type_has_correct_flags(self):
        """Test that invoice DocumentType has correct business logic flags."""
        call_command('populate_documenttypes', stdout=StringIO())
        
        invoice = DocumentType.objects.get(key='invoice')
        self.assertTrue(invoice.is_invoice)
        self.assertFalse(invoice.is_correction)
        self.assertTrue(invoice.requires_due_date)
    
    def test_credit_document_type_has_correct_flags(self):
        """Test that credit DocumentType has correct business logic flags."""
        call_command('populate_documenttypes', stdout=StringIO())
        
        credit = DocumentType.objects.get(key='credit')
        self.assertFalse(credit.is_invoice)
        self.assertTrue(credit.is_correction)
