"""Base tool class for SuperAgent tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, List, Dict


@dataclass
class ToolMetadata:
    """Metadata about a tool execution."""
    duration_ms: int = 0
    exit_code: Optional[int] = None
    files_modified: List[str] = field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    error: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    inject_content: Optional[dict[str, Any]] = None  # For injecting images into context
    metadata: Optional[ToolMetadata] = None
    
    @classmethod
    def ok(cls, output: str, data: Optional[dict[str, Any]] = None) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, output=output, data=data)
    
    @classmethod
    def fail(cls, error: str, output: str = "") -> "ToolResult":
        """Create a failed result."""
        return cls(success=False, output=output, error=error)
    
    def with_metadata(self, metadata: ToolMetadata) -> "ToolResult":
        """Add metadata to this result."""
        self.metadata = metadata
        return self
    
    def to_message(self) -> str:
        """Convert to message format for the LLM."""
        if self.success:
            return self.output
        else:
            return f"Error: {self.error}\n{self.output}" if self.output else f"Error: {self.error}"


class BaseTool(ABC):
    """Base class for all tools."""
    
    name: str
    description: str
    
    def __init__(self, cwd: Path):
        """Initialize the tool.
        
        Args:
            cwd: Current working directory for the tool
        """
        self.cwd = cwd
    
    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given arguments.
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            ToolResult with success status and output
        """
        pass
    
    def resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the working directory.
        
        Args:
            path: Path string (absolute or relative)
            
        Returns:
            Resolved absolute Path
        """
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.cwd / p).resolve()
    
    @classmethod
    def get_spec(cls) -> dict[str, Any]:
        """Get the tool specification for the LLM.
        
        Returns:
            Tool specification dict
        """
        raise NotImplementedError("Subclasses must implement get_spec()")
