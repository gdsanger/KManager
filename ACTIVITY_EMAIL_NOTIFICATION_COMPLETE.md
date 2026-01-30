# Activity Email Notification System - Complete Documentation

## Overview
This document describes the complete email notification system for activities (Aktivitäten) in K-Manager. The system automatically sends HTML emails when activities are assigned or completed.

## Components

### 1. Mail Templates (Database)
Two mail templates are created via migration `core/migrations/0007_add_activity_mail_templates.py`:

#### Template 1: activity-assigned
- **Key**: `activity-assigned`
- **Subject**: `Neue Aktivität zugewiesen: {{ activity_title }}`
- **Trigger**: When an activity is created with an assignee OR when the assignee is changed
- **Recipient**: The assigned user (new assignee)
- **Variables**:
  - `assignee_name` - Full name or username of the assignee
  - `activity_title` - Title of the activity
  - `activity_description` - Description (optional)
  - `activity_priority` - Priority level (display value)
  - `activity_due_date` - Due date formatted as DD.MM.YYYY (optional)
  - `activity_context` - Context info (Vertrag/Mietobjekt/Kunde)
  - `activity_url` - Absolute URL to the activity edit page
  - `creator_name` - Full name of the creator
  - `creator_email` - Email of the creator

#### Template 2: activity-completed
- **Key**: `activity-completed`
- **Subject**: `Aktivität erledigt: {{ activity_title }}`
- **Trigger**: When activity status changes to ERLEDIGT
- **Recipient**: The creator of the activity
- **Variables**:
  - `creator_name` - Full name or username of the creator
  - `activity_title` - Title of the activity
  - `activity_context` - Context info (Vertrag/Mietobjekt/Kunde)
  - `activity_url` - Absolute URL to the activity edit page
  - `completed_by_name` - Name of person who completed it
  - `completed_at` - Timestamp formatted as DD.MM.YYYY HH:MM

### 2. Signal Handlers (`vermietung/signals.py`)
Email notifications are triggered automatically by Django signals:

#### Pre-save Signal
```python
@receiver(pre_save, sender=Aktivitaet)
def store_original_values(sender, instance, **kwargs):
```
Stores the original values of `assigned_user` and `status` before save to detect changes.

#### Post-save Signal
```python
@receiver(post_save, sender=Aktivitaet)
def send_activity_notifications(sender, instance, created, **kwargs):
```
Sends notifications based on detected transitions:

**Case 1: New Activity with Assignee**
- Condition: `created == True AND assigned_user != None`
- Action: Send `activity-assigned` email to assigned_user

**Case 2: Assignee Changed**
- Condition: `original_assigned_user != current_assigned_user AND current_assigned_user != None`
- Action: Send `activity-assigned` email to NEW assigned_user only

**Case 3: Activity Completed**
- Condition: `original_status != 'ERLEDIGT' AND current_status == 'ERLEDIGT'`
- Action: Send `activity-completed` email to creator (ersteller)

**Deduplication**: The signal only sends emails when actual transitions occur, preventing duplicate emails on saves without changes.

### 3. Mail Service (`core/mailing/service.py`)

#### Template Rendering
```python
def render_template(mail_template, context):
    """Renders subject and message with Django template engine"""
```
- Uses Django's Template and Context classes
- Supports `{{ variable }}` syntax
- Supports Django template tags like `{% if %}`, `{% for %}`
- Missing variables render as empty strings (Django default behavior)

#### Email Sending
```python
def send_mail(template_key, to, context):
    """
    Sends email using a template.
    
    Args:
        template_key: str - Unique key of MailTemplate (e.g., 'activity-assigned')
        to: list - List of recipient email addresses
        context: dict - Template variables
    """
```
- Loads template from database by key
- Checks if template is active
- Renders subject and HTML body
- Retrieves SMTP settings
- Sends via SMTP with proper encoding

### 4. UI Components

#### Assignment Button & Modal
Located in `templates/vermietung/aktivitaeten/form.html`:

**Button** (line 269):
```html
<button type="button" class="btn btn-info" data-bs-toggle="modal" data-bs-target="#assignModal">
    <i class="bi bi-person-plus"></i> Zuweisen
</button>
```
- Only visible in edit mode (not create)
- Opens Bootstrap modal for user selection

**Modal** (lines 304-344):
- Centered dialog with user dropdown
- Pre-selects current assignee if set
- Shows email notification hint
- Submits to `aktivitaet_assign` endpoint

