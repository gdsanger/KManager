# Visual Guide: Adressverwaltung Implementation

## Navigation Integration
```
Vermietung Sidebar Menu:
├── Dashboard
├── Mietobjekte
├── Verträge
├── Kunden
├── Standorte
├── ✨ Adressen (NEW) ✨
├── Übergaben
└── Dokumente
```

## URL Routes Added
```
/vermietung/adressen/                    → List all addresses
/vermietung/adressen/neu/               → Create new address
/vermietung/adressen/<id>/              → View address details
/vermietung/adressen/<id>/bearbeiten/   → Edit address
/vermietung/adressen/<id>/loeschen/     → Delete address (POST only)
```

## Page Flow Diagram
```
┌─────────────────┐
│  Adressen List  │  ← Search: name, firma, email, street, city, postal code
│   (20/page)     │  ← Pagination controls
└────────┬────────┘
         │
         ├─────────────┐
         │             │
    ┌────▼────┐   ┌────▼────────┐
    │ Create  │   │   Detail    │
    │  Form   │   │    View     │
    └────┬────┘   └────┬────────┘
         │             │
         │        ┌────┴────┐
         │        │         │
    ┌────▼────┐   │    ┌────▼────┐
    │ Success │   │    │  Edit   │
    │Redirect │   │    │  Form   │
    └─────────┘   │    └────┬────┘
                  │         │
             ┌────▼────┐    │
             │ Delete  │◄───┘
             │(POST)   │
             └─────────┘
```

## Data Model
```
Adresse (core.models.Adresse)
├── adressen_type: "Adresse" (FIXED, not user-editable)
├── firma: CharField (optional)
├── anrede: CharField (optional) - choices: HERR, FRAU, DIVERS
├── name: CharField (required)
├── strasse: CharField (required)
├── plz: CharField (required)
├── ort: CharField (required)
├── land: CharField (required)
├── telefon: CharField (optional)
├── mobil: CharField (optional)
├── email: EmailField (optional)
└── bemerkung: TextField (optional)
```

## Template Structure
```
templates/vermietung/adressen/
├── list.html
│   ├── Extends: vermietung/layouts/list_layout.html
│   ├── Search form
│   ├── Results table (name, firma, address, contact)
│   ├── Action buttons (view, edit, delete)
│   └── Pagination
│
├── detail.html
│   ├── Extends: vermietung/layouts/detail_layout.html
│   ├── Personal Data section (anrede, name, firma)
│   ├── Address section (street, postal code, city, country)
│   ├── Contact section (phone, mobile, email)
│   ├── Remarks section (if present)
│   ├── Documents section (upload/download/delete)
│   └── Action buttons (edit, delete, back)
│
└── form.html
    ├── Extends: vermietung/layouts/form_layout.html
    ├── Personal Data section
    ├── Address Data section
    ├── Contact Data section
    ├── Additional Information section
    └── Help sidebar with instructions
```

## Form Sections Layout
```
┌─────────────────────────────────┬───────────────────┐
│ Neue Adresse / Adresse bearbeiten│   [Abbrechen]   │
├─────────────────────────────────┴───────────────────┤
│                                                      │
│ ┌──────────────────────────────┐ ┌────────────────┐│
│ │ Personal Data                │ │  Help Sidebar  ││
│ │ • Anrede (dropdown)          │ │                ││
│ │ • Firma (optional)           │ │ • Pflichtfelder││
│ │ • Name (required)            │ │ • Adress-Typ   ││
│ ├──────────────────────────────┤ │ • Verwendung   ││
│ │ Address Data                 │ │                ││
│ │ • Straße (required)          │ └────────────────┘│
│ │ • PLZ (required)             │                    │
│ │ • Ort (required)             │                    │
│ │ • Land (required)            │                    │
│ ├──────────────────────────────┤                    │
│ │ Contact Data                 │                    │
│ │ • Telefon (optional)         │                    │
│ │ • Mobil (optional)           │                    │
│ │ • E-Mail (optional)          │                    │
│ ├──────────────────────────────┤                    │
│ │ Additional Information       │                    │
│ │ • Bemerkung (textarea)       │                    │
│ └──────────────────────────────┘                    │
│                                                      │
│ [Speichern]              [Abbrechen]                │
└──────────────────────────────────────────────────────┘
```

