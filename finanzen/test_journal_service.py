"""
Tests für den Rechnungsausgangsjournal-Service (finanzen.services.journal)
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase

from core.models import Mandant, Adresse, TaxRate
from auftragsverwaltung.models import SalesDocument, DocumentType, SalesDocumentLine
from auftragsverwaltung.services.document_calculation import DocumentCalculationService
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry
from finanzen.services.journal import (
    JournalEntryError,
    UnsupportedTaxRateError,
    create_journal_entry,
    get_document_kind,
)


class JournalServiceTestBase(TestCase):
    """Gemeinsame Testdaten für die Journal-Tests"""

    def setUp(self):
        self.company = Mandant.objects.create(
            name="Test Mandant GmbH",
            adresse="Teststraße 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland",
        )
        self.accounting_settings = CompanyAccountingSettings.objects.create(
            company=self.company,
            revenue_account_0="8000",
            revenue_account_7="8100",
            revenue_account_19="8400",
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            firma="Kunde GmbH",
            name="Max Mustermann",
            strasse="Kundenstraße 1",
            plz="54321",
            ort="Kundenstadt",
            land="Deutschland",
            debitor_number="10001",
        )
        self.doc_type_invoice = DocumentType.objects.get(key='invoice')
        self.doc_type_credit = DocumentType.objects.get(key='credit')
        self.doc_type_quote = DocumentType.objects.get(key='quote')

        self.tax_19 = TaxRate.objects.create(code='VAT19', name='19%', rate=Decimal('0.1900'))
        self.tax_7 = TaxRate.objects.create(code='VAT7', name='7%', rate=Decimal('0.0700'))
        self.tax_0 = TaxRate.objects.create(code='VAT0', name='0%', rate=Decimal('0.0000'))
        self.tax_16 = TaxRate.objects.create(code='VAT16', name='16%', rate=Decimal('0.1600'))

    def _create_document(self, document_type=None, number='R26-00001', **kwargs):
        defaults = {
            'company': self.company,
            'document_type': document_type or self.doc_type_invoice,
            'customer': self.customer,
            'number': number,
            'status': 'SENT',
            'issue_date': date(2026, 2, 6),
        }
        defaults.update(kwargs)
        return SalesDocument.objects.create(**defaults)

    def _add_line(self, document, tax_rate, quantity='1', unit_price_net='100.00',
                  line_type='NORMAL', is_selected=True, position_no=None):
        if position_no is None:
            position_no = document.lines.count() + 1
        return SalesDocumentLine.objects.create(
            document=document,
            position_no=position_no,
            line_type=line_type,
            is_selected=is_selected,
            tax_rate=tax_rate,
            quantity=Decimal(quantity),
            unit_price_net=Decimal(unit_price_net),
            description='Testposition',
        )

    def _recalculate(self, document):
        DocumentCalculationService.recalculate(document, persist=True)
        document.refresh_from_db()
        return document


class DocumentKindTest(JournalServiceTestBase):
    """Belegart-Ermittlung"""

    def test_invoice_kind(self):
        document = self._create_document()
        self.assertEqual(get_document_kind(document), 'INVOICE')

    def test_credit_note_kind(self):
        document = self._create_document(document_type=self.doc_type_credit, number='GS26-00001')
        self.assertEqual(get_document_kind(document), 'CREDIT_NOTE')

    def test_quote_is_not_journal_relevant(self):
        document = self._create_document(document_type=self.doc_type_quote, number='AN26-00001')
        self.assertIsNone(get_document_kind(document))

    def test_create_fails_for_quote(self):
        document = self._create_document(document_type=self.doc_type_quote, number='AN26-00001')
        with self.assertRaises(JournalEntryError):
            create_journal_entry(document)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)


class CreateJournalEntryTest(JournalServiceTestBase):
    """Erzeugung der Journaleinträge"""

    def test_creates_entry_with_snapshot_values(self):
        document = self._create_document()
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        document = self._recalculate(document)

        entry, created = create_journal_entry(document)

        self.assertTrue(created)
        self.assertEqual(entry.company, self.company)
        self.assertEqual(entry.document, document)
        self.assertEqual(entry.document_number, 'R26-00001')
        self.assertEqual(entry.document_date, date(2026, 2, 6))
        self.assertEqual(entry.document_kind, 'INVOICE')
        self.assertEqual(entry.customer_name, 'Kunde GmbH (Max Mustermann)')
        self.assertEqual(entry.debtor_number, '10001')
        self.assertEqual(entry.export_status, 'OPEN')
        self.assertIsNone(entry.exported_at)

    def test_amounts_match_document_totals(self):
        document = self._create_document()
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        self._add_line(document, self.tax_7, unit_price_net='50.00')
        self._add_line(document, self.tax_0, unit_price_net='25.00')
        document = self._recalculate(document)

        entry, _ = create_journal_entry(document)

        self.assertEqual(entry.net_19, Decimal('100.00'))
        self.assertEqual(entry.net_7, Decimal('50.00'))
        self.assertEqual(entry.net_0, Decimal('25.00'))
        self.assertEqual(entry.tax_amount, Decimal('22.50'))  # 19.00 + 3.50 + 0.00
        self.assertEqual(entry.gross_amount, Decimal('197.50'))

        # Cent-genau identisch mit den Belegsummen
        self.assertEqual(entry.net_0 + entry.net_7 + entry.net_19, document.total_net)
        self.assertEqual(entry.tax_amount, document.total_tax)
        self.assertEqual(entry.gross_amount, document.total_gross)

    def test_unselected_optional_lines_are_ignored(self):
        document = self._create_document()
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        self._add_line(document, self.tax_19, unit_price_net='500.00',
                       line_type='OPTIONAL', is_selected=False)
        document = self._recalculate(document)

        entry, _ = create_journal_entry(document)

        self.assertEqual(entry.net_19, Decimal('100.00'))
        self.assertEqual(entry.gross_amount, Decimal('119.00'))

    def test_revenue_accounts_are_snapshotted(self):
        document = self._create_document()
        self._add_line(document, self.tax_19)
        document = self._recalculate(document)

        entry, _ = create_journal_entry(document)

        self.assertEqual(entry.revenue_account_0, '8000')
        self.assertEqual(entry.revenue_account_7, '8100')
        self.assertEqual(entry.revenue_account_19, '8400')

    def test_revenue_accounts_empty_without_settings(self):
        self.accounting_settings.delete()
        document = self._create_document()
        self._add_line(document, self.tax_19)
        document = self._recalculate(document)

        entry, _ = create_journal_entry(document)

        self.assertEqual(entry.revenue_account_19, '')

    def test_is_idempotent(self):
        document = self._create_document()
        self._add_line(document, self.tax_19)
        document = self._recalculate(document)

        entry1, created1 = create_journal_entry(document)
        entry2, created2 = create_journal_entry(document)

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(entry1.pk, entry2.pk)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 1)

    def test_document_without_number_is_rejected(self):
        document = self._create_document(number='')
        self._add_line(document, self.tax_19)
        document = self._recalculate(document)

        with self.assertRaises(JournalEntryError):
            create_journal_entry(document)

    def test_document_without_customer_is_rejected(self):
        document = self._create_document(customer=None)
        self._add_line(document, self.tax_19)
        document = self._recalculate(document)

        with self.assertRaises(JournalEntryError):
            create_journal_entry(document)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)

    def test_customer_name_falls_back_to_name(self):
        customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name="Einzelkunde",
            strasse="Straße 2",
            plz="11111",
            ort="Stadt",
            land="Deutschland",
        )
        document = self._create_document(customer=customer)
        self._add_line(document, self.tax_19)
        document = self._recalculate(document)

        entry, _ = create_journal_entry(document)

        customer.refresh_from_db()
        self.assertEqual(entry.customer_name, 'Einzelkunde')
        self.assertEqual(entry.debtor_number, customer.debitor_number or '')


class UnsupportedTaxRateTest(JournalServiceTestBase):
    """Nicht unterstützte Steuersätze"""

    def test_unsupported_rate_raises_error(self):
        document = self._create_document()
        self._add_line(document, self.tax_16, unit_price_net='100.00')
        document = self._recalculate(document)

        with self.assertRaises(UnsupportedTaxRateError) as ctx:
            create_journal_entry(document)

        self.assertIn('16.00 %', str(ctx.exception))
        self.assertIn('0 %, 7 % und 19 %', str(ctx.exception))
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)

    def test_unsupported_rate_on_unselected_line_is_ignored(self):
        document = self._create_document()
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        self._add_line(document, self.tax_16, unit_price_net='100.00',
                       line_type='OPTIONAL', is_selected=False)
        document = self._recalculate(document)

        entry, created = create_journal_entry(document)

        self.assertTrue(created)
        self.assertEqual(entry.net_19, Decimal('100.00'))


class CreditNoteJournalTest(JournalServiceTestBase):
    """Gutschriften"""

    def _create_credit_note(self):
        source = self._create_document()
        self._add_line(source, self.tax_19, unit_price_net='100.00')
        self._recalculate(source)

        credit_note = self._create_document(
            document_type=self.doc_type_credit,
            number='GS26-00001',
            source_document=source,
        )
        self._add_line(credit_note, self.tax_19, unit_price_net='100.00')
        return self._recalculate(credit_note)

    def test_credit_note_is_booked_negative(self):
        credit_note = self._create_credit_note()

        entry, created = create_journal_entry(credit_note)

        self.assertTrue(created)
        self.assertEqual(entry.document_kind, 'CREDIT_NOTE')
        self.assertEqual(entry.net_19, Decimal('-100.00'))
        self.assertEqual(entry.tax_amount, Decimal('-19.00'))
        self.assertEqual(entry.gross_amount, Decimal('-119.00'))

    def test_credit_note_entry_is_model_valid(self):
        credit_note = self._create_credit_note()

        entry, _ = create_journal_entry(credit_note)

        # clean() darf für negative Beträge nicht fehlschlagen
        entry.full_clean()


class AmountConsistencyTest(JournalServiceTestBase):
    """Abgleich zwischen Positions- und Belegsummen"""

    def test_stale_document_totals_are_rejected(self):
        document = self._create_document()
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        document = self._recalculate(document)

        # Belegsummen manipulieren (z.B. Altbestand ohne Neuberechnung)
        SalesDocument.objects.filter(pk=document.pk).update(total_net=Decimal('999.00'))
        document.refresh_from_db()

        with self.assertRaises(JournalEntryError) as ctx:
            create_journal_entry(document)

        self.assertIn('neu berechnen', str(ctx.exception))

    def test_document_without_lines_uses_document_totals(self):
        document = self._create_document(
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00'),
        )

        entry, created = create_journal_entry(document)

        self.assertTrue(created)
        self.assertEqual(entry.net_19, Decimal('100.00'))
        self.assertEqual(entry.tax_amount, Decimal('19.00'))
        self.assertEqual(entry.gross_amount, Decimal('119.00'))

    def test_document_without_lines_and_unsupported_rate_is_rejected(self):
        document = self._create_document(
            total_net=Decimal('100.00'),
            total_tax=Decimal('16.00'),
            total_gross=Decimal('116.00'),
        )

        with self.assertRaises(UnsupportedTaxRateError):
            create_journal_entry(document)

    def test_zero_amount_document_is_booked(self):
        document = self._create_document()

        entry, created = create_journal_entry(document)

        self.assertTrue(created)
        self.assertEqual(entry.gross_amount, Decimal('0.00'))


class SnapshotStabilityTest(JournalServiceTestBase):
    """Snapshot-Charakter des Journals"""

    def test_later_document_changes_do_not_affect_entry(self):
        document = self._create_document()
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        document = self._recalculate(document)

        entry, _ = create_journal_entry(document)

        # Beleg nachträglich ändern
        document.number = 'R26-09999'
        document.issue_date = date(2026, 12, 31)
        document.save(update_fields=['number', 'issue_date'])
        line = document.lines.first()
        line.unit_price_net = Decimal('500.00')
        line.save(update_fields=['unit_price_net'])
        self._recalculate(document)

        entry.refresh_from_db()
        self.assertEqual(entry.document_number, 'R26-00001')
        self.assertEqual(entry.document_date, date(2026, 2, 6))
        self.assertEqual(entry.net_19, Decimal('100.00'))
        self.assertEqual(entry.gross_amount, Decimal('119.00'))
