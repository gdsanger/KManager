"""
Google Gemini provider implementation
"""
from typing import List, Dict, Optional
from .base_provider import BaseProvider
from .schemas import ProviderResponse


class GeminiProvider(BaseProvider):
    """Google Gemini API provider implementation"""
    
    @property
    def provider_type(self) -> str:
        return "Gemini"
    
    def _convert_messages_to_gemini(self, messages: List[Dict[str, str]]) -> tuple:
        """
        Convert OpenAI-style messages to Gemini format.
        
        Gemini uses a different message format:
        - system messages become part of the first user message or system_instruction
        - user/assistant messages are mapped to user/model roles
        
        Returns:
            Tuple of (system_instruction, converted_messages)
        """
        system_instruction = None
        converted_messages = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                # Use system message as system instruction
                if system_instruction is None:
                    system_instruction = content
                else:
                    # If multiple system messages, append to first one
                    system_instruction += "\n\n" + content
            elif role == "user":
                converted_messages.append({
                    "role": "user",
                    "parts": [content]
                })
            elif role == "assistant":
                converted_messages.append({
                    "role": "model",  # Gemini uses 'model' instead of 'assistant'
                    "parts": [content]
                })
        
        return system_instruction, converted_messages
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ProviderResponse:
        """
        Send a chat completion request to Gemini API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_id: Gemini model identifier (e.g., 'gemini-pro', 'gemini-1.5-flash')
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Gemini parameters
            
        Returns:
            ProviderResponse with text, tokens (if available), and raw response
        """
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "Google Generative AI SDK not installed. Install with: pip install google-generativeai"
            )
        
        # Configure API key
        genai.configure(api_key=self.api_key)
        
        # Convert messages to Gemini format
        system_instruction, gemini_messages = self._convert_messages_to_gemini(messages)
        
        # Initialize model
        model_kwargs = {}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction
        
        model = genai.GenerativeModel(model_id, **model_kwargs)
        
        # Build generation config
        generation_config = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_tokens is not None:
            generation_config["max_output_tokens"] = max_tokens
        
        # Add any additional parameters
        generation_config.update(kwargs)
        
        # Make API call
        # If we have chat history, use chat mode
        if gemini_messages:
            # Start chat with history (excluding last message)
            chat = model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
            # Send last message
            last_message = gemini_messages[-1]["parts"][0] if gemini_messages else ""
            response = chat.send_message(
                last_message,
                generation_config=generation_config if generation_config else None
            )
        else:
            # No messages, use empty prompt
            response = model.generate_content(
                "",
                generation_config=generation_config if generation_config else None
            )
        
        # Extract response text
        text = response.text if hasattr(response, 'text') else ""
        
        # Extract token usage if available
        # Note: Gemini may not always provide token counts
        input_tokens = None
        output_tokens = None
        
        if hasattr(response, 'usage_metadata'):
            if hasattr(response.usage_metadata, 'prompt_token_count'):
                input_tokens = response.usage_metadata.prompt_token_count
            if hasattr(response.usage_metadata, 'candidates_token_count'):
                output_tokens = response.usage_metadata.candidates_token_count
        
        return ProviderResponse(
            text=text,
            raw=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
