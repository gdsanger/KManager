# Generated migration for Password Reset Mail Template

from django.db import migrations


def create_password_reset_mail_template(apps, schema_editor):
    """
    Create mail template for password reset notification.
    Template: user-password-reset - sent when admin resets a user's password
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')
    
    password_reset_html = """<!DOCTYPE html>
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
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">Ihr neues Kennwort</h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Hallo {{ username }},
                            </p>
                            
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Ihr Kennwort wurde zurückgesetzt. Sie können sich nun mit den folgenden Zugangsdaten anmelden:
                            </p>
                            
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px; background-color: #f8f9fa; border-left: 4px solid #0d6efd; padding: 20px;">
                                <tr>
                                    <td>
                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px; width: 140px;"><strong>Benutzername:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px; font-family: monospace;">{{ username }}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Neues Kennwort:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px; font-family: monospace;">{{ password }}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="margin: 0 0 30px; color: #333333; font-size: 16px; line-height: 24px;">
                                Bitte ändern Sie Ihr Kennwort nach dem ersten Anmelden aus Sicherheitsgründen.
                            </p>
                            
                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #0d6efd;">
                                        <a href="{{ baseUrl }}" style="display: inline-block; padding: 14px 28px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: bold;">Zur Anmeldung</a>
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
                            <p style="margin: 15px 0 0; color: #adb5bd; font-size: 12px; line-height: 18px;">
                                Diese E-Mail wurde automatisch generiert. Bitte antworten Sie nicht auf diese Nachricht.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    # Create or update template (idempotent)
    MailTemplate.objects.update_or_create(
        key='user-password-reset',
        defaults={
            'subject': 'Ihr neues Kennwort für K-Manager',
            'message': password_reset_html,
            'from_name': '',
            'from_address': '',
            'cc_address': '',
            'is_active': True,
        }
    )


def delete_password_reset_mail_template(apps, schema_editor):
    """
    Reverse migration: delete the password reset mail template.
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')
    MailTemplate.objects.filter(key='user-password-reset').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_add_activity_mail_templates'),
    ]

    operations = [
        migrations.RunPython(
            create_password_reset_mail_template,
            delete_password_reset_mail_template
        ),
    ]
