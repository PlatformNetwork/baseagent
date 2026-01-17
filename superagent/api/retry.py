"""Retry logic with exponential backoff for API calls."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import httpx

from superagent.config.models import RetryConfig


T = TypeVar("T")


@dataclass
class RetryState:
    """State of a retry operation."""
    attempt: int
    last_error: Optional[Exception]
    last_status_code: Optional[int]
    total_delay: float


class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (1-indexed)
            
        Returns:
            Delay in seconds with jitter
        """
        # Exponential backoff: base_delay * 2^(attempt-1)
        exp_delay = self.config.base_delay * (2 ** (attempt - 1))
        
        # Cap at max_delay
        delay = min(exp_delay, self.config.max_delay)
        
        # Add jitter (0.9 to 1.1 multiplier)
        jitter = random.uniform(0.9, 1.1)
        
        return delay * jitter
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if we should retry based on the error.
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number
            
        Returns:
            True if we should retry
        """
        if attempt >= self.config.max_attempts:
            return False
        
        # Check for HTTP status codes
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in self.config.retry_on_status
        
        # Retry on connection errors
        if isinstance(error, (httpx.ConnectError, httpx.TimeoutException)):
            return True
        
        # Retry on specific exception types
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        
        return False
    
    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        on_retry: Optional[Callable[[RetryState], None]] = None,
        **kwargs: Any,
    ) -> T:
        """Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            on_retry: Optional callback called before each retry
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of func
            
        Raises:
            The last exception if all retries fail
        """
        state = RetryState(attempt=0, last_error=None, last_status_code=None, total_delay=0)
        
        while True:
            state.attempt += 1
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                state.last_error = e
                
                # Extract status code if available
                if isinstance(e, httpx.HTTPStatusError):
                    state.last_status_code = e.response.status_code
                
                # Check if we should retry
                if not self.should_retry(e, state.attempt):
                    raise
                
                # Calculate and apply delay
                delay = self.calculate_delay(state.attempt)
                state.total_delay += delay
                
                # Call retry callback
                if on_retry:
                    on_retry(state)
                
                time.sleep(delay)


def with_retry(config: RetryConfig) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic to a function.
    
    Args:
        config: Retry configuration
        
    Returns:
        Decorator function
    """
    handler = RetryHandler(config)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return handler.execute(func, *args, **kwargs)
        return wrapper
    return decorator
