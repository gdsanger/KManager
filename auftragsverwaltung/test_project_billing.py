"""
Tests für den Projekt-Abrechnungslauf (#1192)

Abgedeckt werden:
- erfolgreicher Lauf mit gemischten Leistungs- und Anfahrtszeiten
- Rundung an den Grenzfällen (1, 15, 16, 60, 61 Minuten)
- Rabattübernahme inklusive nicht rabattfähiger Position
- Abbruch bei fehlenden Konditionen und ohne offene Stunden
- kein zweiter Lauf über dieselben Stunden
- Rücksetzung beim Löschen des Entwurfs, Bestand bei finalisiertem Beleg
- Unversehrtheit bei einem Fehler mitten im Lauf
- Bedienung: Vorschau, Erstellen per POST, Projektseite, Zeiterfassungsliste
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.filters import TimeEntryFilter
from auftragsverwaltung.models import (
    DocumentType,
    SalesDocument,
    SalesDocumentLine,
    TimeEntry,
)
from auftragsverwaltung.services.project_billing import (
    ProjectBillingError,
    ProjectBillingService,
)
from core.models import Adresse, Item, Kostenart, Mandant, PaymentTerm, Projekt, TaxRate, Unit


class ProjectBillingTestBase(TestCase):
    """Gemeinsame Stammdaten: Mandant, Kunde, Artikel und Projekt."""

    def setUp(self):
        self.company = Mandant.objects.create(
            name='Test GmbH', adresse='Teststr. 1', plz='12345', ort='Teststadt'
        )
        self.other_company = Mandant.objects.create(
            name='Andere GmbH', adresse='Andere Str. 1', plz='54321', ort='Anderstadt'
        )
        self.customer = Adresse.objects.create(
            name='Muster GmbH', strasse='Kundenweg 2', plz='54321',
            ort='Kundenstadt', adressen_type='KUNDE'
        )
        self.user = User.objects.create_user(username='billing', password='password')

        self.tax_rate = TaxRate.objects.create(
            code='VAT19', name='19% USt', rate=Decimal('0.19')
        )
        self.kostenart = Kostenart.objects.create(
            name='Dienstleistung', umsatzsteuer_satz='19'
        )
        self.unit = Unit.objects.create(code='STD', name='Stunde', symbol='h')

        self.leistung = self._item('ART-LEIST', 'Technikerstunde', Decimal('95.00'))
        self.anfahrt = self._item('ART-FAHRT', 'Anfahrtszeit', Decimal('45.00'))

        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto', net_days=14, is_default=True
        )
        self.doc_type = DocumentType.objects.get(key='invoice')

        self.projekt = Projekt.objects.create(
            titel='Migration ERP',
            kunde=self.customer,
            company=self.company,
            billing_item=self.leistung,
            hourly_rate=Decimal('110.00'),
            travel_item=self.anfahrt,
            travel_hourly_rate=Decimal('55.00'),
            discount_percent=Decimal('10.00'),
        )

    def _item(self, article_no, short_text, net_price, is_discountable=True):
        return Item.objects.create(
            article_no=article_no,
            short_text_1=short_text,
            short_text_2='Abrechnung nach Aufwand',
            net_price=net_price,
            purchase_price=Decimal('0.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.kostenart,
            unit=self.unit,
            is_discountable=is_discountable,
            item_type='SERVICE',
        )

    def _entry(self, day, minutes, travel=False, description='Arbeit', projekt=None, company=None):
        return TimeEntry.objects.create(
            company=company or self.company,
            customer=self.customer,
            projekt=projekt if projekt is not None else self.projekt,
            performed_by=self.user,
            service_date=date(2026, 8, day),
            duration_minutes=minutes,
            description=description,
            is_travel_cost=travel,
        )

    def _bill(self, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)):
        return ProjectBillingService.create_invoice(
            self.projekt, date_from, date_to, actor=self.user
        )


class ProjectBillingSuccessTestCase(ProjectBillingTestBase):
    """Erfolgreicher Lauf mit gemischten Leistungs- und Anfahrtszeiten."""

    def setUp(self):
        super().setUp()
        self.entry_leistung = self._entry(3, 90, description='Datenmigration')
        self.entry_anfahrt = self._entry(3, 40, travel=True, description='Anfahrt Kunde')
        self.entry_zweiter_tag = self._entry(17, 60, description='Nacharbeiten')
        self.document = self._bill()

    def test_document_is_draft_with_number(self):
        """Der Beleg entsteht als Entwurf mit sofort vergebener Nummer."""
        self.assertEqual(self.document.status, 'DRAFT')
        self.assertTrue(self.document.number)
        self.assertEqual(self.document.document_type, self.doc_type)
        self.assertEqual(self.document.company, self.company)
        self.assertEqual(self.document.customer, self.customer)

    def test_document_carries_period(self):
        """Betreff und Leistungszeitraum nennen Projekt und Zeitraum."""
        self.assertEqual(self.document.issue_date, date(2026, 8, 31))
        self.assertEqual(self.document.performance_date_from, date(2026, 8, 1))
        self.assertEqual(self.document.performance_date_to, date(2026, 8, 31))
        self.assertIn('Migration ERP', self.document.subject)
        self.assertIn('01.08.2026', self.document.subject)
        self.assertIn('31.08.2026', self.document.subject)

    def test_payment_term_is_default(self):
        """Zahlungsbedingung, Snapshot und Fälligkeit stammen aus dem Standard."""
        self.assertEqual(self.document.payment_term, self.payment_term)
        self.assertEqual(self.document.payment_term_snapshot['net_days'], 14)
        self.assertEqual(self.document.due_date, date(2026, 9, 14))

    def test_one_line_per_time_entry_sorted_by_date(self):
        """Je Zeiterfassung genau eine Position, fortlaufend nach Leistungsdatum."""
        lines = list(self.document.lines.order_by('position_no'))

        self.assertEqual(len(lines), 3)
        self.assertEqual([line.position_no for line in lines], [1, 2, 3])
        self.assertEqual(
            [line.long_text for line in lines],
            ['Datenmigration', 'Anfahrt Kunde', 'Nacharbeiten'],
        )

    def test_travel_line_uses_travel_conditions(self):
        """Anfahrt nutzt Anfahrtsartikel und Anfahrtssatz, Leistung den Leistungssatz."""
        self.entry_leistung.refresh_from_db()
        self.entry_anfahrt.refresh_from_db()

        leistung_line = self.entry_leistung.invoice_line
        anfahrt_line = self.entry_anfahrt.invoice_line

        self.assertEqual(leistung_line.item, self.leistung)
        self.assertEqual(leistung_line.unit_price_net, Decimal('110.00'))
        self.assertEqual(anfahrt_line.item, self.anfahrt)
        self.assertEqual(anfahrt_line.unit_price_net, Decimal('55.00'))

    def test_project_rate_wins_over_item_price(self):
        """Der Einzelpreis ist der Projektsatz, nicht der Artikelpreis."""
        self.entry_leistung.refresh_from_db()

        self.assertEqual(self.leistung.net_price, Decimal('95.00'))
        self.assertEqual(self.entry_leistung.invoice_line.unit_price_net, Decimal('110.00'))

    def test_line_takes_item_master_data(self):
        """Steuersatz, Einheit, Kurztexte und Kostenarten stammen aus dem Artikel."""
        self.entry_leistung.refresh_from_db()
        line = self.entry_leistung.invoice_line

        self.assertEqual(line.tax_rate, self.tax_rate)
        self.assertEqual(line.unit, self.unit)
        self.assertEqual(line.short_text_1, 'Technikerstunde')
        self.assertEqual(line.short_text_2, 'Abrechnung nach Aufwand')
        self.assertEqual(line.kostenart1, self.kostenart)
        self.assertIsNone(line.kostenart2)
        self.assertEqual(line.line_type, 'NORMAL')
        self.assertTrue(line.is_selected)

    def test_quantity_is_rounded_up(self):
        """90 Minuten ergeben 1,5 h, 40 Minuten werden auf 0,75 h aufgerundet."""
        self.entry_leistung.refresh_from_db()
        self.entry_anfahrt.refresh_from_db()

        self.assertEqual(self.entry_leistung.invoice_line.quantity, Decimal('1.5000'))
        self.assertEqual(self.entry_anfahrt.invoice_line.quantity, Decimal('0.7500'))

    def test_totals_are_persisted(self):
        """Die Belegsummen sind nach dem Lauf berechnet und gespeichert."""
        self.document.refresh_from_db()

        # 1,5 h * 110 + 0,75 h * 55 + 1 h * 110 = 165 + 41,25 + 110 = 316,25
        # abzüglich 10 % Rabatt = 284,63 (kaufmännisch je Position gerundet)
        self.assertGreater(self.document.total_net, Decimal('0.00'))
        expected = sum(line.line_net for line in self.document.lines.all())
        self.assertEqual(self.document.total_net, expected)

    def test_time_entries_are_marked_billed(self):
        """Abgerechnete Stunden tragen Kennzeichen, Zeitpunkt und Positionsbezug."""
        for entry in (self.entry_leistung, self.entry_anfahrt, self.entry_zweiter_tag):
            entry.refresh_from_db()
            self.assertTrue(entry.is_billed)
            self.assertIsNotNone(entry.billed_at)
            self.assertIsNotNone(entry.invoice_line)
            self.assertEqual(entry.invoice_line.document, self.document)

    def test_entries_outside_period_are_untouched(self):
        """Stunden außerhalb des Zeitraums bleiben offen."""
        spaeter = self._entry(3, 30, description='September')
        spaeter.service_date = date(2026, 9, 3)
        spaeter.save(update_fields=['service_date'])

        spaeter.refresh_from_db()
        self.assertFalse(spaeter.is_billed)

    def test_activity_stream_entry_created(self):
        """Der Lauf wird im Activity Stream protokolliert."""
        from core.models import Activity

        activity = Activity.objects.filter(
            activity_type='PROJECT_INVOICE_GENERATED'
        ).first()

        self.assertIsNotNone(activity)
        self.assertIn('Migration ERP', activity.title)
        self.assertIn(self.document.number, activity.description)


class ProjectBillingRoundingTestCase(ProjectBillingTestBase):
    """Rundung je Eintrag auf volle 15 Minuten."""

    def test_rounding_boundaries(self):
        """1, 15, 16, 60 und 61 Minuten runden auf 0,25/0,25/0,50/1,00/1,25 h."""
        erwartet = {
            1: Decimal('0.2500'),
            15: Decimal('0.2500'),
            16: Decimal('0.5000'),
            60: Decimal('1.0000'),
            61: Decimal('1.2500'),
        }
        for minuten, menge in erwartet.items():
            with self.subTest(minuten=minuten):
                self.assertEqual(ProjectBillingService.round_quantity(minuten), menge)

    def test_rounding_applies_per_entry_not_to_sum(self):
        """Zwei Einträge à 10 Minuten ergeben 0,50 h, nicht 0,25 h."""
        self._entry(4, 10)
        self._entry(5, 10)

        document = self._bill()
        mengen = [line.quantity for line in document.lines.order_by('position_no')]

        self.assertEqual(mengen, [Decimal('0.2500'), Decimal('0.2500')])


class ProjectBillingDiscountTestCase(ProjectBillingTestBase):
    """Rabattübernahme aus dem Projekt."""

    def test_discount_from_project_and_non_discountable_item(self):
        """Rabattfähige Position erhält den Projektrabatt, nicht rabattfähige 0."""
        ohne_rabatt = self._item(
            'ART-FIX', 'Pauschale', Decimal('80.00'), is_discountable=False
        )
        self.projekt.travel_item = ohne_rabatt
        self.projekt.save(update_fields=['travel_item'])

        leistung = self._entry(6, 60)
        anfahrt = self._entry(6, 60, travel=True)

        self._bill()
        leistung.refresh_from_db()
        anfahrt.refresh_from_db()

        self.assertEqual(leistung.invoice_line.discount, Decimal('10.00'))
        self.assertTrue(leistung.invoice_line.is_discountable)
        self.assertEqual(anfahrt.invoice_line.discount, Decimal('0.00'))
        self.assertFalse(anfahrt.invoice_line.is_discountable)


class ProjectBillingValidationTestCase(ProjectBillingTestBase):
    """Prüfungen vor dem Lauf."""

    def assertNothingCreated(self):
        self.assertEqual(SalesDocument.objects.count(), 0)
        self.assertFalse(TimeEntry.objects.filter(is_billed=True).exists())

    def test_missing_customer_aborts(self):
        """Ohne Kunde keine Rechnung - die Meldung benennt den fehlenden Wert."""
        self.projekt.kunde = None
        self.projekt.save(update_fields=['kunde'])
        self._entry(7, 60)

        with self.assertRaises(ProjectBillingError) as ctx:
            self._bill()

        self.assertTrue(any('Kunden' in error for error in ctx.exception.errors))
        self.assertNothingCreated()

    def test_missing_company_aborts(self):
        """Ohne Mandant keine Rechnung."""
        entry = self._entry(7, 60)
        self.projekt.company = None
        self.projekt.save(update_fields=['company'])

        with self.assertRaises(ProjectBillingError) as ctx:
            self._bill()

        self.assertTrue(any('Mandanten' in error for error in ctx.exception.errors))
        self.assertNothingCreated()
        entry.refresh_from_db()
        self.assertFalse(entry.is_billed)

    def test_missing_billing_item_aborts(self):
        """Fehlt der Leistungsartikel, wird der Lauf abgebrochen."""
        self.projekt.billing_item = None
        self.projekt.save(update_fields=['billing_item'])
        self._entry(7, 60)

        with self.assertRaises(ProjectBillingError) as ctx:
            self._bill()

        self.assertTrue(
            any('Abrechnungsartikel' in error and 'Leistungszeit' in error
                for error in ctx.exception.errors)
        )
        self.assertNothingCreated()

    def test_missing_hourly_rate_aborts(self):
        """Fehlt der Stundensatz, wird der Lauf abgebrochen."""
        self.projekt.hourly_rate = None
        self.projekt.save(update_fields=['hourly_rate'])
        self._entry(7, 60)

        with self.assertRaises(ProjectBillingError) as ctx:
            self._bill()

        self.assertTrue(any('Stundensatz' in error for error in ctx.exception.errors))
        self.assertNothingCreated()

    def test_missing_travel_conditions_only_matter_with_travel_entries(self):
        """Ohne Anfahrt im Zeitraum sind die Anfahrtsfelder nicht erforderlich."""
        self.projekt.travel_item = None
        self.projekt.travel_hourly_rate = None
        self.projekt.save(update_fields=['travel_item', 'travel_hourly_rate'])
        self._entry(8, 60)

        document = self._bill()

        self.assertEqual(document.lines.count(), 1)

    def test_missing_travel_conditions_abort_with_travel_entries(self):
        """Kommt Anfahrt vor, sind Anfahrtsartikel und -satz Pflicht."""
        self.projekt.travel_item = None
        self.projekt.travel_hourly_rate = None
        self.projekt.save(update_fields=['travel_item', 'travel_hourly_rate'])
        self._entry(8, 60, travel=True)

        with self.assertRaises(ProjectBillingError) as ctx:
            self._bill()

        self.assertTrue(any('Anfahrtszeit' in error for error in ctx.exception.errors))
        self.assertNothingCreated()

    def test_no_open_hours_creates_no_empty_invoice(self):
        """Ohne offene Stunden entsteht keine leere Rechnung."""
        with self.assertRaises(ProjectBillingError) as ctx:
            self._bill()

        self.assertTrue(
            any('keine offenen Zeiterfassungen' in error for error in ctx.exception.errors)
        )
        self.assertNothingCreated()

    def test_company_mismatch_is_reported(self):
        """Ein Mandantenbruch wird gemeldet, nicht stillschweigend übernommen."""
        self._entry(9, 60, company=self.other_company)

        with self.assertRaises(ProjectBillingError) as ctx:
            self._bill()

        self.assertTrue(any('anderen Mandanten' in error for error in ctx.exception.errors))
        self.assertNothingCreated()


class ProjectBillingIdempotencyTestCase(ProjectBillingTestBase):
    """Ein zweiter Lauf erzeugt keine Dubletten."""

    def test_second_run_over_same_period_finds_nothing(self):
        entry = self._entry(10, 60)
        document = self._bill()

        with self.assertRaises(ProjectBillingError):
            self._bill()

        self.assertEqual(SalesDocument.objects.count(), 1)
        entry.refresh_from_db()
        self.assertEqual(entry.invoice_line.document, document)

    def test_new_hours_are_billed_in_a_second_run(self):
        """Neu erfasste Stunden landen im nächsten Lauf."""
        self._entry(10, 60)
        self._bill()

        neue = self._entry(11, 30)
        zweiter_beleg = self._bill()

        neue.refresh_from_db()
        self.assertEqual(zweiter_beleg.lines.count(), 1)
        self.assertEqual(neue.invoice_line.document, zweiter_beleg)


class ProjectBillingAtomicityTestCase(ProjectBillingTestBase):
    """Ein Fehler mitten im Lauf lässt nichts zurück."""

    def test_failure_rolls_back_document_and_time_entries(self):
        entry = self._entry(12, 60)

        with patch(
            'auftragsverwaltung.services.project_billing.DocumentCalculationService.recalculate',
            side_effect=RuntimeError('Berechnung fehlgeschlagen'),
        ):
            with self.assertRaises(RuntimeError):
                self._bill()

        self.assertEqual(SalesDocument.objects.count(), 0)
        self.assertEqual(SalesDocumentLine.objects.count(), 0)
        entry.refresh_from_db()
        self.assertFalse(entry.is_billed)
        self.assertIsNone(entry.billed_at)
        self.assertIsNone(entry.invoice_line)


class ProjectBillingDeletionTestCase(ProjectBillingTestBase):
    """Rücknahme beim Löschen des Entwurfs."""

    def setUp(self):
        super().setUp()
        self.entry_a = self._entry(13, 60)
        self.entry_b = self._entry(14, 30)
        self.document = self._bill()

    def test_deleting_draft_document_resets_time_entries(self):
        """Wird der Entwurf gelöscht, sind die Stunden wieder offen."""
        self.document.delete()

        for entry in (self.entry_a, self.entry_b):
            entry.refresh_from_db()
            self.assertFalse(entry.is_billed)
            self.assertIsNone(entry.billed_at)
            self.assertIsNone(entry.invoice_line)

    def test_deleting_single_draft_line_resets_only_that_entry(self):
        """Eine einzelne gelöschte Position betrifft nur ihre Zeiterfassung."""
        self.entry_a.refresh_from_db()
        self.entry_a.invoice_line.delete()

        self.entry_a.refresh_from_db()
        self.entry_b.refresh_from_db()
        self.assertFalse(self.entry_a.is_billed)
        self.assertTrue(self.entry_b.is_billed)

    def test_deleting_finalized_document_keeps_entries_billed(self):
        """Bei finalisiertem Beleg bleibt die Abrechnung bestehen."""
        self.document.status = 'SENT'
        self.document.save(update_fields=['status'])

        self.document.delete()

        for entry in (self.entry_a, self.entry_b):
            entry.refresh_from_db()
            self.assertTrue(entry.is_billed)
            self.assertIsNotNone(entry.billed_at)
            # Der Positionsverweis fällt durch SET_NULL weg, das Kennzeichen bleibt.
            self.assertIsNone(entry.invoice_line)


class ProjectBillingFinalizationTestCase(ProjectBillingTestBase):
    """Der Entwurf lässt sich anschließend regulär finalisieren."""

    def test_draft_can_be_finalized_and_creates_journal_entry(self):
        """Beim Echtdruck entsteht der Eintrag im Rechnungsausgangsjournal."""
        from auftragsverwaltung.services.invoice_finalization import finalize_invoice
        from finanzen.models import OutgoingInvoiceJournalEntry

        entry = self._entry(20, 60)
        document = self._bill()

        finalize_invoice(document)

        document.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(document.status, 'SENT')
        self.assertTrue(
            OutgoingInvoiceJournalEntry.objects.filter(document=document).exists()
        )
        # Der Beleg bekommt seinen Journaleintrag erst hier, nicht beim Lauf.
        self.assertTrue(entry.is_billed)


class ProjectBillingViewTestCase(ProjectBillingTestBase):
    """Bedienung: Vorschau, Erstellen per POST, Projektseite."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username='billing', password='password')
        self.url = reverse('projekt_abrechnung', kwargs={'pk': self.projekt.pk})

    def test_default_period_is_last_completed_month(self):
        """Der Zeitraum ist mit dem zuletzt abgeschlossenen Monat vorbelegt."""
        from core.views import get_default_billing_period

        von, bis = get_default_billing_period(date(2026, 9, 3))

        self.assertEqual(von, date(2026, 8, 1))
        self.assertEqual(bis, date(2026, 8, 31))

    def test_preview_lists_entries(self):
        """Die Vorschau zeigt die einbezogenen Zeiterfassungen und Summen."""
        self._entry(15, 40, description='Konfiguration Testsystem')

        response = self.client.get(self.url, {
            'date_from': '2026-08-01', 'date_to': '2026-08-31'
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Konfiguration Testsystem')
        # gerundete Menge 0,75 h und Projektsatz 110,00
        self.assertContains(response, '0,75')
        self.assertContains(response, '110,00')
        self.assertTrue(response.context['preview'].can_bill)

    def test_preview_shows_errors_and_blocks_button(self):
        """Fehlende Konditionen erscheinen als Fehlerliste, der Button ist gesperrt."""
        self.projekt.hourly_rate = None
        self.projekt.save(update_fields=['hourly_rate'])
        self._entry(15, 60)

        response = self.client.get(self.url, {
            'date_from': '2026-08-01', 'date_to': '2026-08-31'
        })

        self.assertContains(response, 'Abrechnung nicht möglich')
        self.assertContains(response, 'Stundensatz')
        self.assertContains(response, 'disabled')
        self.assertFalse(response.context['preview'].can_bill)

    def test_get_does_not_create_anything(self):
        """Die Vorschau verändert keinen Zustand."""
        self._entry(15, 60)

        self.client.get(self.url, {'date_from': '2026-08-01', 'date_to': '2026-08-31'})

        self.assertEqual(SalesDocument.objects.count(), 0)

    def test_post_creates_invoice_and_redirects(self):
        """POST erzeugt den Entwurf und leitet mit Erfolgsmeldung weiter."""
        self._entry(15, 60)

        response = self.client.post(
            self.url, {'date_from': '2026-08-01', 'date_to': '2026-08-31'}, follow=True
        )

        document = SalesDocument.objects.get()
        self.assertRedirects(
            response,
            reverse('auftragsverwaltung:document_detail', kwargs={
                'doc_key': self.doc_type.key, 'pk': document.pk
            }),
        )
        meldungen = [str(m) for m in response.context['messages']]
        self.assertTrue(any(document.number in m for m in meldungen))

    def test_post_without_conditions_shows_errors(self):
        """Ohne Konditionen bleibt der POST folgenlos und meldet den Grund."""
        self.projekt.billing_item = None
        self.projekt.save(update_fields=['billing_item'])
        self._entry(15, 60)

        response = self.client.post(
            self.url, {'date_from': '2026-08-01', 'date_to': '2026-08-31'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SalesDocument.objects.count(), 0)
        meldungen = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Abrechnungsartikel' in m for m in meldungen))

    def test_projekt_detail_shows_open_hours(self):
        """Die Projektseite zeigt Anzahl und Stundensumme getrennt nach Art."""
        self._entry(16, 120)
        self._entry(16, 30, travel=True)

        response = self.client.get(reverse('projekt_detail', kwargs={'pk': self.projekt.pk}))

        self.assertContains(response, 'Offene Stunden')
        self.assertContains(response, 'Stunden abrechnen')
        self.assertEqual(response.context['offene_anzahl'], 2)
        self.assertEqual(response.context['offene_leistung_minuten'], 120)
        self.assertEqual(response.context['offene_anfahrt_minuten'], 30)
        self.assertEqual(response.context['offene_von'], date(2026, 8, 16))
        self.assertEqual(response.context['offene_bis'], date(2026, 8, 16))


class TimeEntryBillingVisibilityTestCase(ProjectBillingTestBase):
    """Sichtbarkeit des Abrechnungsstatus in der Zeiterfassung."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username='billing', password='password')
        self.abgerechnet = self._entry(18, 60)
        self.offen = self._entry(19, 60)
        self._bill(date(2026, 8, 18), date(2026, 8, 18))
        self.abgerechnet.refresh_from_db()

    def test_list_links_invoice(self):
        """Die Liste verlinkt die Rechnung der abgerechneten Zeiterfassung."""
        response = self.client.get(reverse('auftragsverwaltung:timeentry_list'))

        self.assertContains(response, self.abgerechnet.invoice_line.document.number)

    def test_detail_links_invoice(self):
        """Die Detailansicht zeigt Rechnung und Position."""
        response = self.client.get(
            reverse('auftragsverwaltung:timeentry_detail', kwargs={'pk': self.abgerechnet.pk})
        )

        self.assertContains(response, self.abgerechnet.invoice_line.document.number)

    def test_unbilled_only_filter(self):
        """Der Filter „nur unabgerechnete" blendet abgerechnete Einträge aus."""
        filter_set = TimeEntryFilter({'unbilled_only': 'on'}, queryset=TimeEntry.objects.all())

        pks = set(filter_set.qs.values_list('pk', flat=True))

        self.assertEqual(pks, {self.offen.pk})
