"""
Tests für die Umsatz- und Einkaufsauswertung je Geschäftspartner
(finanzen.services.partner_stats sowie die Tabs auf der Kunden- und
Lieferantendetailseite).

Schwerpunkte:
- Gesamt- und 12-Monats-Summe, Monatsreihe inklusive Monat ohne Bewegung.
- Gutschriften mindern Umsatz und Monatswert.
- Zuordnung über den Belegbezug: eine Namensänderung am Kunden verändert die
  Auswertung nicht; Entwürfe (ohne Journaleintrag) fließen nicht ein.
- Lieferantenseite nur mit freigegebenen und bezahlten Eingangsrechnungen.
- Durchschnittliche Zahlungsdauer inklusive des Falls ohne jede Zahlung.
- Offene Posten beider Seiten mit Summe, Anzahl, Sortierung und Überfälligkeit.
- Partner ohne Belege liefert Nullwerte statt eines Fehlers.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Kostenart, Mandant
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.services import partner_stats as service
from lieferantenwesen.models import InvoiceIn


# Fester Stichtag: die Auswertung ist rollierend, die Tests dürfen deshalb
# nicht vom Ausführungstag abhängen.
TODAY = date(2026, 8, 31)


def months_back(months, day=15):
    """Tag im Monat, der `months` Monate vor dem Stichtag liegt."""
    index = TODAY.year * 12 + (TODAY.month - 1) - months
    return date(index // 12, index % 12 + 1, day)


class PartnerStatsTestBase(TestCase):
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
        self.other_customer = Adresse.objects.create(
            adressen_type='KUNDE', name="Anderer Kunde", strasse="Str. 3",
            plz="12345", ort="Stadt", land="Deutschland",
        )
        self.supplier = Adresse.objects.create(
            adressen_type='LIEFERANT', name="Lieferant", strasse="Str. 2",
            plz="12345", ort="Stadt", land="Deutschland",
        )
        self.other_supplier = Adresse.objects.create(
            adressen_type='LIEFERANT', name="Anderer Lieferant", strasse="Str. 4",
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
        return f'{prefix}-{self._number:05d}'

    def _document(self, customer=None, company=None, document_type=None,
                  issue_date=None, status='SENT', gross='1190.00',
                  due_date=None, paid_on=None):
        document = SalesDocument.objects.create(
            company=company or self.company,
            document_type=document_type or self.doc_type_invoice,
            customer=customer or self.customer,
            number=self._next_number(),
            status=status,
            issue_date=issue_date or months_back(1),
            due_date=due_date,
            total_gross=Decimal(gross),
        )
        if paid_on:
            document.mark_as_paid(paid_on)
        return document

    def _journal_entry(self, customer=None, company=None, kind='INVOICE',
                       document_date=None, net_19='1000.00', net_7='0.00',
                       net_0='0.00', paid_on=None, document=None):
        """
        Journaleintrag mit zugehörigem Beleg anlegen.

        Gutschriften werden – wie im Produktivcode – mit negativen Beträgen
        gebucht.
        """
        company = company or self.company
        document_date = document_date or months_back(1)
        sign = Decimal('-1') if kind == 'CREDIT_NOTE' else Decimal('1')
        net_19 = Decimal(net_19) * sign
        net_7 = Decimal(net_7) * sign
        net_0 = Decimal(net_0) * sign
        tax = (net_19 * Decimal('0.19') + net_7 * Decimal('0.07')).quantize(Decimal('0.01'))
        gross = net_0 + net_7 + net_19 + tax

        if document is None:
            document = self._document(
                customer=customer,
                company=company,
                document_type=(
                    self.doc_type_credit if kind == 'CREDIT_NOTE'
                    else self.doc_type_invoice
                ),
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
            customer_name=document.customer.matchkey,
            net_0=net_0, net_7=net_7, net_19=net_19,
            tax_amount=tax,
            gross_amount=gross,
        )

    def _incoming_invoice(self, supplier=None, company=None, status='APPROVED',
                          invoice_date=None, net='200.00', tax='38.00',
                          payment_date=None, due_date=None):
        return InvoiceIn.objects.create(
            invoice_no=self._next_number('ER'),
            invoice_date=invoice_date or months_back(1),
            company=company or self.company,
            supplier=supplier or self.supplier,
            status=status,
            net_amount=Decimal(net),
            tax_amount=Decimal(tax),
            gross_amount=Decimal(net) + Decimal(tax),
            payment_date=payment_date,
            due_date=due_date,
            cost_type_main=self.kostenart,
        )


class MonthWindowTestCase(TestCase):
    """Rollierendes Zeitfenster"""

    def test_window_ends_with_current_month_and_spans_twelve_months(self):
        window = service.month_window(TODAY)

        self.assertEqual(len(window), 12)
        self.assertEqual(window[-1], date(2026, 8, 1))
        self.assertEqual(window[0], date(2025, 9, 1))

    def test_window_crosses_the_turn_of_the_year(self):
        window = service.month_window(date(2026, 2, 10))

        self.assertEqual(window[0], date(2025, 3, 1))
        self.assertEqual(window[-1], date(2026, 2, 1))

    def test_labels_carry_the_year_because_the_window_spans_two(self):
        stats = service.customer_stats(None, today=TODAY)

        self.assertEqual(stats.month_labels[0], 'Sep 25')
        self.assertEqual(stats.month_labels[-1], 'Aug 26')


class CustomerVolumeTestCase(PartnerStatsTestBase):
    """Umsatzkennzahlen und Monatsreihe der Kundenseite"""

    def test_total_covers_all_time_while_series_is_rolling(self):
        self._journal_entry(document_date=months_back(20), net_19='500.00')
        self._journal_entry(document_date=months_back(3), net_19='1000.00')

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('1500.00'))
        self.assertEqual(stats.last_12_months_net, Decimal('1000.00'))

    def test_series_has_twelve_values_and_zero_for_months_without_movement(self):
        self._journal_entry(document_date=months_back(3), net_19='1000.00')

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(len(stats.net_by_month), 12)
        # Index 8 = drei Monate vor dem letzten (aktuellen) Monat.
        self.assertEqual(stats.net_by_month[8], Decimal('1000.00'))
        self.assertEqual(
            [value for index, value in enumerate(stats.net_by_month) if index != 8],
            [Decimal('0.00')] * 11,
        )

    def test_twelve_month_metric_equals_the_sum_of_the_chart(self):
        self._journal_entry(document_date=months_back(11), net_19='100.00')
        self._journal_entry(document_date=months_back(5), net_19='250.55')
        self._journal_entry(document_date=months_back(0), net_19='33.45')

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(sum(stats.net_by_month), stats.last_12_months_net)
        self.assertEqual(stats.last_12_months_net, Decimal('384.00'))

    def test_net_sums_all_tax_rates_without_vat(self):
        self._journal_entry(
            document_date=months_back(2),
            net_0='100.00', net_7='200.00', net_19='300.00',
        )

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('600.00'))

    def test_credit_note_reduces_month_and_total(self):
        self._journal_entry(document_date=months_back(2), net_19='1000.00')
        self._journal_entry(
            document_date=months_back(2), kind='CREDIT_NOTE', net_19='400.00',
        )

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('600.00'))
        self.assertEqual(stats.net_by_month[9], Decimal('600.00'))

    def test_credit_note_can_push_a_month_below_zero(self):
        # Übersteigt die Gutschrift den Monatsumsatz, ist der Monatswert
        # negativ – das Diagramm muss das darstellen können.
        self._journal_entry(
            document_date=months_back(2), kind='CREDIT_NOTE', net_19='400.00',
        )

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.net_by_month[9], Decimal('-400.00'))
        self.assertEqual(stats.chart_data['values'][9], -400.0)

    def test_drafts_without_journal_entry_are_not_revenue(self):
        self._document(status='DRAFT', gross='5000.00')

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('0.00'))

    def test_documents_of_other_customers_are_ignored(self):
        self._journal_entry(customer=self.other_customer, net_19='777.00')

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('0.00'))

    def test_all_companies_count_towards_the_partner_view(self):
        self._journal_entry(company=self.company, net_19='100.00')
        self._journal_entry(company=self.other_company, net_19='400.00')

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('500.00'))

    def test_renaming_the_customer_keeps_the_assignment(self):
        self._journal_entry(net_19='1000.00')

        self.customer.name = "Kunde nach Umfirmierung"
        self.customer.firma = "Neue Firma GmbH"
        self.customer.save()
        # `matchkey` ist eine GeneratedField – der neue Wert entsteht in der
        # Datenbank und muss nachgeladen werden.
        self.customer.refresh_from_db()

        stats = service.customer_stats(self.customer, today=TODAY)

        # Der Snapshot im Journal trägt weiter den alten Namen – die Zuordnung
        # läuft über den Belegbezug und bleibt davon unberührt.
        entry = OutgoingInvoiceJournalEntry.objects.get()
        self.assertNotEqual(entry.customer_name, self.customer.matchkey)
        self.assertEqual(stats.total_net, Decimal('1000.00'))


class SupplierVolumeTestCase(PartnerStatsTestBase):
    """Einkaufskennzahlen und Monatsreihe der Lieferantenseite"""

    def test_total_and_twelve_month_volume(self):
        self._incoming_invoice(invoice_date=months_back(18), net='300.00')
        self._incoming_invoice(invoice_date=months_back(4), net='200.00')

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('500.00'))
        self.assertEqual(stats.last_12_months_net, Decimal('200.00'))
        self.assertEqual(sum(stats.net_by_month), stats.last_12_months_net)

    def test_only_approved_and_paid_invoices_count(self):
        self._incoming_invoice(status='APPROVED', net='100.00')
        self._incoming_invoice(status='PAID', net='200.00',
                               payment_date=months_back(0))
        for status in ('DRAFT', 'EXTRACTED', 'IN_REVIEW', 'REJECTED'):
            self._incoming_invoice(status=status, net='999.00')

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('300.00'))

    def test_missing_net_amount_counts_as_zero(self):
        invoice = self._incoming_invoice(net='150.00')
        invoice.net_amount = None
        invoice.save(update_fields=['net_amount'])

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('0.00'))

    def test_invoices_of_other_suppliers_are_ignored(self):
        self._incoming_invoice(supplier=self.other_supplier, net='500.00')

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('0.00'))

    def test_series_has_zero_for_months_without_movement(self):
        self._incoming_invoice(invoice_date=months_back(6), net='120.00')

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(len(stats.net_by_month), 12)
        self.assertEqual(stats.net_by_month[5], Decimal('120.00'))
        self.assertEqual(sum(stats.net_by_month), Decimal('120.00'))


class AveragePaymentDaysTestCase(PartnerStatsTestBase):
    """Durchschnittliche Zahlungsdauer"""

    def test_customer_average_is_rounded_to_full_days(self):
        issue = months_back(2, day=1)
        self._journal_entry(document_date=issue, paid_on=issue + timedelta(days=10))
        self._journal_entry(document_date=issue, paid_on=issue + timedelta(days=21))

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.average_payment_days, 16)

    def test_customer_without_any_payment_has_no_average(self):
        self._journal_entry(document_date=months_back(2))

        stats = service.customer_stats(self.customer, today=TODAY)

        # Bewusst None und nicht 0: eine 0 würde eine sofortige Zahlung
        # behaupten, wo schlicht nichts bekannt ist.
        self.assertIsNone(stats.average_payment_days)

    def test_customer_payments_older_than_24_months_are_ignored(self):
        old = months_back(30, day=1)
        self._journal_entry(document_date=old, paid_on=old + timedelta(days=90))
        recent = months_back(2, day=1)
        self._journal_entry(document_date=recent, paid_on=recent + timedelta(days=5))

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.average_payment_days, 5)

    def test_supplier_average_uses_payment_and_invoice_date(self):
        invoice_date = months_back(3, day=1)
        self._incoming_invoice(
            status='PAID', invoice_date=invoice_date,
            payment_date=invoice_date + timedelta(days=14),
        )
        self._incoming_invoice(
            status='PAID', invoice_date=invoice_date,
            payment_date=invoice_date + timedelta(days=20),
        )

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(stats.average_payment_days, 17)

    def test_supplier_without_payment_has_no_average(self):
        self._incoming_invoice(status='APPROVED')

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertIsNone(stats.average_payment_days)


class CustomerOpenItemsTestCase(PartnerStatsTestBase):
    """Offene Posten der Kundenseite"""

    def test_sum_count_and_overdue_count(self):
        self._journal_entry(
            document=self._document(
                gross='119.00', due_date=TODAY - timedelta(days=5),
            ),
            net_19='100.00',
        )
        self._journal_entry(
            document=self._document(
                gross='238.00', due_date=TODAY + timedelta(days=10),
            ),
            net_19='200.00',
        )

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.open_count, 2)
        self.assertEqual(stats.open_total_gross, Decimal('357.00'))
        self.assertEqual(stats.open_overdue_count, 1)

    def test_items_are_sorted_by_due_date_and_carry_days_overdue(self):
        late = self._document(due_date=TODAY - timedelta(days=30))
        soon = self._document(due_date=TODAY + timedelta(days=3))

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual([item.pk for item in stats.open_items], [late.pk, soon.pk])
        self.assertEqual(stats.open_items[0].days_overdue, 30)
        self.assertEqual(stats.open_items[1].days_overdue, 0)

    def test_drafts_cancelled_and_paid_documents_are_not_open(self):
        self._document(status='DRAFT')
        self._document(status='CANCELLED')
        self._document(paid_on=TODAY - timedelta(days=1))
        open_document = self._document(due_date=TODAY)

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual([item.pk for item in stats.open_items], [open_document.pk])

    def test_quotes_are_not_open_items(self):
        self._document(document_type=self.doc_type_quote, status='SENT')

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.open_count, 0)

    def test_marking_a_document_as_paid_removes_it(self):
        issue_date = months_back(1, day=1)
        document = self._document(
            gross='119.00', issue_date=issue_date, due_date=TODAY,
        )

        before = service.customer_stats(self.customer, today=TODAY)
        self.assertEqual(before.open_count, 1)
        self.assertIsNone(before.average_payment_days)

        document.mark_as_paid(issue_date + timedelta(days=7))

        after = service.customer_stats(self.customer, today=TODAY)
        self.assertEqual(after.open_count, 0)
        self.assertEqual(after.open_total_gross, Decimal('0.00'))
        self.assertEqual(after.open_items, [])
        self.assertEqual(after.average_payment_days, 7)

    def test_list_is_capped_while_totals_cover_everything(self):
        for offset in range(12):
            self._document(gross='10.00', due_date=TODAY + timedelta(days=offset))

        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(len(stats.open_items), service.OPEN_ITEM_LIMIT)
        self.assertTrue(stats.truncated)
        self.assertEqual(stats.open_count, 12)
        self.assertEqual(stats.open_total_gross, Decimal('120.00'))


class SupplierOpenItemsTestCase(PartnerStatsTestBase):
    """Offene Posten der Lieferantenseite"""

    def test_only_approved_invoices_without_payment_date_are_open(self):
        approved = self._incoming_invoice(
            status='APPROVED', due_date=TODAY + timedelta(days=7),
        )
        self._incoming_invoice(status='PAID', payment_date=TODAY)
        self._incoming_invoice(status='IN_REVIEW')

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual([item.pk for item in stats.open_items], [approved.pk])
        self.assertEqual(stats.open_count, 1)

    def test_sum_is_gross_and_overdue_items_are_counted(self):
        self._incoming_invoice(
            net='100.00', tax='19.00', due_date=TODAY - timedelta(days=4),
        )
        self._incoming_invoice(
            net='200.00', tax='38.00', due_date=TODAY + timedelta(days=4),
        )

        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(stats.open_total_gross, Decimal('357.00'))
        self.assertEqual(stats.open_overdue_count, 1)
        self.assertEqual(stats.open_items[0].days_overdue, 4)


class EmptyPartnerTestCase(PartnerStatsTestBase):
    """Partner ohne jeden Beleg"""

    def test_customer_without_documents_is_all_zero(self):
        stats = service.customer_stats(self.customer, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('0.00'))
        self.assertEqual(stats.last_12_months_net, Decimal('0.00'))
        self.assertEqual(stats.net_by_month, [Decimal('0.00')] * 12)
        self.assertEqual(stats.open_count, 0)
        self.assertEqual(stats.open_total_gross, Decimal('0.00'))
        self.assertIsNone(stats.average_payment_days)
        self.assertFalse(stats.has_movement)

    def test_supplier_without_invoices_is_all_zero(self):
        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(stats.total_net, Decimal('0.00'))
        self.assertEqual(stats.net_by_month, [Decimal('0.00')] * 12)
        self.assertEqual(stats.open_count, 0)
        self.assertFalse(stats.has_movement)

    def test_chart_data_is_json_ready_and_twelve_values_long(self):
        stats = service.supplier_stats(self.supplier, today=TODAY)

        self.assertEqual(len(stats.chart_data['labels']), 12)
        self.assertEqual(stats.chart_data['values'], [0.0] * 12)


class PartnerStatsViewTestCase(PartnerStatsTestBase):
    """Tabs auf der Kunden- und Lieferantendetailseite"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='vermietung', password='geheim123',
        )
        group, _ = Group.objects.get_or_create(name='Vermietung')
        self.user.groups.add(group)
        self.client.login(username='vermietung', password='geheim123')

    def test_customer_detail_shows_revenue_tab_with_figures(self):
        self._journal_entry(document_date=months_back(2), net_19='1000.00')

        response = self.client.get(
            reverse('vermietung:kunde_detail', kwargs={'pk': self.customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tab-id="umsatz"')
        self.assertContains(response, 'Gesamtumsatz (netto)')
        self.assertContains(response, '1000,00')
        self.assertEqual(
            response.context['partner_stats'].total_net, Decimal('1000.00')
        )

    def test_customer_without_documents_renders_a_clean_empty_state(self):
        response = self.client.get(
            reverse('vermietung:kunde_detail', kwargs={'pk': self.customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Keine offenen Posten für diesen Kunden.')
        # Ohne bezahlten Beleg zeigt die Kachel „–" und nicht „0 Tagen".
        self.assertContains(response, 'Zahlt durchschnittlich in')
        self.assertNotContains(response, '0 Tagen')

    def test_customer_detail_links_are_prefiltered_on_the_partner(self):
        response = self.client.get(
            reverse('vermietung:kunde_detail', kwargs={'pk': self.customer.pk})
        )

        list_url = reverse(
            'auftragsverwaltung:document_list', kwargs={'doc_key': 'invoice'}
        )
        self.assertContains(response, f'{list_url}?customer={self.customer.pk}')
        self.assertContains(
            response,
            f'{list_url}?customer={self.customer.pk}&amp;payment_status=overdue',
        )

    def test_supplier_detail_shows_purchase_tab_with_figures(self):
        self._incoming_invoice(invoice_date=months_back(2), net='250.00')

        response = self.client.get(
            reverse('vermietung:lieferant_detail', kwargs={'pk': self.supplier.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tab-id="einkauf"')
        self.assertContains(response, 'Einkaufsvolumen gesamt (netto)')
        self.assertContains(response, '250,00')
        self.assertEqual(
            response.context['partner_stats'].total_net, Decimal('250.00')
        )

    def test_supplier_detail_links_are_prefiltered_on_the_partner(self):
        response = self.client.get(
            reverse('vermietung:lieferant_detail', kwargs={'pk': self.supplier.pk})
        )

        list_url = reverse('lieferantenwesen:invoice_list')
        self.assertContains(response, f'{list_url}?supplier={self.supplier.pk}')

    def test_chart_library_is_loaded_on_both_detail_pages_only(self):
        chart_js = 'chart.js@4.4.1'

        customer_page = self.client.get(
            reverse('vermietung:kunde_detail', kwargs={'pk': self.customer.pk})
        )
        supplier_page = self.client.get(
            reverse('vermietung:lieferant_detail', kwargs={'pk': self.supplier.pk})
        )
        list_page = self.client.get(reverse('vermietung:kunde_list'))

        self.assertContains(customer_page, chart_js)
        self.assertContains(supplier_page, chart_js)
        self.assertNotContains(list_page, chart_js)

    def test_detail_page_does_not_query_per_open_item(self):
        # Zehn offene Posten dürfen nicht zehn zusätzliche Abfragen auslösen:
        # die Auswertung aggregiert in der Datenbank und lädt die Zeilen mit
        # `select_related`.
        for offset in range(3):
            self._journal_entry(
                document=self._document(due_date=TODAY + timedelta(days=offset)),
                document_date=months_back(1),
            )
        url = reverse('vermietung:kunde_detail', kwargs={'pk': self.customer.pk})
        baseline = self._query_count(url)

        for offset in range(3, 10):
            self._journal_entry(
                document=self._document(due_date=TODAY + timedelta(days=offset)),
                document_date=months_back(1),
            )

        self.assertEqual(self._query_count(url), baseline)

    def _query_count(self, url):
        """Abfragen einer Seitenauslieferung zählen."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
        return len(captured)


class SupplierInvoiceListFilterTestCase(PartnerStatsTestBase):
    """Filter der Eingangsrechnungsliste für die Verlinkungen"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='einkauf', password='geheim123',
        )
        group, _ = Group.objects.get_or_create(name='Lieferantenwesen')
        self.user.groups.add(group)
        self.client.login(username='einkauf', password='geheim123')

    def test_supplier_filter_limits_the_list(self):
        mine = self._incoming_invoice(supplier=self.supplier)
        other = self._incoming_invoice(supplier=self.other_supplier)

        response = self.client.get(
            reverse('lieferantenwesen:invoice_list'),
            {'supplier': self.supplier.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, mine.invoice_no)
        self.assertNotContains(response, other.invoice_no)

    def test_payment_open_filter_shows_approved_unpaid_invoices(self):
        open_invoice = self._incoming_invoice(status='APPROVED')
        paid = self._incoming_invoice(status='PAID', payment_date=TODAY)
        in_review = self._incoming_invoice(status='IN_REVIEW')

        response = self.client.get(
            reverse('lieferantenwesen:invoice_list'), {'payment': 'open'},
        )

        self.assertContains(response, open_invoice.invoice_no)
        self.assertNotContains(response, paid.invoice_no)
        self.assertNotContains(response, in_review.invoice_no)

    def test_payment_overdue_filter_needs_a_due_date_in_the_past(self):
        overdue = self._incoming_invoice(
            status='APPROVED', due_date=date.today() - timedelta(days=1),
        )
        upcoming = self._incoming_invoice(
            status='APPROVED', due_date=date.today() + timedelta(days=5),
        )

        response = self.client.get(
            reverse('lieferantenwesen:invoice_list'), {'payment': 'overdue'},
        )

        self.assertContains(response, overdue.invoice_no)
        self.assertNotContains(response, upcoming.invoice_no)
