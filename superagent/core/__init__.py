"""Core module - agent loop, session management, and context compaction."""

# Executor doesn't need term_sdk
from superagent.core.executor import (
    AgentExecutor,
    ExecutionResult,
    RiskLevel,
    SandboxPolicy,
)

# Compaction module (like OpenCode/Codex context management)
from superagent.core.compaction import (
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

# Note: run_agent_loop requires term_sdk which is only available at runtime
# in the term challenge environment. Import it directly when needed:
# from superagent.core.loop import run_agent_loop

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
]
