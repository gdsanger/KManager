# SalesDocument DetailView - Quick Start Guide

## Overview

The SalesDocument DetailView provides a premium, intuitive interface for creating and editing sales documents (quotes, invoices, orders, etc.).

## Features at a Glance

### 🎯 Premium UX
- **Beleg-Editor Feel**: Professional document editor, not just a form
- **Live Calculations**: Instant feedback on all changes
- **Keyboard Friendly**: Tab/Enter navigation works perfectly
- **Unsaved Changes Guard**: Never lose your work

### 💰 Smart Calculations
- **Automatic Totals**: Net, tax, and gross amounts calculated live
- **Payment Term Automation**: Due dates and text generated automatically
- **EU Tax Logic**: Correct tax rates based on customer location and status

### 📝 Line Management
- **Article Search**: Full-text search across all article fields
- **Snapshot Principle**: Prices and tax rates locked at creation time
- **Inline Editing**: Edit quantities and prices with instant feedback
- **Add/Remove**: Flexible line management

## UI Layout

```
┌──────────────────────────────────────────────────┬───────────────────┐
│ KOPFDATEN (Header Section)                       │   SUMMEN          │
│ ┌──────────────────────────────────────────────┐ │   (Sticky)        │
│ │ Company | Document Type | Number               │ │                   │
│ │ Subject (required, prominent input)           │ │ Netto: 1.000,00€  │
│ │ Customer | Issue Date | Status                │ │ Steuer:  190,00€  │
│ │ Payment Term | Due Date (auto)                │ │ ════════════════  │
│ │ Reference Number                               │ │ Brutto: 1.190,00€ │
│ └──────────────────────────────────────────────┘ │                   │
│                                                    │ ZAHLUNGSBEDINGUNG │
│ POSITIONEN (Lines Section)                        │ Zahlbar innerhalb │
│ ┌──────────────────────────────────────────────┐ │ 14 Tagen (bis     │
│ │ [+ Position hinzufügen]                      │ │ 15.09.2026) netto │
│ │                                                │ │                   │
│ │ ┌──────────────────────────────────────────┐ │ │                   │
│ │ │ [1] Beratungsleistung         [Delete]   │ │ │                   │
│ │ │     Qty: 10  Price: 100,00€              │ │ │                   │
│ │ │     Net: 1.000,00€  Tax: 190,00€         │ │ │                   │
│ │ └──────────────────────────────────────────┘ │ │                   │
│ └──────────────────────────────────────────────┘ │                   │
│                                                    │                   │
│ TEXTE (Text Sections - Tabs)                      │                   │
│ ┌──────────────────────────────────────────────┐ │                   │
│ │ [Kopftext] [Fußtext] [Notizen]               │ │                   │
│ │ ┌──────────────────────────────────────────┐ │ │                   │
│ │ │ Text area for header/footer/notes        │ │ │                   │
│ │ └──────────────────────────────────────────┘ │ │                   │
│ └──────────────────────────────────────────────┘ │                   │
└──────────────────────────────────────────────────┴───────────────────┘
```

## Workflow

### Creating a New Document

1. **Navigate to List**
   - Go to `/auftragsverwaltung/rechnungen/` (or angebote, auftraege, etc.)
   - Click "Neu erstellen"

2. **Fill Header**
   - **Subject**: Enter document title (required)
   - **Customer**: Select from dropdown
   - **Issue Date**: Defaults to today
   - **Payment Term**: Select to auto-calculate due date

3. **Add Lines**
   - Click "Position hinzufügen"
   - Search for article (type to search)
   - Click article to add
   - Adjust quantity/price as needed
   - Repeat for more lines

4. **Add Texts** (Optional)
   - Click "Kopftext" tab for header text
   - Click "Fußtext" tab for footer text
   - Click "Notizen" tab for internal/public notes

5. **Save**
   - Click "Erstellen" button
   - Document is saved with generated number
   - Redirects to detail view

### Editing an Existing Document

1. **Open Document**
   - Click document number in list
   - Or click "Details" button

2. **Edit Any Field**
   - All header fields are editable
   - Lines can be edited inline
   - Changes show "Nicht gespeichert" indicator

3. **Live Updates**
   - Quantity/price changes update totals instantly
   - Payment term changes update due date
   - No save needed for calculations

4. **Save Changes**
   - Click "Speichern" button
   - All changes persisted
   - Activity logged

## Key Behaviors

### Automatic Calculations

**Line Totals:**
```
Quantity × Unit Price = Line Net
Line Net × Tax Rate = Line Tax
Line Net + Line Tax = Line Gross
```

**Document Totals:**
```
Sum of all Line Net = Total Net
Sum of all Line Tax = Total Tax
Sum of all Line Gross = Total Gross
```

