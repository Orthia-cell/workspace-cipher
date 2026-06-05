# /goal Command Research: Comparative Overview
## Anthropic vs. OpenAI Goal-Oriented Agent Architecture

**Date:** 2026-06-05  
**Researcher:** Cipher Laere (Laere Enterprises)  
**Scope:** Comparison of Anthropic's explicit `/goal` implementation vs. OpenAI's implicit goal-oriented behavior  
**Status:** Active research

---

## Executive Summary

Both Anthropic and OpenAI have identified the same fundamental problem: **agentic AI systems terminate prematurely** or fail to determine when tasks are complete. Their solutions diverge in philosophy and implementation, but the underlying architecture is converging.

**Anthropic's approach:** Explicit `/goal` command with a separate evaluator model (Haiku by default) that checks completion after each turn.  
**OpenAI's approach:** Implicit goal-oriented behavior in Codex, Deep Research, and Tasks where the agent infers completion criteria from the user's intent.

Both represent a shift from "prompt → response" to "goal → plan → execute → evaluate → continue" workflows.

---

## The Problem: Why /goal Matters

### The "Keep Going" Loop

Before `/goal`, Claude Code and similar systems would:
1. Complete one turn of work
2. Stop and wait for user input
3. User types "keep going" or "continue"
4. Repeat for hours

This is not a model failure — it's an **interaction model failure**. The agent is capable of doing the work but requires a human to manually prompt it to continue.

### The Termination Failure

A more subtle problem: agents decide they're done when they aren't. For example:
- A code migration agent reports success but several files were never compiled
- A documentation agent declares the doc complete but misses acceptance criteria
- The agent mixes up what it's accomplished with what still needs to be done

This is a **termination failure**, not a reasoning failure. The agent can do the work but incorrectly decides when to stop.

### The Core Insight

A well-defined goal transforms the question from:
- "Am I done?" (ambiguous, subjective, error-prone)

To:
- "Are all acceptance criteria satisfied?" (objective, verifiable, measurable)

This is the philosophical shift that makes `/goal` powerful.

---

## Side-by-Side Comparison

| Attribute | **Anthropic Claude Code /goal** | **OpenAI Codex / Tasks / Deep Research** |
|-----------|-----------------------------------|------------------------------------------|
| **Command Interface** | Explicit `/goal <condition>` | No explicit command; behavior is implicit |
| **User Input Style** | DONE = X (explicit success condition) | INTENT = X (desired outcome, inferred criteria) |
| **Evaluator** | Separate model (Haiku by default) | Integrated into the agent's own reasoning |
| **Worker Model vs. Evaluator** | Explicitly separated | Same model or tightly coupled |
| **Evaluation Method** | Binary: done / not done + reason | Complex: coverage, quality, completeness inferred |
| **Session Scope** | Session-scoped; 1 goal per session | Thread/task-scoped; may span multiple sessions |
| **Turn Limit** | User-defined turn limit optional | May have internal limits but not user-exposed |
| **Cost Model** | Evaluator tokens are separate, typically negligible | Integrated into overall token spend |
| **Documentation** | Explicitly documented with examples | Not publicly documented as a universal feature |
| **Availability** | Claude Code 2.1.139+ (May 2026) | Codex CLI (experimental), Deep Research, Tasks |
| **Modes** | Interactive, `-p` (persistent), Remote Control | Surface-dependent (IDE, CLI, app, cloud) |
| **Pause/Resume** | `/goal pause`, `/goal resume`, `/goal clear` | Task-level pause/resume in some surfaces |
| **Condition Length** | Max 4,000 characters | Dependent on context window and surface |
| **Feature Flag** | Not required; built-in | Codex requires `goals = true` under `[features]` |

---

## Anthropic's Implementation: Deep Dive

### Architecture

```
User: /goal all tests in test/auth pass and lint is clean

Turn 1:
  ├─ Claude (Sonnet/Opus) reads files, edits code, runs tests
  ├─ Test output: 3 failures, 47 passes
  └─ Goal active ◎ /goal active (turn 1, 2m elapsed, 12k tokens)

  Evaluator (Haiku):
    ├─ Receives: goal + full conversation transcript
    ├─ Checks: Does transcript show all tests pass AND lint clean?
    ├─ Result: NO — "3 tests in test/auth still failing"
    └─ Reason passed to main model as next instruction

Turn 2:
  ├─ Claude reads test output, fixes 3 failures, re-runs tests
  ├─ Test output: 50 passes, 0 failures
  ├─ Lint: clean
  └─ Goal active ◎ /goal active (turn 2, 4m elapsed, 28k tokens)

  Evaluator (Haiku):
    ├─ Receives: goal + updated transcript
    ├─ Result: YES
    ├─ Goal cleared ✅
    └─ Summary: "Goal achieved in 2 turns, 4m, 28k tokens"
```

