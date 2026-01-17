# Astuces - Building a High-Performance Agent

This folder contains practical tips and techniques used in BaseAgent to achieve high performance and cost efficiency on the Term Challenge benchmark.

These are battle-tested patterns learned from analyzing Codex CLI, OpenCode, and optimizing our own agent.

## Contents

1. [Prompt Caching](01-prompt-caching.md) - Achieve 90%+ cache hit rate
2. [Self-Verification](02-self-verification.md) - Validate work before completion
3. [Context Management](03-context-management.md) - Handle long conversations
4. [System Prompt Design](04-system-prompt-design.md) - Codex-inspired prompts
5. [Tool Output Handling](05-tool-output-handling.md) - Truncation strategies
6. [Autonomous Mode](06-autonomous-mode.md) - No questions, just execute
7. [Git Hygiene](07-git-hygiene.md) - Safe git operations
8. [Cost Optimization](08-cost-optimization.md) - Reduce API costs

## Quick Wins

| Technique | Impact | Effort |
|-----------|--------|--------|
| Prompt Caching | -80% cost | Medium |
| Self-Verification | +30% success | Low |
| Context Pruning | Prevents failures | Medium |
| Middle-out Truncation | Better context | Low |

## Key Metrics to Track

- **Cache hit rate**: Target >90%
- **Task completion rate**: Track success/failure
- **Average cost per task**: Monitor token usage
- **Turns per task**: Fewer is better
