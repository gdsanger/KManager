# Textbausteine Feature - UI Visual Guide

This guide provides descriptions of the user interface components for the Textbausteine feature.

## 📱 Navigation

### Sidebar Menu
```
Auftragsverwaltung
├── Angebote
├── Aufträge
├── Rechnungen
├── Lieferscheine
├── Gutschriften
├── Verträge
└── Textbausteine ← NEW MENU ITEM
```

**Icon:** `bi-blockquote-left` (Bootstrap Icons)  
**Route:** `/auftragsverwaltung/textbausteine/`

---

## 📋 Textbausteine List View

### Header Section
- **Page Title:** "Textbausteine"
- **Action Button:** "Neu erstellen" (Primary button with plus icon)

### Filter Section
Three filter inputs in a row:
1. **Search Field** (4 columns)
   - Icon: Search icon (magnifying glass)
   - Placeholder: "Suche nach Titel, Schlüssel, Inhalt..."
   - Full-text search across title, key, and content

2. **Type Filter** (2 columns)
   - Dropdown: "Alle Typen", "Kopftext", "Fußtext", "Kopf- und Fußtext"

3. **Status Filter** (2 columns)
   - Dropdown: "Alle", "Aktiv", "Inaktiv"

4. **Action Buttons** (4 columns)
   - "Filter" button (with funnel icon)
   - "X" button to reset filters (shown when filters are active)

### Table Columns
1. **Titel** - Clickable link to edit view
2. **Typ** - Colored badge:
   - Blue badge: "Kopftext" (HEADER)
   - Yellow badge: "Fußtext" (FOOTER)
   - Green badge: "Kopf- und Fußtext" (BOTH)
3. **Schlüssel** - Unique key identifier
4. **Aktiv** - Checkmark icon (✓) or dash (—)
5. **Aktualisiert** - Date and time (format: d.m.Y H:i)
6. **Aktionen** - Two icon buttons:
   - Pencil icon: Edit (Primary outline button)
   - Trash icon: Delete (Danger outline button)

### Pagination
- Standard Bootstrap pagination at bottom
- 25 items per page
- Shows current page and total pages

---

## ✏️ Textbausteine Form View (Create/Edit)

### Header Section
- **Page Title:** "Textbaustein erstellen" or "Textbaustein bearbeiten"
- **Back Button:** "Zurück" (Secondary outline button with left arrow)

### Form Layout (8 columns centered)

**Section 1: Basic Information (Row 1)**
- **Titel** (6 columns, required)
  - Text input
  - Help text: "Anzeigename für die Auswahl im Dropdown"
  
- **Schlüssel** (6 columns, required)
  - Text input with pattern validation `[a-z0-9_-]+`
  - Help text: "Eindeutiger Kurzbezeichner (z.B. standard_header)"

**Section 2: Type and Options (Row 2)**
- **Typ** (4 columns, required)
  - Dropdown: "Kopftext", "Fußtext", "Kopf- und Fußtext"
  - Help text: "Verwendungszweck des Textbausteins"

- **Sortierung** (4 columns, optional)
  - Number input, default: 0
  - Help text: "Sortierreihenfolge (0 = oben)"

- **Status** (4 columns)
  - Toggle switch: "Aktiv"
  - Help text: "Inaktive Bausteine werden ausgeblendet"
  - Default: Checked

**Section 3: Content**
- **Inhalt** (Full width, required)
  - Large textarea (10 rows)
  - Monospace font for better text editing
  - Help text: "Textinhalt des Bausteins"

### Action Buttons (Right-aligned)
1. "Abbrechen" - Secondary outline button with X icon
2. "Speichern" - Primary button with checkmark icon

---

## 🗑️ Delete Confirmation View

### Layout (6 columns centered)

**Card with Danger Border**
- **Header (Red background)**
  - Icon: Exclamation triangle
  - Title: "Textbaustein löschen"

**Body**
- Lead text: "Möchten Sie den folgenden Textbaustein wirklich löschen?"

- **Warning Box (Yellow/Warning)**
  - Template title in bold
  - Template type in parentheses
  - Small text: "Schlüssel: [key]"

- **Info Text (Gray)**
  - Icon: Info circle
  - Message: "Diese Aktion kann nicht rückgängig gemacht werden. Bereits in Dokumenten verwendeter Text bleibt erhalten."

**Action Buttons (Right-aligned)**
1. "Abbrechen" - Secondary outline button with X icon
2. "Löschen" - Danger button with trash icon

---

## 📄 SalesDocument Detail View Integration

### Text Section (Tabbed Interface)

**Tabs:**
1. Kopfzeile (Header) - Active by default
2. Fußzeile (Footer)
3. Notizen (Notes)

### Kopfzeile Tab Content

