"""
SuperAgent - An autonomous coding agent for Term Challenge.

Inspired by OpenAI Codex CLI, SuperAgent is designed to solve
terminal-based coding tasks autonomously using LLMs.

Usage with term_sdk:
    from term_sdk import run
    from superagent import SuperAgent
    
    run(SuperAgent())
"""

__version__ = "2.0.0"
__author__ = "Orion Team"

# Import main components for convenience
from superagent.config.defaults import CONFIG
from superagent.tools.registry import ToolRegistry
from superagent.output.jsonl import emit

__all__ = [
    "CONFIG",
    "ToolRegistry",
    "emit",
    "__version__",
]
