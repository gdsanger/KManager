# Activity Email Notifications - CC Implementation Summary

## Overview
This implementation adds CC (carbon copy) functionality to all activity email notifications as specified in issue #198.

## Acceptance Criteria Met ✅

### 1. Assignment/Information Email to Responsible Person
- **To:** Verantwortlicher (assigned_user)
- **CC:** Ersteller (creator)
- ✅ CC contains creator when creator != assigned user
- ✅ No CC when creator == assigned user (deduplication)
- ✅ No CC when creator has no email address

### 2. Completion Notification to Creator
- **To:** Ersteller (creator)
- **CC:** Verantwortlicher (assigned_user)
- ✅ CC contains assigned user when assigned_user != creator
- ✅ No CC when assigned_user == creator (deduplication)
- ✅ No CC when assigned user has no email address

### 3. Reminder Before Due Date
- **To:** Verantwortlicher (assigned_user) - existing logic maintained
- **CC:** Ersteller (creator)
- ✅ CC contains creator when creator != assigned user
- ✅ No CC when creator == assigned user (deduplication)
- ✅ No CC when creator has no email address

### 4. No Duplicate Recipients
- ✅ Automatic filtering prevents same address appearing in both To and CC
- ✅ Empty strings and None values filtered from CC list

### 5. Email Still Sent When CC Missing
- ✅ Mail sent to primary recipient even if CC recipient has no email
- ✅ Mail sent to primary recipient even if CC role is missing

## Technical Implementation

### 1. Core Mail Service Enhancement (`core/mailing/service.py`)
```python
def send_mail(template_key, to, context, cc=None):
```

**Changes:**
- Added optional `cc` parameter to accept list of CC recipients
- Implemented deduplication logic to filter out recipients already in To list
- Filters empty strings and None values from CC list
- Combines static CC (from template) with dynamic CC
- Maintains backward compatibility (cc parameter is optional)

**Key Logic:**
```python
# Filter out empty strings and None values
cc_list = [addr for addr in cc if addr]

# Remove duplicates with To recipients
cc_list = [addr for addr in cc_list if addr not in to]
```

### 2. Activity Assignment Signal (`vermietung/signals.py`)
**Location:** `send_activity_notifications` function, Case 1 & 2

**Changes:**
```python
# Prepare CC list (creator, if different from assignee)
cc_list = []
if instance.ersteller and instance.ersteller.email and instance.ersteller != instance.assigned_user:
    cc_list.append(instance.ersteller.email)

# Send email with CC
send_mail(
    template_key='activity-assigned',
    to=[instance.assigned_user.email],
    context=email_context,
    cc=cc_list
)
```

### 3. Activity Completion Signal (`vermietung/signals.py`)
**Location:** `send_activity_notifications` function, Case 3

**Changes:**
```python
# Prepare CC list (assigned user, if different from creator)
cc_list = []
if instance.assigned_user and instance.assigned_user.email and instance.assigned_user != instance.ersteller:
    cc_list.append(instance.assigned_user.email)

# Send email with CC
send_mail(
    template_key='activity-completed',
    to=[instance.ersteller.email],
    context=email_context,
    cc=cc_list
)
```

### 4. Activity Reminder Command (`vermietung/management/commands/send_activity_reminders.py`)
**Location:** `handle` method, email sending loop

**Changes:**
```python
# Prepare CC list (creator, if different from assignee)
cc_list = []
if activity.ersteller and activity.ersteller.email and activity.ersteller != activity.assigned_user:
    cc_list.append(activity.ersteller.email)

# Send email with CC
send_mail(
    template_key='activity-reminder',
    to=[activity.assigned_user.email],
    context=email_context,
    cc=cc_list
)
```

## Test Coverage

### New Tests Added
**Total:** 17 comprehensive test cases

#### Mail Service CC Tests (6 tests)
- `test_send_mail_with_dynamic_cc` - Verifies CC recipients are included
- `test_send_mail_with_empty_cc_list` - Handles empty CC list
- `test_send_mail_with_none_cc` - Handles None CC value
- `test_send_mail_removes_duplicate_cc` - Verifies deduplication
- `test_send_mail_with_static_and_dynamic_cc` - Both static and dynamic CC work together
- `test_send_mail_filters_empty_cc_addresses` - Filters empty/None from CC list

