"""Command execution with timeout, streaming, and secure environment.

This module provides subprocess execution capabilities with:
- Configurable timeouts
- Output streaming via callbacks
- Secure environment variable filtering (removes sensitive data)
- Output truncation for large outputs
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

# =============================================================================
# Constants
# =============================================================================

DEFAULT_TIMEOUT: float = 120.0  # 120 seconds
MAX_OUTPUT_SIZE: int = 100_000  # 100KB

# Patterns in variable names that indicate sensitive data (case-insensitive).
# These will be excluded from the environment passed to child processes.
SENSITIVE_PATTERNS: List[str] = [
    "KEY",        # API_KEY, SSH_KEY, etc.
    "SECRET",     # AWS_SECRET, etc.
    "TOKEN",      # AUTH_TOKEN, etc.
    "PASSWORD",   # DB_PASSWORD, etc.
    "CREDENTIAL", # GOOGLE_CREDENTIALS, etc.
    "PRIVATE",    # PRIVATE_KEY, etc.
]


# =============================================================================
# Output Types
# =============================================================================

class OutputChunkType(Enum):
    """Type of output chunk."""
    STDOUT = auto()
    STDERR = auto()


@dataclass
class OutputChunk:
    """Output chunk from streaming execution.
    
    Represents a single chunk of output from either stdout or stderr.
    """
    chunk_type: OutputChunkType
    data: str
    
    @classmethod
    def stdout(cls, data: str) -> "OutputChunk":
        """Create a stdout chunk."""
        return cls(chunk_type=OutputChunkType.STDOUT, data=data)
    
    @classmethod
    def stderr(cls, data: str) -> "OutputChunk":
        """Create a stderr chunk."""
        return cls(chunk_type=OutputChunkType.STDERR, data=data)
    
    def is_stdout(self) -> bool:
        """Check if this is a stdout chunk."""
        return self.chunk_type == OutputChunkType.STDOUT
    
    def is_stderr(self) -> bool:
        """Check if this is a stderr chunk."""
        return self.chunk_type == OutputChunkType.STDERR


# =============================================================================
# Options and Output
# =============================================================================

@dataclass
class ExecOptions:
    """Options for command execution.
    
    Attributes:
        cwd: Working directory for command execution.
        timeout: Maximum execution time in seconds.
        env: Additional environment variables to set.
        capture_output: Whether to capture stdout/stderr.
    """
    cwd: Path = field(default_factory=Path.cwd)
    timeout: float = DEFAULT_TIMEOUT
    env: Dict[str, str] = field(default_factory=dict)
    capture_output: bool = True
    
    def __post_init__(self):
        """Ensure cwd is a Path object."""
        if isinstance(self.cwd, str):
            self.cwd = Path(self.cwd)


@dataclass
class ExecOutput:
    """Output from command execution.
    
    Attributes:
        stdout: Standard output content.
        stderr: Standard error content.
        aggregated: Combined output (stdout + stderr).
        exit_code: Process exit code (-1 if unavailable).
        duration: Execution duration in seconds.
        timed_out: Whether the command timed out.
    """
    stdout: str
    stderr: str
    aggregated: str
    exit_code: int
    duration: float
    timed_out: bool


# =============================================================================
# Environment Building
# =============================================================================

def build_safe_environment(overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build a safe environment for command execution.
    
    - Inherits ALL environment variables from parent process
    - Excludes variables containing sensitive patterns (KEY, SECRET, TOKEN, etc.)
    - Forces non-interactive mode for common tools
    - Applies any custom overrides
    
    Args:
        overrides: Custom environment variables to set (override filtering).
        
    Returns:
        Dictionary of safe environment variables.
    """
    # Start with filtered parent environment
    env: Dict[str, str] = {}
    
    for key, value in os.environ.items():
        # Exclude variables with sensitive patterns (case-insensitive)
        key_upper = key.upper()
        is_sensitive = any(pattern in key_upper for pattern in SENSITIVE_PATTERNS)
        if not is_sensitive:
            env[key] = value
    
    # Force non-interactive mode for common tools
    # This prevents commands from hanging waiting for user input
    env["CI"] = "true"  # npm/yarn/pnpm/create-* use this
    env["DEBIAN_FRONTEND"] = "noninteractive"  # apt-get
    env["NPM_CONFIG_YES"] = "true"  # npm auto-yes
    env["YARN_ENABLE_IMMUTABLE_INSTALLS"] = "false"  # yarn
    env["NO_COLOR"] = "1"  # disable color codes
    env["TERM"] = "dumb"  # simple terminal
    
    # Apply custom overrides
    if overrides:
        for key, value in overrides.items():
            env[key] = value
    
    return env


