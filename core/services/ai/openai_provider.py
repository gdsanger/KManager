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
    
    def process_pdf_with_responses_api(
        self,
        pdf_path: str,
        prompt: str,
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Process PDF file using OpenAI Responses API with file upload.
        
        PDFs must be sent via Responses API using input_file, not chat/completions.
        
        Args:
            pdf_path: Path to the PDF file
            prompt: Text prompt for extraction
            model_id: OpenAI model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI parameters
            
        Returns:
            ProviderResponse with extracted text
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
        
        # Step 1: Upload PDF file to OpenAI
        with open(pdf_path, 'rb') as f:
            file_upload = client.files.create(
                file=f,
                purpose="user_data"
            )
        
        # Step 2: Use Responses API with input_file
        request_params = {
            "model": model_id,
            "input": [{
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt
                    },
                    {
                        "type": "input_file",
                        "file_id": file_upload.id
                    }
                ]
            }]
        }
        
        if temperature is not None:
            request_params["temperature"] = temperature
        
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens
        
        # Add any additional parameters
        request_params.update(kwargs)
        
        # Make API call to Responses API
        response = client.responses.create(**request_params)
        
        # Extract response data
        text = response.output_text if hasattr(response, 'output_text') else ""
        
        # Extract token usage if available
        input_tokens = None
        output_tokens = None
        if hasattr(response, 'usage'):
            input_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else None
            output_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else None
        
        return ProviderResponse(
            text=text,
            raw=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
