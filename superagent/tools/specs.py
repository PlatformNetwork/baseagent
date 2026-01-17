"""Tool specifications for SuperAgent - defines JSON schemas for all tools."""

from __future__ import annotations

from typing import Any

# Shell command tool
SHELL_COMMAND_SPEC: dict[str, Any] = {
    "name": "shell_command",
    "description": """Runs a shell command and returns its output.
Always set the `workdir` param when using this tool. Do not use `cd` unless absolutely necessary.
Use `rg` (ripgrep) for searching text or files as it's much faster than grep.""",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "workdir": {
                "type": "string",
                "description": "The working directory to execute the command in",
            },
            "timeout_ms": {
                "type": "number",
                "description": "The timeout for the command in milliseconds",
            },
        },
        "required": ["command"],
    },
}

# Read file tool
READ_FILE_SPEC: dict[str, Any] = {
    "name": "read_file",
    "description": """Reads a local file with 1-indexed line numbers.
Returns file content with line numbers in format 'L{number}: {content}'.
Supports reading specific ranges with offset and limit parameters.""",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to the file",
            },
            "offset": {
                "type": "number",
                "description": "The line number to start reading from (1-indexed, default: 1)",
            },
            "limit": {
                "type": "number",
                "description": "The maximum number of lines to return (default: 2000)",
            },
        },
        "required": ["file_path"],
    },
}

# List directory tool
LIST_DIR_SPEC: dict[str, Any] = {
    "name": "list_dir",
    "description": """Lists entries in a local directory with type indicators.
Directories are marked with '/', symlinks with '@'.
Supports recursive listing with configurable depth.""",
    "parameters": {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "Absolute or relative path to the directory to list",
            },
            "offset": {
                "type": "number",
                "description": "The entry number to start listing from (1-indexed, default: 1)",
            },
            "limit": {
                "type": "number",
                "description": "The maximum number of entries to return (default: 50)",
            },
            "depth": {
                "type": "number",
                "description": "The maximum directory depth to traverse (default: 2)",
            },
        },
        "required": ["dir_path"],
    },
}

# Grep files tool
GREP_FILES_SPEC: dict[str, Any] = {
    "name": "grep_files",
    "description": """Finds files whose contents match the pattern.
Uses ripgrep (rg) for fast searching.
Returns file paths sorted by modification time.""",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression pattern to search for",
            },
            "include": {
                "type": "string",
                "description": "Optional glob to filter which files are searched (e.g., '*.py', '*.{ts,tsx}')",
            },
            "path": {
                "type": "string",
                "description": "Directory or file path to search. Defaults to working directory.",
            },
            "limit": {
                "type": "number",
                "description": "Maximum number of file paths to return (default: 100)",
            },
        },
        "required": ["pattern"],
    },
}

# Apply patch tool
APPLY_PATCH_SPEC: dict[str, Any] = {
    "name": "apply_patch",
    "description": """Applies file patches to create, update, or delete files.

Patch format:
*** Begin Patch
*** Add File: <path>
+line to add
*** Update File: <path>
@@ context line
-old line
+new line
*** Delete File: <path>
*** End Patch

Rules:
- Use @@ with context to identify where to make changes
- Prefix new lines with + (even for new files)
- Prefix removed lines with -
- Use 3 lines of context before and after changes
- File paths must be relative, never absolute""",
    "parameters": {
        "type": "object",
        "properties": {
            "patch": {
                "type": "string",
                "description": "The patch content following the format described above",
            },
        },
        "required": ["patch"],
    },
}

# View image tool
VIEW_IMAGE_SPEC: dict[str, Any] = {
    "name": "view_image",
    "description": """View a local image from the filesystem.
Only use this if given a full filepath by the user, and the image isn't already attached.
Supported formats: PNG, JPEG, GIF, WebP, BMP.
The image will be loaded and attached to the conversation for analysis.""",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local filesystem path to the image file",
            },
        },
        "required": ["path"],
    },
}

# Write file tool
WRITE_FILE_SPEC: dict[str, Any] = {
    "name": "write_file",
    "description": """Write content to a file.
Creates the file if it doesn't exist, or overwrites if it does.
Parent directories are created automatically.""",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    },
}

# Update plan tool
UPDATE_PLAN_SPEC: dict[str, Any] = {
    "name": "update_plan",
    "description": """Updates the task plan to track progress.
Use this to show the user your planned steps and mark them as completed.
Each step should be 5-7 words maximum.""",
    "parameters": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Short description of the step (5-7 words)",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Current status of the step",
                        },
                    },
                    "required": ["description", "status"],
                },
                "description": "List of plan steps with their status",
            },
            "explanation": {
                "type": "string",
                "description": "Optional explanation of why the plan changed",
            },
        },
        "required": ["steps"],
    },
}

# All tool specs
TOOL_SPECS: dict[str, dict[str, Any]] = {
    "shell_command": SHELL_COMMAND_SPEC,
    "read_file": READ_FILE_SPEC,
    "write_file": WRITE_FILE_SPEC,
    "list_dir": LIST_DIR_SPEC,
    "grep_files": GREP_FILES_SPEC,
    "apply_patch": APPLY_PATCH_SPEC,
    "view_image": VIEW_IMAGE_SPEC,
    "update_plan": UPDATE_PLAN_SPEC,
}


def get_all_tools() -> list[dict[str, Any]]:
    """Get all tool specifications as a list.
    
    Returns:
        List of tool specification dicts
    """
    return list(TOOL_SPECS.values())


def get_tool_spec(name: str) -> dict[str, Any] | None:
    """Get a specific tool specification.
    
    Args:
        name: Name of the tool
        
    Returns:
        Tool specification dict or None if not found
    """
    return TOOL_SPECS.get(name)
