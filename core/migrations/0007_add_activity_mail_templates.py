# Generated migration for Activity Mail Templates

from django.db import migrations


def create_activity_mail_templates(apps, schema_editor):
    """
    Create mail templates for activity notifications.
    Creates two templates:
    1. activity-assigned - sent when activity is assigned or assignee changes
    2. activity-completed - sent when activity is marked as completed
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')
    
    # Template 1: Activity Assigned
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
    
    # Template 2: Activity Completed
    activity_completed_html = """<!DOCTYPE html>
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
                        <td style="padding: 40px 40px 20px; background-color: #198754; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">Aktivität erledigt</h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Hallo {{ creator_name }},
                            </p>
                            
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Die folgende Aktivität wurde als erledigt markiert:
                            </p>
                            
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px; background-color: #f8f9fa; border-left: 4px solid #198754; padding: 20px;">
                                <tr>
                                    <td>
                                        <h2 style="margin: 0 0 15px; color: #198754; font-size: 20px; font-weight: bold;">{{ activity_title }}</h2>
                                        
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top: 15px;">
                                            {% if completed_by_name %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px; width: 140px;"><strong>Erledigt von:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ completed_by_name }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if completed_at %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Erledigt am:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ completed_at }}</td>
                                            </tr>
                                            {% endif %}
                                            {% if activity_context %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Kontext:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ activity_context }}</td>
                                            </tr>
                                            {% endif %}
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #198754;">
                                        <a href="{{ activity_url }}" style="display: inline-block; padding: 14px 28px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: bold;">Aktivität ansehen</a>
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
    
    # Create or update templates (idempotent)
    MailTemplate.objects.update_or_create(
        key='activity-assigned',
        defaults={
            'subject': 'Neue Aktivität zugewiesen: {{ activity_title }}',
            'message': activity_assigned_html,
            'from_name': '',
            'from_address': '',
            'cc_address': '',
            'is_active': True,
        }
    )
    
    MailTemplate.objects.update_or_create(
        key='activity-completed',
        defaults={
            'subject': 'Aktivität erledigt: {{ activity_title }}',
            'message': activity_completed_html,
            'from_name': '',
            'from_address': '',
            'cc_address': '',
            'is_active': True,
        }
    )


def delete_activity_mail_templates(apps, schema_editor):
    """
    Reverse migration: delete the activity mail templates.
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')
    MailTemplate.objects.filter(key__in=['activity-assigned', 'activity-completed']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_update_mailtemplate_fields'),
    ]

    operations = [
        migrations.RunPython(
            create_activity_mail_templates,
            delete_activity_mail_templates
        ),
    ]
