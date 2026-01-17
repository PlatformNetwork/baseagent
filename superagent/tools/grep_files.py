"""Grep files tool for SuperAgent."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from superagent.tools.base import BaseTool, ToolResult


class GrepFilesTool(BaseTool):
    """Tool for searching file contents using patterns."""
    
    name = "grep_files"
    description = "Finds files whose contents match the pattern."
    
    # Default limits
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 2000
    TIMEOUT_SECONDS = 30
    
    def execute(
        self,
        pattern: str,
        include: Optional[str] = None,
        path: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> ToolResult:
        """Search for files matching a pattern.
        
        Args:
            pattern: Regex pattern to search for
            include: Glob pattern to filter files
            path: Directory to search in
            limit: Maximum number of results
            
        Returns:
            ToolResult with matching file paths
        """
        # Resolve search path
        search_path = self.resolve_path(path) if path else self.cwd
        
        if not search_path.exists():
            return ToolResult.fail(f"Path not found: {search_path}")
        
        # Cap limit
        limit = min(limit, self.MAX_LIMIT)
        
        # Try ripgrep first (fastest)
        rg_result = self._search_with_ripgrep(pattern, include, search_path, limit)
        if rg_result is not None:
            return rg_result
        
        # Fallback to Python implementation
        return self._search_with_python(pattern, include, search_path, limit)
    
    def _search_with_ripgrep(
        self,
        pattern: str,
        include: Optional[str],
        search_path: Path,
        limit: int,
    ) -> Optional[ToolResult]:
        """Search using ripgrep (rg).
        
        Returns None if ripgrep is not available.
        """
        cmd = ["rg", "--files-with-matches", "--no-heading"]
        
        if include:
            # Convert glob to rg glob format
            cmd.extend(["--glob", include])
        
        cmd.extend([pattern, str(search_path)])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_SECONDS,
            )
            
            if result.returncode == 0:
                files = result.stdout.strip().split("\n") if result.stdout.strip() else []
                files = files[:limit]
                
                if not files:
                    return ToolResult.ok("No matching files found.")
                
                output = f"Found {len(files)} matching files:\n" + "\n".join(files)
                return ToolResult.ok(output, data={"count": len(files), "files": files})
            
            elif result.returncode == 1:
                # No matches
                return ToolResult.ok("No matching files found.")
            
            elif result.returncode == 2:
                # Error - might be bad pattern
                return ToolResult.fail(f"Search error: {result.stderr.strip()}")
            
            return None  # Try fallback
            
        except FileNotFoundError:
            return None  # rg not installed, use fallback
        except subprocess.TimeoutExpired:
            return ToolResult.fail(f"Search timed out after {self.TIMEOUT_SECONDS}s")
        except Exception:
            return None  # Use fallback
    
    def _search_with_python(
        self,
        pattern: str,
        include: Optional[str],
        search_path: Path,
        limit: int,
    ) -> ToolResult:
        """Fallback Python implementation for searching."""
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult.fail(f"Invalid regex pattern: {e}")
        
        matching_files: list[str] = []
        errors: list[str] = []
        
        # Convert include glob to regex if provided
        include_regex = None
        if include:
            # Simple glob to regex conversion
            include_pattern = include.replace(".", r"\.").replace("*", ".*").replace("?", ".")
            if "{" in include_pattern:
                # Handle {a,b,c} patterns
                include_pattern = re.sub(
                    r"\{([^}]+)\}",
                    lambda m: f"({'|'.join(m.group(1).split(','))})",
                    include_pattern,
                )
            try:
                include_regex = re.compile(f"^{include_pattern}$", re.IGNORECASE)
            except re.error:
                pass
        
        def should_include(file_path: Path) -> bool:
            if include_regex is None:
                return True
            return include_regex.match(file_path.name) is not None
        
        def search_dir(dir_path: Path) -> None:
            if len(matching_files) >= limit:
                return
            
            try:
                for item in dir_path.iterdir():
                    if len(matching_files) >= limit:
                        return
                    
                    if item.is_file() and should_include(item):
                        try:
                            content = item.read_text(encoding="utf-8", errors="ignore")
                            if regex.search(content):
                                matching_files.append(str(item))
                        except (PermissionError, OSError):
                            pass
                    
                    elif item.is_dir() and not item.is_symlink():
                        # Skip hidden directories
                        if not item.name.startswith("."):
                            search_dir(item)
            
            except PermissionError:
                errors.append(f"Permission denied: {dir_path}")
        
        if search_path.is_file():
            try:
                content = search_path.read_text(encoding="utf-8", errors="ignore")
                if regex.search(content):
                    matching_files.append(str(search_path))
            except (PermissionError, OSError) as e:
                return ToolResult.fail(f"Cannot read file: {e}")
        else:
            search_dir(search_path)
        
        if not matching_files:
            return ToolResult.ok("No matching files found.")
        
        output = f"Found {len(matching_files)} matching files:\n" + "\n".join(matching_files)
        
        if errors:
            output += f"\n\nWarnings:\n" + "\n".join(errors[:5])
        
        return ToolResult.ok(output, data={"count": len(matching_files), "files": matching_files})
