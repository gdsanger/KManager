# Rechnungsausgangsjournal

Das Rechnungsausgangsjournal (`finanzen.OutgoingInvoiceJournalEntry`) ist der
Nachweis aller ausgehenden Rechnungen und Gutschriften. Ein einmal erzeugter
Eintrag wird nicht mehr nachgeführt oder editiert (Snapshot-Prinzip); als
Korrekturweg lässt er sich im Admin-Backend löschen und neu erzeugen (siehe
[Korrigieren und Löschen](#korrigieren-und-löschen)). Es ist
auf der Einnahmenseite die **alleinige Basis für den DATEV-Export**: Der Export
liest ausschließlich das Journal, nie `SalesDocument` direkt. Nur so bleiben
exportierte Werte Snapshots und ändern sich nicht nachträglich mit dem Beleg.

## Wann entsteht ein Eintrag?

Bei der **Finalisierung** eines journalrelevanten Belegs (Echtdruck oder
Versand per E-Mail). Zuständig ist
`auftragsverwaltung.services.invoice_finalization.finalize_document()`:

1. Belegnummer vergeben (falls noch keine vorhanden)
2. Status auf `SENT` setzen
3. Journaleintrag über `finanzen.services.journal.create_journal_entry()` erzeugen

Alle drei Schritte laufen in **einer Transaktion**. Schlägt die Journalerzeugung
fehl, bleibt der Beleg unfinalisiert – ein Beleg mit Nummer, aber ohne
Journaleintrag kann nicht entstehen.

Die Erzeugung ist **idempotent**: Echtdruck und anschließender E-Mail-Versand
laufen beide durch `finalize_document()`, erzeugen aber zusammen genau einen
Eintrag (Unique-Constraint `(company, document)` plus Vorabprüfung im Service).

## Journalrelevante Belegarten

| Dokumenttyp-Flag | `document_kind` | Vorzeichen |
|------------------|-----------------|------------|
| `is_correction`  | `CREDIT_NOTE`   | negativ    |
| `is_invoice`     | `INVOICE`       | positiv    |
| sonst            | –               | kein Eintrag |

`is_correction` wird zuerst geprüft: Ein Dokumenttyp mit beiden Flags (z. B.
„Rechnungskorrektur") ist fachlich eine Gutschrift.

Gutschriften werden mit **negativen Beträgen** gebucht (zusätzlich zum
Kennzeichen `document_kind`). Eine Summe über das Journal ergibt damit direkt
den Umsatz der Periode.

## Beträge und Steuersätze

- Die Nettobeträge werden je Steuersatz auf `net_0`, `net_7`, `net_19` verteilt.
- Grundlage sind die Belegpositionen, die in die Belegsummen eingehen
  (`NORMAL` sowie ausgewählte `OPTIONAL`/`ALTERNATIVE`-Positionen).
- Das Ergebnis wird **cent-genau** gegen `total_net` / `total_tax` /
  `total_gross` des Belegs geprüft. Bei Abweichung bricht die Finalisierung mit
  dem Hinweis ab, den Beleg neu zu berechnen.
- Belege **ohne Positionen** (Altbestand) werden aus den Belegsummen abgeleitet;
  der Steuersatz ergibt sich aus `total_tax / total_net` und muss exakt einem
  unterstützten Satz entsprechen. Seit #1195 rechnet der
  `DocumentCalculationService` die Steuer je Steuersatz auf die Nettosumme, ein
  neu berechneter Beleg trifft diesen Satz also exakt und scheitert nicht mehr
  an reiner Rundungsdrift (früher z. B. 38,03 / 200,00 = 19,02 %).
- Unterstützt sind ausschließlich **0 %, 7 % und 19 %**. Jeder andere Steuersatz
  führt zu `UnsupportedTaxRateError` (Unterklasse von `ValueError`) mit
  verständlicher Meldung – kein stiller Falscheintrag.

Die Erlöskonten aus `CompanyAccountingSettings` werden als Snapshot mitkopiert;
ohne gepflegte Einstellungen bleiben sie leer.

## Bestandsdaten nachtragen

Für Belege, die vor der Journal-Anbindung finalisiert wurden, gibt es ein
Management-Command (bewusst **keine** Migration, damit der Vorgang kontrolliert
und prüfbar bleibt):

```bash
# Trockenlauf: zeigt nur an, was passieren würde
python manage.py backfill_journal_entries --dry-run

# Echtlauf
python manage.py backfill_journal_entries

# Optional: auf einen Mandanten einschränken bzw. Stornos einbeziehen
python manage.py backfill_journal_entries --company 1 --include-cancelled
```

Berücksichtigt werden Rechnungen und Gutschriften mit Belegnummer, deren Status
nicht `DRAFT` ist. Stornierte Belege (`CANCELLED`) werden ohne
`--include-cancelled` übersprungen. Das Command ist wiederholbar und legt keine
Dubletten an; fachlich fehlerhafte Belege werden gemeldet und übersprungen.

## Korrigieren und Löschen

Im Django-Admin (`/admin/finanzen/outgoinginvoicejournalentry/`) gilt bewusst
eine **Asymmetrie**:

| Vorgang     | Admin | Begründung |
|-------------|-------|------------|
| Anlegen     | nein  | Einträge entstehen nur aus einem finalisierten Beleg |
| Bearbeiten  | nein  | Ein editierbarer Snapshot wäre kein Snapshot mehr |
| Löschen     | **ja**| Korrekturweg statt Eingriff direkt in der Datenbank |

Ein falscher Eintrag wird also nicht feldweise repariert, sondern **verworfen
und neu erzeugt**. Das ist kein Datenverlust:

- Der FK `OutgoingInvoiceJournalEntry.document` steht auf `PROTECT` – er
  schützt das `SalesDocument` vor dem Löschen, nicht den Journaleintrag. Der
  Beleg bleibt beim Löschen des Eintrags unverändert bestehen.
- `create_journal_entry()` ist idempotent und legt zu einem Beleg genau einen
  Eintrag an – eine Wiederherstellung erzeugt keine Dublette.

**Korrekturweg:**

```bash
# 1. Eintrag im Admin löschen (einzeln oder über die Massenaktion)
# 2. Ursache am Beleg beheben (Kontierung, Steuersatz, Positionen …)
# 3. Eintrag neu erzeugen – erst prüfen, dann schreiben:
python manage.py backfill_journal_entries --dry-run
python manage.py backfill_journal_entries
```

Alternativ genügt eine **erneute Finalisierung** des Belegs (Echtdruck oder
E-Mail-Versand): `finalize_document()` ruft `create_journal_entry()` bei jedem
Aufruf auf und legt den fehlenden Eintrag wieder an.

**Nach einem Durchrechnen der Bestandsbelege:**
`python manage.py recalculate_document_totals` fasst Journaleinträge bewusst
nicht an. Ändern sich dabei die Summen eines bereits finalisierten Belegs, ist
genau der obige Korrekturweg zu gehen: Eintrag im Admin löschen, dann
`backfill_journal_entries`. Solange das nicht geschehen ist, trägt der
Journaleintrag noch den alten Steuerbetrag – der Beleg selbst ist dann bereits
korrigiert.

**Bereits exportierte Einträge:** Ist `export_status == 'EXPORTED'`, ist der
Eintrag Teil eines DATEV-Buchungsstapels, der bereits im Fibu-System liegt.
Das Löschen wird deshalb nicht verhindert, aber der Admin gibt eine Warnung mit
Belegnummer und `export_batch_id` aus – sowohl beim Einzellöschen als auch bei
der Massenaktion. Die Buchung im Fibu-System muss dort separat korrigiert
werden; das Löschen hier zieht sie nicht zurück.

## Anzeige

Die Liste unter `auftragsverwaltung:journal_list` ist schreibgeschützt und
bietet Volltextsuche (Belegnummer, Kunde, Debitor), Filter nach Kunde,
Belegdatum, Belegart, Export-Status und Mandant sowie Summen über die gesamte
gefilterte Auswahl (nicht nur die aktuelle Seite). Eine Löschaktion gibt es im
Frontend bewusst **nicht** – Löschen ist ausschließlich dem Admin-Backend
vorbehalten.
