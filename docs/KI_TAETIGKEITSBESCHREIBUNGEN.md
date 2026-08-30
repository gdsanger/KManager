# KI-Aufbereitung der Tätigkeitsbeschreibungen (Projekt-Abrechnung)

Beim Projekt-Abrechnungslauf (`auftragsverwaltung/services/project_billing.py`)
wird je Zeiterfassung eine Rechnungsposition erzeugt. Deren **Langtext** ist die
Tätigkeitsbeschreibung der Zeiterfassung — geschrieben im Arbeitsalltag, nicht
für den Kunden: Stichpunkte, interne Kürzel, Tippfehler, wechselnde Zeitformen.

Damit auf dem Beleg eine für eine Dienstleistungsrechnung übliche Formulierung
steht, werden diese Texte vor dem Anlegen der Positionen per KI aufbereitet.

## Was normalisiert wird

- Rechtschreibung, Grammatik und Zeichensetzung
- Zielform: ein bis zwei vollständige, sachliche Sätze in der dritten Person
  oder als Nominalphrase
- eindeutige interne Kürzel und Abkürzungen werden ausgeschrieben
- wertende, entschuldigende oder schuldzuweisende Formulierungen werden
  neutralisiert („Fehler von letzter Woche behoben" → „Behebung eines Fehlers")
- die Sprache bleibt **Deutsch**

## Was ausdrücklich **nicht** passiert

- **Keine inhaltlichen Ergänzungen.** Es wird nichts hinzuerfunden, was nicht im
  Originaltext steht — keine Leistung, keine Dauer, kein Datum, kein Ergebnis.
  Eine Rechnungsposition, die eine nicht erbrachte Leistung beschreibt, ist ein
  Problem gegenüber dem Kunden; diese Vorgabe hat deshalb Vorrang vor jeder
  sprachlichen Glättung.
- **Kein Raten.** Ein leerer Text oder ein unverständliches Fragment wird
  unverändert übernommen.
- Keine Übersetzung, keine Zusammenfassung mehrerer Zeiterfassungen zu einem
  gemeinsamen Text.

## Die Zeiterfassung bleibt unverändert

`TimeEntry.description` behält den **Originaltext**. Aufbereitet wird nur
`SalesDocumentLine.long_text` der erzeugten Rechnungsposition. Die Zeiterfassung
ist der interne Arbeitsnachweis, die Rechnungsposition das Kundendokument — die
beiden dürfen auseinanderlaufen.

Einen eigenen Freigabeschritt gibt es bewusst nicht: die Rechnung entsteht immer
als Entwurf (`DRAFT`) und wird ohnehin geprüft, bevor sie finalisiert wird. Dort
lassen sich einzelne Langtexte von Hand nachziehen.

## Wo der Prompt steht

`core/services/ai/time_entry_normalization.py`, Konstante
`TimeEntryNormalizationService.NORMALIZATION_PROMPT`. Der Prompt liegt an genau
dieser einen Stelle und lässt sich nachjustieren, ohne einen Aufrufer anzufassen.

Der Aufruf läuft über den `AIRouter` (`core/services/ai/router.py`); Provider und
Modell kommen aus der Konfiguration (`AIProvider`/`AIModel`), sie sind **nicht**
im Service hart kodiert. Die Aufrufe erscheinen in der AI-Job-Historie unter dem
Agent `core.ai.time_entry_normalization`.

## Blockweiser Aufruf

Eine Monatsabrechnung hat leicht 30–60 Positionen. Es wird deshalb **ein Aufruf
je Block** von 25 Einträgen abgesetzt (`TimeEntryNormalizationService.BATCH_SIZE`),
nicht ein Aufruf je Position. Die Texte gehen nummeriert hin und werden
nummeriert zurückerwartet; die Zuordnung läuft ausschließlich über diese
Indizes, nie über die Reihenfolge im Antworttext.

## Wenn die KI ausfällt

Ein Ausfall — kein Schlüssel konfiguriert, Zeitüberschreitung, Fehler beim
Anbieter, unbrauchbare oder unvollständige Antwort — bricht den Abrechnungslauf
**nicht** ab:

1. Die betroffenen Positionen tragen die Originalbeschreibung als Langtext.
   Liefert die Antwort nur einen Teil der angefragten Indizes, gilt das nur für
   die fehlenden — geraten wird nichts.
2. Der Anwender bekommt nach dem Lauf eine Warnmeldung, dass die Texte nicht
   aufbereitet werden konnten und die Langtexte im Entwurf zu prüfen sind.
3. Der Fehler steht im Log (`core.services.ai.time_entry_normalization`) und —
   bei konfiguriertem `SENTRY_DSN` — in Sentry.

## Abschalten

Setting `AI_TIME_ENTRY_NORMALIZATION_ENABLED` in `kmanager/settings.py`,
steuerbar über die Umgebungsvariable gleichen Namens. Standard: **eingeschaltet**.

```bash
# .env
AI_TIME_ENTRY_NORMALIZATION_ENABLED=False
```

Ist die Normalisierung aus, wird ohne jeden KI-Aufruf der Originaltext in die
Position übernommen — für den Betrieb ohne KI-Zugang und für Testsysteme.

In den Testeinstellungen (`test_settings.py`, `kmanager/test_settings.py`) ist
sie grundsätzlich **aus**. Tests, die die Aufbereitung prüfen, schalten sie
gezielt per `@override_settings` ein und mocken den `AIRouter`
(`core/test_time_entry_normalization.py`,
`auftragsverwaltung/test_project_billing_normalization.py`) — kein Test ruft
einen echten Anbieter auf.
