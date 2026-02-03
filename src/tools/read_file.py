"""Read file tool for SuperAgent."""

from __future__ import annotations

from typing import Any, Optional

from .base import BaseTool, ToolMetadata, ToolResult


class ReadFileTool(BaseTool):
    """Tool to read file contents with line numbers."""

    name = "read_file"
    description = "Read the contents of a file with line numbers"

    def execute(
        self, file_path: str, offset: int = 0, limit: Optional[int] = None, **kwargs: Any
    ) -> ToolResult:
        """Read file contents.

        Args:
            file_path: Path to the file to read
            offset: Line offset to start from (0-based)
            limit: Maximum number of lines to read (None for all)

        Returns:
            ToolResult with file contents and metadata
        """
        import time

        start_time = time.time()

        resolved_path = self.resolve_path(file_path)

        if not resolved_path.exists():
            return ToolResult.fail(f"File not found: {file_path}")

        if not resolved_path.is_file():
            return ToolResult.fail(f"Not a file: {file_path}")

        try:
            content = resolved_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try reading as binary for non-text files
            try:
                content = resolved_path.read_bytes().decode("latin-1")
            except Exception as e:
                return ToolResult.fail(f"Cannot read file: {e}")
        except Exception as e:
            return ToolResult.fail(f"Error reading file: {e}")

        lines = content.splitlines()
        total_lines = len(lines)

        # Handle empty file
        if total_lines == 0 or (total_lines == 1 and lines[0] == ""):
            duration_ms = int((time.time() - start_time) * 1000)
            metadata = ToolMetadata(
                duration_ms=duration_ms,
                data={
                    "path": str(resolved_path),
                    "filename": resolved_path.name,
                    "extension": resolved_path.suffix,
                    "size": resolved_path.stat().st_size,
                    "total_lines": 0,
                    "shown_lines": 0,
                    "offset": offset,
                    "truncated": False,
                    "empty": True,
                },
            )
            result = ToolResult.ok("(empty file)")
            return result.with_metadata(metadata)

        # Apply offset and limit
        if offset >= total_lines:
            return ToolResult.fail(f"Offset {offset} exceeds total lines {total_lines}")

        end_index = total_lines
        if limit is not None:
            end_index = min(offset + limit, total_lines)

        selected_lines = lines[offset:end_index]
        shown_lines = len(selected_lines)
        truncated = end_index < total_lines

        # Format with line numbers
        formatted_lines = []
        for i, line in enumerate(selected_lines, start=offset + 1):
            formatted_lines.append(f"L{i}: {line}")

        output = "\n".join(formatted_lines)

        duration_ms = int((time.time() - start_time) * 1000)
        metadata = ToolMetadata(
            duration_ms=duration_ms,
            data={
                "path": str(resolved_path),
                "filename": resolved_path.name,
                "extension": resolved_path.suffix,
                "size": resolved_path.stat().st_size,
                "total_lines": total_lines,
                "shown_lines": shown_lines,
                "offset": offset,
                "truncated": truncated,
                "empty": False,
            },
        )

        result = ToolResult.ok(output)
        return result.with_metadata(metadata)

    @classmethod
    def get_spec(cls) -> dict[str, Any]:
        """Get the tool specification for the LLM."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to read"},
                    "offset": {
                        "type": "integer",
                        "description": "Line offset to start from (0-based)",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (optional)",
                    },
                },
                "required": ["file_path"],
            },
        }
