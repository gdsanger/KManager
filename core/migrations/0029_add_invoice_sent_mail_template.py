# Generated migration for Invoice Sent Mail Template

from django.db import migrations


def create_invoice_sent_mail_template(apps, schema_editor):
    """
    Create mail template for invoice sending.
    This template is used to send invoices to customers with PDF attachment.
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')

    # Template: Invoice Sent
    invoice_sent_html = """<!DOCTYPE html>
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
                        <td style="padding: 40px 40px 20px; background-color: #007bff; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">Rechnung {{ invoice_number }}</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                Sehr geehrte Damen und Herren,
                            </p>

                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 24px;">
                                anbei erhalten Sie die Rechnung <strong>{{ invoice_number }}</strong> als PDF-Anhang.
                            </p>

                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 0 0 30px; background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 20px;">
                                <tr>
                                    <td>
                                        <h2 style="margin: 0 0 15px; color: #333333; font-size: 20px; font-weight: bold;">Rechnungsdetails</h2>

                                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px; width: 140px;"><strong>Rechnungsnummer:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ invoice_number }}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Nettobetrag:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px;">{{ amount_net }} €</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Bruttobetrag:</strong></td>
                                                <td style="padding: 8px 0; color: #333333; font-size: 14px; font-weight: bold;">{{ amount_gross }} €</td>
                                            </tr>
                                            {% if due_date %}
                                            <tr>
                                                <td style="padding: 8px 0; color: #666666; font-size: 14px;"><strong>Fällig am:</strong></td>
                                                <td style="padding: 8px 0; color: #d9534f; font-size: 14px; font-weight: bold;">{{ due_date }}</td>
                                            </tr>
                                            {% endif %}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            {% if document_url %}
                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-radius: 4px; background-color: #007bff;">
                                        <a href="{{ document_url }}" style="display: inline-block; padding: 14px 28px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: bold;">Rechnung online ansehen</a>
                                    </td>
                                </tr>
                            </table>
                            {% endif %}
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; background-color: #f8f9fa; border-radius: 0 0 8px 8px; border-top: 1px solid #dee2e6;">
                            <p style="margin: 0; color: #6c757d; font-size: 14px; line-height: 20px;">
                                Mit freundlichen Grüßen,<br>
                                Ihr Team
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
        key='invoice-sent',
        defaults={
            'subject': 'Rechnung {{ invoice_number }} - Netto: {{ amount_net }}€, Brutto: {{ amount_gross }}€, Kunde: {{ customer_name }}',
            'message': invoice_sent_html,
            'from_name': '',
            'from_address': '',
            'cc_address': '',
            'is_active': True,
        }
    )


def delete_invoice_sent_mail_template(apps, schema_editor):
    """
    Reverse migration: delete the invoice sent mail template.
    """
    MailTemplate = apps.get_model('core', 'MailTemplate')
    MailTemplate.objects.filter(key='invoice-sent').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_add_invoice_email_to_adresse'),
    ]

    operations = [
        migrations.RunPython(
            create_invoice_sent_mail_template,
            delete_invoice_sent_mail_template
        ),
    ]
