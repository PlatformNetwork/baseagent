"""Prompt templates for SuperAgent."""

from __future__ import annotations

# Template for plan updates
PLAN_UPDATE_TEMPLATE = """
Current plan:
{current_plan}

Please update the plan based on recent actions and findings.
"""

# Template for reasoning
REASONING_TEMPLATE = """
Please analyze the current situation and decide on the next steps.
Consider:
1. What has been done so far?
2. What information is missing?
3. What is the most efficient way to proceed?
"""
