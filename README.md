# Vermietungs- & Verwaltungsplattform (Django + HTMX + Bootstrap + PostgreSQL)

Dieses Repository enthält die Grundlage für eine modulare Verwaltungsplattform zur **Vermietung beliebiger Mietobjekte** (Immobilien und bewegliche Güter).  
Beispiele: Gebäude, Büros, Räume, Container, Stellplätze, Lagerflächen, Geräte/Equipment u. v. m.

Das System wird langfristig in zwei grobe Bereiche gegliedert:

- **Vermietung**: Mietobjekte, Verfügbarkeit/Reservierungen, Verträge, Dokumente, (optional später Abrechnung)
- **Finanzen**: Finanz- und Vermögensverwaltung, Reporting/Dashboards (Phase 2)

Aktueller Fokus (Phase 1): **Domain-Entities und Beziehungen für „Vermietung“**.

---

## Ziele

- Ein **einheitliches Domänenmodell** für „alles was man vermieten kann“
- Unterstützung von Mietzeiträumen:
  - stunden- oder tagesgenau (`start_at`, `end_at`)
  - `end_at` kann **offen** sein (unbefristete Miete)
- Modellierung von **Beschaffenheit** und **Lage/Standort** eines Mietobjekts
  - Standardisierte Maße (z. B. qm, H×B×T)
  - Flexible typabhängige Attribute (z. B. Bodenbelag, Traglast, Ausstattung)
- **Multi-Tenant** (vorsorglich): mehrere Vermieter/Mandanten in einer Instanz
- UI-Ansatz: **Server Side Rendering mit HTMX** (keine SPA notwendig)
- Datenbank: **PostgreSQL**, mit DB-seitiger Absicherung wichtiger Integritätsregeln (z. B. Zeitüberschneidungen)

---

## Tech Stack

- Python (Version wird im Projekt festgelegt)
- Django
- HTMX (UI-Interaktionen via Partial Rendering)
- **Bootstrap 5.3** (UI Layout & Components)
- PostgreSQL

---

## Domänenüberblick (Vermietung)

### Kernkonzepte

- **Tenant**: Mandant/Vermieter (Multi-Tenant-Root)
- **Party**: Mieter/Kunde (Person oder Organisation)
- **Asset**: Mietobjekt (universell, egal ob Immobilie oder bewegliches Gut)
  - Hierarchisch (Parent/Child), z. B. Gebäude → Etage → Büro
- **Location**: Standort / Adresse (optional historisiert pro Asset)
- **AssetDimension**: Standardisierte Maße (qm, H×B×T)
- **AssetAttribute**: Flexible, typabhängige Eigenschaften via Definition/Value
- **Reservation**: Reservierung/Blocker zur Verfügbarkeitssteuerung
- **Contract**: Mietvertrag
- **ContractItem**: Vertragsposition: Asset + Zeitraum + Konditionen (ein Vertrag kann mehrere Assets enthalten)

### Zeitmodell

Zeiträume werden grundsätzlich als `start_at` / `end_at` (Datetime) geführt.

- `end_at = NULL` bedeutet **offenes Ende**
- Tagesmieten können über Konventionen abgebildet werden (z. B. Start 00:00, Ende 23:59:59 oder durch zusätzliche Flags in späteren Iterationen)
- Kollisionen (Überschneidungen) sollen sowohl auf Applikationsebene (Validation) als auch DB-seitig (Postgres Constraints) verhindert werden

---

## Multi-Tenant Ansatz (vorgesehen)

- Alle fachlichen Tabellen der Vermietung enthalten `tenant_id`
- Uniqueness/Constraints sind tenant-gescoped (z. B. Objekt-Nr pro Tenant eindeutig)
- Zugriff wird tenant-scoped (Middleware/Manager Pattern)

---

## Dashboards (Ausblick)

Es werden zwei Bereiche mit eigenen Dashboards entstehen:

### Dashboard „Vermietung“ (Phase 1/1.5)
Beispiele für Kennzahlen/Widgets:
- aktuell vermietete Assets / freie Assets
- auslaufende Verträge (nächste X Tage)
- offene Reservierungen / Optionen
- Assets in Wartung / Blocker

### Dashboard „Finanzen“ (Phase 2)
Beispiele:
- Einnahmen/Ausgaben
- Cashflow
- Vermögensübersicht (Assets als Anlagevermögen)
- Forderungen/Verbindlichkeiten

---

## Projektphasen (grobe Roadmap)

### Phase 1 – Vermietung: Entities & Beziehungen (aktueller Fokus)
- Tenant
- Party (+ Kontakte/Adressen)
- AssetType, Asset (inkl. Hierarchie)
- Location
- AssetDimension (qm, H×B×T)
- Flexible Asset-Attribute (Definition/Value)
- Reservation (Verfügbarkeit/Blocker)
- Contract + ContractItem (Vertragsverwaltung)

### Phase 1.5 – UI & Workflows (geplant)
- CRUD UI (Django Templates + Bootstrap 5.3 + HTMX)
- Verfügbarkeitsprüfung
- Workflow: Reservierung → Vertrag

### Phase 2 – Finanzen & Vermögensverwaltung (geplant)
- Finanzmodelle, Reporting, Dashboards
- Abrechnung/Billing (Rechnungen, Zahlungen, Mahnungen) – optional/modular

---

## Repository Struktur (geplant)

Empfohlene Django-App-Struktur:

- `core/` – tenant scoping, base models, helpers
- `parties/` – Mieter/Kunden
- `assets/` – AssetType/Asset, Hierarchie, Standort, Maße, Attribute
- `availability/` – Reservierungen/Blocker, Verfügbarkeitslogik
- `contracts/` – Verträge + Positionen
- `dashboards/` – Vermietung/Finanzen Dashboards (später)
- `finance/` – Finanzen/Vermögen (Phase 2)

---

## Nicht-Ziele (aktuell)

- Vollständige Billing-/Rechnungslogik in Phase 1
- Integrationen (DATEV, Banking, DMS) in Phase 1
- Komplexe Preis-/Tarifmodelle (Staffeln, indexierte Mieten etc.) in Phase 1

---

## Beiträge / Entwicklung

- Architektur und Domäne werden über GitHub Issues/Epics beschrieben.
- Änderungen am Domänenmodell sollen stets accompanied sein von:
  - Migrationen
  - Kurzer Doku-Anpassung (README/ADR/ERD)

---

## Lizenz / Rechtliches

TBD (Projektentscheidung offen).
