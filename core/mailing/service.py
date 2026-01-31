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
        
        # Render message
        message_template = Template(mail_template.message)
        rendered_message = message_template.render(Context(context))
        
        return rendered_subject, rendered_message
    except TemplateSyntaxError as e:
        raise TemplateRenderError(f"Template-Syntax-Fehler: {str(e)}")
    except Exception as e:
        raise TemplateRenderError(f"Fehler beim Rendern des Templates: {str(e)}")


def send_mail(template_key, to, context, cc=None):
    """
    Send an email using a template.
    
    Args:
        template_key: str, the unique key of the MailTemplate
        to: list of recipient email addresses
        context: dict with template variables
        cc: optional list of CC recipient email addresses
        
    Raises:
        MailServiceError: If template not found or inactive
        TemplateRenderError: If template rendering fails
        MailSendError: If sending fails
    """
    # Load template
    try:
        mail_template = MailTemplate.objects.get(key=template_key)
    except MailTemplate.DoesNotExist:
        raise MailServiceError(f"Mail-Template mit Key '{template_key}' nicht gefunden.")
    
    # Check if template is active
    if not mail_template.is_active:
        raise MailServiceError(f"Mail-Template '{template_key}' ist deaktiviert.")
    
    # Validate sender fields - use defaults if empty
    from django.conf import settings
    from_address = mail_template.from_address or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
    from_name = mail_template.from_name or getattr(settings, 'DEFAULT_FROM_NAME', 'KManager')
    
    # Render template
    subject, html_body = render_template(mail_template, context)
    
    # Get SMTP settings
    smtp_settings = SmtpSettings.get_settings()
    
    # Build email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = f'"{from_name}" <{from_address}>'
    msg['To'] = ', '.join(to)
    
    # Collect all recipients (To + CC)
    all_recipients = list(to)
    
    # Add CC if configured in template
    if mail_template.cc_address:
        msg['Cc'] = mail_template.cc_address
        all_recipients.append(mail_template.cc_address)
    
    # Add dynamic CC if provided
    if cc:
        # Filter out empty strings and None values
        cc_list = [addr for addr in cc if addr]
        
        # Remove duplicates with To recipients
        cc_list = [addr for addr in cc_list if addr not in to]
        
        if cc_list:
            # Add to CC header (append to existing if template CC exists)
            existing_cc = msg.get('Cc', '')
            if existing_cc:
                msg['Cc'] = existing_cc + ', ' + ', '.join(cc_list)
            else:
                msg['Cc'] = ', '.join(cc_list)
            
            # Add to recipients list (avoid duplicates)
            for addr in cc_list:
                if addr not in all_recipients:
                    all_recipients.append(addr)
    
    # Attach HTML body
    html_part = MIMEText(html_body, 'html', 'utf-8')
    msg.attach(html_part)
    
    # Send via SMTP
    try:
        if smtp_settings.use_tls:
            # Use STARTTLS with timeout
            server = smtplib.SMTP(smtp_settings.host, smtp_settings.port, timeout=10)
            server.starttls()
        else:
            # Plain connection with timeout
            server = smtplib.SMTP(smtp_settings.host, smtp_settings.port, timeout=10)
        
        # Login if credentials provided
        if smtp_settings.username:
            server.login(smtp_settings.username, smtp_settings.password)
        
        # Send message
        server.sendmail(from_address, all_recipients, msg.as_string())
        server.quit()
        
    except smtplib.SMTPException as e:
        raise MailSendError(f"SMTP-Fehler beim Versenden: {str(e)}")
    except Exception as e:
        raise MailSendError(f"Fehler beim Versenden der E-Mail: {str(e)}")
