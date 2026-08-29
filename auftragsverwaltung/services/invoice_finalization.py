"""
Document Finalization Service (Echtdruck)

Provides idempotent finalization of journal-relevant documents (invoices and
credit notes): assigns document number, sets status to SENT and writes the
immutable entry in the outgoing invoice journal (Rechnungsausgangsjournal).
"""
from django.db import transaction
from django.utils import timezone

from auftragsverwaltung.services.number_range import get_next_number
from finanzen.services.journal import create_journal_entry, require_document_kind


def finalize_document(document):
    """
    Finalize an invoice or credit note (Echtdruck).

    Steps (all inside a single transaction):
    - assign document number if missing
    - set status to SENT if not already set
    - create the journal entry (Rechnungsausgangsjournal) for the document

    This operation is idempotent:
    - If the document already has a number, it won't be changed
    - Status is set to SENT if not already set
    - The journal entry is created exactly once per document

    Number assignment, status change and journal entry are transactionally
    coupled: if the journal entry cannot be created (e.g. unsupported tax
    rate), the document stays unfinalized.

    Args:
        document: SalesDocument instance (invoice or credit note)

    Returns:
        tuple: (document, was_modified) - document instance and boolean
        indicating if number or status were changed

    Raises:
        ValueError: If the document is neither an invoice nor a credit note
        finanzen.services.journal.JournalEntryError: If the journal entry
            cannot be created (subclass of ValueError)

    Example:
        >>> document, modified = finalize_document(document)
        >>> if modified:
        >>>     print(f"Document finalized with number: {document.number}")
    """
    # Validate this document belongs into the journal at all
    require_document_kind(document)

    was_modified = False

    with transaction.atomic():
        # Reload with row lock to prevent race conditions
        document = document.__class__.objects.select_for_update().get(pk=document.pk)

        # Assign number if missing (idempotent)
        if not document.number:
            document.number = get_next_number(
                document.company,
                document.document_type,
                document.issue_date or timezone.now()
            )
            was_modified = True

        # Set status to SENT if not already finalized
        if document.status != 'SENT':
            document.status = 'SENT'
            was_modified = True

        if was_modified:
            document.save(update_fields=['number', 'status'])

        # Journal entry is created on every call, but only once per document.
        # Documents finalized before the journal existed get their entry on
        # the next finalization attempt.
        create_journal_entry(document)

    return document, was_modified


def finalize_invoice(invoice):
    """
    Finalize an invoice (Echtdruck).

    Thin wrapper around :func:`finalize_document` that additionally enforces
    that the document really is an invoice.

    Args:
        invoice: SalesDocument instance (must have document_type.is_invoice=True)

    Returns:
        tuple: (invoice, was_modified)

    Raises:
        ValueError: If document is not an invoice

    Example:
        >>> invoice = SalesDocument.objects.get(pk=123)
        >>> invoice, modified = finalize_invoice(invoice)
        >>> if modified:
        >>>     print(f"Invoice finalized with number: {invoice.number}")
    """
    if not invoice.document_type.is_invoice:
        raise ValueError(f"Document type '{invoice.document_type.name}' is not an invoice")

    return finalize_document(invoice)
