"""
Tests der Auswertung „Artikelumsatz" (finanzen.services.item_revenue,
finanzen.views).

Schwerpunkte:
- Aggregation über mehrere Belege, Summenzeile cent-genau.
- **Gutschriften mindern den Umsatz** – die Positionen einer Gutschrift sind
  positiv gespeichert, das Vorzeichen setzt erst die Auswertung.
- Positionen ohne Artikelbezug erscheinen als eigene Zeile und fehlen nicht in
  der Summe.
- Ausschluss nicht ausgewählter OPTIONAL-/ALTERNATIVE-Positionen, von Entwürfen
  und stornierten Belegen sowie nicht journalrelevanter Belegarten.
- Mandantentrennung und Warengruppenfilter inklusive Untergruppen.
- Monatsverlauf: Summe der zwölf Monate = Jahresumsatz der Zeile.
- Uneinheitliche Einheiten werden nicht addiert.
- Ein Jahr ohne Belege liefert einen fehlerfreien Leerzustand.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument, SalesDocumentLine
from core.models import Adresse, Item, ItemGroup, Kostenart, Mandant, TaxRate, Unit
from finanzen.services import item_revenue as service


YEAR = 2026
ZERO = Decimal('0.00')


class ItemRevenueTestBase(TestCase):
    """Gemeinsame Testdaten: zwei Mandanten, Warengruppenbaum, drei Artikel."""

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

        self.doc_type_invoice = DocumentType.objects.get(key='invoice')
        self.doc_type_credit = DocumentType.objects.get(key='credit')
        self.doc_type_quote = DocumentType.objects.get(key='quote')
        self.doc_type_delivery = DocumentType.objects.get(key='delivery')

        self.tax_rate = TaxRate.objects.create(
            code="VAT_19", name="19 %", rate=Decimal('0.19'), is_active=True,
        )
        self.kostenart = Kostenart.objects.create(
            name="Erlöse", aufwandskonto="8400",
        )

        self.unit_stk = Unit.objects.create(code="STK", name="Stück", symbol="Stk")
        self.unit_std = Unit.objects.create(code="STD", name="Stunde", symbol="h")

        # Warengruppenbaum: Hauptgruppe mit einer Untergruppe.
        self.main_group = ItemGroup.objects.create(
            code="10", name="Dienstleistung", group_type='MAIN',
        )
        self.sub_group = ItemGroup.objects.create(
            code="1010", name="Wartung", group_type='SUB', parent=self.main_group,
        )
        self.other_group = ItemGroup.objects.create(
            code="20", name="Material", group_type='MAIN',
        )

        self.item_a = self._item("A-001", "Wartungspauschale", self.sub_group)
        self.item_b = self._item("B-001", "Schraube", self.other_group)
        # Artikel direkt an der Hauptgruppe – darf beim Filtern auf die
        # Hauptgruppe nicht verschwinden.
        self.item_c = self._item("C-001", "Beratung", self.main_group)

        self._number = 0

    # -- Hilfsmethoden ------------------------------------------------

    def _item(self, article_no, short_text, group=None, unit=None):
        return Item.objects.create(
            article_no=article_no,
            short_text_1=short_text,
            net_price=Decimal('100.00'),
            purchase_price=Decimal('50.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.kostenart,
            item_group=group,
            unit=unit,
            item_type='SERVICE',
        )

    def _next_number(self, prefix='R'):
        self._number += 1
        return f'{prefix}{YEAR}-{self._number:05d}'

    def _document(self, company=None, document_type=None, issue_date=None,
                  status='SENT'):
        return SalesDocument.objects.create(
            company=company or self.company,
            document_type=document_type or self.doc_type_invoice,
            customer=self.customer,
            number=self._next_number(),
            status=status,
            issue_date=issue_date or date(YEAR, 3, 15),
        )

    def _line(self, document, item=None, net='100.00', quantity='1.0000',
              unit=None, line_type='NORMAL', is_selected=True, position_no=None):
        """
        Belegposition anlegen.

        Die Beträge werden – wie im Produktivcode nach der Neuberechnung –
        direkt gesetzt; die Auswertung liest ausschließlich `line_net`.
        """
        if position_no is None:
            position_no = document.lines.count() + 1
        return SalesDocumentLine.objects.create(
            document=document,
            position_no=position_no,
            line_type=line_type,
            is_selected=is_selected,
            item=item,
            tax_rate=self.tax_rate,
            description=item.short_text_1 if item else "Freie Position",
            quantity=Decimal(quantity),
            unit=unit,
            unit_price_net=Decimal(net),
            line_net=Decimal(net),
        )

    def _report(self, company=None, year=YEAR, group=None, **kwargs):
        return service.build_report(
            company=company or self.company, year=year, group=group, **kwargs
        )

    def _rows_by_key(self, report):
        return {row.key: row for row in report.rows}


class ItemRevenueAggregationTests(ItemRevenueTestBase):
    """Aggregation über mehrere Belege, Summen und Kennzahlen je Artikel."""

    def test_aggregates_across_multiple_documents(self):
        """Ein Artikel auf mehreren Belegen wird zu einer Zeile summiert."""
        first = self._document(issue_date=date(YEAR, 2, 1))
        self._line(first, self.item_a, net='100.00', quantity='1.0000')
        second = self._document(issue_date=date(YEAR, 5, 1))
        self._line(second, self.item_a, net='250.00', quantity='2.0000')

        report = self._report()

        self.assertEqual(len(report.rows), 1)
        row = report.rows[0]
        self.assertEqual(row.item_id, self.item_a.pk)
        self.assertEqual(row.article_no, "A-001")
        self.assertEqual(row.net, Decimal('350.00'))
        self.assertEqual(row.quantity, Decimal('3.0000'))
        self.assertEqual(row.document_count, 2)
        self.assertEqual(row.group_name, "Wartung")

    def test_multiple_lines_of_one_document_count_as_one_document(self):
        """Zwei Positionen desselben Artikels auf einem Beleg = ein Beleg."""
        document = self._document()
        self._line(document, self.item_a, net='100.00')
        self._line(document, self.item_a, net='50.00')

        row = self._report().rows[0]
        self.assertEqual(row.net, Decimal('150.00'))
        self.assertEqual(row.document_count, 1)

    def test_sorted_by_revenue_descending_by_default(self):
        """Standardsortierung: größter Umsatz zuerst."""
        document = self._document()
        self._line(document, self.item_a, net='100.00')
        self._line(document, self.item_b, net='900.00')
        self._line(document, self.item_c, net='400.00')

        report = self._report()
        self.assertEqual(
            [row.article_no for row in report.rows], ["B-001", "C-001", "A-001"]
        )

    def test_sortable_by_quantity_and_documents(self):
        """Menge und Belegzahl sind ebenfalls Sortierkriterien."""
        first = self._document()
        self._line(first, self.item_a, net='900.00', quantity='1.0000')
        second = self._document()
        self._line(second, self.item_b, net='100.00', quantity='9.0000')
        third = self._document()
        self._line(third, self.item_b, net='10.00', quantity='1.0000')

        by_quantity = self._report(sort=service.SORT_QUANTITY)
        self.assertEqual(by_quantity.rows[0].article_no, "B-001")

        by_documents = self._report(sort=service.SORT_DOCUMENTS)
        self.assertEqual(by_documents.rows[0].article_no, "B-001")

        ascending = self._report(sort=service.SORT_NET, descending=False)
        self.assertEqual(ascending.rows[0].article_no, "B-001")

    def test_total_matches_sum_of_all_included_lines(self):
        """Die Summenzeile entspricht cent-genau der Summe der Positionen."""
        document = self._document()
        self._line(document, self.item_a, net='33.33')
        self._line(document, self.item_b, net='66.67')
        self._line(document, None, net='0.01')

        report = self._report()

        self.assertEqual(report.total_net, Decimal('100.01'))
        self.assertEqual(
            sum((row.net for row in report.rows), ZERO), report.total_net
        )

    def test_share_percent_sums_up_to_hundred(self):
        """Der Anteil am Gesamtumsatz wird je Zeile ausgewiesen."""
        document = self._document()
        self._line(document, self.item_a, net='750.00')
        self._line(document, self.item_b, net='250.00')

        rows = {row.article_no: row for row in self._report().rows}
        self.assertEqual(rows["A-001"].share_percent, Decimal('75.00'))
        self.assertEqual(rows["B-001"].share_percent, Decimal('25.00'))

    def test_share_percent_is_none_when_total_is_zero(self):
        """Ein Anteil an einem Gesamtumsatz von 0 ist keine Kennzahl."""
        invoice = self._document()
        self._line(invoice, self.item_a, net='100.00')
        credit = self._document(document_type=self.doc_type_credit)
        self._line(credit, self.item_b, net='100.00')

        report = self._report()
        self.assertEqual(report.total_net, ZERO)
        self.assertTrue(all(row.share_percent is None for row in report.rows))

    def test_items_without_revenue_are_absent(self):
        """Artikel ohne Umsatz im Zeitraum erscheinen nicht in der Rangliste."""
        document = self._document()
        self._line(document, self.item_a, net='100.00')

        report = self._report()
        self.assertEqual([row.item_id for row in report.rows], [self.item_a.pk])


class ItemRevenueCreditNoteTests(ItemRevenueTestBase):
    """Gutschriften mindern den Umsatz – der wichtigste Punkt der Auswertung."""

    def test_credit_note_reduces_revenue(self):
        """
        Eine Gutschrift über einen Artikel verringert dessen Umsatz.

        Die Positionen der Gutschrift sind positiv gespeichert; würde die
        Auswertung sie ungeprüft aufsummieren, käme 1.300 statt 700 heraus.
        """
        invoice = self._document()
        self._line(invoice, self.item_a, net='1000.00', quantity='10.0000')
        credit = self._document(document_type=self.doc_type_credit)
        credit_line = self._line(credit, self.item_a, net='300.00', quantity='3.0000')

        # Gegenprobe: die Position selbst ist positiv gespeichert.
        self.assertEqual(credit_line.line_net, Decimal('300.00'))

        row = self._report().rows[0]
        self.assertEqual(row.net, Decimal('700.00'))
        self.assertEqual(row.quantity, Decimal('7.0000'))
        self.assertEqual(row.document_count, 2)

    def test_document_type_with_both_flags_counts_as_credit_note(self):
        """
        Ein Belegtyp mit `is_invoice` und `is_correction` ist eine Gutschrift.

        Dieselbe Reihenfolge wie in `journal.get_document_kind()`.
        """
        correction = DocumentType.objects.create(
            key='invoice_correction', name='Rechnungskorrektur', prefix='RK',
            is_invoice=True, is_correction=True, is_active=True,
        )
        invoice = self._document()
        self._line(invoice, self.item_a, net='500.00')
        document = self._document(document_type=correction)
        self._line(document, self.item_a, net='200.00')

        self.assertEqual(self._report().rows[0].net, Decimal('300.00'))

    def test_negative_annual_revenue_is_sorted_and_flagged(self):
        """Ein Artikel mit negativem Jahresumsatz steht hinten und ist erkennbar."""
        invoice = self._document()
        self._line(invoice, self.item_a, net='1000.00')
        self._line(invoice, self.item_b, net='100.00')
        credit = self._document(document_type=self.doc_type_credit)
        self._line(credit, self.item_b, net='400.00')

        report = self._report()
        self.assertEqual([row.article_no for row in report.rows], ["A-001", "B-001"])
        negative = report.rows[1]
        self.assertEqual(negative.net, Decimal('-300.00'))
        self.assertTrue(negative.is_negative)
        self.assertFalse(report.rows[0].is_negative)


class ItemRevenueScopeTests(ItemRevenueTestBase):
    """Welche Belege und Positionen überhaupt in die Auswertung gehören."""

    def test_unselected_optional_and_alternative_lines_are_excluded(self):
        """Nicht ausgewählte optionale/alternative Positionen zählen nicht."""
        document = self._document()
        self._line(document, self.item_a, net='100.00', line_type='NORMAL')
        self._line(document, self.item_a, net='50.00',
                   line_type='OPTIONAL', is_selected=True)
        self._line(document, self.item_a, net='999.00',
                   line_type='OPTIONAL', is_selected=False)
        self._line(document, self.item_a, net='888.00',
                   line_type='ALTERNATIVE', is_selected=False)

        report = self._report()
        self.assertEqual(report.total_net, Decimal('150.00'))
        self.assertEqual(report.rows[0].net, Decimal('150.00'))

    def test_drafts_and_cancelled_documents_are_excluded(self):
        """Entwürfe und stornierte Belege fließen nicht ein."""
        finalized = self._document(status='SENT')
        self._line(finalized, self.item_a, net='100.00')
        draft = self._document(status='DRAFT')
        self._line(draft, self.item_a, net='500.00')
        cancelled = self._document(status='CANCELLED')
        self._line(cancelled, self.item_a, net='700.00')

        report = self._report()
        self.assertEqual(report.total_net, Decimal('100.00'))
        self.assertEqual(report.rows[0].document_count, 1)

    def test_non_journal_document_types_are_excluded(self):
        """Angebote, Aufträge und Lieferscheine sind kein Umsatz."""
        invoice = self._document()
        self._line(invoice, self.item_a, net='100.00')
        for document_type in (self.doc_type_quote, self.doc_type_delivery):
            document = self._document(document_type=document_type)
            self._line(document, self.item_a, net='999.00')

        self.assertEqual(self._report().total_net, Decimal('100.00'))

    def test_other_years_are_excluded(self):
        """Nur Belege des gewählten Jahres fließen ein."""
        current = self._document(issue_date=date(YEAR, 12, 31))
        self._line(current, self.item_a, net='100.00')
        previous = self._document(issue_date=date(YEAR - 1, 12, 31))
        self._line(previous, self.item_a, net='500.00')
        following = self._document(issue_date=date(YEAR + 1, 1, 1))
        self._line(following, self.item_a, net='700.00')

        self.assertEqual(self._report().total_net, Decimal('100.00'))
        self.assertEqual(self._report(year=YEAR - 1).total_net, Decimal('500.00'))

    def test_only_selected_company_is_included(self):
        """Mandantentrennung – geprüft mit Daten aus zwei Mandanten."""
        own = self._document(company=self.company)
        self._line(own, self.item_a, net='100.00')
        foreign = self._document(company=self.other_company)
        self._line(foreign, self.item_a, net='900.00')

        self.assertEqual(self._report(company=self.company).total_net, Decimal('100.00'))
        self.assertEqual(
            self._report(company=self.other_company).total_net, Decimal('900.00')
        )

    def test_report_without_company_is_empty(self):
        """Ohne Mandant (kein Mandant angelegt) bleibt die Auswertung leer."""
        report = service.build_report(company=None, year=YEAR)
        self.assertFalse(report.has_data)
        self.assertEqual(report.total_net, ZERO)


class ItemRevenueWithoutItemTests(ItemRevenueTestBase):
    """Freie Positionen ohne Artikelbezug."""

    def test_lines_without_item_form_their_own_row(self):
        """Positionen ohne Artikel erscheinen als Zeile „Ohne Artikelbezug"."""
        document = self._document()
        self._line(document, self.item_a, net='100.00')
        self._line(document, None, net='40.00', quantity='2.0000')
        self._line(document, None, net='60.00', quantity='3.0000')

        report = self._report()
        rows = self._rows_by_key(report)

        self.assertIn(service.NO_ITEM_KEY, rows)
        free = rows[service.NO_ITEM_KEY]
        self.assertEqual(free.label, service.NO_ITEM_LABEL)
        self.assertIsNone(free.item_id)
        self.assertFalse(free.has_item)
        self.assertEqual(free.net, Decimal('100.00'))
        self.assertEqual(free.quantity, Decimal('5.0000'))

    def test_lines_without_item_are_part_of_the_total(self):
        """Ohne die freie Zeile stimmte die Summe der Auswertung nicht."""
        document = self._document()
        self._line(document, self.item_a, net='100.00')
        self._line(document, None, net='25.00')

        report = self._report()
        self.assertEqual(report.total_net, Decimal('125.00'))
        self.assertEqual(sum((row.net for row in report.rows), ZERO), Decimal('125.00'))

    def test_credit_note_without_item_reduces_the_free_row(self):
        """Auch die Sammelzeile kennt das Vorzeichen der Gutschrift."""
        invoice = self._document()
        self._line(invoice, None, net='100.00')
        credit = self._document(document_type=self.doc_type_credit)
        self._line(credit, None, net='30.00')

        self.assertEqual(self._report().rows[0].net, Decimal('70.00'))


