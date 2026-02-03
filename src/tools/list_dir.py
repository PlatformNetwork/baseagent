"""List directory tool for SuperAgent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from .base import BaseTool, ToolMetadata, ToolResult


class ListDirTool(BaseTool):
    """Tool to list directory contents."""

    name = "list_dir"
    description = "List the contents of a directory"

    def execute(
        self,
        directory_path: str = ".",
        recursive: bool = False,
        include_hidden: bool = False,
        ignore_patterns: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """List directory contents.

        Args:
            directory_path: Path to the directory to list
            recursive: Whether to list recursively
            include_hidden: Whether to include hidden files/directories
            ignore_patterns: List of patterns to ignore

        Returns:
            ToolResult with directory listing and metadata
        """
        import time

        start_time = time.time()

        resolved_path = self.resolve_path(directory_path)

        if not resolved_path.exists():
            return ToolResult.fail(f"Directory not found: {directory_path}")

        if not resolved_path.is_dir():
            return ToolResult.fail(f"Not a directory: {directory_path}")

        ignore_patterns = ignore_patterns or []
        entries = []
        output_lines = []

        try:
            if recursive:
                items = self._list_recursive(resolved_path, include_hidden, ignore_patterns)
            else:
                items = self._list_flat(resolved_path, include_hidden, ignore_patterns)

            for item_path, item_type, item_size in sorted(
                items, key=lambda x: (x[1] != "dir", x[0].lower())
            ):
                if item_type == "dir":
                    output_lines.append(f"dir {item_path}")
                else:
                    output_lines.append(f"file {item_path}")

                entries.append(
                    {
                        "name": item_path,
                        "type": item_type,
                        "size": item_size,
                    }
                )

            if not entries:
                output = (
                    f"Directory '{directory_path}' is empty (no files or subdirectories found)."
                )
            else:
                output = "\n".join(output_lines)

            duration_ms = int((time.time() - start_time) * 1000)
            metadata = ToolMetadata(
                duration_ms=duration_ms,
                data={
                    "path": str(resolved_path),
                    "entries": entries,
                },
            )

            result = ToolResult.ok(output)
            return result.with_metadata(metadata)

        except PermissionError:
            return ToolResult.fail(f"Permission denied: {directory_path}")
        except Exception as e:
            return ToolResult.fail(f"Error listing directory: {e}")

    def _should_ignore(self, name: str, include_hidden: bool, ignore_patterns: List[str]) -> bool:
        """Check if a file/directory should be ignored."""
        # Check hidden files
        if not include_hidden and name.startswith("."):
            return True

        # Check ignore patterns (simple glob matching)
        for pattern in ignore_patterns:
            if self._match_pattern(name, pattern):
                return True

        return False

    def _match_pattern(self, name: str, pattern: str) -> bool:
        """Simple glob pattern matching with * and ?."""
        import fnmatch

        return fnmatch.fnmatch(name, pattern)

    def _list_flat(
        self, path: Path, include_hidden: bool, ignore_patterns: List[str]
    ) -> List[tuple[str, str, int]]:
        """List directory contents non-recursively."""
        items = []

        for entry in path.iterdir():
            if self._should_ignore(entry.name, include_hidden, ignore_patterns):
                continue

            item_type = "dir" if entry.is_dir() else "file"
            item_size = 0 if entry.is_dir() else entry.stat().st_size
            items.append((entry.name, item_type, item_size))

        return items

    def _list_recursive(
        self, path: Path, include_hidden: bool, ignore_patterns: List[str], prefix: str = ""
    ) -> List[tuple[str, str, int]]:
        """List directory contents recursively."""
        items = []

        for entry in path.iterdir():
            if self._should_ignore(entry.name, include_hidden, ignore_patterns):
                continue

            relative_name = f"{prefix}{entry.name}" if prefix else entry.name
            item_type = "dir" if entry.is_dir() else "file"
            item_size = 0 if entry.is_dir() else entry.stat().st_size
            items.append((relative_name, item_type, item_size))

            if entry.is_dir():
                # Recurse into subdirectory
                sub_items = self._list_recursive(
                    entry, include_hidden, ignore_patterns, prefix=f"{relative_name}/"
                )
                items.extend(sub_items)

        return items

    @classmethod
    def get_spec(cls) -> dict[str, Any]:
        """Get the tool specification for the LLM."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Path to the directory to list",
                        "default": ".",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list recursively",
                        "default": False,
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files/directories",
                        "default": False,
                    },
                    "ignore_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of patterns to ignore",
                    },
                },
                "required": [],
            },
        }
