"""
Tests für die KI-Normalisierung der Tätigkeitsbeschreibungen (#1193)

Abgedeckt werden:
- abgeschaltete Normalisierung (kein KI-Aufruf, Originaltexte)
- Zuordnung über die Indizes der Antwort, nicht über deren Reihenfolge
- keine inhaltlichen Ergänzungen durch den Service selbst
- leere und unverständliche Texte bleiben unverändert
- unvollständige, unbrauchbare und fehlgeschlagene Antworten
- blockweiser Aufruf bei mehr als 25 Einträgen

Der ``AIRouter`` wird durchgängig gemockt - es wird nie ein echter Anbieter
aufgerufen.
"""
import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.services.ai.schemas import AIResponse
from core.services.ai.time_entry_normalization import TimeEntryNormalizationService
from core.services.base import ServiceNotConfigured


def _response(entries):
    """Eine gemockte KI-Antwort im erwarteten JSON-Format."""
    return AIResponse(text=json.dumps({'entries': entries}, ensure_ascii=False), raw=None)


class NormalizationTestBase(SimpleTestCase):
    """Gemeinsames Gerüst: der Router ist immer ein Mock."""

    def setUp(self):
        patcher = patch('core.services.ai.time_entry_normalization.AIRouter')
        self.router_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.router = self.router_class.return_value

    def _chat_payloads(self):
        """Die an die KI geschickten Nutzlasten, je Aufruf als Dict."""
        payloads = []
        for call in self.router.chat.call_args_list:
            messages = call.kwargs['messages']
            payloads.append(json.loads(messages[-1]['content']))
        return payloads


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=False)
class NormalizationDisabledTestCase(NormalizationTestBase):
    """Abgeschaltet wird ohne KI-Aufruf der Originaltext übernommen."""

    def test_originals_are_returned_without_ai_call(self):
        result = TimeEntryNormalizationService().normalize(['tel. mit kd', 'doku'])

        self.assertEqual(result.texts, ['tel. mit kd', 'doku'])
        self.assertFalse(result.failed)
        self.assertFalse(result.ai_used)
        self.router.chat.assert_not_called()


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class NormalizationSuccessTestCase(NormalizationTestBase):
    """Erfolgreicher Lauf: ein Aufruf, Zuordnung über die Indizes."""

    def test_single_call_for_all_entries(self):
        """Für mehrere Texte gibt es genau einen KI-Aufruf, nicht einen je Text."""
        self.router.chat.return_value = _response([
            {'index': 0, 'text': 'Telefonat mit dem Kunden.'},
            {'index': 1, 'text': 'Erstellung der Dokumentation.'},
            {'index': 2, 'text': 'Einrichtung des Servers.'},
        ])

        result = TimeEntryNormalizationService().normalize([
            'tel. mit kd', 'doku geschrieben', 'srv eingerichtet',
        ])

        self.assertEqual(self.router.chat.call_count, 1)
        self.assertEqual(result.calls, 1)
        self.assertFalse(result.failed)
        self.assertEqual(result.texts, [
            'Telefonat mit dem Kunden.',
            'Erstellung der Dokumentation.',
            'Einrichtung des Servers.',
        ])

    def test_mapping_uses_index_not_answer_order(self):
        """Die Antwort darf in beliebiger Reihenfolge kommen - der Index zählt."""
        self.router.chat.return_value = _response([
            {'index': 2, 'text': 'Dritter Text.'},
            {'index': 0, 'text': 'Erster Text.'},
            {'index': 1, 'text': 'Zweiter Text.'},
        ])

        result = TimeEntryNormalizationService().normalize(['eins', 'zwei', 'drei'])

        self.assertEqual(result.texts, ['Erster Text.', 'Zweiter Text.', 'Dritter Text.'])

    def test_payload_carries_index_and_original_text(self):
        """Die Texte gehen nummeriert an die KI."""
        self.router.chat.return_value = _response([{'index': 0, 'text': 'Wartung.'}])

        TimeEntryNormalizationService().normalize(['wartung'])

        self.assertEqual(
            self._chat_payloads()[0],
            {'entries': [{'index': 0, 'text': 'wartung'}]},
        )

    def test_unknown_and_duplicate_indexes_are_ignored(self):
        """Fremde oder doppelte Indizes werden verworfen statt zugeordnet."""
        self.router.chat.return_value = _response([
            {'index': 0, 'text': 'Gültig.'},
            {'index': 0, 'text': 'Doppelt - wird verworfen.'},
            {'index': 99, 'text': 'Unbekannter Index.'},
        ])

        result = TimeEntryNormalizationService().normalize(['eins', 'zwei'])

        self.assertEqual(result.texts, ['Gültig.', 'zwei'])
        self.assertTrue(result.failed)

    def test_markdown_fenced_answer_is_accepted(self):
        """Manche Modelle verpacken JSON in einen Codeblock."""
        self.router.chat.return_value = AIResponse(
            text='```json\n{"entries": [{"index": 0, "text": "Wartung des Servers."}]}\n```',
            raw=None,
        )

        result = TimeEntryNormalizationService().normalize(['srv wartung'])

        self.assertEqual(result.texts, ['Wartung des Servers.'])
        self.assertFalse(result.failed)


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class NormalizationContentTestCase(NormalizationTestBase):
    """Keine inhaltlichen Ergänzungen - weder durch den Service noch im Prompt."""

    #: Beispieltexte aus dem Arbeitsalltag samt der erwarteten Aufbereitung.
    BEISPIELE = [
        ('tel. mit kd wg. drucker', 'Telefonat mit dem Kunden zum Drucker.'),
        ('Fehler von letzter Woche behoben', 'Behebung eines Fehlers.'),
        ('vm eingerichtet + tests', 'Einrichtung einer virtuellen Maschine und Tests.'),
    ]

    def test_service_transports_answer_verbatim(self):
        """
        Der Service gibt exakt die gemockte Antwort weiter.

        Er ergänzt nichts (keine Dauer, kein Datum, kein Ergebnis) und mischt
        auch nichts aus dem Originaltext dazu.
        """
        self.router.chat.return_value = _response([
            {'index': index, 'text': normalisiert}
            for index, (_, normalisiert) in enumerate(self.BEISPIELE)
        ])

        result = TimeEntryNormalizationService().normalize(
            [original for original, _ in self.BEISPIELE]
        )

        self.assertEqual(result.texts, [erwartet for _, erwartet in self.BEISPIELE])
        for text in result.texts:
            self.assertNotRegex(text, r'\d{1,2}\.\d{1,2}\.\d{2,4}')  # kein erfundenes Datum
            self.assertNotRegex(text, r'\d+\s*(Std|Stunde|Minuten|h)\b')  # keine erfundene Dauer

    def test_prompt_forbids_invented_content(self):
        """Die wichtigste Vorgabe steht im Prompt."""
        prompt = TimeEntryNormalizationService.NORMALIZATION_PROMPT

        self.assertIn('KEINE INHALTLICHEN ERGÄNZUNGEN', prompt)
        self.assertIn('Erfinde nichts hinzu', prompt)
        self.assertIn('UNVERÄNDERT', prompt)
        self.assertIn('Deutsch', prompt)

    def test_prompt_is_sent_as_system_message(self):
        """Der Prompt liegt an genau einer Stelle und geht so an die KI."""
        self.router.chat.return_value = _response([{'index': 0, 'text': 'Wartung.'}])

        TimeEntryNormalizationService().normalize(['wartung'])

        messages = self.router.chat.call_args.kwargs['messages']
        self.assertEqual(messages[0]['role'], 'system')
        self.assertEqual(
            messages[0]['content'], TimeEntryNormalizationService.NORMALIZATION_PROMPT
        )
        self.assertEqual(
            self.router.chat.call_args.kwargs['agent'],
            'core.ai.time_entry_normalization',
        )


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class NormalizationEdgeCaseTestCase(NormalizationTestBase):
    """Leere und unverständliche Texte."""

    def test_empty_texts_are_kept_and_not_sent(self):
        """Leere Texte gehen gar nicht erst an die KI."""
        self.router.chat.return_value = _response([{'index': 1, 'text': 'Wartung.'}])

        result = TimeEntryNormalizationService().normalize(['', 'wartung', '   ', None])

        self.assertEqual(result.texts, ['', 'Wartung.', '   ', ''])
        self.assertFalse(result.failed)
        self.assertEqual(
            self._chat_payloads()[0],
            {'entries': [{'index': 1, 'text': 'wartung'}]},
        )

    def test_no_call_when_everything_is_empty(self):
        result = TimeEntryNormalizationService().normalize(['', None])

        self.router.chat.assert_not_called()
        self.assertEqual(result.texts, ['', ''])
        self.assertFalse(result.failed)

    def test_unintelligible_fragment_stays_unchanged(self):
        """Ein Fragment gibt die KI laut Prompt unverändert zurück."""
        self.router.chat.return_value = _response([{'index': 0, 'text': 'xyz??'}])

        result = TimeEntryNormalizationService().normalize(['xyz??'])

        self.assertEqual(result.texts, ['xyz??'])


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class NormalizationFailureTestCase(NormalizationTestBase):
    """Ausfälle führen zum Originaltext, nicht zum Abbruch."""

    def test_provider_error_falls_back_to_originals(self):
        self.router.chat.side_effect = ServiceNotConfigured('Kein aktives Modell')

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR') as logs:
            result = TimeEntryNormalizationService().normalize(['tel. mit kd', 'doku'])

        self.assertEqual(result.texts, ['tel. mit kd', 'doku'])
        self.assertTrue(result.failed)
        self.assertIn('Kein aktives Modell', ' '.join(logs.output))

    def test_timeout_falls_back_to_originals(self):
        self.router.chat.side_effect = TimeoutError('Zeitüberschreitung')

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR'):
            result = TimeEntryNormalizationService().normalize(['tel. mit kd'])

        self.assertEqual(result.texts, ['tel. mit kd'])
        self.assertTrue(result.failed)

    def test_unusable_answer_falls_back_to_originals(self):
        self.router.chat.return_value = AIResponse(text='Gerne! Hier die Texte ...', raw=None)

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR'):
            result = TimeEntryNormalizationService().normalize(['tel. mit kd'])

        self.assertEqual(result.texts, ['tel. mit kd'])
        self.assertTrue(result.failed)

    def test_partial_answer_keeps_originals_for_missing_entries(self):
        """Fehlende Indizes werden nicht über die Reihenfolge geraten."""
        self.router.chat.return_value = _response([
            {'index': 2, 'text': 'Einrichtung des Servers.'},
        ])

        with self.assertLogs('core.services.ai.time_entry_normalization', level='WARNING'):
            result = TimeEntryNormalizationService().normalize([
                'tel. mit kd', 'doku geschrieben', 'srv eingerichtet',
            ])

        self.assertEqual(result.texts, [
            'tel. mit kd', 'doku geschrieben', 'Einrichtung des Servers.',
        ])
        self.assertTrue(result.failed)

    def test_empty_answer_text_falls_back_to_originals(self):
        self.router.chat.return_value = AIResponse(text='', raw=None)

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR'):
            result = TimeEntryNormalizationService().normalize(['tel. mit kd'])

        self.assertEqual(result.texts, ['tel. mit kd'])
        self.assertTrue(result.failed)


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class NormalizationBatchingTestCase(NormalizationTestBase):
    """Mehr als 25 Einträge werden blockweise abgearbeitet."""

    def setUp(self):
        super().setUp()
        self.originals = [f'text {index}' for index in range(60)]

        def antwort(messages, **kwargs):
            payload = json.loads(messages[-1]['content'])
            return _response([
                {'index': entry['index'], 'text': f"Normalisiert {entry['index']}."}
                for entry in payload['entries']
            ])

        self.router.chat.side_effect = lambda **kwargs: antwort(**kwargs)

    def test_blocks_of_25_are_merged(self):
        result = TimeEntryNormalizationService().normalize(self.originals)

        self.assertEqual(self.router.chat.call_count, 3)  # 25 + 25 + 10
        self.assertEqual(
            [len(payload['entries']) for payload in self._chat_payloads()],
            [25, 25, 10],
        )
        self.assertEqual(
            result.texts, [f'Normalisiert {index}.' for index in range(60)]
        )
        self.assertFalse(result.failed)

    def test_exactly_batch_size_is_one_call(self):
        TimeEntryNormalizationService().normalize(self.originals[:25])

        self.assertEqual(self.router.chat.call_count, 1)

    def test_failing_block_only_affects_its_own_entries(self):
        """Ein kaputter Block kostet nur seine eigenen Texte."""
        gute_antwort = self.router.chat.side_effect
        calls = {'n': 0}

        def flaky(**kwargs):
            calls['n'] += 1
            if calls['n'] == 2:
                raise ValueError('Anbieter hat gestreikt')
            return gute_antwort(**kwargs)

        self.router.chat.side_effect = flaky

        with self.assertLogs('core.services.ai.time_entry_normalization', level='ERROR'):
            result = TimeEntryNormalizationService().normalize(self.originals)

        self.assertTrue(result.failed)
        self.assertEqual(result.texts[0], 'Normalisiert 0.')
        self.assertEqual(result.texts[25], 'text 25')  # zweiter Block: Original
        self.assertEqual(result.texts[50], 'Normalisiert 50.')


@override_settings(AI_TIME_ENTRY_NORMALIZATION_ENABLED=True)
class NormalizationRouterUsageTestCase(SimpleTestCase):
    """Provider und Modell werden nicht hart kodiert, sondern vom Router gewählt."""

    def test_no_provider_or_model_is_pinned(self):
        router = MagicMock()
        router.chat.return_value = _response([{'index': 0, 'text': 'Wartung.'}])

        TimeEntryNormalizationService(router=router).normalize(['wartung'])

        kwargs = router.chat.call_args.kwargs
        self.assertNotIn('provider_type', kwargs)
        self.assertNotIn('model_id', kwargs)
