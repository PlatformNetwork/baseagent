"""LLM Client supporting Chutes API and litellm providers.

Supports:
- Chutes API (https://llm.chutes.ai/v1) with Kimi K2.5-TEE
- OpenRouter and other litellm-compatible providers (fallback)

Chutes API:
- OpenAI-compatible endpoint
- Requires CHUTES_API_TOKEN environment variable
- Default model: moonshotai/Kimi-K2.5-TEE

Kimi K2.5 Best Practices:
- Thinking mode: temperature=1.0, top_p=0.95
- Instant mode: temperature=0.6, top_p=0.95
- Context window: 256K tokens
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Chutes API configuration
CHUTES_API_BASE = "https://llm.chutes.ai/v1"
CHUTES_DEFAULT_MODEL = "moonshotai/Kimi-K2.5-TEE"

# Kimi K2.5 recommended parameters
KIMI_K25_THINKING_PARAMS = {
    "temperature": 1.0,  # Use 1.0 for thinking mode
    "top_p": 0.95,
}

KIMI_K25_INSTANT_PARAMS = {
    "temperature": 0.6,  # Use 0.6 for instant mode
    "top_p": 0.95,
}


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
    thinking: str = ""  # Thinking/reasoning content (for models supporting thinking mode)
    function_calls: List[FunctionCall] = field(default_factory=list)
    tokens: Optional[Dict[str, int]] = None
    model: str = ""
    finish_reason: str = ""
    raw: Optional[Dict[str, Any]] = None
    cost: float = 0.0
    
    def has_function_calls(self) -> bool:
        """Check if response contains function calls."""
        return len(self.function_calls) > 0


class ChutesClient:
    """LLM Client for Chutes API with Kimi K2.5-TEE.
    
    Chutes API is OpenAI-compatible, hosted at https://llm.chutes.ai/v1
    Default model: moonshotai/Kimi-K2.5-TEE with thinking mode enabled.
    
    Environment variable: CHUTES_API_TOKEN
    
    Kimi K2.5 parameters:
    - Thinking mode: temperature=1.0, top_p=0.95
    - Instant mode: temperature=0.6, top_p=0.95
    - Context window: 256K tokens
    """
    
    def __init__(
        self,
        model: str = CHUTES_DEFAULT_MODEL,
        temperature: Optional[float] = None,
        max_tokens: int = 16384,
        cost_limit: Optional[float] = None,
        enable_thinking: bool = True,
        # Legacy params (kept for compatibility)
        cache_extended_retention: bool = True,
        cache_key: Optional[str] = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.cost_limit = cost_limit or float(os.environ.get("LLM_COST_LIMIT", "100.0"))
        self.enable_thinking = enable_thinking
        
        # Set temperature based on thinking mode if not explicitly provided
        if temperature is None:
            params = KIMI_K25_THINKING_PARAMS if enable_thinking else KIMI_K25_INSTANT_PARAMS
            self.temperature = params["temperature"]
        else:
            self.temperature = temperature
        
        self._total_cost = 0.0
        self._total_tokens = 0
        self._request_count = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cached_tokens = 0
        
        # Get API token
        self._api_token = os.environ.get("CHUTES_API_TOKEN")
        if not self._api_token:
            raise LLMError(
                "CHUTES_API_TOKEN environment variable not set. "
                "Get your API token at https://chutes.ai",
                code="authentication_error"
            )
        
        # Import and configure OpenAI client for Chutes API
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_token,
                base_url=CHUTES_API_BASE,
            )
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")
    
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
    
    def _parse_thinking_content(self, text: str) -> Tuple[str, str]:
        """Parse thinking content from response.
        
        Kimi K2.5 can return thinking content in:
        1. <think>...</think> tags (for some deployments)
        2. reasoning_content field (official API)
        
        Returns (thinking_content, final_response).
        """
        if not text:
            return "", ""
        
        # Check for <think>...</think> pattern
        think_pattern = r"<think>(.*?)</think>"
        match = re.search(think_pattern, text, re.DOTALL)
        
        if match:
            thinking = match.group(1).strip()
            # Remove the think block from the response
            response = re.sub(think_pattern, "", text, flags=re.DOTALL).strip()
            return thinking, response
        
        return "", text
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Send a chat request to Chutes API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions
            max_tokens: Max tokens to generate (default: self.max_tokens)
            extra_body: Additional parameters to pass to the API
            temperature: Override temperature (default: self.temperature)
            
        Returns:
            LLMResponse with text, thinking content, and any tool calls
        """
        # Check cost limit
        if self._total_cost >= self.cost_limit:
            raise CostLimitExceeded(
                f"Cost limit exceeded: ${self._total_cost:.4f} >= ${self.cost_limit:.4f}",
                used=self._total_cost,
                limit=self.cost_limit,
            )
        
        # Use provided temperature or default
        temp = temperature if temperature is not None else self.temperature
        
        # Get appropriate params based on thinking mode
        params = KIMI_K25_THINKING_PARAMS if self.enable_thinking else KIMI_K25_INSTANT_PARAMS
        
        # Build request kwargs
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temp,
            "top_p": params["top_p"],
        }
        
        if tools:
            kwargs["tools"] = self._build_tools(tools)
            kwargs["tool_choice"] = "auto"
        
        # Add extra body params
        if extra_body:
            kwargs.update(extra_body)
        
        try:
            response = self._client.chat.completions.create(**kwargs)
            self._request_count += 1
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
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
        
        # Estimate cost (Kimi K2.5 pricing via Chutes - approximate)
        # $0.60 per million input tokens, $2.50 per million output tokens
        input_cost_per_1k = 0.0006  # $0.60 / 1000
        output_cost_per_1k = 0.0025  # $2.50 / 1000
        if result.tokens:
            cost = (result.tokens["input"] / 1000 * input_cost_per_1k +
                    result.tokens["output"] / 1000 * output_cost_per_1k)
            self._total_cost += cost
            result.cost = cost
        
        # Extract model
        result.model = getattr(response, "model", self.model)
        
        # Extract choices
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            message = choice.message
            
            result.finish_reason = getattr(choice, "finish_reason", "") or ""
            raw_text = getattr(message, "content", "") or ""
            
            # Extract reasoning_content if available (official Kimi API)
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                result.thinking = message.reasoning_content
                result.text = raw_text
            elif self.enable_thinking:
                # Parse thinking content from <think> tags
                result.thinking, result.text = self._parse_thinking_content(raw_text)
            else:
                result.text = raw_text
            
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
        """Close client."""
        if hasattr(self, "_client"):
            self._client.close()


