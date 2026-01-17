"""Search files tool for SuperAgent."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any, Optional, List

from .base import BaseTool, ToolResult, ToolMetadata


class SearchFilesTool(BaseTool):
    """Tool to search for files using glob patterns."""
    
    name = "search_files"
    description = "Search for files matching a glob pattern"
    
    # Default directories to skip
    DEFAULT_SKIP_DIRS = {".git", "node_modules", "target", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}
    
    def execute(
        self,
        pattern: str,
        path: str = ".",
        content_pattern: Optional[str] = None,
        **kwargs: Any
    ) -> ToolResult:
        """Search for files matching a pattern.
        
        Args:
            pattern: Glob pattern to match files (e.g., "*.py", "**/*.js")
            path: Base path to search from
            content_pattern: Optional regex pattern to match file contents
            
        Returns:
            ToolResult with list of matching file paths
        """
        import time
        import re
        start_time = time.time()
        
        resolved_path = self.resolve_path(path)
        
        if not resolved_path.exists():
            return ToolResult.fail(f"Path not found: {path}")
        
        if not resolved_path.is_dir():
            return ToolResult.fail(f"Not a directory: {path}")
        
        # Compile content pattern if provided
        content_regex = None
        if content_pattern:
            try:
                content_regex = re.compile(content_pattern)
            except re.error as e:
                return ToolResult.fail(f"Invalid content pattern: {e}")
        
        matches = []
        
        try:
            # Walk the directory tree
            for root, dirs, files in os.walk(resolved_path):
                # Skip hidden directories and default skip dirs
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d not in self.DEFAULT_SKIP_DIRS
                ]
                
                root_path = Path(root)
                
                for filename in files:
                    # Skip hidden files
                    if filename.startswith("."):
                        continue
                    
                    file_path = root_path / filename
                    relative_path = file_path.relative_to(resolved_path)
                    
                    # Check glob pattern match
                    if not self._match_glob(str(relative_path), pattern):
                        continue
                    
                    # Check content pattern if provided
                    if content_regex:
                        if not self._match_content(file_path, content_regex):
                            continue
                    
                    matches.append(str(relative_path))
            
            # Sort matches
            matches.sort()
            
            if not matches:
                output = f"No files found matching pattern '{pattern}'"
            else:
                output = "\n".join(matches)
            
            duration_ms = int((time.time() - start_time) * 1000)
            metadata = ToolMetadata(
                duration_ms=duration_ms,
                data={
                    "pattern": pattern,
                    "base_path": str(resolved_path),
                    "matches": matches,
                    "count": len(matches),
                }
            )
            
            result = ToolResult.ok(output)
            return result.with_metadata(metadata)
            
        except PermissionError:
            return ToolResult.fail(f"Permission denied while searching: {path}")
        except Exception as e:
            return ToolResult.fail(f"Error searching files: {e}")
    
    def _match_glob(self, filepath: str, pattern: str) -> bool:
        """Match a filepath against a glob pattern.
        
        Supports:
        - * matches any characters except path separator
        - ? matches exactly one character
        - ** matches any characters including path separator
        """
        # Normalize path separators
        filepath = filepath.replace("\\", "/")
        pattern = pattern.replace("\\", "/")
        
        # Handle ** pattern (recursive matching)
        if "**" in pattern:
            # Split pattern at **
            parts = pattern.split("**")
            if len(parts) == 2:
                prefix, suffix = parts
                prefix = prefix.rstrip("/")
                suffix = suffix.lstrip("/")
                
                # Check prefix if it exists
                if prefix and not filepath.startswith(prefix):
                    return False
                
                # Check suffix against any part of the path
                if suffix:
                    return fnmatch.fnmatch(filepath, f"*{suffix}")
                return True
        
        # Simple glob matching for * and ?
        return fnmatch.fnmatch(filepath, pattern)
    
    def _match_content(self, file_path: Path, regex: Any) -> bool:
        """Check if file content matches the regex pattern."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            return bool(regex.search(content))
        except Exception:
            return False
    
    @classmethod
    def get_spec(cls) -> dict[str, Any]:
        """Get the tool specification for the LLM."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files (e.g., '*.py', '**/*.js')"
                    },
                    "path": {
                        "type": "string",
                        "description": "Base path to search from",
                        "default": "."
                    },
                    "content_pattern": {
                        "type": "string",
                        "description": "Optional regex pattern to match file contents"
                    }
                },
                "required": ["pattern"]
            }
        }
