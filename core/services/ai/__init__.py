"""
AI Service Package

Provides unified AI API with support for multiple providers (OpenAI, Gemini, Claude).
Handles routing, cost tracking, and job history logging.

Main entry point: AIRouter

Example usage:
    from core.services.ai import AIRouter
    
    router = AIRouter()
    response = router.chat(
        messages=[{"role": "user", "content": "Hello!"}],
        provider_type="OpenAI"
    )
    print(response.text)
"""

from .router import AIRouter
from .schemas import AIResponse, ProviderResponse, ChatMessage
from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .pricing import calculate_cost

__all__ = [
    'AIRouter',
    'AIResponse',
    'ProviderResponse',
    'ChatMessage',
    'BaseProvider',
    'OpenAIProvider',
    'GeminiProvider',
    'calculate_cost',
]
