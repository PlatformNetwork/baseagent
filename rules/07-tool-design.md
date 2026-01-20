# 07 - Tool Design

This guide covers best practices for designing tools that LLM agents can use effectively.

---

## Principles of Good Tool Design

### 1. Single Responsibility

Each tool should do one thing well.

```python
# GOOD: Single purpose tools
Tool(
    name="read_file",
    description="Read the contents of a file",
    parameters={"path": {"type": "string"}}
)

Tool(
    name="write_file",
    description="Write content to a file",
    parameters={"path": {"type": "string"}, "content": {"type": "string"}}
)

# BAD: Multi-purpose tool
Tool(
    name="file_operation",
    description="Read, write, or delete a file",
    parameters={
        "operation": {"type": "string", "enum": ["read", "write", "delete"]},
        "path": {"type": "string"},
        "content": {"type": "string"}  # Only for write
    }
)
```

### 2. Clear Descriptions

Write descriptions that help the LLM choose the right tool.

```python
# GOOD: Clear, specific description
Tool(
    name="execute_command",
    description="Execute a shell command in the terminal and return stdout/stderr. Use for running programs, listing files, or any terminal operation.",
    parameters={
        "command": {
            "type": "string",
            "description": "The shell command to execute (e.g., 'ls -la', 'python script.py')"
        }
    }
)

# BAD: Vague description
Tool(
    name="run",
    description="Run something",
    parameters={"cmd": {"type": "string"}}
)
```

### 3. Descriptive Parameters

Every parameter should have a clear description.

```python
Tool(
    name="search_files",
    description="Search for files matching a pattern",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g., '*.py', 'src/**/*.ts')"
            },
            "directory": {
                "type": "string",
                "description": "Directory to search in (default: current directory)",
                "default": "."
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 100)",
                "default": 100
            }
        },
        "required": ["pattern"]
    }
)
```

---

## Core Tool Set

Every generalist agent should have these essential tools:

### Execute Command

```python
Tool(
    name="execute_command",
    description="Execute a shell command and return the output. Use for running programs, installing packages, building projects, or any terminal operation.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum seconds to wait (default: 30, max: 300)",
                "default": 30
            },
            "working_directory": {
                "type": "string",
                "description": "Directory to run the command in (default: current)",
                "default": "."
            }
        },
        "required": ["command"]
    }
)
```

### Read File

```python
Tool(
    name="read_file",
    description="Read the contents of a file. Returns the file content as text.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file"
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum lines to read (default: all)",
                "default": -1
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start from (0-indexed, default: 0)",
                "default": 0
            }
        },
        "required": ["path"]
    }
)
```

### Write File

```python
Tool(
    name="write_file",
    description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Creates parent directories if needed.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            }
        },
        "required": ["path", "content"]
    }
)
```

### List Directory

```python
Tool(
    name="list_directory",
    description="List files and directories in a path. Returns file names, sizes, and modification times.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list (default: current directory)",
                "default": "."
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Include hidden files (starting with .)",
                "default": False
            },
            "recursive": {
                "type": "boolean",
                "description": "List recursively",
                "default": False
            }
        },
        "required": []
    }
)
```

### Task Complete

```python
Tool(
    name="task_complete",
    description="Mark the task as complete. Call this when you have finished the task successfully.",
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of what was accomplished"
            },
            "output_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of output files created"
            }
        },
        "required": ["summary"]
    }
)
```

---

## Implementing Tool Handlers

### Basic Handler Pattern

```python
class ToolHandler:
    def __init__(self, ctx: Any):
        self.ctx = ctx
    
    def execute_command(self, command: str, timeout: int = 30, working_directory: str = ".") -> str:
        """Execute a shell command."""
        # Input validation
        timeout = min(max(timeout, 1), 300)  # Clamp 1-300
        
        # Execute
        result = self.shell(command, timeout=timeout, cwd=working_directory)
        
        # Format output
        output = result.output[-10000:]  # Truncate
        
        if result.timed_out:
            return f"TIMEOUT after {timeout}s\nPartial output:\n{output}"
        
        status = "SUCCESS" if result.ok else f"FAILED (exit code {result.exit_code})"
        return f"{status}\n{output}"
    
    def read_file(self, path: str, max_lines: int = -1, offset: int = 0) -> str:
        """Read a file."""
        result = self.read_file(path)
        
        if result.failed:
            return f"ERROR: {result.stderr}"
        
        lines = result.stdout.split('\n')
        
        # Apply offset and limit
        if offset > 0:
            lines = lines[offset:]
        if max_lines > 0:
            lines = lines[:max_lines]
        
        content = '\n'.join(lines)
        
        # Truncate if too long
        if len(content) > 50000:
            content = content[:50000] + "\n[... truncated ...]"
        
        return content
    
    def write_file(self, path: str, content: str) -> str:
        """Write to a file."""
        # Ensure parent directory exists
        import os
        parent = os.path.dirname(path)
        if parent:
            self.shell(f"mkdir -p '{parent}'")
        
        result = self.write_file(path, content)
        
        if result.ok:
            return f"Successfully wrote {len(content)} bytes to {path}"
        else:
            return f"ERROR: {result.stderr}"
```

### Registration

