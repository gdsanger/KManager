"""
Tests für #1195: Umsatzsteuer je Steuersatz auf die Nettosumme

Deckt ab:
- Der Fall aus den Reproduktionsschritten (7 Positionen, 19 %, 200,00 netto)
- Gemischte Steuersätze werden je Satz getrennt gerechnet
- Positionsrabatte: Steuer weiterhin auf dem rabattierten Netto
- Einzelposition bleibt unverändert
- Determinismus bei mehrfacher Neuberechnung
- Positionssummen == Belegsummen (line_tax/line_gross)
- Nicht einbezogene OPTIONAL/ALTERNATIVE-Positionen
- Druckkontext, Journal, Vertrags-Rechnungslauf
- Management-Command (Trockenlauf + Korrektur)
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from auftragsverwaltung.models import (
    Contract,
    ContractLine,
    DocumentType,
    NumberRange,
    SalesDocument,
    SalesDocumentLine,
)
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from auftragsverwaltung.services import DocumentCalculationService
from auftragsverwaltung.services.contract_billing import ContractBillingService
from core.models import Adresse, Mandant, PaymentTerm, TaxRate, Unit
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry
from finanzen.services.journal import create_journal_entry


class TaxRoundingTestBase(TestCase):
    """Gemeinsame Testdaten für die Steuerrundungs-Tests"""

    def setUp(self):
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin',
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            country_code='DE',
            debitor_number='10001',
        )
        self.doc_type = DocumentType.objects.get(key='invoice')
        self.tax_19 = TaxRate.objects.create(code='VAT_19', name='19% USt', rate=Decimal('0.1900'))
        self.tax_7 = TaxRate.objects.create(code='VAT_7', name='7% USt', rate=Decimal('0.0700'))
        self.tax_0 = TaxRate.objects.create(code='VAT_0', name='0% USt', rate=Decimal('0.0000'))
        self.unit = Unit.objects.create(code='STD', name='Stunde', symbol='Std')

        self.document = self._create_document()

    def _create_document(self, number='R26-00001', **kwargs):
        defaults = {
            'company': self.company,
            'document_type': self.doc_type,
            'customer': self.customer,
            'number': number,
            'status': 'DRAFT',
            'issue_date': date(2026, 2, 6),
            'due_date': date(2026, 2, 20),
        }
        defaults.update(kwargs)
        return SalesDocument.objects.create(**defaults)

    def _line(self, quantity, unit_price='25.00', position_no=None, document=None,
              tax_rate=None, discount='0.00', is_discountable=True,
              line_type='NORMAL', is_selected=True):
        document = document or self.document
        if position_no is None:
            position_no = document.lines.count() + 1
        return SalesDocumentLine.objects.create(
            document=document,
            position_no=position_no,
            line_type=line_type,
            is_selected=is_selected,
            short_text_1=f'Position {position_no}',
            description=f'Position {position_no}',
            unit=self.unit,
            quantity=Decimal(quantity),
            unit_price_net=Decimal(unit_price),
            discount=Decimal(discount),
            is_discountable=is_discountable,
            tax_rate=tax_rate or self.tax_19,
        )

    def _build_reproduction_document(self, document=None):
        """7 Positionen à 25,00 €/Std: 5 x 0,5 + 1 x 1,5 + 1 x 4 = 200,00 € netto"""
        document = document or self.document
        for _ in range(5):
            self._line('0.5000', document=document)
        self._line('1.5000', document=document)
        self._line('4.0000', document=document)
        return document

    def _assert_lines_match_totals(self, document):
        """Positionssummen müssen cent-genau den Belegsummen entsprechen"""
        lines = [
            line for line in document.lines.all() if line.is_included_in_totals()
        ]
        self.assertEqual(
            sum((line.line_net for line in lines), Decimal('0.00')),
            document.total_net,
        )
        self.assertEqual(
            sum((line.line_tax for line in lines), Decimal('0.00')),
            document.total_tax,
        )
        self.assertEqual(
            sum((line.line_gross for line in lines), Decimal('0.00')),
            document.total_gross,
        )


class ReproductionCaseTest(TaxRoundingTestBase):
    """Der konkrete Fall aus der Fehlermeldung"""

    def test_seven_lines_at_19_percent(self):
        self._build_reproduction_document()

        result = DocumentCalculationService.recalculate(self.document)

        self.assertEqual(result.total_net, Decimal('200.00'))
        self.assertEqual(result.total_tax, Decimal('38.00'))
        self.assertEqual(result.total_gross, Decimal('238.00'))

    def test_document_fields_are_persisted(self):
        self._build_reproduction_document()

        DocumentCalculationService.recalculate(self.document, persist=True)
        self.document.refresh_from_db()

        self.assertEqual(self.document.total_net, Decimal('200.00'))
        self.assertEqual(self.document.total_tax, Decimal('38.00'))
        self.assertEqual(self.document.total_gross, Decimal('238.00'))
        self._assert_lines_match_totals(self.document)

    def test_rounding_difference_lands_on_largest_line(self):
        """Die Differenz von -0,03 € liegt auf der betragsstärksten Position"""
        self._build_reproduction_document()

        DocumentCalculationService.recalculate(self.document, persist=True)

        lines = list(self.document.lines.order_by('position_no'))
        # Positionen 1-5: je 12,50 netto -> 2,38 Steuer (unverändert gerundet)
        for line in lines[:5]:
            self.assertEqual(line.line_net, Decimal('12.50'))
            self.assertEqual(line.line_tax, Decimal('2.38'))
        # Position 6: 37,50 netto -> 7,13 Steuer
        self.assertEqual(lines[5].line_net, Decimal('37.50'))
        self.assertEqual(lines[5].line_tax, Decimal('7.13'))
        # Position 7 ist die betragsstärkste und trägt die Differenz:
        # 19,00 - 0,03 = 18,97
        self.assertEqual(lines[6].line_net, Decimal('100.00'))
        self.assertEqual(lines[6].line_tax, Decimal('18.97'))
        self.assertEqual(lines[6].line_gross, Decimal('118.97'))


class TaxPerRateTest(TaxRoundingTestBase):
    """Steuer je Steuersatz auf der Nettosumme"""

    def test_mixed_tax_rates_are_calculated_separately(self):
        # 19 %: 5 x 12,50 = 62,50 -> 11,88 (exakt 11,875, HALF_UP)
        for _ in range(5):
            self._line('0.5000')
        # 7 %: 3 x 12,50 = 37,50 -> 2,63 (exakt 2,625, HALF_UP)
        for _ in range(3):
            self._line('0.5000', tax_rate=self.tax_7)
        # 0 %: 1 x 25,00 = 25,00 -> 0,00
        self._line('1.0000', tax_rate=self.tax_0)

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_net, Decimal('125.00'))
        self.assertEqual(result.total_tax, Decimal('11.88') + Decimal('2.63'))
        self.assertEqual(result.total_gross, Decimal('139.51'))
        self._assert_lines_match_totals(self.document)

    def test_rate_is_grouped_by_value_not_by_tax_rate_record(self):
        """Zwei TaxRate-Sätze mit 19 % bilden eine Gruppe"""
        other_19 = TaxRate.objects.create(
            code='VAT_19_ALT', name='19% USt (alt)', rate=Decimal('0.1900')
        )
        for _ in range(3):
            self._line('0.5000')
        for _ in range(4):
            self._line('0.5000', tax_rate=other_19)

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        # 7 x 12,50 = 87,50 -> 16,625 -> 16,63 (nicht 7 x 2,38 = 16,66)
        self.assertEqual(result.total_net, Decimal('87.50'))
        self.assertEqual(result.total_tax, Decimal('16.63'))
        self._assert_lines_match_totals(self.document)

    def test_tax_matches_rate_times_net_per_rate(self):
        """Akzeptanzkriterium: round(Nettosumme * Satz, 2) == ausgewiesene Steuer"""
        for _ in range(7):
            self._line('0.5000')
        for _ in range(5):
            self._line('0.3000', tax_rate=self.tax_7)

        DocumentCalculationService.recalculate(self.document, persist=True)

        nets = {}
        taxes = {}
        for line in self.document.lines.all():
            rate = line.tax_rate.rate
            nets[rate] = nets.get(rate, Decimal('0.00')) + line.line_net
            taxes[rate] = taxes.get(rate, Decimal('0.00')) + line.line_tax

        for rate, net in nets.items():
            self.assertEqual(
                (net * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                taxes[rate],
                msg=f'Steuer stimmt nicht für Satz {rate}',
            )

    def test_single_line_is_unchanged(self):
        self._line('4.0000')

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_net, Decimal('100.00'))
        self.assertEqual(result.total_tax, Decimal('19.00'))
        self.assertEqual(result.total_gross, Decimal('119.00'))
        line = self.document.lines.get()
        self.assertEqual(line.line_tax, Decimal('19.00'))
        self.assertEqual(line.line_gross, Decimal('119.00'))

    def test_document_without_lines_stays_at_zero(self):
        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_net, Decimal('0.00'))
        self.assertEqual(result.total_tax, Decimal('0.00'))
        self.assertEqual(result.total_gross, Decimal('0.00'))

    def test_credit_note_with_negative_amounts(self):
        """Negative Beträge (Gutschrift) werden genauso je Satz gerechnet"""
        for _ in range(5):
            self._line('-0.5000')
        self._line('-1.5000')
        self._line('-4.0000')

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_net, Decimal('-200.00'))
        self.assertEqual(result.total_tax, Decimal('-38.00'))
        self.assertEqual(result.total_gross, Decimal('-238.00'))
        self._assert_lines_match_totals(self.document)


class DiscountAndSelectionTest(TaxRoundingTestBase):
    """Rabatte und nicht einbezogene Positionen"""

    def test_tax_is_calculated_on_the_discounted_net(self):
        # 7 x (0,5 Std à 25,00 = 12,50) abzgl. 10 % = 11,25 netto je Position
        for _ in range(7):
            self._line('0.5000', discount='10.00')

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_discount, Decimal('8.75'))
        self.assertEqual(result.total_net, Decimal('78.75'))
        # 78,75 * 0,19 = 14,9625 -> 14,96 (positionsweise wären es 7 x 2,14 = 14,98)
        self.assertEqual(result.total_tax, Decimal('14.96'))
        self.assertEqual(result.total_gross, Decimal('93.71'))
        self._assert_lines_match_totals(self.document)

    def test_non_discountable_line_keeps_full_net(self):
        self._line('0.5000', discount='10.00', is_discountable=False)
        self._line('0.5000', discount='10.00')

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        # 12,50 + 11,25 = 23,75 netto
        self.assertEqual(result.total_net, Decimal('23.75'))
        self.assertEqual(result.total_discount, Decimal('1.25'))
        self.assertEqual(result.total_tax, Decimal('4.51'))

    def test_unselected_lines_do_not_count(self):
        for _ in range(5):
            self._line('0.5000')
        self._line('1.5000')
        self._line('4.0000')
        # Nicht ausgewählte Zusatzpositionen
        excluded_optional = self._line('0.5000', line_type='OPTIONAL', is_selected=False)
        excluded_alternative = self._line('8.0000', line_type='ALTERNATIVE', is_selected=False)

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_net, Decimal('200.00'))
        self.assertEqual(result.total_tax, Decimal('38.00'))
        self.assertEqual(result.total_gross, Decimal('238.00'))

        # Ausgeschlossene Positionen behalten ihre eigene, positionsweise
        # gerundete Steuer - sie tragen keine Rundungsdifferenz
        excluded_optional.refresh_from_db()
        excluded_alternative.refresh_from_db()
        self.assertEqual(excluded_optional.line_tax, Decimal('2.38'))
        self.assertEqual(excluded_alternative.line_tax, Decimal('38.00'))
        self._assert_lines_match_totals(self.document)

    def test_selected_optional_line_joins_its_tax_group(self):
        for _ in range(6):
            self._line('0.5000')
        self._line('0.5000', line_type='OPTIONAL', is_selected=True)

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        # 7 x 12,50 = 87,50 -> 16,63
        self.assertEqual(result.total_net, Decimal('87.50'))
        self.assertEqual(result.total_tax, Decimal('16.63'))


class DeterminismTest(TaxRoundingTestBase):
    """Die Verteilung der Rundungsdifferenz muss reproduzierbar sein"""

    def test_repeated_recalculation_is_stable(self):
        self._build_reproduction_document()

        DocumentCalculationService.recalculate(self.document, persist=True)
        first = [
            (line.position_no, line.line_net, line.line_tax, line.line_gross)
            for line in self.document.lines.order_by('position_no')
        ]

        for _ in range(3):
            self.document.refresh_from_db()
            DocumentCalculationService.recalculate(self.document, persist=True)

        again = [
            (line.position_no, line.line_net, line.line_tax, line.line_gross)
            for line in self.document.lines.order_by('position_no')
        ]
        self.assertEqual(first, again)
        self.document.refresh_from_db()
        self.assertEqual(self.document.total_tax, Decimal('38.00'))

    def test_tie_is_broken_by_smallest_position_no(self):
        """Bei gleich hohen Nettobeträgen trägt die kleinste Positionsnummer"""
        for _ in range(7):
            self._line('0.5000')

        DocumentCalculationService.recalculate(self.document, persist=True)

        lines = list(self.document.lines.order_by('position_no'))
        # 87,50 * 0,19 = 16,625 -> 16,63; positionsweise 7 x 2,38 = 16,66
        # Differenz -0,03 auf Position 1
        self.assertEqual(lines[0].line_tax, Decimal('2.35'))
        for line in lines[1:]:
            self.assertEqual(line.line_tax, Decimal('2.38'))
        self._assert_lines_match_totals(self.document)


class PrintContextTest(TaxRoundingTestBase):
    """Der Druckkontext weist je Steuersatz einen passenden Betrag aus"""

    def test_printed_tax_blocks_match_their_net(self):
        for _ in range(5):
            self._line('0.5000')
        self._line('1.5000')
        self._line('4.0000')
        for _ in range(3):
            self._line('0.5000', tax_rate=self.tax_7)

        DocumentCalculationService.recalculate(self.document, persist=True)
        self.document.refresh_from_db()

        context = SalesDocumentInvoiceContextBuilder().build_context(self.document)
        totals = context['totals']

        self.assertEqual(totals['net_19'], Decimal('200.00'))
        self.assertEqual(totals['tax_19'], Decimal('38.00'))
        self.assertEqual(
            (totals['net_19'] * Decimal('0.19')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ),
            totals['tax_19'],
        )
        self.assertEqual(totals['net_7'], Decimal('37.50'))
        self.assertEqual(
            (totals['net_7'] * Decimal('0.07')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ),
            totals['tax_7'],
        )
        self.assertEqual(
            totals['tax_0'] + totals['tax_7'] + totals['tax_19'],
            self.document.total_tax,
        )
        self.assertEqual(totals['gross_total'], self.document.total_gross)


class JournalEntryTest(TaxRoundingTestBase):
    """Der Journaleintrag trägt denselben Steuerbetrag wie der Beleg"""

    def setUp(self):
        super().setUp()
        CompanyAccountingSettings.objects.create(
            company=self.company,
            revenue_account_0='8000',
            revenue_account_7='8100',
            revenue_account_19='8400',
        )

    def test_journal_entry_matches_document_tax(self):
        self._build_reproduction_document()
        DocumentCalculationService.recalculate(self.document, persist=True)
        self.document.refresh_from_db()
        self.document.status = 'SENT'
        self.document.save(update_fields=['status'])

        entry, created = create_journal_entry(self.document)

        self.assertTrue(created)

        self.assertEqual(entry.tax_amount, Decimal('38.00'))
        self.assertEqual(entry.tax_amount, self.document.total_tax)
        self.assertEqual(entry.net_19, Decimal('200.00'))
        self.assertEqual(entry.gross_amount, Decimal('238.00'))
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 1)

    def test_document_without_lines_has_a_supported_effective_rate(self):
        """
        Beleg ohne Positionen: der rechnerische Satz total_tax/total_net muss
        exakt 19 % ergeben, sonst schlägt _amounts_from_totals fehl.
        """
        # Summen so, wie sie der Service jetzt berechnet
        source = self._create_document(number='R26-09999')
        self._build_reproduction_document(document=source)
        DocumentCalculationService.recalculate(source, persist=True)
        source.refresh_from_db()

        document = self._create_document(
            number='R26-00002',
            status='SENT',
            total_net=source.total_net,
            total_tax=source.total_tax,
            total_gross=source.total_gross,
        )

        entry, _created = create_journal_entry(document)

        self.assertEqual(entry.net_19, Decimal('200.00'))
        self.assertEqual(entry.tax_amount, Decimal('38.00'))


class ContractBillingTest(TaxRoundingTestBase):
    """Der Vertrags-Rechnungslauf erbt die korrigierte Berechnung"""

    def setUp(self):
        super().setUp()
        # Der Beleg aus der Basisklasse belegt R26-00001 - der Nummernkreis
        # unten würde dieselbe Nummer erneut vergeben.
        self.document.delete()
        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto',
            net_days=14,
        )
        NumberRange.objects.create(
            company=self.company,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}',
        )
        NumberRange.objects.create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type,
            reset_policy='YEARLY',
            format='R{yy}-{seq:05d}',
        )
        self.contract = Contract.objects.create(
            company=self.company,
            name='Wartungsvertrag',
            customer=self.customer,
            document_type=self.doc_type,
            payment_term=self.payment_term,
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True,
        )

    def _contract_line(self, position_no, quantity):
        return ContractLine.objects.create(
            contract=self.contract,
            position_no=position_no,
            description=f'Leistung {position_no}',
            quantity=Decimal(quantity),
            unit_price_net=Decimal('25.00'),
            tax_rate=self.tax_19,
            is_discountable=True,
        )

    def test_generated_invoice_has_correct_tax(self):
        for position_no in range(1, 6):
            self._contract_line(position_no, '0.5000')
        self._contract_line(6, '1.5000')
        self._contract_line(7, '4.0000')

        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, 'SUCCESS', msg=runs[0].message)
        invoice = runs[0].document
        invoice.refresh_from_db()
        self.assertEqual(invoice.total_net, Decimal('200.00'))
        self.assertEqual(invoice.total_tax, Decimal('38.00'))
        self.assertEqual(invoice.total_gross, Decimal('238.00'))
        self._assert_lines_match_totals(invoice)


class RecalculateCommandTest(TaxRoundingTestBase):
    """Management-Command zum Durchrechnen der Bestandsbelege"""

    def setUp(self):
        super().setUp()
        self._build_reproduction_document()
        # Bestandszustand: positionsweise gerundete Steuer
        SalesDocument.objects.filter(pk=self.document.pk).update(
            total_net=Decimal('200.00'),
            total_tax=Decimal('38.03'),
            total_gross=Decimal('238.03'),
        )
        self.document.refresh_from_db()

    def _call(self, *args):
        out = StringIO()
        call_command('recalculate_document_totals', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_but_writes_nothing(self):
        output = self._call('--dry-run')

        self.assertIn('DRY-RUN', output)
        self.assertIn('R26-00001', output)
        self.assertIn('38.03', output)
        self.assertIn('38.00', output)
        self.assertIn('1 mit geänderten Summen', output)

        self.document.refresh_from_db()
        self.assertEqual(self.document.total_tax, Decimal('38.03'))

    def test_command_fixes_existing_documents(self):
        output = self._call()

        self.assertIn('1 mit geänderten Summen', output)
        self.document.refresh_from_db()
        self.assertEqual(self.document.total_tax, Decimal('38.00'))
        self.assertEqual(self.document.total_gross, Decimal('238.00'))
        self._assert_lines_match_totals(self.document)

    def test_journal_entries_are_left_untouched(self):
        CompanyAccountingSettings.objects.create(
            company=self.company,
            revenue_account_0='8000',
            revenue_account_7='8100',
            revenue_account_19='8400',
        )
        entry = OutgoingInvoiceJournalEntry.objects.create(
            company=self.company,
            document=self.document,
            document_number=self.document.number,
            document_date=self.document.issue_date,
            document_kind='INVOICE',
            customer_name='Kunde GmbH',
            debtor_number='10001',
            net_19=Decimal('200.00'),
            tax_amount=Decimal('38.03'),
            gross_amount=Decimal('238.03'),
            revenue_account_19='8400',
        )

        output = self._call()

        entry.refresh_from_db()
        self.assertEqual(entry.tax_amount, Decimal('38.03'))
        self.assertEqual(entry.gross_amount, Decimal('238.03'))
        self.assertIn('Journaleinträge wurden nicht angefasst', output)

    def test_company_filter_skips_other_mandanten(self):
        other_company = Mandant.objects.create(
            name='Andere GmbH', adresse='Weg 2', plz='11111', ort='Köln'
        )
        output = self._call('--company', str(other_company.pk))

        self.assertIn('0 Beleg(e) geprüft', output)
        self.document.refresh_from_db()
        self.assertEqual(self.document.total_tax, Decimal('38.03'))

    def test_date_range_filter(self):
        output = self._call('--date-from', '2026-01-01', '--date-to', '2026-01-31')
        self.assertIn('0 Beleg(e) geprüft', output)
        self.document.refresh_from_db()
        self.assertEqual(self.document.total_tax, Decimal('38.03'))

        output = self._call('--date-from', '2026-02-01', '--date-to', '2026-02-28')
        self.assertIn('1 mit geänderten Summen', output)
        self.document.refresh_from_db()
        self.assertEqual(self.document.total_tax, Decimal('38.00'))

    def test_invalid_date_is_rejected(self):
        with self.assertRaises(CommandError):
            self._call('--date-from', '06.02.2026')

    def test_unchanged_document_is_not_reported(self):
        DocumentCalculationService.recalculate(self.document, persist=True)

        output = self._call('--dry-run')

        self.assertIn('0 mit geänderten Summen', output)


class UnchangedBehaviourTest(TaxRoundingTestBase):
    """Die Positionsberechnung selbst (Netto/Rabatt) bleibt unverändert"""

    def test_line_amounts_helper_still_rounds_per_line(self):
        line = self._line('0.5000')

        amounts = DocumentCalculationService.calculate_line_amounts(line)

        self.assertEqual(amounts.line_subtotal, Decimal('12.50'))
        self.assertEqual(amounts.line_discount, Decimal('0.00'))
        self.assertEqual(amounts.line_net, Decimal('12.50'))
        # Einzelbetrachtung einer Position: weiterhin positionsweise gerundet
        self.assertEqual(amounts.line_tax, Decimal('2.38'))
        self.assertEqual(amounts.line_gross, Decimal('14.88'))
