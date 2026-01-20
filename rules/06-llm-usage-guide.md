# 06 - LLM Usage Guide (SDK 3.0 - litellm)

This guide covers using LLMs with **litellm** (no more term_sdk).

---

## Basic LLM Interaction

### Initialization

```python
from src.llm.client import LiteLLMClient, LLMError, CostLimitExceeded

# Create the LLM client
llm = LiteLLMClient(
    model="openrouter/anthropic/claude-opus-4.5",
    temperature=0.0,  # 0 = deterministic
    max_tokens=16384,
    cost_limit=10.0   # Cost limit in $
)
```

### Conversations (MANDATORY: keep history)

```python
# ALWAYS maintain full history
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What files are in /etc?"},
]

response = llm.chat(messages)
print(response.text)

# Add response to history
messages.append({"role": "assistant", "content": response.text})
messages.append({"role": "user", "content": "Which ones are for networking?"})

response = self.llm.chat(messages)
```

---

## Effective System Prompts

### Basic Structure

```python
SYSTEM_PROMPT = """You are a task-solving agent operating in a Linux terminal.

YOUR CAPABILITIES:
- Execute shell commands
- Read and write files
- Analyze output and errors

YOUR CONSTRAINTS:
- Only use standard Linux tools
- Do not access the internet
- Do not modify system files

RESPONSE FORMAT:
Respond with valid JSON:
{
    "thinking": "your reasoning",
    "command": "shell command to run",
    "task_complete": false
}
"""
```

### Do's and Don'ts

**Do:**
- Be specific about response format
- List available tools/capabilities
- Define constraints clearly
- Give examples of expected output format

**Don't:**
- Include task-specific hints
- Pre-define solutions for task types
- Give examples of specific task solutions
- Mention benchmark or evaluation

### Format-Focused Prompt

```python
SYSTEM_PROMPT = """You are a terminal agent. Respond ONLY with valid JSON.

Required format:
{
    "analysis": "Brief analysis of current state",
    "plan": "What you will do next",
    "commands": [
        {"keystrokes": "command here", "duration": 1.0}
    ],
    "task_complete": false
}

Rules:
1. "analysis" and "plan" are required strings
2. "commands" is an array (can be empty)
3. "task_complete" defaults to false
4. Use proper JSON escaping
5. No markdown, no explanations outside JSON
"""
```

---

## Response Parsing

### Robust JSON Parser

```python
import json
import re

class ResponseParser:
    def parse(self, text: str) -> dict | None:
        """Parse JSON from LLM response."""
        
        # Try direct parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Extract JSON from text
        json_str = self._extract_json(text)
        if not json_str:
            return None
        
        # Try parsing extracted JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Try fixing common issues
        fixed = self._fix_json(json_str)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None
    
    def _extract_json(self, text: str) -> str | None:
        """Extract JSON object from text."""
        # Find outermost braces
        start = text.find('{')
        if start == -1:
            return None
        
        depth = 0
        in_string = False
        escape = False
        
        for i, char in enumerate(text[start:], start):
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if char == '"' and not escape:
                in_string = not in_string
                continue
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]
        
        return None
    
    def _fix_json(self, json_str: str) -> str:
        """Fix common JSON issues."""
        # Remove trailing commas
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix single quotes
        # (This is naive - real impl should be smarter)
        
        return json_str
```

### Using the Parser

```python
def run(self, ctx: AgentContext):
    parser = ResponseParser()
    
    response = self.llm.chat(messages)
    data = parser.parse(response.text)
    
    if not data:
        ctx.log("Failed to parse response, asking for retry")
        messages.append({"role": "assistant", "content": response.text})
        messages.append({"role": "user", "content": "Invalid JSON. Please respond with valid JSON only."})
        continue
    
    # Use parsed data
    commands = data.get("commands", [])
```

---

## Error Handling

### LLM Errors

```python
from src.llm.client import LLMError, CostLimitExceeded

def call_llm_safe(self, messages: list, max_retries: int = 3) -> Response | None:
    """Call LLM with error handling."""
    
    for attempt in range(max_retries):
        try:
            return self.llm.chat(messages)
        
        except CostLimitExceeded as e:
            # Fatal - can't continue
            self.ctx.log(f"Cost limit exceeded: ${e.used:.2f}/${e.limit:.2f}")
            return None
        
        except LLMError as e:
            self.ctx.log(f"LLM error ({e.code}): {e.message}")
            
            if e.code == "rate_limit":
                # Wait and retry
                wait_time = 30 * (attempt + 1)
                self.ctx.log(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            elif e.code == "context_length":
                # Reduce context and retry
                self.ctx.log("Context too long, truncating...")
                messages = self._truncate_messages(messages)
                continue
            
            elif e.code in ("server_error", "service_unavailable"):
                # Transient, retry
                time.sleep(5 * (attempt + 1))
                continue
            
            else:
                # Unknown error
                if attempt == max_retries - 1:
                    return None
    
    return None
```