# =============================================================================
# Output Truncation
# =============================================================================

def truncate_output(data: bytes) -> str:
    """Truncate output if it exceeds MAX_OUTPUT_SIZE.
    
    Args:
        data: Raw bytes from subprocess output.
        
    Returns:
        Decoded string, truncated if necessary with a notice.
    """
    # Decode with replacement for invalid UTF-8
    text = data.decode("utf-8", errors="replace")
    
    if len(text) > MAX_OUTPUT_SIZE:
        return f"{text[:MAX_OUTPUT_SIZE]}...\n[Output truncated, {len(text)} bytes total]"
    
    return text


# =============================================================================
# Command Execution
# =============================================================================

async def execute_command(
    command: List[str],
    options: Optional[ExecOptions] = None,
) -> ExecOutput:
    """Execute a command with timeout and output capture.
    
    Args:
        command: Command and arguments as a list of strings.
        options: Execution options (uses defaults if not provided).
        
    Returns:
        ExecOutput containing stdout, stderr, exit code, duration, etc.
    """
    if options is None:
        options = ExecOptions()
    
    # Handle empty command
    if not command:
        return ExecOutput(
            stdout="",
            stderr="",
            aggregated="Empty command",
            exit_code=1,
            duration=0.0,
            timed_out=False,
        )
    
    program = command[0]
    args = command[1:]
    
    start_time = time.monotonic()
    
    # Build safe environment
    env = build_safe_environment(options.env)
    
    try:
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            program,
            *args,
            cwd=options.cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        
        try:
            # Wait for completion with timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=options.timeout,
            )
            
            duration = time.monotonic() - start_time
            exit_code = process.returncode if process.returncode is not None else -1
            
            # Truncate outputs if necessary
            stdout = truncate_output(stdout_bytes)
            stderr = truncate_output(stderr_bytes)
            
            # Build aggregated output
            aggregated_parts = []
            if stdout:
                aggregated_parts.append(stdout)
            if stderr:
                aggregated_parts.append(stderr)
            aggregated = "\n".join(aggregated_parts)
            
            return ExecOutput(
                stdout=stdout,
                stderr=stderr,
                aggregated=aggregated,
                exit_code=exit_code,
                duration=duration,
                timed_out=False,
            )
            
        except asyncio.TimeoutError:
            # Timeout - kill the process
            duration = time.monotonic() - start_time
            
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass  # Process already terminated
            
            return ExecOutput(
                stdout="",
                stderr="",
                aggregated=f"Command timed out after {options.timeout:.1f}s",
                exit_code=-1,
                duration=duration,
                timed_out=True,
            )
            
    except FileNotFoundError:
        duration = time.monotonic() - start_time
        return ExecOutput(
            stdout="",
            stderr=f"Command not found: {program}",
            aggregated=f"Command not found: {program}",
            exit_code=127,
            duration=duration,
            timed_out=False,
        )
    except PermissionError:
        duration = time.monotonic() - start_time
        return ExecOutput(
            stdout="",
            stderr=f"Permission denied: {program}",
            aggregated=f"Permission denied: {program}",
            exit_code=126,
            duration=duration,
            timed_out=False,
        )
    except Exception as e:
        duration = time.monotonic() - start_time
        return ExecOutput(
            stdout="",
            stderr=f"Failed to spawn: {e}",
            aggregated=f"Failed to spawn: {e}",
            exit_code=-1,
            duration=duration,
            timed_out=False,
        )


