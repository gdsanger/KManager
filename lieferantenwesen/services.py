"""
Services for the Lieferantenwesen module.

- InvoiceInService: Creates/updates InvoiceIn records.
- SupplierMatchService: Matches extracted supplier data to existing Adresse (LIEFERANT) records.
- InvoiceExtractionService: Thin wrapper around core AI extraction service.
"""
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Optional

from django.contrib.auth.models import User
from django.utils import timezone

from core.services.ai.invoice_extraction import (
    InvoiceExtractionService as CoreExtractor,
)
from core.services.model_fields import set_truncated, truncate_to_field

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

        # No match → create. Die Werte stammen aus der KI-Belegerkennung und
        # sind unbegrenzt lang – ohne Kürzung schlägt das INSERT fehl und der
        # gesamte Upload geht verloren.
        values = {
            "name": name,
            "strasse": street or kwargs.get("strasse", ""),
            "ort": city or kwargs.get("ort", ""),
            "plz": kwargs.get("plz", ""),
            "land": kwargs.get("land", "DE"),
            "email": kwargs.get("email", ""),
            "telefon": kwargs.get("telefon", ""),
        }
        adresse = Adresse.objects.create(
            adressen_type="LIEFERANT",
            **{
                field: truncate_to_field(Adresse, field, value)
                for field, value in values.items()
            },
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

    #: DTO-Feld → Modellfeld für alle Datumsangaben aus der Belegerkennung.
    DATE_FIELD_MAP = (
        ("belegdatum", "invoice_date"),
        ("faelligkeit", "due_date"),
        ("leistungszeitraum_von", "service_period_from"),
        ("leistungszeitraum_bis", "service_period_to"),
    )

    def extract(self, pdf_path: str, user: Optional[User] = None):
        """
        Run the core AI extraction on *pdf_path*.

        Returns the InvoiceDataDTO, or None if the AI provider is not
        configured, the call failed, or nothing could be parsed.
        """
        try:
            return CoreExtractor().extract_invoice_data(pdf_path, user=user)
        except Exception as exc:
            logger.warning("AI extraction unavailable or failed: %s", exc)
            return None

    def populate(self, invoice_in, dto):
        """
        Fill empty fields on *invoice_in* from *dto*.

        Bereits gepflegte Werte werden nie überschrieben – die Erkennung
        ergänzt nur, was noch leer ist.

        The invoice status is advanced:
          DRAFT → EXTRACTED (AI ran)  or stays DRAFT (no usable DTO)
          Then → IN_REVIEW after supplier matching.

        Returns the updated invoice_in (unsaved – caller must call .save()).
        """
        if dto is None:
            invoice_in.status = "DRAFT"
            return invoice_in

        # Apply extracted fields. Alle Freitexte werden auf die Feldlänge
        # gekürzt – die KI liefert beliebig lange Werte, ein zu langer Text
        # würde sonst das Speichern der kompletten Rechnung verhindern.
        if dto.belegnummer:
            # Map invoice number to invoice_no field (primary)
            if not invoice_in.invoice_no:
                set_truncated(invoice_in, "invoice_no", dto.belegnummer)
            # Also keep in payment_reference for compatibility
            if not invoice_in.payment_reference:
                set_truncated(invoice_in, "payment_reference", dto.belegnummer)

        for dto_field, model_field in self.DATE_FIELD_MAP:
            value = getattr(dto, dto_field, None)
            if not value or getattr(invoice_in, model_field, None):
                continue
            try:
                setattr(invoice_in, model_field, date.fromisoformat(value))
            except (ValueError, TypeError):
                logger.warning(
                    "Ignoriere unlesbares Datum aus der Belegerkennung: %s=%r",
                    dto_field,
                    value,
                )

        # Payment terms
        if dto.zahlungsbedingungen and not invoice_in.payment_terms_text:
            set_truncated(
                invoice_in, "payment_terms_text", dto.zahlungsbedingungen
            )

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
            set_truncated(invoice_in, "payment_reference", dto.referenznummer)

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

    def extract_and_populate(self, invoice_in, pdf_path: str, user: Optional[User] = None):
        """
        Run AI extraction on *pdf_path* and fill fields on *invoice_in*.

        Returns the updated invoice_in (unsaved – caller must call .save()).
        """
        return self.populate(invoice_in, self.extract(pdf_path, user=user))


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
                    description=truncate_to_field(
                        InvoiceInLine, "description", item.get("description", "")
                    ),
                )

                # Optional numeric fields
                if item.get("quantity"):
                    line.quantity = Decimal(str(item["quantity"]))
                if item.get("unit"):
                    set_truncated(line, "unit", item["unit"])
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

        Die Belegerkennung läuft **vor** dem ersten Speichern auf einer noch
        ungespeicherten Instanz. Nur so ist ``invoice_date`` beim Befüllen
        leer und das im Beleg ausgewiesene Belegdatum wird übernommen – ein
        vorab gesetztes Erfassungsdatum würde von ``populate()`` als bereits
        gepflegter Wert behandelt und das erkannte Datum verwerfen.

        Konnte kein Belegdatum erkannt werden, fällt ``invoice_date`` auf
        heute zurück (Pflichtfeld). Das Attribut ``invoice_date_fallback``
        der zurückgegebenen Instanz zeigt an, ob das passiert ist, damit die
        View den Anwender zur Prüfung auffordern kann – ein falsches
        Rechnungsdatum landet sonst still im falschen DATEV-Buchungsstapel.
        """
        import os
        import tempfile

        from core.models import Adresse, Mandant
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

        # Gibt es genau einen Mandanten, ist die Zuordnung eindeutig. Sonst
        # bleibt sie offen und muss im Bearbeitungsformular gepflegt werden –
        # raten wäre eine unbemerkte Falschbuchung im Buchungsstapel.
        companies = Mandant.objects.all()[:2]
        default_company = companies[0] if len(companies) == 1 else None

        # Noch nicht gespeichert: invoice_date bleibt bewusst leer, damit die
        # Belegerkennung das Rechnungsdatum setzen kann.
        invoice = InvoiceIn(
            invoice_no="",
            supplier=default_supplier,
            company=default_company,
            status="DRAFT",
            created_by=user,
        )

        # Run AI extraction on a temp copy of the file
        dto = None
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                for chunk in pdf_file.chunks() if hasattr(pdf_file, "chunks") else [pdf_file.read()]:
                    tmp.write(chunk)
                tmp_path = tmp.name

            extractor = InvoiceExtractionService()
            # Einmal extrahieren – der DTO wird sowohl für die Kopfdaten als
            # auch für die Positionen gebraucht.
            dto = extractor.extract(tmp_path, user=user)
            invoice = extractor.populate(invoice, dto)
        except Exception as exc:
            logger.warning("PDF extraction failed for uploaded invoice: %s", exc)
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        # invoice_date ist Pflichtfeld: ohne erkanntes Belegdatum bleibt nur
        # das Erfassungsdatum – der Anwender muss darauf hingewiesen werden.
        invoice.invoice_date_fallback = not invoice.invoice_date
        if invoice.invoice_date_fallback:
            invoice.invoice_date = timezone.localdate()
            logger.warning(
                "Kein Rechnungsdatum aus PDF %r erkannt – Rückfall auf %s. "
                "Der Beleg muss geprüft werden, sonst landet er im falschen "
                "Buchungsstapel.",
                getattr(pdf_file, "name", "?"),
                invoice.invoice_date,
            )

        invoice.pdf_file = pdf_file
        invoice.updated_by = user
        invoice.save()

        # Create line items if present in DTO
        if dto:
            self._create_lines_from_dto(invoice, dto)

        return invoice
