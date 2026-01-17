"""Session management for SuperAgent."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from superagent.config.models import AgentConfig


@dataclass
class TokenUsage:
    """Token usage tracking."""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    def add(self, other: "TokenUsage") -> None:
        """Add usage from another TokenUsage instance."""
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_tokens += other.cached_tokens


@dataclass
class Message:
    """A message in the conversation history."""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    name: Optional[str] = None  # For tool messages
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to API format."""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        
        if self.name:
            msg["name"] = self.name
        
        return msg


@dataclass
class Session:
    """Manages the state of an agent session."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: AgentConfig = field(default_factory=AgentConfig)
    cwd: Path = field(default_factory=Path.cwd)
    
    # Conversation history
    messages: list[Message] = field(default_factory=list)
    
    # Token usage
    usage: TokenUsage = field(default_factory=TokenUsage)
    
    # Iteration tracking
    iteration: int = 0
    
    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Status
    is_done: bool = False
    final_message: Optional[str] = None
    
    def add_system_message(self, content: str) -> None:
        """Add a system message."""
        self.messages.append(Message(role="system", content=content))
        self._update_activity()
    
    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.messages.append(Message(role="user", content=content))
        self._update_activity()
    
    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Add an assistant message."""
        self.messages.append(Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        ))
        self._update_activity()
    
    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """Add a tool result message."""
        self.messages.append(Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        ))
        self._update_activity()
    
    def get_messages_for_api(self) -> list[dict[str, Any]]:
        """Get messages formatted for the API."""
        return [msg.to_dict() for msg in self.messages]
    
    def update_usage(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> None:
        """Update token usage."""
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens
        self.usage.cached_tokens += cached_tokens
    
    def increment_iteration(self) -> bool:
        """Increment iteration and check if we should continue.
        
        Returns:
            True if we can continue, False if max iterations reached
        """
        self.iteration += 1
        return self.iteration < self.config.max_iterations
    
    def mark_done(self, final_message: Optional[str] = None) -> None:
        """Mark the session as done."""
        self.is_done = True
        self.final_message = final_message
        self._update_activity()
    
    def _update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.started_at).total_seconds()
