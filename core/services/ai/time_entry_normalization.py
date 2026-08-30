"""
KI-Normalisierung von Tätigkeitsbeschreibungen für Rechnungspositionen.

Tätigkeitsbeschreibungen einer Zeiterfassung entstehen im Arbeitsalltag:
Stichpunkte, interne Kürzel, Tippfehler, gelegentlich auch Formulierungen, die
auf einem Kundenbeleg unglücklich wirken. Dieser Service bringt die Texte in
die auf einer Dienstleistungsrechnung übliche Form - **ohne** inhaltlich etwas
zu ergänzen.

Aufbau analog ``InvoiceExtractionService``: fachlicher Service über dem
``AIRouter``, eigenes DTO, Validierung der Antwort, defensive Fehlerbehandlung.

Grundsätze:

- **Ein Aufruf je Block** (``BATCH_SIZE`` Einträge), nicht einer je Text.
- Die Zuordnung läuft über **Indizes** aus der Antwort, nie über die
  Reihenfolge im Antworttext.
- Fällt die KI aus (kein Schlüssel, Timeout, unbrauchbare Antwort), gilt der
  **Originaltext**. Der Aufrufer erfährt das über ``NormalizationResult.failed``
  und kann eine Warnung anzeigen - abgebrochen wird nichts.

Beispiel:
    >>> service = TimeEntryNormalizationService()
    >>> result = service.normalize(['tel. mit kd wg. bug', ''])
    >>> result.texts[1]
    ''
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from django.conf import settings
from django.contrib.auth.models import User

from core.services.ai.router import AIRouter
from core.services.base import ServiceDisabled, ServiceNotConfigured


logger = logging.getLogger(__name__)


@dataclass
class NormalizationResult:
    """
    Ergebnis eines Normalisierungslaufs.

    ``texts`` hat immer dieselbe Länge und Reihenfolge wie die Eingabe: für
    jeden nicht normalisierten Eintrag steht dort der Originaltext.
    """

    texts: List[str] = field(default_factory=list)
    #: True, sobald mindestens ein Block nicht normalisiert werden konnte.
    failed: bool = False
    #: Klartext des ersten Fehlers (für Log und Oberfläche).
    error: Optional[str] = None
    #: Anzahl der tatsächlich abgesetzten KI-Aufrufe (0 = abgeschaltet/nichts zu tun).
    calls: int = 0

    @property
    def ai_used(self) -> bool:
        return self.calls > 0


class TimeEntryNormalizationService:
    """
    Bringt Tätigkeitsbeschreibungen in eine für die Rechnung übliche Form.

    Der Prompt liegt als Konstante ``NORMALIZATION_PROMPT`` an genau dieser
    Stelle und kann nachjustiert werden, ohne einen Aufrufer anzufassen.
    """

    #: Einträge je KI-Aufruf. Eine Monatsabrechnung hat leicht 30-60 Einträge;
    #: die werden blockweise geschickt statt einzeln.
    BATCH_SIZE = 25

    #: Grobes Token-Budget je Eintrag plus Aufschlag für das JSON-Gerüst.
    MAX_TOKENS_PER_ENTRY = 160
    MAX_TOKENS_OVERHEAD = 400

    NORMALIZATION_PROMPT = """Du bereitest Tätigkeitsbeschreibungen aus einer Zeiterfassung für eine Dienstleistungsrechnung auf.

Du bekommst ein JSON-Objekt mit einer Liste „entries". Jeder Eintrag hat „index" (Zahl) und „text" (die Originalbeschreibung).

Regeln:
1. KEINE INHALTLICHEN ERGÄNZUNGEN. Das ist die wichtigste Regel. Erfinde nichts hinzu, was nicht im Originaltext steht - keine Leistung, keine Dauer, kein Datum, kein Ergebnis, keinen Ort, keine Namen. Im Zweifel weniger schreiben, nicht mehr.
2. Zielform: ein bis zwei vollständige, sachliche Sätze in der dritten Person oder als Nominalphrase, wie auf einer Dienstleistungsrechnung üblich.
3. Rechtschreibung, Grammatik und Zeichensetzung korrigieren; einheitliche Zeitform.
4. Gängige Fachbegriffe bleiben erhalten. Interne Kürzel und Abkürzungen ausschreiben, sofern sie eindeutig sind; ist ein Kürzel nicht eindeutig, bleibt es unverändert stehen.
5. Wertende, entschuldigende oder schuldzuweisende Formulierungen neutralisieren (aus „Fehler von letzter Woche behoben" wird „Behebung eines Fehlers").
6. Ist ein Text leer oder nur ein unverständliches Fragment, gib ihn UNVERÄNDERT zurück. Rate nicht, was gemeint sein könnte.
7. Die Sprache bleibt Deutsch.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in genau dieser Form, ohne Markdown, ohne Erklärung:
{"entries": [{"index": 0, "text": "Normalisierter Text."}]}

