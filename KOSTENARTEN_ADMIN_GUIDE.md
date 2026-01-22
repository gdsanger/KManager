# Kostenarten Admin Interface - Visual Guide

## Admin List View

```
┌─────────────────────────────────────────────────────────────────────┐
│ Django Administration                            Theme: Auto ☾      │
├─────────────────────────────────────────────────────────────────────┤
│ Home › Core › Kostenarten                                           │
│                                                                      │
│ ┌─────────────────────────────────┐  [+ Add Kostenart]             │
│ │ Search: [________________] 🔍  │                                  │
│ └─────────────────────────────────┘                                 │
│                                                                      │
│ Filter                                                               │
│ ┌─────────────────┐                                                 │
│ │ By parent       │                                                 │
│ │ • All           │                                                 │
│ │ • Has parent    │                                                 │
│ │ • No parent     │                                                 │
│ └─────────────────┘                                                 │
│                                                                      │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ ☐  Name         │ Parent │ Hauptkostenart                       │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ☐  Material     │   -    │        ✓                             │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ☐  Personal     │   -    │        ✓                             │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ☐  Verwaltung   │   -    │        ✓                             │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ 3 Kostenarten                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Note:** Only Hauptkostenarten (main cost types) are shown in the list view.
Unterkostenarten are managed through the inline editor when editing a parent.

## Admin Detail/Edit View (for "Personal")

```
┌─────────────────────────────────────────────────────────────────────┐
│ Django Administration                            Theme: Auto ☾      │
├─────────────────────────────────────────────────────────────────────┤
│ Home › Core › Kostenarten › Personal                                │
│                                                                      │
│ Change Kostenart                                                     │
│                                                                      │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ Name:                                                         │   │
│ │ [Personal_______________________________________________]     │   │
│ │                                                               │   │
│ │ Hauptkostenart:                                              │   │
│ │ [---------] (leave empty for main cost type)                 │   │
│ └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│ Unterkostenarten                                                     │
│ ┌───────────────────────────────────────────────────────────────┐   │
│ │ Name                    │ Parent   │ DELETE                   │   │
│ ├───────────────────────────────────────────────────────────────┤   │
│ │ [Gehälter__________]    │ Personal │ ☐                        │   │
│ ├───────────────────────────────────────────────────────────────┤   │
│ │ [Sozialversicherung]    │ Personal │ ☐                        │   │
│ ├───────────────────────────────────────────────────────────────┤   │
│ │ [Weiterbildung_____]    │ Personal │ ☐                        │   │
│ ├───────────────────────────────────────────────────────────────┤   │
│ │ [_______________]       │ Personal │                          │   │
│ └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│                        [Save and add another]                        │
│                        [Save and continue editing]                   │
│                        [Save]                                        │
│                                                                      │
│ Note: Delete button is DISABLED if this Hauptkostenart has children │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Features Illustrated

### 1. Hierarchical Structure
- **Hauptkostenart (Main):** Shown in main list, can have children
- **Unterkostenart (Sub):** Edited inline within parent, must have parent

### 2. Deletion Protection
```
Scenario: Try to delete "Personal" with 3 children
Result: ❌ Delete option is NOT available (has_delete_permission returns False)

Scenario: Try to delete "Material" with no children
Result: ✅ Delete option IS available
```

### 3. Validation
```
Attempt: Create "Sub-Sub Type" with parent="Gehälter" (which has parent="Personal")
Result: ❌ ValidationError
Message: "Kostenarten können nur eine Hierarchieebene haben. 
          Eine Unterkostenart kann nicht einer anderen Unterkostenart 
          zugeordnet werden."
```

### 4. Search and Filter
- **Search:** Type any part of a Kostenart name
- **Filter by parent:** 
  - "All" - Shows all Hauptkostenarten
  - "No parent" - Same as default (only main types)
  - "Has parent" - Would show nothing (sub types not in main list)

### 5. Data Relationships
```
Database Structure:

┌──────────────────────────────────────────┐
│ Kostenart Table                          │
├──────────────────────────────────────────┤
│ id │ name                 │ parent_id    │
├──────────────────────────────────────────┤
│ 1  │ Personal             │ NULL         │ ← Hauptkostenart
│ 2  │ Material             │ NULL         │ ← Hauptkostenart
│ 3  │ Verwaltung           │ NULL         │ ← Hauptkostenart
│ 4  │ Gehälter             │ 1            │ ← Unterkostenart of Personal
│ 5  │ Sozialversicherung   │ 1            │ ← Unterkostenart of Personal
│ 6  │ Weiterbildung        │ 1            │ ← Unterkostenart of Personal
│ 7  │ Rohstoffe            │ 2            │ ← Unterkostenart of Material
│ 8  │ Verbrauchsmaterial   │ 2            │ ← Unterkostenart of Material
│ 9  │ Bürobedarf           │ 3            │ ← Unterkostenart of Verwaltung
│ 10 │ Software-Lizenzen    │ 3            │ ← Unterkostenart of Verwaltung
└──────────────────────────────────────────┘

Constraints:
- parent_id FOREIGN KEY REFERENCES Kostenart(id) ON DELETE PROTECT
- When parent_id IS NULL → Hauptkostenart
- When parent_id IS NOT NULL → Unterkostenart
```

## Usage Examples

### Adding a New Hauptkostenart
1. Click "Add Kostenart" button
2. Enter name (e.g., "Energie")
3. Leave "Hauptkostenart" field empty
4. Click "Save"

### Adding Unterkostenarten
1. Click on existing Hauptkostenart (e.g., "Personal")
2. Scroll to "Unterkostenarten" section
3. Fill in name in empty inline form
4. Click "Save and continue editing" to add more
5. Or click "Save" when done

### Deleting a Kostenart
- **With children:** Delete button/option will not appear
- **Without children:** Select checkbox, choose "Delete selected" action
- **Single item:** Click item, then "Delete" button on detail page

## Technical Implementation

### Model Features
- `on_delete=models.PROTECT` prevents accidental deletion
- `clean()` method enforces single-level hierarchy
- `is_hauptkostenart()` helper method for templates/admin
- Alphabetical ordering by name

### Admin Features
- Custom `get_queryset()` filters to main types only
- Custom `has_delete_permission()` prevents parent deletion
- TabularInline for efficient child editing
- Boolean icon display for is_hauptkostenart column
