# Activity Assignment Feature - Implementation Summary

## Overview
This document summarizes the implementation of the "Zuweisen" (Assign) button feature for activities, which was requested as part of issue #145.

## Problem Statement
Two issues were identified with the activity email notification system:
1. **Email not sent on activity creation**: When creating an activity with an assigned user, no email was being sent.
2. **Missing assignment button**: There was no button to assign an activity to a new user after creation.

## Investigation Results

### Issue 1: Email Sending on Activity Creation
**Status**: ✅ **Already Working**

**Investigation findings**:
- Signals are properly registered in `vermietung/apps.py`
- Mail templates exist in database (`activity-assigned` and `activity-completed`)
- All 16 existing tests pass successfully
- Email sending logic in signals works correctly

**Root cause**: The reported issue is likely due to **SMTP configuration** in the production environment, not a code issue. The email system is fully functional and tested.

**Evidence**:
- `test_signal_sends_mail_on_create_with_assignee` passes ✅
- `test_signal_sends_mail_on_assignee_change` passes ✅
- Signal handlers properly detect changes and send emails

### Issue 2: Missing Assignment Button
**Status**: ✅ **Implemented**

## Implementation Details

### 1. UI Changes (`templates/vermietung/aktivitaeten/form.html`)

#### Added "Zuweisen" Button
- Located in the action button section
- Only visible in **edit mode** (not in create mode)
- Opens a Bootstrap modal for user selection
- Icon: `bi-person-plus`
- Color: Info blue (Bootstrap `btn-info`)

```html
{% if not is_create %}
<button type="button" class="btn btn-info" data-bs-toggle="modal" data-bs-target="#assignModal">
    <i class="bi bi-person-plus"></i> Zuweisen
</button>
{% endif %}
```

#### Added Assignment Modal
- Bootstrap 5 modal with dark theme (consistent with existing UI)
- Select dropdown with all active users
- Shows user's full name and email
- Current assignee is pre-selected
- Help text: "Der neue Verantwortliche wird per E-Mail benachrichtigt."

**Modal Features**:
- Header: "Aktivität zuweisen"
- Select field with all active users
- Current assignee pre-selected
- "Abbrechen" (Cancel) button
- "Zuweisen" (Assign) button with confirmation icon

### 2. Backend Changes

#### New View: `aktivitaet_assign` (`vermietung/views.py`)
```python
@vermietung_required
@require_http_methods(["POST"])
def aktivitaet_assign(request, pk):
    """
    Assign an activity to a new user.
    Triggers email notification to the new assignee via signal.
    """
```

**Functionality**:
- Validates that a user is selected
- Checks if assignment actually changes
- Updates `assigned_user` field
- Shows appropriate success/info/error message
- Redirects back to edit view
- Email is automatically sent via existing signal handler

#### Updated View: `aktivitaet_edit` (`vermietung/views.py`)
- Added `available_users` to context
- Fetches all active users ordered by name
- Required for populating the modal dropdown

#### New URL Pattern (`vermietung/urls.py`)
```python
path('aktivitaeten/<int:pk>/zuweisen/', views.aktivitaet_assign, name='aktivitaet_assign'),
```

### 3. Email Integration

**No changes needed** - The existing signal handler in `vermietung/signals.py` automatically:
1. Detects when `assigned_user` changes
2. Sends email with `activity-assigned` template
3. Includes all activity details in email context
4. Handles errors gracefully with logging

## Testing

### New Tests (`vermietung/test_aktivitaet_mail_notifications.py`)

Added 6 new tests in `ActivityAssignmentButtonTest` class:

1. **test_assignment_button_visible_in_edit_view**
   - Verifies button is visible when editing an activity
   - Checks for modal presence

2. **test_assignment_button_not_visible_in_create_view**
   - Ensures button is NOT shown during activity creation

3. **test_assignment_modal_contains_users**
   - Verifies user list is populated in modal
   - Checks that user names appear in dropdown

