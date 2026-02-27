"""
Services for the Lieferantenwesen module.

- InvoiceInService: Creates/updates InvoiceIn records.
- SupplierMatchService: Matches extracted supplier data to existing Supplier records.
- InvoiceExtractionService: Thin wrapper around core AI extraction service.
"""
import logging
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Optional

from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SupplierMatchService
# ---------------------------------------------------------------------------

class SupplierMatchService:
    """Match extracted supplier name/address data to existing Supplier records."""

    SIMILARITY_THRESHOLD = 0.80

    def _similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    def find_or_create(self, name: str, street: str = "", city: str = "", **kwargs):
        """
        Try to find an existing Supplier matching the given data.
        If none is found, create a new one.

        Returns (supplier, created) tuple.
        """
        from lieferantenwesen.models import Supplier

        # Exact name match first
        qs = Supplier.objects.filter(is_active=True)
        for supplier in qs:
            if self._similarity(name, supplier.name) >= self.SIMILARITY_THRESHOLD:
                logger.debug("Supplier matched by name similarity: %s", supplier)
                return supplier, False

        # No match → create
        supplier = Supplier.objects.create(
            name=name,
            adresse_street=street or kwargs.get("adresse_street", ""),
            adresse_city=city or kwargs.get("adresse_city", ""),
            adresse_zip=kwargs.get("adresse_zip", ""),
            adresse_country=kwargs.get("adresse_country", "DE"),
            email=kwargs.get("email", ""),
            telefon=kwargs.get("telefon", ""),
        )
        logger.info("New supplier created: %s (pk=%s)", supplier.name, supplier.pk)
        return supplier, True


# ---------------------------------------------------------------------------
# InvoiceExtractionService
# ---------------------------------------------------------------------------

class InvoiceExtractionService:
    """
    Extract invoice data from a PDF using the core AI extraction service and
    populate an InvoiceIn instance.

    Falls back gracefully if the AI provider is not configured.
    """

    def extract_and_populate(self, invoice_in, pdf_path: str, user: Optional[User] = None):
        """
        Run AI extraction on *pdf_path* and fill fields on *invoice_in*.

        The invoice status is advanced:
          DRAFT → EXTRACTED (AI ran)  or stays DRAFT (AI unavailable)
          Then → IN_REVIEW after supplier matching.

        Returns the updated invoice_in (unsaved – caller must call .save()).
        """
        from core.services.ai.invoice_extraction import InvoiceExtractionService as CoreExtractor
        from core.services.base import ServiceNotConfigured

        try:
            extractor = CoreExtractor()
            dto = extractor.extract_from_pdf(pdf_path, user=user)
        except (ServiceNotConfigured, Exception) as exc:
            logger.warning("AI extraction unavailable or failed: %s", exc)
            invoice_in.status = "DRAFT"
            return invoice_in

        # Apply extracted fields
        if dto.belegnummer and not invoice_in.invoice_no:
            invoice_in.invoice_no = dto.belegnummer
        if dto.belegdatum and not invoice_in.invoice_date:
            try:
                from datetime import date
                invoice_in.invoice_date = date.fromisoformat(dto.belegdatum)
            except (ValueError, TypeError):
                pass
        if dto.faelligkeit and not invoice_in.due_date:
            try:
                from datetime import date
                invoice_in.due_date = date.fromisoformat(dto.faelligkeit)
            except (ValueError, TypeError):
                pass

        # Amounts
        for src_field, dest_field in [
            ("nettobetrag", "net_amount"),
            ("umsatzsteuer", "tax_amount"),
            ("bruttobetrag", "gross_amount"),
        ]:
            val = getattr(dto, src_field, None)
            if val is not None:
                try:
                    setattr(invoice_in, dest_field, Decimal(str(val)))
                except (InvalidOperation, TypeError):
                    pass

        # Payment reference / IBAN
        if dto.referenznummer:
            invoice_in.payment_reference = dto.referenznummer

        invoice_in.status = "EXTRACTED"

        # Supplier matching
        supplier_name = getattr(dto, "lieferant_name", None)
        if supplier_name:
            matcher = SupplierMatchService()
            supplier, _ = matcher.find_or_create(
                name=supplier_name,
                street=getattr(dto, "lieferant_strasse", "") or "",
                city=getattr(dto, "lieferant_ort", "") or "",
                adresse_zip=getattr(dto, "lieferant_plz", "") or "",
                adresse_country=getattr(dto, "lieferant_land", "") or "DE",
            )
            invoice_in.supplier = supplier

        invoice_in.status = "IN_REVIEW"
        return invoice_in


# ---------------------------------------------------------------------------
# InvoiceInService
# ---------------------------------------------------------------------------

class InvoiceInService:
    """High-level service for creating and managing InvoiceIn records."""

    def create_from_pdf(self, pdf_file, user: Optional[User] = None):
        """
        Persist the uploaded PDF file, create an InvoiceIn draft, run AI
        extraction, and return the saved instance.
        """
        import os
        import tempfile

        from lieferantenwesen.models import InvoiceIn, Supplier

        # We need a placeholder supplier for the initial save – the extraction
        # service will replace it if AI succeeds.
        default_supplier = Supplier.objects.filter(is_active=True).first()
        if default_supplier is None:
            default_supplier = Supplier.objects.create(name="Unbekannt (KI-Import)")

        invoice = InvoiceIn(
            invoice_no="TBD",
            invoice_date=timezone.now().date(),
            supplier=default_supplier,
            status="DRAFT",
            created_by=user,
        )
        invoice.pdf_file = pdf_file
        invoice.save()

        # Run AI extraction on a temp copy of the file
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                for chunk in pdf_file.chunks() if hasattr(pdf_file, "chunks") else [pdf_file.read()]:
                    tmp.write(chunk)
                tmp_path = tmp.name

            extractor = InvoiceExtractionService()
            invoice = extractor.extract_and_populate(invoice, tmp_path, user=user)
            invoice.updated_by = user
            invoice.save()
        except Exception as exc:
            logger.warning("PDF extraction failed for invoice %s: %s", invoice.pk, exc)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return invoice
