# AI Core Service Documentation

## Overview

The AI Core Service provides a unified API for interacting with multiple AI providers (OpenAI, Gemini, and Claude). It handles provider/model selection, request routing, usage tracking, and cost calculation.

## Architecture

### Components

```
core/services/ai/
├── __init__.py           # Package exports
├── router.py             # Main AIRouter class
├── base_provider.py      # Abstract provider interface
├── openai_provider.py    # OpenAI implementation
├── gemini_provider.py    # Gemini implementation
├── pricing.py            # Cost calculation utilities
└── schemas.py            # Data structures (AIResponse, etc.)
```

### Database Models

#### AIProvider
Stores AI provider configurations:
- `name`: Human-readable provider name
- `provider_type`: Provider type (OpenAI, Gemini, Claude)
- `api_key`: Encrypted API key
- `organization_id`: Optional organization ID (for OpenAI)
- `is_active`: Whether the provider is enabled

#### AIModel
Stores AI model configurations with pricing:
- `provider`: Foreign key to AIProvider
- `name`: Human-readable model name
- `model_id`: Provider-specific model identifier (e.g., "gpt-4", "gemini-pro")
- `input_price_per_1m_tokens`: Input token pricing in USD
- `output_price_per_1m_tokens`: Output token pricing in USD
- `is_active`: Whether the model is enabled

#### AIJobsHistory
Logs all AI API calls for auditing and cost tracking:
- `agent`: Service/agent that initiated the call
- `user`: User who made the request (if applicable)
- `provider`: Provider used
- `model`: Model used
- `status`: Pending, Completed, or Error
- `client_ip`: Client IP address
- `input_tokens`: Number of input tokens used
- `output_tokens`: Number of output tokens generated
- `costs`: Calculated cost in USD
- `timestamp`: When the request was made
- `duration_ms`: API call duration in milliseconds
- `error_message`: Error details (if status is Error)

## Usage

### Basic Chat Request

```python
from core.services.ai import AIRouter

router = AIRouter()

# Simple chat request
response = router.chat(
    messages=[
        {"role": "user", "content": "What is the capital of France?"}
    ]
)

print(response.text)  # "The capital of France is Paris."
print(response.input_tokens)  # e.g., 12
print(response.output_tokens)  # e.g., 8
print(response.provider)  # e.g., "OpenAI"
print(response.model)  # e.g., "gpt-4"
```

### Chat with System Message

```python
response = router.chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"}
    ],
    temperature=0.7,
    max_tokens=100
)
```

### Explicit Provider/Model Selection

```python
# Specify provider type only (uses first active model)
response = router.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    provider_type="Gemini"
)

# Specify both provider and model
response = router.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    provider_type="OpenAI",
    model_id="gpt-4"
)
```

### Simple Text Generation

```python
# Shortcut for single-prompt requests
response = router.generate(
    prompt="Write a haiku about coding",
    temperature=0.9
)

print(response.text)
```

### With User and Agent Tracking

```python
from django.contrib.auth.models import User

user = User.objects.get(username="john")

response = router.chat(
    messages=[{"role": "user", "content": "Help me plan my day"}],
    user=user,
    client_ip="192.168.1.100",
    agent="task_planner"
)
```

## Model Selection Logic

The router uses the following logic to select a provider and model:

1. **Explicit Selection**: If both `provider_type` and `model_id` are specified, use that exact combination
2. **Provider Only**: If only `provider_type` is specified, use the first active model for that provider
3. **Default Selection**: If nothing is specified:
   - Try OpenAI first (first active model)
   - Then try Gemini (first active model)
   - Finally, use any active model

## Cost Calculation

Costs are automatically calculated when token usage is available:

```
cost = (input_tokens / 1,000,000 × input_price) + (output_tokens / 1,000,000 × output_price)
```