class ItemRevenueGroupFilterTests(ItemRevenueTestBase):
    """Warengruppenfilter inklusive Untergruppen."""

    def setUp(self):
        super().setUp()
        document = self._document()
        self._line(document, self.item_a, net='100.00')   # Untergruppe „Wartung"
        self._line(document, self.item_c, net='200.00')   # direkt an Hauptgruppe
        self._line(document, self.item_b, net='400.00')   # andere Hauptgruppe
        self._line(document, None, net='50.00')           # ohne Artikelbezug

    def test_without_group_filter_everything_is_included(self):
        report = self._report()
        self.assertEqual(report.total_net, Decimal('750.00'))
        self.assertEqual(len(report.rows), 4)

    def test_main_group_includes_subgroup_items(self):
        """Bei einer Hauptgruppe zählen die Artikel ihrer Untergruppen mit."""
        report = self._report(group=self.main_group)
        self.assertEqual(
            sorted(row.article_no for row in report.rows), ["A-001", "C-001"]
        )
        self.assertEqual(report.total_net, Decimal('300.00'))

    def test_subgroup_filter_is_exact(self):
        report = self._report(group=self.sub_group)
        self.assertEqual([row.article_no for row in report.rows], ["A-001"])
        self.assertEqual(report.total_net, Decimal('100.00'))

    def test_group_filter_excludes_lines_without_item(self):
        """Eine Position ohne Artikel gehört zu keiner Warengruppe."""
        report = self._report(group=self.other_group)
        self.assertEqual([row.article_no for row in report.rows], ["B-001"])


