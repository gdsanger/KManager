# Implementation Summary: Eingangsrechnungen (Incoming Invoices)

## Overview
This implementation adds comprehensive incoming invoice management for rental properties to the KManager system. The feature allows users to track supplier invoices, allocate costs by type, calculate VAT automatically, and manage payment status.

## Implemented Features

### 1. Core Data Models

#### Kostenart Enhancement
- Added `umsatzsteuer_satz` field (0%, 7%, 19%) to support automatic VAT calculation
- Maintains existing hierarchical structure (Hauptkostenart → Unterkostenart)

#### Eingangsrechnung (Main Invoice Model)
**Key Fields:**
- Supplier (Lieferant) - FK to Adresse
- Rental Property (Mietobjekt) - FK to MietObjekt
- Document details: belegnummer, belegdatum, fälligkeit, betreff, referenznummer
- Service period (optional): leistungszeitraum_von, leistungszeitraum_bis
- Status: NEU → PRÜFUNG → OFFEN → KLÄRUNG → BEZAHLT
- Payment tracking: zahlungsdatum
- Allocation flag: umlagefaehig (for area-based cost distribution)
- Audit fields: erstellt_am, geaendert_am

**Calculated Properties:**
- `nettobetrag` - Sum of all allocation net amounts
- `umsatzsteuer` - Sum of all allocation VAT amounts
- `bruttobetrag` - Net + VAT

**Validations:**
- Service period: von ≤ bis
- Status BEZAHLT requires zahlungsdatum

**Methods:**
- `mark_as_paid(payment_date)` - Mark invoice as paid

#### EingangsrechnungAufteilung (Cost Allocation)
**Key Fields:**
- Invoice reference (FK to Eingangsrechnung)
- Cost type 1 (Hauptkostenart) - required
- Cost type 2 (Unterkostenart) - optional
- Net amount
- Description (optional)

**Calculated Properties:**
- `umsatzsteuer_satz` - VAT rate from cost type (prefers kostenart2)
- `umsatzsteuer` - Calculated VAT amount (net * rate)
- `bruttobetrag` - Net + VAT

**Validations:**
- Net amount ≥ 0
- Kostenart2 must be child of Kostenart1

### 2. User Interface

#### List View (/eingangsrechnungen/)
- Displays all invoices in paginated table
- Search by: belegnummer, betreff, lieferant, referenznummer
- Filters: status, mietobjekt
- Shows: belegdatum, belegnummer, lieferant, betreff, netto, brutto, status, fälligkeit, umlagefähig
- Actions: view, edit, delete

#### Detail View (/eingangsrechnungen/<pk>/)
- Complete invoice information
- Cost allocation breakdown table with VAT calculations
- Status badge with color coding
- Summary panel with totals
- Links to related lieferant and mietobjekt
- Action buttons: mark as paid, edit, delete

#### Create/Edit Forms
- Inline cost allocation formset
- Dynamic add/remove allocation rows
- Bootstrap 5 form styling
- Field validation with error messages
- Auto-calculation of totals

#### Mark as Paid
- Simple form to enter payment date (defaults to today)
- Updates status to BEZAHLT
- Sets zahlungsdatum

#### Mietobjekt Integration
- New "Eingangsrechnungen" tab on Mietobjekt detail page
- Shows all invoices for the property
- Paginated table with key information
- Quick access to create new invoice

### 3. Admin Interface
- Full CRUD support via Django admin
- Inline cost allocations
- Search fields: belegnummer, betreff, referenznummer, lieferant, mietobjekt
- List filters: status, umlagefaehig, mietobjekt, lieferant
- Date hierarchy by belegdatum
- Organized fieldsets

### 4. Testing
**14 comprehensive tests covering:**
- Model creation and validation
- VAT calculations (0%, 7%, 19%)
- Total amount calculations
- Service period validation
- Payment date validation
- Cost type hierarchy validation
- Mark as paid functionality
- Negative amount rejection
- Kostenart2 parent validation

**Test Results:** ✅ All 14 tests passing

### 5. Security
- Code review completed with all issues addressed
- CodeQL security scan: ✅ 0 security issues found
- Proper validation on all user inputs
- Protected foreign key relationships
- Decimal precision for financial calculations

