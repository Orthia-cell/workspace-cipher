# Anthropic Claude Code /goal: Deep Dive
## Architecture, Evaluator Model, and Feedback Loop

**Date:** 2026-06-05  
**Researcher:** Cipher Laere (Laere Enterprises)  
**Scope:** Detailed analysis of Anthropic's /goal implementation  
**Status:** Research complete

---

## Architecture Overview

Anthropic's `/goal` implementation is built on a **two-model separation** architecture. This is the defining architectural decision that distinguishes it from other agent systems.

```
┌─────────────────────────────────────────────────────┐
│                   User Input                         │
│              /goal <condition>                       │
└────────────────┬──────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              Session Loop Controller                 │
│  ┌──────────────────────────────────────────────┐   │
│  │   Turn 1: Main Model (Claude Sonnet/Opus)    │   │
│  │   ├─ Reads files, runs commands, edits code   │   │
│  │   ├─ Surfaces results in conversation         │   │
│  │   └─ Attempts to declare "done" or continues   │   │
│  └──────────────────┬───────────────────────────┘   │
                     │
                     ▼
  ┌──────────────────────────────────────────────┐
  │   Evaluator Model (Claude Haiku, ~3.5B)        │
  │   ├─ Receives: goal + full transcript         │
  │   ├─ Analyzes: Is condition met?              │
  │   ├─ Returns: YES/NO + one-line reason        │
  │   └─ Cost: ~$0.001-0.003 per evaluation       │
  └──────────────────┬───────────────────────────┘
                     │
           ┌─────────┴─────────┐
           │                   │
           ▼                   ▼
      ┌─────────┐       ┌─────────┐
      │  YES    │       │   NO    │
      │ Goal    │       │ Reason  │
      │ Cleared │       │ Passed  │
      │ Summary │       │ to Next │
      │ Output  │       │ Turn    │
      └─────────┘       └─────────┘
           │                   │
           │                   ▼
           │            ┌──────────────────┐
           │            │ Turn 2+: Repeat   │
           │            │ (up to N turns) │
           │            └──────────────────┘
           │
           ▼
  ┌──────────────────────────────────────────────┐
  │              User Gets Control Back             │
  └──────────────────────────────────────────────┘
```

---

## The Evaluator Model: Claude Haiku

### Model Selection

Anthropic uses **Claude Haiku** (the smallest, fastest model in the Claude family) as the default evaluator. This is a deliberate choice with several advantages:

1. **Cost efficiency** — Haiku is significantly cheaper than Sonnet or Opus
2. **Speed** — Evaluations must be fast to avoid bottlenecking the main loop
3. **Simplicity** — The evaluator only needs to make a binary decision (yes/no) with a reason
4. **Neutrality** — A smaller model has less "ego" about the quality of the work

**Model variants:** Users can configure which model serves as the evaluator, but Haiku is the default and recommended choice.

### What the Evaluator Sees

The evaluator receives:

```
Input to Evaluator:
  1. The original goal condition (set by user)
  2. The complete conversation transcript (all turns so far)
  3. Any context from the current session

What the evaluator does NOT see:
  - File system state (unless surfaced in conversation)
  - External command outputs (unless surfaced in conversation)
  - Previous session context (unless explicitly resumed)
  - Tool call results (unless surfaced in conversation)
```

This is a **critical constraint**: The evaluator can only judge what the main model has already surfaced in the conversation transcript. If the main model hasn't run a test and shown the output, the evaluator can't verify whether the test passed.

### Evaluator Decision Process

```
Evaluator Logic (simplified):

function evaluate_goal(condition, transcript):
    # Step 1: Parse condition into verifiable criteria
    criteria = parse_condition(condition)
    # e.g., "all tests pass" → "test output shows 0 failures"
    # e.g., "lint is clean" → "lint command exits with 0"
    
    # Step 2: Search transcript for evidence
    evidence = search_transcript(transcript, criteria)
    
    # Step 3: Make binary decision
    if evidence_meets_all_criteria(evidence, criteria):
        return {
            "decision": "YES",
            "reason": "All acceptance criteria met: [summary]"
        }
    else:
        return {
            "decision": "NO", 
            "reason": "Not yet: [specific gap]"
        }
```