## Security & Permissions
```
All Views Protected:
├── @login_required (Django built-in)
├── @vermietung_required (custom decorator)
│   └── Checks user is in "Vermietung" group
│
Delete View Additional Protection:
└── @require_http_methods(["POST"])
    └── Prevents accidental deletion via GET
```

## Testing Coverage
```
test_adresse_crud.py (18 tests)
├── Authentication & Permissions (4 tests)
│   ├── list_requires_authentication
│   ├── list_requires_vermietung_access
│   ├── detail_requires_authentication
│   └── create_requires_authentication
│
├── List View (3 tests)
│   ├── shows_only_adressen
│   ├── search (name, city, email, no results)
│   └── pagination
│
├── Detail View (2 tests)
│   ├── shows_correct_data
│   └── only_shows_adresse_type (404 for KUNDE/STANDORT)
│
├── Create (3 tests)
│   ├── get (form displays)
│   ├── post_valid (creates address)
│   └── post_invalid (validation errors)
│
├── Edit (3 tests)
│   ├── requires_authentication
│   ├── get (form with existing data)
│   └── post_valid (updates address)
│
├── Delete (2 tests)
│   ├── requires_post
│   └── success
│
└── Form Behavior (1 test)
    └── sets_adressen_type_to_adresse
```

## Integration Points
```
Documents Integration:
├── Upload documents to addresses
├── View/Download documents
└── Delete documents

Routing Logic (vermietung/views.py):
├── dokument_upload view
│   └── Routes to correct detail page based on address type:
│       ├── KUNDE → kunde_detail
│       ├── STANDORT → standort_detail
│       └── Adresse → adresse_detail
│
└── dokument_delete view
    └── Same routing logic for redirects after deletion
```

## Key Features
```
✅ CRUD Operations (Create, Read, Update, Delete)
✅ Search across multiple fields
✅ Pagination (20 items per page)
✅ Document management integration
✅ Responsive Bootstrap 5 UI
✅ Form validation
✅ Success/Error messages
✅ Permission-based access control
✅ Type restriction (adressen_type = "Adresse")
✅ Comprehensive test coverage
```

## Comparison with Similar Features
```
Feature Consistency Table:
┌─────────────────┬────────┬──────────┬─────────┐
│                 │ Kunde  │ Standort │ Adresse │
├─────────────────┼────────┼──────────┼─────────┤
│ List View       │   ✓    │    ✓     │    ✓    │
│ Detail View     │   ✓    │    ✓     │    ✓    │
│ Create Form     │   ✓    │    ✓     │    ✓    │
│ Edit Form       │   ✓    │    ✓     │    ✓    │
│ Delete          │   ✓    │    ✓     │    ✓    │
│ Search          │   ✓    │    ✓     │    ✓    │
│ Pagination      │   ✓    │    ✓     │    ✓    │
│ Documents       │   ✓    │    -     │    ✓    │
│ Type Fixed      │   ✓    │    ✓     │    ✓    │
│ Tests           │   ✓    │    ✓     │    ✓    │
│ Menu Item       │   ✓    │    ✓     │    ✓    │
└─────────────────┴────────┴──────────┴─────────┘
```

## Implementation Statistics
```
Lines of Code Added:
├── forms.py: ~110 lines (AdresseForm class)
├── views.py: ~150 lines (5 view functions + routing updates)
├── urls.py: ~7 lines (5 URL patterns)
├── Templates: ~680 lines total
│   ├── list.html: ~180 lines
│   ├── detail.html: ~265 lines
│   └── form.html: ~170 lines
├── Navigation: ~5 lines
└── Tests: ~335 lines (18 test cases)

Total: ~1,287 lines of production code + tests
```