## Technical Details

### Database Schema
```
Kostenart (extended)
├── umsatzsteuer_satz (CharField: '0', '7', '19')

Eingangsrechnung
├── lieferant (FK to Adresse)
├── mietobjekt (FK to MietObjekt)
├── belegdatum (DateField)
├── faelligkeit (DateField)
├── belegnummer (CharField)
├── betreff (CharField)
├── referenznummer (CharField, optional)
├── leistungszeitraum_von (DateField, optional)
├── leistungszeitraum_bis (DateField, optional)
├── notizen (TextField, optional)
├── status (CharField with choices)
├── zahlungsdatum (DateField, optional)
├── umlagefaehig (BooleanField)
├── erstellt_am (DateTimeField, auto)
└── geaendert_am (DateTimeField, auto)

EingangsrechnungAufteilung
├── eingangsrechnung (FK to Eingangsrechnung, CASCADE)
├── kostenart1 (FK to Kostenart, PROTECT)
├── kostenart2 (FK to Kostenart, PROTECT, optional)
├── nettobetrag (DecimalField)
└── beschreibung (CharField, optional)
```

### URL Structure
```
/vermietung/eingangsrechnungen/                    - List
/vermietung/eingangsrechnungen/neu/                - Create
/vermietung/eingangsrechnungen/<pk>/               - Detail
/vermietung/eingangsrechnungen/<pk>/bearbeiten/    - Edit
/vermietung/eingangsrechnungen/<pk>/loeschen/      - Delete
/vermietung/eingangsrechnungen/<pk>/bezahlt/       - Mark as paid
```

### Files Changed
```
Core Models:
- core/models.py (added VAT field to Kostenart)
- core/migrations/0005_add_vat_to_kostenart.py

Vermietung App:
- vermietung/models.py (added Eingangsrechnung models)
- vermietung/forms.py (added forms and formsets)
- vermietung/views.py (added 6 views)
- vermietung/admin.py (added admin classes)
- vermietung/urls.py (added URL patterns)
- vermietung/migrations/0020_add_eingangsrechnung_models.py
- vermietung/test_eingangsrechnung_model.py (14 tests)

Templates:
- templates/vermietung/eingangsrechnungen/list.html
- templates/vermietung/eingangsrechnungen/detail.html
- templates/vermietung/eingangsrechnungen/form.html
- templates/vermietung/eingangsrechnungen/mark_paid.html
- templates/vermietung/mietobjekte/detail.html (updated)
```

## Business Logic

### Cost Allocation
1. **Standard Case**: One allocation per invoice
2. **Split Case**: Multiple allocations for different cost types
3. VAT automatically calculated from cost type
4. Totals calculated from allocations (not stored)

### Status Workflow
```
NEU (New)
  ↓
PRÜFUNG (Review)
  ↓
OFFEN (Open)
  ↓
KLAERUNG (Clarification) OR → BEZAHLT (Paid)
```

### Validation Rules
1. Service period: leistungszeitraum_bis ≥ leistungszeitraum_von
2. Status BEZAHLT requires zahlungsdatum
3. Net amount ≥ 0
4. Kostenart2 must be child of Kostenart1

## Out of Scope (Future Enhancements)
- Document/receipt upload and OCR
- AI-based data extraction
- Payment transaction integration
- Automatic cost allocation to tenants
- Custom allocation keys (currently area-based only)

## Migration Path
1. Apply migrations: `python manage.py migrate`
2. Create cost types (Kostenarten) with VAT rates via admin
3. Start creating invoices with cost allocations
4. Use mark as paid feature to track payments

## Compatibility
- Django 5.2+
- PostgreSQL/SQLite
- Bootstrap 5
- Existing KManager codebase patterns

## Performance Considerations
- Lazy loading of related allocations
- Pagination on all list views (20 items/page)
- Select_related for foreign keys
- Prefetch_related for reverse relations

## Summary
This implementation provides a complete, production-ready system for managing incoming invoices for rental properties. All requirements from the original issue have been met, with comprehensive testing, security validation, and integration into the existing application structure.
