"""
Apply patch tool for SuperAgent - Complete unified diff parser and applier.

Matches fabric-core/src/tools/handlers/apply_patch.rs implementation.
Supports both standard unified diff format AND custom *** Begin Patch format.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Tuple

from src.tools.base import BaseTool, ToolResult


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class HunkLine:
    """A single line in a hunk."""
    type: str  # "context", "add", "remove"
    content: str


@dataclass
class Hunk:
    """A parsed hunk from a unified diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[HunkLine] = field(default_factory=list)


@dataclass
class FileChange:
    """A file change from a unified diff."""
    old_path: Optional[Path]
    new_path: Optional[Path]
    hunks: List[Hunk] = field(default_factory=list)
    is_new_file: bool = False
    is_deleted: bool = False
    is_rename: bool = False


# =============================================================================
# Unified Diff Parser (matches fabric-core)
# =============================================================================

def parse_file_path(path_str: str) -> Optional[Path]:
    """Parse a file path from diff header.
    
    Handles formats: a/path, b/path, or just path
    """
    path = path_str.strip()
    
    # Remove a/ or b/ prefix
    if path.startswith("a/"):
        path = path[2:]
    elif path.startswith("b/"):
        path = path[2:]
    
    # Remove timestamp if present (e.g., "file.txt\t2024-01-01 00:00:00")
    path = path.split("\t")[0].strip()
    
    if path == "/dev/null":
        return Path("/dev/null")
    
    return Path(path) if path else None


def parse_hunk_header(line: str) -> Optional[Hunk]:
    """Parse a hunk header like '@@ -1,5 +1,6 @@'.
    
    Returns Hunk with start/count info but empty lines.
    """
    # Strip @@ markers
    line = line.strip("@").strip()
    parts = line.split()
    
    if len(parts) < 2:
        return None
    
    def parse_range(s: str) -> Tuple[int, int]:
        """Parse range like '1,5' or '1' into (start, count)."""
        s = s.lstrip("-+")
        if "," in s:
            parts = s.split(",")
            return int(parts[0]), int(parts[1])
        return int(s), 1
    
    try:
        old_start, old_count = parse_range(parts[0])
        new_start, new_count = parse_range(parts[1])
        return Hunk(
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
        )
    except (ValueError, IndexError):
        return None


def parse_unified_diff(patch: str) -> List[FileChange]:
    """Parse a unified diff into file changes.
    
    Matches fabric-core parse_unified_diff() implementation.
    """
    file_changes: List[FileChange] = []
    current_change: Optional[FileChange] = None
    current_hunk: Optional[Hunk] = None
    
    lines = patch.splitlines()
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Detect file header: --- a/path
        if line.startswith("--- "):
            # Save previous change
            if current_change is not None:
                if current_hunk is not None:
                    current_change.hunks.append(current_hunk)
                    current_hunk = None
                file_changes.append(current_change)
            
            old_path = parse_file_path(line[4:])
            
            # Look for +++ line
            if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                new_path = parse_file_path(lines[i + 1][4:])
                
                is_new_file = old_path is not None and str(old_path) == "/dev/null"
                is_deleted = new_path is not None and str(new_path) == "/dev/null"
                
                current_change = FileChange(
                    old_path=None if is_new_file else old_path,
                    new_path=None if is_deleted else new_path,
                    is_new_file=is_new_file,
                    is_deleted=is_deleted,
                )
                i += 2
                continue
        
        # Detect hunk header: @@ -1,5 +1,6 @@
        if line.startswith("@@ "):
            # Save previous hunk
            if current_change is not None and current_hunk is not None:
                current_change.hunks.append(current_hunk)
            
            current_hunk = parse_hunk_header(line)
            i += 1
            continue
        
        # Parse hunk lines
        if current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk.lines.append(HunkLine("add", line[1:]))
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk.lines.append(HunkLine("remove", line[1:]))
            elif line.startswith(" ") or line == "":
                content = line[1:] if line.startswith(" ") else ""
                current_hunk.lines.append(HunkLine("context", content))
            elif line.startswith("\\"):
                # "\ No newline at end of file" - ignore
                pass
        
        i += 1
    
    # Save final change and hunk
    if current_change is not None:
        if current_hunk is not None:
            current_change.hunks.append(current_hunk)
        file_changes.append(current_change)
    
    return file_changes


# =============================================================================
# Hunk Application (matches fabric-core with fuzzy matching)
# =============================================================================

