# 05 - Best Practices

This document covers proven best practices for building effective generalist agents. Each practice includes code examples and explanations.

---

## Practice 1: Always Explore First

Before taking any action, gather context about the environment.

### Implementation

```python
def explore(self, ctx: Any) -> str:
    """Gather context about the current environment."""
    results = []
    
    # Current location
    pwd = shell("pwd")
    results.append(f"Working directory: {pwd.stdout.strip()}")
    
    # List files
    ls = shell("ls -la")
    results.append(f"Files:\n{ls.stdout}")
    
    # Check for README
    readme = shell("cat README.md 2>/dev/null")
    if readme.ok:
        results.append(f"README.md:\n{readme.stdout[:2000]}")
    
    # Check for common project files
    for config in ["package.json", "Cargo.toml", "setup.py", "Makefile"]:
        check = shell(f"cat {config} 2>/dev/null")
        if check.ok:
            results.append(f"{config}:\n{check.stdout[:1000]}")
    
    return "\n\n".join(results)

def run(self, ctx: Any):
    # ALWAYS explore first
    context = self.explore(ctx)
    
    # Now let LLM reason with full context
    response = self.llm.ask(
        f"Task: {ctx.instruction}\n\n"
        f"Environment:\n{context}\n\n"
        "What should I do first?",
        system="You are a task-solving agent."
    )
    
    # Continue with LLM-driven execution...
```

### Why This Matters

- LLM makes better decisions with more context
- Prevents assumptions about the environment
- Discovers constraints and requirements early

---

## Practice 2: Use Structured JSON Responses

Always use JSON for LLM responses to enable reliable parsing.

### System Prompt

```python
SYSTEM_PROMPT = """You are a task-solving agent. Always respond with valid JSON:

{
    "analysis": "Your analysis of the current situation",
    "plan": "What you plan to do next",
    "commands": [
        {"command": "shell command here", "timeout": 10}
    ],
    "task_complete": false
}

Rules:
- "analysis" and "plan" are required strings
- "commands" is an array of command objects
- "task_complete" is a boolean (default false)
- Use proper JSON escaping for special characters
"""
```

### Parser

```python
import json
import re

def parse_llm_response(response_text: str) -> dict | None:
    """Parse JSON from LLM response, handling common issues."""
    
    # Try to extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if not json_match:
        return None
    
    json_str = json_match.group()
    
    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError:
        # Try to fix common issues
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
```

### Usage in Agent

```python
def run(self, ctx: Any):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: {ctx.instruction}"}
    ]
    
    while True:
        response = self.llm.chat(messages)
        data = parse_llm_response(response.text)
        
        if not data:
            # Ask for valid JSON
            messages.append({"role": "assistant", "content": response.text})
            messages.append({"role": "user", "content": "Please respond with valid JSON."})
            continue
        
        if data.get("task_complete"):
            break
        
        # Execute commands
        for cmd_obj in data.get("commands", []):
            result = shell(cmd_obj["command"], timeout=cmd_obj.get("timeout", 30))
            messages.append({"role": "assistant", "content": response.text})
            messages.append({"role": "user", "content": f"Output:\n{result.output[-3000:]}"})
    
    # Task complete
```

---

## Practice 3: Truncate Outputs for Context Management

Prevent context overflow by truncating long outputs.

### Implementation

```python
def truncate_output(output: str, max_bytes: int = 10000) -> str:
    """Truncate output while preserving useful information."""
    
    if len(output.encode('utf-8')) <= max_bytes:
        return output
    
    # Keep first and last portions
    portion_size = max_bytes // 2
    
    output_bytes = output.encode('utf-8')
    first = output_bytes[:portion_size].decode('utf-8', errors='ignore')
    last = output_bytes[-portion_size:].decode('utf-8', errors='ignore')
    
    omitted = len(output_bytes) - portion_size * 2
    
    return (
        f"{first}\n"
        f"[... {omitted} bytes omitted ...]\n"
        f"{last}"
    )

def run(self, ctx: Any):
    while True:
        response = self.llm.chat(messages[-20:])  # Keep last 20 messages
        
        result = shell(command)
        
        # Truncate output before adding to context
        truncated = truncate_output(result.output)
        
        messages.append({
            "role": "user",
            "content": f"Output:\n{truncated}"
        })
```

### Alternative: Smart Truncation

```python
def smart_truncate(output: str, max_lines: int = 100) -> str:
    """Truncate keeping error messages and important info."""
    
    lines = output.split('\n')
    
    if len(lines) <= max_lines:
        return output
    
    # Prioritize lines with errors or important info
    priority_patterns = ['error', 'Error', 'ERROR', 'failed', 'Failed', 'warning', 'Warning']
    
    priority_lines = []
    other_lines = []
    
    for line in lines:
        if any(p in line for p in priority_patterns):
            priority_lines.append(line)
        else:
            other_lines.append(line)
    
    # Keep all priority lines + fill rest with other lines
    result_lines = priority_lines[:max_lines // 2]
    remaining = max_lines - len(result_lines)
    
    # Keep first and last portions of other lines
    if other_lines:
        half = remaining // 2
        result_lines = other_lines[:half] + ['[...]'] + other_lines[-half:] + result_lines
    
    return '\n'.join(result_lines[:max_lines])
```

