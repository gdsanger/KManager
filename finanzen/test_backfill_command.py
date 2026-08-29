"""
Tests für das Management-Command `backfill_journal_entries`
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Mandant
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.test_journal_service import JournalServiceTestBase


class BackfillJournalEntriesCommandTest(JournalServiceTestBase):
    """Nachtrag der Journaleinträge für bereits finalisierte Belege"""

    def setUp(self):
        super().setUp()

        # Finalisierte Rechnung ohne Journaleintrag
        self.invoice = self._create_document(number='R26-00001', status='SENT')
        self._add_line(self.invoice, self.tax_19, unit_price_net='100.00')
        self.invoice = self._recalculate(self.invoice)

        # Finalisierte Gutschrift ohne Journaleintrag
        self.credit_note = self._create_document(
            document_type=self.doc_type_credit,
            number='GS26-00001',
            status='SENT',
            source_document=self.invoice,
        )
        self._add_line(self.credit_note, self.tax_7, unit_price_net='50.00')
        self.credit_note = self._recalculate(self.credit_note)

        # Entwurf (nicht finalisiert)
        self.draft = self._create_document(number='', status='DRAFT')

        # Angebot (nicht journalrelevant)
        self.quote = self._create_document(
            document_type=self.doc_type_quote,
            number='AN26-00001',
            status='SENT',
        )

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_journal_entries', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_creates_nothing(self):
        output = self._run('--dry-run')

        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)
        self.assertIn('Trockenlauf', output)
        self.assertIn('R26-00001', output)
        self.assertIn('GS26-00001', output)
        self.assertIn('2 Einträge würden angelegt', output)

    def test_creates_entries(self):
        output = self._run()

        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 2)
        self.assertIn('2 Einträge angelegt', output)

        invoice_entry = OutgoingInvoiceJournalEntry.objects.get(document=self.invoice)
        self.assertEqual(invoice_entry.document_kind, 'INVOICE')
        self.assertEqual(invoice_entry.gross_amount, Decimal('119.00'))
        self.assertEqual(invoice_entry.export_status, 'OPEN')

        credit_entry = OutgoingInvoiceJournalEntry.objects.get(document=self.credit_note)
        self.assertEqual(credit_entry.document_kind, 'CREDIT_NOTE')
        self.assertEqual(credit_entry.gross_amount, Decimal('-53.50'))

    def test_is_repeatable_without_duplicates(self):
        self._run()
        output = self._run()

        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 2)
        self.assertIn('0 Einträge angelegt', output)
        self.assertIn('2 übersprungen', output)

    def test_drafts_and_quotes_are_ignored(self):
        self._run()

        self.assertFalse(
            OutgoingInvoiceJournalEntry.objects.filter(document=self.draft).exists()
        )
        self.assertFalse(
            OutgoingInvoiceJournalEntry.objects.filter(document=self.quote).exists()
        )

    def test_cancelled_documents_are_skipped_by_default(self):
        cancelled = self._create_document(number='R26-00002', status='CANCELLED')
        self._add_line(cancelled, self.tax_19, unit_price_net='10.00')
        self._recalculate(cancelled)

        self._run()
        self.assertFalse(
            OutgoingInvoiceJournalEntry.objects.filter(document=cancelled).exists()
        )

        self._run('--include-cancelled')
        self.assertTrue(
            OutgoingInvoiceJournalEntry.objects.filter(document=cancelled).exists()
        )

    def test_company_filter(self):
        other_company = Mandant.objects.create(
            name="Zweiter Mandant",
            adresse="Weg 2",
            plz="22222",
            ort="Stadt",
            land="Deutschland",
        )
        other_invoice = self._create_document(
            company=other_company, number='R26-00003', status='SENT'
        )
        self._add_line(other_invoice, self.tax_19, unit_price_net='10.00')
        self._recalculate(other_invoice)

        self._run('--company', str(other_company.pk))

        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 1)
        self.assertTrue(
            OutgoingInvoiceJournalEntry.objects.filter(document=other_invoice).exists()
        )

    def test_unknown_company_raises(self):
        with self.assertRaises(CommandError):
            self._run('--company', '9999')

    def test_faulty_document_is_reported_and_skipped(self):
        broken = self._create_document(number='R26-00004', status='SENT')
        self._add_line(broken, self.tax_16, unit_price_net='100.00')
        self._recalculate(broken)

        output = self._run()

        self.assertIn('FEHLER', output)
        self.assertIn('R26-00004', output)
        self.assertIn('1 fehlerhaft', output)
        # Die übrigen Belege werden trotzdem verarbeitet
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 2)

    def test_dry_run_reports_faulty_document(self):
        broken = self._create_document(number='R26-00004', status='SENT')
        self._add_line(broken, self.tax_16, unit_price_net='100.00')
        self._recalculate(broken)

        output = self._run('--dry-run')

        self.assertIn('FEHLER', output)
        self.assertIn('1 fehlerhaft', output)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)
