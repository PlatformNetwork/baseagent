"""LLM Client for SuperAgent - wraps the term_sdk or uses direct HTTP."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generator, Optional

import httpx

from src.config.models import AgentConfig, Provider
from src.api.retry import RetryHandler


# Try to import term_sdk if available
try:
    # Add SDK path if needed
    sdk_path = Path(__file__).parent.parent.parent.parent.parent / "term-challenge" / "sdk" / "python"
    if sdk_path.exists() and str(sdk_path) not in sys.path:
        sys.path.insert(0, str(sdk_path))
    
    from term_sdk import LLM as TermLLM, Tool
    HAS_TERM_SDK = True
except ImportError:
    HAS_TERM_SDK = False
    TermLLM = None
    Tool = None


@dataclass
class FunctionCall:
    """Represents a function/tool call from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]
    
    @classmethod
    def from_openai(cls, call: dict[str, Any]) -> "FunctionCall":
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
    
    @classmethod
    def from_anthropic(cls, content: dict[str, Any]) -> "FunctionCall":
        """Parse from Anthropic tool_use format."""
        return cls(
            id=content.get("id", ""),
            name=content.get("name", ""),
            arguments=content.get("input", {}),
        )


@dataclass
class LLMResponse:
    """Response from the LLM."""
    text: str = ""
    function_calls: list[FunctionCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    model: str = ""
    finish_reason: str = ""
    raw: Optional[dict[str, Any]] = None
    
    @property
    def has_function_calls(self) -> bool:
        """Check if response contains function calls."""
        return len(self.function_calls) > 0
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


class LLMClient:
    """LLM Client with retry, streaming, and prompt caching support."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.retry_handler = RetryHandler(config.retry)
        self._http_client: Optional[httpx.Client] = None
        self._term_llm: Optional[Any] = None
        self._seen_content_hashes: set[str] = set()
        
        # Initialize appropriate client
        if HAS_TERM_SDK and config.provider == Provider.OPENROUTER:
            self._init_term_sdk()
        else:
            self._init_http_client()
    
    def _init_term_sdk(self) -> None:
        """Initialize term_sdk LLM client."""
        if not HAS_TERM_SDK:
            raise RuntimeError("term_sdk not available")
        
        self._term_llm = TermLLM(
            provider="openrouter",
            timeout=self.config.timeout,
        )
    
    def _init_http_client(self) -> None:
        """Initialize HTTP client for direct API calls."""
        self._http_client = httpx.Client(
            timeout=httpx.Timeout(self.config.timeout),
            headers={
                "Authorization": f"Bearer {self.config.get_api_key()}",
                "Content-Type": "application/json",
            },
        )
    
    def _get_model_name(self) -> str:
        """Get the model name for the API."""
        model = self.config.model
        
        # For OpenRouter, model names may already include provider prefix
        if self.config.provider == Provider.OPENROUTER:
            return model
        
        # For direct providers, strip provider prefix if present
        if "/" in model:
            return model.split("/", 1)[1]
        
        return model
    
    def _supports_temperature(self, model: str) -> bool:
        """Check if the model supports the temperature parameter.
        
        Reasoning models like o1, o3, deepseek-r1 don't support temperature.
        """
        model_lower = model.lower()
        # OpenAI reasoning models
        if model_lower.startswith("o1") or model_lower.startswith("o3"):
            return False
        if "/o1" in model_lower or "/o3" in model_lower:
            return False
        # DeepSeek reasoning models
        if "deepseek-r1" in model_lower or "deepseek/deepseek-r1" in model_lower:
            return False
        return True
    
    def _build_tools_json(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build tools JSON for the API."""
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
    
    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse API response to LLMResponse."""
        response = LLMResponse(raw=data)
        
        # Parse usage
        usage = data.get("usage", {})
        response.input_tokens = usage.get("prompt_tokens", 0)
        response.output_tokens = usage.get("completion_tokens", 0)
        
        # Check for cached tokens
        prompt_details = usage.get("prompt_tokens_details", {})
        response.cached_tokens = prompt_details.get("cached_tokens", 0)
        
        # Parse model
        response.model = data.get("model", self.config.model)
        
        # Parse choices
        choices = data.get("choices", [])
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            response.finish_reason = choice.get("finish_reason", "")
            
            # Text content
            response.text = message.get("content") or ""
            
            # Function calls
            tool_calls = message.get("tool_calls", [])
            for call in tool_calls:
                if call.get("type") == "function":
                    response.function_calls.append(FunctionCall.from_openai(call))
        
        return response
    
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        on_retry: Optional[Callable[[Any], None]] = None,
    ) -> LLMResponse:
        """Send a chat request to the LLM.
        
        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tools/functions
            on_retry: Optional callback for retry events
            
        Returns:
            LLMResponse with text and/or function calls
        """
        # Use term_sdk if available
        if self._term_llm is not None:
            return self._chat_with_term_sdk(messages, tools)
        
        # Otherwise use direct HTTP
        return self._chat_with_http(messages, tools, on_retry)
    
    def _chat_with_term_sdk(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Chat using term_sdk."""
        if self._term_llm is None:
            raise RuntimeError("term_sdk not initialized")
        
        # Convert tools to term_sdk format
        sdk_tools = None
        if tools:
            sdk_tools = [
                Tool(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {}),
                )
                for t in tools
            ]
        
        # Build kwargs for the call
        model_name = self._get_model_name()
        chat_kwargs: dict[str, Any] = {
            "messages": messages,
            "model": model_name,
            "tools": sdk_tools,
            "max_tokens": self.config.max_tokens,
        }
        
        # Only add temperature if the model supports it
        if self._supports_temperature(model_name):
            chat_kwargs["temperature"] = self.config.temperature
        
        # Make the call
        response = self._term_llm.chat(**chat_kwargs)
        
        # Convert to our response format
        # term_sdk returns tokens as int (total), try to get details from raw
        input_tokens = 0
        output_tokens = 0
        if response.raw and isinstance(response.raw, dict):
            usage = response.raw.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        if input_tokens == 0 and output_tokens == 0:
            # Fallback: use total tokens as input estimate
            total = response.tokens if isinstance(response.tokens, int) else 0
            input_tokens = total
        
        result = LLMResponse(
            text=response.text or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.config.model,
        )
        
        # Parse function calls
        if response.function_calls:
            for call in response.function_calls:
                result.function_calls.append(FunctionCall(
                    id=call.id or "",
                    name=call.name,
                    arguments=call.arguments if isinstance(call.arguments, dict) else {},
                ))
        
        return result
    
    def _chat_with_http(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        on_retry: Optional[Callable[[Any], None]] = None,
    ) -> LLMResponse:
        """Chat using direct HTTP client."""
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")
        
        # Build request body (messages already have cache_control from loop.py)
        model_name = self._get_model_name()
        body: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
        }
        
        # Only add temperature if the model supports it
        if self._supports_temperature(model_name):
            body["temperature"] = self.config.temperature
        
        if tools:
            body["tools"] = self._build_tools_json(tools)
            body["tool_choice"] = "auto"
        
        # Make request with retry
        def do_request() -> dict[str, Any]:
            url = f"{self.config.get_base_url()}/chat/completions"
            response = self._http_client.post(url, json=body)  # type: ignore
            response.raise_for_status()
            return response.json()
        
        data = self.retry_handler.execute(do_request, on_retry=on_retry)
        return self._parse_response(data)
    
    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> Generator[str, None, LLMResponse]:
        """Stream a chat response.
        
        Args:
            messages: List of messages
            tools: Optional list of tools
            on_chunk: Optional callback for each text chunk
            
        Yields:
            Text chunks
            
        Returns:
            Final LLMResponse with complete text and usage
        """
        # For now, use non-streaming and yield the full response
        # TODO: Implement proper SSE streaming
        response = self.chat(messages, tools)
        
        if response.text:
            if on_chunk:
                on_chunk(response.text)
            yield response.text
        
        return response
    
    def close(self) -> None:
        """Close the client and release resources."""
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None
