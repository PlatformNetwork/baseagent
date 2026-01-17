"""Token estimation utilities."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a string.
    
    This uses a simple heuristic (4 chars per token) which is commonly used
    as a rough approximation for English text when a tokenizer isn't available.
    
    Args:
        text: Input text
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
        
    return len(text) // 4