class ItemRevenueUnitTests(ItemRevenueTestBase):
    """Einheiten werden nicht stillschweigend zusammengeworfen."""

    def test_uniform_unit_is_reported_with_the_quantity(self):
        document = self._document()
        self._line(document, self.item_a, net='100.00', quantity='2.0000',
                   unit=self.unit_stk)
        self._line(document, self.item_a, net='100.00', quantity='3.0000',
                   unit=self.unit_stk)

        row = self._report().rows[0]
        self.assertEqual(row.quantity, Decimal('5.0000'))
        self.assertEqual(row.unit_label, "Stk")
        self.assertFalse(row.quantity_is_mixed)

    def test_mixed_units_are_not_added(self):
        """Eine Summe aus Stunden und Stück ist keine Menge."""
        document = self._document()
        self._line(document, self.item_a, net='100.00', quantity='2.0000',
                   unit=self.unit_stk)
        self._line(document, self.item_a, net='100.00', quantity='3.0000',
                   unit=self.unit_std)

        row = self._report().rows[0]
        self.assertIsNone(row.quantity)
        self.assertTrue(row.quantity_is_mixed)
        # Der Umsatz bleibt davon unberührt – nur die Menge ist uneinheitlich.
        self.assertEqual(row.net, Decimal('200.00'))

    def test_missing_unit_counts_as_its_own_variant(self):
        """„5 Stk" und „5 ohne Einheit" sind nicht dieselbe Menge."""
        document = self._document()
        self._line(document, self.item_a, net='100.00', quantity='2.0000',
                   unit=self.unit_stk)
        self._line(document, self.item_a, net='100.00', quantity='3.0000', unit=None)

        self.assertTrue(self._report().rows[0].quantity_is_mixed)

    def test_lines_without_any_unit_keep_their_quantity(self):
        document = self._document()
        self._line(document, self.item_a, net='100.00', quantity='2.0000', unit=None)

        row = self._report().rows[0]
        self.assertEqual(row.quantity, Decimal('2.0000'))
        self.assertEqual(row.unit_label, "")
        self.assertFalse(row.quantity_is_mixed)

    def test_unit_without_symbol_falls_back_to_code(self):
        unit = Unit.objects.create(code="PAU", name="Pauschal", symbol="")
        document = self._document()
        self._line(document, self.item_a, net='100.00', quantity='1.0000', unit=unit)

        self.assertEqual(self._report().rows[0].unit_label, "PAU")


