from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

from core.models import Mandant, Adresse
from auftragsverwaltung.models import SalesDocument, DocumentType
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry


class CompanyAccountingSettingsTest(TestCase):
    """Test CompanyAccountingSettings model"""
    
    def setUp(self):
        """Create test data"""
        self.mandant = Mandant.objects.create(
            name="Test Mandant GmbH",
            adresse="Teststraße 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland"
        )
    
    def test_create_accounting_settings(self):
        """Test creating accounting settings for a company"""
        settings = CompanyAccountingSettings.objects.create(
            company=self.mandant,
            datev_consultant_number="12345",
            datev_client_number="67890",
            tax_number="123/456/78901",
            revenue_account_0="8000",
            revenue_account_7="8100",
            revenue_account_19="8400"
        )
        
        self.assertEqual(settings.company, self.mandant)
        self.assertEqual(settings.datev_consultant_number, "12345")
        self.assertEqual(settings.revenue_account_7, "8100")
    
    def test_one_to_one_relationship(self):
        """Test that only one settings instance per company is allowed"""
        CompanyAccountingSettings.objects.create(
            company=self.mandant,
            datev_consultant_number="12345"
        )
        
        # Try to create a second settings for the same company
        with self.assertRaises(Exception):
            CompanyAccountingSettings.objects.create(
                company=self.mandant,
                datev_consultant_number="99999"
            )
    
    def test_access_via_company(self):
        """Test accessing settings via company's related name"""
        settings = CompanyAccountingSettings.objects.create(
            company=self.mandant,
            revenue_account_19="8400"
        )
        
        # Access via company
        company_settings = self.mandant.accounting_settings
        self.assertEqual(company_settings, settings)
        self.assertEqual(company_settings.revenue_account_19, "8400")


