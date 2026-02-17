# Visual Guide: Bemerkung Field Implementation

## Overview
This document provides a visual description of the UI changes for the new "Bemerkung" (remark/note) field in the Mietvertrag (rental contract) feature.

---

## 📋 Form View (Create/Edit Contract)

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Vertrag erstellen/bearbeiten                     │
├─────────────────────────────┬──────────────────────────────────────────┤
│                             │                                          │
│  Main Form (col-lg-8)       │  Sidebar (col-lg-4)                     │
│                             │                                          │
│  ┌─────────────────────┐   │  ┌────────────────────────────────────┐ │
│  │ Vertragsdaten       │   │  │ 📝 Bemerkung (NEW!)               │ │
│  ├─────────────────────┤   │  ├────────────────────────────────────┤ │
│  │ - Vertragsnummer    │   │  │ ┌────────────────────────────────┐ │ │
│  │ - Mieter            │   │  │ │ Label: Bemerkung               │ │ │
│  └─────────────────────┘   │  │ ├────────────────────────────────┤ │ │
│                             │  │ │ Textarea (4 rows)              │ │ │
│  ┌─────────────────────┐   │  │ │ Placeholder: "Hinweise oder    │ │ │
│  │ Objekte             │   │  │ │  Bemerkungen zum Mietvertrag..."│ │ │
│  ├─────────────────────┤   │  │ │                                │ │ │
│  │ Table with objects  │   │  │ │                                │ │ │
│  └─────────────────────┘   │  │ └────────────────────────────────┘ │ │
│                             │  │ Help text: "Freitextfeld für       │ │
│  ┌─────────────────────┐   │  │  Hinweise und Bemerkungen..."     │ │
│  │ Zeitraum            │   │  └────────────────────────────────────┘ │
│  └─────────────────────┘   │                                          │
│                             │  ┌────────────────────────────────────┐ │
│  ┌─────────────────────┐   │  │ ℹ️ Hinweise                        │ │
│  │ Finanzielle Kondit. │   │  ├────────────────────────────────────┤ │
│  └─────────────────────┘   │  │ Information about contract         │ │
│                             │  │ creation and fields                │ │
│  ┌─────────────────────┐   │  └────────────────────────────────────┘ │
│  │ Status & Mandant    │   │                                          │
│  └─────────────────────┘   │  ┌────────────────────────────────────┐ │
│                             │  │ ⚙️ Aktionen (only in edit mode)   │ │
│                             │  └────────────────────────────────────┘ │
└─────────────────────────────┴──────────────────────────────────────────┘
```

### Card Details: Bemerkung (NEW!)

```html
┌──────────────────────────────────────────────────┐
│ 📝 Bemerkung                                     │ ← Card Header (bg-light)
├──────────────────────────────────────────────────┤
│                                                  │
│ Bemerkung                                        │ ← Label (form-label)
│ ┌──────────────────────────────────────────────┐ │
│ │ Hinweise oder Bemerkungen zum Mietvertrag... │ │ ← Textarea (4 rows)
│ │                                              │ │   Bootstrap styled
│ │                                              │ │   (form-control)
│ │                                              │ │
│ └──────────────────────────────────────────────┘ │
│ Freitextfeld für Hinweise und Bemerkungen...    │ ← Help text (form-text)
│                                                  │
└──────────────────────────────────────────────────┘
```

**Visual Properties:**
- **Icon**: 📝 (bi-chat-left-text)
- **Position**: Right sidebar, ABOVE "Hinweise" card
- **Card Style**: Bootstrap 5 card with header
- **Widget**: Textarea with 4 rows
- **Styling**: form-control (Bootstrap 5)
- **Placeholder**: "Hinweise oder Bemerkungen zum Mietvertrag..."
- **Validation**: Error messages appear below textarea in red

---

## 📄 Detail View (View Contract)

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Vertrag: V-00001                                    │
├─────────────────────────────┬──────────────────────────────────────────┤
│                             │                                          │
│  Main Content (col-lg-8)    │  Sidebar (col-lg-4)                     │
│                             │                                          │
│  ┌─────────────────────┐   │  ┌────────────────────────────────────┐ │
│  │ Vertragsdaten       │   │  │ 📝 Bemerkung (NEW!)               │ │
│  ├─────────────────────┤   │  ├────────────────────────────────────┤ │
│  │ - Vertragsnummer    │   │  │ Content of bemerkung field         │ │
│  │ - Status            │   │  │ (multi-line preserved)             │ │
│  │ - Mandant           │   │  │                                    │ │
│  └─────────────────────┘   │  │ OR                                 │ │
│                             │  │                                    │ │
│  ┌─────────────────────┐   │  │ Keine Bemerkung vorhanden          │ │
│  │ Objekte im Vertrag  │   │  │ (if empty, shown in italic gray)   │ │
│  ├─────────────────────┤   │  └────────────────────────────────────┘ │
│  │ Table with objects  │   │                                          │
│  └─────────────────────┘   │  ┌────────────────────────────────────┐ │
│                             │  │ ℹ️ Information                     │ │
│  ┌─────────────────────┐   │  ├────────────────────────────────────┤ │
│  │ Zeitraum & Mieter   │   │  │ - Vertragsnummer: V-00001          │ │
│  └─────────────────────┘   │  │ - Status: Aktiv                    │ │
│                             │  │ - ID: 123                          │ │
│  ┌─────────────────────┐   │  └────────────────────────────────────┘ │
│  │ Finanzielle Kondit. │   │                                          │
│  └─────────────────────┘   │  ┌────────────────────────────────────┐ │
│                             │  │ ⚙️ Aktionen                        │ │
│  ┌─────────────────────┐   │  ├────────────────────────────────────┤ │
│  │ Übergabeprotokolle  │   │  │ - Vertrag beenden                  │ │
│  └─────────────────────┘   │  │ - Vertrag stornieren               │ │
│                             │  └────────────────────────────────────┘ │
│  ┌─────────────────────┐   │                                          │
│  │ Dokumente           │   │                                          │
│  └─────────────────────┘   │                                          │
│                             │                                          │
│  ┌─────────────────────┐   │                                          │
│  │ Aktivitäten         │   │                                          │
│  └─────────────────────┘   │                                          │
└─────────────────────────────┴──────────────────────────────────────────┘
```

