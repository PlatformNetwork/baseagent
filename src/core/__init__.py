"""Core module - agent loop, session management, and context compaction."""

from src.core.executor import (
    AgentExecutor,
    ExecutionResult,
    RiskLevel,
    SandboxPolicy,
)

# Compaction module (like OpenCode/Codex context management)
from src.core.compaction import (
    manage_context,
    estimate_tokens,
    estimate_message_tokens,
    estimate_total_tokens,
    is_overflow,
    needs_compaction,
    prune_old_tool_outputs,
    run_compaction,
    MODEL_CONTEXT_LIMIT,
    OUTPUT_TOKEN_MAX,
    AUTO_COMPACT_THRESHOLD,
    PRUNE_PROTECT,
    PRUNE_MINIMUM,
    PRUNE_MARKER,
)

# Import run_agent_loop
from src.core.loop import run_agent_loop

__all__ = [
    # Executor
    "AgentExecutor",
    "ExecutionResult",
    "RiskLevel",
    "SandboxPolicy",
    # Compaction
    "manage_context",
    "estimate_tokens",
    "estimate_message_tokens",
    "estimate_total_tokens",
    "is_overflow",
    "needs_compaction",
    "prune_old_tool_outputs",
    "run_compaction",
    "MODEL_CONTEXT_LIMIT",
    "OUTPUT_TOKEN_MAX",
    "AUTO_COMPACT_THRESHOLD",
    "PRUNE_PROTECT",
    "PRUNE_MINIMUM",
    "PRUNE_MARKER",
    # Loop
    "run_agent_loop",
]
