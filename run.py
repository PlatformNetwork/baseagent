#!/usr/bin/env python3
"""
SuperAgent runner for Term Challenge.

This is a simple wrapper that runs the SuperAgent with term_sdk.
All configuration is hardcoded for benchmark mode.

Usage:
    python run.py
    
The instruction comes from term_sdk automatically - no arguments needed.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from term_sdk import run
from agent import SuperAgent

if __name__ == "__main__":
    run(SuperAgent())
