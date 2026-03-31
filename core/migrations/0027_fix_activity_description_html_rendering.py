# Generated migration to fix HTML rendering in activity email templates

from django.db import migrations


def fix_activity_description_html_rendering(apps, schema_editor):
    """
    Fix HTML rendering of activity description in email templates.

    The activity description field contains HTML from the rich text editor,
    but it was being auto-escaped in the email templates. This migration
    adds the |safe filter to render the HTML properly instead of showing
    raw HTML tags to users.

    Affected templates:
    - activity-reminder: Activity reminder emails (2 days before due date)
    - activity-assigned: Activity assignment notifications
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')

    # Fix Template 1: Activity Reminder
    # Only need to change line 48 to add |safe filter
    activity_reminder_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f4f4f4;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; background-color: #ffc107; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #000000; font-size: 24px; font-weight: bold;">⏰ Erinnerung: Aktivität fällig in 2 Tagen</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Hallo {{ assignee_name }},
                            </p>

                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                diese Aktivität ist in <strong>2 Tagen</strong> fällig:
                            </p>

                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px; background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 20px;">
                                <tr>
                                    <td>
                                        <h2 style="margin: 0 0 15px; color: #856404; font-size: 20px; font-weight: bold;">{{ activity_title }}</h2>
                                        {% if activity_description %}
                                        <p style="margin: 0 0 15px; color: #555555; font-size: 14px; line-height: 20px;">{{ activity_description|safe }}</p>
                                        {% endif %}

                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 15px;">
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px; width: 140px;"><strong>Priorität:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_priority }}</td>
                                            </tr>
                                            {% if activity_due_date %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Fällig am:</strong></td>
                                                <td style="padding: 8px 0; color: #d9534f; font-size: 14px; font-weight: bold;">{{ activity_due_date }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if activity_context %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Kontext:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_context }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if creator_name %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Erstellt von:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ creator_name }}{% if creator_email %} ({{ creator_email }}){% endif %}</td>
                                            </tr>
                                            {% endif %}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #ffc107;">
                                        <a href="{{ activity_url }}" style="display: inline-block; padding: 14px 28px; color: #000000; text-decoration: none; font-size: 16px; font-weight: bold;">Aktivität öffnen</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; border-top: 1px solid #dee2e6;">
                            <p style="margin: 0; color: #6c757d; font-size: 14px; line-height: 20px;">
                                Mit freundlichen Grüßen,<br>
                                Ihr K-Manager Team
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    # Fix Template 2: Activity Assigned
    # Only need to change line 50 to add |safe filter
    activity_assigned_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f4f4f4;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; background-color: #0d6efd; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">Neue Aktivität zugewiesen</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Hallo {{ assignee_name }},
                            </p>

                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Ihnen wurde eine neue Aktivität zugewiesen:
                            </p>

                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px; background-color: #f8f9fa; border-left: 4px solid #0d6efd; padding: 20px;">
                                <tr>
                                    <td>
                                        <h2 style="margin: 0 0 15px; color: #0d6efd; font-size: 20px; font-weight: bold;">{{ activity_title }}</h2>
                                        {% if activity_description %}
                                        <p style="margin: 0 0 15px; color: #555555; font-size: 14px; line-height: 20px;">{{ activity_description|safe }}</p>
                                        {% endif %}

                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 15px;">
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px; width: 140px;"><strong>Priorität:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_priority }}</td>
                                            </tr>
                                            {% if activity_due_date %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Fällig am:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_due_date }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if activity_context %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Kontext:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_context }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if creator_name %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Erstellt von:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ creator_name }}{% if creator_email %} ({{ creator_email }}){% endif %}</td>
                                            </tr>
                                            {% endif %}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #0d6efd;">
                                        <a href="{{ activity_url }}" style="display: inline-block; padding: 14px 28px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: bold;">Aktivität öffnen</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; border-top: 1px solid #dee2e6;">
                            <p style="margin: 0; color: #6c757d; font-size: 14px; line-height: 20px;">
                                Mit freundlichen Grüßen,<br>
                                Ihr K-Manager Team
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    # Update templates
    try:
        reminder_template = MailTemplate.objects.get(key='activity-reminder')
        reminder_template.message = activity_reminder_html
        reminder_template.save()
    except MailTemplate.DoesNotExist:
        # Template doesn't exist yet, will be created by earlier migration
        pass

    try:
        assigned_template = MailTemplate.objects.get(key='activity-assigned')
        assigned_template.message = activity_assigned_html
        assigned_template.save()
    except MailTemplate.DoesNotExist:
        # Template doesn't exist yet, will be created by earlier migration
        pass


def revert_activity_description_html_rendering(apps, schema_editor):
    """
    Reverse migration: revert to escaped HTML in activity email templates.
    Note: This is mainly for completeness. In practice, reverting this fix
    would bring back the bug where HTML is shown as raw tags.
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')

    # Revert Template 1: Activity Reminder (remove |safe filter)
    activity_reminder_html_old = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f4f4f4;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; background-color: #ffc107; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #000000; font-size: 24px; font-weight: bold;">⏰ Erinnerung: Aktivität fällig in 2 Tagen</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Hallo {{ assignee_name }},
                            </p>

                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                diese Aktivität ist in <strong>2 Tagen</strong> fällig:
                            </p>

                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px; background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 20px;">
                                <tr>
                                    <td>
                                        <h2 style="margin: 0 0 15px; color: #856404; font-size: 20px; font-weight: bold;">{{ activity_title }}</h2>
                                        {% if activity_description %}
                                        <p style="margin: 0 0 15px; color: #555555; font-size: 14px; line-height: 20px;">{{ activity_description }}</p>
                                        {% endif %}

                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 15px;">
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px; width: 140px;"><strong>Priorität:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_priority }}</td>
                                            </tr>
                                            {% if activity_due_date %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Fällig am:</strong></td>
                                                <td style="padding: 8px 0; color: #d9534f; font-size: 14px; font-weight: bold;">{{ activity_due_date }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if activity_context %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Kontext:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_context }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if creator_name %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Erstellt von:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ creator_name }}{% if creator_email %} ({{ creator_email }}){% endif %}</td>
                                            </tr>
                                            {% endif %}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #ffc107;">
                                        <a href="{{ activity_url }}" style="display: inline-block; padding: 14px 28px; color: #000000; text-decoration: none; font-size: 16px; font-weight: bold;">Aktivität öffnen</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; border-top: 1px solid #dee2e6;">
                            <p style="margin: 0; color: #6c757d; font-size: 14px; line-height: 20px;">
                                Mit freundlichen Grüßen,<br>
                                Ihr K-Manager Team
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    # Revert Template 2: Activity Assigned (remove |safe filter)
    activity_assigned_html_old = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f4f4f4;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; background-color: #0d6efd; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">Neue Aktivität zugewiesen</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Hallo {{ assignee_name }},
                            </p>

                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Ihnen wurde eine neue Aktivität zugewiesen:
                            </p>

                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px; background-color: #f8f9fa; border-left: 4px solid #0d6efd; padding: 20px;">
                                <tr>
                                    <td>
                                        <h2 style="margin: 0 0 15px; color: #0d6efd; font-size: 20px; font-weight: bold;">{{ activity_title }}</h2>
                                        {% if activity_description %}
                                        <p style="margin: 0 0 15px; color: #555555; font-size: 14px; line-height: 20px;">{{ activity_description }}</p>
                                        {% endif %}

                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 15px;">
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px; width: 140px;"><strong>Priorität:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_priority }}</td>
                                            </tr>
                                            {% if activity_due_date %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Fällig am:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_due_date }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if activity_context %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Kontext:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_context }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if creator_name %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Erstellt von:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ creator_name }}{% if creator_email %} ({{ creator_email }}){% endif %}</td>
                                            </tr>
                                            {% endif %}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #0d6efd;">
                                        <a href="{{ activity_url }}" style="display: inline-block; padding: 14px 28px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: bold;">Aktivität öffnen</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; border-top: 1px solid #dee2e6;">
                            <p style="margin: 0; color: #6c757d; font-size: 14px; line-height: 20px;">
                                Mit freundlichen Grüßen,<br>
                                Ihr K-Manager Team
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    # Revert templates
    try:
        reminder_template = MailTemplate.objects.get(key='activity-reminder')
        reminder_template.message = activity_reminder_html_old
        reminder_template.save()
    except MailTemplate.DoesNotExist:
        pass

    try:
        assigned_template = MailTemplate.objects.get(key='activity-assigned')
        assigned_template.message = activity_assigned_html_old
        assigned_template.save()
    except MailTemplate.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_projekt_projektfile'),
    ]

    operations = [
        migrations.RunPython(
            fix_activity_description_html_rendering,
            revert_activity_description_html_rendering
        ),
    ]