---

## Practice 4: Implement Double Confirmation

Never mark complete without verification.

### Implementation

```python
CONFIRMATION_PROMPT = """You indicated the task is complete.

Current state:
{terminal_state}

Task was: {instruction}

Are you SURE the task is complete? This will trigger grading.
If yes, respond with {{"task_complete": true}} again.
If not, continue working.
"""

def run(self, ctx: Any):
    pending_confirmation = False
    
    while True:
        response = self.llm.chat(messages)
        data = parse_llm_response(response.text)
        
        if data.get("task_complete"):
            if pending_confirmation:
                # Second confirmation - actually done
                print("Task completion confirmed")
                break
            else:
                # First signal - ask for confirmation
                pending_confirmation = True
                state = shell("pwd && ls -la").output
                
                messages.append({"role": "assistant", "content": response.text})
                messages.append({
                    "role": "user",
                    "content": CONFIRMATION_PROMPT.format(
                        terminal_state=state,
                        instruction=ctx.instruction
                    )
                })
                continue
        else:
            pending_confirmation = False
        
        # Normal execution...
    
    # Task complete
```

---

## Practice 5: Verify Output Files Exist

Before completing, always verify expected outputs.

### Implementation

```python
def verify_outputs(self, ctx: Any, expected_files: list[str]) -> bool:
    """Verify that expected output files exist and have content."""
    
    for filepath in expected_files:
        # Check existence
        check = shell(f"test -f {filepath} && echo EXISTS")
        if "EXISTS" not in check.stdout:
            print(f"Missing output file: {filepath}")
            return False
        
        # Check non-empty
        size = shell(f"stat -c%s {filepath} 2>/dev/null || stat -f%z {filepath}")
        if size.ok and int(size.stdout.strip()) == 0:
            print(f"Output file is empty: {filepath}")
            return False
    
    return True

def run(self, ctx: Any):
    # ... task execution ...
    
    # Before completing, verify outputs
    # Let LLM determine expected outputs
    verification = self.llm.ask(
        f"Task: {ctx.instruction}\n\n"
        "What output files should exist? List them as JSON array.",
        system="Respond with JSON: {\"files\": [\"path1\", \"path2\"]}"
    )
    
    data = parse_llm_response(verification.text)
    expected_files = data.get("files", [])
    
    if expected_files and not self.verify_outputs(ctx, expected_files):
        print("Output verification failed, continuing...")
        # Don't mark complete - continue working
    else:
        # Task complete
```

---

## Practice 6: Understand What the Instruction Really Wants

The agent must **reason about the instruction** to understand what is truly expected - not assume or hardcode behaviors.

### Key Principle

