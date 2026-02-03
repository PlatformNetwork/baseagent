"""Tools module - registry and tool implementations."""

# Individual tools
from src.tools.apply_patch import ApplyPatchTool
from src.tools.base import BaseTool, ToolMetadata, ToolResult
from src.tools.list_dir import ListDirTool
from src.tools.read_file import ReadFileTool
from src.tools.registry import (
    CachedResult,
    ExecutorConfig,
    ExecutorStats,
    ToolRegistry,
    ToolStats,
)
from src.tools.search_files import SearchFilesTool
from src.tools.specs import TOOL_SPECS, get_all_tools, get_tool_spec
from src.tools.view_image import view_image
from src.tools.write_file import WriteFileTool

__all__ = [
    # Base
    "ToolResult",
    "BaseTool",
    "ToolMetadata",
    # Registry
    "ToolRegistry",
    "ExecutorConfig",
    "ExecutorStats",
    "ToolStats",
    "CachedResult",
    # Specs
    "get_all_tools",
    "get_tool_spec",
    "TOOL_SPECS",
    # Tools
    "ApplyPatchTool",
    "ReadFileTool",
    "WriteFileTool",
    "ListDirTool",
    "SearchFilesTool",
    "view_image",
]
