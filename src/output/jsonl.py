"""
JSONL output format matching Codex exec --json.

Emits events to stdout in JSONL format for machine consumption.
All events follow the exact same structure as Codex CLI.

Event Types:
- thread.started: New thread/session started
- turn.started: Turn (request/response cycle) started
- turn.completed: Turn completed with usage stats
- turn.failed: Turn failed with error
- item.started: Item (tool call, message) started
- item.updated: Item updated (e.g., todo list)
- item.completed: Item completed
- error: Fatal error
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# =============================================================================
# Thread Events
# =============================================================================


@dataclass
class ThreadStartedEvent:
    """Emitted when a new thread/session is started."""

    thread_id: str
    type: str = field(default="thread.started", init=False)


# =============================================================================
# Turn Events
# =============================================================================


@dataclass
class TurnStartedEvent:
    """Emitted when a turn is started (user sends message)."""

    type: str = field(default="turn.started", init=False)


@dataclass
class Usage:
    """Token usage statistics."""

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TurnCompletedEvent:
    """Emitted when a turn is completed successfully."""

    usage: Dict[str, int]
    type: str = field(default="turn.completed", init=False)


@dataclass
class TurnFailedEvent:
    """Emitted when a turn fails."""

    error: Dict[str, str]
    type: str = field(default="turn.failed", init=False)


# =============================================================================
# Item Events
# =============================================================================


@dataclass
class ItemStartedEvent:
    """Emitted when an item starts processing."""

    item: Dict[str, Any]
    type: str = field(default="item.started", init=False)


@dataclass
class ItemUpdatedEvent:
    """Emitted when an item is updated (e.g., todo list)."""

    item: Dict[str, Any]
    type: str = field(default="item.updated", init=False)


@dataclass
class ItemCompletedEvent:
    """Emitted when an item completes processing."""

    item: Dict[str, Any]
    type: str = field(default="item.completed", init=False)


# =============================================================================
# Error Events
# =============================================================================


@dataclass
class ErrorEvent:
    """Emitted for fatal errors."""

    message: str
    type: str = field(default="error", init=False)


# =============================================================================
# Item Types (for item.started/completed payloads)
# =============================================================================


def make_agent_message_item(item_id: str, text: str) -> Dict[str, Any]:
    """Create an agent_message item."""
    return {
        "id": item_id,
        "type": "agent_message",
        "text": text,
    }


def make_reasoning_item(item_id: str, text: str) -> Dict[str, Any]:
    """Create a reasoning item."""
    return {
        "id": item_id,
        "type": "reasoning",
        "text": text,
    }


def make_command_execution_item(
    item_id: str,
    command: str,
    status: str = "in_progress",
    aggregated_output: str = "",
    exit_code: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a command_execution item."""
    item = {
        "id": item_id,
        "type": "command_execution",
        "command": command,
        "status": status,
        "aggregated_output": aggregated_output,
    }
    if exit_code is not None:
        item["exit_code"] = exit_code
    return item


def make_file_change_item(
    item_id: str,
    changes: List[Dict[str, str]],
    status: str = "completed",
) -> Dict[str, Any]:
    """Create a file_change item."""
    return {
        "id": item_id,
        "type": "file_change",
        "changes": changes,
        "status": status,
    }


def make_todo_list_item(
    item_id: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create a todo_list item."""
    return {
        "id": item_id,
        "type": "todo_list",
        "items": items,
    }


def make_error_item(item_id: str, message: str) -> Dict[str, Any]:
    """Create an error item."""
    return {
        "id": item_id,
        "type": "error",
        "message": message,
    }


# =============================================================================
# Emitter
# =============================================================================

_item_counter = 0


def next_item_id() -> str:
    """Generate the next item ID."""
    global _item_counter
    _item_counter += 1
    return f"item_{_item_counter}"


def reset_item_counter() -> None:
    """Reset the item counter (for testing)."""
    global _item_counter
    _item_counter = 0


def emit(event) -> None:
    """
    Emit a single JSONL event to stdout.

    Args:
        event: Dataclass event to emit
    """
    try:
        data = asdict(event)
        line = json.dumps(data, ensure_ascii=False)
        print(line, flush=True)
    except Exception as e:
        # Fallback: emit error event
        error_data = {"type": "error", "message": f"Failed to emit event: {e}"}
        print(json.dumps(error_data), flush=True)


def emit_raw(data: Dict[str, Any]) -> None:
    """
    Emit a raw dictionary as JSONL.

    Args:
        data: Dictionary to emit
    """
    try:
        line = json.dumps(data, ensure_ascii=False)
        print(line, flush=True)
    except Exception as e:
        error_data = {"type": "error", "message": f"Failed to emit: {e}"}
        print(json.dumps(error_data), flush=True)