### Card Details: Bemerkung (NEW!)

**Case 1: When bemerkung is present**

```html
┌──────────────────────────────────────────────────┐
│ 📝 Bemerkung                                     │ ← Card Header
├──────────────────────────────────────────────────┤
│                                                  │
│ Dies ist eine Testbemerkung für den Vertrag.    │ ← Text content
│ Mehrere Zeilen werden korrekt dargestellt.      │   (white-space: pre-wrap)
│                                                  │   Preserves line breaks
│ • Punkt 1                                        │
│ • Punkt 2                                        │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Case 2: When bemerkung is empty**

```html
┌──────────────────────────────────────────────────┐
│ 📝 Bemerkung                                     │ ← Card Header
├──────────────────────────────────────────────────┤
│                                                  │
│ Keine Bemerkung vorhanden                        │ ← Placeholder text
│                                                  │   (italic, gray, em tag)
│                                                  │
└──────────────────────────────────────────────────┘
```

**Visual Properties:**
- **Icon**: 📝 (bi-chat-left-text)
- **Position**: Right sidebar, ABOVE "Information" card
- **Card Style**: Bootstrap 5 card with header (same as other sidebar cards)
- **Text Style**: 
  - With content: Normal paragraph, white-space: pre-wrap
  - Without content: Italic, muted gray text
- **Header**: h5 with icon

---

## 🎨 Styling Details

### Bootstrap Classes Used

**Form View:**
```css
.card                      /* Card container */
.card-header              /* Header with icon */
.card-body                /* Body content */
.form-label               /* Field label */
.form-control             /* Textarea styling */
.form-text                /* Help text */
.text-danger              /* Error messages */
.mb-3                     /* Bottom margin */
```

**Detail View:**
```css
.card                      /* Card container */
.card-header              /* Header with icon */
.card-body                /* Body content */
.mb-0                     /* No bottom margin for text */
.text-muted               /* Gray text for empty state */
```

### Custom Styles

**Detail View Text Preservation:**
```html
<p class="mb-0" style="white-space: pre-wrap;">{{ vertrag.bemerkung }}</p>
```
- `white-space: pre-wrap` ensures line breaks are preserved
- Essential for multi-line text display

---

## 🎯 User Experience

### Creating/Editing a Contract

1. **Access**: Users see the bemerkung field in the right sidebar
2. **Input**: Multi-line textarea with helpful placeholder
3. **Optional**: Field can be left empty (not required)
4. **Save**: Content is saved when form is submitted
5. **Feedback**: Help text explains the field purpose

### Viewing a Contract

1. **Display**: Bemerkung shows prominently in sidebar
2. **Formatting**: Line breaks preserved for readability
3. **Empty State**: Clear message when no bemerkung exists
4. **Consistency**: Matches other sidebar card styling

---

## 📱 Responsive Behavior

### Desktop (≥ 992px)
- Two-column layout (col-lg-8 + col-lg-4)
- Bemerkung card in right sidebar

### Tablet/Mobile (< 992px)
- Single-column layout
- Bemerkung card appears after main form content
- Full-width display

---

## ✨ Icon Reference

- **Bemerkung Card**: `bi-chat-left-text` (📝)
- **Hinweise Card**: `bi-info-circle` (ℹ️)
- **Information Card**: `bi-info-circle` (ℹ️)
- **Aktionen Card**: `bi-gear` (⚙️)

---

## 🔍 Accessibility

- **Labels**: Properly associated with inputs via `for` attribute
- **Help Text**: Connected to field via `aria-describedby`
- **Placeholder**: Provides clear guidance
- **Error Messages**: Clearly indicated with `.text-danger` class
- **Semantic HTML**: Uses proper heading levels (h5) and structure

---

## 📝 Content Examples

### Example 1: Simple Note
```
Wichtiger Hinweis: Mieter hat spezielle Anforderungen bezüglich der Schlüsselübergabe.
```

### Example 2: Multi-line with Formatting
```
Bemerkungen zum Vertrag:

