"""Tools module - registry and tool implementations."""

from src.tools.base import ToolResult, BaseTool, ToolMetadata
from src.tools.registry import (
    ToolRegistry,
    ExecutorConfig,
    ExecutorStats,
    ToolStats,
    CachedResult,
)
from src.tools.specs import get_all_tools, get_tool_spec, TOOL_SPECS

# Individual tools
from src.tools.apply_patch import ApplyPatchTool
from src.tools.read_file import ReadFileTool
from src.tools.write_file import WriteFileTool
from src.tools.list_dir import ListDirTool
from src.tools.search_files import SearchFilesTool
from src.tools.view_image import view_image

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
