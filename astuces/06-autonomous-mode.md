# Autonomous Mode - No Questions, Just Execute

## The Problem

In benchmarks and headless environments:
- There's no user to answer questions
- Waiting for input means timeout/failure
- The agent must make decisions independently

Agents trained on interactive chat often ask questions by default.

## The Solution

Explicit instructions in the system prompt that override the "ask for clarification" instinct.

## System Prompt Section

```
## Autonomy

You are fully autonomous. Keep working until the task is COMPLETELY resolved:
- Do NOT stop to ask questions - make reasonable decisions and proceed
- Do NOT ask for permission or confirmation - just execute
- When you face a choice (e.g., Option A vs Option B), pick the most reasonable one
- Only signal completion AFTER verifying your work
- If something fails, try alternative approaches until it works

CRITICAL: You are in headless mode.
- No user is available to answer questions
- Do not wait for input that will never come
- Make decisions based on context and best practices
```

## Decision-Making Guidelines

When the agent faces ambiguity:

### File Locations
```
If unsure where to create a file:
- Check for existing similar files
- Follow project conventions
- Default to current directory or src/
- Never ask "where should I put this?"
```

### Implementation Choices
```
If multiple approaches exist:
- Check existing code for patterns
- Prefer simpler solutions
- Use standard library over dependencies
- Never ask "which approach do you prefer?"
```

### Missing Information
```
If information is missing:
- Search the codebase for context
- Check documentation files (README, AGENTS.md)
- Make reasonable assumptions
- Document assumptions in code comments
- Never ask "can you clarify?"
```

## Handling Errors

```
## Error Recovery

When you encounter an error:
1. Read the error message carefully
2. Try to fix the issue
3. If fix doesn't work, try alternative approach
4. Retry up to 3 times with different strategies
5. Only give up after exhausting options

Do NOT:
- Ask user how to fix it
- Wait for guidance
- Give up after first failure
```

## Code Example: Autonomous Loop

```python
async def autonomous_loop(ctx: AgentContext) -> str:
    """Run agent in fully autonomous mode."""
    
    max_turns = 50
    max_errors = 10
    consecutive_errors = 0
    
    for turn in range(max_turns):
        try:
            response = await call_llm(messages)
            
            # Check for question patterns
            if contains_question(response.text):
                # Inject reminder
                messages.append({
                    "role": "user",
                    "content": "REMINDER: You are in autonomous mode. Do not ask questions. Make a decision and proceed."
                })
                continue
            
            # Execute tools
            if response.has_function_calls():
                for call in response.function_calls:
                    result = execute_tool(call)
                    # Add result to context
                
                consecutive_errors = 0
            else:
                # No tools = completion attempt
                return response.text
                
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors >= max_errors:
                return f"Task failed after {max_errors} consecutive errors: {e}"
            
            # Add error to context, let agent retry
            messages.append({
                "role": "user", 
                "content": f"Error occurred: {e}\nPlease try a different approach."
            })
    
    return "Task incomplete: max turns reached"

def contains_question(text: str) -> bool:
    """Detect if agent is asking a question instead of executing."""
    patterns = [
        "would you like",
        "should I",
        "do you want",
        "please confirm",
        "please clarify",
        "can you tell me",
        "what would you prefer",
        "?",  # Any question mark at end of sentences
    ]
    
    text_lower = text.lower()
    return any(p in text_lower for p in patterns)
```

## Testing Autonomous Mode

Create test cases that require decisions:

```python
def test_autonomous_decisions():
    # Ambiguous task
    result = run_agent("Create a config file for the project")
    
    # Agent should:
    # 1. Decide format (json, yaml, toml)
    # 2. Decide location (root, config/, etc.)
    # 3. Decide content structure
    # WITHOUT asking any questions
    
    assert "?" not in result  # No questions
    assert file_exists("config.*")  # File was created
```

## Common Anti-Patterns

### Bad: Asking for Clarification
```
"I see there are two possible approaches. Would you like me to:
1. Use the REST API
2. Use the GraphQL API

Please let me know which you prefer."
```

### Good: Making a Decision
```
"I'll use the REST API since it's already used elsewhere in the codebase.
[proceeds to implement]"
```

### Bad: Waiting for Confirmation
```
"I'm about to delete the old config file. Should I proceed?"
```

### Good: Proceeding Safely
```
"Backing up old config to config.bak, then creating new config.
[proceeds]"
```
