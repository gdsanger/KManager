"""
Mail service for rendering and sending emails via SMTP
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from django.template import Template, Context, TemplateSyntaxError
from core.models import SmtpSettings, MailTemplate


class MailServiceError(Exception):
    """Base exception for mail service errors"""
    pass


class TemplateRenderError(MailServiceError):
    """Error during template rendering"""
    pass


class MailSendError(MailServiceError):
    """Error during mail sending"""
    pass


def render_template(mail_template, context):
    """
    Render a mail template with given context.
    
    Args:
        mail_template: MailTemplate instance
        context: dict with template variables
        
    Returns:
        tuple: (rendered_subject, rendered_html)
        
    Raises:
        TemplateRenderError: If template rendering fails
    """
    try:
        # Render subject
        subject_template = Template(mail_template.subject)
        rendered_subject = subject_template.render(Context(context))
        
        # Render HTML message
        html_template = Template(mail_template.message_html)
        rendered_html = html_template.render(Context(context))
        
        return rendered_subject, rendered_html
    except TemplateSyntaxError as e:
        raise TemplateRenderError(f"Template-Syntax-Fehler: {str(e)}")
    except Exception as e:
        raise TemplateRenderError(f"Fehler beim Rendern des Templates: {str(e)}")


def send_mail(template_key, to, context):
    """
    Send an email using a template.
    
    Args:
        template_key: str, the unique key of the MailTemplate
        to: list of recipient email addresses
        context: dict with template variables
        
    Raises:
        MailServiceError: If template not found
        TemplateRenderError: If template rendering fails
        MailSendError: If sending fails
    """
    # Load template
    try:
        mail_template = MailTemplate.objects.get(key=template_key)
    except MailTemplate.DoesNotExist:
        raise MailServiceError(f"Mail-Template mit Key '{template_key}' nicht gefunden.")
    
    # Render template
    subject, html_body = render_template(mail_template, context)
    
    # Get SMTP settings
    smtp_settings = SmtpSettings.get_settings()
    
    # Build email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = f'"{mail_template.from_name}" <{mail_template.from_address}>'
    msg['To'] = ', '.join(to)
    
    # Add CC if configured
    if mail_template.cc_copy_to:
        msg['Cc'] = mail_template.cc_copy_to
        # Add CC to recipients list
        to = list(to) + [mail_template.cc_copy_to]
    
    # Attach HTML body
    html_part = MIMEText(html_body, 'html', 'utf-8')
    msg.attach(html_part)
    
    # Send via SMTP
    try:
        if smtp_settings.use_tls:
            # Use STARTTLS
            server = smtplib.SMTP(smtp_settings.host, smtp_settings.port)
            server.starttls()
        else:
            # Plain connection
            server = smtplib.SMTP(smtp_settings.host, smtp_settings.port)
        
        # Login if credentials provided
        if smtp_settings.username:
            server.login(smtp_settings.username, smtp_settings.password)
        
        # Send message
        server.sendmail(mail_template.from_address, to, msg.as_string())
        server.quit()
        
    except smtplib.SMTPException as e:
        raise MailSendError(f"SMTP-Fehler beim Versenden: {str(e)}")
    except Exception as e:
        raise MailSendError(f"Fehler beim Versenden der E-Mail: {str(e)}")