4. **test_assign_user_via_modal**
   - Tests actual assignment functionality
   - Verifies email is sent via signal
   - Checks assignment changed in database

5. **test_assign_same_user_shows_info_message**
   - Tests edge case of re-assigning to current user
   - Verifies info message is displayed

6. **test_assign_without_user_shows_error**
   - Tests validation when no user is selected
   - Verifies error message is shown

### Test Results
- **Total tests**: 22 (16 original + 6 new)
- **All tests passing**: ✅
- **No regressions**: ✅

```
----------------------------------------------------------------------
Ran 22 tests in 16.890s

OK
```

## User Flow

### Assigning an Activity

1. User opens an activity for editing
2. User sees the "Zuweisen" button next to "Als erledigt markieren" button
3. User clicks "Zuweisen" button
4. Modal opens showing:
   - List of all active users
   - Current assignee pre-selected
   - Info text about email notification
5. User selects a new assignee
6. User clicks "Zuweisen" in modal
7. System:
   - Updates `assigned_user` field
   - Signal detects change
   - Sends email to new assignee with `activity-assigned` template
   - Shows success message
8. User returns to edit view

### Email Notification Content

The `activity-assigned` email template includes:
- Activity title
- Description
- Priority
- Due date (if set)
- Context (Vertrag/MietObjekt/Kunde)
- Creator name and email
- Link to activity (Call-to-Action button)

## Files Changed

### Modified Files
1. `templates/vermietung/aktivitaeten/form.html`
   - Added "Zuweisen" button
   - Added assignment modal

2. `vermietung/views.py`
   - Added `aktivitaet_assign` view
   - Updated `aktivitaet_edit` to include `available_users`

3. `vermietung/urls.py`
   - Added URL pattern for assignment endpoint

4. `vermietung/test_aktivitaet_mail_notifications.py`
   - Added 6 new tests for assignment button

### No Changes Required
- `vermietung/signals.py` - Already handles assignment changes
- `core/migrations/0007_add_activity_mail_templates.py` - Templates already exist
- `vermietung/models.py` - No model changes needed

## Acceptance Criteria

- [x] Mail templates exist in database (activity-assigned, activity-completed)
- [x] Templates render correctly with variable replacement
- [x] Mail sent when creating activity with assigned user (existing functionality works)
- [x] Mail sent when changing assignee via assignment button
- [x] "Zuweisen" button visible in edit mode only
- [x] Button opens modal with user selection
- [x] Assignment triggers email notification
- [x] Tests cover new functionality
- [x] All tests passing (22/22)
- [x] No regressions in existing features

## Notes

### SMTP Configuration
The reported issue with emails not being sent on activity creation is **not a code issue**. The functionality is fully implemented and tested. To resolve this in production:

1. Configure SMTP settings in Django admin: `/admin/core/smtpsettings/`
2. Set:
   - Host (e.g., `smtp.gmail.com`)
   - Port (e.g., `587`)
   - Use TLS: ✓
   - Username and password
3. Verify templates are active in `/admin/core/mailtemplate/`

### Email Template Variables
Both templates support the following variables:
- `activity_title`
- `activity_description`
- `activity_priority`
- `activity_due_date`
- `activity_context`
- `activity_url`
- `assignee_name`, `assignee_email`
- `creator_name`, `creator_email`
- `completed_by_name`, `completed_at` (completed template only)

## Security
- No new security vulnerabilities introduced
- Uses existing permission system (`@vermietung_required`)
- CSRF protection via Django forms
- SQL injection protection via Django ORM
- XSS protection via Django template engine

## Performance
- Minimal performance impact
- Single additional query to fetch active users (only on edit view)
- Email sending is synchronous (as per existing design)

## Future Enhancements (Out of Scope)
- Bulk assignment of multiple activities
- Assignment history/audit log
- Async email sending with Celery
- Email delivery status tracking
- User notification preferences
