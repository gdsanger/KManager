# Admin Interface Guide - Item Group Feature

## Overview
This guide shows how the item_group field appears in the Django Admin interface.

## Item List View (Changelist)

The Item list view now includes the `item_group` column:

```
+-------------+------------------+-----------+------------------+------------+-----+
| Artikelnr.  | Kurztext 1       | Artikeltyp| Warengruppe      | Preis(€)   | ... |
+-------------+------------------+-----------+------------------+------------+-----+
| ART-001     | Smartphone XY    | MATERIAL  | ELEC > PHONE     | 799.00     | ... |
| ART-002     | Consulting Hour  | SERVICE   | -                | 120.00     | ... |
| ART-003     | Laptop Pro       | MATERIAL  | ELEC > COMP      | 1,299.00   | ... |
+-------------+------------------+-----------+------------------+------------+-----+
```

**Note:** When an item has no item_group assigned, it displays as "-" or empty.

## Filters (Right Sidebar)

The admin interface now includes two new filters:

### 1. Filter by Item Group (Direct)
```
┌─────────────────────────────┐
│ Nach Warengruppe            │
├─────────────────────────────┤
│ ○ Alle                      │
│ ○ ELEC > PHONE              │
│ ○ ELEC > COMP               │
│ ○ FURN > DESK               │
│ ○ FURN > CHAIR              │
│ ○ (Leer)                    │
└─────────────────────────────┘
```

This filter shows all SUB item groups and allows filtering by specific group or items without a group.

### 2. Filter by Parent Group (Indirect)
```
┌─────────────────────────────┐
│ Nach Hauptwarengruppe       │
├─────────────────────────────┤
│ ○ Alle                      │
│ ○ ELEC (Elektronik)         │
│ ○ FURN (Möbel)              │
│ ○ (Leer)                    │
└─────────────────────────────┘
```

This filter shows MAIN item groups and filters items by their sub-group's parent.

## Item Edit/Create Form

When editing or creating an item, the form now includes a new section:

```
╔═══════════════════════════════════════════════════════════════╗
║ Artikel bearbeiten                                            ║
╚═══════════════════════════════════════════════════════════════╝

┌───────────────────────────────────────────────────────────────┐
│ Identifikation                                                │
├───────────────────────────────────────────────────────────────┤
│ Artikelnummer: [ART-001________________]                      │
│ Artikeltyp:    [MATERIAL ▼]                                  │
│ Aktiv:         [✓]                                           │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ Texte                                                         │
├───────────────────────────────────────────────────────────────┤
│ Kurztext 1:    [Smartphone XY__________]                      │
│ Kurztext 2:    [________________________]                     │
│ Langtext:      [________________________]                     │
│                [________________________]                     │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ Klassifizierung                                               │
│ Optional: Zuordnung zu einer Unterwarengruppe (SUB)           │
├───────────────────────────────────────────────────────────────┤
│ Warengruppe:   [ELEC > PHONE ▼]                              │
│                                                               │
│ Dropdown shows only SUB groups:                              │
│   - ELEC > PHONE (Smartphones)                               │
│   - ELEC > COMP (Computer)                                   │
│   - FURN > DESK (Schreibtische)                              │
│   - FURN > CHAIR (Stühle)                                    │
│   - (Leer) for no assignment                                 │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ Preise                                                        │
├───────────────────────────────────────────────────────────────┤
│ ...                                                           │
└───────────────────────────────────────────────────────────────┘
```

## Validation Behavior

### Valid Assignments

**1. No Item Group (NULL)**
- User leaves the field empty
- ✅ Form saves successfully
- Item is created/updated without classification

**2. SUB Item Group Selected**
- User selects "ELEC > PHONE"
- ✅ Form saves successfully
- Item is assigned to the sub-group
- Indirect relationship to MAIN group (ELEC) established

### Invalid Assignments

**MAIN Item Group Selected**

If a MAIN item group somehow gets selected (should not appear in dropdown, but could happen via API/shell):

```
╔═══════════════════════════════════════════════════════════════╗
║ ❌ Fehler beim Speichern                                      ║
╚═══════════════════════════════════════════════════════════════╝

┌───────────────────────────────────────────────────────────────┐
│ Warengruppe:                                                  │
│   ⚠ Ein Artikel kann nur einer Unterwarengruppe (SUB)        │
│     zugeordnet werden, nicht einer Hauptwarengruppe (MAIN).   │
│     Bitte wählen Sie eine Unterwarengruppe.                   │
└───────────────────────────────────────────────────────────────┘
```

The form will not save and display the validation error in German.

## Search Functionality

Items can still be searched by:
- Artikelnummer (article_no)
- Kurztext 1 (short_text_1)
- Kurztext 2 (short_text_2)
- Langtext (long_text)

**Note:** The item_group field is NOT in search_fields by design. Use filters instead.

## Use Cases

### Use Case 1: Assign Item to Category
1. Navigate to Items in Django Admin
2. Click on an item or create new item
3. Scroll to "Klassifizierung" section
4. Select a sub-group from dropdown (e.g., "ELEC > PHONE")
5. Save the item

### Use Case 2: Filter Items by Category
1. Navigate to Items list
2. Use "Nach Warengruppe" filter on right side
3. Select desired sub-group
4. View filtered list

### Use Case 3: Filter by Main Category
1. Navigate to Items list
2. Use "Nach Hauptwarengruppe" filter
3. Select desired main group (e.g., "ELEC")
4. View all items in any sub-group under that main group

### Use Case 4: Find Unclassified Items
1. Navigate to Items list
2. Use "Nach Warengruppe" filter
3. Select "(Leer)" option
4. View all items without classification

## Technical Notes

### Dropdown Population
The item_group dropdown will show:
- All active ItemGroups where `group_type='SUB'`
- Displayed as: `parent.code > code: name`
- Example: `ELEC > PHONE: Smartphones`

### Performance Considerations
- The filters use Django's standard queryset filtering
- Indexes exist on ItemGroup fields for efficient filtering
- Foreign key lookups are optimized by Django ORM

### Permissions
- Standard Django Item permissions apply
- No special permissions needed for item_group field
- Add/Change/Delete Item permissions control access

## Migration Impact

After deploying this feature:
1. All existing items will have `item_group = NULL`
2. No data loss or corruption
3. Users can gradually classify items
4. Filter by "(Leer)" to find unclassified items

## Related Models

### ItemGroup Display
In the ItemGroup admin, you can now see which items are assigned:
- Navigate to ItemGroups
- Open a SUB group
- Related items shown in reverse relation

Example:
```
Warengruppe: PHONE (Smartphones)
Parent: ELEC (Elektronik)

Zugeordnete Artikel (3):
- ART-001: Smartphone XY
- ART-025: Smartphone ABC
- ART-042: Smartphone DEF
```

This is possible through the `related_name='items'` on the ForeignKey.
