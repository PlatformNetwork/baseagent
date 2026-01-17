"""
BaseAgent - An autonomous coding agent for Term Challenge.

Inspired by OpenAI Codex CLI, BaseAgent is designed to solve
terminal-based coding tasks autonomously using LLMs.

Usage with term_sdk:
    from term_sdk import run
    from src import BaseAgent
    
    run(BaseAgent())
"""

__version__ = "1.0.0"
__author__ = "Platform Network"

# Import main components for convenience
from src.config.defaults import CONFIG
from src.tools.registry import ToolRegistry
from src.output.jsonl import emit

__all__ = [
    "CONFIG",
    "ToolRegistry",
    "emit",
    "__version__",
]
