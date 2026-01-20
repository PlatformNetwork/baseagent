# 03 - Allowed vs Forbidden

This document clearly defines what is permitted and what is prohibited when building generalist agents for Subnet 100.

---

## The Core Principle

> **Your agent must solve tasks through reasoning, not recognition.**

If your agent can identify a specific task and take a shortcut, it's cheating. The benchmark tests whether your agent can **think**, not whether it can **pattern match**.

---

## Allowed Behaviors

### LLM Usage

| Allowed | Example |
|---------|---------|
| Using LLM to analyze tasks | `llm.ask(f"Task: {task}\nWhat should I do?")` |
| Using LLM to generate code | `llm.ask("Write Python code that...")` |
| Using LLM to debug errors | `llm.ask(f"This error occurred: {error}")` |
| Using LLM to verify output | `llm.ask(f"Does this output match: {output}")` |
| Using LLM with tools | Function calling, tool use |
| Multi-turn conversations | Building on previous context |

### Shell Operations

| Allowed | Example |
|---------|---------|
| Exploring the environment | `ls -la`, `pwd`, `find .` |
| Running builds | `make`, `npm install`, `cargo build` |
| Executing tests | `pytest`, `npm test` |
| File operations | `cat`, `cp`, `mv`, `rm` |
| Process management | `ps`, `kill`, `timeout` |
| Network tools | `curl`, `wget` (to allowed endpoints) |

### File Operations

| Allowed | Example |
|---------|---------|
| Reading any file in workspace | `ctx.read("/app/src/main.py")` |
| Writing output files | `ctx.write("/app/result.txt", content)` |
| Creating directories | `mkdir -p /app/output` |
| Modifying source code | Editing files to fix bugs |
| Deleting files | Cleanup operations |

### Agent Architecture

| Allowed | Example |
|---------|---------|
| Generic system prompts | "You are a task-solving agent..." |
| Tool definitions | Shell, read, write tools |
| Error handling | Retry logic, fallbacks |
| Output truncation | Limiting context size |
| State management | Tracking conversation history |
| Iterative refinement | Multiple attempts at a task |

---

## Forbidden Behaviors

### Task-Specific Logic

| Forbidden | Why |
|-----------|-----|
| Keyword matching on instructions | `if "file" in task` |
| Task type classification | `task_type = classify(task)` |
| Handler dispatch tables | `handlers[task_type]()` |
| Regex matching on tasks | `re.search(r"create.*file", task)` |
| Embedding similarity to templates | Semantic task matching |

### Pre-Computed Solutions

| Forbidden | Why |
|-----------|-----|
| Cached responses | Solutions stored from previous runs |
| Template injection | Pre-written code for task types |
| Lookup tables | `solutions[task_hash]` |
| Hardcoded commands | Commands not from LLM reasoning |
| Response databases | Indexed solution retrieval |

### Test Circumvention

| Forbidden | Why |
|-----------|-----|
| Reading test files | Accessing `/tests/` or similar |
| Parsing assertions | Extracting expected outputs |
| Reverse-engineering validators | Understanding test logic |
| Timing-based detection | Detecting test vs real tasks |
| Environment fingerprinting | Detecting benchmark environment |

### Unauthorized Access

| Forbidden | Why |
|-----------|-----|
| Accessing test/validation files | Reading expected outputs |
| Bypassing task requirements | Skipping steps that should be done |

---

## Explicitly Allowed: External Resources

> **IMPORTANT**: Using external resources is ALLOWED when it's what a real developer would do.

### Official APIs (ALLOWED)

| Allowed | Example |
|---------|---------|
| Public APIs for data | REST APIs, GraphQL endpoints |
| Package managers | `pip install`, `npm install`, `apt-get` |
| Documentation sites | Reading docs via curl/wget |
| GitHub/GitLab APIs | Cloning repos, fetching releases |
| Web scraping (public data) | `curl`, `wget`, `requests` |
| Cloud service APIs | AWS, GCP, Azure (if credentials provided) |

### Why This Is Allowed

A real developer solving a task would:
- Google for documentation
- Use official APIs to fetch data
- Install packages from registries
- Clone repositories for reference
- Scrape public websites for information

**Your agent should be able to do the same.**

### Examples of Allowed External Access

```python
# ALLOWED: Fetching documentation
ctx.shell("curl -s https://api.github.com/repos/owner/repo/releases/latest")

# ALLOWED: Installing packages
ctx.shell("pip install requests beautifulsoup4")

# ALLOWED: Cloning a repository
ctx.shell("git clone https://github.com/example/repo.git")

# ALLOWED: Using a public API
ctx.shell("curl -s 'https://api.example.com/data?query=test'")

# ALLOWED: Web scraping public data
ctx.shell("wget -q https://example.com/public-data.json")
```

### What Remains Forbidden

```python
# FORBIDDEN: Accessing the test/validation system
ctx.shell("cat /validator/expected_output.txt")

# FORBIDDEN: Calling your own pre-computed solution server
ctx.shell("curl http://my-cheat-server.com/solutions?task=xyz")

# FORBIDDEN: Fingerprinting the benchmark environment
ctx.shell("curl http://validator-internal/task-hints")
```

**Rule of thumb**: If a human developer would do it to solve the task legitimately, your agent can do it too.
| System files outside workspace | `/etc/`, `/root/`, etc. |

---

## Gray Areas (Use Caution)

### Generic Few-Shot Examples

