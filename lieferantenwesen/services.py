"""
Services for the Lieferantenwesen module.

- InvoiceInService: Creates/updates InvoiceIn records.
- SupplierMatchService: Matches extracted supplier data to existing Adresse (LIEFERANT) records.
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
    """Match extracted supplier name/address data to existing Adresse (LIEFERANT) records."""

    SIMILARITY_THRESHOLD = 0.80

    def _similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    def find_or_create(self, name: str, street: str = "", city: str = "", **kwargs):
        """
        Try to find an existing Adresse (LIEFERANT) matching the given data.
        If none is found, create a new one.

        Returns (adresse, created) tuple.
        """
        from core.models import Adresse

        # Exact name match first
        qs = Adresse.objects.filter(adressen_type="LIEFERANT")
        for adresse in qs:
            if self._similarity(name, adresse.name) >= self.SIMILARITY_THRESHOLD:
                logger.debug("Supplier matched by name similarity: %s", adresse)
                return adresse, False

        # No match → create
        adresse = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name=name,
            strasse=street or kwargs.get("strasse", ""),
            ort=city or kwargs.get("ort", ""),
            plz=kwargs.get("plz", ""),
            land=kwargs.get("land", "DE"),
            email=kwargs.get("email", ""),
            telefon=kwargs.get("telefon", ""),
        )
        logger.info("New supplier created: %s (pk=%s)", adresse.name, adresse.pk)
        return adresse, True


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
            dto = extractor.extract_invoice_data(pdf_path, user=user)
        except (ServiceNotConfigured, Exception) as exc:
            logger.warning("AI extraction unavailable or failed: %s", exc)
            invoice_in.status = "DRAFT"
            return invoice_in

        # Apply extracted fields
        if dto.belegnummer:
            # Map invoice number to invoice_no field (primary)
            if not invoice_in.invoice_no or invoice_in.invoice_no == "TBD":
                invoice_in.invoice_no = dto.belegnummer
            # Also keep in payment_reference for compatibility
            if not invoice_in.payment_reference:
                invoice_in.payment_reference = dto.belegnummer

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

        # Payment terms
        if dto.zahlungsbedingungen and not invoice_in.payment_terms_text:
            invoice_in.payment_terms_text = dto.zahlungsbedingungen

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

        # Payment reference / IBAN (keep existing behavior for referenznummer)
        if dto.referenznummer and not invoice_in.payment_reference:
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
                plz=getattr(dto, "lieferant_plz", "") or "",
                land=getattr(dto, "lieferant_land", "") or "DE",
            )
            invoice_in.supplier = supplier

        invoice_in.status = "IN_REVIEW"
        return invoice_in


# ---------------------------------------------------------------------------
# InvoiceInService
# ---------------------------------------------------------------------------

class InvoiceInService:
    """High-level service for creating and managing InvoiceIn records."""

    def _create_lines_from_dto(self, invoice, dto):
        """
        Create InvoiceInLine records from extracted line items.

        Args:
            invoice: The InvoiceIn instance
            dto: InvoiceDataDTO with potential positionen field
        """
        from lieferantenwesen.models import InvoiceInLine

        positionen = getattr(dto, "positionen", None)
        if not positionen or not isinstance(positionen, list):
            return

        for item in positionen:
            if not isinstance(item, dict):
                continue

            try:
                line = InvoiceInLine(
                    invoice=invoice,
                    position_no=item.get("position_no", 1),
                    description=item.get("description", ""),
                )

                # Optional numeric fields
                if item.get("quantity"):
                    line.quantity = Decimal(str(item["quantity"]))
                if item.get("unit"):
                    line.unit = item["unit"]
                if item.get("unit_price"):
                    line.unit_price = Decimal(str(item["unit_price"]))
                if item.get("net_amount"):
                    line.net_amount = Decimal(str(item["net_amount"]))
                if item.get("tax_rate"):
                    line.tax_rate = Decimal(str(item["tax_rate"]))
                if item.get("tax_amount"):
                    line.tax_amount = Decimal(str(item["tax_amount"]))
                if item.get("gross_amount"):
                    line.gross_amount = Decimal(str(item["gross_amount"]))

                line.save()
                logger.info(f"Created line item {line.position_no} for invoice {invoice.pk}")
            except (InvalidOperation, TypeError, ValueError) as exc:
                logger.warning(f"Failed to create line item from {item}: {exc}")
                continue

    def create_from_pdf(self, pdf_file, user: Optional[User] = None):
        """
        Persist the uploaded PDF file, create an InvoiceIn draft, run AI
        extraction, and return the saved instance.
        """
        import os
        import tempfile

        from core.models import Adresse
        from lieferantenwesen.models import InvoiceIn

        # We need a placeholder supplier for the initial save – the extraction
        # service will replace it if AI succeeds.
        default_supplier = Adresse.objects.filter(adressen_type="LIEFERANT").first()
        if default_supplier is None:
            default_supplier = Adresse.objects.create(
                adressen_type="LIEFERANT",
                name="Unbekannt (KI-Import)",
                strasse="",
                plz="",
                ort="",
                land="DE",
            )

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
        dto = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                for chunk in pdf_file.chunks() if hasattr(pdf_file, "chunks") else [pdf_file.read()]:
                    tmp.write(chunk)
                tmp_path = tmp.name

            extractor = InvoiceExtractionService()

            # Get the DTO before populating to access line items
            from core.services.ai.invoice_extraction import InvoiceExtractionService as CoreExtractor
            core_extractor = CoreExtractor()
            dto = core_extractor.extract_invoice_data(tmp_path, user=user)

            # Now populate the invoice fields
            invoice = extractor.extract_and_populate(invoice, tmp_path, user=user)
            invoice.updated_by = user
            invoice.save()

            # Create line items if present in DTO
            if dto:
                self._create_lines_from_dto(invoice, dto)
        except Exception as exc:
            logger.warning("PDF extraction failed for invoice %s: %s", invoice.pk, exc)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return invoice
