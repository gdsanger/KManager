"""
AI Router - Main entry point for AI service requests
"""
import time
from typing import List, Dict, Optional
from decimal import Decimal
from django.contrib.auth.models import User

from core.models import AIProvider, AIModel, AIJobsHistory
from core.services.base import ServiceNotConfigured, ServiceDisabled
from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .schemas import AIResponse
from .pricing import calculate_cost


class AIRouter:
    """
    Router for AI service requests.
    Handles provider/model selection, request routing, and job history logging.
    """
    
    def __init__(self):
        """Initialize the AI router"""
        self._provider_classes = {
            "OpenAI": OpenAIProvider,
            "Gemini": GeminiProvider,
            # "Claude": ClaudeProvider,  # Future implementation
        }
    
    def _get_provider_instance(self, provider: AIProvider) -> BaseProvider:
        """
        Create provider instance from AIProvider model.
        
        Args:
            provider: AIProvider model instance
            
        Returns:
            Instantiated provider class
            
        Raises:
            ServiceNotConfigured: If provider type is not supported
        """
        provider_class = self._provider_classes.get(provider.provider_type)
        if not provider_class:
            raise ServiceNotConfigured(
                f"Provider type '{provider.provider_type}' is not supported"
            )
        
        return provider_class(
            api_key=provider.api_key,
            organization_id=provider.organization_id or None
        )
    
    def _select_model(
        self,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> tuple[AIProvider, AIModel]:
        """
        Select appropriate AI provider and model based on parameters.
        
        Selection logic:
        1. If both provider_type and model_id specified: use that exact combination
        2. If only provider_type specified: use first active model for that provider
        3. If nothing specified: use default (first active OpenAI, else first active Gemini)
        
        Args:
            provider_type: Optional provider type filter
            model_id: Optional model identifier
            
        Returns:
            Tuple of (AIProvider, AIModel)
            
        Raises:
            ServiceNotConfigured: If no active model is found
        """
        if provider_type and model_id:
            # Explicit provider and model selection
            try:
                provider = AIProvider.objects.get(
                    provider_type=provider_type,
                    is_active=True
                )
                model = AIModel.objects.get(
                    provider=provider,
                    model_id=model_id,
                    is_active=True
                )
                return provider, model
            except (AIProvider.DoesNotExist, AIModel.DoesNotExist):
                raise ServiceNotConfigured(
                    f"No active model found for provider '{provider_type}' "
                    f"with model_id '{model_id}'"
                )
        
        if provider_type:
            # Select first active model for specified provider
            try:
                provider = AIProvider.objects.get(
                    provider_type=provider_type,
                    is_active=True
                )
                model = AIModel.objects.filter(
                    provider=provider,
                    is_active=True
                ).first()
                
                if not model:
                    raise ServiceNotConfigured(
                        f"No active model found for provider '{provider_type}'"
                    )
                
                return provider, model
            except AIProvider.DoesNotExist:
                raise ServiceNotConfigured(
                    f"Provider '{provider_type}' not found or not active"
                )
        
        # No parameters specified - use default
        # Priority: OpenAI > Gemini > any other active provider
        for default_provider_type in ["OpenAI", "Gemini"]:
            try:
                provider = AIProvider.objects.get(
                    provider_type=default_provider_type,
                    is_active=True
                )
                model = AIModel.objects.filter(
                    provider=provider,
                    is_active=True
                ).first()
                
                if model:
                    return provider, model
            except AIProvider.DoesNotExist:
                continue
        
        # Fallback: any active model
        model = AIModel.objects.filter(
            provider__is_active=True,
            is_active=True
        ).select_related('provider').first()
        
        if not model:
            raise ServiceNotConfigured("No active AI model configured")
        
        return model.provider, model
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        provider_type: Optional[str] = None,
        user: Optional[User] = None,
        client_ip: Optional[str] = None,
        agent: str = "core.ai",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AIResponse:
        """
        Send a chat completion request through the AI router.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_id: Optional explicit model identifier
            provider_type: Optional explicit provider type
            user: Optional User instance for tracking
            client_ip: Optional client IP address
            agent: Agent/service identifier (default: "core.ai")
            temperature: Optional sampling temperature
            max_tokens: Optional maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            AIResponse with text, tokens, model, provider info
            
        Raises:
            ServiceNotConfigured: If no active model is found
            ServiceDisabled: If selected provider/model is disabled
        """
        # Select provider and model
        provider, model = self._select_model(provider_type, model_id)
        
        # Create job history record with Pending status
        job = AIJobsHistory.objects.create(
            agent=agent,
            user=user,
            provider=provider,
            model=model,
            status='Pending',
            client_ip=client_ip
        )
        
        start_time = time.time()
        
        try:
            # Get provider instance
            provider_instance = self._get_provider_instance(provider)
            
            # Make API call
            provider_response = provider_instance.chat(
                messages=messages,
                model_id=model.model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Calculate costs if tokens are available
            costs = None
            if provider_response.input_tokens is not None and provider_response.output_tokens is not None:
                costs = calculate_cost(
                    provider_response.input_tokens,
                    provider_response.output_tokens,
                    model.input_price_per_1m_tokens,
                    model.output_price_per_1m_tokens
                )
            
            # Update job with success
            job.status = 'Completed'
            job.input_tokens = provider_response.input_tokens
            job.output_tokens = provider_response.output_tokens
            job.costs = costs
            job.duration_ms = duration_ms
            job.save()
            
            # Return unified response
            return AIResponse(
                text=provider_response.text,
                raw=provider_response.raw,
                input_tokens=provider_response.input_tokens,
                output_tokens=provider_response.output_tokens,
                model=model.model_id,
                provider=provider.provider_type
            )
            
        except Exception as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Update job with error
            job.status = 'Error'
            job.duration_ms = duration_ms
            job.error_message = str(e)
            job.save()
            
            # Re-raise the exception
            raise
    
    def generate(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        provider_type: Optional[str] = None,
        user: Optional[User] = None,
        client_ip: Optional[str] = None,
        agent: str = "core.ai",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AIResponse:
        """
        Shortcut for simple text generation (single prompt in, text out).
        
        Args:
            prompt: Input prompt text
            model_id: Optional explicit model identifier
            provider_type: Optional explicit provider type
            user: Optional User instance for tracking
            client_ip: Optional client IP address
            agent: Agent/service identifier (default: "core.ai")
            temperature: Optional sampling temperature
            max_tokens: Optional maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            AIResponse with text, tokens, model, provider info
        """
        # Convert simple prompt to chat format
        messages = [{"role": "user", "content": prompt}]
        
        return self.chat(
            messages=messages,
            model_id=model_id,
            provider_type=provider_type,
            user=user,
            client_ip=client_ip,
            agent=agent,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
