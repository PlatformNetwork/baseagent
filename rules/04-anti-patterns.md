# 04 - Anti-Patterns (30+ Examples)

This document catalogs **anti-patterns** - things you must NOT do when building generalist agents. Each anti-pattern includes:
- Code example showing the violation
- Explanation of why it's wrong
- Correct alternative

---

## Category 1: Pattern Matching on Instructions (10 Examples)

### Anti-Pattern 1.1: Direct Keyword Matching

```python
# WRONG
def run(self, ctx: Any):
    if "hello" in ctx.instruction.lower():
        shell('echo "Hello, World!" > hello.txt')
        # Task complete
        return
```

**Why it's wrong:** Matches specific task keywords to bypass LLM reasoning.

**Correct approach:**
```python
# RIGHT
def run(self, ctx: Any):
    response = self.llm.ask(f"Task: {ctx.instruction}\nWhat commands should I run?")
    commands = self.parse_commands(response.text)
    for cmd in commands:
        shell(cmd)
    # Task complete
```

---

### Anti-Pattern 1.2: Multi-Keyword Conditional

```python
# WRONG
def run(self, ctx: Any):
    task = ctx.instruction.lower()
    
    if "create" in task and "file" in task:
        self.handle_file_creation(ctx)
    elif "compile" in task or "build" in task:
        self.handle_compilation(ctx)
    elif "test" in task or "pytest" in task:
        self.handle_testing(ctx)
```

**Why it's wrong:** Routes tasks based on keyword combinations.

---

### Anti-Pattern 1.3: Regex Task Detection

```python
# WRONG
import re

TASK_PATTERNS = {
    r"create\s+(a\s+)?file": "file_creation",
    r"(compile|build)\s+": "compilation",
    r"(fix|debug)\s+": "debugging",
    r"(commit|push)\s+": "git_ops"
}

def classify_task(instruction):
    for pattern, task_type in TASK_PATTERNS.items():
        if re.search(pattern, instruction, re.IGNORECASE):
            return task_type
    return "generic"
```

**Why it's wrong:** Pre-defined regex patterns for task classification.

---

### Anti-Pattern 1.4: Task Type Enum

```python
# WRONG
from enum import Enum

class TaskType(Enum):
    FILE_OPERATION = "file"
    GIT_OPERATION = "git"
    BUILD = "build"
    TEST = "test"
    DEBUG = "debug"
    UNKNOWN = "unknown"

def detect_task_type(instruction: str) -> TaskType:
    keywords = {
        TaskType.FILE_OPERATION: ["file", "create", "write", "read", "delete"],
        TaskType.GIT_OPERATION: ["git", "commit", "push", "branch", "merge"],
        TaskType.BUILD: ["build", "compile", "make", "cargo", "npm"],
        TaskType.TEST: ["test", "pytest", "jest", "spec"],
        TaskType.DEBUG: ["debug", "fix", "error", "bug"]
    }
    
    for task_type, words in keywords.items():
        if any(word in instruction.lower() for word in words):
            return task_type
    return TaskType.UNKNOWN
```

**Why it's wrong:** Defines fixed task categories based on keyword lists.

---

### Anti-Pattern 1.5: Handler Dispatch Table

```python
# WRONG
class Agent:
    def __init__(self):
        self.handlers = {
            "file": self.handle_file_task,
            "git": self.handle_git_task,
            "python": self.handle_python_task,
            "compile": self.handle_compile_task,
        }
    
    def run(self, ctx: Any):
        for keyword, handler in self.handlers.items():
            if keyword in ctx.instruction.lower():
                handler(ctx)
                return
        self.handle_generic(ctx)
```

**Why it's wrong:** Dispatch table based on instruction keywords.

---

### Anti-Pattern 1.6: Instruction Hashing

```python
# WRONG
KNOWN_TASKS = {
    hash("create a file named hello.txt"): "echo 'Hello' > hello.txt",
    hash("list all files"): "ls -la",
    hash("show current directory"): "pwd",
}

def run(self, ctx: Any):
    task_hash = hash(ctx.instruction.lower().strip())
    if task_hash in KNOWN_TASKS:
        shell(KNOWN_TASKS[task_hash])
        # Task complete
        return
```

**Why it's wrong:** Uses instruction hash as lookup key.

---

### Anti-Pattern 1.7: Prefix/Suffix Matching