**Key insight:** The evaluator is doing a **retrieval and classification task**, not a reasoning task. It's searching the transcript for evidence that matches the criteria and returning a binary classification. This is why Haiku is sufficient — it doesn't need deep reasoning, just careful pattern matching.

### Evaluator Output Format

```json
{
  "goal_met": false,
  "reason": "Three tests in test/auth are still failing: test_login.py, test_session.py, test_permissions.py",
  "confidence": 0.95,
  "suggested_next_action": "Fix the remaining test failures and re-run the test suite"
}
```

This output is then:
1. **Logged** to the conversation transcript (for future evaluation turns)
2. **Displayed** to the user in the status indicator (`◎ /goal active - 3 turns, 12m, 45k tokens`)
3. **Passed** to the main model as the next instruction if the goal is not met

---

## The Feedback Loop

### How the Loop Works

1. **User sets goal** — `/goal all tests in test/auth pass and lint is clean`
2. **Main model works** — Reads files, edits code, runs tests, surfaces output
3. **Evaluator checks** — Reviews transcript, decides if condition is met
4. **If NO:**
   - Evaluator's reason becomes the main model's next instruction
   - Main model works on the specific gap identified
   - Loop continues
5. **If YES:**
   - Goal is cleared automatically
   - Summary shows: turns elapsed, time elapsed, tokens spent
   - User gets control back

### Self-Correcting Property

The loop is **self-correcting** because the evaluator's reason provides specific guidance:

- **Scenario A:** Claude thinks it's done but missed a test
  - Evaluator says: "NO — three tests in test/auth are still red"
  - This sentence becomes Claude's next instruction
  - Claude doesn't need the user to type anything

- **Scenario B:** Claude is stuck in a loop
  - Evaluator says: "NO — no progress in last 3 turns; tests still failing"
  - This triggers a different approach from Claude
  - Or the turn limit is reached and the loop stops

### Checkpointing and Resume

Claude Code /goal supports session resumption:
- `--resume` flag allows continuing a previous session
- Goal state is preserved across sessions
- Transcript is maintained for context
- This enables multi-day goals without losing progress

---

## Condition Parsing and Goal Grammar

### The Condition as a DSL

Anthropic's documentation reveals that `/goal` conditions follow an implicit grammar:

```
goal_condition ::= end_state [verification_method] [constraints] [termination_clause]

end_state        ::= "all" collection "are" state
                  | "every" item "has" property
                  | command "exits" exit_code
                  | file "contains" content
                  | directory "is" state

verification_method ::= "verified by" command
                   | "confirmed by" test_suite
                   | "measured by" metric

constraints      ::= "do not modify" file_pattern
                  | "preserve" property
                  | "only change" scope

termination_clause ::= "stop after" number "turns"
                   | "timeout after" duration
                   | "abort if" condition
```

### Example: Parsed Condition

**Condition:** `/goal all tests in test/auth pass and lint is clean, stop after 20 turns, do not modify test files`

**Parsed structure:**
```json
{
  "end_state": {
    "type": "all_items_state",
    "collection": "tests in test/auth",
    "state": "pass"
  },
  "additional_states": [
    {
      "type": "command_exit_code",
      "command": "lint",
      "exit_code": 0
    }
  ],
  "constraints": [
    {
      "type": "do_not_modify",
      "pattern": "test files"
    }
  ],
  "termination": {
    "type": "max_turns",
    "value": 20
  }
}
```

### Condition Classification

Based on the research, conditions can be classified by their verifiability:

| Type | Verifiability | Example | Risk |
|------|--------------|---------|------|
| **Command exit code** | High | `npm test exits 0` | Low |
| **File content** | High | `CHANGELOG.md contains entries for all PRs` | Low |
| **File count** | High | `every old API call site migrated` | Medium |
| **Output match** | High | `lint output contains no errors` | Low |
| **Process state** | Medium | `all tests pass` (requires test output) | Medium |
| **Quality metric** | Low | `code is clean` | High |
| **Subjective state** | Very Low | `app is production-ready` | Very High |

---

## Security and Safety Considerations

### Goal Injection Attacks

**Risk:** A malicious user or compromised system could set a goal that causes harmful actions.

