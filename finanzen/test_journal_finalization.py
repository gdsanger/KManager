"""
Tests für die Kopplung von Belegfinalisierung und Rechnungsausgangsjournal
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.models import SalesDocument
from auftragsverwaltung.services.invoice_finalization import finalize_document, finalize_invoice
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.services.journal import UnsupportedTaxRateError
from finanzen.test_journal_service import JournalServiceTestBase


User = get_user_model()


class FinalizationCreatesJournalEntryTest(JournalServiceTestBase):
    """finalize_document/finalize_invoice erzeugen genau einen Journaleintrag"""

    def _draft_invoice(self, tax_rate=None):
        document = self._create_document(number='', status='DRAFT')
        self._add_line(document, tax_rate or self.tax_19, unit_price_net='100.00')
        return self._recalculate(document)

    def test_finalize_creates_single_entry(self):
        document = self._draft_invoice()

        document, was_modified = finalize_invoice(document)

        self.assertTrue(was_modified)
        self.assertTrue(document.number)
        self.assertEqual(document.status, 'SENT')

        entries = OutgoingInvoiceJournalEntry.objects.filter(document=document)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.document_number, document.number)
        self.assertEqual(entry.document_date, document.issue_date)
        self.assertEqual(entry.customer_name, 'Kunde GmbH (Max Mustermann)')
        self.assertEqual(entry.net_19, Decimal('100.00'))
        self.assertEqual(entry.gross_amount, Decimal('119.00'))
        self.assertEqual(entry.export_status, 'OPEN')

    def test_second_finalization_does_not_duplicate_entry(self):
        document = self._draft_invoice()

        document, _ = finalize_invoice(document)
        document, was_modified = finalize_invoice(document)

        self.assertFalse(was_modified)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.filter(document=document).count(), 1)

    def test_entry_created_for_already_sent_legacy_document(self):
        """Vor dem Journal finalisierte Belege bekommen ihren Eintrag nachträglich."""
        document = self._create_document(number='R26-00042', status='SENT')
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        document = self._recalculate(document)

        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)

        document, was_modified = finalize_invoice(document)

        self.assertFalse(was_modified)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 1)

    def test_unsupported_tax_rate_keeps_document_unfinalized(self):
        document = self._draft_invoice(tax_rate=self.tax_16)

        with self.assertRaises(UnsupportedTaxRateError):
            finalize_invoice(document)

        document.refresh_from_db()
        self.assertEqual(document.number, '')
        self.assertEqual(document.status, 'DRAFT')
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)

    def test_finalize_document_handles_credit_note(self):
        credit_note = self._create_document(
            document_type=self.doc_type_credit,
            number='',
            status='DRAFT',
            source_document=self._create_document(number='R26-00100'),
        )
        self._add_line(credit_note, self.tax_19, unit_price_net='100.00')
        credit_note = self._recalculate(credit_note)

        credit_note, was_modified = finalize_document(credit_note)

        self.assertTrue(was_modified)
        self.assertTrue(credit_note.number.startswith('GS'))

        entry = OutgoingInvoiceJournalEntry.objects.get(document=credit_note)
        self.assertEqual(entry.document_kind, 'CREDIT_NOTE')
        self.assertEqual(entry.net_19, Decimal('-100.00'))
        self.assertEqual(entry.gross_amount, Decimal('-119.00'))

    def test_finalize_invoice_rejects_credit_note(self):
        credit_note = self._create_document(
            document_type=self.doc_type_credit,
            number='GS26-00001',
        )
        with self.assertRaises(ValueError):
            finalize_invoice(credit_note)

    def test_finalize_document_rejects_quote(self):
        quote = self._create_document(document_type=self.doc_type_quote, number='AN26-00001')
        with self.assertRaises(ValueError):
            finalize_document(quote)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)


class EmailAfterFinalizationTest(JournalServiceTestBase):
    """Versand per E-Mail erzeugt keinen zweiten Journaleintrag"""

    def setUp(self):
        super().setUp()
        from core.models import MailTemplate
        MailTemplate.objects.update_or_create(
            key='invoice-sent',
            defaults={
                'name': 'Rechnung versendet',
                'subject': 'Rechnung {{ invoice_number }}',
                'body_text': 'Rechnung {{ invoice_number }}',
                'from_address': 'buchhaltung@example.com',
            },
        )
        self.customer.invoice_email = 'kunde@example.com'
        self.customer.save(update_fields=['invoice_email'])

    @patch('auftragsverwaltung.services.invoice_email.send_mail')
    @patch('auftragsverwaltung.services.invoice_email.PdfRenderService')
    def test_print_then_email_creates_one_entry(self, mock_pdf_service, mock_send_mail):
        mock_result = MagicMock()
        mock_result.pdf_bytes = b'%PDF-1.4'
        mock_result.filename = 'Rechnung.pdf'
        mock_pdf_service.return_value.render.return_value = mock_result

        from auftragsverwaltung.services.invoice_email import send_invoice_email

        document = self._create_document(number='', status='DRAFT')
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        document = self._recalculate(document)

        # 1. Echtdruck
        document, _ = finalize_invoice(document)
        # 2. Versand per E-Mail (finalisiert erneut)
        result = send_invoice_email(document, to_customer=True, to_internal=False)

        self.assertTrue(result['success'])
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.filter(document=document).count(), 1)


class FinalizeViewJournalTest(JournalServiceTestBase):
    """Echtdruck-View schreibt das Journal"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='tester', password='pw12345678')
        self.client = Client()
        self.client.force_login(self.user)

    @patch('auftragsverwaltung.views.PdfRenderService')
    def test_view_creates_journal_entry(self, mock_pdf_service):
        mock_result = MagicMock()
        mock_result.pdf_bytes = b'%PDF-1.4'
        mock_result.filename = 'Rechnung.pdf'
        mock_result.content_type = 'application/pdf'
        mock_pdf_service.return_value.render.return_value = mock_result

        document = self._create_document(number='', status='DRAFT')
        self._add_line(document, self.tax_19, unit_price_net='100.00')
        document = self._recalculate(document)

        url = reverse('auftragsverwaltung:invoice_finalize', kwargs={'pk': document.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.filter(document=document).count(), 1)

    @patch('auftragsverwaltung.views.PdfRenderService')
    def test_view_finalizes_credit_note(self, mock_pdf_service):
        mock_result = MagicMock()
        mock_result.pdf_bytes = b'%PDF-1.4'
        mock_result.filename = 'Gutschrift.pdf'
        mock_result.content_type = 'application/pdf'
        mock_pdf_service.return_value.render.return_value = mock_result

        credit_note = self._create_document(
            document_type=self.doc_type_credit,
            number='',
            status='DRAFT',
            source_document=self._create_document(number='R26-00100'),
        )
        self._add_line(credit_note, self.tax_19, unit_price_net='100.00')
        credit_note = self._recalculate(credit_note)

        url = reverse('auftragsverwaltung:invoice_finalize', kwargs={'pk': credit_note.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        entry = OutgoingInvoiceJournalEntry.objects.get(document=credit_note)
        self.assertEqual(entry.document_kind, 'CREDIT_NOTE')

    def test_view_rejects_quote(self):
        quote = self._create_document(document_type=self.doc_type_quote, number='AN26-00001')

        url = reverse('auftragsverwaltung:invoice_finalize', kwargs={'pk': quote.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_view_reports_unsupported_tax_rate(self):
        document = self._create_document(number='', status='DRAFT')
        self._add_line(document, self.tax_16, unit_price_net='100.00')
        document = self._recalculate(document)

        url = reverse('auftragsverwaltung:invoice_finalize', kwargs={'pk': document.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 400)
        self.assertIn('16.00 %', response.json()['error'])

        document.refresh_from_db()
        self.assertEqual(document.number, '')
        self.assertEqual(document.status, 'DRAFT')


class ContractBillingJournalTest(JournalServiceTestBase):
    """Vertragsabrechnung: auto-finalisierte Rechnungen landen im Journal"""

    def _create_contract(self, auto_finalize):
        from datetime import date
        from auftragsverwaltung.models import Contract, ContractLine, NumberRange

        NumberRange.objects.get_or_create(
            company=self.company,
            target='CONTRACT',
            document_type=None,
            defaults={
                'current_year': 26,
                'current_seq': 0,
                'format': '{prefix}{yy}-{seq:05d}',
                'reset_policy': 'YEARLY',
            },
        )

        contract = Contract.objects.create(
            company=self.company,
            name="Testvertrag",
            customer=self.customer,
            document_type=self.doc_type_invoice,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True,
            auto_finalize=auto_finalize,
        )
        ContractLine.objects.create(
            contract=contract,
            position_no=1,
            description="Monatliche Leistung",
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_19,
            is_discountable=True,
        )
        return contract

    def test_auto_finalized_contract_invoice_is_journaled(self):
        from datetime import date
        from auftragsverwaltung.services.contract_billing import ContractBillingService

        self._create_contract(auto_finalize=True)

        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))

        self.assertEqual(runs[0].status, 'SUCCESS')
        document = runs[0].document
        self.assertEqual(document.status, 'SENT')

        entry = OutgoingInvoiceJournalEntry.objects.get(document=document)
        self.assertEqual(entry.document_number, document.number)
        self.assertEqual(entry.net_19, Decimal('100.00'))
        self.assertEqual(entry.gross_amount, Decimal('119.00'))

    def test_draft_contract_invoice_is_not_journaled(self):
        from datetime import date
        from auftragsverwaltung.services.contract_billing import ContractBillingService

        self._create_contract(auto_finalize=False)

        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))

        self.assertEqual(runs[0].status, 'SUCCESS')
        self.assertEqual(runs[0].document.status, 'DRAFT')
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)


class JournalListViewTest(JournalServiceTestBase):
    """Listenansicht mit echten Daten"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='tester', password='pw12345678')
        self.client = Client()
        self.client.force_login(self.user)

        invoice = self._create_document(number='R26-00001')
        self._add_line(invoice, self.tax_19, unit_price_net='100.00')
        self.invoice = self._recalculate(invoice)
        from finanzen.services.journal import create_journal_entry
        create_journal_entry(self.invoice)

        credit_note = self._create_document(
            document_type=self.doc_type_credit,
            number='GS26-00001',
            source_document=self.invoice,
        )
        self._add_line(credit_note, self.tax_7, unit_price_net='50.00')
        self.credit_note = self._recalculate(credit_note)
        create_journal_entry(self.credit_note)

    def test_list_shows_entries(self):
        response = self.client.get(reverse('auftragsverwaltung:journal_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'R26-00001')
        self.assertContains(response, 'GS26-00001')
        self.assertEqual(response.context['table'].paginator.count, 2)

    def test_totals_include_credit_note_negative(self):
        response = self.client.get(reverse('auftragsverwaltung:journal_list'))

        totals = response.context['totals']
        self.assertEqual(totals['net_19'], Decimal('100.00'))
        self.assertEqual(totals['net_7'], Decimal('-50.00'))
        self.assertEqual(totals['net'], Decimal('50.00'))
        self.assertEqual(totals['gross'], Decimal('65.50'))  # 119.00 - 53.50

    def test_search_filter(self):
        response = self.client.get(reverse('auftragsverwaltung:journal_list'), {'q': 'GS26'})

        self.assertEqual(response.context['table'].paginator.count, 1)
        self.assertEqual(response.context['totals']['gross'], Decimal('-53.50'))

    def test_document_kind_filter(self):
        response = self.client.get(
            reverse('auftragsverwaltung:journal_list'), {'document_kind': 'CREDIT_NOTE'}
        )

        self.assertEqual(response.context['table'].paginator.count, 1)

    def test_date_range_filter(self):
        response = self.client.get(
            reverse('auftragsverwaltung:journal_list'),
            {'document_date_from': '2026-03-01'},
        )

        self.assertEqual(response.context['table'].paginator.count, 0)

    def test_detail_view(self):
        entry = OutgoingInvoiceJournalEntry.objects.get(document=self.credit_note)
        response = self.client.get(
            reverse('auftragsverwaltung:journal_detail', kwargs={'pk': entry.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GS26-00001')
        self.assertContains(response, 'Gutschrift')