```python
# WRONG
def run(self, ctx: Any):
    instruction = ctx.instruction.lower()
    
    if instruction.startswith("write"):
        self.write_mode(ctx)
    elif instruction.startswith("read"):
        self.read_mode(ctx)
    elif instruction.endswith(".py"):
        self.python_mode(ctx)
    elif instruction.endswith(".rs"):
        self.rust_mode(ctx)
```

**Why it's wrong:** Routes based on instruction prefix/suffix.

---

### Anti-Pattern 1.8: Keyword Extraction for Routing

```python
# WRONG
def extract_action_keywords(instruction: str) -> set:
    actions = {"create", "delete", "modify", "read", "write", "compile", "run", "test"}
    words = set(instruction.lower().split())
    return words & actions

def run(self, ctx: Any):
    keywords = extract_action_keywords(ctx.instruction)
    
    if "create" in keywords:
        self.creation_flow(ctx)
    elif "delete" in keywords:
        self.deletion_flow(ctx)
```

**Why it's wrong:** Extracts action keywords to determine flow.

---

### Anti-Pattern 1.9: Semantic Similarity to Templates

```python
# WRONG
from sentence_transformers import SentenceTransformer

TASK_TEMPLATES = [
    ("Create a new file with content", "file_creation"),
    ("Compile the source code", "compilation"),
    ("Run the test suite", "testing"),
]

def classify_by_embedding(instruction: str, model) -> str:
    inst_embedding = model.encode(instruction)
    
    best_match = None
    best_score = -1
    
    for template, task_type in TASK_TEMPLATES:
        template_embedding = model.encode(template)
        score = cosine_similarity(inst_embedding, template_embedding)
        if score > best_score:
            best_score = score
            best_match = task_type
    
    return best_match if best_score > 0.7 else "unknown"
```

**Why it's wrong:** Uses embedding similarity to pre-defined templates.

---

### Anti-Pattern 1.10: NLP Task Classification

```python
# WRONG
from transformers import pipeline

classifier = pipeline("zero-shot-classification")
TASK_LABELS = ["file operation", "git operation", "compilation", "testing", "debugging"]

def run(self, ctx: Any):
    result = classifier(ctx.instruction, TASK_LABELS)
    task_type = result["labels"][0]
    
    if task_type == "file operation":
        self.file_handler(ctx)
    elif task_type == "git operation":
        self.git_handler(ctx)
    # ...
```

**Why it's wrong:** Uses ML classifier with pre-defined task labels.

---

## Category 2: Pre-Defined Responses (8 Examples)

### Anti-Pattern 2.1: Hardcoded Shell Commands

```python
# WRONG
def run(self, ctx: Any):
    # Hardcoded sequence without LLM
    shell("git add .")
    shell("git commit -m 'Update'")
    shell("git push")
    # Task complete
```

**Why it's wrong:** Commands are hardcoded, not from LLM reasoning.

---

### Anti-Pattern 2.2: Template Responses

```python
# WRONG
TEMPLATES = {
    "file_creation": """
with open('{filename}', 'w') as f:
    f.write('{content}')
""",
    "read_json": """
import json
with open('{filename}') as f:
    data = json.load(f)
""",
}

def generate_code(task_type: str, **kwargs) -> str:
    return TEMPLATES[task_type].format(**kwargs)
```

**Why it's wrong:** Pre-written code templates injected without reasoning.

---

### Anti-Pattern 2.3: Solution Database

```python
# WRONG
import sqlite3

class SolutionCache:
    def __init__(self):
        self.conn = sqlite3.connect("solutions.db")
    
    def lookup(self, instruction: str) -> str | None:
        cursor = self.conn.execute(
            "SELECT solution FROM cache WHERE instruction LIKE ?",
            (f"%{instruction[:50]}%",)
        )
        row = cursor.fetchone()
        return row[0] if row else None

def run(self, ctx: Any):
    cached = self.cache.lookup(ctx.instruction)
    if cached:
        exec(cached)  # Execute cached solution
        # Task complete
        return
```

**Why it's wrong:** Looks up solutions from a database.

---

### Anti-Pattern 2.4: Cached Conversation Responses

```python
# WRONG
RESPONSE_CACHE = {}

def run(self, ctx: Any):
    cache_key = ctx.instruction[:100]
    
    if cache_key in RESPONSE_CACHE:
        # Replay cached response instead of calling LLM
        self.execute_cached(ctx, RESPONSE_CACHE[cache_key])
        # Task complete
        return
    
    response = self.llm.ask(ctx.instruction)
    RESPONSE_CACHE[cache_key] = response
    self.execute(ctx, response)
```

