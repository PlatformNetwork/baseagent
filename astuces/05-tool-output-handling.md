# Tool Output Handling - Truncation Strategies

## The Problem

Tool outputs can be massive:
- `find /` returns thousands of lines
- `cat large_file.py` dumps entire file
- Build logs can be megabytes
- Stack traces repeat endlessly

Sending all this to the LLM wastes tokens and confuses the model.

## Strategy 1: Line-Based Limits

Simple approach - limit output lines:

```python
MAX_OUTPUT_LINES = 500

def limit_lines(output: str, max_lines: int = MAX_OUTPUT_LINES) -> str:
    lines = output.split('\n')
    if len(lines) <= max_lines:
        return output
    
    return '\n'.join(lines[:max_lines]) + f"\n\n[... {len(lines) - max_lines} more lines truncated ...]"
```

**Problem**: Cuts off the END, which often has the most important info (errors, results).

## Strategy 2: Middle-Out Truncation

Keep start AND end, remove the middle:

```python
def middle_out_truncate(text: str, max_bytes: int = 50000) -> str:
    """Keep start and end, remove middle."""
    if len(text) <= max_bytes:
        return text
    
    # Keep 45% at start, 45% at end, 10% for message
    keep_each = int(max_bytes * 0.45)
    
    start = text[:keep_each]
    end = text[-keep_each:]
    removed = len(text) - (keep_each * 2)
    
    return f"{start}\n\n[... {removed} bytes truncated from middle ...]\n\n{end}"
```

**Why this works**:
- Start has headers, command info
- End has final results, error messages
- Middle is often repetitive (progress logs, repeated patterns)

## Strategy 3: Smart Truncation by Content Type

Different outputs need different handling:

```python
def smart_truncate(output: str, tool_name: str) -> str:
    if tool_name == "shell_command":
        return truncate_shell_output(output)
    elif tool_name == "read_file":
        return truncate_file_content(output)
    elif tool_name == "grep_files":
        return truncate_search_results(output)
    else:
        return middle_out_truncate(output)

def truncate_shell_output(output: str) -> str:
    """For shell: prioritize errors and last lines."""
    lines = output.split('\n')
    
    # Check for common error patterns
    error_lines = [l for l in lines if 'error' in l.lower() or 'failed' in l.lower()]
    
    if error_lines:
        # Include context around errors
        return extract_error_context(output, error_lines)
    
    return middle_out_truncate(output)

def truncate_file_content(output: str) -> str:
    """For files: use line-based truncation with line numbers."""
    lines = output.split('\n')
    
    if len(lines) > 200:
        return '\n'.join(lines[:100]) + \
               f"\n\n[... {len(lines) - 200} lines omitted ...]\n\n" + \
               '\n'.join(lines[-100:])
    
    return output
```

## Strategy 4: Byte-Based Limits

Token estimation based on bytes:

```python
APPROX_BYTES_PER_TOKEN = 4
MAX_OUTPUT_TOKENS = 10000
MAX_OUTPUT_BYTES = MAX_OUTPUT_TOKENS * APPROX_BYTES_PER_TOKEN  # 40KB

def enforce_byte_limit(output: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    if len(output.encode('utf-8')) <= max_bytes:
        return output
    
    return middle_out_truncate(output, max_bytes)
```

## Best Practices

### 1. Truncate BEFORE Storing in Context

```python
def execute_tool(name: str, args: dict) -> str:
    result = run_tool(name, args)
    
    # Truncate immediately, not later
    return enforce_byte_limit(result.output)
```

### 2. Preserve Error Information

```python
def truncate_with_errors(output: str, stderr: str) -> str:
    # Always include full stderr (usually short)
    # Truncate stdout more aggressively
    
    truncated_stdout = middle_out_truncate(output, max_bytes=30000)
    
    if stderr:
        return f"{truncated_stdout}\n\n[STDERR]\n{stderr}"
    
    return truncated_stdout
```

### 3. Add Truncation Metadata

Tell the model what was removed:

```python
def truncate_with_metadata(output: str, max_bytes: int) -> str:
    if len(output) <= max_bytes:
        return output
    
    truncated = middle_out_truncate(output, max_bytes)
    
    metadata = f"""
[Output truncated: {len(output)} bytes -> {len(truncated)} bytes]
[To see full output, write to a file and read specific sections]
"""
    
    return truncated + metadata
```

## Recommended Limits

| Output Type | Max Bytes | Max Lines | Reasoning |
|-------------|-----------|-----------|-----------|
| Shell command | 50KB | 500 | Build logs can be huge |
| File read | 40KB | 400 | Large files need pagination |
| Grep results | 20KB | 200 | Many matches = narrow search |
| Directory list | 10KB | 100 | Deep trees are rarely useful |
| Error output | 10KB | 100 | Errors should be short |

## Testing Truncation

```python
def test_truncation():
    # Generate large output
    large_output = "x" * 100000  # 100KB
    
    truncated = middle_out_truncate(large_output, 50000)
    
    assert len(truncated) <= 50000
    assert "[truncated]" in truncated
    assert truncated.startswith("x")  # Start preserved
    assert truncated.rstrip().endswith("x")  # End preserved
```
