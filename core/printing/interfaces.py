"""
Core Printing Interfaces

Defines contracts for PDF rendering and context building.
"""

from abc import ABC, abstractmethod
from typing import Any


class IPdfRenderer(ABC):
    """
    Interface for PDF rendering engines.
    
    Implementations convert HTML strings to PDF bytes.
    """
    
    @abstractmethod
    def render_html_to_pdf(self, html: str, base_url: str) -> bytes:
        """
        Render HTML string to PDF bytes.
        
        Args:
            html: HTML content to render
            base_url: Base URL for resolving relative paths (CSS, images, etc.)
            
        Returns:
            PDF content as bytes
            
        Raises:
            Exception: If rendering fails
        """
        pass


class IContextBuilder(ABC):
    """
    Interface for building template contexts from domain objects.
    
    This is a placeholder interface for future module implementations.
    Individual modules (e.g., auftragsverwaltung) will implement this
    to provide document-specific context.
    """
    
    @abstractmethod
    def build_context(self, obj: Any, *, company: Any = None) -> dict:
        """
        Build template context from domain object.
        
        Args:
            obj: Domain object (e.g., SalesDocument, Invoice)
            company: Optional company context
            
        Returns:
            Template context dictionary
        """
        pass
    
    def get_template_name(self, obj: Any) -> str:
        """
        Get template name for domain object.
        
        Optional method for implementations that need dynamic template selection.
        
        Args:
            obj: Domain object
            
        Returns:
            Template name/path
        """
        raise NotImplementedError("Subclass must implement get_template_name if needed")
