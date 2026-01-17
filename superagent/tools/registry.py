"""Tool registry for SuperAgent - manages and dispatches tool calls."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from superagent.tools.base import ToolResult
from superagent.tools.specs import get_all_tools

if TYPE_CHECKING:
    from term_sdk import AgentContext


@dataclass
class ExecutorConfig:
    """Configuration for tool execution."""
    max_concurrent: int = 4
    default_timeout: float = 120.0
    cache_enabled: bool = True
    cache_ttl: float = 300.0  # 5 minutes


@dataclass
class CachedResult:
    """A cached tool result with timestamp."""
    result: ToolResult
    cached_at: float  # timestamp from time.time()
    
    def is_valid(self, ttl: float) -> bool:
        """Check if the cached result is still valid."""
        return (time.time() - self.cached_at) < ttl


@dataclass
class ToolStats:
    """Per-tool execution statistics."""
    executions: int = 0
    successes: int = 0
    total_ms: int = 0
    
    def success_rate(self) -> float:
        """Get the success rate for this tool."""
        if self.executions == 0:
            return 0.0
        return self.successes / self.executions
    
    def avg_ms(self) -> float:
        """Get average execution time in milliseconds."""
        if self.executions == 0:
            return 0.0
        return self.total_ms / self.executions


@dataclass
class ExecutorStats:
    """Aggregate execution statistics."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    cache_hits: int = 0
    total_duration_ms: int = 0
    by_tool: Dict[str, ToolStats] = field(default_factory=dict)
    
    def success_rate(self) -> float:
        """Get overall success rate."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    def cache_hit_rate(self) -> float:
        """Get cache hit rate."""
        if self.total_executions == 0:
            return 0.0
        return self.cache_hits / self.total_executions
    
    def avg_duration_ms(self) -> float:
        """Get average execution duration in milliseconds."""
        if self.total_executions == 0:
            return 0.0
        return self.total_duration_ms / self.total_executions


class ToolRegistry:
    """Registry for managing and dispatching tool calls.
    
    Adapted for term_sdk - tools now receive AgentContext for shell execution.
    Includes caching and execution statistics.
    """
    
    def __init__(
        self,
        cwd: Optional[Path] = None,
        config: Optional[ExecutorConfig] = None,
    ):
        """Initialize the registry.
        
        Args:
            cwd: Current working directory for tools (optional, can be set later)
            config: Executor configuration (optional, uses defaults)
        """
        self.cwd = cwd or Path("/app")
        self._plan: list[dict[str, str]] = []
        self._config = config or ExecutorConfig()
        self._cache: Dict[str, CachedResult] = {}
        self._stats = ExecutorStats()
    
    def execute(
        self,
        ctx: "AgentContext",
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool by name.
        
        Args:
            ctx: Agent context from term_sdk
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            ToolResult from the tool execution
        """
        start_time = time.time()
        
        # Check cache first if enabled
        if self._config.cache_enabled:
            cache_key = self._cache_key(name, arguments)
            cached = self._get_cached(cache_key)
            if cached is not None:
                duration_ms = int((time.time() - start_time) * 1000)
                self._record_execution(name, duration_ms, success=True, cached=True)
                return cached
        
        cwd = Path(ctx.cwd) if hasattr(ctx, 'cwd') else self.cwd
        
        try:
            if name == "shell_command":
                result = self._execute_shell(ctx, cwd, arguments)
            elif name == "read_file":
                result = self._execute_read_file(cwd, arguments)
            elif name == "write_file":
                result = self._execute_write_file(cwd, arguments)
            elif name == "list_dir":
                result = self._execute_list_dir(cwd, arguments)
            elif name == "grep_files":
                result = self._execute_grep(ctx, cwd, arguments)
            elif name == "apply_patch":
                result = self._execute_apply_patch(cwd, arguments)
            elif name == "view_image":
                result = self._execute_view_image(cwd, arguments)
            elif name == "update_plan":
                result = self._execute_update_plan(arguments)
            else:
                result = ToolResult.fail(f"Unknown tool: {name}")
                
        except Exception as e:
            result = ToolResult.fail(f"Tool {name} failed: {e}")
        
        # Record execution stats
        duration_ms = int((time.time() - start_time) * 1000)
        self._record_execution(name, duration_ms, success=result.success, cached=False)
        
        # Cache successful results
        if self._config.cache_enabled and result.success:
            cache_key = self._cache_key(name, arguments)
            self._cache_result(cache_key, result)
        
        return result
    
    def _execute_shell(
        self,
        ctx: "AgentContext",
        cwd: Path,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute shell command using subprocess directly."""
        command = args.get("command", "")
        workdir = args.get("workdir")
        timeout_ms = args.get("timeout_ms", 60000)
        
        if not command:
            return ToolResult.fail("No command provided")
        
        # Resolve working directory
        effective_cwd = cwd
        if workdir:
            wd = Path(workdir)
            effective_cwd = wd if wd.is_absolute() else cwd / wd
        
        timeout_sec = max(1, timeout_ms // 1000)
        
        try:
            result = subprocess.run(
                ["sh", "-c", command],
                cwd=str(effective_cwd),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n{result.stderr}"
            
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output.strip(),
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=f"Command timed out after {timeout_sec}s",
            )
        except Exception as e:
            return ToolResult.fail(str(e))
    
    def _execute_read_file(self, cwd: Path, args: dict[str, Any]) -> ToolResult:
        """Read file contents."""
        file_path = args.get("file_path", "")
        offset = args.get("offset", 1)
        limit = args.get("limit", 2000)
        
        if not file_path:
            return ToolResult.fail("No file_path provided")
        
        path = Path(file_path)
        if not path.is_absolute():
            path = cwd / path
        
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")
        
        if not path.is_file():
            return ToolResult.fail(f"Not a file: {path}")
        
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            
            # Apply offset and limit (1-indexed)
            start = max(0, offset - 1)
            end = start + limit
            selected = lines[start:end]
            
            # Format with line numbers
            output_lines = []
            for i, line in enumerate(selected, start=start + 1):
                output_lines.append(f"L{i}: {line.rstrip()}")
            
            output = "\n".join(output_lines)
            
            if len(lines) > end:
                output += f"\n\n[... {len(lines) - end} more lines ...]"
            
            return ToolResult.ok(output)
            
        except Exception as e:
            return ToolResult.fail(f"Failed to read file: {e}")
    
    def _execute_write_file(self, cwd: Path, args: dict[str, Any]) -> ToolResult:
        """Write content to a file."""
        file_path = args.get("file_path", "")
        content = args.get("content", "")
        
        if not file_path:
            return ToolResult.fail("No file_path provided")
        
        path = Path(file_path)
        if not path.is_absolute():
            path = cwd / path
        
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult.ok(f"Wrote {len(content)} bytes to {path}")
            
        except Exception as e:
            return ToolResult.fail(f"Failed to write file: {e}")
    
    def _execute_list_dir(self, cwd: Path, args: dict[str, Any]) -> ToolResult:
        """List directory contents."""
        dir_path = args.get("dir_path", ".")
        depth = args.get("depth", 2)
        limit = args.get("limit", 50)
        
        path = Path(dir_path)
        if not path.is_absolute():
            path = cwd / path
        
        if not path.exists():
            return ToolResult.fail(f"Directory not found: {path}")
        
        if not path.is_dir():
            return ToolResult.fail(f"Not a directory: {path}")
        
        try:
            entries = []
            self._list_recursive(path, path, entries, depth, limit)
            
            if not entries:
                return ToolResult.ok("(empty directory)")
            
            output = "\n".join(entries[:limit])
            if len(entries) > limit:
                output += f"\n\n[... {len(entries) - limit} more entries ...]"
            
            return ToolResult.ok(output)
            
        except Exception as e:
            return ToolResult.fail(f"Failed to list directory: {e}")
    
    def _list_recursive(
        self,
        base: Path,
        current: Path,
        entries: list,
        max_depth: int,
        max_entries: int,
        current_depth: int = 0,
    ) -> None:
        """Recursively list directory contents."""
        if current_depth > max_depth or len(entries) >= max_entries:
            return
        
        try:
            items = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for item in items:
                if len(entries) >= max_entries:
                    break
                
                rel_path = item.relative_to(base)
                
                if item.is_dir():
                    entries.append(f"{rel_path}/")
                    self._list_recursive(base, item, entries, max_depth, max_entries, current_depth + 1)
                elif item.is_symlink():
                    entries.append(f"{rel_path}@")
                else:
                    entries.append(str(rel_path))
                    
        except PermissionError:
            pass
    
    def _execute_grep(
        self,
        ctx: "AgentContext",
        cwd: Path,
        args: dict[str, Any],
    ) -> ToolResult:
        """Search files using ripgrep."""
        pattern = args.get("pattern", "")
        include = args.get("include", "")
        search_path = args.get("path", ".")
        limit = args.get("limit", 100)
        
        if not pattern:
            return ToolResult.fail("No pattern provided")
        
        # Build ripgrep command
        cmd_parts = ["rg", "-l", "--color=never"]
        
        if include:
            cmd_parts.extend(["-g", include])
        
        cmd_parts.append(pattern)
        cmd_parts.append(search_path)
        
        cmd = " ".join(f'"{p}"' if " " in p else p for p in cmd_parts)
        
        try:
            result = subprocess.run(
                ["sh", "-c", cmd],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            files = [f for f in result.stdout.strip().split("\n") if f]
            
            if not files:
                return ToolResult.ok("No matches found")
            
            output = "\n".join(files[:limit])
            if len(files) > limit:
                output += f"\n\n[... {len(files) - limit} more files ...]"
            
            return ToolResult.ok(output)
            
        except subprocess.TimeoutExpired:
            return ToolResult.fail("Search timed out")
        except Exception as e:
            return ToolResult.fail(f"Search failed: {e}")
    
    def _execute_apply_patch(self, cwd: Path, args: dict[str, Any]) -> ToolResult:
        """Apply a patch to files."""
        patch = args.get("patch", "")
        
        if not patch:
            return ToolResult.fail("No patch provided")
        
        from superagent.tools.apply_patch import ApplyPatchTool
        
        tool = ApplyPatchTool(cwd)
        return tool.execute(patch=patch)
    
    def _execute_view_image(self, cwd: Path, args: dict[str, Any]) -> ToolResult:
        """View an image file."""
        path = args.get("path", "")
        
        if not path:
            return ToolResult.fail("No path provided")
        
        from superagent.tools.view_image import view_image
        return view_image(path, cwd)
    
    def _execute_update_plan(self, args: dict[str, Any]) -> ToolResult:
        """Update the task plan."""
        steps = args.get("steps", [])
        explanation = args.get("explanation")
        
        self._plan = steps
        
        # Format plan for output
        lines = ["Plan updated:"]
        for i, step in enumerate(steps, 1):
            status_icon = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]",
            }.get(step.get("status", "pending"), "[ ]")
            lines.append(f"  {status_icon} {i}. {step.get('description', '')}")
        
        if explanation:
            lines.append(f"\nReason: {explanation}")
        
        return ToolResult.ok("\n".join(lines))
    
    # -------------------------------------------------------------------------
    # Caching methods
    # -------------------------------------------------------------------------
    
    def _cache_key(self, name: str, arguments: dict[str, Any]) -> str:
        """Generate a cache key for a tool call."""
        args_json = json.dumps(arguments, sort_keys=True, default=str)
        content = f"{name}:{args_json}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def _get_cached(self, key: str) -> Optional[ToolResult]:
        """Get a cached result if valid."""
        cached = self._cache.get(key)
        if cached is not None and cached.is_valid(self._config.cache_ttl):
            return cached.result
        return None
    
    def _cache_result(self, key: str, result: ToolResult) -> None:
        """Cache a tool result."""
        self._cache[key] = CachedResult(result=result, cached_at=time.time())
        
        # Evict old entries if cache is too large
        if len(self._cache) > 1000:
            self._evict_expired_cache()
    
    def _evict_expired_cache(self) -> None:
        """Remove expired entries from cache."""
        now = time.time()
        expired_keys = [
            key for key, cached in self._cache.items()
            if not cached.is_valid(self._config.cache_ttl)
        ]
        for key in expired_keys:
            del self._cache[key]
    
    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
    
    # -------------------------------------------------------------------------
    # Statistics methods
    # -------------------------------------------------------------------------
    
    def _record_execution(
        self,
        tool_name: str,
        duration_ms: int,
        success: bool,
        cached: bool,
    ) -> None:
        """Record execution statistics."""
        self._stats.total_executions += 1
        self._stats.total_duration_ms += duration_ms
        
        if success:
            self._stats.successful_executions += 1
        else:
            self._stats.failed_executions += 1
        
        if cached:
            self._stats.cache_hits += 1
        
        # Per-tool stats
        if tool_name not in self._stats.by_tool:
            self._stats.by_tool[tool_name] = ToolStats()
        
        tool_stats = self._stats.by_tool[tool_name]
        tool_stats.executions += 1
        tool_stats.total_ms += duration_ms
        if success:
            tool_stats.successes += 1
    
    def stats(self) -> ExecutorStats:
        """Get execution statistics."""
        return self._stats
    
    # -------------------------------------------------------------------------
    # Batch execution
    # -------------------------------------------------------------------------
    
    def execute_batch(
        self,
        ctx: "AgentContext",
        calls: List[Tuple[str, dict]],
    ) -> List[ToolResult]:
        """Execute multiple tool calls in parallel.
        
        Args:
            ctx: Agent context from term_sdk
            calls: List of (tool_name, arguments) tuples
            
        Returns:
            List of ToolResults in the same order as input calls
        """
        if not calls:
            return []
        
        # For single call, just execute directly
        if len(calls) == 1:
            name, args = calls[0]
            return [self.execute(ctx, name, args)]
        
        # Execute in parallel using ThreadPoolExecutor
        results: List[Optional[ToolResult]] = [None] * len(calls)
        
        with ThreadPoolExecutor(max_workers=self._config.max_concurrent) as executor:
            future_to_index = {
                executor.submit(self.execute, ctx, name, args): i
                for i, (name, args) in enumerate(calls)
            }
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    results[index] = ToolResult.fail(f"Batch execution failed: {e}")
        
        # Ensure all results are filled (shouldn't happen, but just in case)
        return [r if r is not None else ToolResult.fail("No result") for r in results]
    
    def get_plan(self) -> list[dict[str, str]]:
        """Get the current plan."""
        return self._plan.copy()
    
    def get_tools_for_llm(self) -> list:
        """Get tool specifications formatted for the LLM.
        
        Returns tools in term_sdk Tool format.
        """
        from term_sdk import Tool
        
        specs = get_all_tools()
        tools = []
        
        for spec in specs:
            tools.append(Tool(
                name=spec["name"],
                description=spec.get("description", ""),
                parameters=spec.get("parameters", {}),
            ))
        
        return tools
