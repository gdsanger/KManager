# Visual Guide: Kanban Drag & Drop UI Changes

## Overview
This document describes the visual changes made to the Aktivitäten Kanban view.

## UI Changes

### 1. Information Banner (NEW)
**Location:** Top of the Kanban view, above the column layout

**Appearance:**
- Bootstrap "info" alert box (light blue background)
- Info circle icon on the left
- Bold "Tipp:" label
- Message text in regular weight

**HTML Structure:**
```html
<div class="alert alert-info mb-3" role="alert">
    <i class="bi bi-info-circle" aria-hidden="true"></i>
    <strong>Tipp:</strong> Aufgaben können per Drag & Drop in eine andere Spalte gezogen werden, um den Status zu ändern.
</div>
```

**Visual Description:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ℹ️  Tipp: Aufgaben können per Drag & Drop in eine andere Spalte │
│           gezogen werden, um den Status zu ändern.               │
└─────────────────────────────────────────────────────────────────┘
```

**Styling:**
- Background: Light blue (`alert-info`)
- Margin bottom: 1rem (`mb-3`)
- Border radius: Default Bootstrap alert radius
- Padding: Default Bootstrap alert padding
- Icon: Bootstrap Icons "bi-info-circle"
- Text color: Dark blue (Bootstrap info color)

### 2. Kanban Board Layout (UNCHANGED)
The existing Kanban board layout remains the same with four columns:

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│   Offen     │ In Bearb.   │  Erledigt   │ Abgebrochen │
│    (3)      │     (2)     │     (1)     │     (1)     │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │ ┌─────────┐ │
│ │Task 1   │ │ │Task 4   │ │ │Task 7   │ │ │Task 8   │ │
│ │ [High]  │ │ │[Normal] │ │ │[Normal] │ │ │ [Low]   │ │
│ └─────────┘ │ └─────────┘ │ │Updated  │ │ └─────────┘ │
│ ┌─────────┐ │ ┌─────────┐ │ │3d ago   │ │             │
│ │Task 2   │ │ │Task 5   │ │ └─────────┘ │             │
│ │[Normal] │ │ │[Normal] │ │             │             │
│ └─────────┘ │ └─────────┘ │             │             │
│ ┌─────────┐ │             │             │             │
│ │Task 3   │ │             │             │             │
│ │[Normal] │ │             │             │             │
│ └─────────┘ │             │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

### 3. Drag & Drop Interaction (EXISTING, ENHANCED)

#### Visual States:

**1. Normal State:**
- Cards have `cursor: pointer`
- Hover effect: Border changes to primary color with shadow

**2. Dragging State:**
- Card becomes semi-transparent (`opacity-50`)
- Original position remains visible
- Browser shows drag cursor

**3. Drop Zone Highlighting:**
- Column background changes to light primary color (`bg-primary bg-opacity-10`)
- Indicates valid drop target

**4. Error State:**
- Alert dialog appears with error message
- Page reloads to restore consistent state

### 4. "Erledigt" Column Filter (MODIFIED)

**Before:**
Shows last 20 completed activities (`:20` limit)

**After:**
Shows only activities updated in the last 7 days (no item limit, but naturally limited by time window)

**Visual Impact:**
- Older completed activities (>7 days) no longer appear
- Column may show fewer or zero items
- More relevant recent completions are highlighted

**Example Scenarios:**

Scenario A - Active Project:
```
┌─────────────┐
│  Erledigt   │
│    (5)      │
├─────────────┤
│ ✓ Task A    │  Updated: Today
│ ✓ Task B    │  Updated: 2d ago
│ ✓ Task C    │  Updated: 4d ago
│ ✓ Task D    │  Updated: 5d ago
│ ✓ Task E    │  Updated: 6d ago
└─────────────┘
```

Scenario B - Quiet Period:
```
┌─────────────┐
│  Erledigt   │
│    (0)      │
├─────────────┤
│   Keine     │
│ erledigten  │
│Aktivitäten  │
└─────────────┘
```

### 5. Permission-Based Interaction

**Authorized User (assigned_user or ersteller):**
1. Can drag cards
2. Status updates successfully
3. Page reloads showing new status

**Unauthorized User:**
1. Can still drag cards (client-side)
2. Drop triggers permission error
3. Alert shows: "Sie haben keine Berechtigung, den Status dieser Aktivität zu ändern."
4. Page reloads, card returns to original column

### 6. Activity Card Structure (UNCHANGED)

Cards maintain existing structure:
```
┌─────────────────────────────┐
│ Task Title                  │
│ ┌──┐ ┌──┐ ┌──┐             │
│ │❗│ │📄│ │🏷│              │  Priority, Context, Category badges
│ └──┘ └──┘ └──┘             │
│                             │
│ 📅 Due: 15.02.2026          │
│ 👤 Assigned: Username       │
│ 👁 CC: User1, User2         │
└─────────────────────────────┘
```

## Responsive Behavior

### Desktop (≥992px):
- All columns visible side-by-side
- Horizontal scrolling if many columns
- Info banner full width

### Tablet (768px - 991px):
- Columns may wrap
- Horizontal scroll enabled
- Info banner full width

### Mobile (<768px):
- Single column view with horizontal scroll
- Info banner full width
- Touch-friendly drag targets

## Color Scheme

### Alert Banner:
- Background: `var(--bs-info)` with opacity
- Border: Light blue
- Text: Dark blue
- Icon: Same as text color

### Column Headers:
- Offen: Blue badge (`badge-info`)
- In Bearbeitung: Yellow badge (`badge-warning`)
- Erledigt: Green badge (`badge-success`)
- Abgebrochen: Red badge (`badge-danger`)

### Drag States:
- Dragging: 50% opacity
- Drop zone: Primary color at 10% opacity

## Accessibility

### Screen Readers:
- Info icon has `aria-hidden="true"` (decorative)
- Alert has implicit `role="alert"`
- Meaningful text describes functionality
- Cards maintain existing accessibility structure

### Keyboard Navigation:
- Drag & Drop requires mouse/touch
- Alternative: Click card to open edit form
- All interactive elements remain keyboard accessible

## Browser Support

### Tested/Supported:
- Chrome/Edge (Chromium)
- Firefox
- Safari
- Modern mobile browsers

### Required Features:
- Drag and Drop API
- Fetch API
- ES6 JavaScript
- CSS Grid/Flexbox

## Performance

### Initial Load:
- Minimal JavaScript (~50 lines)
- No additional libraries
- Standard Bootstrap CSS

### Runtime:
- Efficient DOM queries (cached)
- Single AJAX request per drag
- Full page reload after update (ensures consistency)

## Error Scenarios

### Network Error:
```
Alert: "Fehler beim Aktualisieren des Status: Failed to fetch"
→ Page reloads
→ Original state restored
```

### Permission Error (403):
```
Alert: "Fehler: Sie haben keine Berechtigung, den Status dieser Aktivität zu ändern."
→ Page reloads
→ Original state restored
```

### Invalid Status (400):
```
Alert: "Fehler: Ungültiger Status"
→ Page reloads
→ Original state restored
```

### Server Error (500):
```
Alert: "Fehler: [Server error message]"
→ Page reloads
→ Original state restored
```

## Summary of Visual Changes

1. ✅ **NEW:** Blue info banner at top explaining drag & drop
2. ✅ **MODIFIED:** "Erledigt" column shows fewer (more relevant) items
3. ✅ **ENHANCED:** Better error feedback with clear messages
4. ✅ **UNCHANGED:** Overall layout, card design, and color scheme

## User Experience Flow

1. User views Kanban board
2. Reads info banner (first time)
3. Drags activity card to new column
4. Column highlights during drag
5. Drops card in new column
6. Permission check passes → Success
7. Page reloads showing updated status
8. ActivityStream logs the change

OR (if permission denied):

6. Permission check fails → 403 Error
7. Alert shows permission error
8. Page reloads, card back in original position
9. No state change persisted
