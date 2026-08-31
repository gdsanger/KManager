"""
Tests für den DATEV-Buchungsstapel-Export (finanzen.services.datev_export)

Schwerpunkte:
- Die Einnahmenseite stammt ausschließlich aus dem Rechnungsausgangsjournal.
- Gutschriften bekommen das richtige Soll/Haben-Kennzeichen.
- Belege mit mehreren Steuersätzen werden aufgeteilt, Summen bleiben cent-genau.
- Belege ohne auflösbares Konto landen in der Fehlerliste statt still zu fehlen.
- Bereits exportierte Belege werden nicht versehentlich erneut exportiert.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Kostenart, Mandant
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry
from finanzen.services import datev_export as service
from lieferantenwesen.models import InvoiceIn, InvoiceInLine


class DatevExportTestBase(TestCase):
    """Gemeinsame Testdaten"""

    def setUp(self):
        self.company = Mandant.objects.create(
            name="Test Mandant GmbH", adresse="Str. 1", plz="12345", ort="Stadt",
        )
        self.settings = CompanyAccountingSettings.objects.create(
            company=self.company,
            datev_consultant_number="1001",
            datev_client_number="1",
            revenue_account_0="8000",
            revenue_account_7="8300",
            revenue_account_19="8400",
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE', name="Kunde", strasse="Str. 1",
            plz="12345", ort="Stadt", land="Deutschland",
        )
        self.supplier = Adresse.objects.create(
            adressen_type='LIEFERANT', name="Lieferant", strasse="Str. 2",
            plz="12345", ort="Stadt", land="Deutschland",
        )
        self.doc_type_invoice = DocumentType.objects.get(key='invoice')
        self.kostenart = Kostenart.objects.create(
            name="Bürobedarf", aufwandskonto="4930",
        )

    def _journal_entry(self, number='R26-00001', kind='INVOICE', document_date=None,
                       net_19='1000.00', net_7='0.00', net_0='0.00', tax=None, **kwargs):
        """Journaleintrag direkt anlegen – der Export liest nur das Journal."""
        document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            customer=self.customer,
            number=number,
            status='SENT',
            issue_date=document_date or date(2026, 1, 15),
        )
        net_19, net_7, net_0 = Decimal(net_19), Decimal(net_7), Decimal(net_0)
        if tax is None:
            tax = (net_19 * Decimal('0.19') + net_7 * Decimal('0.07')).quantize(Decimal('0.01'))
        else:
            tax = Decimal(tax)

        defaults = {
            'company': self.company,
            'document': document,
            'document_number': number,
            'document_date': document_date or date(2026, 1, 15),
            'document_kind': kind,
            'customer_name': "Kunde",
            'debtor_number': self.customer.debitor_number,
            'net_0': net_0, 'net_7': net_7, 'net_19': net_19,
            'tax_amount': tax,
            'gross_amount': net_0 + net_7 + net_19 + tax,
            'revenue_account_0': "8000",
            'revenue_account_7': "8300",
            'revenue_account_19': "8400",
        }
        defaults.update(kwargs)
        return OutgoingInvoiceJournalEntry.objects.create(**defaults)

    def _incoming_invoice(self, invoice_no='ER-1', status='APPROVED',
                          invoice_date=None, net='200.00', tax='38.00', **kwargs):
        defaults = {
            'invoice_no': invoice_no,
            'invoice_date': invoice_date or date(2026, 1, 10),
            'company': self.company,
            'supplier': self.supplier,
            'status': status,
            'net_amount': Decimal(net),
            'tax_amount': Decimal(tax),
            'gross_amount': Decimal(net) + Decimal(tax),
            'cost_type_main': self.kostenart,
        }
        defaults.update(kwargs)
        return InvoiceIn.objects.create(**defaults)

    def _preview(self, **kwargs):
        return service.build_preview(
            self.company, date(2026, 1, 1), date(2026, 1, 31), **kwargs
        )


class OutgoingSideTestCase(DatevExportTestBase):
    """Einnahmenseite – ausschließlich aus dem Rechnungsausgangsjournal"""

    def test_invoice_produces_debit_booking(self):
        self._journal_entry()
        preview = self._preview()

        self.assertEqual(preview.booking_count, 1)
        booking = preview.bookings[0]
        self.assertEqual(booking.account, self.customer.debitor_number)
        self.assertEqual(booking.contra_account, "8400")
        self.assertEqual(booking.debit_credit, 'S')
        self.assertEqual(booking.amount, Decimal('1190.00'))
        self.assertEqual(booking.document_field_1, 'R26-00001')
        self.assertEqual(booking.document_date, date(2026, 1, 15))

    def test_credit_note_uses_haben(self):
        """Gutschriften stehen negativ im Journal und werden mit H gebucht"""
        self._journal_entry(
            number='GS26-00001', kind='CREDIT_NOTE',
            net_19='-1000.00', tax='-190.00',
        )
        preview = self._preview()

        booking = preview.bookings[0]
        self.assertEqual(booking.debit_credit, 'H')
        self.assertEqual(booking.amount, Decimal('-1190.00'))

    def test_multiple_tax_rates_are_split(self):
        self._journal_entry(net_19='1000.00', net_7='100.00')
        preview = self._preview()

        self.assertEqual(preview.booking_count, 2)
        by_account = {b.contra_account: b.amount for b in preview.bookings}
        self.assertEqual(by_account['8400'], Decimal('1190.00'))
        self.assertEqual(by_account['8300'], Decimal('107.00'))

    def test_split_sums_match_document_total_to_the_cent(self):
        """Rundungsdifferenzen dürfen die Belegsumme nicht verändern"""
        entry = self._journal_entry(net_19='33.33', net_7='16.67', tax='7.50')
        preview = self._preview()

        total = sum(b.amount for b in preview.bookings)
        self.assertEqual(total, entry.gross_amount)

    def test_sales_document_is_not_read_directly(self):
        """
        Ohne Journaleintrag entsteht keine Buchung – auch wenn ein
        finalisierter Beleg existiert.
        """
        SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type_invoice,
            customer=self.customer, number='R26-09999', status='SENT',
            issue_date=date(2026, 1, 20), total_net=Decimal('500.00'),
            total_tax=Decimal('95.00'), total_gross=Decimal('595.00'),
        )
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertEqual(preview.problems, [])

    def test_missing_debtor_account_is_reported(self):
        self._journal_entry(debtor_number='')
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertEqual(len(preview.problems), 1)
        self.assertIn('Debitorenkonto', preview.problems[0].message)

    def test_missing_revenue_account_is_reported(self):
        self._journal_entry(revenue_account_19='')
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertEqual(len(preview.problems), 1)
        self.assertIn('Erlöskonto', preview.problems[0].message)

    def test_entries_outside_the_period_are_ignored(self):
        self._journal_entry(number='R26-00002', document_date=date(2026, 2, 5))
        preview = self._preview()
        self.assertEqual(preview.booking_count, 0)

    def test_zero_document_produces_no_booking_and_no_error(self):
        self._journal_entry(net_19='0.00', tax='0.00')
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertEqual(preview.problems, [])
        self.assertEqual(len(preview.journal_entries), 1)

    def test_inconsistent_tax_is_reported(self):
        self._journal_entry(net_19='1000.00', tax='250.00')
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertIn('Umsatzsteuer', preview.problems[0].message)


class IncomingSideTestCase(DatevExportTestBase):
    """Ausgabenseite – freigegebene Eingangsrechnungen"""

    def test_approved_invoice_produces_booking(self):
        self._incoming_invoice()
        preview = self._preview()

        booking = preview.bookings[0]
        self.assertEqual(booking.account, "4930")
        self.assertEqual(booking.contra_account, self.supplier.debitor_number)
        self.assertEqual(booking.debit_credit, 'S')
        self.assertEqual(booking.amount, Decimal('238.00'))
        self.assertEqual(booking.document_field_1, 'ER-1')

    def test_draft_invoice_is_not_exported(self):
        self._incoming_invoice(status='DRAFT')
        preview = self._preview()
        self.assertEqual(preview.booking_count, 0)

    def test_paid_invoice_is_exported(self):
        self._incoming_invoice(status='PAID', payment_date=date(2026, 1, 20))
        preview = self._preview()
        self.assertEqual(preview.booking_count, 1)

    def test_missing_expense_account_is_reported(self):
        self.kostenart.aufwandskonto = ""
        self.kostenart.save()
        self._incoming_invoice()
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertIn('Aufwandskonto', preview.problems[0].message)

    def test_missing_creditor_account_is_reported(self):
        self.supplier.debitor_number = None
        self.supplier.save()
        self._incoming_invoice()
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertIn('Kreditorenkonto', preview.problems[0].message)

    def test_lines_are_grouped_by_account_and_tax_rate(self):
        other = Kostenart.objects.create(name="Reisekosten", aufwandskonto="4670")
        invoice = self._incoming_invoice(net='300.00', tax='45.00')
        InvoiceInLine.objects.create(
            invoice=invoice, position_no=1, description="Papier",
            net_amount=Decimal('100.00'), tax_rate=Decimal('19.00'),
            cost_type_main_line=self.kostenart,
        )
        InvoiceInLine.objects.create(
            invoice=invoice, position_no=2, description="Ordner",
            net_amount=Decimal('100.00'), tax_rate=Decimal('19.00'),
            cost_type_main_line=self.kostenart,
        )
        InvoiceInLine.objects.create(
            invoice=invoice, position_no=3, description="Bahnfahrt",
            net_amount=Decimal('100.00'), tax_rate=Decimal('7.00'),
            cost_type_main_line=other,
        )
        invoice.gross_amount = Decimal('345.00')
        invoice.save()

        preview = self._preview()
        by_account = {b.account: b.amount for b in preview.bookings}
        self.assertEqual(by_account['4930'], Decimal('238.00'))
        self.assertEqual(by_account['4670'], Decimal('107.00'))
        self.assertEqual(sum(by_account.values()), Decimal('345.00'))

    def test_line_totals_must_match_header(self):
        invoice = self._incoming_invoice(net='300.00', tax='57.00')
        InvoiceInLine.objects.create(
            invoice=invoice, position_no=1, description="Papier",
            net_amount=Decimal('100.00'), tax_rate=Decimal('19.00'),
            cost_type_main_line=self.kostenart,
        )
        preview = self._preview()

        self.assertEqual(preview.booking_count, 0)
        self.assertIn('Positionssummen', preview.problems[0].message)

    def test_line_cost_type_wins_over_header(self):
        other = Kostenart.objects.create(name="Reisekosten", aufwandskonto="4670")
        invoice = self._incoming_invoice(net='100.00', tax='19.00')
        InvoiceInLine.objects.create(
            invoice=invoice, position_no=1, description="Bahnfahrt",
            net_amount=Decimal('100.00'), tax_rate=Decimal('19.00'),
            cost_type_main_line=other,
        )
        preview = self._preview()
        self.assertEqual(preview.bookings[0].account, "4670")


class IncomingCompanyScopeTestCase(DatevExportTestBase):
    """Eingangsrechnungen gehören in den Stapel genau eines Mandanten"""

    def setUp(self):
        super().setUp()
        self.other_company = Mandant.objects.create(
            name="Zweiter Mandant GmbH", adresse="Str. 9", plz="54321", ort="Ort",
        )
        CompanyAccountingSettings.objects.create(
            company=self.other_company,
            datev_consultant_number="1001",
            datev_client_number="2",
            revenue_account_0="8000",
            revenue_account_7="8300",
            revenue_account_19="8400",
        )

    def _other_preview(self, **kwargs):
        return service.build_preview(
            self.other_company, date(2026, 1, 1), date(2026, 1, 31), **kwargs
        )

    def test_invoice_of_other_company_is_not_in_the_stack(self):
        self._incoming_invoice(company=self.company)

        preview = self._other_preview()
        self.assertEqual(preview.booking_count, 0)
        self.assertEqual(preview.incoming_invoices, [])
        self.assertEqual(preview.problems, [])

    def test_own_invoice_stays_in_the_own_stack(self):
        self._incoming_invoice(company=self.company)

        preview = self._preview()
        self.assertEqual(preview.booking_count, 1)
        self.assertEqual(preview.bookings[0].document_field_1, 'ER-1')

    def test_re_export_does_not_leak_into_the_other_company(self):
        """Auch der bewusste Wiederholungsexport bleibt mandantenrein."""
        self._incoming_invoice(company=self.company)
        service.mark_exported(self._preview(), 'BATCH-1')

        repeat = self._other_preview(include_exported=True)
        self.assertEqual(repeat.booking_count, 0)
        self.assertEqual(repeat.skipped_exported, 0)

    def test_export_of_one_company_leaves_the_other_stack_complete(self):
        """Der Export von Mandant B darf Belege von A nicht verbrauchen."""
        invoice = self._incoming_invoice(company=self.company)

        service.mark_exported(self._other_preview(), 'BATCH-B')
        invoice.refresh_from_db()
        self.assertEqual(invoice.export_status, 'OPEN')
        self.assertEqual(self._preview().booking_count, 1)

    def test_invoice_without_company_is_reported_instead_of_exported(self):
        self._incoming_invoice(company=None)

        preview = self._preview()
        self.assertEqual(preview.booking_count, 0)
        self.assertEqual(len(preview.problems), 1)
        self.assertEqual(preview.problems[0].source, 'EINGANG')
        self.assertIn('kein Mandant zugeordnet', preview.problems[0].message)

    def test_invoice_without_company_blocks_the_download(self):
        self._incoming_invoice(company=None)

        preview = self._preview()
        with self.assertRaises(service.DatevExportError):
            service.render_extf(preview)

    def test_invoice_without_company_is_reported_for_every_company(self):
        """Der Beleg ist offen, egal welcher Stapel gerade erzeugt wird."""
        self._incoming_invoice(company=None)
        self.assertEqual(len(self._other_preview().problems), 1)

    def test_draft_without_company_is_not_reported(self):
        """Nur buchungsreife Belege gehören in die Fehlerliste."""
        self._incoming_invoice(company=None, status='DRAFT')
        self.assertEqual(self._preview().problems, [])

    def test_invoice_without_company_outside_the_period_is_not_reported(self):
        self._incoming_invoice(company=None, invoice_date=date(2026, 2, 10))
        self.assertEqual(self._preview().problems, [])

    def test_already_exported_invoice_without_company_stays_reported(self):
        """Ein versehentlich exportierter Beleg ohne Mandant bleibt offen."""
        self._incoming_invoice(company=None, export_status='EXPORTED')
        self.assertEqual(len(self._preview().problems), 1)


class ExportStatusTestCase(DatevExportTestBase):
    """Export-Status und Wiederholungsexport"""

    def test_exported_entries_are_skipped_by_default(self):
        self._journal_entry()
        self._incoming_invoice()

        preview = self._preview()
        service.mark_exported(preview, 'BATCH-1')

        second = self._preview()
        self.assertEqual(second.booking_count, 0)
        self.assertEqual(second.skipped_exported, 2)

    def test_mark_exported_sets_status_on_both_sides(self):
        entry = self._journal_entry()
        invoice = self._incoming_invoice()

        service.mark_exported(self._preview(), 'BATCH-1')

        entry.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(entry.export_status, 'EXPORTED')
        self.assertEqual(entry.export_batch_id, 'BATCH-1')
        self.assertIsNotNone(entry.exported_at)
        self.assertEqual(invoice.export_status, 'EXPORTED')
        self.assertEqual(invoice.export_batch_id, 'BATCH-1')
        self.assertIsNotNone(invoice.exported_at)

    def test_deliberate_re_export_is_possible_and_traceable(self):
        entry = self._journal_entry()
        service.mark_exported(self._preview(), 'BATCH-1')

        repeat = self._preview(include_exported=True)
        self.assertEqual(repeat.booking_count, 1)

        service.mark_exported(repeat, 'BATCH-2')
        entry.refresh_from_db()
        self.assertEqual(entry.export_batch_id, 'BATCH-2')


class ExtfFileFormatTestCase(DatevExportTestBase):
    """Aufbau der EXTF-Datei"""

    def _render(self):
        preview = self._preview()
        return service.render_extf(preview).decode(service.ENCODING)

    def test_header_and_column_row(self):
        self._journal_entry()
        content = self._render()
        lines = content.split(service.LINE_ENDING)

        header = lines[0].split(';')
        self.assertEqual(header[0], '"EXTF"')
        self.assertEqual(header[1], '700')
        self.assertEqual(header[2], '21')
        self.assertEqual(header[3], '"Buchungsstapel"')
        self.assertEqual(header[10], '1001')          # Beraternummer
        self.assertEqual(header[11], '1')             # Mandantennummer
        self.assertEqual(header[12], '20260101')      # Wirtschaftsjahresbeginn
        self.assertEqual(header[13], '4')             # Sachkontenlänge
        self.assertEqual(header[14], '20260101')      # Datum von
        self.assertEqual(header[15], '20260131')      # Datum bis
        self.assertEqual(header[21], '"EUR"')

        columns = lines[1].split(';')
        self.assertEqual(len(columns), 125)
        self.assertEqual(columns[0], '"Umsatz (ohne Soll/Haben-Kz)"')
        self.assertEqual(columns[6], '"Konto"')
        self.assertEqual(columns[7], '"Gegenkonto (ohne BU-Schlüssel)"')

    def test_booking_row_fields(self):
        self._journal_entry()
        content = self._render()
        row = content.split(service.LINE_ENDING)[2].split(';')

        self.assertEqual(len(row), 125)
        self.assertEqual(row[service.COL_UMSATZ], '1190,00')
        self.assertEqual(row[service.COL_SOLL_HABEN], '"S"')
        self.assertEqual(row[service.COL_WKZ], '"EUR"')
        self.assertEqual(row[service.COL_KONTO], self.customer.debitor_number)
        self.assertEqual(row[service.COL_GEGENKONTO], '8400')
        self.assertEqual(row[service.COL_BELEGDATUM], '1501')
        self.assertEqual(row[service.COL_BELEGFELD1], '"R26-00001"')

    def test_amounts_use_german_decimal_separator(self):
        self._journal_entry(net_19='1234.50', tax='234.56')
        content = self._render()
        row = content.split(service.LINE_ENDING)[2].split(';')

        self.assertEqual(row[service.COL_UMSATZ], '1469,06')
        self.assertNotIn('.', row[service.COL_UMSATZ])

    def test_credit_note_amount_is_positive_with_haben_flag(self):
        self._journal_entry(
            number='GS26-00001', kind='CREDIT_NOTE',
            net_19='-100.00', tax='-19.00',
        )
        content = self._render()
        row = content.split(service.LINE_ENDING)[2].split(';')

        self.assertEqual(row[service.COL_UMSATZ], '119,00')
        self.assertEqual(row[service.COL_SOLL_HABEN], '"H"')

    def test_encoding_is_windows_1252(self):
        self._journal_entry(customer_name='Müller & Söhne')
        preview = self._preview()
        content = service.render_extf(preview)

        self.assertIsInstance(content, bytes)
        self.assertIn('Müller', content.decode('cp1252'))

    def test_lines_end_with_crlf(self):
        self._journal_entry()
        content = service.render_extf(self._preview()).decode(service.ENCODING)
        self.assertTrue(content.endswith('\r\n'))

    def test_separator_in_text_is_neutralised(self):
        """Ein Semikolon im Buchungstext darf die Feldstruktur nicht zerstören"""
        self._journal_entry(customer_name='Meier; Schulze GmbH')
        content = service.render_extf(self._preview()).decode(service.ENCODING)
        row = content.split(service.LINE_ENDING)[2].split(';')
        self.assertEqual(len(row), 125)

    def test_export_is_blocked_while_problems_remain(self):
        self._journal_entry(debtor_number='')
        preview = self._preview()

        with self.assertRaises(service.DatevExportError) as cm:
            service.render_extf(preview)
        self.assertIn('Fehlerliste', str(cm.exception))

    def test_filename_contains_period(self):
        preview = self._preview()
        self.assertEqual(
            service.build_filename(preview),
            'EXTF_Buchungsstapel_20260101_20260131.csv',
        )


class PeriodValidationTestCase(DatevExportTestBase):
    """Zeitraumprüfungen"""

    def test_reversed_period_is_rejected(self):
        with self.assertRaises(service.DatevExportError):
            service.build_preview(self.company, date(2026, 2, 1), date(2026, 1, 1))

    def test_period_across_year_boundary_is_rejected(self):
        """Das Belegdatum trägt nur Tag und Monat – ein Jahreswechsel wäre mehrdeutig"""
        with self.assertRaises(service.DatevExportError) as cm:
            service.build_preview(self.company, date(2025, 12, 1), date(2026, 1, 31))
        self.assertIn('Jahreswechsel', str(cm.exception))

    def test_missing_accounting_settings_is_rejected(self):
        other = Mandant.objects.create(
            name="Ohne Einstellungen", adresse="Str.", plz="1", ort="X",
        )
        with self.assertRaises(service.DatevExportError) as cm:
            service.build_preview(other, date(2026, 1, 1), date(2026, 1, 31))
        self.assertIn('Buchhaltungseinstellungen', str(cm.exception))


class PreviewSummaryTestCase(DatevExportTestBase):
    """Kennzahlen der Vorschau"""

    def test_counts_and_totals(self):
        self._journal_entry(net_19='1000.00')
        self._incoming_invoice(net='200.00', tax='38.00')
        preview = self._preview()

        self.assertEqual(preview.booking_count, 2)
        self.assertEqual(preview.outgoing_total, Decimal('1190.00'))
        self.assertEqual(preview.incoming_total, Decimal('238.00'))
        self.assertEqual(preview.total_debit, Decimal('1428.00'))
        self.assertEqual(preview.total_credit, Decimal('0.00'))

    def test_credit_note_counts_towards_credit_total(self):
        self._journal_entry(
            number='GS26-1', kind='CREDIT_NOTE', net_19='-100.00', tax='-19.00',
        )
        preview = self._preview()
        self.assertEqual(preview.total_credit, Decimal('119.00'))


class ManagementCommandTestCase(DatevExportTestBase):
    """
    Management-Command `datev_export`.

    Das `--sample`-Flag dient der Formatprüfung gegen den Importer des
    Zielsystems, bevor mit Echtbelegen gearbeitet wird.
    """

    def _call(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('datev_export', *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_sample_file_has_valid_structure(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'probe.csv'
            self._call('--sample', '--output', str(target))

            content = target.read_bytes().decode(service.ENCODING)
            lines = content.split(service.LINE_ENDING)

            self.assertTrue(lines[0].startswith('"EXTF";700;21;"Buchungsstapel"'))
            self.assertEqual(len(lines[1].split(';')), 125)
            # Rechnung (S), Gutschrift (H) und Eingangsrechnung (S)
            self.assertEqual(len(lines[2].split(';')), 125)
            self.assertIn('"H"', lines[3])

    def test_preview_run_leaves_export_status_untouched(self):
        entry = self._journal_entry()
        output = self._call('--company', str(self.company.pk),
                            '--from', '2026-01-01', '--to', '2026-01-31')

        self.assertIn('1 Buchungssätze', output)
        entry.refresh_from_db()
        self.assertEqual(entry.export_status, 'OPEN')

    def test_mark_exported_flag_sets_status(self):
        import tempfile
        from pathlib import Path

        entry = self._journal_entry()
        with tempfile.TemporaryDirectory() as tmp:
            self._call('--company', str(self.company.pk),
                       '--from', '2026-01-01', '--to', '2026-01-31',
                       '--output', str(Path(tmp) / 'stapel.csv'), '--mark-exported')

        entry.refresh_from_db()
        self.assertEqual(entry.export_status, 'EXPORTED')

    def test_problems_abort_the_command(self):
        from django.core.management.base import CommandError

        self._journal_entry(debtor_number='')
        with self.assertRaises(CommandError):
            self._call('--company', str(self.company.pk),
                       '--from', '2026-01-01', '--to', '2026-01-31')

    def test_run_without_output_writes_no_file(self):
        """Ein Vorschaulauf darf keine Datei ins Arbeitsverzeichnis schreiben"""
        import os
        import tempfile
        from pathlib import Path

        self._journal_entry()
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                self._call('--company', str(self.company.pk),
                           '--from', '2026-01-01', '--to', '2026-01-31')
                self.assertEqual(list(Path(tmp).iterdir()), [])
            finally:
                os.chdir(previous)

    def test_mark_exported_requires_output(self):
        from django.core.management.base import CommandError

        self._journal_entry()
        with self.assertRaises(CommandError):
            self._call('--company', str(self.company.pk),
                       '--from', '2026-01-01', '--to', '2026-01-31', '--mark-exported')


class SharedFormatHelpersTestCase(TestCase):
    """
    Regression nach dem Verschieben der Feldaufbereitung.

    Zeichensatz, Trennzeichen, Zeilenende sowie `_clean()` und `_quote()`
    liegen seit dem Stammdatenexport der Personenkonten in
    `finanzen.services.datev_common` und werden von beiden Exporten genutzt.
    Der Buchungsstapel muss sie unverändert über sein eigenes Modul anbieten –
    sonst ändert sich sein Verhalten still mit.
    """

    def test_helpers_come_from_the_shared_module(self):
        from finanzen.services import datev_common

        self.assertIs(service._clean, datev_common._clean)
        self.assertIs(service._quote, datev_common._quote)
        self.assertEqual(service.ENCODING, datev_common.ENCODING)
        self.assertEqual(service.DELIMITER, datev_common.DELIMITER)
        self.assertEqual(service.LINE_ENDING, datev_common.LINE_ENDING)

    def test_format_constants_unchanged(self):
        self.assertEqual(service.ENCODING, 'cp1252')
        self.assertEqual(service.DELIMITER, ';')
        self.assertEqual(service.LINE_ENDING, '\r\n')

    def test_clean_still_strips_delimiter_quotes_and_length(self):
        self.assertEqual(service._clean('A;B "C"  D', 60), "A B 'C' D")
        self.assertEqual(service._clean(None, 60), '')
        self.assertEqual(service._clean('abcdef', 3), 'abc')

    def test_quote_still_wraps_in_text_delimiters(self):
        self.assertEqual(service._quote('Text'), '"Text"')
