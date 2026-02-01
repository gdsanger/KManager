# CC/Reviewer Feature - UI Guide

## Overview
This document describes the user interface changes for the CC/Reviewer feature in activities.

## 1. Activity Creation/Edit Form

### Location
The CC users field is located in the "Zuständigkeit" (Assignment) section of the activity form, between the "Lieferant" (Supplier) field and the "Serien-Aktivität" (Series) section.

### Field Appearance
```
┌─────────────────────────────────────────────────────────┐
│ Zuständigkeit                                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Ersteller                 Interner Verantwortlicher    │
│ [Current User ▼]          [Select User      ▼]        │
│                                                         │
│ Lieferant                                              │
│ [Select Supplier                            ▼]        │
│                                                         │
│ Zur Kontrolle informieren                              │
│ ┌───────────────────────────────────────────────────┐ │
│ │ user1                                             │ │
│ │ user2                                             │ │
│ │ user3                                             │ │
│ │ admin                                             │ │
│ │ testuser                                          │ │
│ └───────────────────────────────────────────────────┘ │
│ ℹ️ Optional: Weitere Benutzer zur Information/       │
│    Kontrolle (erhalten Benachrichtigungen bei         │
│    Erstellung, Änderung der CC-Liste und Abschluss)   │
└─────────────────────────────────────────────────────────┘
```

### Field Details
- **Label**: "Zur Kontrolle informieren"
- **Widget**: Multi-select listbox (size: 5 rows)
- **Help Text**: "Optional: Weitere Benutzer zur Information/Kontrolle (erhalten Benachrichtigungen bei Erstellung, Änderung der CC-Liste und Abschluss)"
- **Selection**: Hold Ctrl/Cmd to select multiple users
- **Styling**: Bootstrap form-select class

## 2. Kanban View

### Card Display
Each Kanban card now shows CC users if present:

```
┌────────────────────────────────────────┐
│ Fix critical bug in login              │
│                                        │
│ 🔴 Hoch  🏢  📋 Finanzen              │
│                                        │
│ 📅 31.01.2026                         │
│ 👤 john.doe                           │
│ 👁️ reviewer1, reviewer2              │
└────────────────────────────────────────┘
```

### Icon Legend
- 🔴 = High Priority
- 🏢 = MietObjekt context
- 📋 = Category/Bereich
- 📅 = Due date
- 👤 = Assigned user
- 👁️ = CC users (Zur Kontrolle informieren)

### Implementation Details
- CC users appear after assigned user and supplier
- Multiple CC users are comma-separated
- Shows username for each CC user
- Icon: Bootstrap icon `bi-eye`
- Title attribute provides tooltip: "Zur Kontrolle informieren"

## 3. List View

### Table Display
The list view shows CC users in the assignment column:

```
┌──────────────┬──────────┬───────────────────────────────┬────────┐
│ Titel        │ Status   │ Zuständigkeit                 │ Datum  │
├──────────────┼──────────┼───────────────────────────────┼────────┤
│ Fix login    │ OFFEN    │ 👤 john.doe                   │ 31.01  │
│              │          │ 👁️ reviewer1, reviewer2       │        │
├──────────────┼──────────┼───────────────────────────────┼────────┤
│ Update docs  │ ERLEDIGT │ 👤 jane.smith                 │ 28.01  │
│              │          │ 🚚 External Supplier Ltd.     │        │
│              │          │ 👁️ admin, manager             │        │
└──────────────┴──────────┴───────────────────────────────┴────────┘
```

### Icon Legend
- 👤 = Internal assigned user
- 🚚 = External supplier
- 👁️ = CC users

## 4. Email Notifications

### Email 1: Activity Creation (to CC users)
```
Von: K-Manager <noreply@kmanager.local>
An: reviewer1@company.com, reviewer2@company.com
Betreff: Neue Aktivität zugewiesen: Fix critical bug

Hallo,

Sie wurden zur Information über folgende Aktivität benachrichtigt:

Titel: Fix critical bug in login
Beschreibung: The login page shows error 500 on certain conditions
Priorität: Hoch
Fällig am: 31.01.2026
Kontext: Mietobjekt: Büro 1

Verantwortlich: john.doe
Erstellt von: jane.smith (jane.smith@company.com)

[Zur Aktivität →]
```

### Email 2: CC User Added (to newly added user only)
```
Von: K-Manager <noreply@kmanager.local>
An: reviewer3@company.com
Betreff: Neue Aktivität zugewiesen: Fix critical bug

Hallo,

Sie wurden zur Information über folgende Aktivität hinzugefügt:

[Same content as creation email]
```

### Email 3: Activity Completed (to all stakeholders)
```
Von: K-Manager <noreply@kmanager.local>
An: jane.smith@company.com, john.doe@company.com, 
    reviewer1@company.com, reviewer2@company.com, reviewer3@company.com
Betreff: Aktivität erledigt: Fix critical bug

Hallo,

Die Aktivität wurde erledigt:

Titel: Fix critical bug in login
Kontext: Mietobjekt: Büro 1
Erledigt von: john.doe
Erledigt am: 01.02.2026 15:30

[Zur Aktivität →]
```

## 5. User Experience Flow

### Creating an Activity with CC Users
1. Click "Neue Aktivität" button
2. Fill in activity details (Title, Description, etc.)
3. Select responsible user in "Interner Verantwortlicher"
4. Scroll to "Zur Kontrolle informieren" field
5. Hold Ctrl/Cmd and click multiple users to select
6. Click "Speichern"
7. System sends notification to assigned user
8. System sends notification to CC users (if they're not the assigned user)

### Adding CC Users to Existing Activity
1. Open activity in edit mode
2. Scroll to "Zur Kontrolle informieren" field
3. Hold Ctrl/Cmd and select additional users
4. Click "Speichern"
5. System sends notification ONLY to newly added CC users

### Completing an Activity
1. Mark activity as "ERLEDIGT"
2. System sends notification to:
   - Creator
   - Assigned user
   - All CC users
   - (Deduplicated - each person receives only one email)

## 6. Accessibility

### Keyboard Navigation
- Tab to CC users field
- Use arrow keys to navigate users
- Hold Ctrl/Cmd + Arrow keys to select multiple
- Space to toggle selection

### Screen Readers
- Field labeled as "Zur Kontrolle informieren"
- Help text announced: "Optional: Weitere Benutzer..."
- Selected users announced as list

## 7. Responsive Design

### Desktop (≥992px)
- Full-width multi-select with 5 visible rows
- All CC users visible in cards/lists

### Tablet (768px-991px)
- Multi-select adapts to available width
- CC users may wrap in cards

### Mobile (<768px)
- Multi-select stacks vertically
- CC users shown in compact format with ellipsis if needed

## 8. Edge Cases Handled

### No CC Users
- Field is empty (valid)
- No CC section shown in Kanban/List views
- No CC users receive notifications

### CC User is Also Assigned User
- User appears in CC list
- User receives assignment notification
- User does NOT receive duplicate CC notification
- User receives completion notification (once)

### CC User is Also Creator
- User appears in CC list
- User does NOT receive CC notification
- User receives completion notification (once)

### CC User Without Email
- User can be selected
- User does NOT receive email notifications
- No error shown to user

## 9. Performance

### Form Load
- All users loaded in single query
- Optimized with `order_by('username')`

### Card/List Display
- CC users loaded with activity
- Consider `prefetch_related('cc_users')` for list views
- Minimal impact on page load time

## 10. Browser Compatibility

Tested and working on:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

The multi-select widget is a standard HTML element, fully cross-browser compatible.
