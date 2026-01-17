"""High-level tool executor for SuperAgent.

This module wraps ToolRegistry with:
- Timeout enforcement
- Execution tracking  
- Batch execution support
- Risk assessment for commands

Adapted from: cli/fabric-core/src/agent/executor.rs
"""

from __future__ import annotations

import concurrent.futures
import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from term_sdk import AgentContext

from src.tools.registry import ToolRegistry, ExecutorConfig, ExecutorStats
from src.tools.base import ToolResult


class RiskLevel(Enum):
    """Risk level for tool operations."""
    SAFE = auto()      # Read-only operations
    LOW = auto()       # Network/environment access
    MEDIUM = auto()    # File modifications
    HIGH = auto()      # Destructive operations
    CRITICAL = auto()  # System destruction potential


class SandboxPolicy(Enum):
    """Policy for sandbox enforcement."""
    STRICT = auto()    # Block all risky operations
    PROMPT = auto()    # Prompt user for risky operations  
    PERMISSIVE = auto()  # Allow most operations


@dataclass
class ExecutionResult:
    """Result of a tool execution with timing and metadata."""
    tool_name: str
    result: ToolResult
    duration_ms: int
    cached: bool = False
    risk_level: Optional[RiskLevel] = None
    
    @property
    def success(self) -> bool:
        """Whether the execution was successful."""
        return self.result.success
    
    @property
    def output(self) -> str:
        """The output from the tool."""
        return self.result.output


@dataclass
class CachedExecutionResult:
    """A cached execution result with timestamp."""
    result: ExecutionResult
    cached_at: float
    
    def is_valid(self, ttl: float) -> bool:
        """Check if the cached result is still valid."""
        return (time.time() - self.cached_at) < ttl


