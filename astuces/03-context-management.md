# Context Management - Handle Long Conversations

## The Problem

Long-running tasks accumulate context:
- Tool outputs (shell results, file contents)
- Previous assistant messages
- Error messages and retries

Eventually, you hit the model's context limit and the request fails.

## Strategy Overview

```
Context Usage:  [============================-----] 85%
                ↓
Step 1: PRUNE tool outputs (keep last N)
                ↓
Context Usage:  [====================-------------] 60%
                ↓
If still high: COMPACT via AI summarization
                ↓
Context Usage:  [============---------------------] 35%
```

## Token Estimation

Quick estimation without a tokenizer:

```python
APPROX_CHARS_PER_TOKEN = 4

def estimate_tokens(text: str) -> int:
    """Estimate token count from text."""
    if not text:
        return 0
    return len(text) // APPROX_CHARS_PER_TOKEN + 1

def estimate_message_tokens(msg: dict) -> int:
    """Estimate tokens in a message."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return estimate_tokens(content)
    elif isinstance(content, list):
        return sum(
            estimate_tokens(part.get("text", ""))
            for part in content
            if part.get("type") == "text"
        )
    return 0
```

## Step 1: Prune Tool Outputs

Tool outputs are the biggest context consumers. Strategy:
- Keep only the **last N tool results**
- Replace old results with "[output pruned]"

```python
def prune_tool_outputs(messages: List[Dict], keep_last: int = 5) -> List[Dict]:
    """Replace old tool outputs with placeholder."""
    result = []
    
    # Find tool result messages
    tool_results = [
        (i, m) for i, m in enumerate(messages)
        if m.get("role") == "tool"
    ]
    
    # Mark old ones for pruning
    to_prune = {i for i, _ in tool_results[:-keep_last]}
    
    for i, msg in enumerate(messages):
        if i in to_prune:
            result.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id"),
                "content": "[output pruned - context limit]"
            })
        else:
            result.append(msg)
    
    return result
```

## Step 2: AI Compaction

When pruning isn't enough, summarize the conversation:

```python
COMPACTION_PROMPT = '''Summarize this conversation concisely.
Focus on:
- What task was requested
- What has been accomplished
- Current state (files modified, errors encountered)
- What remains to be done

Be brief but preserve critical details like file paths and error messages.'''

async def compact_messages(messages: List[Dict], llm) -> List[Dict]:
    """Use LLM to summarize conversation history."""
    
    # Keep system message and last few messages intact
    system_msgs = [m for m in messages if m.get("role") == "system"]
    recent_msgs = messages[-4:]  # Keep last 4
    middle_msgs = messages[len(system_msgs):-4]
    
    # Summarize the middle
    summary_request = [
        {"role": "system", "content": COMPACTION_PROMPT},
        {"role": "user", "content": format_messages_for_summary(middle_msgs)}
    ]
    
    summary = await llm.chat(summary_request)
    
    # Reconstruct with summary
    return system_msgs + [
        {"role": "user", "content": f"[Previous conversation summary]\n{summary}"}
    ] + recent_msgs
```

## Thresholds

```python
MAX_CONTEXT_TOKENS = 180000  # Model limit
PRUNE_THRESHOLD = 0.70       # 70% - start pruning
COMPACT_THRESHOLD = 0.85     # 85% - do AI compaction
CRITICAL_THRESHOLD = 0.95    # 95% - emergency measures
```

## The Full Flow

```python
def manage_context(messages: List[Dict], max_tokens: int) -> List[Dict]:
    """Manage context to stay within limits."""
    
    current = estimate_total_tokens(messages)
    
    # Stage 1: Prune tool outputs
    if current > max_tokens * PRUNE_THRESHOLD:
        messages = prune_tool_outputs(messages, keep_last=5)
        current = estimate_total_tokens(messages)
    
    # Stage 2: Prune more aggressively
    if current > max_tokens * COMPACT_THRESHOLD:
        messages = prune_tool_outputs(messages, keep_last=2)
        current = estimate_total_tokens(messages)
    
    # Stage 3: AI compaction
    if current > max_tokens * COMPACT_THRESHOLD:
        messages = await compact_messages(messages)
    
    return messages
```

## Tool Output Truncation

For individual large outputs, use middle-out truncation:

```python
def middle_out_truncate(text: str, max_bytes: int = 50000) -> str:
    """Keep start and end, remove middle."""
    if len(text) <= max_bytes:
        return text
    
    keep_each = max_bytes // 2 - 50
    
    return (
        text[:keep_each] +
        f"\n\n[... {len(text) - max_bytes} bytes truncated ...]\n\n" +
        text[-keep_each:]
    )
```

Why middle-out? Because:
- Start has command output headers
- End has the final result/error
- Middle is often repetitive (logs, progress)

## Monitoring

Log context usage for debugging:

```python
def log_context_status(messages, max_tokens):
    tokens = estimate_total_tokens(messages)
    pct = tokens / max_tokens * 100
    print(f"[context] {tokens}/{max_tokens} tokens ({pct:.1f}%)")
```
