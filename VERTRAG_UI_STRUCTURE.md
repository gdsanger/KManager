# Vertrag UI Structure and Flow

## Page Hierarchy

```
Vermietung Dashboard
    └── Verträge (Contracts)
        ├── List View (/vermietung/vertraege/)
        │   ├── Search by contract number, customer, or rental object
        │   ├── Filter by status (Draft, Active, Ended, Cancelled)
        │   ├── Pagination (20 per page)
        │   └── Actions:
        │       ├── View Details (👁️)
        │       └── Edit (✏️)
        │
        ├── Create View (/vermietung/vertraege/neu/)
        │   ├── Select Rental Object (with availability warning)
        │   ├── Select Customer (KUNDE type only)
        │   ├── Set Contract Period (start required, end optional)
        │   ├── Set Financial Terms (rent, deposit - pre-filled)
        │   ├── Set Status (Draft, Active, Ended, Cancelled)
        │   └── Auto-generates Contract Number on save
        │
        ├── Detail View (/vermietung/vertraege/{id}/)
        │   ├── Contract Information
        │   │   ├── Contract Number (V-00001)
        │   │   ├── Status Badge
        │   │   └── Currently Active Indicator
        │   ├── Rental Object Details (linked)
        │   ├── Customer/Tenant Details (linked)
        │   ├── Contract Period
        │   ├── Financial Terms
        │   ├── Related Data Tabs:
        │   │   ├── Handover Protocols (paginated)
        │   │   └── Documents (paginated)
        │   └── Actions:
        │       ├── Edit (✏️)
        │       ├── End Contract (📅) [if active/draft]
        │       ├── Cancel Contract (⛔) [if active/draft]
        │       └── Back to List (⬅️)
        │
        ├── Edit View (/vermietung/vertraege/{id}/bearbeiten/)
        │   └── Same form as Create, pre-filled with existing data
        │
        ├── End View (/vermietung/vertraege/{id}/beenden/)
        │   ├── Shows current contract information
        │   ├── Date picker for end date
        │   ├── Validation (must be after start date)
        │   ├── Auto-sets status to "Beendet" if date is in past
        │   └── Updates rental object availability
        │
        └── Cancel Action (/vermietung/vertraege/{id}/stornieren/)
            ├── POST-only with JavaScript confirmation
            ├── Changes status to "Storniert"
            └── Updates rental object availability
```

## Data Flow

### Creating a Contract

```
User clicks "Neuer Vertrag"
    ↓
Form loads with:
    - Rental objects list (all available)
    - Customers list (KUNDE type only)
    - Empty fields
    ↓
User selects Rental Object
    ↓
JavaScript triggers:
    - Shows warning if object is not available
    - Pre-fills rent from object's mietpreis
    - Pre-fills deposit from object's kaution
    ↓
User fills:
    - Customer
    - Start date (required)
    - End date (optional)
    - Adjusts rent/deposit if needed
    - Sets status
    ↓
User clicks "Speichern"
    ↓
Server validates:
    - Required fields present
    - End date > start date (if provided)
    - No overlapping active contracts
    ↓
If valid:
    - Auto-generates contract number (V-00001)
    - Saves to database
    - Updates rental object availability
    - Redirects to detail view
    - Shows success message
```

### Ending a Contract

```
User on Detail View
    ↓
Clicks "Beenden" button
    ↓
End Contract page loads:
    - Shows current contract info
    - Date picker with today's date
    ↓
User selects end date
    ↓
User clicks "Vertrag beenden"
    ↓
Server validates:
    - End date > start date
    - Contract is not already cancelled
    ↓
If valid:
    - Sets ende field to selected date
    - If date ≤ today: status = 'ended'
    - Updates rental object availability
    - Redirects to detail view
    - Shows success message
```

### Cancelling a Contract

```
User on Detail View
    ↓
Clicks "Stornieren" button
    ↓
JavaScript shows confirmation dialog
    ↓
User confirms
    ↓
POST request to cancel endpoint
    ↓
Server validates:
    - Contract is not already cancelled
    - Contract is not already ended
    ↓
If valid:
    - status = 'cancelled'
    - Updates rental object availability
    - Redirects to detail view
    - Shows success message
```

## Status Flow

```
         ┌─────────┐
         │  DRAFT  │ ─┐
         └─────────┘  │
              │       │
              ↓       │
         ┌─────────┐  │
    ┌──→ │ ACTIVE  │  │
    │    └─────────┘  │
    │         │       │
    │         │       │
    │    End  │       │ Cancel
    │  Action │       │ Action
    │         ↓       │
    │    ┌────────┐  │
    │    │ ENDED  │ ←┘
    │    └────────┘
    │         
    │    ┌───────────┐
    └──→ │ CANCELLED │
         └───────────┘

Notes:
- DRAFT → ACTIVE: Manual status change
- ACTIVE → ENDED: Via "Beenden" action or auto when end date passes
- ACTIVE → CANCELLED: Via "Stornieren" action
- DRAFT → CANCELLED: Via "Stornieren" action
- ENDED: Cannot be changed
- CANCELLED: Cannot be changed
```

