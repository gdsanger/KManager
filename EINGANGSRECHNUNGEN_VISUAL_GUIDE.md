# Visual Guide: Eingangsrechnungen Global Navigation

## Navigation Changes

### Before
```
├── Adressen
│   ├── Adressen
│   ├── Kunden
│   └── Lieferanten
├── Aktivitäten
│   ├── Kanban
│   ├── Alle Aktivitäten
│   ├── Meine zugewiesenen
│   └── Meine erstellten
├── Gebäude
│   ├── Standorte
│   ├── Objekte
│   ├── Verträge
│   └── Übergabeprotokolle
├── Finanzen
│   ├── Eingangsrechnungen  ← WAS HERE
│   └── Kostenarten
└── Einstellungen
```

### After
```
├── Adressen
│   ├── Adressen
│   ├── Kunden
│   └── Lieferanten
├── Aktivitäten
│   ├── Kanban
│   ├── Alle Aktivitäten
│   ├── Meine zugewiesenen
│   └── Meine erstellten
├── Gebäude
│   ├── Standorte
│   ├── Objekte
│   ├── Verträge
│   ├── Übergabeprotokolle
│   └── Eingangsrechnungen  ← NOW HERE
├── Finanzen
│   └── Kostenarten
└── Einstellungen
```

## List View Features

### Header Section
```
┌─────────────────────────────────────────────────────────┐
│ Eingangsrechnungen                                      │
│                                                         │
│ [Aus PDF erstellen] [Manuell erstellen]               │
└─────────────────────────────────────────────────────────┘
```

### Filter Section
```
┌─────────────────────────────────────────────────────────┐
│ 🔍 [Search field________________] [Status▼] [Objekt▼]  │
│    [Umlagefähig▼] [Filter] [×]                         │
│                                                         │
│    [Belegdatum von: ____] [Belegdatum bis: ____]      │
│                                             24 Rechnungen│
└─────────────────────────────────────────────────────────┘
```

### Table
```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Belegdatum ▲│ Belegnummer │ Lieferant │ Mietobjekt │ ... │ Status  │ Aktionen       │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ 01.02.2024  │ RE-2024-001 │ Firma GmbH│ Gebäude A  │ ... │ [OFFEN] │ [👁] [✏] [🗑] │
│ 31.01.2024  │ RE-2024-002 │ Supplier  │ Gebäude B  │ ... │ [BEZAHLT]│ [👁] [✏] [🗑] │
│ ...         │ ...         │ ...       │ ...        │ ... │ ...     │ ...           │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Pagination
```
┌─────────────────────────────────────────────────────────┐
│    [Zurück] [Seite 1 von 2] [Weiter]                   │
└─────────────────────────────────────────────────────────┘
```

## PDF Upload Form

```
┌─────────────────────────────────────────────────────────┐
│ Eingangsrechnung aus PDF erstellen                     │
│                                                         │
│ ℹ KI-gestützte PDF-Auswertung                          │
│   Die hochgeladene PDF-Rechnung wird automatisch       │
│   durch künstliche Intelligenz analysiert.             │
│                                                         │
│ Mietobjekt auswählen                                   │
│ [Bitte wählen... ▼]                                    │
│                                                         │
│ PDF-Datei hochladen                                    │
│ [Choose File] [No file chosen]                         │
│                                                         │
│                              [Abbrechen] [PDF hochladen]│
└─────────────────────────────────────────────────────────┘
```

## Upload Status Feedback

```
┌─────────────────────────────────────────────────────────┐
│ ⟳ PDF wird hochgeladen...                              │
│   Bitte warten Sie, während die Datei hochgeladen      │
│   und analysiert wird.                                 │
└─────────────────────────────────────────────────────────┘

           ↓ (after processing)

┌─────────────────────────────────────────────────────────┐
│ ⟳ KI-Extraktion läuft...                               │
│   Die Rechnungsdaten werden analysiert und extrahiert. │
└─────────────────────────────────────────────────────────┘

           ↓ (on success)