class ItemRevenueMonthlyTests(ItemRevenueTestBase):
    """Monatsverlauf eines Artikels."""

    def test_months_sum_up_to_the_annual_revenue(self):
        january = self._document(issue_date=date(YEAR, 1, 10))
        self._line(january, self.item_a, net='100.00')
        march = self._document(issue_date=date(YEAR, 3, 20))
        self._line(march, self.item_a, net='250.00')

        series = service.monthly_revenue(self.company, YEAR, self.item_a)

        self.assertEqual(len(series.net_by_month), 12)
        self.assertEqual(series.net_by_month[0], Decimal('100.00'))
        self.assertEqual(series.net_by_month[2], Decimal('250.00'))
        # Monate ohne Umsatz erscheinen als 0 und werden nicht ausgelassen.
        self.assertEqual(series.net_by_month[1], ZERO)
        self.assertEqual(series.total_net, Decimal('350.00'))
        self.assertEqual(series.total_net, self._report().rows[0].net)

    def test_credit_note_reduces_its_month(self):
        invoice = self._document(issue_date=date(YEAR, 4, 1))
        self._line(invoice, self.item_a, net='500.00')
        credit = self._document(
            document_type=self.doc_type_credit, issue_date=date(YEAR, 4, 20)
        )
        self._line(credit, self.item_a, net='800.00')

        series = service.monthly_revenue(self.company, YEAR, self.item_a)
        self.assertEqual(series.net_by_month[3], Decimal('-300.00'))

    def test_monthly_series_for_lines_without_item(self):
        document = self._document(issue_date=date(YEAR, 7, 5))
        self._line(document, None, net='60.00')
        self._line(document, self.item_a, net='999.00')

        series = service.monthly_revenue(self.company, YEAR, None)
        self.assertEqual(series.net_by_month[6], Decimal('60.00'))
        self.assertEqual(series.total_net, Decimal('60.00'))
        self.assertEqual(series.label, service.NO_ITEM_LABEL)

    def test_monthly_series_respects_company_and_scope(self):
        own = self._document(issue_date=date(YEAR, 2, 1))
        self._line(own, self.item_a, net='100.00')
        foreign = self._document(
            company=self.other_company, issue_date=date(YEAR, 2, 1)
        )
        self._line(foreign, self.item_a, net='900.00')
        draft = self._document(issue_date=date(YEAR, 2, 1), status='DRAFT')
        self._line(draft, self.item_a, net='700.00')

        series = service.monthly_revenue(self.company, YEAR, self.item_a)
        self.assertEqual(series.net_by_month[1], Decimal('100.00'))

    def test_chart_data_covers_twelve_months(self):
        series = service.monthly_revenue(self.company, YEAR, self.item_a)
        data = series.chart_data
        self.assertEqual(len(data['labels']), 12)
        self.assertEqual(len(data['values']), 12)
        self.assertTrue(all(isinstance(value, float) for value in data['values']))
        self.assertIn('"labels"', series.chart_data_json)


