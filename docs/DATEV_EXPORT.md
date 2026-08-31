# DATEV-Buchungsstapel-Export (EXTF)

GIS exportiert Ausgangs- und Eingangsbelege als DATEV-Buchungsstapel im
EXTF-Format. Damit übernimmt ein beliebiges Fibu-System oder ein Steuerberater
die eigentliche Buchhaltung – UStVA, EÜR, AfA, Kontenblätter –, ohne dass GIS
selbst eine Buchhaltung wird. Die Belegerfassung inklusive KI-Belegerkennung
bleibt in GIS.

## Verwendete Formatversion

| Angabe | Wert |
|---|---|
| Kennzeichen | `EXTF` |
| DATEV-Versionsnummer | `700` |
| Formatkategorie | `21` (Buchungsstapel) |
| Formatname | `Buchungsstapel` |
| Formatversion | `13` |
| Spaltenanzahl je Buchungssatz | **125** |
| Zeichensatz | Windows-1252 (ANSI) |
| Trennzeichen | `;` |
| Textbegrenzer | `"` |
| Dezimaltrennzeichen | `,` (deutsches Zahlenformat) |
| Zeilenende | CRLF |

Die Feldliste steht als **eine** Konstante `BOOKING_COLUMNS` in
`finanzen/services/datev_export.py`. DATEV entwickelt das Format versioniert
weiter; ein Versionswechsel wird ausschließlich dort nachgezogen.

> **Offener Punkt:** Kopfsatz, Feldreihenfolge und Zahlenformat sind noch
> nicht gegen den Importer des Zielsystems (aktuell in Prüfung: Kontolino)
> verifiziert. Dafür gibt es das Management-Command
> `python manage.py datev_export --sample --output probe.csv` (siehe unten).
> Die Prüfung sollte **vor** dem ersten Echteinsatz erfolgen.

## Datenquellen

### Einnahmenseite

Ausschließlich `finanzen.OutgoingInvoiceJournalEntry` (Rechnungsausgangsjournal).
`SalesDocument` wird vom Export **nicht** gelesen. Nur so sind die exportierten
Werte echte Snapshots und ändern sich nicht nachträglich mit dem Beleg mit.

Buchungssatz je Steuersatz-Topf:

```
Konto = Debitorenkonto   an   Gegenkonto = Erlöskonto      Umsatz = brutto
```

Soll/Haben ergibt sich aus dem Vorzeichen: Rechnungen stehen positiv im
Journal (`S`), Gutschriften negativ (`H`).

### Ausgabenseite

`lieferantenwesen.InvoiceIn` mit Status `APPROVED` oder `PAID` – nicht
freigegebene Rechnungen gehören nicht in den Buchungsstapel.

```
Konto = Aufwandskonto    an   Gegenkonto = Kreditorenkonto  Umsatz = brutto
```

Hat die Rechnung Positionen, wird je Kombination aus Aufwandskonto und
Steuersatz ein Buchungssatz gebildet. Positionssummen müssen zur Kopfsumme
passen, sonst wird der Beleg gemeldet statt still falsch gebucht.

### Mandantenbezug

Ein Buchungsstapel gehört immer zu genau **einem** Mandanten – dessen Berater-
und Mandantennummer stehen im Kopfsatz. Beide Seiten werden deshalb auf den
gewählten Mandanten gefiltert: die Ausgangsseite über
`OutgoingInvoiceJournalEntry.company`, die Eingangsseite über
`InvoiceIn.company`.

`InvoiceIn.company` wird beim Erfassen gepflegt; bei genau einem Mandanten ist
das Feld vorbelegt. Fehlt der Mandant, leitet `InvoiceIn.save()` ihn aus
`order.company` und ersatzweise aus `rental_object.mandant` ab. Ein bereits
gesetzter Mandant wird dabei **nie** überschrieben.

