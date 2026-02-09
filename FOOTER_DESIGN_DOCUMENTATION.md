# Invoice Footer Design - Implementation Documentation

## Overview
This document describes the new 4-column footer design implemented for the invoice.html print template.

## Visual Layout

The footer is divided into 4 equal columns arranged horizontally:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         COMPANY FOOTER                                    │
├──────────────┬──────────────┬──────────────┬──────────────────────────────┤
│   Column 1   │   Column 2   │   Column 3   │         Column 4             │
│              │              │              │                              │
│ 🏢 Anschrift │ 📞 Kontakt   │ ⚖ Rechtliches│    🏦 Bankverbindung         │
│              │              │              │                              │
│ Company Name │ ☎ Phone      │ Steuernr.    │    Bank Name                 │
│ Street       │ 📠 Fax       │ USt-IdNr.    │    IBAN                      │
│ ZIP City     │ ✉ Email      │ GF: ...      │    BIC                       │
│ Country      │ 🌐 Website   │ HRB ...      │    Account Holder (optional) │
│              │              │              │                              │
└──────────────┴──────────────┴──────────────┴──────────────────────────────┘
```

## Column Details

### Column 1: Name & Address (Anschrift)
- 🏢 Icon for visual appeal
- Company Name (bold)
- Street Address
- Postal Code + City
- Country (optional, only if present)

**Data Source**: `company.name`, `company.address_lines[]`

### Column 2: Contact Details (Kontakt)
- 📞 Section icon
- ☎ Phone number
- 📠 Fax number
- ✉ Email address
- 🌐 Website/Internet

**Data Source**: `company.phone`, `company.fax`, `company.email`, `company.internet`

### Column 3: Legal Information (Rechtliches)
- ⚖ Section icon
- Tax Number (Steuernummer)
- VAT ID (USt-IdNr)
- Managing Director (Geschäftsführer) - abbreviated as "GF:"
- Commercial Register (Handelsregister)

**Data Source**: `company.tax_number`, `company.vat_id`, `company.managing_director`, `company.commercial_register`

### Column 4: Bank Details (Bankverbindung)
- 🏦 Section icon
- Bank Name
- IBAN
- BIC
- Account Holder (optional, only shown if different from company name)

**Data Source**: `company.bank_name`, `company.iban`, `company.bic`, `company.account_holder`

## Implementation Details

### CSS Classes
- `.company-footer`: Main footer container with top border separator
- `.footer-columns`: Table-based layout container (4 columns)
- `.footer-column`: Individual column (25% width each)
- `.footer-column-title`: Bold section headers with icons
- `.footer-item`: Individual data items within columns
- `.footer-icon`: Icons for visual decoration

### Key Features
1. **Print-Stable Layout**: Uses CSS `display: table` for reliable print rendering with WeasyPrint
2. **Conditional Rendering**: Empty fields are automatically hidden (no blank lines)
3. **Visual Separation**: 2pt solid border at the top separates footer from content
4. **Page Break Control**: `page-break-inside: avoid` ensures footer stays together
5. **Unicode Icons**: Simple, reliable icons that work across all platforms

### Font Sizes
- Section titles: 8pt (bold)
- Data items: 7pt
- Icons: Inline with text, 12pt width

## Example Data

### Complete Example (all fields filled):
```
┌──────────────────────────────────────────────────────────────────────────┐
│ 🏢 Anschrift          📞 Kontakt              ⚖ Rechtliches    🏦 Bankverbindung     │
│                                                                           │
│ KManager Demo GmbH    ☎ 030-12345678         Steuernr.:        Demo Bank            │
│ Musterstraße 123      📠 030-12345679        12/345/67890      IBAN: DE89...        │
│ 10115 Berlin          ✉ info@kmanager.de    USt-IdNr.:        BIC: COBADEFFXXX     │
│ Deutschland           🌐 www.kmanager.de     DE123456789        Inhaber: Demo GmbH   │
│                                              GF: Max Mustermann                      │
│                                              HRB 12345 B, AG Berlin                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Partial Example (some fields missing):
```
┌──────────────────────────────────────────────────────────────────────────┐
│ 🏢 Anschrift          📞 Kontakt              ⚖ Rechtliches    🏦 Bankverbindung     │
│                                                                           │
│ Test Company          ☎ 123-456              Steuernr.:        Test Bank            │
│ Test Street 1         ✉ test@example.com    12345              IBAN: DE1234...      │
│ 12345 Test City                                                                     │
│ Deutschland                                                                         │
└──────────────────────────────────────────────────────────────────────────┘
```
Note: Missing fields (Fax, Website, VAT ID, Managing Director, Commercial Register, BIC, Account Holder) don't create empty lines.

## Database Schema Changes

### New Field Added to Mandant Model
```python
handelsregister = models.CharField(
    max_length=200, 
    blank=True, 
    verbose_name="Handelsregister"
)
```

**Migration**: `core/migrations/0025_add_handelsregister_to_mandant.py`

## Files Modified

1. **core/models.py**: Added `handelsregister` field to `Mandant` model
2. **core/admin.py**: Added `handelsregister` to admin fieldsets
3. **core/migrations/0025_add_handelsregister_to_mandant.py**: Migration for new field
4. **auftragsverwaltung/printing/context.py**: Exposed all company fields in context
5. **auftragsverwaltung/templates/printing/orders/invoice.html**: Implemented new footer design

## Testing

Generated test invoices confirm:
- ✅ All 4 columns display correctly
- ✅ Icons render properly in PDF
- ✅ Empty fields are hidden automatically
- ✅ Layout remains stable in print (WeasyPrint)
- ✅ Data from all fields displays correctly
- ✅ Footer separates visually from content
- ✅ No page breaks within footer

## Acceptance Criteria Status

- ✅ Footer consists of 4 columns with defined information groups
- ✅ All required information is manageable in Mandant admin and displayed in print
- ✅ Missing values don't create visible empty lines/placeholders
- ✅ Change is effective for invoice.html as specified in requirements
