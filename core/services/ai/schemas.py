"""
Data schemas for AI service requests and responses
"""
from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict


@dataclass
class AIResponse:
    """Structured response from AI provider"""
    text: str
    raw: Any
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    model: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class ProviderResponse:
    """Response from a specific AI provider"""
    text: str
    raw: Any
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


@dataclass
class ChatMessage:
    """Chat message structure"""
    role: str  # 'system', 'user', 'assistant'
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for API calls"""
        return {"role": self.role, "content": self.content}
