"""
AI-powered invoice data extraction service.

This module provides functionality to extract invoice data from PDF files using AI vision models.
"""
import base64
import json
import logging
import io
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from dataclasses import dataclass, asdict

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from pdf2image import convert_from_path
from PIL import Image

from core.models import AIJobsHistory
from core.services.ai.router import AIRouter
from core.services.base import ServiceNotConfigured


logger = logging.getLogger(__name__)


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
    betreff: Optional[str] = None
    referenznummer: Optional[str] = None
    
    # Service period
    leistungszeitraum_von: Optional[str] = None  # ISO format: YYYY-MM-DD
    leistungszeitraum_bis: Optional[str] = None  # ISO format: YYYY-MM-DD
    
    # Amounts (as strings to avoid precision issues in JSON)
    nettobetrag: Optional[str] = None
    umsatzsteuer: Optional[str] = None
    bruttobetrag: Optional[str] = None
    
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
            'belegnummer', 'betreff', 'referenznummer', 'notizen'
        ]
        for field in string_fields:
            value = getattr(self, field)
            if value is not None:
                validated[field] = str(value).strip()
        
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
    "betreff": "Subject/description",
    "referenznummer": "Reference number",
    "leistungszeitraum_von": "Service period start (YYYY-MM-DD)",
    "leistungszeitraum_bis": "Service period end (YYYY-MM-DD)",
    "nettobetrag": "Net amount (as string)",
    "umsatzsteuer": "VAT amount (as string)",
    "bruttobetrag": "Gross amount (as string)",
    "notizen": "Any additional notes"
}

Extract the data now:"""
    
    def __init__(self):
        """Initialize the invoice extraction service."""
        self.router = AIRouter()
    
    def _pdf_to_image_base64(self, pdf_path: str) -> Tuple[str, str]:
        """
        Convert PDF file to image (PNG) and encode as base64 for AI processing.
        
        OpenAI's Vision API only accepts image MIME types (image/jpeg, image/png),
        not PDFs. This method converts the first page of the PDF to a PNG image.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (base64-encoded image content, MIME type)
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            Exception: If PDF conversion fails
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        try:
            # Convert first page of PDF to image
            # pdf2image returns a list of PIL Image objects, one per page
            logger.debug(f"Converting PDF to image: {pdf_path}")
            images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=200)
            
            if not images:
                raise ValueError("PDF conversion returned no images - file may be corrupted or empty")
            
            # Use the first page
            image = images[0]
            
            # Convert PIL Image to base64 PNG
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            image_bytes = buffer.read()
            
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            logger.debug(f"PDF converted to image. Size: {len(image_bytes)} bytes, Base64 length: {len(image_base64)}")
            
            return image_base64, 'image/png'
            
        except Exception as e:
            logger.error(f"Failed to convert PDF to image: {e}")
            raise
    
    def extract_invoice_data(
        self,
        pdf_path: str,
        user: Optional[User] = None,
        client_ip: Optional[str] = None
    ) -> Optional[InvoiceDataDTO]:
        """
        Extract invoice data from a PDF file using AI.
        
        Args:
            pdf_path: Path to the invoice PDF file
            user: Optional user making the request
            client_ip: Optional client IP address
            
        Returns:
            InvoiceDataDTO with extracted data, or None if extraction failed
            
        Raises:
            ServiceNotConfigured: If AI service is not configured
            FileNotFoundError: If PDF file doesn't exist
        """
        logger.info(f"Starting invoice extraction for PDF: {pdf_path}")
        
        try:
            # Convert PDF to image (OpenAI Vision API requires images, not PDFs)
            image_base64, mime_type = self._pdf_to_image_base64(pdf_path)
            
            # Prepare message with image
            # OpenAI vision API expects a specific format with image MIME types
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.EXTRACTION_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            # Call AI service
            # Use vision-capable model (GPT-4 Vision or Gemini Pro Vision)
            # The router will select the appropriate model
            response = self.router.chat(
                messages=messages,
                user=user,
                client_ip=client_ip,
                agent="core.ai.invoice_extraction",
                temperature=0.0,  # Use deterministic output
                max_tokens=1000
            )
            
            logger.info(f"AI extraction completed. Response length: {len(response.text)}")
            
            # Parse JSON response
            try:
                # Remove potential markdown code blocks
                response_text = response.text.strip()
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
                logger.error(f"Response text: {response.text[:500]}")
                return None
            
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
        
        except Exception as e:
            logger.error(f"Unexpected error during invoice extraction: {e}", exc_info=True)
            return None
