"""
Tests for DocumentCalculationService admin actions
"""
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from decimal import Decimal
from datetime import date

from auftragsverwaltung.models import (
    DocumentType,
    SalesDocument,
    SalesDocumentLine
)
from auftragsverwaltung.admin import SalesDocumentAdmin
from core.models import Mandant, TaxRate


class DocumentCalculationAdminTestCase(TestCase):
    """Test admin actions for DocumentCalculationService"""
    
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
        
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code="VAT_19",
            name="19% VAT",
            rate=Decimal('0.19'),
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
        
        # Create a line
        self.line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Item",
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate
        )
        
        # Set up admin
        self.site = AdminSite()
        self.admin = SalesDocumentAdmin(SalesDocument, self.site)
        
        # Set up request factory
        self.factory = RequestFactory()
    
    def test_recalculate_totals_action_exists(self):
        """Test that recalculate_totals action is registered"""
        self.assertIn('recalculate_totals', self.admin.actions)
    
    def test_recalculate_totals_action(self):
        """Test that recalculate_totals action works correctly"""
        # Create request
        request = self.factory.get('/admin/auftragsverwaltung/salesdocument/')
        
        # Add messages middleware (required for admin actions)
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Create queryset with our document
        queryset = SalesDocument.objects.filter(pk=self.document.pk)
        
        # Execute action
        self.admin.recalculate_totals(request, queryset)
        
        # Reload document from database
        self.document.refresh_from_db()
        
        # Check that totals are calculated and persisted
        # Expected: net=200.00, tax=38.00, gross=238.00
        self.assertEqual(self.document.total_net, Decimal('200.00'))
        self.assertEqual(self.document.total_tax, Decimal('38.00'))
        self.assertEqual(self.document.total_gross, Decimal('238.00'))
    
    def test_recalculate_totals_action_multiple_documents(self):
        """Test that recalculate_totals action works with multiple documents"""
        # Create another document
        document2 = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            number="INV-002",
            status="DRAFT",
            issue_date=date(2026, 1, 16)
        )
        
        # Create a line for document2
        SalesDocumentLine.objects.create(
            document=document2,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            description="Test Item 2",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate
        )
        
        # Create request
        request = self.factory.get('/admin/auftragsverwaltung/salesdocument/')
        
        # Add messages middleware
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Create queryset with both documents
        queryset = SalesDocument.objects.filter(pk__in=[self.document.pk, document2.pk])
        
        # Execute action
        self.admin.recalculate_totals(request, queryset)
        
        # Reload documents from database
        self.document.refresh_from_db()
        document2.refresh_from_db()
        
        # Check that totals are calculated for both documents
        self.assertEqual(self.document.total_net, Decimal('200.00'))
        self.assertEqual(self.document.total_tax, Decimal('38.00'))
        self.assertEqual(self.document.total_gross, Decimal('238.00'))
        
        self.assertEqual(document2.total_net, Decimal('50.00'))
        self.assertEqual(document2.total_tax, Decimal('9.50'))
        self.assertEqual(document2.total_gross, Decimal('59.50'))