Gib zu jedem übergebenen „index" genau einen Eintrag zurück und übernimm den Index unverändert."""

    def __init__(self, router: Optional[AIRouter] = None):
        """Initialisiert den Service. ``router`` ist nur für Tests gedacht."""
        self.router = router or AIRouter()

    # ------------------------------------------------------------------
    # Öffentliche Schnittstelle
    # ------------------------------------------------------------------

    @staticmethod
    def is_enabled() -> bool:
        """Ist die Normalisierung eingeschaltet? (Setting, Standard: an)"""
        return bool(getattr(settings, 'AI_TIME_ENTRY_NORMALIZATION_ENABLED', True))

    def normalize(
        self,
        descriptions: Sequence[Optional[str]],
        user: Optional[User] = None,
        client_ip: Optional[str] = None,
    ) -> NormalizationResult:
        """
        Normalisiert eine Liste von Tätigkeitsbeschreibungen.

        Args:
            descriptions: Originaltexte in der Reihenfolge der Positionen
            user: auslösender Benutzer (für die AI-Job-Historie), optional
            client_ip: IP des Aufrufers, optional

        Returns:
            NormalizationResult - ``texts`` in derselben Reihenfolge wie die
            Eingabe. Nicht normalisierte Einträge tragen den Originaltext.

        Es wird nie eine Exception aus dem KI-Aufruf durchgereicht: ein Ausfall
        des Anbieters darf keinen Abrechnungslauf abbrechen.
        """
        originals = [(text or '') for text in descriptions]
        result = NormalizationResult(texts=list(originals))

        if not self.is_enabled():
            logger.debug('Normalisierung der Tätigkeitsbeschreibungen ist abgeschaltet.')
            return result

        # Leere Texte gehen gar nicht erst an die KI - sie bleiben unverändert.
        pending = [index for index, text in enumerate(originals) if text.strip()]
        if not pending:
            return result

        for block_start in range(0, len(pending), self.BATCH_SIZE):
            block = pending[block_start:block_start + self.BATCH_SIZE]
            try:
                normalized = self._normalize_block(originals, block, user, client_ip)
            except (ServiceNotConfigured, ServiceDisabled) as exc:
                # Ohne konfigurierten Anbieter scheitern auch alle Folgeblöcke.
                logger.error(
                    'KI-Dienst für die Normalisierung nicht verfügbar: %s', exc
                )
                result.failed = True
                result.error = result.error or str(exc)
                break
            except Exception as exc:  # pragma: no cover - defensiv
                logger.error(
                    'Normalisierung eines Blocks fehlgeschlagen (%s Einträge): %s',
                    len(block), exc, exc_info=True,
                )
                result.failed = True
                result.error = result.error or str(exc)
                continue

            result.calls += 1

            missing = [index for index in block if index not in normalized]
            if missing:
                # Fehlende Indizes werden NICHT über die Reihenfolge geraten.
                logger.warning(
                    'KI-Antwort enthält %s von %s angefragten Einträgen nicht - '
                    'für diese gilt der Originaltext.',
                    len(missing), len(block),
                )
                result.failed = True
                result.error = result.error or (
                    'Die KI-Antwort war unvollständig.'
                )

            for index, text in normalized.items():
                result.texts[index] = text

        return result

    # ------------------------------------------------------------------
    # Interna
    # ------------------------------------------------------------------

    def _normalize_block(
        self,
        originals: List[str],
        block: List[int],
        user: Optional[User],
        client_ip: Optional[str],
    ) -> Dict[int, str]:
        """
        Ein KI-Aufruf für einen Block von Indizes.

        Returns:
            Dict Index -> normalisierter Text. Enthält nur Einträge, die
            eindeutig zugeordnet und plausibel sind.
        """
        payload = {
            'entries': [{'index': index, 'text': originals[index]} for index in block]
        }

        response = self.router.chat(
            messages=[
                {'role': 'system', 'content': self.NORMALIZATION_PROMPT},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
            ],
            user=user,
            client_ip=client_ip,
            agent='core.ai.time_entry_normalization',
            temperature=0.0,
            max_tokens=self.MAX_TOKENS_OVERHEAD + self.MAX_TOKENS_PER_ENTRY * len(block),
        )

        return self._parse_response(response.text, block)

    @classmethod
    def _parse_response(cls, raw_text: str, block: List[int]) -> Dict[int, str]:
        """
        Wertet die Antwort aus und ordnet sie über die Indizes zu.

        Verworfen wird alles, was nicht eindeutig ist: unbekannte oder doppelte
        Indizes, fehlende oder leere Texte. Für solche Einträge gilt beim
        Aufrufer der Originaltext.
        """
        text = (raw_text or '').strip()
        if not text:
            raise ValueError('Die KI hat eine leere Antwort geliefert.')

        # Markdown-Codeblöcke entfernen (wie in InvoiceExtractionService).
        if text.startswith('```'):
            text = '\n'.join(
                line for line in text.split('\n') if not line.startswith('```')
            ).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error('KI-Antwort ist kein gültiges JSON: %s', raw_text[:500])
            raise ValueError(f'Die KI-Antwort war kein gültiges JSON: {exc}') from exc

        if isinstance(data, dict):
            entries = data.get('entries')
        elif isinstance(data, list):
            entries = data
        else:
            entries = None

        if not isinstance(entries, list):
            raise ValueError('Die KI-Antwort enthält keine Liste „entries".')

        allowed = set(block)
        normalized: Dict[int, str] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            index = entry.get('index')
            value = entry.get('text')
            if isinstance(index, bool) or not isinstance(index, int):
                continue
            if index not in allowed or index in normalized:
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            normalized[index] = value.strip()

        return normalized