def matches_at_position(lines: List[str], match_lines: List[str], start: int) -> bool:
    """Check if lines match at a given position (with whitespace tolerance)."""
    if start + len(match_lines) > len(lines):
        return False
    
    for i, expected in enumerate(match_lines):
        if lines[start + i].strip() != expected.strip():
            return False
    
    return True


def find_hunk_position(
    lines: List[str],
    hunk: Hunk,
    suggested_start: int,
) -> int:
    """Find the best position to apply a hunk, with fuzzy matching.
    
    Matches fabric-core find_hunk_position() - searches ±50 lines.
    """
    # Extract context and remove lines for matching
    match_lines = [
        hl.content for hl in hunk.lines
        if hl.type in ("context", "remove")
    ]
    
    if not match_lines:
        return suggested_start
    
    # Try exact position first
    if matches_at_position(lines, match_lines, suggested_start):
        return suggested_start
    
    # Search nearby positions (within 50 lines)
    for offset in range(1, 51):
        # Try before
        if suggested_start >= offset:
            pos = suggested_start - offset
            if matches_at_position(lines, match_lines, pos):
                return pos
        
        # Try after
        pos = suggested_start + offset
        if pos < len(lines) and matches_at_position(lines, match_lines, pos):
            return pos
    
    # If we can't find a match but position is valid, use it anyway
    if suggested_start <= len(lines):
        return suggested_start
    
    raise ValueError(f"Could not find matching context for hunk at line {hunk.old_start}")


def apply_hunks_to_lines(
    original_lines: List[str],
    hunks: List[Hunk],
) -> str:
    """Apply hunks to existing lines.
    
    Applies hunks in reverse order to maintain line numbers.
    """
    result_lines = list(original_lines)
    
    # Apply in reverse order
    for hunk in reversed(hunks):
        start_idx = hunk.old_start - 1 if hunk.old_start > 0 else 0
        
        # Find actual position
        actual_start = find_hunk_position(result_lines, hunk, start_idx)
        
        # Count lines to remove
        lines_to_remove = sum(
            1 for hl in hunk.lines
            if hl.type in ("remove", "context")
        )
        
        # Build replacement
        replacement = [
            hl.content for hl in hunk.lines
            if hl.type in ("add", "context")
        ]
        
        # Apply replacement
        end_idx = min(actual_start + lines_to_remove, len(result_lines))
        result_lines = result_lines[:actual_start] + replacement + result_lines[end_idx:]
    
    # Join with newlines
    content = "\n".join(result_lines)
    if content and not content.endswith("\n"):
        content += "\n"
    
    return content


def build_new_content(hunks: List[Hunk]) -> str:
    """Build content for a new file from hunks."""
    lines = []
    for hunk in hunks:
        for hl in hunk.lines:
            if hl.type in ("add", "context"):
                lines.append(hl.content)
    
    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    return content


# =============================================================================
# File Change Application
# =============================================================================

def apply_file_change(
    change: FileChange,
    cwd: Path,
    dry_run: bool = False,
) -> str:
    """Apply a single file change."""
    
    # Handle deletion
    if change.is_deleted and change.old_path:
        full_path = cwd / change.old_path
        if not dry_run:
            full_path.unlink()
        return f"  D {change.old_path}"
    
    # Get target path
    target_path = change.new_path or change.old_path
    if not target_path:
        raise ValueError("No file path specified")
    
    full_path = cwd / target_path
    
    # Handle new file
    if change.is_new_file:
        content = build_new_content(change.hunks)
        if not dry_run:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
        return f"  A {target_path}"
    
    # Handle modification
    original_content = full_path.read_text(encoding="utf-8")
    original_lines = original_content.splitlines()
    
    new_content = apply_hunks_to_lines(original_lines, change.hunks)
    
    if not dry_run:
        full_path.write_text(new_content, encoding="utf-8")
    
    return f"  M {target_path}"


def apply_unified_diff(
    patch: str,
    cwd: Path,
    dry_run: bool = False,
) -> str:
    """Apply a unified diff to the filesystem.
    
    Main entry point matching fabric-core apply_unified_diff().
    """
    file_changes = parse_unified_diff(patch)
    
    if not file_changes:
        return "No changes to apply"
    
    report = []
    modified_files = []
    
    for change in file_changes:
        result = apply_file_change(change, cwd, dry_run)
        report.append(result)
        if change.new_path:
            modified_files.append(str(change.new_path))
    
    action = "Would apply" if dry_run else "Applied"
    return f"{action} changes to {len(modified_files)} file(s):\n" + "\n".join(report)


# =============================================================================
# Legacy Format Support (*** Begin Patch)
# =============================================================================

