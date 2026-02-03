"""Write file tool for SuperAgent."""

from __future__ import annotations

from typing import Any

from .base import BaseTool, ToolMetadata, ToolResult


class WriteFileTool(BaseTool):
    """Tool to write content to a file."""

    name = "write_file"
    description = "Write content to a file, creating parent directories if needed"

    def execute(self, file_path: str, content: str, **kwargs: Any) -> ToolResult:
        """Write content to a file.

        Args:
            file_path: Path to the file to write
            content: Content to write to the file

        Returns:
            ToolResult with write status and metadata
        """
        import time

        start_time = time.time()

        resolved_path = self.resolve_path(file_path)

        try:
            # Create parent directories if they don't exist
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the content
            resolved_path.write_text(content, encoding="utf-8")

            # Get file stats
            file_size = resolved_path.stat().st_size

            # Create content preview (max 500 chars)
            content_preview = content[:500]
            if len(content) > 500:
                content_preview += "..."

            duration_ms = int((time.time() - start_time) * 1000)
            metadata = ToolMetadata(
                duration_ms=duration_ms,
                files_modified=[str(resolved_path)],
                data={
                    "path": str(resolved_path),
                    "filename": resolved_path.name,
                    "extension": resolved_path.suffix,
                    "size": file_size,
                    "content_preview": content_preview,
                },
            )

            result = ToolResult.ok(f"Successfully wrote {file_size} bytes to {file_path}")
            return result.with_metadata(metadata)

        except PermissionError:
            return ToolResult.fail(f"Permission denied: {file_path}")
        except Exception as e:
            return ToolResult.fail(f"Error writing file: {e}")

    @classmethod
    def get_spec(cls) -> dict[str, Any]:
        """Get the tool specification for the LLM."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to write"},
                    "content": {"type": "string", "description": "Content to write to the file"},
                },
                "required": ["file_path", "content"],
            },
        }
