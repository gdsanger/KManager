"""
Services for the Lieferantenwesen module.

- InvoiceInService: Creates/updates InvoiceIn records.
- SupplierMatchService: Matches extracted supplier data to existing Adresse (LIEFERANT) records.
- InvoiceExtractionService: Thin wrapper around core AI extraction service.
"""
import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Optional, Tuple

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import Error as DatabaseError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.services.ai.invoice_extraction import (
    InvoiceExtractionService as CoreExtractor,
)
from core.services.model_fields import set_truncated, truncate_to_field

logger = logging.getLogger(__name__)

#: Genauigkeit aller Geldbeträge – Cent, kaufmännisch gerundet.
CENT = Decimal("0.01")


# ---------------------------------------------------------------------------
# Beträge aus der Belegerkennung
# ---------------------------------------------------------------------------

def to_decimal(value) -> Optional[Decimal]:
    """
    Einen Wert aus der Belegerkennung in ein ``Decimal`` wandeln.

    Liefert ``None``, wenn der Wert fehlt, leer oder unlesbar ist. Die ``0``
    ist ein gültiger Betrag und wird als ``Decimal("0")`` zurückgegeben –
    ein Wahrheitswert-Test würde sie fälschlich verwerfen.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def derive_line_net_amount(item: dict) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Nettobetrag einer erkannten Rechnungsposition bestimmen.

    Reihenfolge (der Bruttobetrag ist der Wert, der zum Rechnungsbetrag
    passen muss, deshalb hat er Vorrang):

    1. ``net_amount`` vorhanden → verwenden.
    2. ``gross_amount`` + ``tax_rate`` → ``net = gross / (1 + tax_rate/100)``.
       Die Steuer wird als ``gross - net`` zurückgegeben, damit
       Netto + Steuer exakt den Bruttobetrag ergeben.
    3. ``gross_amount`` + ``tax_amount`` → ``net = gross - tax``.
    4. ``quantity`` + ``unit_price`` → ``net = quantity * unit_price``.
       Nur der letzte Ausweg: ``unit_price`` ist im Extraktions-Prompt als
       Nettopreis beschrieben, wird vom Modell aber erkennbar auch brutto
       gefüllt.
    5. Sonst nicht herleitbar.

    Returns:
        ``(net_amount, tax_amount)``. ``tax_amount`` ist nur gesetzt, wenn
        er zwingend zum hergeleiteten Nettobetrag gehört (Fall 2), sonst
        ``None``. ``net_amount`` ist ``None``, wenn sich der Nettobetrag aus
        keiner Kombination ergibt – dann darf die Position **nicht**
        gespeichert werden, ein geratener Betrag ginge unbemerkt in den
        DATEV-Buchungsstapel.
    """
    net = to_decimal(item.get("net_amount"))
    if net is not None:
        return net.quantize(CENT, rounding=ROUND_HALF_UP), None

    gross = to_decimal(item.get("gross_amount"))
    if gross is not None:
        gross = gross.quantize(CENT, rounding=ROUND_HALF_UP)

        tax_rate = to_decimal(item.get("tax_rate"))
        if tax_rate is not None:
            divisor = Decimal("1") + tax_rate / Decimal("100")
            if divisor != 0:
                net = (gross / divisor).quantize(CENT, rounding=ROUND_HALF_UP)
                return net, gross - net

        tax_amount = to_decimal(item.get("tax_amount"))
        if tax_amount is not None:
            return gross - tax_amount.quantize(CENT, rounding=ROUND_HALF_UP), None

    quantity = to_decimal(item.get("quantity"))
    unit_price = to_decimal(item.get("unit_price"))
    if quantity is not None and unit_price is not None:
        return (quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP), None

    return None, None


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

    #: Toleranz beim Abgleich der Positionssummen mit dem Rechnungsbetrag.
    GROSS_TOLERANCE = Decimal("0.01")

    def _create_lines_from_dto(self, invoice, dto) -> Tuple[int, int]:
        """
        Create InvoiceInLine records from extracted line items.

        Jede Position wird einzeln in einem eigenen ``transaction.atomic()``
        gespeichert: Ohne eigenen Sicherungspunkt versetzt ein Datenbank-
        fehler unter PostgreSQL die laufende Transaktion in einen Fehler-
        zustand, und alle folgenden Positionen scheitern ebenfalls. Eine
        fehlerhafte Position darf den Import der übrigen nicht mitreißen.

        Positionen ohne herleitbaren Nettobetrag werden übersprungen – nicht
        mit ``0`` gespeichert und nicht geraten (siehe
        :func:`derive_line_net_amount`).

        Args:
            invoice: The InvoiceIn instance
            dto: InvoiceDataDTO with potential positionen field

        Returns:
            ``(created, skipped)`` – Anzahl übernommener und übersprungener
            Positionen, damit die View den Anwender auf die fehlenden
            Positionen hinweisen kann.
        """
        from lieferantenwesen.models import InvoiceInLine

        positionen = getattr(dto, "positionen", None)
        if not positionen or not isinstance(positionen, list):
            return 0, 0

        created = 0
        skipped = 0
        for item in positionen:
            if not isinstance(item, dict):
                logger.warning("Ignoriere unlesbare Rechnungsposition: %r", item)
                skipped += 1
                continue

            try:
                net_amount, derived_tax = derive_line_net_amount(item)
                if net_amount is None:
                    logger.warning(
                        "Position ohne herleitbaren Nettobetrag übersprungen "
                        "(Rechnung %s): %r",
                        invoice.pk,
                        item,
                    )
                    skipped += 1
                    continue

                line = InvoiceInLine(
                    invoice=invoice,
                    description=truncate_to_field(
                        InvoiceInLine, "description", item.get("description") or ""
                    ),
                    net_amount=net_amount,
                )

                position_no = to_decimal(item.get("position_no"))
                if position_no is not None and position_no >= 0:
                    line.position_no = int(position_no)

                # Optionale Felder: auf „Wert vorhanden“ prüfen, nicht auf
                # „Wert wahr“ – eine Position mit Betrag 0 (Rabatt-, Gratis-
                # oder Sammelzeile) behält so ihren Wert.
                unit = item.get("unit")
                if unit:
                    set_truncated(line, "unit", unit)

                for key, field in (
                    ("quantity", "quantity"),
                    ("unit_price", "unit_price"),
                    ("tax_rate", "tax_rate"),
                    ("tax_amount", "tax_amount"),
                    ("gross_amount", "gross_amount"),
                ):
                    value = to_decimal(item.get(key))
                    if value is not None:
                        setattr(line, field, value)

                # Aus dem Bruttobetrag zurückgerechnet: Die Steuer ergibt sich
                # zwingend als Differenz, sonst passt Netto + Steuer nicht
                # exakt auf den ausgewiesenen Bruttobetrag.
                if derived_tax is not None:
                    line.tax_amount = derived_tax

                with transaction.atomic():
                    line.save()
                created += 1
                logger.info(
                    "Created line item %s for invoice %s",
                    line.position_no,
                    invoice.pk,
                )
            except (
                InvalidOperation,
                TypeError,
                ValueError,
                ValidationError,
                DatabaseError,
            ) as exc:
                logger.warning("Failed to create line item from %r: %s", item, exc)
                skipped += 1
                continue

        return created, skipped

    def _lines_gross_mismatch(self, invoice) -> Optional[Decimal]:
        """
        Summe der Positions-Bruttobeträge gegen den Rechnungsbetrag prüfen.

        Returns die Positionssumme, wenn sie um mehr als einen Cent vom
        Bruttobetrag der Rechnung abweicht, sonst ``None``. Es wird bewusst
        nichts korrigiert und nichts abgebrochen – aber ohne diesen Hinweis
        ginge ein aus dem Bruttobetrag zurückgerechneter Nettobetrag
        unbemerkt in den Buchungsstapel.
        """
        if invoice.gross_amount is None:
            return None
        total = invoice.lines.aggregate(total=Sum("gross_amount"))["total"]
        if total is None:
            return None
        # SQLite liefert die Summe mit Nachkommastellen aus der Fließkomma-
        # Arithmetik – für Vergleich und Meldung zählt der Cent.
        total = Decimal(total).quantize(CENT, rounding=ROUND_HALF_UP)
        if abs(total - invoice.gross_amount) <= self.GROSS_TOLERANCE:
            return None
        logger.warning(
            "Positionssumme %s weicht vom Bruttobetrag %s der Rechnung %s ab.",
            total,
            invoice.gross_amount,
            invoice.pk,
        )
        return total

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

        Analog dazu trägt die zurückgegebene Instanz:

        * ``skipped_line_count`` – Anzahl der Positionen, die nicht
          übernommen werden konnten (fehlender oder unlesbarer Betrag).
        * ``lines_gross_mismatch`` – Summe der Positions-Bruttobeträge, wenn
          sie um mehr als einen Cent vom Bruttobetrag der Rechnung abweicht,
          sonst ``None``.
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

        # Positionen anlegen. Der Beleg ist an dieser Stelle bereits
        # gespeichert – ein Fehler beim Anlegen der Positionen darf den
        # Upload deshalb nicht mehr scheitern lassen, sonst bleibt ein
        # verwaister Entwurf zurück, von dem der Anwender nichts erfährt.
        invoice.skipped_line_count = 0
        invoice.lines_gross_mismatch = None
        if dto:
            try:
                created, invoice.skipped_line_count = self._create_lines_from_dto(
                    invoice, dto
                )
                if created:
                    invoice.lines_gross_mismatch = self._lines_gross_mismatch(invoice)
            except Exception as exc:
                logger.exception(
                    "Positionen der Rechnung %s konnten nicht angelegt werden: %s",
                    invoice.pk,
                    exc,
                )

        return invoice