**Updates:**
- Instant (no save needed)
- Visible in right column
- Per-line and per-document

### Payment Term Automation

**When Changed:**
- Payment term selected
- Issue date changed

**Result:**
```
Due Date = Issue Date + Net Days
Payment Text = Generated in German

Example:
Issue Date: 01.09.2026
Payment Term: "14 Tage netto"
→ Due Date: 15.09.2026
→ Text: "Zahlbar innerhalb 14 Tagen (bis 15.09.2026) netto."

With Skonto:
Payment Term: "2% Skonto 10 Tage, netto 30 Tage"
→ Text: "Zahlbar innerhalb 10 Tagen (bis 11.09.2026) mit 2% Skonto,
         spätestens innerhalb 30 Tagen (bis 01.10.2026) netto."
```

### Tax Determination

**Automatic Selection:**
When adding a line, tax rate is determined by:

**German Customer (DE):**
```
Item Tax Rate: 19%
→ Line Tax Rate: 19%
(Standard DE VAT)
```

**EU Customer with VAT ID (B2B):**
```
Customer: France, VAT ID: FR123...
Item Tax Rate: 19%
→ Line Tax Rate: 0%
(Reverse Charge)
```

**EU Customer without VAT ID (B2C):**
```
Customer: France, no VAT ID
Item Tax Rate: 19%
→ Line Tax Rate: 19%
(DE VAT applies)
```

**Non-EU Customer:**
```
Customer: USA
Item Tax Rate: 19%
→ Line Tax Rate: 0%
(Export)
```

### Unsaved Changes Protection

**Triggers:**
- Any field change
- Navigation away from page
- Browser close/refresh

**Behavior:**
- Shows "Nicht gespeichert" indicator
- Browser warns on navigation
- Prevents accidental data loss

**Resolution:**
- Click "Speichern" to save
- Click "Abbrechen" to discard
- Stay on page to continue editing

## Article Search

### How to Search

1. Click "Position hinzufügen"
2. Modal opens with search box
3. Type at least 2 characters
4. Results appear instantly (debounced 300ms)

### What Gets Searched

- Article number (`article_no`)
- Short text 1 (`short_text_1`)
- Short text 2 (`short_text_2`)
- Long text (`long_text`)

### Search Examples

```
"ART-001" → Finds by article number
"Beratung" → Finds by description
"Software" → Finds by any text field
```

### Result Display

```
[ART-001] - Beratungsleistung
Preis: 100,00 € (VAT)
[Click to add]
```

### Adding Article

- Click on search result
- Modal closes
- Line is created with:
  - Description from article
  - Price from article  
  - Tax rate (auto-determined)
  - Quantity = 1 (editable)

## Keyboard Shortcuts

### Navigation
- **Tab**: Move to next field
- **Shift+Tab**: Move to previous field
- **Enter**: Submit form (on buttons)
- **Esc**: Close modal (in search)

### Editing
- **All standard text input shortcuts work**
- **Browser autocomplete available**
- **Copy/paste supported**

## Tips & Tricks

### Quick Document Creation
1. Use keyboard navigation (Tab/Enter)
2. Payment term auto-fills due date
3. Customer changes tax rates automatically
4. Article search is fast - just start typing

### Editing Multiple Lines
1. Edit quantities inline
2. Totals update live
3. No save needed for calculations
4. Only save when done

### Finding Articles
1. Search by number for exact match
2. Search by description for browsing
3. Results limited to 20 (scroll if needed)
4. Click anywhere on result to add

### Payment Terms
1. Set once per customer
2. Changes reflected in all documents
3. Text auto-generates
4. Due date auto-calculates

## Troubleshooting

### "Nicht gespeichert" Always Shows
- This is normal after editing
- Click "Speichern" to clear
- Indicates unsaved changes exist

### Totals Don't Update
- Check if changes are saved
- Refresh page to reload
- Check browser console for errors

### Article Search No Results
- Check spelling
- Try partial match
- Verify article is active
- Check minimum 2 characters entered

### Tax Rate Incorrect
- Verify customer country code
- Check customer VAT ID (for EU B2B)
- Review article default tax rate
- Tax is determined at line creation

## Next Steps

### Learn More
- Read full documentation: `SALESDOCUMENT_DETAILVIEW_IMPLEMENTATION.md`
- Review service APIs for integration
- Check test files for examples

### Customize
- Modify templates for your branding
- Extend services for custom logic
- Add fields to models as needed

### Report Issues
- Check existing GitHub issues
- Create new issue with details
- Include browser console errors

---

**Version:** 1.0  
**Last Updated:** 2026-02-06  
**Author:** GitHub Copilot Agent