- Prices are stored per model in the `AIModel` table
- Costs are calculated in USD with 6 decimal places precision
- If tokens are not available (some providers don't return them), cost is `None`

## Job History Logging

Every AI request is automatically logged to `AIJobsHistory`:

1. **Before Request**: Job created with status='Pending'
2. **After Request**: Job updated with:
   - status='Completed' or 'Error'
   - Token counts (if available)
   - Calculated costs
   - Duration in milliseconds
   - Error message (if applicable)

This provides complete audit trail and cost tracking.

## Security

- **API Keys**: Stored in database (should be encrypted in production)
- **No Keys in Logs**: API keys are never logged or exposed in exceptions
- **No Keys in Responses**: Raw provider responses may contain sensitive data; handle with care

## Error Handling

```python
from core.services.base import ServiceNotConfigured, ServiceDisabled

try:
    response = router.chat(...)
except ServiceNotConfigured as e:
    # No active provider/model configured
    print(f"Service not configured: {e}")
except ServiceDisabled as e:
    # Selected provider/model is disabled
    print(f"Service disabled: {e}")
except Exception as e:
    # Other errors (API errors, network issues, etc.)
    print(f"Error: {e}")
```

## Admin Interface

### Managing Providers

1. Navigate to Django Admin → AI Providers
2. Add a new provider:
   - Name: "My OpenAI Account"
   - Provider Type: OpenAI
   - API Key: `sk-...`
   - Organization ID: (optional)
   - Active: ✓

### Managing Models

1. Navigate to Django Admin → AI Models
2. Add a new model:
   - Provider: Select from dropdown
   - Name: "GPT-4"
   - Model ID: "gpt-4"
   - Input Price: 30.00 (per 1M tokens)
   - Output Price: 60.00 (per 1M tokens)
   - Active: ✓

### Viewing Job History

1. Navigate to Django Admin → AI Jobs History
2. Filter by:
   - Status (Pending, Completed, Error)
   - Provider
   - Model
   - User
   - Date

View detailed information:
- Token usage
- Costs
- Duration
- Error messages (if any)

## Provider-Specific Notes

### OpenAI

- Supports all standard chat models (GPT-3.5, GPT-4, etc.)
- Returns accurate token counts
- Temperature range: 0-2
- Requires `openai` package

### Gemini

- Supports Gemini models (gemini-pro, gemini-1.5-flash, etc.)
- Message format is converted automatically:
  - `system` → system instruction
  - `user` → user
  - `assistant` → model
- Token counts may not always be available
- Temperature range: 0-2
- Requires `google-generativeai` package

### Claude (Future)

- Not yet implemented
- Will follow same interface as other providers

## Examples

### Multi-turn Conversation

```python
messages = [
    {"role": "system", "content": "You are a helpful coding assistant."},
    {"role": "user", "content": "How do I reverse a string in Python?"},
    {"role": "assistant", "content": "You can use slicing: `reversed_string = my_string[::-1]`"},
    {"role": "user", "content": "Can you show me with an example?"}
]

response = router.chat(messages=messages)
print(response.text)
```

### Cost Analysis Query

```python
from core.models import AIJobsHistory
from django.db.models import Sum

# Get total costs for a user
total_cost = AIJobsHistory.objects.filter(
    user__username="john",
    status='Completed'
).aggregate(Sum('costs'))['costs__sum']

print(f"Total spent: ${total_cost}")

# Get costs by provider
from django.db.models import Count, Sum

costs_by_provider = AIJobsHistory.objects.filter(
    status='Completed'
).values('provider__provider_type').annotate(
    total_cost=Sum('costs'),
    total_calls=Count('id')
)

for item in costs_by_provider:
    print(f"{item['provider__provider_type']}: ${item['total_cost']} ({item['total_calls']} calls)")
```

## Testing

See `core/test_ai_service.py` for comprehensive test examples.

## Future Enhancements

- Claude provider implementation
- Embeddings support
- Streaming responses
- Retry logic with exponential backoff
- Rate limiting
- Model fallback mechanisms
- Caching for repeated queries
