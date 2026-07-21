"""
Browser-/Integrationstests (Playwright) für die Positionserfassung.

Issue #721 Sub 4/4: Die bisherige Testsuite (test_ajax_line_update.py,
test_multiple_position_save.py, test_issue_377_langtext.py, ...) besteht
ausschließlich aus Django-Testclient-Tests gegen den Endpunkt - sequenziell,
ein Feld pro Request. Genau die Fehlerklassen, die Issue #721 auslösten
(überlappende/entprellte Autosaves, blur-Timing, location.reload()-Races,
Doppel-POSTs, Langtext an nicht-letzter Position, fehlende
Fehler-Signalisierung), sind damit prinzipiell nicht abgedeckt, weil ein
Testclient-Request nie mit dem im Browser laufenden JavaScript
(scheduleLineSave/flushLineSave/flushAllLineSavesAndCheck in
templates/auftragsverwaltung/documents/detail.html) interagiert.

Diese Tests treiben stattdessen einen echten (headless) Browser gegen eine
laufende Django-LiveServer-Instanz und reproduzieren damit die Timing-/
Race-Ebene, nicht nur den Endpunkt.

Laufen lassen (zusätzlich zu `python manage.py test`):

    pip install -r requirements-dev.txt
    playwright install --with-deps chromium
    python manage.py test --settings=test_settings auftragsverwaltung.test_browser_position_entry

Ist Playwright oder der Chromium-Browser nicht installiert, werden alle
Tests in diesem Modul automatisch (mit Begründung) übersprungen, statt die
restliche Suite fehlschlagen zu lassen.
"""
import re
import unittest
from decimal import Decimal
from datetime import date
from unittest import mock

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType, NumberRange
from core.models import Mandant, Adresse, TaxRate, PaymentTerm, Unit

User = get_user_model()

try:
    from playwright.sync_api import sync_playwright, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _browser_available():
    """Probes once at module-collection time whether a Chromium binary can
    actually be launched, so the whole class is skipped (not errored) when
    only `pip install playwright` was run without `playwright install`."""
    if not PLAYWRIGHT_AVAILABLE:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


BROWSER_AVAILABLE = _browser_available()
SKIP_REASON = (
    "Playwright/Chromium nicht verfügbar - installieren mit: "
    "pip install -r requirements-dev.txt && playwright install --with-deps chromium"
)