┌─────────────────────────────────────────────────────────┐
│ ✓ Rechnungsdaten wurden erfolgreich durch KI extrahiert│
│ ✓ Lieferant "Firma GmbH" wurde automatisch zugeordnet  │
│ ✓ Eingangsrechnung "RE-2024-123" wurde erfolgreich     │
│   angelegt und PDF hochgeladen.                        │
└─────────────────────────────────────────────────────────┘
```

## Column Details

### Table Columns (Left to Right)
1. **Belegdatum** - Invoice date (sortable, dd.mm.yyyy format)
2. **Belegnummer** - Invoice number (sortable, clickable link to detail)
3. **Lieferant** - Supplier (sortable by name)
4. **Mietobjekt** - Rental object (sortable by name)
5. **Betreff** - Subject (truncated to fit, sortable)
6. **Netto** - Net amount (right-aligned, EUR format)
7. **Brutto** - Gross amount (right-aligned, EUR format)
8. **Status** - Status badge (colored: NEU=gray, OFFEN=yellow, BEZAHLT=green)
9. **Fälligkeit** - Due date (sortable, dd.mm.yyyy format)
10. **Umlagefähig** - Allocatable (✓ or ✗ icon)
11. **Aktionen** - Action buttons (view/edit/delete)

### Filter Options
- **Search**: Searches across belegnummer, betreff, lieferant, referenznummer
- **Status**: NEU, PRÜFUNG, OFFEN, KLÄRUNG, BEZAHLT, Alle Status
- **Mietobjekt**: All rental objects in system, Alle Objekte
- **Umlagefähig**: Ja, Nein, Alle
- **Belegdatum von/bis**: Date range picker (HTML5 date input)

## Status Badges Color Scheme
- **NEU** (New): Secondary (gray)
- **PRÜFUNG** (Under Review): Info (blue)
- **OFFEN** (Open): Warning (yellow)
- **KLÄRUNG** (Needs Clarification): Danger (red)
- **BEZAHLT** (Paid): Success (green)

## User Workflow

### Creating Invoice from PDF
1. Click "Gebäude" in navigation
2. Click "Eingangsrechnungen"
3. Click "Aus PDF erstellen" button
4. Select Mietobjekt from dropdown
5. Choose PDF file
6. Click "PDF hochladen und analysieren"
7. Wait for AI extraction
8. Review pre-filled data in detail view
9. Edit/correct as needed
10. Save

### Searching Invoices
1. Navigate to Eingangsrechnungen
2. Enter search term in search box
3. Select additional filters (status, object, etc.)
4. Click "Filter" button
5. Results update instantly
6. Click column headers to sort
7. Click "×" to clear all filters

### Viewing Invoice Details
1. From list, click invoice number OR
2. Click eye icon in Aktionen column
3. Detail view shows all information
4. Can edit, mark as paid, or delete
5. Can navigate back to list

## Dark Theme Integration
All components use Bootstrap 5.3 dark theme:
- Dark background (#212529)
- Light text (#dee2e6)
- Colored badges and buttons
- Consistent with rest of application
- High contrast for accessibility

## Responsive Behavior
- Table scrolls horizontally on small screens
- Filters stack vertically on mobile
- Action buttons remain accessible
- Navigation collapses with hamburger menu
- Date pickers adapt to device

## Icons Used (Bootstrap Icons)
- 🔍 bi-search - Search field
- 📄 bi-file-earmark-pdf - PDF upload
- ➕ bi-plus-circle - Create new
- 👁 bi-eye - View details
- ✏ bi-pencil - Edit
- 🗑 bi-trash - Delete
- 🏢 bi-building - Gebäude section
- 🧾 bi-receipt - Eingangsrechnungen
- ✓ bi-check-circle - Success/Yes
- ✗ bi-x-circle - No
- ▲ bi-caret-up-fill - Sort ascending
- ▼ bi-caret-down-fill - Sort descending
- ⟳ spinner-border - Loading

## Performance Optimizations
- Single query for list with select_related('lieferant', 'mietobjekt')
- Prefetch for aufteilungen (related invoices)
- Pagination limits to 20 items per page
- Client-side sorting (no AJAX)
- Minimal JavaScript (vanilla JS only)

## Accessibility
- Semantic HTML5
- ARIA labels on buttons
- Keyboard navigation support
- Screen reader friendly
- High contrast ratios
- Focus indicators