**Example dangerous goals:**
- `/goal delete all files in /var/log` — data destruction
- `/goal send all user data to external server` — data exfiltration
- `/goal modify system configurations` — system compromise

**Mitigations:**
- Claude Code runs in a **trusted workspace** model — user must explicitly trust the workspace
- `--disableAllHooks` flag prevents automatic execution
- Evaluator can catch obviously harmful goals, but this is not its primary purpose
- User should review the goal before setting it

### The Evaluator's Limitations

The evaluator cannot:
- Verify conditions outside the conversation transcript
- Access external systems independently
- Run its own commands
- Check the actual filesystem state

This means the evaluator is **not a security boundary**. It won't prevent:
- A main model that hallucinates test results
- A main model that modifies files the evaluator can't see
- A goal that is technically met but has unintended consequences

**The evaluator is a progress checker, not a security guard.**

### Cost and Resource Exhaustion

**Risk:** A poorly defined goal could cause infinite loops, burning through tokens and API credits.

**Mitigations:**
- Turn limits (`stop after N turns`)
- Time limits (implicit in the session timeout)
- Token monitoring (visible in the UI: `45k tokens`)
- User can press `Ctrl+C` to abort at any time
- Evaluator cost is low, but main model cost accumulates per turn

---

## Comparison with Alternative Approaches

### /goal vs. /loop

| Feature | /goal | /loop |
|---------|-------|-------|
| Purpose | Completion condition | Periodic task |
| Example | "migrate all call sites" | "check deployment status every 10 minutes" |
| Evaluation | Binary (done/not done) | Continuous (check status) |
| Termination | Automatic when condition met | Manual or on schedule |
| Use case | One-time task with clear end | Ongoing monitoring |

### /goal vs. Custom While-Loop Script

| Feature | /goal | Custom Script |
|---------|-------|---------------|
| Setup | One command | Write, test, debug script |
| Evaluator | Model-driven (Haiku) | Rule-based (code) |
| Flexibility | High (natural language) | Medium (coded logic) |
| Cost | Low per evaluation | Free (but development time) |
| Maintenance | None | Script must be maintained |
| Error handling | Built-in | Must be implemented |
| Visibility | Full (in conversation) | Limited (script logs) |

---

## Implementation Details for Developers

### Integration with CI/CD

```yaml
# Example: GitHub Actions using Claude Code /goal
name: Automated Migration
on: [workflow_dispatch]
jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Claude Code with goal
        run: |
          claude code --non-interactive \
            --goal "all tests pass and old API calls are migrated, stop after 50 turns" \
            --resume-if-previous
```

### API Usage (if available)

```python
# Pseudocode for Anthropic API usage with goal
from anthropic import Claude

client = Claude(api_key="...")

# Start a session with a goal
session = client.start_session(
    model="claude-sonnet-4-5",
    goal="all tests in test/auth pass and lint is clean",
    evaluator_model="claude-haiku-4-5",
    max_turns=20,
    timeout=1800  # 30 minutes
)

# Let it run autonomously
result = session.run_until_goal_met()

print(f"Completed in {result.turns} turns, {result.time_elapsed}s, {result.tokens} tokens")
print(f"Goal met: {result.goal_met}")
print(f"Summary: {result.summary}")
```

---

## Sources and Citations

- Anthropic Claude Code /goal documentation (official, May 2026)
- Alberto Arena, "Stop Typing, Keep Going" (May 22, 2026) — albertoarena.it
- VentureBeat, "Claude Code's /goals separates the agent that works from the one that decides it's done" (May 14, 2026)
- APIYI Technical Team, "Introduction to Claude Code goal mode" (May 13, 2026) — help.apiyi.com
- Avi Chawla, "Claude Code's /goal Command" (May 14, 2026) — blog.dailydoseofds.com
- FindSkill, "Claude Code /goal: Set a Finish Line, Walk Away" (May 13, 2026) — findskill.ai
- Startup Fortune, "Claude adds /goal to keep working until the job is done" (May 12, 2026) — startupfortune.com
- SMNTCN, "Claude Code introduces task separation for enhanced agent efficiency" (May 15, 2026) — smntcn.com

---

*This file is part of the Laere /goal research project. See the full directory for comparative analysis, strengths/weaknesses, Laere synthesis, and implementation recommendations.*