@unittest.skipUnless(BROWSER_AVAILABLE, SKIP_REASON)
class PositionEntryBrowserTestCase(StaticLiveServerTestCase):
    """Basisklasse: startet einen headless Chromium einmal pro Testklasse
    und legt vor jedem Test einen frischen Beleg mit Positionen an."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username='browsertester', email='browsertester@example.com', password='testpass123'
        )
        self.company = Mandant.objects.create(
            name='Test Company GmbH', adresse='Teststraße 123', plz='12345',
            ort='Teststadt', land='Deutschland', steuernummer='DE123456789'
        )
        # StaticLiveServerTestCase behaves like TransactionTestCase (no
        # per-test rollback, only a flush() between tests), so the CUSTOMER
        # NumberRange seeded by migration 0021 only survives the first test
        # in the class - every test must (re-)create the fixtures it needs.
        NumberRange.objects.get_or_create(
            target='CUSTOMER',
            defaults={'reset_policy': 'YEARLY', 'format': '{prefix}{yy}-{seq:05d}'}
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE', name='Test Customer', anrede='Herr',
            strasse='Kundenstraße 1', plz='54321', ort='Kundenstadt', land='Deutschland'
        )
        self.tax_rate_standard = TaxRate.objects.create(
            code='STANDARD', name='Standard-Steuersatz', rate=Decimal('0.19'), is_active=True
        )
        self.tax_rate_reduced = TaxRate.objects.create(
            code='REDUCED', name='Ermäßigter Steuersatz', rate=Decimal('0.07'), is_active=True
        )
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')
        self.payment_term = PaymentTerm.objects.create(name='14 Tage netto', net_days=14, is_default=False)
        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='quote', defaults={'name': 'Angebot', 'prefix': 'AN', 'is_invoice': False, 'is_active': True}
        )
        NumberRange.objects.create(
            company=self.company, target='DOCUMENT', document_type=self.doc_type,
            reset_policy='YEARLY', format='{prefix}{yy}-{seq:05d}'
        )
        self.document = SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type, number='AN-2026-1001',
            status='DRAFT', customer=self.customer, payment_term=self.payment_term,
            issue_date=date.today(), total_net=Decimal('0.00'), total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )
        self.lines = [
            SalesDocumentLine.objects.create(
                document=self.document, position_no=i + 1, line_type='NORMAL', is_selected=True,
                short_text_1=f'Position {i + 1}', short_text_2='', long_text=f'Ursprungslangtext {i + 1}',
                description=f'Position {i + 1}', quantity=Decimal('1.0000'),
                unit_price_net=Decimal('100.00'), tax_rate=self.tax_rate_standard,
                is_discountable=True, discount=Decimal('0.00'),
                line_net=Decimal('100.00'), line_tax=Decimal('19.00'), line_gross=Decimal('119.00')
            )
            for i in range(3)
        ]
        self.detail_url = self.live_server_url + reverse(
            'auftragsverwaltung:document_detail', kwargs={'doc_key': 'quote', 'pk': self.document.pk}
        )

        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        # Auto-accept the native confirm() dialogs the page uses (e.g.
        # "Position wirklich löschen?") - Playwright dismisses dialogs by
        # default, which would silently cancel every delete-line test.
        self.page.on('dialog', lambda d: d.accept())
        self._login()
        self.page.goto(self.detail_url)

    def tearDown(self):
        self.context.close()

    def _login(self):
        self.page.goto(self.live_server_url + reverse('login'))
        self.page.locator('#id_username').fill('browsertester')
        self.page.locator('#id_password').fill('testpass123')
        self.page.locator('button[type="submit"]').click()
        expect(self.page.locator('#id_username')).to_have_count(0)

    def line_item(self, line):
        return self.page.locator(f'.line-item[data-line-id="{line.pk}"]')

    def save_status(self, line):
        return self.page.locator(f'.line-save-status[data-line-id="{line.pk}"]')

    def reload_lines(self):
        """Refetches the current line state straight from the DB (bypassing
        any Python-side cache) after a browser action, mirroring what a
        real reload/second visit would see."""
        return list(SalesDocumentLine.objects.filter(document=self.document).order_by('position_no'))


class MultiplePositionsIndependentEditTest(PositionEntryBrowserTestCase):
    """Mehrere Positionen unabhängig erfassen/ändern -> nach Reload alle
    Werte korrekt (Kernszenario aus der Sub-Issue-Beschreibung)."""

    def test_independent_edits_on_different_lines_all_persist(self):
        line1, line2, line3 = self.lines

        self.line_item(line1).locator('.line-short-text-1').fill('Kurztext Position 1 (geändert)')
        self.line_item(line2).locator('.line-quantity').fill('5')
        self.line_item(line3).locator('.line-unit-price').fill('42.50')

        for line in self.lines:
            expect(self.save_status(line)).to_contain_text('gespeichert', timeout=10000)

        self.page.reload()
        expect(self.page.locator('.line-item')).to_have_count(3, timeout=10000)

        refreshed = self.reload_lines()
        self.assertEqual(refreshed[0].short_text_1, 'Kurztext Position 1 (geändert)')
        self.assertEqual(refreshed[1].quantity, Decimal('5.0000'))
        self.assertEqual(refreshed[2].unit_price_net, Decimal('42.50'))
        # Fields nobody touched must survive untouched.
        self.assertEqual(refreshed[0].quantity, Decimal('1.0000'))
        self.assertEqual(refreshed[2].short_text_1, 'Position 3')


class FastTypingImmediateAddTest(PositionEntryBrowserTestCase):
    """Schnelles Tippen in Kurztext + sofortiges "Position hinzufügen" ->
    kein Verlust. Reproduziert die location.reload()-Race, bei der ein noch
    entprellter Autosave durch den Reload verschluckt wurde."""

    def test_typing_then_immediate_add_position_does_not_lose_edit(self):
        line1 = self.lines[0]
        # Deliberately do NOT wait for the 500ms debounce or the
        # "gespeichert" status before triggering the action that reloads
        # the page - this is exactly the race the fix closes.
        self.line_item(line1).locator('.line-short-text-1').fill('Blitzedit vor Add')
        self.page.locator('#addLineButton').click()

        # location.reload() happens once ajax_add_line succeeds; wait for
        # the new (4th) line to show up as proof the reload completed.
        expect(self.page.locator('.line-item')).to_have_count(4, timeout=10000)

        refreshed = self.reload_lines()
        self.assertEqual(refreshed[0].short_text_1, 'Blitzedit vor Add')
        self.assertEqual(len(refreshed), 4)


class TaxRateChangePersistsTest(PositionEntryBrowserTestCase):
    """USt-Wechsel je Position -> nach Reload persistiert."""

    def test_tax_rate_change_on_one_line_persists_others_unaffected(self):
        line1, line2, _ = self.lines

        self.line_item(line1).locator('.line-tax-rate').select_option(str(self.tax_rate_reduced.pk))
        expect(self.save_status(line1)).to_contain_text('gespeichert', timeout=10000)

        self.page.reload()

        refreshed = self.reload_lines()
        self.assertEqual(refreshed[0].tax_rate_id, self.tax_rate_reduced.pk)
        self.assertEqual(refreshed[1].tax_rate_id, self.tax_rate_standard.pk)

        selected_value = self.line_item(line1).locator('.line-tax-rate').input_value()
        self.assertEqual(selected_value, str(self.tax_rate_reduced.pk))


class LongtextNonLastPositionRegressionTest(PositionEntryBrowserTestCase):
    """Regression #377: Langtext an nicht-letzter Position ändern -> nur
    diese Zeile geändert. Der historische Bug sendete alle Langtext-
    Textareas mit demselben name-Attribut, sodass am Ende der Wert der
    LETZTEN Position landete, egal welche Zeile bearbeitet wurde."""

    def test_editing_longtext_of_middle_line_only_changes_that_line(self):
        line1, line2, line3 = self.lines

        self.line_item(line2).locator('.edit-longtext-btn').click()
        editor = self.page.locator('#longtextEditor .ql-editor')
        expect(editor).to_be_visible()
        editor.fill('Neuer Langtext für Position 2')
        self.page.locator('#saveLongtextButton').click()

        expect(self.page.locator('#longtextEditorModal')).to_be_hidden(timeout=10000)

        refreshed = self.reload_lines()
        self.assertIn('Neuer Langtext für Position 2', refreshed[1].long_text)
        self.assertEqual(refreshed[0].long_text, 'Ursprungslangtext 1')
        self.assertEqual(refreshed[2].long_text, 'Ursprungslangtext 3')


class DeleteDuringOpenEditTest(PositionEntryBrowserTestCase):
    """Delete (an einer anderen Position) während ein Zeilen-Edit noch
    nicht committet/entprellt ist -> das offene Edit geht nicht verloren,
    weil flushAllLineSavesAndCheck() vor dem löschenden Reload greift."""

    def test_deleting_other_line_flushes_pending_edit_first(self):
        line1, line2, line3 = self.lines

        # Start editing line1 but don't blur/wait - immediately delete line3.
        self.line_item(line1).locator('.line-short-text-1').fill('Noch nicht entprellt')
        self.line_item(line3).locator('.delete-line-btn').click()

        expect(self.page.locator('.line-item')).to_have_count(2, timeout=10000)

        refreshed = self.reload_lines()
        self.assertEqual(len(refreshed), 2)
        self.assertEqual(refreshed[0].short_text_1, 'Noch nicht entprellt')
        self.assertNotIn(line3.pk, [l.pk for l in refreshed])


class RapidOverlappingFieldEditsTest(PositionEntryBrowserTestCase):
    """Doppel-POSTs / überlappende Saves auf derselben Zeile: Kurztext wird
    per Debounce, Steuersatz per sofortigem saveLineFieldsNow() gespeichert.
    Beide dürfen sich nicht gegenseitig überschreiben (serialisierter Save
    pro Zeile, siehe flushLineSave()/entry.inFlight)."""

    def test_overlapping_edits_on_same_line_both_persist(self):
        line1 = self.lines[0]
        item = self.line_item(line1)

        item.locator('.line-short-text-1').fill('Überlappender Kurztext')
        # Fired while the short-text debounce timer is still pending; the
        # select's change handler flushes immediately (saveLineFieldsNow),
        # which must not drop the still-pending short_text_1 edit.
        item.locator('.line-tax-rate').select_option(str(self.tax_rate_reduced.pk))

        expect(self.save_status(line1)).to_contain_text('gespeichert', timeout=10000)
        self.page.wait_for_timeout(600)  # let a straggling debounce flush settle, if any

        refreshed = self.reload_lines()
        self.assertEqual(refreshed[0].short_text_1, 'Überlappender Kurztext')
        self.assertEqual(refreshed[0].tax_rate_id, self.tax_rate_reduced.pk)


class ServerErrorVisibleFeedbackTest(PositionEntryBrowserTestCase):
    """Fehlerfall (Server 500) -> sichtbares Feedback statt stillem
    console.error, inklusive Retry-Recovery (verifiziert Sub 3)."""

    def test_failed_save_shows_error_status_and_retry_recovers(self):
        line1 = self.lines[0]

        with mock.patch(
            'auftragsverwaltung.views.DocumentCalculationService.calculate_line_totals',
            side_effect=Exception('Simulated failure'),
        ):
            # Uses the price field rather than Kurztext 1, which also drives
            # a live article-autocomplete lookup unrelated to this scenario.
            self.line_item(line1).locator('.line-unit-price').fill('55.00')
            self.line_item(line1).locator('.line-unit-price').blur()

            expect(self.save_status(line1)).to_have_class(re.compile('status-error'), timeout=10000)
            expect(self.save_status(line1).locator('.retry-line-save-btn')).to_contain_text('Erneut versuchen')
            expect(self.page.locator('#unsavedIndicator')).to_have_class(re.compile('show'))

        # Backend recovered (mock context exited) - Retry must now succeed.
        self.save_status(line1).locator('.retry-line-save-btn').click()
        expect(self.save_status(line1)).to_contain_text('gespeichert', timeout=10000)

        refreshed = self.reload_lines()
        self.assertEqual(refreshed[0].unit_price_net, Decimal('55.00'))