**Template Selection Row:**
- **Dropdown** (8 columns)
  - Label: "-- Textbaustein wählen --" (placeholder)
  - Options: List of active header templates sorted by sort_order, title
  - Each option shows template title
  
- **Apply Button** (4 columns)
  - Primary outline button
  - Icon: Down arrow circle
  - Text: "Übernehmen"

**Text Area:**
- Large textarea for `header_text`
- 4 rows
- Placeholder: "Kopftext des Dokuments"
- ID: `header_text`

### Fußzeile Tab Content

**Template Selection Row:**
- **Dropdown** (8 columns)
  - Label: "-- Textbaustein wählen --" (placeholder)
  - Options: List of active footer templates sorted by sort_order, title
  
- **Apply Button** (4 columns)
  - Primary outline button
  - Icon: Down arrow circle
  - Text: "Übernehmen"

**Text Area:**
- Large textarea for `footer_text`
- 4 rows
- Placeholder: "Fußtext des Dokuments"
- ID: `footer_text`

---

## 🔔 User Interactions

### Template Application Flow

1. **User selects template from dropdown**
   - Dropdown shows template titles
   - Data attributes store template content

2. **User clicks "Übernehmen" button**
   - JavaScript checks if template is selected
   - If no template: Shows error toast "Bitte wählen Sie einen Textbaustein aus."
   - If template selected and textarea has content:
     - Shows confirmation dialog: "Der [Kopf/Fuß]text enthält bereits Text. Möchten Sie ihn überschreiben?"
     - If confirmed: Proceeds to step 3
     - If cancelled: Aborts operation
   - If template selected and textarea is empty: Proceeds to step 3

3. **Content is copied to textarea**
   - Template content copied from data attribute
   - Textarea value updated
   - Form marked as "dirty" (unsaved changes)
   - Success toast shown: "Textbaustein erfolgreich übernommen"

### Toast Notifications

**Success Toast (Green background):**
- Header: "Benachrichtigung"
- Body: "Textbaustein erfolgreich übernommen"
- Auto-hides after 3 seconds
- Close button available

**Error Toast (Red background):**
- Header: "Benachrichtigung"
- Body: Error message (e.g., "Bitte wählen Sie einen Textbaustein aus.")
- Auto-hides after 3 seconds
- Close button available

**Position:** Top-right corner (Bootstrap toast-container)

### Confirmation Dialogs

**Native browser confirm() dialog:**
- Message: "Der [Kopf/Fuß]text enthält bereits Text. Möchten Sie ihn überschreiben?"
- Buttons: "OK" / "Abbrechen"
- Blocking modal (must respond before continuing)

---

## 🎨 Styling

### Color Scheme (Bootstrap 5 Dark Theme)
- **Primary Color:** Blue (Bootstrap primary)
- **Secondary Color:** Gray (Bootstrap secondary)
- **Success Color:** Green
- **Danger Color:** Red
- **Warning Color:** Yellow
- **Info Color:** Light Blue

### Type Badges
- **HEADER:** `bg-info` (light blue)
- **FOOTER:** `bg-warning` (yellow)
- **BOTH:** `bg-success` (green)

### Card Styling
- Dark background: `bg-dark`
- Dark borders: Bootstrap border utilities
- Rounded corners: Bootstrap border-radius

### Form Elements
- Bootstrap 5 form controls
- Dark mode compatible
- Consistent spacing with mb-3, mb-2 utilities
- Help text in muted color

### Buttons
- Primary: Solid blue background
- Outline: Transparent with colored border
- Icon + text combination
- Consistent sizing (btn, btn-sm)

### Table
- Bootstrap 5 Dark table
- Hover effect on rows
- Dark header
- Responsive (scrolls horizontally on mobile)

---

## 📱 Responsive Behavior

### Mobile (< 768px)
- Table scrolls horizontally
- Filter inputs stack vertically
- Sidebar collapsible with hamburger menu
- Form inputs full width

### Tablet (768px - 992px)
- Filter inputs may wrap to 2 rows
- Table columns condensed
- Sidebar remains visible

### Desktop (> 992px)
- All elements at full width
- Sidebar fixed position
- Optimal column spacing

---

## ♿ Accessibility

- All form inputs have labels
- Help text associated with inputs
- ARIA labels on icon buttons
- Keyboard navigation support
- Color contrast meets WCAG AA standards
- Focus indicators visible
- Screen reader friendly

---

## 🔍 Empty States

### No Templates Available
When no templates match filters:
- Table shows "Keine Daten verfügbar" message
- Pagination hidden
- Filter reset button shown

### No Active Templates
When user has no active templates:
- Dropdowns in document view show only placeholder
- Apply button disabled (grayed out)
- User must create templates first

---

This visual guide complements the technical implementation documentation and provides a complete picture of the user interface.