#### Mark as Completed Button
**Button** (line 274):
```html
<button type="button" class="btn btn-success" onclick="markAsCompleted()">
    <i class="bi bi-check-circle-fill"></i> Als erledigt markieren
</button>
```
- Only visible when status != 'ERLEDIGT'
- Confirms action with JavaScript
- Submits to `aktivitaet_mark_completed` endpoint

### 5. View Endpoints

#### Assignment View (`vermietung/views.py`)
```python
@vermietung_required
@require_http_methods(["POST"])
def aktivitaet_assign(request, pk):
    """Assign activity to a new user"""
```
- Validates user selection
- Updates `assigned_user` field
- Calls `save()` which triggers signal
- Shows success message
- Redirects to edit page

URL: `aktivitaeten/<int:pk>/zuweisen/`

#### Mark as Completed View (`vermietung/views.py`)
```python
@vermietung_required
@require_http_methods(["POST"])
def aktivitaet_mark_completed(request, pk):
    """Mark activity as completed (ERLEDIGT)"""
```
- Checks current status
- Sets status to 'ERLEDIGT'
- Calls `save()` which triggers signal
- Shows success message
- Redirects to edit page

URL: `aktivitaeten/<int:pk>/erledigt/`

## Email Template Design

### Outlook Compatibility
Both templates use:
- Table-based layout (no flexbox or grid)
- Inline CSS styles (no external stylesheets)
- Simple structure (no complex nesting)
- UTF-8 encoding
- Proper DOCTYPE and meta tags

### Template Structure
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
        <!-- Header with colored background -->
        <!-- Content with activity details -->
        <!-- CTA Button -->
        <!-- Footer -->
    </table>
</body>
</html>
```

### Color Scheme
- **activity-assigned**: Blue header (#0d6efd)
- **activity-completed**: Green header (#198754)
- Background: Light gray (#f4f4f4)
- Content area: White (#ffffff)

## Configuration

### SMTP Settings
Configure via Django admin at `/admin/core/smtpsettings/`:
- Host
- Port  
- Username
- Password
- Use TLS

### Base URL
Set in Django settings for absolute URLs in emails:
```python
BASE_URL = 'https://your-domain.com'
```

## Testing

### Unit Tests
Location: `vermietung/test_aktivitaet_mail_notifications.py`

**Test Classes**:
1. `ActivityMailTemplateCreationTest` - Verifies templates exist
2. `ActivityMailTemplateRenderingTest` - Tests variable substitution
3. `ActivitySignalNotificationTest` - Tests signal triggers
4. `ActivityMarkCompletedViewTest` - Tests completion flow
5. `ActivityAssignmentButtonTest` - Tests assignment UI

**Total**: 22 tests, all passing

### Manual Testing Checklist
- [ ] Create activity with assignee → Email sent to assignee
- [ ] Create activity without assignee → No email sent
- [ ] Edit activity, change assignee → Email sent to new assignee only
- [ ] Edit activity without changing assignee → No email sent
- [ ] Mark activity as completed → Email sent to creator
- [ ] Assignment button opens modal
- [ ] Modal shows all users
- [ ] Modal pre-selects current assignee
- [ ] Completing assignment sends email
- [ ] Email renders correctly in Outlook
- [ ] All template variables are replaced

## Troubleshooting

### No Emails Sent
1. Check SMTP settings in admin panel
2. Verify templates are active: `MailTemplate.objects.filter(key__in=['activity-assigned', 'activity-completed'], is_active=True)`
3. Check logs for errors: Look for `logger.warning()` messages
4. Verify recipient has email address set
5. Test SMTP connection manually

### Variables Not Replaced
1. Check spelling of variable names in context
2. Verify template uses `{{ variable }}` syntax
3. Review signal handler code for context building
4. Test rendering separately: `render_template(template, context)`

### Modal Flickering (FIXED)
- Issue was caused by `bg-dark` and `text-light` classes
- Fixed by using default Bootstrap light theme
- See `MODAL_FLICKERING_FIX.md` for details

## Future Enhancements
- [ ] Allow customizing email templates via admin UI
- [ ] Add email preview before sending
- [ ] Support attachments
- [ ] Add BCC/Reply-To options
- [ ] Email queue for better reliability
- [ ] Template versioning
- [ ] Rich text editor for templates
- [ ] Email delivery status tracking

## References
- Django Signal Documentation: https://docs.djangoproject.com/en/5.2/topics/signals/
- Bootstrap 5 Modal: https://getbootstrap.com/docs/5.3/components/modal/
- Email template best practices: Campaign Monitor, Litmus
