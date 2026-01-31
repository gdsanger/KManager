"""
Pricing calculations for AI service usage
"""
from decimal import Decimal
from typing import Optional


def calculate_cost(
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    input_price_per_1m: Decimal,
    output_price_per_1m: Decimal
) -> Optional[Decimal]:
    """
    Calculate cost for AI API call based on token usage and pricing.
    
    Args:
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
        input_price_per_1m: Price per 1 million input tokens in USD
        output_price_per_1m: Price per 1 million output tokens in USD
        
    Returns:
        Total cost in USD, or None if tokens are not available
    """
    if input_tokens is None or output_tokens is None:
        return None
    
    # Calculate cost: (tokens / 1,000,000) * price_per_1m
    input_cost = Decimal(input_tokens) / Decimal(1_000_000) * input_price_per_1m
    output_cost = Decimal(output_tokens) / Decimal(1_000_000) * output_price_per_1m
    
    total_cost = input_cost + output_cost
    
    # Round to 6 decimal places for precision
    return total_cost.quantize(Decimal('0.000001'))