class ItemRevenueEmptyYearTests(ItemRevenueTestBase):
    """Leerzustände."""

    def test_year_without_documents_is_empty_but_valid(self):
        report = self._report(year=YEAR - 1)
        self.assertFalse(report.has_data)
        self.assertEqual(report.rows, [])
        self.assertEqual(report.total_net, ZERO)
        self.assertEqual(report.total_document_count, 0)

    def test_monthly_series_of_an_empty_year_is_all_zero(self):
        series = service.monthly_revenue(self.company, YEAR - 1, self.item_a)
        self.assertEqual(series.net_by_month, [ZERO] * 12)
        self.assertEqual(series.total_net, ZERO)


class ResolveSortTests(TestCase):
    """Der Sortierschlüssel kommt aus der URL und wird auf eine Whitelist abgebildet."""

    def test_default_is_revenue_descending(self):
        self.assertEqual(service.resolve_sort(None, None), (service.SORT_NET, True))

    def test_unknown_sort_falls_back(self):
        self.assertEqual(
            service.resolve_sort('drop table', 'asc'), (service.SORT_NET, True)
        )

    def test_ascending_direction_is_honoured(self):
        self.assertEqual(
            service.resolve_sort(service.SORT_QUANTITY, 'asc'),
            (service.SORT_QUANTITY, False),
        )


