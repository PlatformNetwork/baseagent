# Self-Verification - Validate Work Before Completion

## The Problem

Agents often declare "task complete" prematurely:
- Forgot a requirement from the original instruction
- Didn't test the code they wrote
- Made assumptions that weren't verified

This leads to failed benchmarks even when the agent "tried" to complete the task.

## The Solution

Before allowing the agent to complete, inject a verification prompt that forces it to:
1. Re-read the original instruction
2. Check each requirement
3. Only complete after verification passes

## Implementation

```python
async def run_agent_loop(ctx: Any) -> str:
    """Main agent loop with self-verification."""
    
    while True:
        response = await call_llm(messages)
        
        # Check if agent wants to complete (no tool calls)
        if not response.has_function_calls():
            
            # CRITICAL: Inject verification before allowing completion
            if not verification_done:
                verification_prompt = f'''
STOP - Before completing, you MUST verify your work:

Original instruction: {ctx.instruction}

Verification checklist:
1. Re-read the original instruction above
2. List ALL requirements (explicit and implicit)
3. For EACH requirement, run a command to verify it's satisfied
4. If ANY requirement is NOT met, fix it now

Do NOT say "task complete" until all verifications pass.

CRITICAL: You are in headless mode - no user to ask questions.
'''
                messages.append({"role": "user", "content": verification_prompt})
                verification_done = True
                continue  # Get another response
            
            # Verification done, actually complete
            return response.text
        
        # Execute tool calls...
```

## What to Verify

### For Code Tasks
- Does the code compile/run?
- Do tests pass?
- Does the output match expected format?
- Are all files created that were requested?

### For Build Tasks
- Does the binary exist?
- Is it executable?
- Does it produce expected output?

### For File Tasks
- Do all expected files exist?
- Is the content correct?
- Are permissions set correctly?

## Verification Prompt Template

```
VERIFICATION CHECKLIST for: "{original_instruction}"

Requirements identified:
1. [Explicit requirement 1]
2. [Explicit requirement 2]
3. [Implicit requirement - e.g., "build" implies runnable binary]

Verification commands:
- [ ] Check 1: `command to verify`
- [ ] Check 2: `command to verify`
- [ ] Check 3: `command to verify`

ONLY signal completion after ALL checks pass.
If any check fails, FIX IT before completing.
```

## Common Verification Commands

```bash
# Check file exists
test -f /path/to/file && echo "OK" || echo "MISSING"

# Check binary is executable
test -x ./binary && ./binary --version

# Check code compiles
python -m py_compile script.py

# Check tests pass
pytest tests/ -v

# Check output matches
diff expected.txt actual.txt

# Check directory structure
find . -type f -name "*.py" | head -20
```

## Impact

| Metric | Without Verification | With Verification |
|--------|---------------------|-------------------|
| Task Success Rate | ~60% | ~85% |
| False Completions | High | Near Zero |
| User Trust | Low | High |

## Edge Cases

### Headless Mode
In autonomous/headless mode, the agent cannot ask questions. The verification prompt must remind it:

```
CRITICAL: You are in headless mode.
- Do NOT ask questions
- Do NOT wait for user input
- Make reasonable decisions and proceed
- If something is unclear, pick the most sensible option
```

### Infinite Loops
Add a maximum verification attempts counter:

```python
max_verification_attempts = 3
if verification_attempts >= max_verification_attempts:
    log("Max verification attempts reached, completing anyway")
    return response.text
```

### Large Tasks
For tasks with many requirements, group verifications:

```
Phase 1: Core functionality
Phase 2: Edge cases
Phase 3: Documentation/cleanup
```
