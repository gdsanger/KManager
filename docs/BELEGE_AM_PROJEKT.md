# Verkaufsbelege am Projekt

`auftragsverwaltung.SalesDocument` trägt mit `projekt` eine optionale
Zuordnung zu `core.Projekt`. Die Zuordnung liegt bewusst am **Belegkopf** und
gilt für **alle Belegarten** — ein Projektangebot oder ein Projektauftrag ist
genauso zuordnungswürdig wie die Rechnung.

## Feld

| Eigenschaft | Wert |
|-------------|------|
| Feld | `SalesDocument.projekt` |
| Ziel | `core.Projekt` (`related_name='sales_documents'`) |
| Löschverhalten | `PROTECT` |
| Pflicht | nein (`null=True, blank=True`) |
| Index | ja (`SalesDocument.Meta.indexes`) |

`PROTECT` statt `SET_NULL`: Bei kaufmännischen Belegen darf die Zuordnung
nicht stillschweigend verloren gehen. Ein Projekt mit Belegen lässt sich daher
nicht löschen; `projekt_delete` fängt das ab und meldet es verständlich, statt
in einen `ProtectedError` zu laufen.

## Validierung

`SalesDocument.get_projekt_assignment_error()` prüft die Zuordnung, `clean()`
meldet den Fehler am Feld `projekt`:

- Ist am Projekt ein **Kunde** hinterlegt und weicht er vom Kunden des Belegs
  ab → Fehler.
- Ist am Projekt ein **Mandant** hinterlegt und weicht er vom Mandanten des
  Belegs ab → Fehler.
- Ist am Projekt weder Kunde noch Mandant gepflegt (internes Projekt), wird
  nichts geprüft.

Die Belegmasken (`document_create`, `document_update`) rufen dieselbe Prüfung
auf und rendern das Formular mit einer Meldung erneut, ohne zu speichern.

## Pflege im Beleg

Im Kopfbereich der Belegmaske steht das Auswahlfeld „Projekt" (leere Option =
keine Zuordnung). Angeboten werden Projekte **ohne Kunde** sowie Projekte
**des am Beleg gewählten Kunden**; ohne Kunde am Beleg stehen alle Projekte
zur Auswahl (`get_selectable_projekte()`).

Die Zuordnung bleibt in **jedem Belegstatus** änderbar — sie ist eine
Auswertungszuordnung und kein Bestandteil des Belegs gegenüber dem Kunden.

Der Projekt-Abrechnungslauf (`ProjectBillingService`) setzt `projekt` an der
erzeugten Rechnung automatisch.

## Projektseite

Die Projekt-Detailseite zeigt im Abschnitt „Belege" alle zugeordneten Belege
(Belegart, Nummer verlinkt, Belegdatum, Status, Netto, Brutto), absteigend nach
Belegdatum. Darüber steht eine Kennzahlenzeile mit zwei **getrennten** Werten
(`get_projekt_belege_context()`):

- **Fakturiert** — Nettosumme der finalisierten Rechnungen und Gutschriften
  (Status ≠ `DRAFT`, `document_type.is_invoice` oder `is_correction`).
- **In Entwurf** — Nettosumme aller Belege im Status `DRAFT`.

Gutschriften (`document_type.is_correction`) gehen mit negativem Vorzeichen in
die jeweilige Summe ein und sind in der Liste per Badge erkennbar.

Beide Werte werden **nicht** addiert: Ein Entwurf ist kein Umsatz, eine
gemeinsame Summe würde die Projektauswertung systematisch zu hoch erscheinen
lassen. Ein angenommenes Angebot zählt aus demselben Grund in keine der beiden
Summen.

## Belegübersicht

Die Belegliste (`document_list`) lässt sich über `SalesDocumentFilter` nach
Projekt filtern; die Spalte „Projekt" verlinkt auf die Projektseite und bleibt
leer, wenn keine Zuordnung besteht.

## Nicht abgedeckt

Projektergebnisrechnung (Erlöse gegen Kosten), Budgets/Kostendeckel,
Zuordnung von Eingangsrechnungen sowie eine Zuordnung einzelner Belegpositionen
zu unterschiedlichen Projekten.
