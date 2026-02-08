"""
Data Transfer Objects for Printing Framework
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PdfResult:
    """
    Result of PDF rendering operation.
    
    Encapsulates PDF content and metadata.
    """
    
    pdf_bytes: bytes
    filename: Optional[str] = None
    content_type: str = "application/pdf"
    
    def __post_init__(self):
        """Validate result after initialization."""
        if not isinstance(self.pdf_bytes, bytes):
            raise TypeError("pdf_bytes must be bytes")
        if len(self.pdf_bytes) == 0:
            raise ValueError("pdf_bytes cannot be empty")
