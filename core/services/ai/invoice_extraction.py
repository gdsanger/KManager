"""
AI-powered invoice data extraction service.

This module provides functionality to extract invoice data from PDF files using AI vision models.
"""
import base64
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from dataclasses import dataclass, asdict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.models import AIJobsHistory
from core.services.ai.router import AIRouter
from core.services.base import ServiceNotConfigured


logger = logging.getLogger(__name__)


class InvoiceExtractionError(Exception):
    """
    Die Belegerkennung ist fehlgeschlagen – mit benennbarer Ursache.

    Die Klasse liegt bewusst in ``core``: ``lieferantenwesen`` setzt auf
    ``core`` auf, nicht umgekehrt.

    Attribute:
        reason: Kurzer, für den Anwender verständlicher Satz (deutsch).
        detail: Technischer Text – Originalfehler bzw. Anfang der
            Modellantwort. Auf ``DETAIL_MAX_LENGTH`` Zeichen gekürzt, damit
            eine seitenlange Anbieterantwort keine Meldung sprengt.
        ai_job_id: id des zugehörigen :class:`core.models.AIJobsHistory`-
            Eintrags, sofern bekannt – damit der technische Fehler
            nachschlagbar ist, ohne raten zu müssen.
    """

    #: Maximale Länge des technischen Details.
    DETAIL_MAX_LENGTH = 500

    def __init__(
        self,
        reason: str,
        detail: str = "",
        ai_job_id: Optional[int] = None,
    ):
        self.reason = reason
        self.detail = (detail or "")[: self.DETAIL_MAX_LENGTH]
        self.ai_job_id = ai_job_id
        super().__init__(reason)

    def __str__(self) -> str:
        return self.reason


@dataclass
class InvoiceDataDTO:
    """
    Data Transfer Object for extracted invoice data.
    Matches the Eingangsrechnung model structure.
    All fields are optional - unrecognized values should be None.
    """
    # Supplier information (as text - will be matched to Lieferant separately)
    lieferant_name: Optional[str] = None
    lieferant_strasse: Optional[str] = None
    lieferant_plz: Optional[str] = None
    lieferant_ort: Optional[str] = None
    lieferant_land: Optional[str] = None

    # Invoice details
    belegnummer: Optional[str] = None
    belegdatum: Optional[str] = None  # ISO format: YYYY-MM-DD
    faelligkeit: Optional[str] = None  # ISO format: YYYY-MM-DD
    zahlungsbedingungen: Optional[str] = None  # Payment terms text
    betreff: Optional[str] = None
    referenznummer: Optional[str] = None

    # Service period
    leistungszeitraum_von: Optional[str] = None  # ISO format: YYYY-MM-DD
    leistungszeitraum_bis: Optional[str] = None  # ISO format: YYYY-MM-DD

    # Amounts (as strings to avoid precision issues in JSON)
    nettobetrag: Optional[str] = None
    umsatzsteuer: Optional[str] = None
    bruttobetrag: Optional[str] = None

    # Line items
    positionen: Optional[list] = None

    # Notes
    notizen: Optional[str] = None
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate extracted data and convert to proper types.

        Returns:
            Dict with validated data (None values are removed)

        Raises:
            ValidationError: If data contains invalid values
        """
        errors = {}
        validated = {}

        # Validate dates
        date_fields = ['belegdatum', 'faelligkeit', 'leistungszeitraum_von', 'leistungszeitraum_bis']
        for field in date_fields:
            value = getattr(self, field)
            if value is not None:
                try:
                    # Try to parse ISO date format
                    datetime.strptime(value, '%Y-%m-%d')
                    validated[field] = value
                except (ValueError, TypeError):
                    errors[field] = f'Invalid date format: {value}. Expected YYYY-MM-DD.'

        # Validate amounts (decimals)
        amount_fields = ['nettobetrag', 'umsatzsteuer', 'bruttobetrag']
        for field in amount_fields:
            value = getattr(self, field)
            if value is not None:
                try:
                    decimal_value = Decimal(str(value))
                    validated[field] = decimal_value
                except (InvalidOperation, ValueError, TypeError):
                    errors[field] = f'Invalid decimal value: {value}'

        # String fields - just copy if not None
        string_fields = [
            'lieferant_name', 'lieferant_strasse', 'lieferant_plz',
            'lieferant_ort', 'lieferant_land',
            'belegnummer', 'betreff', 'referenznummer', 'notizen',
            'zahlungsbedingungen'
        ]
        for field in string_fields:
            value = getattr(self, field)
            if value is not None:
                validated[field] = str(value).strip()

        # Line items (positionen) - just copy if present
        if self.positionen is not None:
            validated['positionen'] = self.positionen

        if errors:
            raise ValidationError(errors)

        return validated


class InvoiceExtractionService:
    """Service for extracting invoice data from PDFs using AI."""
    
    EXTRACTION_PROMPT = """You are an AI assistant that extracts invoice data from PDF images.
Extract the following information from the invoice. Return ONLY a JSON object with these exact field names.
If a value is not found or unclear, use null (not "unknown", "N/A", or any other placeholder).

IMPORTANT:
- Return ONLY the JSON object, no markdown formatting, no explanations
- Use ISO date format (YYYY-MM-DD) for all dates
- Use numeric strings for amounts (e.g., "123.45")
- Never invent or guess values - use null if uncertain