• Kaution wurde in zwei Raten bezahlt
• Übergabetermin: 01.03.2024
• Renovierung vor Einzug erforderlich

Kontakt: Max Mustermann (0123-456789)
```

### Example 3: Detailed Information
```
Vertragliche Sondervereinbarungen:

1. Parkplatz #23 ist im Mietpreis enthalten
2. Nutzung des Gemeinschaftsraums möglich
3. Kündigungsfrist: 6 Monate zum Quartalsende

Ansprechpartner Hausverwaltung:
Frau Schmidt, Tel: 0123-999888
```

---

## 🔄 Positioning Comparison

### Before (without Bemerkung field)

**Form View - Right Sidebar:**
```
1. Hinweise (ℹ️)
2. Aktionen (⚙️) [only in edit mode]
```

**Detail View - Right Sidebar:**
```
1. Information (ℹ️)
2. Aktionen (⚙️)
```

### After (with Bemerkung field)

**Form View - Right Sidebar:**
```
1. Bemerkung (📝) ← NEW!
2. Hinweise (ℹ️)
3. Aktionen (⚙️) [only in edit mode]
```

**Detail View - Right Sidebar:**
```
1. Bemerkung (📝) ← NEW!
2. Information (ℹ️)
3. Aktionen (⚙️)
```

---

## ✅ Implementation Checklist

- [x] Field added to model (TextField, nullable, blank)
- [x] Database migration created
- [x] Form configuration with Textarea widget
- [x] Form template updated (right sidebar, above "Hinweise")
- [x] Detail template updated (right sidebar, above "Information")
- [x] Bootstrap 5 styling applied
- [x] Icon added (bi-chat-left-text)
- [x] Help text and labels configured
- [x] Line breaks preserved in display (white-space: pre-wrap)
- [x] Empty state handled gracefully
- [x] Tests implemented and passing
- [x] Responsive design maintained

---

## 📚 References

- **Issue**: #448 - WG: Erweiterung
- **Branch**: `copilot/add-notes-field-to-lease-contracts`
- **Files Modified**: 6 (models, forms, migration, 2 templates, tests)
- **Icon Source**: Bootstrap Icons (https://icons.getbootstrap.com/)
- **CSS Framework**: Bootstrap 5.3

---

*Last Updated: February 17, 2026*
