"""
Base provider interface for AI services
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from .schemas import ProviderResponse


class BaseProvider(ABC):
    """
    Abstract base class for AI providers.
    All providers must implement this interface.
    """
    
    def __init__(self, api_key: str, organization_id: Optional[str] = None):
        """
        Initialize the provider with credentials.
        
        Args:
            api_key: API key for the provider
            organization_id: Optional organization ID (e.g., for OpenAI)
        """
        self.api_key = api_key
        self.organization_id = organization_id
    
    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return the provider type identifier (e.g., 'OpenAI', 'Gemini')"""
        pass
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Send a chat completion request to the provider.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_id: Provider-specific model identifier
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            ProviderResponse with text, tokens, and raw response
            
        Raises:
            Exception: On API errors or invalid parameters
        """
        pass
