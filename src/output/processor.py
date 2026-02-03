"""Output processor for SuperAgent - handles JSON and human-readable output."""

from __future__ import annotations

import json
import sys
from typing import Any, Optional, TextIO

from rich.console import Console
from rich.panel import Panel

from src.config.models import AgentConfig, OutputMode
from src.core.session import Session
from src.output.events import Event
from src.tools.base import ToolResult


class OutputProcessor:
    """Processes and formats agent output."""

    def __init__(
        self,
        config: AgentConfig,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
    ):
        """Initialize the output processor.

        Args:
            config: Agent configuration
            stdout: Standard output stream
            stderr: Standard error stream
        """
        self.config = config
        self.stdout = stdout
        self.stderr = stderr

        # Rich console for human-readable output
        self.console = Console(
            file=stderr,
            force_terminal=config.output.colors,
            no_color=not config.output.colors,
        )

        # JSON mode outputs to stdout
        self.json_mode = config.output.mode == OutputMode.JSON

    def emit(self, event: Event) -> None:
        """Emit an event.

        Args:
            event: Event to emit
        """
        if self.json_mode:
            self._emit_json(event)
        else:
            self._emit_human(event)

    def _emit_json(self, event: Event) -> None:
        """Emit event as JSON line to stdout."""
        line = json.dumps(event.to_dict())
        print(line, file=self.stdout, flush=True)

    def _emit_human(self, event: Event) -> None:
        """Emit event in human-readable format to stderr."""
        from src.output.events import EventType

        if event.type == EventType.TURN_STARTED:
            self.console.print("[dim]Session started[/dim]")

        elif event.type == EventType.TURN_COMPLETED:
            usage = event.data.get("usage", {})
            self.console.print()
            self.console.print(
                f"[dim]Tokens: {usage.get('input_tokens', 0)} in / "
                f"{usage.get('output_tokens', 0)} out "
                f"(cached: {usage.get('cached_tokens', 0)})[/dim]"
            )

        elif event.type == EventType.MESSAGE:
            content = event.data.get("content", "")
            if content:
                self.console.print()
                self.console.print(Panel(content, border_style="blue"))

        elif event.type == EventType.THINKING:
            self.console.print("[dim]Thinking...[/dim]", end="\r")

        elif event.type == EventType.TOOL_CALL_START:
            name = event.data.get("name", "unknown")
            self.console.print(f"[yellow]> {name}[/yellow]")

        elif event.type == EventType.TOOL_CALL_END:
            name = event.data.get("name", "unknown")
            success = event.data.get("success", False)
            output = event.data.get("output", "")

            status = "[green]OK[/green]" if success else "[red]FAILED[/red]"
            self.console.print(f"[dim]  {status}[/dim]")

            # Show truncated output
            if output:
                lines = output.split("\n")
                if len(lines) > 10:
                    display = "\n".join(lines[:5] + ["...", f"({len(lines) - 5} more lines)"])
                else:
                    display = output
                self.console.print(f"[dim]{display}[/dim]")

        elif event.type == EventType.ERROR:
            message = event.data.get("message", "Unknown error")
            self.console.print(f"[red]Error: {message}[/red]")

    # Convenience methods

    def emit_turn_started(self, session: Session) -> None:
        """Emit turn started event."""
        self.emit(Event.turn_started(session.id))

    def emit_turn_completed(self, session: Session, final_message: str) -> None:
        """Emit turn completed event."""
        self.emit(
            Event.turn_completed(
                session_id=session.id,
                final_message=final_message,
                input_tokens=session.usage.input_tokens,
                output_tokens=session.usage.output_tokens,
                cached_tokens=session.usage.cached_tokens,
            )
        )

    def emit_message(self, content: str, role: str = "assistant") -> None:
        """Emit a message event."""
        self.emit(Event.message(content, role))

    def emit_assistant_message(self, content: str) -> None:
        """Emit an assistant message."""
        self.emit(Event.message(content, "assistant"))

    def emit_thinking(self) -> None:
        """Emit a thinking event."""
        self.emit(Event.thinking())

    def emit_tool_call_start(self, name: str, arguments: dict[str, Any]) -> None:
        """Emit tool call start event."""
        self.emit(Event.tool_call_start(name, arguments))

    def emit_tool_call_end(self, name: str, result: ToolResult) -> None:
        """Emit tool call end event."""
        self.emit(
            Event.tool_call_end(
                name=name,
                success=result.success,
                output=result.output,
                error=result.error,
            )
        )

    def emit_error(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        """Emit an error event."""
        self.emit(Event.error(message, details))

    def print_final(self, message: str) -> None:
        """Print the final message to stdout."""
        if self.json_mode:
            # In JSON mode, final message is part of turn.completed event
            pass
        else:
            # In human mode, print to stdout
            print(message, file=self.stdout)