Expected JSON structure:
{
    "lieferant_name": "Company or person name",
    "lieferant_strasse": "Street address",
    "lieferant_plz": "Postal code",
    "lieferant_ort": "City",
    "lieferant_land": "Country",
    "belegnummer": "Invoice number",
    "belegdatum": "Invoice date (YYYY-MM-DD)",
    "faelligkeit": "Due date (YYYY-MM-DD)",
    "zahlungsbedingungen": "Payment terms as text (e.g., '30 Tage netto', 'sofort', etc.)",
    "betreff": "Subject/description",
    "referenznummer": "Reference number",
    "leistungszeitraum_von": "Service period start (YYYY-MM-DD)",
    "leistungszeitraum_bis": "Service period end (YYYY-MM-DD)",
    "nettobetrag": "Net amount (as string)",
    "umsatzsteuer": "VAT amount (as string)",
    "bruttobetrag": "Gross amount (as string)",
    "positionen": [
        {
            "position_no": 1,
            "description": "Item description",
            "quantity": "1.0",
            "unit": "Stk",
            "unit_price": "100.00",
            "net_amount": "100.00",
            "tax_rate": "19.00",
            "tax_amount": "19.00",
            "gross_amount": "119.00"
        }
    ],
    "notizen": "Any additional notes"
}

Extract the data now:"""
    
    def __init__(self):
        """Initialize the invoice extraction service."""
        self.router = AIRouter()
    
    def extract_invoice_data(
        self,
        pdf_path: str,
        user: Optional[User] = None,
        client_ip: Optional[str] = None
    ) -> InvoiceDataDTO:
        """
        Extract invoice data from a PDF file using AI.

        Die Methode liefert entweder ein ``InvoiceDataDTO`` oder wirft – ein
        ``None`` als Rückgabewert würde die Ursache des Fehlschlags
        einebnen, und der Anwender bekäme keine Auskunft darüber, warum die
        Erkennung nicht funktioniert hat.

        Args:
            pdf_path: Path to the invoice PDF file
            user: Optional user making the request
            client_ip: Optional client IP address

        Returns:
            InvoiceDataDTO with extracted data

        Raises:
            ServiceNotConfigured: If AI service is not configured
            FileNotFoundError: If PDF file doesn't exist
            InvoiceExtractionError: If the provider call failed or the model
                answer could not be evaluated
        """
        logger.info(f"Starting invoice extraction for PDF: {pdf_path}")

        try:
            # Validate PDF exists
            path = Path(pdf_path)
            if not path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Use OpenAI Responses API with file upload
            # PDFs must be sent via Responses API using input_file, not chat/completions
            response = self.router.process_pdf_with_responses_api(
                pdf_path=pdf_path,
                prompt=self.EXTRACTION_PROMPT,
                user=user,
                client_ip=client_ip,
                agent="core.ai.invoice_extraction",
                temperature=0.0,
                max_tokens=1000
            )
            
            raw_text = response.text or ""
            logger.info(f"AI extraction completed. Response length: {len(raw_text)}")

            if not raw_text.strip():
                logger.error("AI returned an empty response for %s", pdf_path)
                raise InvoiceExtractionError(
                    reason="Die KI hat keine Antwort zum Beleg zurückgeliefert.",
                )

            # Parse JSON response
            try:
                # Remove potential markdown code blocks
                response_text = raw_text.strip()
                if response_text.startswith('```'):
                    # Remove markdown code blocks
                    lines = response_text.split('\n')
                    response_text = '\n'.join(
                        line for line in lines 
                        if not line.startswith('```')
                    )
                
                data = json.loads(response_text)
                logger.info("Successfully parsed JSON response")
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response text: {raw_text[:500]}")
                raise InvoiceExtractionError(
                    reason="Die KI hat keine auswertbaren Daten zurückgeliefert.",
                    detail=raw_text[:500],
                ) from e

            if not isinstance(data, dict):
                logger.error("AI returned a non-object JSON response: %r", data)
                raise InvoiceExtractionError(
                    reason="Die KI hat keine auswertbaren Daten zurückgeliefert.",
                    detail=raw_text[:500],
                )

            # Create DTO from extracted data
            dto = InvoiceDataDTO(**{
                k: v for k, v in data.items()
                if k in InvoiceDataDTO.__annotations__
            })

            logger.info(f"Created InvoiceDataDTO: {asdict(dto)}")
            return dto

        except ServiceNotConfigured as e:
            logger.error(f"AI service not configured: {e}")
            raise

        except FileNotFoundError as e:
            logger.error(f"PDF file not found: {e}")
            raise

        except InvoiceExtractionError:
            # Ursache bereits benannt – nicht ein zweites Mal einpacken.
            raise

        except Exception as e:
            logger.error(f"Unexpected error during invoice extraction: {e}", exc_info=True)
            raise InvoiceExtractionError(
                reason="Die KI-Auswertung ist fehlgeschlagen.",
                detail=str(e),
                # Der Router hängt die id des fehlgeschlagenen Jobs an die
                # Exception – so bleibt der technische Fehler auffindbar.
                ai_job_id=getattr(e, "ai_job_id", None),
            ) from e
