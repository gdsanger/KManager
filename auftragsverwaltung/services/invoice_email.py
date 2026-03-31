"""
Invoice Email Service

Handles sending invoices via email to customers with PDF attachments.
"""
from django.urls import reverse
from django.conf import settings
from core.mailing.service import send_mail, MailServiceError, MailSendError
from core.printing.service import PdfRenderService
from auftragsverwaltung.printing.context import SalesDocumentInvoiceContextBuilder
from auftragsverwaltung.services.invoice_finalization import finalize_invoice


class InvoiceEmailError(Exception):
    """Base exception for invoice email errors"""
    pass


def send_invoice_email(invoice, to_customer=True, to_internal=False, request=None):
    """
    Send invoice email with PDF attachment.

    Args:
        invoice: SalesDocument instance (must be an invoice)
        to_customer: bool, send to customer's invoice_email
        to_internal: bool, send to internal accounting (template sender)
        request: HttpRequest instance for building absolute URLs (optional)

    Returns:
        dict: {
            'success': bool,
            'recipients': list of email addresses,
            'error': str (only if success=False)
        }

    Raises:
        InvoiceEmailError: If sending fails or configuration is invalid
        ValueError: If document is not an invoice

    Example:
        >>> result = send_invoice_email(invoice, to_customer=True, to_internal=True)
        >>> if result['success']:
        >>>     print(f"Invoice sent to: {result['recipients']}")
    """
    # Validate this is an invoice
    if not invoice.document_type.is_invoice:
        raise ValueError(f"Document type '{invoice.document_type.name}' is not an invoice")

    # Finalize invoice (assign number if missing, set status to SENT)
    invoice, was_modified = finalize_invoice(invoice)

    # Build recipients list
    recipients = []
    cc_recipients = []

    # Load mail template to get sender address (for internal copy)
    from core.models import MailTemplate
    try:
        mail_template = MailTemplate.objects.get(key='invoice-sent')
        internal_address = mail_template.from_address or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    except MailTemplate.DoesNotExist:
        raise InvoiceEmailError("Mail-Template 'invoice-sent' nicht gefunden. Bitte Migration ausführen.")

    # Add customer email if requested
    if to_customer:
        if invoice.customer and invoice.customer.invoice_email:
            recipients.append(invoice.customer.invoice_email)
        else:
            raise InvoiceEmailError(
                f"Kunde '{invoice.customer.name if invoice.customer else 'N/A'}' "
                "hat keine Rechnungs-E-Mail-Adresse hinterlegt."
            )

    # Add internal email if requested (either as primary or CC)
    if to_internal:
        if not internal_address:
            raise InvoiceEmailError("Keine interne E-Mail-Adresse konfiguriert (Template oder Settings).")

        if to_customer:
            # Send to customer, CC to internal
            cc_recipients.append(internal_address)
        else:
            # Send only to internal (print scenario)
            recipients.append(internal_address)

    if not recipients:
        raise InvoiceEmailError("Keine Empfänger angegeben (to_customer oder to_internal muss True sein).")

    # Generate PDF
    try:
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(invoice)
        template_name = 'printing/orders/invoice.html'

        pdf_service = PdfRenderService()

        # Build base URL for static assets
        if request:
            base_url = request.build_absolute_uri('/')[:-1]
        else:
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')

        result = pdf_service.render(
            template_name=template_name,
            context=context,
            base_url=base_url,
            filename=f'Rechnung_{invoice.number}.pdf'
        )

        pdf_bytes = result.pdf_bytes
        pdf_filename = result.filename

    except Exception as e:
        raise InvoiceEmailError(f"Fehler beim Erzeugen des PDF: {str(e)}")

    # Build email context
    email_context = {
        'invoice_number': invoice.number,
        'customer_name': invoice.customer.name if invoice.customer else 'N/A',
        'amount_net': f"{invoice.total_net:.2f}",
        'amount_gross': f"{invoice.total_gross:.2f}",
        'due_date': invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else '',
    }

    # Add document URL if request is available
    if request:
        document_path = reverse('auftragsverwaltung:document_detail', kwargs={'pk': invoice.pk})
        email_context['document_url'] = request.build_absolute_uri(document_path)

    # Prepare PDF attachment
    attachments = [
        (pdf_filename, pdf_bytes, 'application/pdf')
    ]

    # Send email
    try:
        send_mail(
            template_key='invoice-sent',
            to=recipients,
            context=email_context,
            cc=cc_recipients if cc_recipients else None,
            attachments=attachments
        )

        all_recipients = recipients + cc_recipients
        return {
            'success': True,
            'recipients': all_recipients,
        }

    except (MailServiceError, MailSendError) as e:
        raise InvoiceEmailError(f"Fehler beim Versenden der E-Mail: {str(e)}")