async def execute_command_streaming(
    command: List[str],
    options: Optional[ExecOptions] = None,
    callback: Optional[Callable[[OutputChunk], None]] = None,
) -> ExecOutput:
    """Execute a command with streaming output.
    
    Reads stdout and stderr line by line, calling the callback for each chunk.
    
    Args:
        command: Command and arguments as a list of strings.
        options: Execution options (uses defaults if not provided).
        callback: Function called with each OutputChunk as it arrives.
        
    Returns:
        ExecOutput containing full stdout, stderr, exit code, duration, etc.
    """
    if options is None:
        options = ExecOptions()
    
    # Handle empty command
    if not command:
        return ExecOutput(
            stdout="",
            stderr="",
            aggregated="Empty command",
            exit_code=1,
            duration=0.0,
            timed_out=False,
        )
    
    program = command[0]
    args = command[1:]
    
    start_time = time.monotonic()
    
    # Build safe environment
    env = build_safe_environment(options.env)
    
    # Accumulators
    stdout_acc: List[str] = []
    stderr_acc: List[str] = []
    
    try:
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            program,
            *args,
            cwd=options.cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        
        async def read_stdout():
            """Read stdout line by line."""
            if process.stdout is None:
                return
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                stdout_acc.append(decoded)
                if callback:
                    callback(OutputChunk.stdout(decoded))
        
        async def read_stderr():
            """Read stderr line by line."""
            if process.stderr is None:
                return
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                stderr_acc.append(decoded)
                if callback:
                    callback(OutputChunk.stderr(decoded))
        
        try:
            # Read streams concurrently with timeout
            await asyncio.wait_for(
                asyncio.gather(
                    read_stdout(),
                    read_stderr(),
                    process.wait(),
                ),
                timeout=options.timeout,
            )
            
            duration = time.monotonic() - start_time
            exit_code = process.returncode if process.returncode is not None else -1
            
            # Join accumulated output
            stdout = "".join(stdout_acc)
            stderr = "".join(stderr_acc)
            
            # Truncate if necessary
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = f"{stdout[:MAX_OUTPUT_SIZE]}...\n[Output truncated, {len(stdout)} bytes total]"
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = f"{stderr[:MAX_OUTPUT_SIZE]}...\n[Output truncated, {len(stderr)} bytes total]"
            
            # Build aggregated output
            aggregated_parts = []
            if stdout:
                aggregated_parts.append(stdout)
            if stderr:
                aggregated_parts.append(stderr)
            aggregated = "\n".join(aggregated_parts)
            
            return ExecOutput(
                stdout=stdout,
                stderr=stderr,
                aggregated=aggregated,
                exit_code=exit_code,
                duration=duration,
                timed_out=False,
            )
            
        except asyncio.TimeoutError:
            # Timeout - kill the process
            duration = time.monotonic() - start_time
            
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
            
            # Return what we accumulated before timeout
            stdout = "".join(stdout_acc)
            stderr = "".join(stderr_acc)
            
            return ExecOutput(
                stdout=stdout,
                stderr=stderr,
                aggregated=f"Command timed out after {options.timeout:.1f}s",
                exit_code=-1,
                duration=duration,
                timed_out=True,
            )
            
    except FileNotFoundError:
        duration = time.monotonic() - start_time
        return ExecOutput(
            stdout="",
            stderr=f"Command not found: {program}",
            aggregated=f"Command not found: {program}",
            exit_code=127,
            duration=duration,
            timed_out=False,
        )
    except PermissionError:
        duration = time.monotonic() - start_time
        return ExecOutput(
            stdout="",
            stderr=f"Permission denied: {program}",
            aggregated=f"Permission denied: {program}",
            exit_code=126,
            duration=duration,
            timed_out=False,
        )
    except Exception as e:
        duration = time.monotonic() - start_time
        return ExecOutput(
            stdout="",
            stderr=f"Failed to spawn: {e}",
            aggregated=f"Failed to spawn: {e}",
            exit_code=-1,
            duration=duration,
            timed_out=False,
        )


# =============================================================================
# Synchronous Wrappers (convenience)
# =============================================================================

def execute_command_sync(
    command: List[str],
    options: Optional[ExecOptions] = None,
) -> ExecOutput:
    """Synchronous wrapper for execute_command.
    
    Args:
        command: Command and arguments as a list of strings.
        options: Execution options.
        
    Returns:
        ExecOutput containing stdout, stderr, exit code, etc.
    """
    return asyncio.run(execute_command(command, options))


def execute_command_streaming_sync(
    command: List[str],
    options: Optional[ExecOptions] = None,
    callback: Optional[Callable[[OutputChunk], None]] = None,
) -> ExecOutput:
    """Synchronous wrapper for execute_command_streaming.
    
    Args:
        command: Command and arguments as a list of strings.
        options: Execution options.
        callback: Function called with each OutputChunk.
        
    Returns:
        ExecOutput containing stdout, stderr, exit code, etc.
    """
    return asyncio.run(execute_command_streaming(command, options, callback))
