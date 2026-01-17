# 10 - Pre-Submission Checklist

Use this checklist before every submission to ensure your agent meets all requirements.

---

## Quick Validation Commands

Run these commands to validate your agent:

```bash
# 1. Syntax check
python -m py_compile my_agent.py && echo "Syntax: OK"

# 2. Import check
python -c "from my_agent import MyAgent" && echo "Imports: OK"

# 3. Instantiation check
python -c "from my_agent import MyAgent; a = MyAgent(); a.setup(); a.cleanup()" && echo "Init: OK"

# 4. Basic test
term bench agent -a ./my_agent.py -t ./test-task --timeout 60
```

---

## Mandatory Requirements

### A. Agent Structure

| Requirement | Check | How to Verify |
|-------------|-------|---------------|
| Extends `Agent` class | [ ] | `grep "class.*Agent" my_agent.py` |
| Has `setup()` method | [ ] | `grep "def setup" my_agent.py` |
| Has `run()` method | [ ] | `grep "def run" my_agent.py` |
| Has `cleanup()` method | [ ] | `grep "def cleanup" my_agent.py` |
| Calls `ctx.done()` | [ ] | `grep "ctx.done" my_agent.py` |

### B. Generalist Compliance

| Requirement | Check | How to Verify |
|-------------|-------|---------------|
| No task keyword matching | [ ] | See verification below |
| No hardcoded solutions | [ ] | See verification below |
| No test file access | [ ] | See verification below |
| LLM-driven decisions | [ ] | Manual review |

**Verification Commands:**

```bash
# Check for keyword matching (should return nothing)
grep -n "in ctx.instruction" my_agent.py
grep -n "in task" my_agent.py
grep -n "instruction.lower()" my_agent.py

# Check for hardcoded handlers (should return nothing)
grep -n "def handle_" my_agent.py
grep -n "handlers\[" my_agent.py
grep -n "TASK_TYPE" my_agent.py

# Check for test file access (should return nothing)
grep -n "/tests/" my_agent.py
grep -n "test_" my_agent.py | grep -v "def test"
```

---

## Code Quality Checklist

### C. Error Handling

| Requirement | Check |
|-------------|-------|
| LLM errors handled | [ ] |
| Parse errors handled | [ ] |
| Command errors handled | [ ] |
| Timeouts handled | [ ] |
| Cost limits handled | [ ] |

**Minimum Error Handling:**

```python
# Must have try/except for LLM calls
try:
    response = self.llm.chat(messages)
except LLMError as e:
    ctx.log(f"LLM error: {e}")
    # Handle appropriately

# Must have try/except for JSON parsing
data = response.json()
if not data:
    # Handle parse failure
```

### D. Context Management

| Requirement | Check |
|-------------|-------|
| Output truncation | [ ] |
| Message history limits | [ ] |
| Token estimation | [ ] |

**Verification:**

```bash
# Check for truncation (should find something)
grep -n "truncate\|limit\|\[:.*\]" my_agent.py
```

### E. Resource Management

| Requirement | Check |
|-------------|-------|
| LLM client closed in cleanup | [ ] |
| No resource leaks | [ ] |
| Proper file handle closure | [ ] |

---

## Runtime Checklist

### F. Before Task Execution

| Step | Check |
|------|-------|
| Explore environment first | [ ] |
| Gather context before LLM call | [ ] |
| Use absolute paths | [ ] |

### G. During Task Execution

| Step | Check |
|------|-------|
| Log progress | [ ] |
| Check command results | [ ] |
| Update conversation history | [ ] |
| Respect step limits | [ ] |

### H. After Task Execution

| Step | Check |
|------|-------|
| Verify output files exist | [ ] |
| Clean up artifacts | [ ] |
| Double-confirm completion | [ ] |
| Call ctx.done() | [ ] |

---

## Output Verification

### I. Understand the Instruction

Before acting, the agent must reason about what the instruction truly requires:

```python
# Let LLM analyze the task requirements
response = llm.ask(
    f"Task: {ctx.instruction}\n\n"
    "What exactly does this task require?\n"
    "- What is the expected output?\n"
    "- What should NOT be done unless asked?",
    system="Analyze the task requirements carefully."
)
```

**Key principle:** Only do what the instruction asks. Don't assume cleanup, validation, or other actions are needed unless explicitly requested.

---

## Anti-Pattern Verification

### K. Forbidden Patterns

Run these checks - all should return nothing:

```bash
# 1. Keyword matching
grep -En 'if.*"[a-z]+".*in.*(instruction|task)' my_agent.py

# 2. Task classification
grep -En 'task_type|TaskType|classify|TASK_' my_agent.py

# 3. Handler dispatch
grep -En 'handler|Handler|dispatch|DISPATCH' my_agent.py

# 4. Hardcoded commands for tasks
grep -En 'COMMANDS|SOLUTIONS|TEMPLATES' my_agent.py

# 5. Test file access
grep -En '/tests?/|test_.*\.py|_test\.py' my_agent.py

# 6. Environment detection
grep -En 'TERM_BENCH|BENCHMARK|is_test' my_agent.py
```

---

## Final Validation

### L. Complete Test Run

```bash
# 1. Run against a simple task
term bench agent -a ./my_agent.py -t ./simple-task --verbose

# 2. Check the output
cat results/tasks/simple-task/agent.log

# 3. Verify completion
grep "done" results/tasks/simple-task/agent.log
```

### M. Cost Check

```bash
# Review LLM costs
grep -i "cost\|token" results/tasks/*/agent.log
```

---

## Submission Checklist Summary

```markdown
## Pre-Submission Verification

### Structure
- [ ] Agent class with setup(), run(), cleanup()
- [ ] ctx.done() always called

### Compliance
- [ ] No keyword matching on instructions
- [ ] No hardcoded task handlers
- [ ] No test file access
- [ ] All decisions via LLM

### Quality
- [ ] Error handling for LLM/parse/command
- [ ] Context truncation
- [ ] Output verification
- [ ] Artifact cleanup

### Testing
- [ ] Passes syntax check
- [ ] Passes import check
- [ ] Completes test task
- [ ] Logs progress appropriately

### Final
- [ ] Reviewed anti-pattern checks
- [ ] Ran full validation
- [ ] Ready to submit
```

---

## Quick Reference Card

### MUST HAVE

| Requirement | Description |
|-------------|-------------|
| `setup()`, `run()`, `cleanup()` | All three methods implemented |
| `ctx.done()` on all paths | Every execution path calls done |
| LLM for all decisions | No hardcoded logic |
| Error handling | Try/except for LLM, parse, shell |
| Output truncation | Limit context size |
| Output verification | Check files before marking done |

### MUST NOT HAVE

| Forbidden | Why |
|-----------|-----|
| `if keyword in instruction` | Task-specific matching |
| `task_type` handlers | Pre-defined task routing |
| Hardcoded solutions | Bypasses reasoning |
| Test file access | Cheating |
| Cached responses | Pre-computed answers |
| Assumed behaviors | Only do what's asked |

### KEY PRINCIPLE

| Do | Don't |
|----|-------|
| Reason about what instruction wants | Assume cleanup is needed |
| Let LLM decide actions | Hardcode validation steps |
| Only do what's requested | Add unrequested behaviors |

### BEFORE MARKING COMPLETE

| Step | Action |
|------|--------|
| 1 | Verify the instruction's requirements are met |
| 2 | Let LLM confirm task completion |
| 3 | Call `ctx.done()` |
