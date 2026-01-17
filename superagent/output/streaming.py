"""
Streaming module for processing LLM output streams.

This module provides classes for handling streaming responses from language models,
including text deltas, tool calls, and token usage tracking.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Callable, Any
import time
import asyncio
from collections import deque


class StreamState(Enum):
    """State of the stream processor."""
    IDLE = auto()
    STREAMING_TEXT = auto()
    STREAMING_TOOL_CALL = auto()
    COMPLETE = auto()
    ERROR = auto()


@dataclass
class StreamEvent:
    """Base class for stream events."""
    pass


@dataclass
class StartEvent(StreamEvent):
    """Event indicating stream start."""
    pass


@dataclass 
class TextDeltaEvent(StreamEvent):
    """Event containing a text delta."""
    delta: str


@dataclass
class ToolCallStartEvent(StreamEvent):
    """Event indicating start of a tool call."""
    id: str
    name: str


@dataclass
class ToolCallDeltaEvent(StreamEvent):
    """Event containing tool call argument delta."""
    id: str
    arguments: str


@dataclass
class ToolCallCompleteEvent(StreamEvent):
    """Event indicating tool call completion."""
    id: str


@dataclass
class TokenUsageEvent(StreamEvent):
    """Event containing token usage information."""
    prompt: int
    completion: int


@dataclass
class CompleteEvent(StreamEvent):
    """Event indicating stream completion."""
    pass


@dataclass
class ErrorEvent(StreamEvent):
    """Event indicating an error occurred."""
    message: str


@dataclass
class TokenCounts:
    """Token usage counts for prompt and completion."""
    prompt: int = 0
    completion: int = 0
    
    def total(self) -> int:
        """Return total token count."""
        return self.prompt + self.completion


@dataclass
class StreamToolCall:
    """Represents a tool call being streamed."""
    id: str
    name: str
    arguments: str = ""
    complete: bool = False
    
    def parse_arguments(self) -> Optional[dict]:
        """Parse arguments as JSON if complete."""
        if self.complete:
            import json
            try:
                return json.loads(self.arguments)
            except:
                return None
        return None


@dataclass
class StreamContent:
    """Accumulated content from a stream."""
    text: str = ""
    tool_calls: List[StreamToolCall] = field(default_factory=list)
    tokens: TokenCounts = field(default_factory=TokenCounts)
    
    def append_text(self, delta: str):
        """Append text delta to content."""
        self.text += delta
    
    def start_tool_call(self, id: str, name: str):
        """Start a new tool call."""
        self.tool_calls.append(StreamToolCall(id=id, name=name))
    
    def append_tool_call(self, id: str, arguments: str):
        """Append arguments to an existing tool call."""
        for tc in self.tool_calls:
            if tc.id == id:
                tc.arguments += arguments
                break
    
    def complete_tool_call(self, id: str):
        """Mark a tool call as complete."""
        for tc in self.tool_calls:
            if tc.id == id:
                tc.complete = True
                break
    
    def has_content(self) -> bool:
        """Check if any content has been accumulated."""
        return bool(self.text) or bool(self.tool_calls)


@dataclass
class StreamStats:
    """Statistics about a stream."""
    state: StreamState
    event_count: int
    text_length: int
    tool_call_count: int
    time_to_first_token: Optional[float]
    total_time: Optional[float]
    tokens: TokenCounts


class StreamProcessor:
    """Process stream events and accumulate content."""
    
    def __init__(self):
        self.state = StreamState.IDLE
        self.content = StreamContent()
        self.buffer: deque = deque()
        self.start_time: Optional[float] = None
        self.first_token_time: Optional[float] = None
        self.last_event_time: Optional[float] = None
        self.event_count = 0
    
    def process(self, event: StreamEvent):
        """Process a stream event."""
        now = time.time()
        
        if self.start_time is None:
            self.start_time = now
        
        self.last_event_time = now
        self.event_count += 1
        
        if isinstance(event, StartEvent):
            self.state = StreamState.STREAMING_TEXT
        
        elif isinstance(event, TextDeltaEvent):
            if self.first_token_time is None:
                self.first_token_time = now
            self.content.append_text(event.delta)
            self.state = StreamState.STREAMING_TEXT
        
        elif isinstance(event, ToolCallStartEvent):
            self.content.start_tool_call(event.id, event.name)
            self.state = StreamState.STREAMING_TOOL_CALL
        
        elif isinstance(event, ToolCallDeltaEvent):
            self.content.append_tool_call(event.id, event.arguments)
        
        elif isinstance(event, ToolCallCompleteEvent):
            self.content.complete_tool_call(event.id)
        
        elif isinstance(event, TokenUsageEvent):
            self.content.tokens.prompt = event.prompt
            self.content.tokens.completion = event.completion
        
        elif isinstance(event, CompleteEvent):
            self.state = StreamState.COMPLETE
        
        elif isinstance(event, ErrorEvent):
            self.state = StreamState.ERROR
        
        self.buffer.append(event)
    
    def time_to_first_token(self) -> Optional[float]:
        """Get time to first token in seconds."""
        if self.start_time and self.first_token_time:
            return self.first_token_time - self.start_time
        return None
    
    def elapsed(self) -> Optional[float]:
        """Get elapsed time since stream start."""
        if self.start_time:
            return time.time() - self.start_time
        return None
    
    def is_complete(self) -> bool:
        """Check if stream is complete or errored."""
        return self.state in (StreamState.COMPLETE, StreamState.ERROR)
    
    def drain_events(self) -> List[StreamEvent]:
        """Drain and return all buffered events."""
        events = list(self.buffer)
        self.buffer.clear()
        return events
    
    def stats(self) -> StreamStats:
        """Get current stream statistics."""
        return StreamStats(
            state=self.state,
            event_count=self.event_count,
            text_length=len(self.content.text),
            tool_call_count=len(self.content.tool_calls),
            time_to_first_token=self.time_to_first_token(),
            total_time=self.elapsed(),
            tokens=self.content.tokens,
        )


class StreamBuffer:
    """Buffer for rate limiting output."""
    
    def __init__(self, min_interval: float = 0.01):
        self.buffer = ""
        self.min_interval = min_interval
        self.last_flush = time.time()
    
    def push(self, text: str):
        """Push text to buffer."""
        self.buffer += text
    
    def flush_if_ready(self) -> Optional[str]:
        """Flush buffer if minimum interval has passed."""
        if time.time() - self.last_flush >= self.min_interval and self.buffer:
            self.last_flush = time.time()
            result = self.buffer
            self.buffer = ""
            return result
        return None
    
    def flush(self) -> str:
        """Force flush all buffered content."""
        self.last_flush = time.time()
        result = self.buffer
        self.buffer = ""
        return result
    
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return not self.buffer


class WordBuffer:
    """Buffer for word-boundary aligned output."""
    
    def __init__(self, min_words: int = 3):
        self.buffer = ""
        self.min_words = min_words
    
    def push(self, text: str):
        """Push text to buffer."""
        self.buffer += text
    
    def flush_words(self) -> Optional[str]:
        """Flush complete words if minimum word count reached."""
        word_count = len(self.buffer.split())
        if word_count >= self.min_words:
            # Find last whitespace
            pos = self.buffer.rfind(' ')
            if pos > 0:
                result = self.buffer[:pos+1]
                self.buffer = self.buffer[pos+1:]
                return result
        return None
    
    def flush(self) -> str:
        """Force flush all buffered content."""
        result = self.buffer
        self.buffer = ""
        return result


class SentenceBuffer:
    """Buffer for sentence-boundary aligned output."""
    
    def __init__(self):
        self.buffer = ""
    
    def push(self, text: str):
        """Push text to buffer."""
        self.buffer += text
    
    def flush_sentences(self) -> Optional[str]:
        """Flush complete sentences."""
        endings = [". ", "! ", "? ", ".\n", "!\n", "?\n"]
        last_end = 0
        
        for ending in endings:
            pos = self.buffer.rfind(ending)
            if pos >= 0:
                end = pos + len(ending)
                if end > last_end:
                    last_end = end
        
        if last_end > 0:
            result = self.buffer[:last_end]
            self.buffer = self.buffer[last_end:]
            return result
        return None
    
    def flush(self) -> str:
        """Force flush all buffered content."""
        result = self.buffer
        self.buffer = ""
        return result


class StreamCollector:
    """Collect all stream content."""
    
    def __init__(self):
        self.processor = StreamProcessor()
    
    def process(self, event: StreamEvent):
        """Process a stream event."""
        self.processor.process(event)
    
    def is_complete(self) -> bool:
        """Check if stream is complete."""
        return self.processor.is_complete()
    
    def result(self) -> dict:
        """Get collected results."""
        return {
            "text": self.processor.content.text,
            "tool_calls": self.processor.content.tool_calls,
            "tokens": self.processor.content.tokens,
            "stats": self.processor.stats(),
        }