**Why it's wrong:** Caches and replays LLM responses for similar instructions.

---

### Anti-Pattern 2.5: Static File Content

```python
# WRONG
KNOWN_FILES = {
    "hello.txt": "Hello, World!",
    "readme.md": "# Project\n\nThis is a project.",
    "config.json": '{"version": "1.0"}',
}

def run(self, ctx: Any):
    for filename, content in KNOWN_FILES.items():
        if filename in ctx.instruction.lower():
            write_file(f"/app/{filename}", content)
            # Task complete
            return
```

**Why it's wrong:** Pre-defined file contents for known filenames.

---

### Anti-Pattern 2.6: Command Sequences Per Task Type

```python
# WRONG
COMMAND_SEQUENCES = {
    "python_project": [
        "python -m venv venv",
        "source venv/bin/activate",
        "pip install -r requirements.txt",
        "python main.py"
    ],
    "node_project": [
        "npm install",
        "npm run build",
        "npm start"
    ],
}

def run(self, ctx: Any):
    if "python" in ctx.instruction.lower():
        for cmd in COMMAND_SEQUENCES["python_project"]:
            shell(cmd)
```

**Why it's wrong:** Pre-defined command sequences by task type.

---

### Anti-Pattern 2.7: Fallback Responses

```python
# WRONG
DEFAULT_RESPONSES = {
    "unknown_error": "echo 'Task could not be completed'",
    "file_not_found": "touch placeholder.txt",
    "compilation_failed": "echo '// TODO: fix compilation' > fix.txt",
}

def run(self, ctx: Any):
    try:
        self.attempt_task(ctx)
    except Exception as e:
        error_type = classify_error(e)
        shell(DEFAULT_RESPONSES.get(error_type, "echo 'Error'"))
```

**Why it's wrong:** Pre-defined fallback responses for error types.

---

### Anti-Pattern 2.8: Output Format Templates

```python
# WRONG
OUTPUT_TEMPLATES = {
    "result.txt": "Result: {value}",
    "output.json": '{{"status": "success", "data": {data}}}',
    "answer.txt": "The answer is: {answer}",
}

def write_output(self, ctx, filename: str, **values):
    if filename in OUTPUT_TEMPLATES:
        content = OUTPUT_TEMPLATES[filename].format(**values)
        write_file(f"/app/{filename}", content)
```

**Why it's wrong:** Pre-defined output format templates.

---

## Category 3: Cheating/Circumvention (7 Examples)

### Anti-Pattern 3.1: Reading Test Files

```python
# WRONG
def run(self, ctx: Any):
    # Trying to read test expectations
    test_files = shell("find . -name 'test_*.py' -o -name '*_test.py'").stdout
    
    for test_file in test_files.strip().split('\n'):
        content = read_file(test_file)
        expected = self.extract_assertions(content)
        self.use_expected_values(expected)
```

**Why it's wrong:** Reads test files to extract expected outputs.

---

### Anti-Pattern 3.2: Parsing Assertion Values

```python
# WRONG
import ast

def extract_expected_values(test_content: str) -> list:
    tree = ast.parse(test_content)
    expected = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if hasattr(node.func, 'attr') and node.func.attr in ('assertEqual', 'assertEquals'):
                # Extract the expected value from assertions
                expected.append(ast.literal_eval(node.args[1]))
    
    return expected
```

**Why it's wrong:** Parses test code to extract expected values.

---

### Anti-Pattern 3.3: Environment Detection

```python
# WRONG
import os

def run(self, ctx: Any):
    # Detect if running in benchmark environment
    if os.environ.get("TERM_BENCH") or os.environ.get("BENCHMARK_MODE"):
        self.benchmark_optimized_mode(ctx)
    else:
        self.normal_mode(ctx)
```

**Why it's wrong:** Detects benchmark environment for special behavior.

---

### Anti-Pattern 3.4: Workspace Path Analysis

```python
# WRONG
def run(self, ctx: Any):
    pwd = shell("pwd").stdout.strip()
    
    # Detect task by workspace path
    if "polyglot" in pwd:
        self.handle_polyglot(ctx)
    elif "cryptanalysis" in pwd:
        self.handle_crypto(ctx)
    elif "sanitize" in pwd:
        self.handle_sanitization(ctx)
```