class LiteLLMClient:
    """LLM Client using litellm (fallback for non-Chutes providers)."""
    
    def __init__(
        self,
        model: str,
        temperature: Optional[float] = None,
        max_tokens: int = 16384,
        cost_limit: Optional[float] = None,
        # Legacy params for compatibility
        enable_thinking: bool = False,
        cache_extended_retention: bool = True,
        cache_key: Optional[str] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cost_limit = cost_limit or float(os.environ.get("LLM_COST_LIMIT", "10.0"))
        self.enable_thinking = enable_thinking
        
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
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Send a chat request."""
        # Check cost limit
        if self._total_cost >= self.cost_limit:
            raise CostLimitExceeded(
                f"Cost limit exceeded: ${self._total_cost:.4f} >= ${self.cost_limit:.4f}",
                used=self._total_cost,
                limit=self.cost_limit,
            )
        
        # Use provided temperature or default
        temp = temperature if temperature is not None else self.temperature
        
        # Build request
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
        }
        
        if self._supports_temperature(self.model) and temp is not None:
            kwargs["temperature"] = temp
        
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
            result.cost = cost
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


def get_llm_client(
    provider: str = "chutes",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 16384,
    cost_limit: Optional[float] = None,
    enable_thinking: bool = True,
    **kwargs,
):
    """Factory function to get appropriate LLM client based on provider.
    
    Args:
        provider: "chutes" for Chutes API, "openrouter" or others for litellm
        model: Model name (default depends on provider)
        temperature: Temperature setting (default based on thinking mode)
        max_tokens: Max tokens to generate
        cost_limit: Cost limit in USD
        enable_thinking: Enable thinking mode (for Chutes/Kimi K2.5)
        **kwargs: Additional arguments passed to client
        
    Returns:
        ChutesClient or LiteLLMClient instance
    """
    if provider == "chutes":
        return ChutesClient(
            model=model or CHUTES_DEFAULT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            cost_limit=cost_limit,
            enable_thinking=enable_thinking,
            **kwargs,
        )
    else:
        return LiteLLMClient(
            model=model or "openrouter/anthropic/claude-sonnet-4-20250514",
            temperature=temperature,
            max_tokens=max_tokens,
            cost_limit=cost_limit,
            enable_thinking=enable_thinking,
            **kwargs,
        )
