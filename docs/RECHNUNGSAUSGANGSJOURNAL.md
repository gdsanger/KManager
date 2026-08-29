# Rechnungsausgangsjournal

Das Rechnungsausgangsjournal (`finanzen.OutgoingInvoiceJournalEntry`) ist der
unveränderliche Nachweis aller ausgehenden Rechnungen und Gutschriften. Es ist
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
  unterstützten Satz entsprechen.
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

## Anzeige

Die Liste unter `auftragsverwaltung:journal_list` ist schreibgeschützt und
bietet Volltextsuche (Belegnummer, Kunde, Debitor), Filter nach Kunde,
Belegdatum, Belegart, Export-Status und Mandant sowie Summen über die gesamte
gefilterte Auswahl (nicht nur die aktuelle Seite).