**Why it's wrong:** Infers task type from workspace path.

---

### Anti-Pattern 3.5: File Structure Detection

```python
# WRONG
def detect_project_type(self, ctx: Any) -> str:
    files = shell("ls -la").stdout
    
    # Detect project type by files present
    if "Cargo.toml" in files:
        return "rust"
    elif "package.json" in files:
        return "node"
    elif "setup.py" in files or "pyproject.toml" in files:
        return "python"
    elif "Makefile" in files:
        return "make"
    
    return "unknown"

def run(self, ctx: Any):
    project_type = self.detect_project_type(ctx)
    # Use project type to skip reasoning
    self.handlers[project_type](ctx)
```

**Why it's wrong:** Uses file structure to bypass task analysis.

**Note:** Detecting project type via LLM reasoning is fine. Hardcoded detection with handlers is not.

---

## Category 4: Bad LLM Usage (5 Examples)

### Anti-Pattern 4.1: No Context Truncation

```python
# WRONG
def run(self, ctx: Any):
    all_output = ""
    
    for i in range(100):
        response = self.llm.chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {ctx.instruction}\n\nAll output so far:\n{all_output}"}
        ])
        
        result = shell(response.text)
        all_output += result.output  # Grows unboundedly!
```

**Why it's wrong:** Context grows without limit, causing overflow.

**Correct approach:**
```python
# RIGHT
def run(self, ctx: Any):
    history = []
    
    for i in range(100):
        # Keep only last N messages
        recent_history = history[-20:]
        
        response = self.llm.chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            *recent_history
        ])
        
        result = shell(response.text)
        # Truncate output
        history.append({"role": "user", "content": result.output[-3000:]})
```

---

### Anti-Pattern 4.2: Single Massive Prompt

```python
# WRONG
def run(self, ctx: Any):
    # Try to do everything in one prompt
    mega_prompt = f"""
    Task: {ctx.instruction}
    
    Please:
    1. Analyze the task
    2. Create a complete plan
    3. Write all necessary code
    4. Provide all shell commands
    5. Anticipate all errors
    6. Give the final answer
    
    Respond with everything at once.
    """
    
    response = self.llm.ask(mega_prompt)
    # Hope it works...
```

**Why it's wrong:** Tries to do everything in one shot without iteration.

---

### Anti-Pattern 4.3: Ignoring LLM Errors

```python
# WRONG
def run(self, ctx: Any):
    response = self.llm.ask(ctx.instruction)  # Might fail!
    
    data = response.json()  # Might be None!
    command = data["command"]  # Might KeyError!
    
    shell(command)
```

**Why it's wrong:** No error handling for LLM failures.

**Correct approach:**
```python
# RIGHT
def run(self, ctx: Any):
    try:
        response = self.llm.ask(ctx.instruction)
    except LLMError as e:
        print(f"LLM error: {e}")
        if e.code in ("rate_limit", "server_error"):
            time.sleep(5)
            response = self.llm.ask(ctx.instruction)  # Retry
        else:
            raise
    
    data = response.json()
    if not data:
        print("Failed to parse JSON, asking for clarification")
        response = self.llm.ask("Please respond with valid JSON")
        data = response.json()
    
    command = data.get("command")
    if command:
        shell(command)
```

---

### Anti-Pattern 4.4: No Retry Logic

```python
# WRONG
def run(self, ctx: Any):
    response = self.llm.ask(ctx.instruction)
    
    if not response.text:
        # Task complete  # Just give up
        return
```

**Why it's wrong:** Gives up on first failure without retry.

---

### Anti-Pattern 4.5: Raw Response Without Validation

```python
# WRONG
def run(self, ctx: Any):
    response = self.llm.ask("Give me a shell command")
    
    # Execute whatever the LLM says without validation
    shell(response.text)
```

**Why it's wrong:** Doesn't validate LLM output before execution.

**Correct approach:**
```python
# RIGHT
def run(self, ctx: Any):
    response = self.llm.ask(
        "Give me a shell command as JSON: {\"command\": \"...\"}",
        system="Respond only with valid JSON."
    )
    
    data = response.json()
    if not data:
        print("Invalid response format")
        return
    
    command = data.get("command", "").strip()
    if not command:
        print("No command provided")
        return
    
    # Now safe to execute
    shell(command)
```

---

## Category 5: Subtle Anti-Patterns (8 Examples)

### Anti-Pattern 5.1: Hardcoded Timeouts Per Task