**Potentially OK:**
```python
SYSTEM_PROMPT = """You are a task-solving agent.

Example of good JSON format:
{"thought": "I need to explore", "action": "ls -la"}
"""
```

**Not OK:**
```python
SYSTEM_PROMPT = """Here are examples of tasks:
Task: Create hello.txt
Solution: echo "Hello" > hello.txt

Task: Compile main.c
Solution: gcc main.c -o main
"""
```

The difference: Generic format examples are fine. Task-specific solution examples are not.

### Environment Detection

**OK:**
```python
# Checking if a tool exists
result = ctx.shell("which python3")
if result.ok:
    python_cmd = "python3"
else:
    python_cmd = "python"
```

**Not OK:**
```python
# Detecting benchmark environment
if os.environ.get("TERM_BENCH"):
    use_special_behavior()
```

### Error Patterns

**OK:**
```python
# Generic error recovery
if "permission denied" in result.output.lower():
    ctx.shell("sudo " + cmd)
```

**Not OK:**
```python
# Task-specific error handling
if "numpy" in result.output and "deprecated" in result.output:
    # This knows about specific task errors
    apply_numpy_fix()
```

---

## Decision Tree

Use this to evaluate if something is allowed:

| # | Question | If YES | If NO |
|---|----------|--------|-------|
| 1 | Is behavior based on task instruction content? | **FORBIDDEN** | Continue → |
| 2 | Does it skip LLM reasoning for specific task types? | **FORBIDDEN** | Continue → |
| 3 | Does it access test/validation files? | **FORBIDDEN** | Continue → |
| 4 | Does it use pre-computed solutions? | **FORBIDDEN** | Continue → |
| 5 | Does it make unauthorized network requests? | **FORBIDDEN** | **ALLOWED** |

**Simple rule:** If you answer YES to any question, the behavior is FORBIDDEN.

---

## Examples of Violations

### Violation 1: Keyword Matching

```python
# FORBIDDEN
def run(self, ctx):
    if "hello" in ctx.instruction.lower():
        ctx.shell('echo "Hello, World!" > hello.txt')
        ctx.done()
        return
```

**Why:** Matches on task content to bypass reasoning.

### Violation 2: Task Classification

```python
# FORBIDDEN
TASK_TYPES = {
    "file_creation": ["create", "write", "make", "generate"],
    "compilation": ["compile", "build", "make"],
    "git": ["commit", "push", "branch", "merge"]
}

def classify_task(instruction):
    for task_type, keywords in TASK_TYPES.items():
        if any(kw in instruction.lower() for kw in keywords):
            return task_type
    return "unknown"
```

**Why:** Pre-defined task categories based on keywords.

### Violation 3: Solution Cache

```python
# FORBIDDEN
KNOWN_SOLUTIONS = {
    "create a file named hello.txt": 'echo "Hello" > hello.txt',
    "list all files": "ls -la",
}

def run(self, ctx):
    if ctx.instruction in KNOWN_SOLUTIONS:
        ctx.shell(KNOWN_SOLUTIONS[ctx.instruction])
```

**Why:** Cached solutions bypass reasoning entirely.

### Violation 4: Test File Access

```python
# FORBIDDEN
def run(self, ctx):
    # Trying to read test expectations
    test_file = ctx.shell("find . -name 'test*.py' | head -1").stdout.strip()
    if test_file:
        test_content = ctx.read(test_file)
        expected = extract_assertions(test_content)
```

**Why:** Accessing test files to extract expected outputs.

---

## Allowed Patterns (For Reference)

### Pattern A: Pure LLM Reasoning

```python
# ALLOWED
def run(self, ctx):
    context = ctx.shell("pwd && ls -la").output
    
    response = self.llm.ask(
        f"Task: {ctx.instruction}\n\nEnvironment:\n{context}\n\n"
        "What should I do?",
        system="You are a task-solving agent."
    )
    
    # LLM decides everything
    self.execute_llm_plan(ctx, response)
```

### Pattern B: Generic Error Recovery

```python
# ALLOWED - Generic, not task-specific
def run_with_retry(self, ctx, cmd, retries=3):
    for attempt in range(retries):
        result = ctx.shell(cmd)
        if result.ok:
            return result
        
        # Generic retry on transient errors
        if "connection" in result.stderr.lower():
            ctx.shell("sleep 5")
            continue
        
        break
    return result
```

### Pattern C: Output Verification

```python
# ALLOWED - Verifies via LLM, not hardcoded checks
def verify_output(self, ctx, expected_path):
    if not ctx.shell(f"test -f {expected_path}").ok:
        return False
    
    content = ctx.read(expected_path).stdout
    
    verification = self.llm.ask(
        f"Task was: {ctx.instruction}\n\n"
        f"Output file contains:\n{content[:1000]}\n\n"
        "Does this correctly complete the task? Answer YES or NO."
    )
    
    return "YES" in verification.text.upper()
```

---

## Summary Table

| Category | Allowed | Forbidden |
|----------|---------|-----------|
| LLM reasoning | All | N/A |
| Task keywords | Never check | Always forbidden |
| Shell commands | From LLM | Hardcoded per task |
| File access | Workspace only | Test files |
| Error handling | Generic | Task-specific |
| Caching | Conversation history | Solution lookup |
| Network | Allowed LLM providers | External APIs |

**When in doubt:** If it gives an advantage on known tasks but wouldn't help on novel tasks, it's probably forbidden.