```python
def setup(self):
    self.llm = LLM(default_model="anthropic/claude-3.5-sonnet")
    self.handler = ToolHandler(self.ctx)
    
    # Register all handlers
    self.llm.register_function("execute_command", self.handler.execute_command)
    self.llm.register_function("read_file", self.handler.read_file)
    self.llm.register_function("write_file", self.handler.write_file)
    self.llm.register_function("list_directory", self.handler.list_directory)
    self.llm.register_function("task_complete", self.handler.task_complete)
```

---

## Advanced Tool Patterns

### Tool with Validation

```python
def execute_command(self, command: str, timeout: int = 30) -> str:
    """Execute command with validation."""
    
    # Validate command isn't empty
    if not command or not command.strip():
        return "ERROR: Empty command"
    
    # Validate timeout
    if not isinstance(timeout, int) or timeout < 1:
        timeout = 30
    timeout = min(timeout, 300)
    
    # Check for obviously dangerous commands
    dangerous = ["rm -rf /", "mkfs", "> /dev/sda"]
    if any(d in command for d in dangerous):
        return "ERROR: Potentially dangerous command blocked"
    
    # Execute
    result = self.shell(command, timeout=timeout)
    
    # Format response
    return self._format_result(result)
```

### Tool with State

```python
class StatefulToolHandler:
    def __init__(self, ctx: Any):
        self.ctx = ctx
        self.command_history = []
        self.files_created = []
    
    def execute_command(self, command: str, **kwargs) -> str:
        result = self.shell(command, **kwargs)
        
        # Track history
        self.command_history.append({
            "command": command,
            "exit_code": result.exit_code,
            "timestamp": time.time()
        })
        
        return self._format_result(result)
    
    def write_file(self, path: str, content: str) -> str:
        result = self.write_file(path, content)
        
        if result.ok:
            self.files_created.append(path)
        
        return self._format_result(result)
    
    def get_summary(self) -> dict:
        return {
            "commands_run": len(self.command_history),
            "files_created": self.files_created,
            "last_command": self.command_history[-1] if self.command_history else None
        }
```

### Composite Tool

```python
Tool(
    name="edit_file",
    description="Make a specific edit to a file. Replaces old_text with new_text.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit"
            },
            "old_text": {
                "type": "string",
                "description": "Exact text to find and replace"
            },
            "new_text": {
                "type": "string",
                "description": "Text to replace with"
            }
        },
        "required": ["path", "old_text", "new_text"]
    }
)

def edit_file(self, path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing text."""
    
    # Read current content
    read_result = self.read_file(path)
    if read_result.failed:
        return f"ERROR: Could not read file: {read_result.stderr}"
    
    content = read_result.stdout
    
    # Check if old_text exists
    if old_text not in content:
        return f"ERROR: Could not find the specified text in {path}"
    
    # Check for multiple matches
    count = content.count(old_text)
    if count > 1:
        return f"ERROR: Found {count} matches. Please provide more specific text."
    
    # Make replacement
    new_content = content.replace(old_text, new_text, 1)
    
    # Write back
    write_result = self.write_file(path, new_content)
    if write_result.failed:
        return f"ERROR: Could not write file: {write_result.stderr}"
    
    return f"Successfully edited {path}"
```

---

## Tool Response Formatting

### Consistent Format

```python
class ToolResponse:
    @staticmethod
    def success(message: str, data: dict = None) -> str:
        response = f"SUCCESS: {message}"
        if data:
            response += f"\n{json.dumps(data, indent=2)}"
        return response
    
    @staticmethod
    def error(message: str, details: str = None) -> str:
        response = f"ERROR: {message}"
        if details:
            response += f"\nDetails: {details}"
        return response
    
    @staticmethod
    def output(content: str, truncated: bool = False) -> str:
        response = content
        if truncated:
            response += "\n[... output truncated ...]"
        return response
```

### Usage

```python
def read_file(self, path: str) -> str:
    result = self.read_file(path)
    
    if result.failed:
        return ToolResponse.error(f"Could not read {path}", result.stderr)
    
    content = result.stdout
    truncated = False
    
    if len(content) > 50000:
        content = content[:50000]
        truncated = True
    
    return ToolResponse.output(content, truncated)
```

---

## Common Mistakes

### Mistake 1: No Input Validation

```python
# BAD
def execute_command(self, command: str) -> str:
    return self.shell(command).output

# GOOD
def execute_command(self, command: str) -> str:
    if not command or not isinstance(command, str):
        return "ERROR: Invalid command"
    
    command = command.strip()
    if not command:
        return "ERROR: Empty command"
    
    return self.shell(command).output
```

### Mistake 2: Unbounded Output

```python
# BAD
def read_file(self, path: str) -> str:
    return self.read_file(path).stdout  # Could be huge!

# GOOD
def read_file(self, path: str) -> str:
    content = self.read_file(path).stdout
    if len(content) > 50000:
        return content[:50000] + "\n[truncated]"
    return content
```

### Mistake 3: Missing Error Handling

```python
# BAD
def write_file(self, path: str, content: str) -> str:
    self.write_file(path, content)
    return "Done"

# GOOD
def write_file(self, path: str, content: str) -> str:
    result = self.write_file(path, content)
    if result.failed:
        return f"ERROR: {result.stderr}"
    return f"Wrote {len(content)} bytes to {path}"
```

---

## Summary

| Principle | Description |
|-----------|-------------|
| Single Responsibility | One tool = one purpose |
| Clear Descriptions | Help LLM choose correctly |
| Input Validation | Check all parameters |
| Output Truncation | Bound response size |
| Error Handling | Return useful error messages |
| Consistent Format | Predictable response structure |