#### Activity Email CC Tests (7 tests)
- `test_assignment_email_includes_creator_in_cc` - Assignment with creator in CC
- `test_assignment_email_no_cc_when_creator_is_assignee` - No CC when same user
- `test_assignment_email_no_cc_when_creator_has_no_email` - No CC when no email
- `test_completed_email_includes_assignee_in_cc` - Completion with assignee in CC
- `test_completed_email_no_cc_when_assignee_is_creator` - No CC when same user
- `test_completed_email_no_cc_when_no_assignee` - No CC when no assignee
- `test_completed_email_no_cc_when_assignee_has_no_email` - No CC when no email

#### Activity Reminder CC Tests (4 tests)
- `test_reminder_email_includes_creator_in_cc` - Reminder with creator in CC
- `test_reminder_email_no_cc_when_creator_is_assignee` - No CC when same user
- `test_reminder_email_no_cc_when_creator_has_no_email` - No CC when no email
- `test_reminder_email_no_cc_when_no_creator` - No CC when no creator (edge case)

### Test Results
```
Ran 65 tests in 11.848s
OK
```

All existing tests continue to pass, demonstrating backward compatibility.

## Security Analysis

### CodeQL Scan Results
```
Analysis Result for 'python'. Found 0 alerts:
- python: No alerts found.
```

No security vulnerabilities introduced by this implementation.

## Edge Cases Handled

1. **Same User as Creator and Assignee**
   - CC is empty (not duplicated in To and CC)
   - Example: User creates task and assigns it to themselves

2. **Missing Email Address**
   - CC is empty if creator/assignee has no email
   - Primary recipient still receives email

3. **Missing Creator/Assignee**
   - CC is empty if role is not set (e.g., no creator)
   - Primary recipient still receives email

4. **Empty String Email**
   - Filtered out from CC list
   - Does not cause errors

5. **None Values in CC List**
   - Filtered out from CC list
   - Does not cause errors

## Backward Compatibility

- ✅ `cc` parameter in `send_mail()` is optional
- ✅ Existing code calling `send_mail()` without CC continues to work
- ✅ Static CC from templates still works
- ✅ All 48 existing tests continue to pass

## Files Modified

1. `core/mailing/service.py` - Extended send_mail function
2. `vermietung/signals.py` - Added CC to assignment and completion emails
3. `vermietung/management/commands/send_activity_reminders.py` - Added CC to reminder emails
4. `core/test_mail_service.py` - Added 6 CC tests
5. `vermietung/test_aktivitaet_mail_notifications.py` - Added 7 CC tests
6. `vermietung/test_activity_reminder.py` - Added 4 CC tests

## References

- Issue: #198 - Änderung an Domus Aktivitäten und Benachrichtigungen
- Related PRs:
  - #120 - Aktivitäten: MailTemplates + Sendelogik Zuweisung & Erledigt
  - #124 - Aktivitäten: MailTemplates + Sendelogik Zuweisung & Erledigt
- Related Issues:
  - #51 - Core-Mail: SMTP + Templates + Rendering

## Migration Notes

No database migrations required. This is a pure code change affecting:
- Mail service logic
- Signal handlers
- Management command logic

## Usage Examples

### Example 1: Assignment Email
```
To: assignee@example.com
CC: creator@example.com
Subject: Neue Aktivität zugewiesen: Fix bug in system
```

### Example 2: Completion Email
```
To: creator@example.com
CC: assignee@example.com
Subject: Aktivität erledigt: Fix bug in system
```

### Example 3: Reminder Email
```
To: assignee@example.com
CC: creator@example.com
Subject: Erinnerung: Fix bug in system fällig in 2 Tagen
```

### Example 4: Self-Assignment (No CC)
```
To: user@example.com
CC: (none)
Subject: Neue Aktivität zugewiesen: Personal task
```

## Conclusion

This implementation successfully adds CC functionality to all activity email notifications while:
- Meeting all acceptance criteria
- Maintaining backward compatibility
- Handling all edge cases gracefully
- Passing all tests (65/65)
- Introducing no security vulnerabilities
- Following existing code patterns and conventions