class ItemRevenueViewTests(ItemRevenueTestBase):
    """Views: Seite, Filterstand in der URL und nachgeladener Monatsverlauf."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='tester', password='secret')
        self.client.force_login(self.user)
        self.url = reverse('finanzen:item_revenue')

        document = self._document()
        self._line(document, self.item_a, net='100.00', unit=self.unit_stk)
        self._line(document, None, net='25.00')

    def test_page_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_page_renders_ranking(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'finanzen/artikelumsatz.html')
        self.assertContains(response, "A-001")
        self.assertContains(response, service.NO_ITEM_LABEL)
        # Hinweis auf die Datengrundlage steht über der Tabelle.
        self.assertContains(response, "Steuerungsgröße")
        self.assertContains(response, "Gutschriften mindern den Umsatz")

    def test_article_number_links_into_item_management(self):
        response = self.client.get(self.url)
        self.assertContains(response, f"{reverse('item_management')}?q=A-001")

    def test_filters_apply_and_stay_in_the_url(self):
        response = self.client.get(self.url, {
            'company': self.other_company.pk,
            'year': YEAR,
            'group': self.sub_group.pk,
        })
        self.assertEqual(response.status_code, 200)
        report = response.context['report']
        self.assertEqual(report.company, self.other_company)
        self.assertEqual(report.group, self.sub_group)
        self.assertFalse(report.has_data)
        # Sortierlinks tragen den Filterstand weiter.
        self.assertIn(
            f'company={self.other_company.pk}', response.context['sort_links']['net']['url']
        )
        self.assertIn(f'group={self.sub_group.pk}', response.context['sort_links']['net']['url'])

    def test_sorting_via_url(self):
        response = self.client.get(self.url, {'sort': 'quantity', 'dir': 'asc'})
        self.assertEqual(response.context['report'].sort, service.SORT_QUANTITY)
        self.assertFalse(response.context['report'].descending)

    def test_empty_year_renders_empty_state(self):
        response = self.client.get(self.url, {'year': YEAR - 1})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['report'].has_data)
        self.assertContains(response, "keine Rechnungen oder Gutschriften")

    def test_page_renders_when_the_total_is_zero(self):
        """Rechnung und Gutschrift heben sich auf – der Anteil ist dann keine Zahl."""
        credit = self._document(document_type=self.doc_type_credit)
        self._line(credit, self.item_a, net='100.00')
        self._line(credit, None, net='25.00')

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['report'].total_net, ZERO)

    def test_negative_row_is_marked_in_the_table(self):
        credit = self._document(document_type=self.doc_type_credit)
        self._line(credit, self.item_a, net='400.00')

        response = self.client.get(self.url)
        self.assertContains(response, 'artikelumsatz-row-negative')

    def test_monthly_history_is_not_rendered_upfront(self):
        """Der Monatsverlauf wird erst beim Aufklappen geladen."""
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn('hx-trigger="click once"', content)
        # Die Übersicht selbst zeichnet noch kein Diagramm.
        self.assertNotIn('artikelumsatz-chart', content)

    def test_page_does_not_query_per_row(self):
        """
        Die Abfragezahl der Seite hängt nicht von der Zahl der Zeilen ab –
        die Aggregation erfolgt in der Datenbank.
        """
        baseline = self._page_query_count()

        document = self._document()
        for index in range(10):
            item = self._item(f'X-{index:03d}', f'Extra {index}', self.other_group)
            self._line(document, item, net='10.00')

        response = self.client.get(self.url)
        self.assertGreater(len(response.context['report'].rows), 10)
        self.assertEqual(self._page_query_count(), baseline)

    def _page_query_count(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as captured:
            self.client.get(self.url)
        return len(captured)

    def test_monthly_endpoint_returns_the_series(self):
        response = self.client.get(
            reverse('finanzen:item_revenue_months', args=[self.item_a.pk]),
            {'company': self.company.pk, 'year': YEAR},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'finanzen/partials/artikelumsatz_monate.html')
        self.assertEqual(
            response.context['series'].total_net, Decimal('100.00')
        )
        self.assertContains(response, 'artikelumsatz-chart')

    def test_monthly_endpoint_for_lines_without_item(self):
        response = self.client.get(
            reverse('finanzen:item_revenue_months', args=[service.NO_ITEM_KEY]),
            {'company': self.company.pk, 'year': YEAR},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['series'].total_net, Decimal('25.00'))

    def test_monthly_endpoint_rejects_unknown_keys(self):
        response = self.client.get(
            reverse('finanzen:item_revenue_months', args=['kein-artikel']),
            {'company': self.company.pk, 'year': YEAR},
        )
        self.assertEqual(response.status_code, 404)

    def test_monthly_endpoint_404_for_missing_item(self):
        response = self.client.get(
            reverse('finanzen:item_revenue_months', args=[999999]),
            {'company': self.company.pk, 'year': YEAR},
        )
        self.assertEqual(response.status_code, 404)

    def test_item_management_links_to_the_report(self):
        response = self.client.get(reverse('item_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('finanzen:item_revenue'))

    def test_finanzen_home_links_to_the_report(self):
        response = self.client.get(reverse('finanzen:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('finanzen:item_revenue'))
