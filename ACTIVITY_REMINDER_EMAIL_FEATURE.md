# Activity Reminder Email Feature

## Overview
This feature automatically sends reminder emails to users 2 days before an activity's due date.

## Components

### 1. Database Model
- **Field**: `Aktivitaet.reminder_sent_at` (DateTimeField, nullable)
- **Purpose**: Tracks when a reminder email was sent to ensure idempotency
- **Index**: Added for query performance

### 2. Mail Template
- **Key**: `activity-reminder`
- **Subject**: `Erinnerung: {{ activity_title }} fällig in 2 Tagen`
- **Style**: Yellow/warning color scheme (similar to Bootstrap warning alerts)
- **Created**: Via migration `core/migrations/0009_add_activity_reminder_mail_template.py`

### 3. Management Command
- **Command**: `send_activity_reminders`
- **Location**: `vermietung/management/commands/send_activity_reminders.py`

#### Selection Criteria
The command finds activities that meet ALL of the following criteria:
- Due date is exactly 2 days from today
- Status is `OFFEN` or `IN_BEARBEITUNG` (not completed or cancelled)
- `reminder_sent_at` is NULL (no reminder sent yet)
- Has an assigned user (`assigned_user` is not NULL)
- Assigned user has an email address (not NULL or empty)

#### Features
- **Idempotent**: Only sends one reminder per activity
- **Error Handling**: Continues processing if one email fails
- **Dry-run Mode**: Test without sending emails
- **Logging**: Detailed logging for monitoring

## Usage

### Manual Execution

Test without sending emails:
```bash
python manage.py send_activity_reminders --dry-run
```

Send reminder emails:
```bash
python manage.py send_activity_reminders
```

### Production Deployment

Schedule the command to run daily using cron. For example, to run every day at 9:00 AM:

```bash
0 9 * * * cd /path/to/kmanager && /path/to/venv/bin/python manage.py send_activity_reminders >> /var/log/kmanager/reminders.log 2>&1
```

Or using systemd timer, create `/etc/systemd/system/kmanager-reminders.service`:

```ini
[Unit]
Description=KManager Activity Reminders
After=network.target

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/kmanager
ExecStart=/path/to/venv/bin/python manage.py send_activity_reminders
```

And `/etc/systemd/system/kmanager-reminders.timer`:

```ini
[Unit]
Description=KManager Activity Reminders Timer
Requires=kmanager-reminders.service

[Timer]
OnCalendar=daily
OnCalendar=09:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable kmanager-reminders.timer
sudo systemctl start kmanager-reminders.timer
```

## Testing

Run the test suite:
```bash
python manage.py test vermietung.test_activity_reminder
```

### Test Coverage
- ✅ Template exists and renders correctly
- ✅ Finds activities due in exactly 2 days
- ✅ Sends reminder emails
- ✅ Idempotency (no duplicate sends)
- ✅ Ignores completed activities
- ✅ Ignores cancelled activities
- ✅ Ignores activities not due in 2 days
- ✅ Ignores activities without assigned user
- ✅ Ignores users without email
- ✅ Dry-run mode works correctly
- ✅ Handles multiple activities
- ✅ Continues on error

## Monitoring

Check logs for:
- **Success**: `Sent activity reminder to {email} for activity #{id}`
- **Warning**: `Failed to send activity reminder for activity #{id}: {error}`
- **Error**: `Unexpected error sending activity reminder for activity #{id}: {error}`

## Template Customization

To customize the email template:
1. Go to Django Admin → Mail Templates
2. Find template with key `activity-reminder`
3. Edit subject or message
4. Available placeholders:
   - `{{ assignee_name }}` - Name of assigned user
   - `{{ activity_title }}` - Activity title
   - `{{ activity_description }}` - Activity description
   - `{{ activity_priority }}` - Priority display text
   - `{{ activity_due_date }}` - Due date (formatted)
   - `{{ activity_context }}` - Context (Mietobjekt/Vertrag/Kunde)
   - `{{ activity_url }}` - Link to activity
   - `{{ creator_name }}` - Activity creator name
   - `{{ creator_email }}` - Activity creator email

## Troubleshooting

### No emails are being sent
1. Check SMTP settings in Django Admin → SMTP Einstellungen
2. Verify activities meet all selection criteria
3. Check `reminder_sent_at` hasn't already been set
4. Run with `--dry-run` to see what would be sent

### Emails sent multiple times
- Check that `reminder_sent_at` is being set correctly
- Verify the command isn't being run multiple times by mistake

### Email template not found
- Ensure migration `0009_add_activity_reminder_mail_template.py` has been applied
- Check template exists in admin with key `activity-reminder`

## Related Files
- Model: `vermietung/models.py` (Aktivitaet class)
- Migration (model): `vermietung/migrations/0024_add_reminder_sent_at_to_aktivitaet.py`
- Migration (template): `core/migrations/0009_add_activity_reminder_mail_template.py`
- Command: `vermietung/management/commands/send_activity_reminders.py`
- Tests: `vermietung/test_activity_reminder.py`
