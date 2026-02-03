#!/usr/bin/env python3
"""
SuperAgent for Term Challenge - Entry Point (SDK 3.0 Compatible).

This agent accepts --instruction from the validator and runs autonomously.
Supports multiple LLM providers:
- Chutes API (default): Uses moonshotai/Kimi-K2.5-TEE with thinking mode
- OpenRouter/litellm: Fallback to other providers

Installation:
    pip install .                    # via pyproject.toml
    pip install -r requirements.txt  # via requirements.txt

Usage:
    # With Chutes API (default - requires CHUTES_API_TOKEN)
    export CHUTES_API_TOKEN="your-token"
    python agent.py --instruction "Your task description here..."
    
    # With OpenRouter (fallback)
    export LLM_PROVIDER="openrouter"
    export OPENROUTER_API_KEY="your-key"
    python agent.py --instruction "Your task description here..."
"""

from __future__ import annotations

import argparse
import sys
import time
import os
import subprocess
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Auto-install dependencies if missing
def ensure_dependencies():
    """Install dependencies if not present."""
    try:
        import openai
        import httpx
        import pydantic
    except ImportError:
        print("[setup] Installing dependencies...", file=sys.stderr)
        agent_dir = Path(__file__).parent
        req_file = agent_dir / "requirements.txt"
        if req_file.exists():
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"], check=True)
        else:
            subprocess.run([sys.executable, "-m", "pip", "install", str(agent_dir), "-q"], check=True)
        print("[setup] Dependencies installed", file=sys.stderr)

ensure_dependencies()

from src.config.defaults import CONFIG
from src.core.loop import run_agent_loop
from src.tools.registry import ToolRegistry
from src.output.jsonl import emit, ErrorEvent
from src.llm.client import get_llm_client, CostLimitExceeded, ChutesClient, LiteLLMClient


class AgentContext:
    """Minimal context for agent execution (replaces term_sdk.AgentContext)."""
    
    def __init__(self, instruction: str, cwd: str = None):
        self.instruction = instruction
        self.cwd = cwd or os.getcwd()
        self.step = 0
        self.is_done = False
        self.history = []
        self._start_time = time.time()
    
    @property
    def elapsed_secs(self) -> float:
        return time.time() - self._start_time
    
    def shell(self, cmd: str, timeout: int = 120) -> "ShellResult":
        """Execute a shell command."""
        self.step += 1
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cwd,
            )
            output = result.stdout + result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            output = "[TIMEOUT]"
            exit_code = -1
        except Exception as e:
            output = f"[ERROR] {e}"
            exit_code = -1
        
        shell_result = ShellResult(output=output, exit_code=exit_code)
        self.history.append({
            "step": self.step,
            "command": cmd,
            "output": output[:1000],
            "exit_code": exit_code,
        })
        return shell_result
    
    def done(self):
        """Mark task as complete."""
        self.is_done = True
    
    def log(self, msg: str):
        """Log a message."""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [ctx] {msg}", file=sys.stderr, flush=True)


class ShellResult:
    """Result from shell command."""
    
    def __init__(self, output: str, exit_code: int):
        self.output = output
        self.stdout = output
        self.stderr = ""
        self.exit_code = exit_code
    
    def has(self, text: str) -> bool:
        return text in self.output


def _log(msg: str):
    """Log to stderr."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [superagent] {msg}", file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description="SuperAgent for Term Challenge SDK 3.0")
    parser.add_argument("--instruction", required=True, help="Task instruction from validator")
    args = parser.parse_args()
    
    provider = CONFIG.get("provider", "chutes")
    
    _log("=" * 60)
    _log(f"SuperAgent Starting (SDK 3.0 - {provider})")
    _log("=" * 60)
    _log(f"Provider: {provider}")
    _log(f"Model: {CONFIG['model']}")
    _log(f"Thinking mode: {CONFIG.get('enable_thinking', True)}")
    _log(f"Instruction: {args.instruction[:200]}...")
    _log("-" * 60)
    
    # Initialize components
    start_time = time.time()
    
    # Use factory function to get appropriate client based on provider
    llm = get_llm_client(
        provider=provider,
        model=CONFIG["model"],
        temperature=CONFIG.get("temperature"),
        max_tokens=CONFIG.get("max_tokens", 16384),
        cost_limit=CONFIG.get("cost_limit", 100.0),
        enable_thinking=CONFIG.get("enable_thinking", True),
        cache_extended_retention=CONFIG.get("cache_extended_retention", True),
        cache_key=CONFIG.get("cache_key"),
    )
    
    tools = ToolRegistry()
    ctx = AgentContext(instruction=args.instruction)
    
    _log("Components initialized")
    
    try:
        run_agent_loop(
            llm=llm,
            tools=tools,
            ctx=ctx,
            config=CONFIG,
        )
    except CostLimitExceeded as e:
        _log(f"Cost limit exceeded: {e}")
        emit(ErrorEvent(message=f"Cost limit exceeded: {e}"))
    except Exception as e:
        _log(f"Fatal error: {e}")
        emit(ErrorEvent(message=str(e)))
        raise
    finally:
        elapsed = time.time() - start_time
        try:
            stats = llm.get_stats()
            _log(f"Total tokens: {stats.get('total_tokens', 0)}")
            _log(f"Total cost: ${stats.get('total_cost', 0):.4f}")
            _log(f"Requests: {stats.get('request_count', 0)}")
        except Exception as e:
            _log(f"Stats error: {e}")
        _log(f"Elapsed: {elapsed:.1f}s")
        _log("Agent finished")
        _log("=" * 60)


if __name__ == "__main__":
    main()
