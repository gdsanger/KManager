"""
OpenAI provider implementation
"""
from typing import List, Dict, Optional
from .base_provider import BaseProvider
from .schemas import ProviderResponse


class OpenAIProvider(BaseProvider):
    """OpenAI API provider implementation"""
    
    @property
    def provider_type(self) -> str:
        return "OpenAI"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Send a chat completion request to OpenAI API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_id: OpenAI model identifier (e.g., 'gpt-4', 'gpt-3.5-turbo')
            temperature: Sampling temperature (0-2 for OpenAI)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI parameters
            
        Returns:
            ProviderResponse with text, tokens, and raw response
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI SDK not installed. Install with: pip install openai"
            )
        
        # Initialize OpenAI client
        client_kwargs = {"api_key": self.api_key}
        if self.organization_id:
            client_kwargs["organization"] = self.organization_id
        
        client = OpenAI(**client_kwargs)
        
        # Build request parameters
        request_params = {
            "model": model_id,
            "messages": messages,
        }
        
        if temperature is not None:
            request_params["temperature"] = temperature
        
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens
        
        # Add any additional parameters
        request_params.update(kwargs)
        
        # Make API call
        response = client.chat.completions.create(**request_params)
        
        # Extract response data
        text = response.choices[0].message.content or ""
        
        # Extract token usage
        input_tokens = response.usage.prompt_tokens if response.usage else None
        output_tokens = response.usage.completion_tokens if response.usage else None
        
        return ProviderResponse(
            text=text,
            raw=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