```python
# WRONG
TASK_TIMEOUTS = {
    "compile": 120,
    "test": 60,
    "download": 300,
    "simple": 10,
}

def run(self, ctx: Any):
    # Determine timeout by task keywords
    timeout = 30  # default
    for keyword, t in TASK_TIMEOUTS.items():
        if keyword in ctx.instruction.lower():
            timeout = t
            break
    
    shell(command, timeout=timeout)
```

**Why it's wrong:** Timeouts are based on task keywords.

---

### Anti-Pattern 5.2: Output Length Expectations

```python
# WRONG
def verify_output(self, ctx, output: str) -> bool:
    # Expect certain output lengths for task types
    if "list" in ctx.instruction.lower():
        return len(output.split('\n')) > 5
    elif "count" in ctx.instruction.lower():
        return len(output) < 20
```

**Why it's wrong:** Validates based on task-specific expectations.

---

### Anti-Pattern 5.3: File Count Heuristics

```python
# WRONG
def check_completion(self, ctx: Any) -> bool:
    file_count = len(shell("ls").stdout.split())
    
    # Expect certain file counts
    if "cleanup" in ctx.instruction.lower():
        return file_count < 5  # Cleanup should reduce files
    elif "generate" in ctx.instruction.lower():
        return file_count > 10  # Generation should create files
```

**Why it's wrong:** Uses file count heuristics based on task type.

---

### Anti-Pattern 5.4: Exit Code Assumptions

```python
# WRONG
def run(self, ctx: Any):
    result = shell("make")
    
    # Assume specific exit codes mean specific things
    if result.exit_code == 2:
        # "Must be missing Makefile, create one"
        write_file("Makefile", DEFAULT_MAKEFILE)
```

**Why it's wrong:** Hardcoded interpretation of exit codes.

---

### Anti-Pattern 5.5: Error Message Pattern Matching

```python
# WRONG
ERROR_HANDLERS = {
    r"No such file": lambda ctx: shell("touch missing_file"),
    r"Permission denied": lambda ctx: shell("chmod +x script.sh"),
    r"Module not found": lambda ctx: shell("pip install -r requirements.txt"),
    r"ECONNREFUSED": lambda ctx: shell("sleep 5") and retry(),
}

def handle_error(self, ctx, error: str):
    for pattern, handler in ERROR_HANDLERS.items():
        if re.search(pattern, error):
            handler(ctx)
            return
```

**Why it's wrong:** Pre-defined error handlers with fixed responses.

**Note:** Generic retry on transient errors is OK. Task-specific error handlers are not.

---

### Anti-Pattern 5.6: Instruction Length Heuristics

```python
# WRONG
def run(self, ctx: Any):
    # Assume short instructions are simple
    if len(ctx.instruction) < 50:
        self.simple_mode(ctx)
    else:
        self.complex_mode(ctx)
```

**Why it's wrong:** Uses instruction length to determine behavior.

---

### Anti-Pattern 5.7: Step Count Assumptions

```python
# WRONG
def run(self, ctx: Any):
    # Assume task types need certain step counts
    if "deploy" in ctx.instruction.lower():
        max_steps = 20  # Deployments are complex
    elif "create" in ctx.instruction.lower():
        max_steps = 3   # Creation is simple
    else:
        max_steps = 10
```

**Why it's wrong:** Pre-defines step limits by task keywords.

---

### Anti-Pattern 5.8: Directory Name Detection

```python
# WRONG
def run(self, ctx: Any):
    dirs = shell("ls -d */").stdout.split()
    
    # Detect task by directory names
    if "src" in dirs and "tests" in dirs:
        self.python_project_mode(ctx)
    elif "node_modules" in dirs:
        self.node_project_mode(ctx)
```

**Why it's wrong:** Infers task type from directory structure.

---

## Summary: Quick Reference

| Category | Count | Key Violation |
|----------|-------|---------------|
| Pattern Matching | 10 | Checking instruction content |
| Pre-Defined Responses | 8 | Hardcoded solutions/templates |
| Cheating | 7 | Accessing test files/environment |
| Bad LLM Usage | 5 | No error handling/truncation |
| Subtle Patterns | 8 | Hidden task-specific logic |
| **TOTAL** | **38** | |

### The Golden Test

For any code you write, ask:

> "Would this code behave differently if I changed the task instruction?"

If the answer is YES and it's not because of LLM reasoning, it's an anti-pattern.