### Parse Errors

```python
def get_valid_response(self, ctx, messages: list, max_attempts: int = 3) -> dict | None:
    """Get a valid parsed response from LLM."""
    
    for attempt in range(max_attempts):
        response = self.call_llm_safe(messages)
        if not response:
            return None
        
        data = self.parser.parse(response.text)
        if data:
            return data
        
        # Ask for valid JSON
        ctx.log(f"Parse failed (attempt {attempt + 1})")
        messages.append({"role": "assistant", "content": response.text})
        messages.append({
            "role": "user",
            "content": "Your response was not valid JSON. Please respond with ONLY valid JSON, no other text."
        })
    
    return None
```

---

## Context Management

### Token Estimation

```python
def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token)."""
    return len(text) // 4

class ContextManager:
    def __init__(self, max_tokens: int = 50000):
        self.max_tokens = max_tokens
        self.messages = []
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self._enforce_limit()
    
    def _enforce_limit(self):
        total = sum(estimate_tokens(m["content"]) for m in self.messages)
        
        while total > self.max_tokens and len(self.messages) > 2:
            # Keep first (system) and remove oldest user/assistant
            removed = self.messages.pop(1)
            total -= estimate_tokens(removed["content"])
    
    def get_messages(self) -> list:
        return self.messages.copy()
```

### Sliding Window

```python
def run(self, ctx: AgentContext):
    # Keep only last N exchanges
    MAX_HISTORY = 10
    
    system_msg = {"role": "system", "content": SYSTEM_PROMPT}
    history = []
    
    while True:
        # Build messages with sliding window
        messages = [system_msg] + history[-MAX_HISTORY * 2:]
        
        response = self.llm.chat(messages)
        history.append({"role": "assistant", "content": response.text})
        
        # ... execute ...
        
        history.append({"role": "user", "content": output})
```

---

## Function Calling

### Defining Tools

```python
# Format OpenAI/litellm pour les outils

TOOLS = [
    Tool(
        name="execute_command",
        description="Run a shell command and return the output",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30)",
                    "default": 30
                }
            },
            "required": ["command"]
        }
    ),
    Tool(
        name="read_file",
        description="Read the contents of a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            "required": ["path"]
        }
    ),
    Tool(
        name="write_file",
        description="Write content to a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    ),
    Tool(
        name="task_complete",
        description="Mark the task as complete",
        parameters={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what was accomplished"
                }
            },
            "required": ["summary"]
        }
    )
]
```

### Implementing Tool Handlers

```python
class ToolHandler:
    def __init__(self, ctx: AgentContext):
        self.ctx = ctx
        self.completed = False
    
    def execute_command(self, command: str, timeout: int = 30) -> str:
        result = self.ctx.shell(command, timeout=timeout)
        output = result.output[-5000:]  # Truncate
        
        if result.timed_out:
            return f"[TIMEOUT after {timeout}s]\n{output}"
        
        status = "success" if result.ok else f"failed (exit {result.exit_code})"
        return f"[{status}]\n{output}"
    
    def read_file(self, path: str) -> str:
        result = self.ctx.read(path)
        if result.ok:
            return result.stdout[:10000]  # Truncate
        return f"Error reading file: {result.stderr}"
    
    def write_file(self, path: str, content: str) -> str:
        result = self.ctx.write(path, content)
        if result.ok:
            return f"Successfully wrote {len(content)} bytes to {path}"
        return f"Error writing file: {result.stderr}"
    
    def task_complete(self, summary: str) -> str:
        self.completed = True
        return f"Task marked complete: {summary}"
```

### Using Function Calling

```python
def run(self, ctx: AgentContext):
    handler = ToolHandler(ctx)
    
    # Register handlers
    self.llm.register_function("execute_command", handler.execute_command)
    self.llm.register_function("read_file", handler.read_file)
    self.llm.register_function("write_file", handler.write_file)
    self.llm.register_function("task_complete", handler.task_complete)
    
    messages = [
        {"role": "system", "content": "You are a task-solving agent with tools."},
        {"role": "user", "content": f"Task: {ctx.instruction}"}
    ]
    
    # Let LLM call functions automatically
    response = self.llm.chat_with_functions(
        messages,
        TOOLS,
        max_iterations=50
    )
    
    if handler.completed:
        ctx.done()
```

---

## Model Selection

### Supported Models

**All foundation models are supported** as long as they meet these criteria:

| Requirement | Allowed | Forbidden |
|-------------|---------|-----------|
| Model origin | Official provider releases | Community fine-tunes |
| Training | Base/instruct versions | Task-specific fine-tuning |
| Weights | Unmodified | Custom merged weights |

### Why No Community Fine-Tunes?

Community fine-tuned models are **forbidden** because they may:

- Be trained on benchmark data (data contamination)
- Have task-specific optimizations that constitute hardcoding
- Produce artificially inflated scores through overfitting

### Model Selection Strategy

```python
def setup(self):
    # Any official foundation model works
    # Examples: claude-3.5-sonnet, gpt-4o, deepseek-v3, llama-3, etc.
    self.llm = LLM(
        provider="openrouter",  # or any supported provider
        default_model="anthropic/claude-3.5-sonnet",
        temperature=0.3
    )
```

### Multi-Model Strategy

You can use different models for different purposes:

```python
def setup(self):
    # Strong model for complex reasoning
    self.reasoning_model = "anthropic/claude-3.5-sonnet"
    # Fast model for simple operations
    self.fast_model = "anthropic/claude-3-haiku"

def run(self, ctx: AgentContext):
    # Use strong model for planning
    plan = self.llm.ask(
        f"Task: {ctx.instruction}\nCreate a plan.",
        model=self.reasoning_model
    )
    
    # Use fast model for parsing
    parsed = self.llm.ask(
        f"Extract commands from:\n{plan.text}",
        model=self.fast_model
    )
```

---

---

## Prompt Caching

Prompt caching significantly reduces costs and latency by reusing previously processed prompts. The Term SDK supports caching via the `cache=True` parameter.

### Enabling Caching in Term SDK

```python
from src.llm.client import LiteLLMClient

class MyAgent(Agent):
    def setup(self):
        self.llm = LLM(
            provider="openrouter",
            default_model="anthropic/claude-3.5-sonnet",
            cache=True  # Enable prompt caching
        )
```

### How Caching Works by Provider

| Provider | Caching | Configuration |
|----------|---------|---------------|
| **OpenAI** | Automatic | No config needed, min 1024 tokens |
| **Anthropic** | Manual | Requires `cache_control` breakpoints |
| **DeepSeek** | Automatic | No config needed |
| **Google Gemini** | Automatic | No config needed, min 4096 tokens |
| **Groq** | Automatic | No config needed |

### Anthropic Cache Control (Important!)

Anthropic requires explicit `cache_control` breakpoints. This is critical for cost savings:

**Pricing:**
- **Cache writes**: 1.25x input price (slightly more expensive)
- **Cache reads**: 0.1x input price (90% savings!)

**TTL Options:**
- Default: 5 minutes
- Extended: 1 hour with `"ttl": "1h"`

### Anthropic Caching Example

```python
# Structure messages with cache_control for large content
messages = [
    {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": "You are a task-solving agent."
            },
            {
                "type": "text",
                "text": LARGE_SYSTEM_PROMPT,  # Cache this!
                "cache_control": {
                    "type": "ephemeral",
                    "ttl": "1h"  # Optional: extend to 1 hour
                }
            }
        ]
    },
    {
        "role": "user",
        "content": f"Task: {ctx.instruction}"
    }
]

response = self.llm.chat(messages)
```

### What to Cache

**Good candidates for caching:**
- Large system prompts
- Tool definitions
- Reference documentation
- Few-shot examples
- Context that stays constant across requests

**Don't cache:**
- Dynamic user input
- Changing context
- Small prompts (under 1024 tokens)

### Cache Placement Strategy

```python
# Put static content FIRST, dynamic content LAST
messages = [
    {
        "role": "system",
        "content": [
            # Static: Cache this large prompt
            {
                "type": "text",
                "text": STATIC_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}
            }
        ]
    },
    # Dynamic: User instruction (changes each task)
    {"role": "user", "content": ctx.instruction},
    # Dynamic: Previous outputs (change each iteration)
    {"role": "assistant", "content": last_response},
    {"role": "user", "content": command_output}
]
```

### Inspecting Cache Usage

```python
response = self.llm.chat(messages, usage=True)

# Check cache statistics
if response.usage:
    cached_tokens = response.usage.get("cached_tokens", 0)
    cache_discount = response.usage.get("cache_discount", 0)
    ctx.log(f"Cached: {cached_tokens} tokens, saved: ${cache_discount:.4f}")
```

### Cost Optimization Tips

1. **Keep static content first** - Cache hits require matching prefixes
2. **Use 1-hour TTL for long sessions** - Avoids repeated cache writes
3. **Batch related requests** - Maximize cache hits within TTL window
4. **Monitor cache_discount** - Negative = cache write, positive = savings

---

## Best Practices Summary

| Practice | Description |
|----------|-------------|
| Structured output | Always request JSON |
| Robust parsing | Handle malformed responses |
| Error handling | Retry transient failures |
| Context management | Bound history size |
| Token awareness | Truncate long outputs |
| Clear prompts | Specific format requirements |
| Tool definitions | Well-documented parameters |
| **Prompt caching** | Enable `cache=True`, use cache_control for Anthropic |