## Availability Management

```
When creating ACTIVE contract:
    - Check for overlapping active contracts
    - If none: Allow creation
    - Set mietobjekt.verfuegbar = False
    - If overlap: Show validation error

When ending contract:
    - If end date ≤ today:
        - status = 'ended'
    - Check if mietobjekt has other active contracts
    - If none: mietobjekt.verfuegbar = True

When cancelling contract:
    - status = 'cancelled'
    - Check if mietobjekt has other active contracts
    - If none: mietobjekt.verfuegbar = True

When editing contract:
    - Re-validate for overlaps
    - Update availability based on active status
```

## Permission Requirements

All views require:
- User must be authenticated
- User must be in "Vermietung" group
- Enforced by `@vermietung_required` decorator

## Navigation Structure

```
Top Navigation Bar
    ├── K-Manager v1.0 (Home)
    ├── Vermietung (Active)
    ├── Finanzen
    └── User Menu
        ├── Abmelden (username)
        └── Anmelden (if not logged in)

Sidebar Navigation
    ├── Dashboard
    ├── Mietobjekte
    ├── Verträge ← NEW (Active when on contracts pages)
    ├── Kunden
    ├── Übergaben
    └── Dokumente
```

## Templates Inheritance

```
vermietung_base.html (Base template)
    ├── layouts/list_layout.html
    │   └── vertraege/list.html
    │
    ├── layouts/form_layout.html
    │   ├── vertraege/form.html (create/edit)
    │   └── vertraege/end.html
    │
    └── layouts/detail_layout.html
        └── vertraege/detail.html
```

## Forms

### VertragForm
- Used for: Create and Edit
- Fields: mietobjekt, mieter, start, ende, miete, kaution, status
- Special features:
  - Filters mieter to KUNDE type
  - JavaScript for availability warning
  - Pre-fills miete and kaution from mietobjekt

### VertragEndForm
- Used for: End Contract
- Fields: ende (date)
- Validation: ende > vertrag.start

## URL Patterns

| URL Pattern | View Function | Name | HTTP Methods |
|------------|---------------|------|--------------|
| `/vermietung/vertraege/` | vertrag_list | vertrag_list | GET |
| `/vermietung/vertraege/neu/` | vertrag_create | vertrag_create | GET, POST |
| `/vermietung/vertraege/{id}/` | vertrag_detail | vertrag_detail | GET |
| `/vermietung/vertraege/{id}/bearbeiten/` | vertrag_edit | vertrag_edit | GET, POST |
| `/vermietung/vertraege/{id}/beenden/` | vertrag_end | vertrag_end | GET, POST |
| `/vermietung/vertraege/{id}/stornieren/` | vertrag_cancel | vertrag_cancel | POST |

## Key Design Decisions

1. **No Delete in User Area**: Only End and Cancel actions available
   - Prevents accidental data loss
   - Maintains audit trail
   - Delete only available to admins in Django admin

2. **Auto-generated Contract Numbers**: V-00001, V-00002, etc.
   - Sequential numbering
   - Database-level locking to prevent race conditions
   - Format ensures easy sorting and identification

3. **Availability Warning vs. Blocking**: 
   - Shows warning if object is not available
   - But doesn't prevent selection
   - Model validation prevents actual overlaps
   - Provides better UX for edge cases

4. **Separate End Action**:
   - End is a deliberate action with date selection
   - Cancel is immediate status change
   - Clear distinction in UI and backend

5. **Status Auto-management**:
   - Status set to "Beendet" when end date passes
   - Availability auto-updated on all contract changes
   - Reduces manual maintenance

## Bootstrap 5 Components Used

- Cards (for information sections)
- Forms (styled inputs, selects, dates)
- Tables (responsive tables for lists)
- Badges (for status indicators)
- Buttons (Primary, Warning, Danger, Secondary)
- Alerts (for messages and warnings)
- Tabs (for related data sections)
- Pagination (for list views)
- Modals (JavaScript confirmation dialogs)
- Icons (Bootstrap Icons for visual elements)

## JavaScript Features

1. **Availability Warning**:
   - Checks mietobjekt availability when selected
   - Shows/hides warning div
   - Pre-fills miete and kaution

2. **Cancel Confirmation**:
   - Shows browser confirm dialog
   - Submits hidden form if confirmed

3. **Tab Navigation**:
   - Bootstrap 5 tabs for related data
   - Preserves state in URL

All JavaScript is inline in templates (no external JS files needed).