Every action should be driven by the instruction. Don't assume the task needs:
- Cleanup (only if asked)
- Specific file formats (only if specified)
- Certain outputs (only what's requested)

### Implementation

```python
def run(self, ctx: Any):
    # Let LLM analyze what the instruction actually requires
    response = self.llm.ask(
        f"Task: {ctx.instruction}\n\n"
        "Analyze this task carefully:\n"
        "1. What is the expected deliverable?\n"
        "2. What format/location is expected?\n"
        "3. Are there any implicit requirements?\n"
        "4. What should NOT be done (unless asked)?",
        system="Think step by step about what the task truly requires."
    )
    
    # Agent acts based on LLM's understanding, not assumptions
```

### What NOT to Do

```python
# WRONG: Assuming cleanup is always needed
def run(self, ctx):
    # ... do task ...
    self.cleanup()  # NOT REQUESTED!
    # Task complete

# WRONG: Assuming specific output format
def run(self, ctx):
    # ... do task ...
    self.save_as_json()  # WAS JSON REQUESTED?
    # Task complete

# RIGHT: Only do what's asked
def run(self, ctx):
    # Let LLM determine exactly what's needed
    # based on the instruction
```

### Why This Matters

The benchmark tests whether your agent understands tasks - not whether it follows a hardcoded checklist. If the instruction says "create a file", don't also clean up, format, validate, etc. unless asked.

---

## Practice 7: Handle Errors Gracefully

Implement robust error handling with retries.

### Implementation

```python
def run_with_retry(
    self,
    ctx: Any,
    command: str,
    max_retries: int = 3,
    retry_delay: int = 5
) -> ShellResult:
    """Execute command with retry logic."""
    
    last_result = None
    
    for attempt in range(max_retries):
        result = shell(command)
        last_result = result
        
        if result.ok:
            return result
        
        # Check for transient errors worth retrying
        transient_errors = [
            "connection refused",
            "connection reset",
            "timeout",
            "temporary failure",
            "try again",
        ]
        
        is_transient = any(
            err in result.output.lower()
            for err in transient_errors
        )
        
        if is_transient and attempt < max_retries - 1:
            print(f"Transient error, retrying in {retry_delay}s...")
            shell(f"sleep {retry_delay}")
            continue
        
        # Non-transient error or out of retries
        break
    
    return last_result
```

### LLM-Assisted Error Recovery

```python
def handle_error(self, ctx: Any, error_output: str) -> str | None:
    """Let LLM suggest error recovery."""
    
    response = self.llm.ask(
        f"Command failed with output:\n{error_output[-2000:]}\n\n"
        "How should I fix this? Respond with JSON:\n"
        '{"recovery_command": "...", "explanation": "..."}',
        system="Suggest a recovery command or say 'no_fix' if unfixable."
    )
    
    data = parse_llm_response(response.text)
    if data and data.get("recovery_command") != "no_fix":
        return data.get("recovery_command")
    
    return None
```

---

## Practice 8: Log Progress

Make debugging easier with clear logging.

### Implementation

```python
def run(self, ctx: Any):
    print(f"Starting task: {ctx.instruction[:100]}...")
    
    context = self.explore(ctx)
    print(f"Explored environment: {len(context)} chars")
    
    iteration = 0
    while iteration < 100:
        iteration += 1
        print(f"Iteration {iteration}")
        
        response = self.llm.chat(messages)
        data = parse_llm_response(response.text)
        
        if not data:
            print("Failed to parse LLM response")
            continue
        
        print(f"Analysis: {data.get('analysis', '')[:100]}...")
        print(f"Plan: {data.get('plan', '')[:100]}...")
        
        for cmd in data.get("commands", []):
            print(f"$ {cmd['command'][:80]}")
            result = shell(cmd["command"])
            print(f"Exit: {result.exit_code}, Output: {len(result.output)} chars")
        
        if data.get("task_complete"):
            print("Task marked complete")
            break
    
    print(f"Finished after {iteration} iterations")
    # Task complete
```

---

## Practice 9: Manage Context Window

Keep conversation history bounded.

### Implementation

```python
class ContextManager:
    def __init__(self, max_messages: int = 20, max_tokens_estimate: int = 50000):
        self.messages = []
        self.max_messages = max_messages
        self.max_tokens = max_tokens_estimate
    
    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self._prune()
    
    def _prune(self):
        # Keep system message + recent messages
        if len(self.messages) <= self.max_messages:
            return
        
        # Always keep system message if present
        system_msg = None
        if self.messages and self.messages[0]["role"] == "system":
            system_msg = self.messages[0]
            self.messages = self.messages[1:]
        
        # Keep most recent messages
        self.messages = self.messages[-(self.max_messages - 1):]
        
        # Restore system message
        if system_msg:
            self.messages.insert(0, system_msg)
    
    def get_messages(self) -> list:
        return self.messages.copy()

def run(self, ctx: Any):
    context_mgr = ContextManager(max_messages=20)
    context_mgr.add("system", SYSTEM_PROMPT)
    context_mgr.add("user", f"Task: {ctx.instruction}")
    
    while True:
        response = self.llm.chat(context_mgr.get_messages())
        context_mgr.add("assistant", response.text)
        
        # ... execute commands ...
        
        context_mgr.add("user", f"Output:\n{truncated_output}")
```

---

## Practice 10: Use Absolute Paths

Always use absolute paths for output files.

### Implementation

```python
def run(self, ctx: Any):
    # Get working directory
    pwd = shell("pwd").stdout.strip()
    
    # When writing files, use absolute paths
    output_path = f"{pwd}/result.txt"
    write_file(output_path, content)
    
    # Verify with absolute path
    shell(f"ls -la {output_path}")
```

### In LLM Prompts

```python
SYSTEM_PROMPT = """You are a task-solving agent.

IMPORTANT: Always use absolute paths for file operations.
The working directory is: {pwd}

When creating files, use full paths like:
- {pwd}/output.txt
- {pwd}/result.json

Never use relative paths like ./output.txt
"""

def run(self, ctx: Any):
    pwd = shell("pwd").stdout.strip()
    system = SYSTEM_PROMPT.format(pwd=pwd)
    
    messages = [{"role": "system", "content": system}, ...]
```

---

## Summary: Best Practices Checklist

| Practice | Key Point |
|----------|-----------|
| Explore First | Gather context before acting |
| JSON Responses | Structured, parseable output |
| Truncate Outputs | Prevent context overflow |
| Double Confirmation | Verify before completing |
| Verify Outputs | Check files exist |
| **Understand Instruction** | **Only do what's asked** |
| Handle Errors | Retry transient failures |
| Log Progress | Enable debugging |
| Manage Context | Bound conversation history |
| Absolute Paths | Prevent path confusion |

**Key Principle:** The agent must reason about what the instruction truly wants. Don't assume behaviors like cleanup, validation, or formatting unless explicitly requested.
