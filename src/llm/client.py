"""LLM Client using litellm - replaces term_sdk dependency."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class CostLimitExceeded(Exception):
    """Raised when cost limit is exceeded."""
    def __init__(self, message: str, used: float = 0, limit: float = 0):
        super().__init__(message)
        self.used = used
        self.limit = limit


class LLMError(Exception):
    """LLM API error."""
    def __init__(self, message: str, code: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class FunctionCall:
    """Represents a function/tool call from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]
    
    @classmethod
    def from_openai(cls, call: Dict[str, Any]) -> "FunctionCall":
        """Parse from OpenAI tool_calls format."""
        func = call.get("function", {})
        args_str = func.get("arguments", "{}")
        
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {"raw": args_str}
        
        return cls(
            id=call.get("id", ""),
            name=func.get("name", ""),
            arguments=args,
        )


@dataclass
class LLMResponse:
    """Response from the LLM."""
    text: str = ""
    function_calls: List[FunctionCall] = field(default_factory=list)
    tokens: Optional[Dict[str, int]] = None
    model: str = ""
    finish_reason: str = ""
    raw: Optional[Dict[str, Any]] = None
    
    def has_function_calls(self) -> bool:
        """Check if response contains function calls."""
        return len(self.function_calls) > 0


class LiteLLMClient:
    """LLM Client using litellm."""
    
    def __init__(
        self,
        model: str,
        temperature: Optional[float] = None,
        max_tokens: int = 16384,
        cost_limit: Optional[float] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cost_limit = cost_limit or float(os.environ.get("LLM_COST_LIMIT", "10.0"))
        
        self._total_cost = 0.0
        self._total_tokens = 0
        self._request_count = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cached_tokens = 0
        
        # Import litellm
        try:
            import litellm
            self._litellm = litellm
            # Configure litellm
            litellm.drop_params = True  # Drop unsupported params silently
        except ImportError:
            raise ImportError("litellm not installed. Run: pip install litellm")
    
    def _supports_temperature(self, model: str) -> bool:
        """Check if model supports temperature parameter."""
        model_lower = model.lower()
        # Reasoning models don't support temperature
        if any(x in model_lower for x in ["o1", "o3", "deepseek-r1"]):
            return False
        return True
    
    def _build_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """Build tools in OpenAI format."""
        if not tools:
            return None
        
        result = []
        for tool in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            })
        return result
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Send a chat request."""
        # Check cost limit
        if self._total_cost >= self.cost_limit:
            raise CostLimitExceeded(
                f"Cost limit exceeded: ${self._total_cost:.4f} >= ${self.cost_limit:.4f}",
                used=self._total_cost,
                limit=self.cost_limit,
            )
        
        # Build request
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
        }
        
        if self._supports_temperature(self.model) and self.temperature is not None:
            kwargs["temperature"] = self.temperature
        
        if tools:
            kwargs["tools"] = self._build_tools(tools)
            kwargs["tool_choice"] = "auto"
        
        # Add extra body params (like reasoning effort)
        if extra_body:
            kwargs.update(extra_body)
        
        try:
            response = self._litellm.completion(**kwargs)
            self._request_count += 1
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                raise LLMError(error_msg, code="authentication_error")
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                raise LLMError(error_msg, code="rate_limit")
            else:
                raise LLMError(error_msg, code="api_error")
        
        # Parse response
        result = LLMResponse(raw=response.model_dump() if hasattr(response, "model_dump") else None)
        
        # Extract usage
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0
            cached_tokens = 0
            
            # Check for cached tokens
            if hasattr(usage, "prompt_tokens_details"):
                details = usage.prompt_tokens_details
                if details and hasattr(details, "cached_tokens"):
                    cached_tokens = details.cached_tokens or 0
            
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._cached_tokens += cached_tokens
            self._total_tokens += input_tokens + output_tokens
            
            result.tokens = {
                "input": input_tokens,
                "output": output_tokens,
                "cached": cached_tokens,
            }
        
        # Calculate cost using litellm
        try:
            cost = self._litellm.completion_cost(completion_response=response)
            self._total_cost += cost
        except Exception:
            pass  # Cost calculation may fail for some models
        
        # Extract model
        result.model = getattr(response, "model", self.model)
        
        # Extract choices
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            message = choice.message
            
            result.finish_reason = getattr(choice, "finish_reason", "") or ""
            result.text = getattr(message, "content", "") or ""
            
            # Extract function calls
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                for call in tool_calls:
                    if hasattr(call, "function"):
                        func = call.function
                        args_str = getattr(func, "arguments", "{}")
                        try:
                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except json.JSONDecodeError:
                            args = {"raw": args_str}
                        
                        result.function_calls.append(FunctionCall(
                            id=getattr(call, "id", "") or "",
                            name=getattr(func, "name", "") or "",
                            arguments=args if isinstance(args, dict) else {},
                        ))
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_tokens": self._total_tokens,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "cached_tokens": self._cached_tokens,
            "total_cost": self._total_cost,
            "request_count": self._request_count,
        }
    
    def close(self):
        """Close client (no-op for litellm)."""
        pass