Eine buchungsreife Eingangsrechnung **ohne** Mandant wird nicht exportiert und
auch nicht still übergangen: Sie steht in der Fehlerliste („Der Rechnung ist
kein Mandant zugeordnet.") und blockiert den Download, bis der Mandant
nachgepflegt ist. Auffinden lassen sich solche Belege über den Filter
„Ohne Mandant" in der Eingangsrechnungsliste.

## Kontierung über die Kostenarten

Die Auflösungsregel ist an genau **einer** Stelle implementiert:
`finanzen/services/accounts.py`. Ein- und Ausgangsseite nutzen sie gemeinsam.

| Seite | Reihenfolge |
|---|---|
| Aufwand | Unterkostenart → Hauptkostenart → *Fehler* |
| Erlös | Unterkostenart → Hauptkostenart → `revenue_account_{0,7,19}` des Mandanten → *Fehler* |

`core.Kostenart` trägt dafür `aufwandskonto` und `erloeskonto`; beide sind auf
Haupt- und Unterkostenart pflegbar. Ist an einer Kostenart ein Erlöskonto
hinterlegt, übersteuert es das Konto aus dem Steuersatz.

**Wichtig für die Erlösseite:** Die Auflösung passiert bereits bei der
Finalisierung (`finanzen/services/journal.py`) und landet im Journal-Snapshot.
Der Export liest nur diesen Snapshot. Wer ein Erlöskonto nachträglich ändert,
muss den Beleg neu finalisieren, damit die Änderung greift – das ist
beabsichtigt.

Zeigen zwei Positionen desselben Steuersatzes auf unterschiedliche
Erlöskonten, wird die Finalisierung mit einem Fehler abgelehnt: Das Journal
führt je Steuersatz genau ein Konto, eine stille Auswahl wäre eine
Falschbuchung.

## Umsatzsteuer und BU-Schlüssel

Es wird **kein BU-Schlüssel** gesetzt. Die Steuer leitet das Zielsystem aus
dem Automatikkonto ab (z. B. SKR03/04 „Erlöse 19 % USt" = 8400). Ein selbst
gesetzter BU-Schlüssel wäre kontenrahmenabhängig und würde bei falscher Wahl
still falsch buchen.

Die rechnerische Steuer je Steuersatz wird vor dem Export gegen die im Beleg
ausgewiesene Steuer geprüft. Rundungsdifferenzen aus der positionsweisen
Steuerberechnung landen im betragsstärksten steuerpflichtigen Topf, damit die
Belegsumme cent-genau bleibt. Weicht die Steuer um mehr als 1,00 € ab, wird
der Beleg gemeldet statt exportiert.

## Ist- oder Soll-Versteuerung

Für GIS irrelevant. Die Versteuerungsart ist kein Bestandteil eines
Buchungssatzes, sondern eine Einstellung des Fibu-Systems, das daraus die
UStVA ableitet. Die dafür nötigen Zahlungsbuchungen erzeugt GIS nicht – sie
entstehen im Fibu-System aus dessen Bankanbindung beim Ausgleich der offenen
Posten.

## Personenkonten

Debitoren- und Kreditorenkonten sind rein numerisch, ohne Präfix und ohne
Jahresbestandteil. Ein Personenkonto gehört dauerhaft zu einem
Geschäftspartner und darf sich nicht jährlich ändern.

| Typ | Bereich | Nummernkreis |
|---|---|---|
| Debitoren (`adressen_type='KUNDE'`) | 10000–69999 | `NumberRange` mit `target='CUSTOMER'` |
| Kreditoren (`adressen_type='LIEFERANT'`) | 70000–99999 | `NumberRange` mit `target='SUPPLIER'` |

Beide Nummernkreise sind global (kein Mandant), haben `format='{seq}'`,
`reset_policy='NEVER'` und einen `start_seq` (10000 bzw. 70000). Die Vergabe
läuft race-sicher über `select_for_update()` in
`auftragsverwaltung/services/number_range.py`.

Die Bereichsgrenzen stehen in den Django-Settings
(`DEBITOR_ACCOUNT_RANGE` / `CREDITOR_ACCOUNT_RANGE`) und sind damit für
abweichende Kontenrahmen anpassbar.

Beide Konten liegen im Feld `core.Adresse.debitor_number` – eine Adresse ist
entweder Kunde oder Lieferant, ein zweites Feld hätte eine zweite
Nummernschicht mit eigener Eindeutigkeitsproblematik bedeutet.

### Migration des Bestands

`core/migrations/0037_datev_personenkonten.py` ersetzt die alten
`DEB26-00001`-Werte durch fortlaufende numerische Konten:

- Reihenfolge stabil (bisherige Nummer, dann `pk`).
- Bereits numerische Konten im passenden Bereich bleiben unangetastet und
  blockieren ihre Nummer für andere.
- `current_seq` der Nummernkreise wird nachgezogen, damit Neuanlagen nicht
  mit dem Bestand kollidieren.
- Idempotent: Ein zweiter Lauf ändert nichts.

Die **Kunden-Nr. auf der Rechnung** (`templates/printing/orders/invoice.html`)
zeigt dieselbe Nummer und ändert sich für Bestandskunden entsprechend mit.

## Stammdatenexport der Personenkonten

Der Buchungsstapel bucht gegen Personenkonten, trägt davon aber nur die
**Kontonummer** in die Datei. Wer die Buchungen einliest, kann sie ohne die
zugehörigen Stammdaten keinem Namen zuordnen – beim ersten Import existieren
die Personenkonten im Zielsystem überhaupt noch nicht. Der Stammdatenexport
liefert die fehlende Gegenseite: je Adresse mit Personenkonto eine Zeile mit
Name, Anschrift und Kontaktdaten.

`Auftragsverwaltung → Buchhaltung → Personenkonten-Export`
(`/auftragsverwaltung/buchhaltung/personenkonten-export/`), Service:
`finanzen/services/partner_export.py`.

### Auswahl

Ein Export für beide Seiten, mit der Auswahl **Debitoren** (`adressen_type='KUNDE'`),
**Kreditoren** (`adressen_type='LIEFERANT'`) oder **beide** (Vorbelegung). Der
Satzaufbau ist identisch; unterschieden wird allein über den Kontenbereich –
zwei getrennte Exporte wären derselbe Code zweimal. Adressen der übrigen Typen
(`Adresse`, `STANDORT`, `SONSTIGES`) führen kein Personenkonto und erscheinen
in keiner Auswahl.

**Keine Mandantenauswahl:** `core.Adresse` hat keinen Mandantenbezug,
Personenkonten sind in GIS mandantenübergreifend.

**Kein Zeitraum- und kein Änderungsfilter:** Exportiert werden immer alle
Adressen mit Personenkonto. Stammdaten werden einmal vollständig übergeben und
bei Bedarf erneut; der Download verändert keine Daten und ist beliebig
wiederholbar. Ein Gegenstück zu `mark_exported()` gibt es hier bewusst nicht.

### Vorschau und Fehlerliste

Die Vorschau zeigt die Anzahl der Datensätze je Kontoart. Nicht exportierbare
Adressen werden **nicht still weggelassen**, sondern gelistet:

- Adresse **ohne** Personenkonto.
- Personenkonto **außerhalb** des zum Adresstyp gehörenden Bereichs oder nicht
  rein numerisch (möglich bei importierten Altdaten). Die Grenzen kommen über
  `Adresse.personal_account_range()` aus denselben Settings wie die Validierung
  bei der Neuanlage.

Anders als beim Buchungsstapel blockiert die Fehlerliste den Download **nicht**:
Ein fehlendes Personenkonto ist ein Pflegehinweis, kein falscher Buchungssatz.
Die betroffenen Adressen stehen in der Vorschau und fehlen in der Datei. Auf
doppelte Kontonummern wird nicht geprüft – die UniqueConstraint
`unique_debitor_number` schließt sie bereits aus.

### Dateiformat

Bewusst **kein EXTF-Kopfsatz** und keine DATEV-Formatkategorie 16
(„Debitoren/Kreditoren"): Diese schreibt mehrere hundert Spalten in fester
Reihenfolge vor, die sich ohne die DATEV-Formatbeschreibung nicht korrekt
nachbilden lässt – eine geratene Feldliste würde bei einem echten DATEV-Import
abgewiesen. Zielsystem ist Kontolino; dort wird beim Import ohnehin **manuell
gemappt**, formatseitige Vorgaben gibt es nicht. Die Datei ist deshalb eine CSV
mit sprechender Überschriftenzeile, technisch aber in derselben Hülle wie der
Buchungsstapel (`finanzen/services/datev_common.py`), damit Umlaute und
Trennzeichen sich gleich verhalten:

| Angabe | Wert |
|---|---|
| Zeichensatz | Windows-1252 (ANSI) |
| Trennzeichen | `;` |
| Textbegrenzer | `"` |
| Zeilenende | CRLF |
| Kopfsatz | keiner; 1. Zeile = Spaltennamen |

Die Spaltenliste steht als **eine** Konstante `PARTNER_COLUMNS` – wie
`BOOKING_COLUMNS` beim Buchungsstapel:

| Spalte | Herkunft |
|---|---|
| Konto | `debitor_number` (als Text, führende Nullen bleiben erhalten) |
| Kontoart | „Debitor" / „Kreditor", aus `adressen_type` |
| Adressattyp | „Unternehmen" / „natürliche Person", aus `is_business` |
| Firma | `firma` |
| Name | `name` |
| Anrede | `get_anrede_display()` (Klartext) |
| Straße | `strasse` |
| PLZ | `plz` |
| Ort | `ort` |
| Land | `land` |
| Ländercode | `country_code` |
| USt-IdNr. | `vat_id` |
| EU | „ja" / „nein", aus `is_eu` |
| E-Mail | `email` |
| E-Mail Rechnung | `invoice_email` |
| Telefon | `telefon` |
| Mobil | `mobil` |

Firma und Name stehen **getrennt**; der zusammengesetzte `matchkey` wird
bewusst nicht exportiert, damit das Zielsystem die Felder einzeln zuordnen
kann. Leere Felder bleiben leer – kein Platzhaltertext, keine Ersatzwerte.

Bankverbindung und Zahlungsbedingungen sind **nicht** Bestandteil der Datei:
`Adresse` führt keine Bankverbindung (eine IBAN gibt es nur am Mandanten und
an der einzelnen Eingangsrechnung), und `core.PaymentTerm` hängt nicht an der
Adresse.

### Import im Zielsystem

Die Spaltenzuordnung passiert **beim Import im Zielsystem**. Kontolino fragt
sie beim Einlesen ab; die sprechende Überschriftenzeile ist genau dafür da.
Ein Ausbau auf das EXTF-Format der Formatkategorie 16 bleibt möglich, sobald
die DATEV-Formatbeschreibung vorliegt – Ansatzpunkt ist `PARTNER_COLUMNS`.

## Buchhaltungseinstellungen

`finanzen.CompanyAccountingSettings` je Mandant, pflegbar im Django-Admin:

- **Beraternummer / Mandantennummer** – Pflichtfelder des EXTF-Kopfsatzes.
  Vorbelegt mit den Platzhaltern `1001` und `1`. Solange der Stapel nicht an
  einen Steuerberater übermittelt wird, genügen die Platzhalter; der Export
  funktioniert mit beiden.
- **Sachkontenlänge** (Standard 4) und **Wirtschaftsjahresbeginn** – gehen in
  den Kopfsatz ein. Ohne Wirtschaftsjahresbeginn gilt der 1. Januar des
  Exportjahres.
- **Erlöskonten je Steuersatz** (0 %, 7 %, 19 %).
- **Gegenkonten Bank / Kasse / Verrechnung** – für die Einrichtung des
  Zielsystems; GIS exportiert selbst keine Zahlungsbuchungen.

## Bedienung

### UI

`Auftragsverwaltung → Buchhaltung → DATEV-Export`
(`/auftragsverwaltung/buchhaltung/datev-export/`):

1. Mandant und Zeitraum wählen (Monat, Quartal oder Jahr).
2. Vorschau erzeugen: Anzahl der Buchungssätze, Summen je Seite, Soll/Haben.
3. **Fehlerliste** prüfen. Solange Belege ohne auflösbares Konto oder
   Eingangsrechnungen ohne Mandanten vorhanden sind, ist der Download gesperrt
   – ein stillschweigend kleinerer Stapel wäre der teurere Fehler.
4. EXTF-Datei herunterladen. Der Download kennzeichnet die enthaltenen Belege
   als exportiert.

Ein Zeitraum darf nicht über einen Jahreswechsel gehen: Das Belegdatum eines
Buchungssatzes trägt nur Tag und Monat, der Jahresbezug kommt aus dem Kopfsatz.

### Wiederholungsexport

Bereits exportierte Belege bleiben standardmäßig außen vor. Für einen
bewussten Wiederholungsexport nach einem Fehlimport gibt es die Option
„Bereits exportierte Belege erneut aufnehmen". Jeder Export vergibt eine
Batch-ID, die am Beleg gespeichert wird (`export_batch_id`) – ein
Wiederholungsexport ist damit im Nachhinein erkennbar.

### Kommandozeile

```bash
# Formatprüfung: kleine Beispieldatei ohne Zugriff auf Echtbelege
python manage.py datev_export --sample --output probe.csv

# Vorschau eines Zeitraums: nur Zusammenfassung, keine Datei, kein Statuswechsel
python manage.py datev_export --company 1 --from 2026-01-01 --to 2026-01-31

# Datei schreiben, Export-Status unverändert lassen
python manage.py datev_export --company 1 --from 2026-01-01 --to 2026-01-31 \
    --output stapel.csv

# Export mit Statuspflege (setzt --output voraus)
python manage.py datev_export --company 1 --from 2026-01-01 --to 2026-01-31 \
    --output stapel.csv --mark-exported
```

## Nicht im Scope

- Eigene UStVA-, EÜR- oder AfA-Auswertungen in GIS.
- Zahlungsbuchungen im Export – der Ausgleich der offenen Posten passiert im
  Fibu-System über dessen Bankanbindung.
- Rückimport von Buchungen oder Zahlungen aus dem Fibu-System.
- Zahlungserfassung mit Teilzahlungen und Verrechnung in GIS.
- Anbieterspezifische API-Anbindung.

## Verwandte Doku

- `docs/RECHNUNGSAUSGANGSJOURNAL.md` – Quelle der Einnahmenseite
