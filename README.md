# BaseAgent - SDK 3.0

High-performance autonomous agent for [Term Challenge](https://term.challenge). **Does NOT use term_sdk** - fully autonomous with litellm.

## Installation

```bash
# Via pyproject.toml
pip install .

# Via requirements.txt
pip install -r requirements.txt
```

## Usage

```bash
python agent.py --instruction "Your task here..."
```

The agent receives the instruction via `--instruction` and executes the task autonomously.

## Mandatory Architecture

> **IMPORTANT**: Agents MUST follow these rules to work correctly.

### 1. Project Structure (MANDATORY)

Agents **MUST** be structured projects, NOT single files:

```
my-agent/
├── agent.py              # Entry point with --instruction
├── src/                  # Modules
│   ├── core/
│   │   ├── loop.py       # Main loop
│   │   └── compaction.py # Context management (MANDATORY)
│   ├── llm/
│   │   └── client.py     # LLM client (litellm)
│   └── tools/
│       └── ...           # Available tools
├── requirements.txt      # Dependencies
└── pyproject.toml        # Project config
```

### 2. Session Management (MANDATORY)

Agents **MUST** maintain complete conversation history:

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": instruction},
]

# Add each exchange
messages.append({"role": "assistant", "content": response})
messages.append({"role": "tool", "tool_call_id": id, "content": result})
```

### 3. Context Compaction (MANDATORY)

Compaction is **CRITICAL** for:
- Avoiding "context too long" errors
- Preserving critical information
- Enabling complex multi-step tasks
- Improving response coherence

```python
# Recommended threshold: 85% of context window
AUTO_COMPACT_THRESHOLD = 0.85

# 2-step strategy:
# 1. Pruning: Remove old tool outputs
# 2. AI Compaction: Summarize conversation if pruning insufficient
```

## Features

### LLM Client (litellm)

```python
from src.llm.client import LiteLLMClient

llm = LiteLLMClient(
    model="openrouter/anthropic/claude-opus-4.5",
    temperature=0.0,
    max_tokens=16384,
)

response = llm.chat(messages, tools=tool_specs)
```

### Prompt Caching

Caches system and recent messages to reduce costs:
- Cache hit rate: **90%+** on long conversations
- Significant API cost reduction

### Self-Verification

Before completing, the agent automatically:
1. Re-reads the original instruction
2. Verifies each requirement
3. Only confirms completion if everything is validated

### Context Management

- **Token-based overflow detection** (not message count)
- **Tool output pruning** (removes old outputs)
- **AI compaction** (summarizes if needed)
- **Middle-out truncation** for large outputs

## Available Tools

| Tool | Description |
|------|-------------|
| `shell_command` | Execute shell commands |
| `read_file` | Read files with pagination |
| `write_file` | Create/overwrite files |
| `apply_patch` | Apply patches |
| `grep_files` | Search with ripgrep |
| `list_dir` | List directories |
| `view_image` | Analyze images |

## Configuration

See `src/config/defaults.py`:

```python
CONFIG = {
    "model": "openrouter/anthropic/claude-opus-4.5",
    "max_tokens": 16384,
    "max_iterations": 200,
    "auto_compact_threshold": 0.85,
    "prune_protect": 40_000,
    "cache_enabled": True,
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key |

## Documentation

### Rules - Development Guidelines

See [rules/](rules/) for comprehensive guides:

- [Architecture Patterns](rules/02-architecture-patterns.md) - **Mandatory project structure**
- [LLM Usage Guide](rules/06-llm-usage-guide.md) - **Using litellm**
- [Best Practices](rules/05-best-practices.md)
- [Error Handling](rules/08-error-handling.md)

### Tips - Practical Techniques

See [astuces/](astuces/) for techniques:

- [Prompt Caching](astuces/01-prompt-caching.md)
- [Context Management](astuces/03-context-management.md)
- [Local Testing](astuces/09-local-testing.md)

## License

MIT License - see [LICENSE](LICENSE).