### The Evaluator Loop

**Key insight:** The evaluator is a **fresh, neutral observer** every turn. It:
- Has no ego (didn't write the code)
- Has a single job: check if condition is met
- Sees only what the main model has surfaced in the conversation
- Returns a binary decision + a one-line reason

**Constraint:** The evaluator can only judge what's in the transcript. It cannot:
- Run commands independently
- Read files directly
- Browse the filesystem
- Call external tools

This means the condition must be **verifiable through the conversation transcript**. If the main model hasn't surfaced the evidence, the evaluator can't check it.

### The Four-Part Condition

Anthropic recommends conditions with four components:

1. **Measurable End State** — A test result, build exit code, file count, empty queue
2. **Stated Check** — How Claude should prove it: "npm test exits 0" or "git status is clean"
3. **Constraints** — What must not change on the way there: "no other test file is modified"
4. **Turn/Time Limit** — Optional: "stop after 20 turns" or "stop after 30 minutes"

### Examples: Good vs. Bad Conditions

**Good conditions (observable, verifiable):**
- `/goal all tests in test/auth pass and the lint step is clean`
- `/goal CHANGELOG.md has an entry for every PR merged this week`
- `/goal every call site of the old API has been migrated and the build succeeds, stop after 20 turns`
- `/goal npm test exits 0 and git status is clean`

**Bad conditions (ambiguous, unverifiable):**
- `/goal the app is production-ready` — no single command proves this
- `/goal no dirty data in the production database` — not verifiable through conversation
- `/goal make the code better` — no measurable end state
- `/goal refactor until it's clean` — no stated check

### Cost Model

- **Evaluator model:** Haiku by default (smaller, faster, cheaper than Sonnet/Opus)
- **Token consumption:** Evaluator calls are "typically negligible compared to main-turn spend"
- **Evaluation frequency:** Once per turn
- **Turn limit:** User can specify; prevents runaway costs
- **Time limit:** User can specify; alternative to turn limit

**Total cost = Main model cost + (Turns × Evaluator cost)**  
Example: 10 turns × $0.001/turn (Haiku) + $2.00 (Sonnet) = ~$2.01 total

### Risks and Mitigations

| Risk | Trigger | Mitigation |
|------|---------|------------|
| **Cost Overrun** | Evaluator misjudgment or loose conditions | Include "or stop after N turns" in conditions |
| **Evaluator Hallucination** | Conditions cannot be verified via transcript | Use observable phrasing like "run X command to verify Y output" |
| **Destructive Changes** | Main model modifies files it shouldn't to finish | Add "do not modify ..." constraints to conditions |
| **Workspace Misuse** | Accidental trigger in untrusted environment | Must accept trust dialog; use `disableAllHooks` to disable |
| **Infinite Loop** | Condition never satisfiable | Include turn limit; monitor for non-progress turns |
| **Partial Progress** | Agent restarts instead of continuing | /goal is session-scoped; check for resume features |

### Modes

1. **Interactive Mode** — Default; user can intervene any time
2. **`-p` / Persistent Mode** — Claude works until goal is met; user can check in later
3. **Remote Control Mode** — For CI/CD integration; non-interactive

---

## OpenAI's Implementation: Deep Dive

### Architecture

OpenAI's approach is **implicit and distributed** across multiple products. There is no single `/goal` command. Instead, goal-oriented behavior appears in:

#### Codex CLI (Experimental /goal)

```
User: /goal migrate all call sites to the new API

Codex:
  1. Parses goal into subtasks
  2. Plans migration steps
  3. Executes: reads files, edits code, runs tests
  4. Self-evaluates: checks coverage, runs tests
  5. If not complete: continues to next subtask
  6. If complete: reports success
```

**Key differences from Claude:**
- Codex `/goal` is **experimental**; requires feature flag `goals = true` under `[features]`
- `/goal` gives the thread a **persistent target** while the task runs
- Can be paused with `/goal pause`, resumed with `/goal resume`, cleared with `/goal clear`
- Not production-ready; documented as experimental
- Surface-dependent (IDE, CLI, app, cloud) — behavior varies by route

#### Deep Research

Deep Research's goal-oriented behavior is **implicit** in the prompt:

```
User: "Research analog computing startups. Create a comparison report.
Continue until all companies are categorized."

Deep Research:
  1. Creates subtasks: find startups, categorize, compare
  2. Searches the web iteratively
  3. Gathers data
  4. Checks coverage: "have I found all relevant companies?"
  5. If gaps: continues searching
  6. If complete: generates final report
```

**Key characteristics:**
- No explicit `/goal` command — the goal is embedded in the user's request
- The agent **infers** the completion criteria
- Self-evaluation is **integrated** into the agent's reasoning, not separate
- Subtask creation is dynamic and adaptive
- User can specify "continue until X" but the system interprets it

#### Tasks

OpenAI's Tasks feature (formerly Scheduled Tasks) has a similar implicit goal model:
- User defines a task: "Find and summarize AI news every morning"
- System runs at intervals
- Implicit goal: "complete the summary" each time
- No explicit success criteria; the agent determines completion

### The Philosophical Model: INTENT = X

Where Anthropic asks the user to provide:
```
DONE = X  (explicit, measurable, binary)
```

OpenAI's systems infer from:
```
INTENT = X  (desired outcome, agent determines completion criteria)
```

Example:
- **Claude /goal:** `/goal all 73 tests pass` — user defines exact success condition
- **ChatGPT Agents:** `Refactor this codebase and make it production-ready` — agent infers what "production-ready" means

This is a **gradient of specification**, not a binary choice. In practice, both systems can handle both styles, but their defaults and documentation emphasize different philosophies.

### Self-Evaluation vs. Separate Evaluation

**OpenAI's model** (integrated evaluation):
- The same model (or a tightly coupled model) evaluates its own progress
- Advantages: cheaper, simpler, no coordination overhead
- Disadvantages: model can hallucinate completion, ego bias (it wrote the code, so it thinks it's good), no independent verification

**Anthropic's model** (separate evaluation):
- Different model (Haiku) evaluates the main model's (Sonnet/Opus) work
- Advantages: neutral, fresh perspective, catches errors the main model misses
- Disadvantages: higher cost (two models), evaluator limited to transcript, potential for evaluator hallucination

### Current Status

As of June 2026:
- **Claude Code /goal:** Production-ready, well-documented, actively promoted
- **Codex /goal:** Experimental, feature-flagged, limited documentation
- **OpenAI's long-term strategy:** Likely to integrate goal-oriented behavior more deeply, but the explicit command approach may be secondary to the implicit model
- **No evidence** of a universal `/goal` command across all OpenAI surfaces (ChatGPT web, API, etc.)

---

## Convergence and Divergence

### What Both Systems Agree On

1. **Goal-oriented workflows are the future** — both have invested heavily
2. **Explicit success criteria are better than vague prompts** — both document this
3. **Autonomous loops are needed** — the "keep going" model is unsustainable
4. **Evaluation is a separate problem from execution** — even if integrated, both treat it as distinct

### Where They Diverge

| Dimension | Anthropic | OpenAI |
|-----------|-----------|--------|
| **User control** | High (explicit condition) | Medium (implicit condition) |
| **System complexity** | Higher (two-model architecture) | Lower (integrated) |
| **Documentation** | Explicit, detailed | Implicit, surface-dependent |
| **Enterprise readiness** | Production-ready | Experimental |
| **Cost model** | Transparent (evaluator tokens separate) | Opaque (integrated) |
| **Error modes** | Evaluator hallucination, loose conditions | Premature termination, vague goals |
| **Philosophy** | Human defines done; AI figures out how | Human defines intent; AI figures out everything |

---

## Sources

- Anthropic Claude Code /goal documentation (official)
- Alberto Arena, "Stop Typing, Keep Going" (May 22, 2026)
- VentureBeat, "Claude Code's /goals separates the agent that works from the one that decides it's done" (May 14, 2026)
- Yingtu AI, "Codex /goal vs Claude Code /goal" (May 15, 2026)
- APIYI, "Introduction to Claude Code goal mode" (May 13, 2026)
- Avi Chawla, "Claude Code's /goal Command" (May 14, 2026)
- FindSkill, "Claude Code /goal: Set a Finish Line, Walk Away" (May 13, 2026)
- Startup Fortune, "Claude adds /goal to keep working until the job is done" (May 12, 2026)
- SMNTCN, "Claude Code introduces task separation for enhanced agent efficiency" (May 15, 2026)

---

*This file is part of the Laere /goal research project. See the full directory for deep dives, synthesis, and implementation recommendations.*
