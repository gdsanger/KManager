# Übergabeprotokoll UI - Visual Description

Since we cannot run the application in this environment (requires PostgreSQL), here's a detailed description of what the UI looks like based on the templates.

## 1. List View (`/vermietung/uebergabeprotokolle/`)

### Layout
- **Header**: "Übergabeprotokolle" with "Neues Übergabeprotokoll" button (primary blue)
- **Search Bar**: 
  - Text input: "Suche nach Vertrag, Mietobjekt, Mieter, Personen..."
  - Dropdown filter: "Alle Typen", "Einzug", "Auszug"
  - "Suchen" button
  - Count: "X Protokolle" displayed on the right
- **Table**: Dark theme (table-dark) with columns:
  - Datum (clickable, links to detail)
  - Typ (badge: green for Einzug, yellow for Auszug)
  - Vertrag (clickable, links to vertrag detail)
  - Mietobjekt (clickable, links to mietobjekt detail)
  - Mieter (name)
  - Aktionen (eye icon for detail, pencil icon for edit)
- **Pagination**: Centered at bottom if more than 20 items

### Color Scheme
- Background: Dark theme
- Badges: 
  - Einzug: Green badge with box-arrow-in-right icon
  - Auszug: Yellow badge with box-arrow-left icon
- Buttons: Bootstrap primary (blue), info (light blue), warning (yellow)

## 2. Detail View (`/vermietung/uebergabeprotokolle/<pk>/`)

### Header
- Title: "Übergabeprotokoll: Einzug" (or Auszug)
- Action buttons:
  - "Bearbeiten" (warning/yellow)
  - "Löschen" (danger/red)
  - "Zurück zur Liste" (secondary/gray)

### Main Content (Left Column - 8/12 width)

#### Card 1: Übergabedaten
- Typ: Badge (green/yellow)
- Übergabedatum: Formatted as "01.01.2024"
- Person Vermieter: Name
- Person Mieter: Name

#### Card 2: Vertrag
- Vertragsnummer: Link to vertrag detail
- Mieter: Link to kunde detail
- Vertragszeitraum: Start - End (or "unbefristet")

#### Card 3: Mietobjekt
- Name: Link to mietobjekt detail
- Typ: Display value
- Standort: Address with street and city

#### Card 4: Zählerstände
- Strom (kWh): Value or "-"
- Gas (m³): Value or "-"
- Wasser (m³): Value or "-"

#### Card 5: Schlüssel
- Anzahl übergeben: Number

#### Card 6: Bemerkungen & Mängel (if any)
- Bemerkungen: Text (preserves line breaks)
- Mängel: Shown in warning alert box if present

### Sidebar (Right Column - 4/12 width)

#### Card: Information
- Protokoll-ID
- Typ
- Datum

#### Card: Verknüpfungen
- "Zum Vertrag" button (outline primary)
- "Zum Mietobjekt" button (outline primary)

### Bottom Section
#### Documents Tab (if any)
- Table showing:
  - Dateiname
  - Hochgeladen am
  - Hochgeladen von
  - Größe
  - Download button

## 3. Create/Edit Form (`/vermietung/uebergabeprotokolle/neu/`)

### Header
- Title: "Neues Übergabeprotokoll" (or "bearbeiten")
- If from vertrag: Shows "für Vertrag V-00001" subtitle
- "Abbrechen" button (secondary/gray)

### Main Form (Left Column - 8/12 width)

#### Section 1: Vertragsinformationen
- Vertrag dropdown (required, with asterisk)
- Mietobjekt dropdown (required, with asterisk)
- Note: In guided flow, these are read-only/disabled

#### Section 2: Übergabedaten
- Typ: Dropdown (Einzug/Auszug) - required
- Übergabedatum: Date picker - required
- Person Vermieter: Text input
- Person Mieter: Text input

#### Section 3: Zählerstände
Three inputs in a row (4 columns each):
- Zählerstand Strom: Number input with "kWh" suffix
- Zählerstand Gas: Number input with "m³" suffix
- Zählerstand Wasser: Number input with "m³" suffix

#### Section 4: Schlüssel
- Anzahl Schlüssel: Number input

#### Section 5: Bemerkungen & Mängel
- Bemerkungen: Textarea (4 rows)
- Mängel: Textarea (4 rows)

#### Action Buttons
- "Speichern" (primary/blue) on left
- "Abbrechen" (secondary/gray) on right

### Sidebar (Right Column - 4/12 width)

#### Card: Hinweise
Different content based on context:
- Guided flow: Explains vertrag is fixed
- Standalone: Explains how to select vertrag/mietobjekt
- Always includes help for typ, zählerstände, schlüssel, mängel

## 4. Integration in Vertrag Detail

### In Übergabeprotokolle Tab
- Header row with:
  - Left: "Übergabeprotokolle für diesen Vertrag"
  - Right: "Neues Protokoll" button (small primary)
- Table showing existing protocols with:
  - Same columns as list view
  - Extra "Aktionen" column with eye icon
- Empty state: "Keine Übergabeprotokolle vorhanden"

## Design Patterns Used

### Consistent with Existing UI
- Same dark theme (table-dark)
- Same card layout
- Same button styles and icons
- Same Bootstrap 5 components
- Same color scheme and spacing

### Icons (Bootstrap Icons)
- clipboard-check: Übergabeprotokoll
- box-arrow-in-right: Einzug
- box-arrow-left: Auszug
- speedometer2: Zählerstände
- key: Schlüssel
- chat-left-text: Bemerkungen
- file-earmark-text: Vertrag
- building: Mietobjekt
- person-badge: Mieter
- eye: View
- pencil: Edit
- trash: Delete
- plus-circle: Create
- arrow-left: Back

### Responsive Design
- Main content: col-lg-8
- Sidebar: col-lg-4
- Mobile: Stacks vertically
- Tables: table-responsive wrapper

### User Feedback
- Success messages: Green alerts
- Error messages: Red alerts
- Validation errors: Red text below fields
- Confirmation dialogs: JavaScript confirm() for delete
