# BaseAgent

A high-performance autonomous coding agent built for the [Term Challenge](https://term.challenge) benchmark platform. BaseAgent is designed to compete with state-of-the-art agents like Codex CLI and OpenCode in both performance and cost efficiency.

## Overview

BaseAgent is an autonomous terminal-based coding assistant that:
- Executes shell commands to explore and modify systems
- Reads, writes, and patches files with surgical precision
- Searches codebases using ripgrep for fast pattern matching
- Validates its own work before signaling completion
- Manages context efficiently with intelligent compaction

## Key Features

### Codex-Inspired System Prompt

The system prompt is carefully crafted based on OpenAI's Codex CLI prompts, including:

- **AGENTS.md Support**: Respects repository-level agent instructions
- **Preamble Messages**: Concise updates before tool calls (8-12 words)
- **Git Worktree Hygiene**: Never reverts uncommitted changes, avoids destructive commands
- **Frontend Task Guidelines**: Avoids "AI slop" with intentional, bold designs
- **Review Mindset**: Prioritizes bugs, risks, and regressions when reviewing code
- **Structured Final Answers**: Clean formatting with headers, bullets, and file references

### Prompt Caching (Anthropic)

Implements intelligent prompt caching for significant cost reduction:

```python
# Cache breakpoints:
# 1. System prompt (stable across turns)
# 2. Last 2 non-system messages (extends cache to conversation history)
```

This achieves **90%+ cache hit rates** on long conversations, similar to Codex CLI's approach.

### Self-Verification System

Before completing any task, the agent automatically:

1. Re-reads the original instruction
2. Creates a verification checklist of all requirements
3. Runs commands to verify each requirement is met
4. Only signals completion after all verifications pass

### Context Management

Intelligent context management prevents token overflow:

- **Token-based overflow detection** (not message count)
- **Tool output pruning** (clears old outputs first)
- **AI compaction** when needed (summarizes conversation history)
- **Middle-out truncation** for large outputs

## Architecture

```
baseagent/
├── agent.py              # Entry point for Term SDK
├── superagent/
│   ├── core/
│   │   ├── loop.py       # Main agent loop with caching
│   │   ├── compaction.py # Context management
│   │   ├── session.py    # Message history
│   │   └── agent.py      # High-level agent interface
│   ├── tools/
│   │   ├── specs.py      # Tool JSON schemas
│   │   ├── registry.py   # Tool execution dispatch
│   │   ├── shell.py      # Shell command execution
│   │   ├── apply_patch.py # File patching
│   │   ├── read_file.py  # File reading
│   │   ├── write_file.py # File writing
│   │   ├── grep_files.py # Content search (ripgrep)
│   │   ├── list_dir.py   # Directory listing
│   │   └── view_image.py # Image analysis
│   ├── prompts/
│   │   └── system.py     # Codex-based system prompt
│   ├── api/
│   │   └── client.py     # LLM API client
│   └── output/
│       └── jsonl.py      # JSONL event emission
```

## Tools

| Tool | Description |
|------|-------------|
| `shell_command` | Execute shell commands with workdir support |
| `read_file` | Read files with line numbers and pagination |
| `write_file` | Create or overwrite files |
| `apply_patch` | Apply patches to create/update/delete files |
| `grep_files` | Search file contents with ripgrep |
| `list_dir` | List directory contents with depth control |
| `view_image` | Load and analyze images (PNG, JPEG, GIF, WebP) |
| `update_plan` | Track task progress with step statuses |

## Usage with Term SDK

BaseAgent is designed to work with the [Term SDK](https://github.com/ArcadeLabsInc/term-sdk):

```python
from term_sdk import AgentContext

def run(ctx: AgentContext) -> str:
    """Main entry point called by Term SDK."""
from src.core.loop import run_agent_loop
    return run_agent_loop(ctx)
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | API key for OpenRouter (default provider) |
| `ANTHROPIC_API_KEY` | API key for Anthropic direct |

## Configuration

Configuration is defined in `superagent/config/defaults.py`:

```python
# Key settings
MAX_CONTEXT_TOKENS = 180000      # Max tokens before compaction
COMPACTION_THRESHOLD = 0.85      # Trigger compaction at 85% capacity
PRUNE_THRESHOLD = 0.70           # Target 70% after pruning
SHELL_TIMEOUT_MS = 120000        # 2 minute timeout for commands
MAX_OUTPUT_BYTES = 51200         # 50KB max output per tool
```

Note: The agent uses Term SDK's LLM interface, so model selection is handled by the Term Challenge platform.

## Development

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/PlatformNetwork/baseagent.git
cd baseagent

# Install dependencies
uv sync

# Or with pip
pip install -e .
```

### Running Tests

```bash
uv run pytest tests/
```

### Local Testing

```bash
# Run with a test instruction
python -c "
from superagent.core.loop import run_agent_loop
from unittest.mock import MagicMock

ctx = MagicMock()
ctx.instruction = 'List the files in the current directory'
ctx.cwd = '/tmp'
ctx.llm = ...  # Your LLM instance

result = run_agent_loop(ctx)
print(result)
"
```

## Benchmarks

BaseAgent is optimized for the Term Challenge benchmark:

| Metric | Target | Notes |
|--------|--------|-------|
| Cache Hit Rate | >90% | Via prompt caching |
| Task Completion | High | Self-verification ensures quality |
| Cost Efficiency | Low | Caching + context management |

## Documentation

### Rules - Agent Development Guidelines

See the [rules/](rules/) folder for comprehensive guides on building autonomous agents:

- [What is a Generalist Agent](rules/01-what-is-generalist-agent.md)
- [Architecture Patterns](rules/02-architecture-patterns.md)
- [Allowed vs Forbidden](rules/03-allowed-vs-forbidden.md)
- [Anti-Patterns](rules/04-anti-patterns.md)
- [Best Practices](rules/05-best-practices.md)
- [LLM Usage Guide](rules/06-llm-usage-guide.md)
- [Tool Design](rules/07-tool-design.md)
- [Error Handling](rules/08-error-handling.md)
- [Testing Your Agent](rules/09-testing-your-agent.md)
- [Checklist](rules/10-checklist.md)

### Astuces - Practical Techniques

See the [astuces/](astuces/) folder for battle-tested techniques used in BaseAgent:

- [Prompt Caching](astuces/01-prompt-caching.md) - Achieve 90%+ cache hit rate
- [Self-Verification](astuces/02-self-verification.md) - Validate work before completion
- [Context Management](astuces/03-context-management.md) - Handle long conversations
- [System Prompt Design](astuces/04-system-prompt-design.md) - Codex-inspired prompts
- [Tool Output Handling](astuces/05-tool-output-handling.md) - Truncation strategies
- [Autonomous Mode](astuces/06-autonomous-mode.md) - No questions, just execute
- [Git Hygiene](astuces/07-git-hygiene.md) - Safe git operations
- [Cost Optimization](astuces/08-cost-optimization.md) - Reduce API costs
- [Local Testing](astuces/09-local-testing.md) - Using Term Challenge

## Credits

- **System Prompt**: Based on [Codex CLI](https://github.com/openai/codex) by OpenAI
- **Architecture**: Inspired by [OpenCode](https://github.com/anomalyco/opencode) patterns
- **SDK**: Built on [Term SDK](https://github.com/PlatformNetwork/term-challenge)

## License

MIT License - see [LICENSE](LICENSE) for details.
