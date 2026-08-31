"""
Tests für das Finanzen-Dashboard (finanzen.services.dashboard, finanzen.views).

Schwerpunkte:
- Monatsaggregation beider Seiten, Jahressumme = Kennzahl.
- Netto gegen Brutto, Belegdatum gegen Zahldatum.
- Gutschriften mindern die Einnahmen des Monats, in den sie fallen.
- Mandantentrennung: nur Belege des gewählten Mandanten fließen ein.
- Ausgaben nur aus freigegebenen und bezahlten Eingangsrechnungen.
- Offene Posten beider Seiten als Stichtagsbild, mit Summe, Anzahl und
  Sortierung nach Fälligkeit.
- Ein Jahr ohne Bewegung liefert ein fehlerfreies Dashboard mit Nullwerten.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Kostenart, Mandant
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.services import dashboard as service
from lieferantenwesen.models import InvoiceIn


YEAR = 2026


class DashboardTestBase(TestCase):
    """Gemeinsame Testdaten: zwei Mandanten, Kunde, Lieferant."""

    def setUp(self):
        self.company = Mandant.objects.create(
            name="A-Mandant GmbH", adresse="Str. 1", plz="12345", ort="Stadt",
        )
        self.other_company = Mandant.objects.create(
            name="B-Mandant GmbH", adresse="Str. 2", plz="12345", ort="Stadt",
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
        self.doc_type_credit = DocumentType.objects.get(key='credit')
        self.doc_type_quote = DocumentType.objects.get(key='quote')
        self.kostenart = Kostenart.objects.create(
            name="Bürobedarf", aufwandskonto="4930",
        )
        self._number = 0

    # -- Hilfsmethoden ------------------------------------------------

    def _next_number(self, prefix='R'):
        self._number += 1
        return f'{prefix}{YEAR}-{self._number:05d}'

    def _document(self, company=None, document_type=None, issue_date=None,
                  status='SENT', gross='1190.00', due_date=None, paid_on=None,
                  number=None):
        """Verkaufsbeleg anlegen (ohne Journaleintrag)."""
        document = SalesDocument.objects.create(
            company=company or self.company,
            document_type=document_type or self.doc_type_invoice,
            customer=self.customer,
            number=number or self._next_number(),
            status=status,
            issue_date=issue_date or date(YEAR, 1, 15),
            due_date=due_date,
            total_gross=Decimal(gross),
        )
        if paid_on:
            document.mark_as_paid(paid_on)
        return document

    def _journal_entry(self, company=None, kind='INVOICE', document_date=None,
                       net_19='1000.00', net_7='0.00', net_0='0.00',
                       paid_on=None, document=None):
        """
        Journaleintrag anlegen – die Einnahmenseite liest ausschließlich hier.

        Gutschriften werden wie im Produktivcode mit negativen Beträgen
        gebucht.
        """
        company = company or self.company
        document_date = document_date or date(YEAR, 1, 15)
        sign = Decimal('-1') if kind == 'CREDIT_NOTE' else Decimal('1')
        net_19 = Decimal(net_19) * sign
        net_7 = Decimal(net_7) * sign
        net_0 = Decimal(net_0) * sign
        tax = (net_19 * Decimal('0.19') + net_7 * Decimal('0.07')).quantize(Decimal('0.01'))
        gross = net_0 + net_7 + net_19 + tax

        if document is None:
            document = self._document(
                company=company,
                document_type=self.doc_type_credit if kind == 'CREDIT_NOTE' else self.doc_type_invoice,
                issue_date=document_date,
                gross=str(gross),
                paid_on=paid_on,
            )

        return OutgoingInvoiceJournalEntry.objects.create(
            company=company,
            document=document,
            document_number=document.number,
            document_date=document_date,
            document_kind=kind,
            customer_name="Kunde",
            net_0=net_0, net_7=net_7, net_19=net_19,
            tax_amount=tax,
            gross_amount=gross,
        )

    def _incoming_invoice(self, company=None, status='APPROVED', invoice_date=None,
                          net='200.00', tax='38.00', payment_date=None,
                          due_date=None, invoice_no=None):
        return InvoiceIn.objects.create(
            invoice_no=invoice_no or self._next_number('ER'),
            invoice_date=invoice_date or date(YEAR, 1, 10),
            company=company or self.company,
            supplier=self.supplier,
            status=status,
            net_amount=Decimal(net),
            tax_amount=Decimal(tax),
            gross_amount=Decimal(net) + Decimal(tax),
            payment_date=payment_date,
            due_date=due_date,
            cost_type_main=self.kostenart,
        )


class MonthlyIncomeTestCase(DashboardTestBase):
    """Monatsaggregation der Einnahmen"""

    def test_series_has_twelve_months_and_zero_gaps(self):
        self._journal_entry(document_date=date(YEAR, 3, 5), net_19='1000.00')

        series = service.monthly_income(self.company, YEAR)

        self.assertEqual(len(series), 12)
        self.assertEqual(series[2], Decimal('1000.00'))
        self.assertEqual(
            [value for index, value in enumerate(series) if index != 2],
            [Decimal('0.00')] * 11,
        )

    def test_entries_of_same_month_are_summed(self):
        self._journal_entry(document_date=date(YEAR, 3, 5), net_19='1000.00')
        self._journal_entry(document_date=date(YEAR, 3, 25), net_19='250.50')

        series = service.monthly_income(self.company, YEAR)

        self.assertEqual(series[2], Decimal('1250.50'))

    def test_other_years_are_ignored(self):
        self._journal_entry(document_date=date(YEAR - 1, 3, 5), net_19='999.00')

        series = service.monthly_income(self.company, YEAR)

        self.assertEqual(sum(series), Decimal('0.00'))

    def test_net_sums_all_tax_rates_without_vat(self):
        self._journal_entry(
            document_date=date(YEAR, 4, 1),
            net_0='100.00', net_7='200.00', net_19='300.00',
        )

        series = service.monthly_income(self.company, YEAR, service.VALUE_BASIS_NET)

        self.assertEqual(series[3], Decimal('600.00'))

    def test_gross_includes_vat(self):
        entry = self._journal_entry(document_date=date(YEAR, 4, 1), net_19='1000.00')

        series = service.monthly_income(self.company, YEAR, service.VALUE_BASIS_GROSS)

        self.assertEqual(series[3], Decimal('1190.00'))
        self.assertEqual(series[3], entry.gross_amount)

    def test_credit_note_reduces_income_of_its_month(self):
        self._journal_entry(document_date=date(YEAR, 5, 2), net_19='1000.00')
        self._journal_entry(
            document_date=date(YEAR, 5, 20), kind='CREDIT_NOTE', net_19='400.00',
        )

        series = service.monthly_income(self.company, YEAR)

        self.assertEqual(series[4], Decimal('600.00'))

    def test_draft_document_without_journal_entry_is_not_income(self):
        # Ein Entwurf hat keinen Journaleintrag – er darf nicht auftauchen,
        # auch wenn er einen Bruttobetrag trägt.
        self._document(status='DRAFT', issue_date=date(YEAR, 6, 1), gross='5000.00')

        series = service.monthly_income(self.company, YEAR)

        self.assertEqual(sum(series), Decimal('0.00'))

    def test_only_selected_company_is_counted(self):
        self._journal_entry(document_date=date(YEAR, 2, 1), net_19='1000.00')
        self._journal_entry(
            company=self.other_company, document_date=date(YEAR, 2, 1), net_19='7777.00',
        )

        series = service.monthly_income(self.company, YEAR)
        other = service.monthly_income(self.other_company, YEAR)

        self.assertEqual(series[1], Decimal('1000.00'))
        self.assertEqual(other[1], Decimal('7777.00'))


class IncomeByPaymentDateTestCase(DashboardTestBase):
    """Einnahmen nach Zahldatum"""

    def test_payment_month_wins_over_document_month(self):
        self._journal_entry(
            document_date=date(YEAR, 1, 10),
            net_19='1000.00',
            paid_on=date(YEAR, 3, 4),
        )

        by_document = service.monthly_income(
            self.company, YEAR, date_basis=service.DATE_BASIS_DOCUMENT,
        )
        by_payment = service.monthly_income(
            self.company, YEAR, date_basis=service.DATE_BASIS_PAYMENT,
        )

        self.assertEqual(by_document[0], Decimal('1000.00'))
        self.assertEqual(by_payment[0], Decimal('0.00'))
        self.assertEqual(by_payment[2], Decimal('1000.00'))

    def test_unpaid_entries_do_not_appear(self):
        self._journal_entry(document_date=date(YEAR, 1, 10), net_19='1000.00')

        by_payment = service.monthly_income(
            self.company, YEAR, date_basis=service.DATE_BASIS_PAYMENT,
        )

        self.assertEqual(sum(by_payment), Decimal('0.00'))


class MonthlyExpensesTestCase(DashboardTestBase):
    """Monatsaggregation der Ausgaben"""

    def test_series_has_twelve_months_and_zero_gaps(self):
        self._incoming_invoice(invoice_date=date(YEAR, 2, 3), net='500.00', tax='95.00')

        series = service.monthly_expenses(self.company, YEAR)

        self.assertEqual(len(series), 12)
        self.assertEqual(series[1], Decimal('500.00'))
        self.assertEqual(sum(series), Decimal('500.00'))

    def test_gross_includes_vat(self):
        self._incoming_invoice(invoice_date=date(YEAR, 2, 3), net='500.00', tax='95.00')

        series = service.monthly_expenses(
            self.company, YEAR, value_basis=service.VALUE_BASIS_GROSS,
        )

        self.assertEqual(series[1], Decimal('595.00'))

    def test_only_approved_and_paid_invoices_count(self):
        self._incoming_invoice(status='APPROVED', invoice_date=date(YEAR, 2, 3), net='100.00', tax='19.00')
        self._incoming_invoice(
            status='PAID', invoice_date=date(YEAR, 2, 4), net='50.00', tax='9.50',
            payment_date=date(YEAR, 2, 10),
        )
        for status in ('DRAFT', 'EXTRACTED', 'IN_REVIEW', 'REJECTED'):
            self._incoming_invoice(status=status, invoice_date=date(YEAR, 2, 5), net='9999.00', tax='0.00')

        series = service.monthly_expenses(self.company, YEAR)

        self.assertEqual(series[1], Decimal('150.00'))

    def test_missing_amounts_count_as_zero(self):
        invoice = self._incoming_invoice(invoice_date=date(YEAR, 7, 1), net='100.00', tax='19.00')
        InvoiceIn.objects.filter(pk=invoice.pk).update(net_amount=None, gross_amount=None)

        net_series = service.monthly_expenses(self.company, YEAR)
        gross_series = service.monthly_expenses(
            self.company, YEAR, value_basis=service.VALUE_BASIS_GROSS,
        )

        self.assertEqual(net_series[6], Decimal('0.00'))
        self.assertEqual(gross_series[6], Decimal('0.00'))

    def test_payment_date_basis_ignores_invoices_without_payment_date(self):
        self._incoming_invoice(
            status='PAID', invoice_date=date(YEAR, 1, 5), net='100.00', tax='19.00',
            payment_date=date(YEAR, 4, 20),
        )
        self._incoming_invoice(status='APPROVED', invoice_date=date(YEAR, 1, 6), net='300.00', tax='57.00')

        by_payment = service.monthly_expenses(
            self.company, YEAR, date_basis=service.DATE_BASIS_PAYMENT,
        )

        self.assertEqual(by_payment[3], Decimal('100.00'))
        self.assertEqual(sum(by_payment), Decimal('100.00'))

    def test_only_selected_company_is_counted(self):
        self._incoming_invoice(invoice_date=date(YEAR, 2, 3), net='100.00', tax='19.00')
        self._incoming_invoice(
            company=self.other_company, invoice_date=date(YEAR, 2, 3), net='800.00', tax='0.00',
        )

        series = service.monthly_expenses(self.company, YEAR)

        self.assertEqual(sum(series), Decimal('100.00'))


class DashboardTotalsTestCase(DashboardTestBase):
    """Kennzahlen und ihr Verhältnis zu den Diagrammlinien"""

    def test_totals_match_series_and_result_is_the_difference(self):
        self._journal_entry(document_date=date(YEAR, 1, 15), net_19='1000.33')
        self._journal_entry(document_date=date(YEAR, 6, 15), net_19='2000.67')
        self._incoming_invoice(invoice_date=date(YEAR, 3, 1), net='500.11', tax='95.02')

        data = service.build_dashboard(self.company, YEAR)

        self.assertEqual(data.total_income, sum(data.income_by_month))
        self.assertEqual(data.total_expenses, sum(data.expense_by_month))
        self.assertEqual(data.total_income, Decimal('3001.00'))
        self.assertEqual(data.total_expenses, Decimal('500.11'))
        self.assertEqual(data.result, Decimal('2500.89'))
        self.assertEqual(data.result, data.total_income - data.total_expenses)

    def test_negative_result_when_expenses_exceed_income(self):
        self._incoming_invoice(invoice_date=date(YEAR, 3, 1), net='500.00', tax='95.00')

        data = service.build_dashboard(self.company, YEAR)

        self.assertEqual(data.result, Decimal('-500.00'))

    def test_year_without_movement_is_empty_but_valid(self):
        data = service.build_dashboard(self.company, YEAR)

        self.assertEqual(data.income_by_month, [Decimal('0.00')] * 12)
        self.assertEqual(data.expense_by_month, [Decimal('0.00')] * 12)
        self.assertEqual(data.total_income, Decimal('0.00'))
        self.assertEqual(data.total_expenses, Decimal('0.00'))
        self.assertEqual(data.result, Decimal('0.00'))
        self.assertFalse(data.has_movement)
        self.assertEqual(data.receivables.entries, [])
        self.assertEqual(data.payables.entries, [])

    def test_basis_label_names_the_active_basis(self):
        self.assertEqual(
            service.basis_label(service.VALUE_BASIS_NET, service.DATE_BASIS_DOCUMENT),
            'Netto, nach Belegdatum',
        )
        self.assertEqual(
            service.basis_label(service.VALUE_BASIS_GROSS, service.DATE_BASIS_PAYMENT),
            'Brutto, nach Zahldatum',
        )


class OpenReceivablesTestCase(DashboardTestBase):
    """Offene Posten Rechnungsausgang"""

    def setUp(self):
        super().setUp()
        self.today = date(YEAR, 6, 30)

    def test_only_unpaid_journal_relevant_documents_of_the_company(self):
        open_invoice = self._document(due_date=date(YEAR, 6, 1), gross='100.00')
        self._document(status='DRAFT', due_date=date(YEAR, 6, 1), gross='200.00')
        self._document(status='CANCELLED', due_date=date(YEAR, 6, 1), gross='300.00')
        self._document(
            document_type=self.doc_type_quote, due_date=date(YEAR, 6, 1), gross='400.00',
        )
        self._document(company=self.other_company, due_date=date(YEAR, 6, 1), gross='500.00')
        self._document(due_date=date(YEAR, 6, 2), gross='600.00', paid_on=date(YEAR, 6, 3))

        items = service.open_receivables(self.company, today=self.today)

        self.assertEqual([doc.pk for doc in items.entries], [open_invoice.pk])
        self.assertEqual(items.count, 1)
        self.assertEqual(items.total, Decimal('100.00'))

    def test_credit_notes_are_open_items_too(self):
        credit = self._document(
            document_type=self.doc_type_credit, due_date=date(YEAR, 5, 1), gross='-100.00',
        )

        items = service.open_receivables(self.company, today=self.today)

        self.assertIn(credit.pk, [doc.pk for doc in items.entries])

    def test_sorted_by_due_date_ascending_with_overdue_days(self):
        late = self._document(due_date=date(YEAR, 4, 1), gross='100.00')
        middle = self._document(due_date=date(YEAR, 5, 1), gross='100.00')
        future = self._document(due_date=date(YEAR, 12, 1), gross='100.00')
        without_due = self._document(due_date=None, gross='100.00')

        items = service.open_receivables(self.company, today=self.today)

        self.assertEqual(
            [doc.pk for doc in items.entries],
            [late.pk, middle.pk, future.pk, without_due.pk],
        )
        self.assertEqual(items.entries[0].days_overdue, 90)
        self.assertEqual(items.entries[2].days_overdue, 0)
        self.assertEqual(items.entries[3].days_overdue, 0)
        self.assertEqual(items.overdue_count, 2)

    def test_total_and_count_cover_all_items_not_only_the_shown_ones(self):
        for index in range(18):
            self._document(due_date=date(YEAR, 4, 1) + timedelta(days=index), gross='10.00')

        items = service.open_receivables(self.company, today=self.today)

        self.assertEqual(len(items.entries), service.OPEN_ITEM_LIMIT)
        self.assertEqual(items.count, 18)
        self.assertEqual(items.total, Decimal('180.00'))
        self.assertTrue(items.truncated)

    def test_paid_document_disappears_from_the_list(self):
        document = self._document(due_date=date(YEAR, 5, 1), gross='100.00')
        self.assertEqual(service.open_receivables(self.company, today=self.today).count, 1)

        document.mark_as_paid(date(YEAR, 5, 20))

        items = service.open_receivables(self.company, today=self.today)
        self.assertEqual(items.count, 0)
        self.assertEqual(items.total, Decimal('0.00'))

    def test_list_does_not_query_per_row(self):
        for _ in range(5):
            self._document(due_date=date(YEAR, 5, 1), gross='10.00')

        # Eine Abfrage für die Summen, eine für die Zeilen – die angezeigten
        # Beziehungen sind über select_related mitgeladen.
        with self.assertNumQueries(2):
            items = service.open_receivables(self.company, today=self.today)
            [
                (doc.customer.name, doc.document_type.key, doc.days_overdue)
                for doc in items.entries
            ]


class OpenPayablesTestCase(DashboardTestBase):
    """Offene Posten Rechnungseingang"""

    def setUp(self):
        super().setUp()
        self.today = date(YEAR, 6, 30)

    def test_only_approved_invoices_without_payment_date(self):
        open_invoice = self._incoming_invoice(
            status='APPROVED', due_date=date(YEAR, 6, 1), net='100.00', tax='19.00',
        )
        self._incoming_invoice(
            status='PAID', due_date=date(YEAR, 6, 1), net='200.00', tax='38.00',
            payment_date=date(YEAR, 6, 5),
        )
        self._incoming_invoice(status='IN_REVIEW', due_date=date(YEAR, 6, 1), net='300.00', tax='57.00')
        self._incoming_invoice(
            company=self.other_company, status='APPROVED', due_date=date(YEAR, 6, 1),
            net='400.00', tax='76.00',
        )

        items = service.open_payables(self.company, today=self.today)

        self.assertEqual([inv.pk for inv in items.entries], [open_invoice.pk])
        self.assertEqual(items.count, 1)
        self.assertEqual(items.total, Decimal('119.00'))

    def test_sorted_by_due_date_ascending_with_overdue_days(self):
        late = self._incoming_invoice(due_date=date(YEAR, 4, 1))
        soon = self._incoming_invoice(due_date=date(YEAR, 7, 1))

        items = service.open_payables(self.company, today=self.today)

        self.assertEqual([inv.pk for inv in items.entries], [late.pk, soon.pk])
        self.assertEqual(items.entries[0].days_overdue, 90)
        self.assertEqual(items.entries[1].days_overdue, 0)
        self.assertEqual(items.overdue_count, 1)

    def test_paid_invoice_disappears_from_the_list(self):
        invoice = self._incoming_invoice(due_date=date(YEAR, 4, 1))
        self.assertEqual(service.open_payables(self.company, today=self.today).count, 1)

        invoice.mark_as_paid(date(YEAR, 5, 2))

        self.assertEqual(service.open_payables(self.company, today=self.today).count, 0)

    def test_list_does_not_query_per_row(self):
        for _ in range(5):
            self._incoming_invoice(due_date=date(YEAR, 5, 1))

        with self.assertNumQueries(2):
            items = service.open_payables(self.company, today=self.today)
            [(inv.supplier.name, inv.days_overdue) for inv in items.entries]


class DashboardViewTestCase(DashboardTestBase):
    """Seite, Filterleiste und Diagrammdaten"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('finanzen', 'f@example.com', 'geheim1234')
        self.client.login(username='finanzen', password='geheim1234')
        self.url = reverse('finanzen:home')
        self.current_year = date.today().year

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_defaults_to_first_company_current_year_net_and_document_date(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.context['dashboard']
        self.assertEqual(data.company, self.company)  # erster Mandant nach Name
        self.assertEqual(data.year, self.current_year)
        self.assertEqual(data.value_basis, service.VALUE_BASIS_NET)
        self.assertEqual(data.date_basis, service.DATE_BASIS_DOCUMENT)
        self.assertContains(response, 'Netto, nach Belegdatum')

    def test_chart_data_has_twelve_points_per_line(self):
        response = self.client.get(self.url)

        chart = response.context['chart_data']
        self.assertEqual(len(chart['labels']), 12)
        self.assertEqual(len(chart['income']), 12)
        self.assertEqual(len(chart['expenses']), 12)

    def test_filters_from_the_url_are_applied(self):
        self._journal_entry(
            company=self.other_company,
            document_date=date(self.current_year, 3, 1),
            net_19='1000.00',
        )

        response = self.client.get(self.url, {
            'company': self.other_company.pk,
            'year': self.current_year,
            'value_basis': service.VALUE_BASIS_GROSS,
            'date_basis': service.DATE_BASIS_DOCUMENT,
        })

        data = response.context['dashboard']
        self.assertEqual(data.company, self.other_company)
        self.assertEqual(data.value_basis, service.VALUE_BASIS_GROSS)
        self.assertEqual(data.total_income, Decimal('1190.00'))
        self.assertContains(response, 'Brutto, nach Belegdatum')
        # Bei Brutto ist das Ergebnis keine Ertragsgröße – Hinweis erforderlich.
        self.assertContains(response, 'Umsatzsteuer')

    def test_invalid_filter_values_fall_back_to_the_defaults(self):
        response = self.client.get(self.url, {'company': 'abc', 'year': 'kein-jahr'})

        self.assertEqual(response.status_code, 200)
        data = response.context['dashboard']
        self.assertEqual(data.company, self.company)
        self.assertEqual(data.year, self.current_year)

    def test_open_items_ignore_the_year_filter(self):
        # Offene Posten aus dem Vorjahr – sie gehören ins Stichtagsbild.
        document = self._document(
            issue_date=date(self.current_year - 1, 2, 1),
            due_date=date(self.current_year - 1, 3, 1),
            gross='100.00',
        )
        invoice = self._incoming_invoice(
            invoice_date=date(self.current_year - 1, 2, 1),
            due_date=date(self.current_year - 1, 3, 1),
        )

        response = self.client.get(self.url, {'year': self.current_year})

        data = response.context['dashboard']
        self.assertEqual(data.receivables.count, 1)
        self.assertEqual(data.payables.count, 1)
        self.assertContains(response, 'unabhängig vom Jahresfilter')
        # Beide Listen sind gerendert, überfällige Zeilen hervorgehoben.
        self.assertContains(response, document.number)
        self.assertContains(response, invoice.invoice_no)
        self.assertContains(response, 'table-row-overdue')

    def test_empty_lists_show_a_clean_empty_state(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'Keine offenen Posten im Rechnungsausgang.')
        self.assertContains(response, 'Keine offenen Posten im Rechnungseingang.')

    def test_chart_library_is_loaded_only_on_this_page(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'chart.js@4.4.1')

        other = self.client.get(reverse('auftragsverwaltung:home'))
        self.assertNotContains(other, 'chart.js@')

    def test_accounting_hint_is_still_present(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Zur Buchhaltung')
