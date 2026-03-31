"""
Invoice Finalization Service (Echtdruck)

Provides idempotent invoice finalization: assigns document number and sets status to SENT.
"""
from django.db import transaction
from django.utils import timezone
from auftragsverwaltung.services.number_range import get_next_number


def finalize_invoice(invoice):
    """
    Finalize an invoice (Echtdruck): assign number if missing and set status to SENT.

    This operation is idempotent:
    - If invoice already has a number, it won't be changed
    - Status is set to SENT if not already set

    Args:
        invoice: SalesDocument instance (must have document_type.is_invoice=True)

    Returns:
        tuple: (invoice, was_modified) - invoice instance and boolean indicating if changes were made

    Raises:
        ValueError: If document is not an invoice

    Example:
        >>> invoice = SalesDocument.objects.get(pk=123)
        >>> invoice, modified = finalize_invoice(invoice)
        >>> if modified:
        >>>     print(f"Invoice finalized with number: {invoice.number}")
    """
    # Validate this is an invoice
    if not invoice.document_type.is_invoice:
        raise ValueError(f"Document type '{invoice.document_type.name}' is not an invoice")

    was_modified = False

    with transaction.atomic():
        # Reload with row lock to prevent race conditions
        invoice = invoice.__class__.objects.select_for_update().get(pk=invoice.pk)

        # Assign number if missing (idempotent)
        if not invoice.number:
            invoice.number = get_next_number(
                invoice.company,
                invoice.document_type,
                invoice.issue_date or timezone.now()
            )
            was_modified = True

        # Set status to SENT if not already finalized
        if invoice.status != 'SENT':
            invoice.status = 'SENT'
            was_modified = True

        if was_modified:
            invoice.save(update_fields=['number', 'status'])

    return invoice, was_modified