def parse_legacy_patch(patch: str) -> List[FileChange]:
    """Parse legacy *** Begin Patch format."""
    file_changes: List[FileChange] = []
    
    # Extract content between markers
    match = re.search(r"\*\*\* Begin Patch\s*\n(.*?)\*\*\* End Patch", patch, re.DOTALL)
    if not match:
        return []
    
    content = match.group(1)
    
    # Split into file operations
    file_pattern = r"\*\*\* (Add|Delete|Update) File: (.+?)(?=\n\*\*\* (?:Add|Delete|Update)|$)"
    
    for file_match in re.finditer(file_pattern, content, re.DOTALL):
        op_type = file_match.group(1).lower()
        file_path = file_match.group(2).strip()
        
        # Get content after header
        start = file_match.end()
        remaining = content[start:]
        next_file = re.search(r"\*\*\* (?:Add|Delete|Update) File:", remaining)
        file_content = remaining[:next_file.start()] if next_file else remaining
        
        if op_type == "add":
            change = FileChange(
                old_path=None,
                new_path=Path(file_path),
                is_new_file=True,
            )
            # Parse added lines
            hunk = Hunk(old_start=0, old_count=0, new_start=1, new_count=0)
            for line in file_content.splitlines():
                if line.startswith("+"):
                    hunk.lines.append(HunkLine("add", line[1:]))
                elif line.strip() and not line.startswith("***"):
                    hunk.lines.append(HunkLine("add", line))
            if hunk.lines:
                change.hunks.append(hunk)
            file_changes.append(change)
            
        elif op_type == "delete":
            file_changes.append(FileChange(
                old_path=Path(file_path),
                new_path=None,
                is_deleted=True,
            ))
            
        elif op_type == "update":
            change = FileChange(
                old_path=Path(file_path),
                new_path=Path(file_path),
            )
            # Parse hunks
            current_hunk: Optional[Hunk] = None
            for line in file_content.splitlines():
                if line.startswith("@@"):
                    if current_hunk:
                        change.hunks.append(current_hunk)
                    # Simple hunk header
                    current_hunk = Hunk(old_start=1, old_count=0, new_start=1, new_count=0)
                elif line.startswith("-") and current_hunk:
                    current_hunk.lines.append(HunkLine("remove", line[1:]))
                elif line.startswith("+") and current_hunk:
                    current_hunk.lines.append(HunkLine("add", line[1:]))
                elif line.startswith(" ") and current_hunk:
                    current_hunk.lines.append(HunkLine("context", line[1:]))
            if current_hunk:
                change.hunks.append(current_hunk)
            file_changes.append(change)
    
    return file_changes


# =============================================================================
# Tool Implementation
# =============================================================================

class ApplyPatchTool(BaseTool):
    """Tool for applying file patches.
    
    Supports both standard unified diff format and legacy *** Begin Patch format.
    """
    
    name = "apply_patch"
    description = "Applies file patches using unified diff or custom format."
    
    def execute(self, **kwargs: Any) -> ToolResult:
        """Apply a patch.
        
        Args:
            **kwargs: Tool arguments
                - patch: The patch content (unified diff or *** Begin Patch format)
                - dry_run: If True, don't actually modify files
            
        Returns:
            ToolResult with success/failure info
        """
        # Extract parameters from kwargs
        patch: str = kwargs.get("patch", "")
        dry_run: bool = kwargs.get("dry_run", False)
        
        if not patch:
            return ToolResult.fail("Missing required parameter: patch")
        
        try:
            # Detect format and parse
            if "*** Begin Patch" in patch:
                # Legacy format
                file_changes = parse_legacy_patch(patch)
                if not file_changes:
                    return ToolResult.fail("No valid operations in patch")
                
                report = []
                for change in file_changes:
                    result = apply_file_change(change, self.cwd, dry_run)
                    report.append(result)
                
                action = "Would apply" if dry_run else "Applied"
                return ToolResult.ok(f"{action} changes:\n" + "\n".join(report))
            
            elif "---" in patch and "+++" in patch:
                # Standard unified diff
                result = apply_unified_diff(patch, self.cwd, dry_run)
                return ToolResult.ok(result)
            
            else:
                return ToolResult.fail(
                    "Invalid patch format. Use unified diff (--- / +++) "
                    "or custom format (*** Begin Patch)"
                )
        
        except FileNotFoundError as e:
            return ToolResult.fail(f"File not found: {e}")
        except PermissionError as e:
            return ToolResult.fail(f"Permission denied: {e}")
        except Exception as e:
            return ToolResult.fail(f"Failed to apply patch: {e}")
