"""
Tests für die KI-Aufbereitung der Langtexte im Projekt-Abrechnungslauf (#1193)

Abgedeckt werden:
- normalisierter Text als Langtext der Position, Zeiterfassung unverändert
- ein KI-Aufruf für den ganzen Lauf, Zuordnung über die Indizes
- Ausfall der KI bricht den Lauf nicht ab (Originaltext + Warnung)
- unvollständige Antwort: nur die fehlenden Positionen tragen das Original
- abgeschaltete Normalisierung läuft ohne KI-Aufruf

Der ``AIRouter`` wird in jedem Test gemockt - es wird nie ein echter Anbieter
aufgerufen.
"""
import json
from datetime import date
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from auftragsverwaltung.services.project_billing import (
    NORMALIZATION_WARNING,
    ProjectBillingService,
)
from auftragsverwaltung.test_project_billing import ProjectBillingTestBase
from core.services.ai.schemas import AIResponse
from core.services.base import ServiceNotConfigured


def _response(entries):
    """Eine gemockte KI-Antwort im erwarteten JSON-Format."""
    return AIResponse(text=json.dumps({'entries': entries}, ensure_ascii=False), raw=None)


class ProjectBillingNormalizationTestBase(ProjectBillingTestBase):
    """Stammdaten des Abrechnungslaufs plus gemockter Router."""

    def setUp(self):
        super().setUp()
        patcher = patch('core.services.ai.time_entry_normalization.AIRouter')
        self.router_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.router = self.router_class.return_value


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class ProjectBillingNormalizationTestCase(ProjectBillingNormalizationTestBase):
    """Erfolgreicher Lauf mit aufbereiteten Langtexten."""

    def setUp(self):
        super().setUp()
        self.entry_a = self._entry(3, 90, description='tel. mit kd wg. drucker')
        self.entry_b = self._entry(4, 40, travel=True, description='hinfahrt kd')
        self.entry_c = self._entry(5, 60, description='Fehler von letzter Woche behoben')

        # Antwort bewusst in anderer Reihenfolge als die Anfrage.
        self.router.chat.return_value = _response([
            {'index': 1, 'text': 'Anfahrt zum Kunden.'},
            {'index': 2, 'text': 'Behebung eines Fehlers.'},
            {'index': 0, 'text': 'Telefonat mit dem Kunden zum Drucker.'},
        ])

        self.document = self._bill()

    def test_lines_carry_normalized_long_text(self):
        """Der aufbereitete Text steht als Langtext an der richtigen Position."""
        lines = list(self.document.lines.order_by('position_no'))

        self.assertEqual(
            [line.long_text for line in lines],
            [
                'Telefonat mit dem Kunden zum Drucker.',
                'Anfahrt zum Kunden.',
                'Behebung eines Fehlers.',
            ],
        )

    def test_line_is_linked_to_its_own_time_entry(self):
        """Jede Position hängt an der Zeiterfassung, aus der ihr Text stammt."""
        self.entry_c.refresh_from_db()

        self.assertEqual(self.entry_c.invoice_line.long_text, 'Behebung eines Fehlers.')

    def test_time_entry_keeps_original_description(self):
        """Die Zeiterfassung bleibt als Arbeitsnachweis unverändert."""
        for entry, original in (
            (self.entry_a, 'tel. mit kd wg. drucker'),
            (self.entry_b, 'hinfahrt kd'),
            (self.entry_c, 'Fehler von letzter Woche behoben'),
        ):
            with self.subTest(original=original):
                entry.refresh_from_db()
                self.assertEqual(entry.description, original)

    def test_single_ai_call_for_the_whole_run(self):
        """Ein Aufruf für den Lauf, nicht einer je Position."""
        self.assertEqual(self.router.chat.call_count, 1)

        payload = json.loads(self.router.chat.call_args.kwargs['messages'][-1]['content'])
        self.assertEqual(
            payload['entries'],
            [
                {'index': 0, 'text': 'tel. mit kd wg. drucker'},
                {'index': 1, 'text': 'hinfahrt kd'},
                {'index': 2, 'text': 'Fehler von letzter Woche behoben'},
            ],
        )

    def test_no_warning_on_success(self):
        self.assertIsNone(self.document.normalization_warning)


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class ProjectBillingNormalizationFailureTestCase(ProjectBillingNormalizationTestBase):
    """Ein Ausfall der KI darf die Abrechnung nicht verhindern."""

    def setUp(self):
        super().setUp()
        self.entry_a = self._entry(3, 90, description='tel. mit kd')
        self.entry_b = self._entry(4, 60, description='doku geschrieben')

    def test_run_completes_with_original_texts(self):
        self.router.chat.side_effect = ServiceNotConfigured('Kein aktives Modell')

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR'):
            document = self._bill()

        self.assertEqual(document.status, 'DRAFT')
        self.assertEqual(
            [line.long_text for line in document.lines.order_by('position_no')],
            ['tel. mit kd', 'doku geschrieben'],
        )
        self.assertEqual(document.normalization_warning, NORMALIZATION_WARNING)

    def test_entries_are_marked_billed_despite_failure(self):
        """Der Lauf ist vollständig - nur die Texte sind nicht aufbereitet."""
        self.router.chat.side_effect = TimeoutError('Zeitüberschreitung')

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR'):
            self._bill()

        self.entry_a.refresh_from_db()
        self.assertTrue(self.entry_a.is_billed)
        self.assertIsNotNone(self.entry_a.invoice_line)

    def test_partial_answer_keeps_originals_for_missing_lines(self):
        """Fehlende Indizes werden nicht über die Reihenfolge zugeordnet."""
        self.router.chat.return_value = _response([
            {'index': 1, 'text': 'Erstellung der Dokumentation.'},
        ])

        with self.assertLogs('core.services.ai.time_entry_normalization', level='WARNING'):
            document = self._bill()

        self.assertEqual(
            [line.long_text for line in document.lines.order_by('position_no')],
            ['tel. mit kd', 'Erstellung der Dokumentation.'],
        )
        self.assertEqual(document.normalization_warning, NORMALIZATION_WARNING)

    def test_view_shows_warning_and_creates_invoice(self):
        """Die Oberfläche meldet Erfolg und weist auf die Prüfung der Langtexte hin."""
        self.router.chat.side_effect = ServiceNotConfigured('Kein aktives Modell')
        client = self.client
        client.force_login(self.user)

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR'):
            response = client.post(
                reverse('projekt_abrechnung', kwargs={'pk': self.projekt.pk}),
                {'date_from': '2026-08-01', 'date_to': '2026-08-31'},
                follow=True,
            )

        texte = [str(message) for message in response.context['messages']]
        self.assertTrue(any('wurde erstellt' in text for text in texte), texte)
        self.assertIn(NORMALIZATION_WARNING, texte)


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=False)
class ProjectBillingNormalizationDisabledTestCase(ProjectBillingNormalizationTestBase):
    """Abgeschaltet läuft die Abrechnung ohne KI-Aufruf."""

    def test_original_text_without_ai_call(self):
        self._entry(3, 90, description='tel. mit kd')

        document = self._bill()

        self.router.chat.assert_not_called()
        self.assertEqual(document.lines.first().long_text, 'tel. mit kd')
        self.assertIsNone(document.normalization_warning)


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class ProjectBillingNormalizationBatchTestCase(ProjectBillingNormalizationTestBase):
    """Mehr als 25 Zeiterfassungen werden blockweise aufbereitet."""

    def test_thirty_entries_are_billed_in_two_calls(self):
        for tag in range(1, 31):
            self._entry(tag, 60, description=f'aufgabe {tag}')

        def antwort(**kwargs):
            payload = json.loads(kwargs['messages'][-1]['content'])
            return _response([
                {'index': entry['index'], 'text': f"Bearbeitung der Aufgabe {entry['index']}."}
                for entry in payload['entries']
            ])

        self.router.chat.side_effect = antwort

        document = self._bill()

        self.assertEqual(self.router.chat.call_count, 2)  # 25 + 5
        lines = list(document.lines.order_by('position_no'))
        self.assertEqual(len(lines), 30)
        self.assertEqual(
            [line.long_text for line in lines],
            [f'Bearbeitung der Aufgabe {index}.' for index in range(30)],
        )
        self.assertIsNone(document.normalization_warning)


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class ProjectBillingNormalizationContentTestCase(ProjectBillingNormalizationTestBase):
    """Der Langtext enthält nichts, was nicht in der Antwort stand."""

    def test_no_content_is_added_to_the_line(self):
        self._entry(3, 90, description='tel. mit kd wg. drucker')

        self.router.chat.return_value = _response([
            {'index': 0, 'text': 'Telefonat mit dem Kunden zum Drucker.'},
        ])

        document = self._bill()
        long_text = document.lines.first().long_text

        self.assertEqual(long_text, 'Telefonat mit dem Kunden zum Drucker.')
        # Weder Dauer noch Datum der Zeiterfassung wandern in den Text.
        self.assertNotIn('90', long_text)
        self.assertNotIn('1,50', long_text)
        self.assertNotIn('03.08.2026', long_text)
