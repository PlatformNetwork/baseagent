"""Tools module - registry and tool implementations."""

from superagent.tools.base import ToolResult, BaseTool, ToolMetadata
from superagent.tools.registry import (
    ToolRegistry,
    ExecutorConfig,
    ExecutorStats,
    ToolStats,
    CachedResult,
)
from superagent.tools.specs import get_all_tools, get_tool_spec, TOOL_SPECS

# Individual tools
from superagent.tools.apply_patch import ApplyPatchTool
from superagent.tools.read_file import ReadFileTool
from superagent.tools.write_file import WriteFileTool
from superagent.tools.list_dir import ListDirTool
from superagent.tools.search_files import SearchFilesTool
from superagent.tools.view_image import view_image

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
