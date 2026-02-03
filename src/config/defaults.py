"""
Hardcoded benchmark configuration for SuperAgent.

Default provider: Chutes API with Kimi K2.5-TEE model.
Supports thinking mode with <think>...</think> reasoning blocks.

Alternative providers available via LLM_PROVIDER environment variable:
- "chutes" (default): Chutes API with Kimi K2.5-TEE
- "openrouter": OpenRouter with Claude or other models

All settings are hardcoded - no CLI arguments needed.
"""

from __future__ import annotations

import os
from typing import Any, Dict


# Main configuration - default to Chutes API with Kimi K2.5-TEE
CONFIG: Dict[str, Any] = {
    # ==========================================================================
    # Model Settings - Chutes API with Kimi K2.5-TEE
    # ==========================================================================
    
    # Model to use via Chutes API
    # Kimi K2.5-TEE: 1T params (32B activated), 256K context window
    # Supports thinking mode with reasoning_content
    "model": os.environ.get("LLM_MODEL", "moonshotai/Kimi-K2.5-TEE"),
    
    # Provider: "chutes" for Chutes API, "openrouter" for litellm/OpenRouter
    "provider": os.environ.get("LLM_PROVIDER", "chutes"),
    
    # Enable Kimi K2.5 thinking mode (reasoning in thinking blocks)
    "enable_thinking": True,
    
    # Token limits (Kimi K2.5 supports up to 32K output)
    "max_tokens": 16384,
    
    # Temperature - Kimi K2.5 best practices:
    # - Thinking mode: 1.0 (with top_p=0.95)
    # - Instant mode: 0.6 (with top_p=0.95)
    "temperature": 1.0,
    
    # Cost limit in USD
    "cost_limit": 100.0,
    
    # ==========================================================================
    # Agent Execution Settings
    # ==========================================================================
    
    # Maximum iterations before stopping
    "max_iterations": 350,
    
    # Maximum tokens for tool output truncation (middle-out strategy)
    "max_output_tokens": 2500,  # ~10KB
    
    # Timeout for shell commands (seconds)
    "shell_timeout": 60,
    
    # ==========================================================================
    # Context Management (like OpenCode/Codex)
    # ==========================================================================
    
    # Model context window (Kimi K2.5 = 256K)
    "model_context_limit": 256_000,
    
    # Reserved tokens for output (Kimi K2.5 can output up to 32K)
    "output_token_max": 32_000,
    
    # Trigger compaction at this % of usable context (85%)
    "auto_compact_threshold": 0.85,
    
    # Tool output pruning constants (from OpenCode)
    "prune_protect": 40_000,   # Protect this many tokens of recent tool output
    "prune_minimum": 20_000,   # Only prune if we can recover at least this many
    
    # ==========================================================================
    # Prompt Caching
    # ==========================================================================
    
    # Enable prompt caching (Chutes may support server-side caching)
    "cache_enabled": True,
    
    # Chutes API caching notes:
    # - Kimi K2.5 on Chutes uses server-side optimization
    # - Keep system prompt stable for best performance
    "cache_extended_retention": True,
    "cache_key": None,
    
    # ==========================================================================
    # Simulated Codex Flags (all enabled/bypassed for benchmark)
    # ==========================================================================
    
    # --dangerously-bypass-approvals-and-sandbox
    "bypass_approvals": True,
    "bypass_sandbox": True,
    
    # --skip-git-repo-check
    "skip_git_check": True,
    
    # --enable unified_exec
    "unified_exec": True,
    
    # --json (always JSONL output)
    "json_output": True,
    
    # ==========================================================================
    # Double Confirmation for Task Completion
    # ==========================================================================
    
    # Require double confirmation before marking task complete
    # Disabled for fully autonomous operation in evaluation mode
    "require_completion_confirmation": False,
}


def get_config() -> Dict[str, Any]:
    """Get the configuration dictionary."""
    return CONFIG.copy()


def get(key: str, default: Any = None) -> Any:
    """Get a configuration value."""
    return CONFIG.get(key, default)