class OutgoingInvoiceJournalEntryTest(TestCase):
    """Test OutgoingInvoiceJournalEntry model"""
    
    def setUp(self):
        """Create test data"""
        # Create Mandant
        self.mandant = Mandant.objects.create(
            name="Test Mandant GmbH",
            adresse="Teststraße 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland"
        )
        
        # Create Accounting Settings
        self.settings = CompanyAccountingSettings.objects.create(
            company=self.mandant,
            revenue_account_0="8000",
            revenue_account_7="8100",
            revenue_account_19="8400"
        )
        
        # Create Customer
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name="Test Kunde",
            strasse="Kundenstraße 1",
            plz="54321",
            ort="Kundenstadt",
            land="Deutschland",
            debitor_number="10001"
        )
        
        # Create DocumentType
        self.doc_type = DocumentType.objects.create(
            key="rechnung",
            name="Rechnung",
            prefix="R",
            is_invoice=True
        )
        
        # Create SalesDocument
        self.document = SalesDocument.objects.create(
            company=self.mandant,
            document_type=self.doc_type,
            customer=self.customer,
            number="R26-00001",
            status="OPEN",
            issue_date=date(2026, 2, 6)
        )
    
    def test_create_journal_entry(self):
        """Test creating a journal entry"""
        entry = OutgoingInvoiceJournalEntry.objects.create(
            company=self.mandant,
            document=self.document,
            document_number="R26-00001",
            document_date=date(2026, 2, 6),
            document_kind='INVOICE',
            customer_name="Test Kunde",
            debtor_number="10001",
            net_0=Decimal('0.00'),
            net_7=Decimal('100.00'),
            net_19=Decimal('200.00'),
            tax_amount=Decimal('45.00'),
            gross_amount=Decimal('345.00'),
            revenue_account_0=self.settings.revenue_account_0,
            revenue_account_7=self.settings.revenue_account_7,
            revenue_account_19=self.settings.revenue_account_19
        )
        
        self.assertEqual(entry.company, self.mandant)
        self.assertEqual(entry.document, self.document)
        self.assertEqual(entry.document_number, "R26-00001")
        self.assertEqual(entry.document_kind, 'INVOICE')
        self.assertEqual(entry.gross_amount, Decimal('345.00'))
        self.assertEqual(entry.export_status, 'OPEN')
    
    def test_unique_constraint_company_document(self):
        """Test unique constraint on (company, document)"""
        # Create first entry
        OutgoingInvoiceJournalEntry.objects.create(
            company=self.mandant,
            document=self.document,
            document_number="R26-00001",
            document_date=date(2026, 2, 6),
            document_kind='INVOICE',
            customer_name="Test Kunde",
            gross_amount=Decimal('100.00')
        )
        
        # Try to create second entry for same company+document
        with self.assertRaises(Exception):
            OutgoingInvoiceJournalEntry.objects.create(
                company=self.mandant,
                document=self.document,
                document_number="R26-00001",
                document_date=date(2026, 2, 6),
                document_kind='INVOICE',
                customer_name="Test Kunde",
                gross_amount=Decimal('100.00')
            )
    
    def test_validation_gross_amount(self):
        """Test validation of gross amount calculation"""
        entry = OutgoingInvoiceJournalEntry(
            company=self.mandant,
            document=self.document,
            document_number="R26-00001",
            document_date=date(2026, 2, 6),
            document_kind='INVOICE',
            customer_name="Test Kunde",
            net_0=Decimal('0.00'),
            net_7=Decimal('100.00'),
            net_19=Decimal('200.00'),
            tax_amount=Decimal('45.00'),
            gross_amount=Decimal('999.99')  # Wrong!
        )
        
        # Should raise ValidationError
        with self.assertRaises(ValidationError):
            entry.clean()
    
    def test_validation_gross_amount_correct(self):
        """Test that correct gross amount passes validation"""
        entry = OutgoingInvoiceJournalEntry(
            company=self.mandant,
            document=self.document,
            document_number="R26-00001",
            document_date=date(2026, 2, 6),
            document_kind='INVOICE',
            customer_name="Test Kunde",
            net_0=Decimal('0.00'),
            net_7=Decimal('100.00'),
            net_19=Decimal('200.00'),
            tax_amount=Decimal('45.00'),
            gross_amount=Decimal('345.00')  # Correct: 300 + 45
        )
        
        # Should not raise ValidationError
        try:
            entry.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly!")
    
    def test_snapshot_principle(self):
        """Test that journal entry is snapshot-based"""
        # Create entry with snapshot of settings
        entry = OutgoingInvoiceJournalEntry.objects.create(
            company=self.mandant,
            document=self.document,
            document_number="R26-00001",
            document_date=date(2026, 2, 6),
            document_kind='INVOICE',
            customer_name="Test Kunde",
            gross_amount=Decimal('100.00'),
            revenue_account_7="8100"  # Original value
        )
        
        # Change settings
        self.settings.revenue_account_7 = "9999"
        self.settings.save()
        
        # Entry should still have old value (snapshot)
        entry.refresh_from_db()
        self.assertEqual(entry.revenue_account_7, "8100")
        self.assertNotEqual(entry.revenue_account_7, self.settings.revenue_account_7)
    
    def test_export_tracking_fields(self):
        """Test export tracking functionality"""
        from django.utils import timezone
        
        entry = OutgoingInvoiceJournalEntry.objects.create(
            company=self.mandant,
            document=self.document,
            document_number="R26-00001",
            document_date=date(2026, 2, 6),
            document_kind='INVOICE',
            customer_name="Test Kunde",
            gross_amount=Decimal('100.00'),
            export_status='OPEN'
        )
        
        # Initially OPEN, no export time
        self.assertEqual(entry.export_status, 'OPEN')
        self.assertIsNone(entry.exported_at)
        
        # Mark as exported
        entry.export_status = 'EXPORTED'
        entry.exported_at = timezone.now()
        entry.export_batch_id = 'BATCH-2026-02-06-001'
        entry.save()
        
        entry.refresh_from_db()
        self.assertEqual(entry.export_status, 'EXPORTED')
        self.assertIsNotNone(entry.exported_at)
        self.assertEqual(entry.export_batch_id, 'BATCH-2026-02-06-001')
