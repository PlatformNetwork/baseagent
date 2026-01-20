# Local Testing - Using Term Challenge

## Overview

[Term Challenge](https://github.com/PlatformNetwork/term-challenge) is the benchmark platform for testing autonomous agents. It provides:
- A Python SDK for agent development
- Local testing infrastructure
- Task runner with metrics collection

## Installation

```bash
# Clone the Term Challenge repo
git clone https://github.com/PlatformNetwork/term-challenge.git
cd term-challenge

# Install the SDK
pip install -e sdk/python/
```

## Project Structure

```
term-challenge/
├── sdk/
│   └── python/
│       └── term_sdk/
│           ├── __init__.py
│           ├── context.py      # Any
│           ├── llm.py          # LLM interface
│           └── errors.py       # CostLimitExceeded, etc.
├── tasks/                      # Benchmark tasks
└── src/                        # Platform backend
```

## The Term SDK

### Any

Your agent receives an `Any` with:

```python
from term_sdk import Any

def run(ctx: Any) -> str:
    # Available attributes:
    ctx.instruction  # The task to complete
    ctx.cwd          # Working directory
    ctx.llm          # LLM interface for API calls
    
    # Your agent logic here
    return "Task completed"
```

### LLM Interface

The SDK provides an LLM wrapper:

```python
# Make API calls through the SDK
response = ctx.llm.chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": ctx.instruction}
    ],
    tools=[...],  # Tool definitions
    model="anthropic/claude-sonnet-4"
)

# Response contains:
response.text           # Assistant's text response
response.function_calls # List of tool calls
response.usage          # Token usage stats
```

### Error Handling

```python
from term_sdk import CostLimitExceeded, LLMError

try:
    response = ctx.llm.chat(messages)
except CostLimitExceeded:
    return "Task aborted: cost limit reached"
except LLMError as e:
    return f"LLM error: {e}"
```

## Running Tests Locally

### Method 1: Direct Python

```python
# test_agent.py
from unittest.mock import MagicMock
from src.core.loop import run_agent_loop

# Create mock context
ctx = MagicMock()
ctx.instruction = "Create a file called hello.txt with 'Hello World'"
ctx.cwd = "/tmp/test_workspace"

# Mock the LLM (or use real API)
ctx.llm = create_mock_llm()  # or RealLLM(api_key="...")

# Run
result = run_agent_loop(ctx)
print(result)
```

### Method 2: Using Term Bench CLI

```bash
# From term-challenge repo
cd term-challenge

# Run a single task
python -m term_bench run \
    --agent /path/to/baseagent \
    --task tasks/simple/hello_world.yaml

# Run multiple tasks
python -m term_bench run \
    --agent /path/to/baseagent \
    --tasks tasks/simple/*.yaml \
    --parallel 4
```

### Method 3: Docker Container

```bash
# Build the test container
docker build -t baseagent-test .

# Run with task
docker run -v $(pwd)/tasks:/tasks baseagent-test \
    python -m term_bench run --task /tasks/hello.yaml
```

## Creating Test Tasks

Task files are YAML:

```yaml
# tasks/my_test.yaml
name: "Create Python Script"
instruction: |
  Create a Python script called fib.py that computes
  the first 10 Fibonacci numbers and prints them.
  
expected_files:
  - fib.py

validation:
  - command: "python fib.py"
    expect_output: "0 1 1 2 3 5 8 13 21 34"

timeout: 300  # 5 minutes
cost_limit: 5.0  # $5 max
```

## Debugging Failures

### Enable Verbose Logging

```python
import sys

def _log(msg: str):
    print(f"[DEBUG] {msg}", file=sys.stderr, flush=True)

# Add throughout your agent
_log(f"Received instruction: {ctx.instruction}")
_log(f"Tool result: {result[:200]}...")
```

### Inspect Message History

```python
def debug_messages(messages):
    for i, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content", "")[:100]
        print(f"[{i}] {role}: {content}...")
```

### Check Token Usage

```python
def log_usage(response):
    usage = response.usage
    print(f"Tokens: {usage.get('input_tokens')} in, {usage.get('output_tokens')} out")
    print(f"Cached: {usage.get('cache_read_input_tokens', 0)}")
```

## Common Issues

### 1. Import Errors

```
ModuleNotFoundError: No module named 'term_sdk'
```

**Fix**: Install the SDK
```bash
pip install -e /path/to/term-challenge/sdk/python/
```

### 2. Context Too Long

```
Error: context_length_exceeded
```

**Fix**: Enable context management
```python
messages = manage_context(messages, max_tokens=180000)
```

### 3. Cost Limit Hit

```
CostLimitExceeded: Task exceeded $5.00 budget
```

**Fix**: Enable prompt caching, reduce context

### 4. Timeout

```
Task timed out after 300 seconds
```

**Fix**: Add progress tracking, optimize long operations

## CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Test Agent

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install -e path/to/term-challenge/sdk/python/
      
      - name: Run tests
        run: |
          python -m pytest tests/
          python -m term_bench run --agent . --tasks tests/tasks/*.yaml
```