class AgentExecutor:
    """
    High-level executor for agent tool calls.
    
    Wraps ToolRegistry with:
    - Timeout enforcement
    - Execution tracking
    - Batch execution support
    - Risk assessment
    - Result caching
    
    Example:
        executor = AgentExecutor(cwd=Path("/project"))
        result = executor.execute(ctx, "read_file", {"file_path": "main.py"})
        if result.success:
            print(result.output)
    """
    
    def __init__(
        self,
        cwd: Optional[Path] = None,
        config: Optional[ExecutorConfig] = None,
        sandbox_policy: SandboxPolicy = SandboxPolicy.PROMPT,
    ):
        """Initialize the executor.
        
        Args:
            cwd: Working directory for tool operations
            config: Executor configuration (timeouts, concurrency, etc.)
            sandbox_policy: Policy for handling risky operations
        """
        self.registry = ToolRegistry(cwd=cwd)
        if config:
            self.registry._config = config
        self._sandbox_policy = sandbox_policy
        self._execution_cache: Dict[str, CachedExecutionResult] = {}
    
    @property
    def config(self) -> ExecutorConfig:
        """Get the executor configuration."""
        return self.registry._config
    
    @property
    def cwd(self) -> Path:
        """Get the current working directory."""
        return self.registry.cwd
    
    @cwd.setter
    def cwd(self, value: Path) -> None:
        """Set the current working directory."""
        self.registry.cwd = value
    
    def execute(
        self,
        ctx: "AgentContext",
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Execute a single tool with timeout.
        
        Args:
            ctx: Agent context from term_sdk
            tool_name: Name of tool to execute
            arguments: Tool arguments
            timeout: Optional timeout override (seconds)
            
        Returns:
            ExecutionResult with result and timing
        """
        start = time.time()
        
        # Assess risk level
        risk = self.assess_risk(tool_name, arguments)
        
        # Use config timeout if not specified
        effective_timeout = timeout or self.registry._config.default_timeout
        
        # Execute with timeout
        cached = False
        try:
            result = self._execute_with_timeout(
                ctx, tool_name, arguments, effective_timeout
            )
        except TimeoutError:
            result = ToolResult.fail(
                f"Tool {tool_name} timed out after {effective_timeout}s"
            )
        except Exception as e:
            result = ToolResult.fail(f"Tool {tool_name} failed: {e}")
        
        duration_ms = int((time.time() - start) * 1000)
        
        return ExecutionResult(
            tool_name=tool_name,
            result=result,
            duration_ms=duration_ms,
            cached=cached,
            risk_level=risk,
        )
    
    def _execute_with_timeout(
        self,
        ctx: "AgentContext",
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: float,
    ) -> ToolResult:
        """Execute with timeout using threading.
        
        Args:
            ctx: Agent context
            tool_name: Name of tool to execute
            arguments: Tool arguments
            timeout: Timeout in seconds
            
        Returns:
            ToolResult from the tool
            
        Raises:
            TimeoutError: If execution exceeds timeout
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self.registry.execute, ctx, tool_name, arguments
            )
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"Execution timed out after {timeout}s")
    
    def execute_batch(
        self,
        ctx: "AgentContext",
        calls: List[Tuple[str, Dict[str, Any]]],
        parallel: bool = True,
    ) -> List[ExecutionResult]:
        """
        Execute multiple tools.
        
        Args:
            ctx: Agent context
            calls: List of (tool_name, arguments) tuples
            parallel: If True, execute in parallel (up to max_concurrent)
            
        Returns:
            List of ExecutionResults in same order as calls
        """
        if not calls:
            return []
        
        if not parallel:
            return [
                self.execute(ctx, name, args)
                for name, args in calls
            ]
        
        # Parallel execution with ordering preserved
        results: List[Optional[ExecutionResult]] = [None] * len(calls)
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.registry._config.max_concurrent
        ) as executor:
            # Submit all futures with their indices
            future_to_index = {
                executor.submit(self.execute, ctx, name, args): i
                for i, (name, args) in enumerate(calls)
            }
            
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    # Create a failed result for exceptions
                    name, _ = calls[index]
                    results[index] = ExecutionResult(
                        tool_name=name,
                        result=ToolResult.fail(str(e)),
                        duration_ms=0,
                        cached=False,
                    )
        
        return results  # type: ignore
    
    def execute_sequential(
        self,
        ctx: "AgentContext",
        calls: List[Tuple[str, Dict[str, Any]]],
    ) -> List[ExecutionResult]:
        """
        Execute tools sequentially (alias for execute_batch with parallel=False).
        
        Args:
            ctx: Agent context
            calls: List of (tool_name, arguments) tuples
            
        Returns:
            List of ExecutionResults in same order as calls
        """
        return self.execute_batch(ctx, calls, parallel=False)
    
    def assess_risk(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> RiskLevel:
        """
        Assess risk level of a tool call.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            RiskLevel indicating the risk of this operation
        """
        # Check for shell commands specifically
        if tool_name == "shell_command":
            cmd = arguments.get("command", "")
            return self._assess_command_risk(cmd)
        
        # Default risk by tool category
        if tool_name in ("read_file", "list_dir", "grep_files", "view_image"):
            return RiskLevel.SAFE
        
        if tool_name == "write_file":
            return RiskLevel.MEDIUM
        
        if tool_name == "apply_patch":
            return RiskLevel.MEDIUM
        
        if tool_name == "update_plan":
            return RiskLevel.SAFE
        
        # Unknown tools get medium risk
        return RiskLevel.MEDIUM
    
    def _assess_command_risk(self, command: str) -> RiskLevel:
        """
        Assess risk of a shell command.
        
        Args:
            command: Shell command string
            
        Returns:
            RiskLevel for the command
        """
        cmd = command.lower().strip()
        
        # Critical: system destruction
        if (
            (cmd.startswith("rm -rf /") and (cmd == "rm -rf /" or cmd.startswith("rm -rf / ")))
            or "dd if=" in cmd
            or ":(){" in cmd
            or "mkfs" in cmd
        ):
            return RiskLevel.CRITICAL
        
        # High: destructive operations
        if (
            "rm -rf" in cmd
            or "rm -r" in cmd
            or "rmdir" in cmd
            or "git push" in cmd
            or "git reset --hard" in cmd
            or "chmod 777" in cmd
            or "sudo" in cmd
            or ("curl" in cmd and "| sh" in cmd)
            or ("wget" in cmd and "| sh" in cmd)
        ):
            return RiskLevel.HIGH
        
        # Medium: file modifications
        if (
            "mv " in cmd
            or "cp " in cmd
            or ">" in cmd
            or ">>" in cmd
            or "git commit" in cmd
            or "npm install" in cmd
            or "pip install" in cmd
        ):
            return RiskLevel.MEDIUM
        
        # Low: network or environment access
        if (
            "curl" in cmd
            or "wget" in cmd
            or "ssh" in cmd
            or "env" in cmd
            or "export" in cmd
        ):
            return RiskLevel.LOW
        
        # Safe: read-only operations
        if (
            cmd.startswith("ls")
            or cmd.startswith("cat ")
            or cmd.startswith("head ")
            or cmd.startswith("tail ")
            or cmd.startswith("grep ")
            or cmd.startswith("find ")
            or cmd.startswith("pwd")
            or cmd.startswith("echo ")
            or cmd.startswith("git status")
            or cmd.startswith("git log")
            or cmd.startswith("git diff")
        ):
            return RiskLevel.SAFE
        
        return RiskLevel.MEDIUM
    
    def can_auto_approve(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> bool:
        """
        Check if a tool call can be auto-approved based on risk and policy.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            True if the call can be auto-approved
        """
        risk = self.assess_risk(tool_name, arguments)
        
        if self._sandbox_policy == SandboxPolicy.STRICT:
            return risk == RiskLevel.SAFE
        elif self._sandbox_policy == SandboxPolicy.PROMPT:
            return risk in (RiskLevel.SAFE, RiskLevel.LOW)
        else:  # PERMISSIVE
            return risk != RiskLevel.CRITICAL
    
    def stats(self) -> ExecutorStats:
        """Get execution statistics."""
        return self.registry.stats()
    
    def clear_cache(self) -> None:
        """Clear the result cache."""
        self.registry.clear_cache()
        self._execution_cache.clear()
    
    def cache_size(self) -> int:
        """Get the current cache size."""
        return len(self.registry._cache)
    
    def get_tools_for_llm(self) -> list:
        """Get tool specs for LLM."""
        return self.registry.get_tools_for_llm()
    
    def get_plan(self) -> list:
        """Get the current execution plan."""
        return self.registry.get_plan()


def _cache_key(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Generate a cache key for a tool call."""
    args_json = json.dumps(arguments, sort_keys=True)
    return f"{tool_name}:{args_json}"
