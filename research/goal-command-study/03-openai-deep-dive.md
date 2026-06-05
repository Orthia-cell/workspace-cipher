# OpenAI Goal-Oriented Workflows: Deep Dive

> Research File: `03-openai-deep-dive.md`  
> Research Agent: Cipher Laere (Laere Enterprises)  
> Date: 2026-06-05  
> Status: Complete  
> Sources: OpenAI Codex Goals cookbook (`developers.openai.com/cookbook`), OpenAI Deep Research docs (`developers.openai.com/api/docs/guides/deep-research`), OpenAI Deep Research announcement (2025-02-02), ChatGPT Deep Research help (`help.openai.com`), OpenAI community forum (2026-05-26), VentureBeat (2026-05-14), juejin.cn comparison (2026-05-16), albertoarena.it (2026-05-22)

---

## Executive Summary

OpenAI does not ship a single, universal `/goal` command. Instead, goal-oriented behavior is distributed across three products with different architectures: **Codex Goals** (explicit `/goal` in CLI, thread-persistent state), **Deep Research** (implicit goal completion via multi-step planning, no user-defined condition), and **Tasks** (scheduled execution with no convergence loop). This document examines each in depth, then analyzes OpenAI's broader architectural philosophy: goals as **system-inferred completion** rather than **user-defined terminal states**.

---

## 1. Codex Goals: The Explicit Implementation

### 1.1 Overview

Codex Goals shipped in **v0.128.0** (April 2026, broadly visible May 2026) with a `/goal` surface command that is functionally similar to Claude Code's. However, the internal architecture differs in three significant ways:

1. **Persistent thread state** — goals survive session crashes, restarts, and explicit pause/resume
2. **Richer goal contract** — six recommended elements vs. Anthropic's simpler condition string
3. **Conservative continuation dispatcher** — event-driven, not loop-driven; suppresses continuation if the previous turn produced no tool calls

### 1.2 The Goal State Object

Unlike Anthropic's flat condition string, Codex Goals are implemented as **structured thread-scoped state objects**:

```typescript
// Inferred structure from OpenAI documentation
interface GoalState {
  objective: string;           // The desired end state
  verificationSurface: string;   // How to prove it (test, benchmark, artifact)
  constraints: string[];         // What must not regress
  boundaries: string[];          // Allowed files, tools, data, repos
  iterationPolicy: string;       // How to choose next action after each attempt
  blockedStopCondition: string; // What to report when no valid path remains
  lifecycle: 'active' | 'paused' | 'complete' | 'budget-limited' | 'blocked';
  turnCount: number;
  createdAt: timestamp;
  lastEvaluatedAt: timestamp;
}
```

> "Goals are implemented as persisted thread state, not as global memory and not as project-level instructions. That design choice is important: the objective belongs to the thread where the relevant context lives, including the files Codex inspected, the commands it ran, the diffs it produced, the logs it saw, and the reasoning trail it built up."  
> — OpenAI Codex Goals cookbook (2026-05-09)

This state object is **durable** — it persists across:
- Session crashes
- Explicit `/goal pause` and `/goal resume`
- Context compaction (the goal metadata is preserved even when old conversation turns are summarized)
- Thread restarts (if the thread is resumed, the goal state is restored)

### 1.3 The Six-Element Goal Contract

OpenAI's documentation recommends a **six-element structure** for strong goals:

```
/goal <desired end state>
     verified by <specific evidence>
     while preserving <constraints>
     using <allowed inputs, tools, or boundaries>
     between iterations, <how to choose next best action>
     if blocked or no valid paths remain, <what to report and what would unlock progress>
```

Example (strong):
```
/goal Reduce p95 checkout latency below 120 ms,
      verified by the checkout benchmark,
      while keeping the correctness suite green.
      Use only the checkout service, benchmark fixtures, and related tests.
      Between iterations, record what changed, what the benchmark showed,
      and the next best experiment to try.
      If the benchmark cannot run or no valid paths remain, stop with the
      attempted paths, the evidence gathered, the blocker, and the next input needed.
```

Example (weak, but workable):
```
/goal Reduce p95 checkout latency below 120 ms without regressing correctness tests
```

The six-element structure is **not enforced** — it's a recommendation. The user can write a simple condition string like Anthropic's. But the system is designed to **benefit from** richer metadata.

> "A good Goal is more than a larger prompt. It is a compact contract for how Codex should work, what counts as success, and what should happen if success is not yet reachable."  
> — OpenAI Codex Goals cookbook (2026-05-09)

### 1.4 The Evaluator Architecture

OpenAI's evaluator is **less documented** than Anthropic's. What we know:

| Property | Codex Evaluator | Claude Code Evaluator |
|----------|----------------|----------------------|
| Model identity | **Undisclosed** — likely GPT-4.1-mini or lightweight custom model | **Haiku** (explicitly documented) |
| Capabilities | Read-only thread judge | Read-only transcript judge |
| Output | Binary yes/no + reason | Binary yes/no + one-sentence reason |
| Tool access | No | No |
| Cost visibility | Not documented | Documented as negligible |
| Configurability | Not documented | Configurable "small fast model" |

The community inference is that Codex uses a **lightweight GPT model** (possibly GPT-4.1-mini at $0.40/$1.60 per million tokens, or a custom distilled variant) for evaluation. The evaluation tokens are presumably billed, but OpenAI does not provide a separate cost breakdown.

> **Assessment**: OpenAI's lack of transparency on the evaluator model is a **minor weakness**. It prevents users from optimizing cost, verifying fairness, or debugging evaluator behavior. Anthropic's explicit Haiku choice is more user-friendly.

### 1.5 The Conservative Continuation Dispatcher

This is Codex's most distinctive architectural feature. The continuation is **not** a simple loop. It is **event-driven** and **deliberately conservative**:

```python
# Pseudocode for the continuation dispatcher (inferred)
def should_continue(goal_state, thread_state):
    # Must be active
    if goal_state.lifecycle != 'active':
        return False
    
    # Must be within budget
    if goal_state.turnCount > MAX_TURNS:  # or budget exceeded
        return False
    
    # Previous turn must have completed
    if thread_state.last_turn_status != 'complete':
        return False
    
    # No user input queued
    if thread_state.has_pending_user_input():
        return False
    
    # No other thread work pending
    if thread_state.has_pending_work():
        return False
    
    # Thread must be idle
    if not thread_state.is_idle():
        return False
    
    # Previous turn must have produced at least one tool call
    # (prevents spinning when the model is just thinking)
    if thread_state.last_turn_tool_calls == 0:
        return False  # Suppress next continuation
    
    return True
```

> "Codex does not continue while another turn is active, while user input is queued, or while other thread work is pending. It continues only when the thread is idle and the Goal is active and within budget."  
> "If a continuation turn makes no tool call, the next automatic continuation is suppressed so Codex does not spin."  
> — OpenAI Codex Goals cookbook (2026-05-09)

This is **anti-spin protection** — a recognition that LLMs can "hallucinate progress" by generating text that looks like work but doesn't actually call tools or change state. The dispatcher requires **evidence of work** (a tool call) before continuing.

### 1.6 Lifecycle States and Transitions

```
                    ┌─────────────┐
                    │   SET_GOAL  │
                    │  (user sets)│
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌────►│   ACTIVE    │◄────┐
              │     │  (running)  │     │
              │     └──────┬──────┘     │
              │            │            │
    ┌─────────┼────────────┼────────────┼─────────┐
    │         │            │            │         │
    ▼         ▼            ▼            ▼         ▼
┌───────┐ ┌───────┐  ┌──────────┐  ┌──────────┐ ┌───────┐
│PAUSED │ │COMPLETE│  │BUDGET-  │  │BLOCKED   │ │CLEARED│
│(user) │ │(eval)  │  │LIMITED  │  │(eval)    │ │(user) │
└───────┘ └───────┘  └──────────┘  └──────────┘ └───────┘
    │                                     │
    │                                     │
    └─────────────────────────────────────┘
              │ user provides new input
              ▼
       ┌─────────────┐
       │  UNBLOCKED    │
       │ (becomes      │
       │  ACTIVE again)│
       └─────────────┘
```

The **blocked** state is notable: when the agent encounters a problem it cannot solve (e.g., a dependency is missing, a test is fundamentally broken), it transitions to BLOCKED and reports the blocker to the user. The user can then provide new input to unblock it. This is a **graceful failure mode** that Anthropic's `/goal` lacks.

> "The stopping condition may be success, pause, clear, interruption, budget limit, or a blocker that requires user input."  
> — OpenAI Codex Goals cookbook (2026-05-09)

### 1.7 Comparison with Anthropic

| Dimension | Codex Goals | Claude Code `/goal` |
|-----------|-------------|---------------------|
| State persistence | **Thread-persistent** (survives crash/restart) | **Session-scoped** (lost on new session) |
| Pause/Resume | **Native** (`/goal pause`, `/goal resume`) | **Not native** (`/goal clear` only; `--resume` restores session) |
| Goal structure | **Six-element contract** (recommended) | **Flat condition string** (up to 4K chars) |
| Anti-spin | **Tool-call gate** (suppresses if no tool calls) | **No explicit gate** |
| Blocked state | **Native** — reports blocker, waits for user | **None** — loops until interrupted |
| Evaluator model | **Undocumented** | **Haiku (explicit)** |
| Evaluator feedback | Reason + blocked state | Reason only |
| Documentation | **Partial** | **Extensive** |

---

## 2. Deep Research: The Implicit Goal Architecture

### 2.1 Overview

Deep Research (launched in ChatGPT February 2025, API available 2025) is OpenAI's **implicit goal-oriented** system. There is no `/goal` command. Instead, the user provides a research intent, and the system internally plans, executes, and decides when it has gathered "enough" information.

This is the **system-inferred completion** model — the human provides INTENT, the agent infers DONE.

### 2.2 The Three-Step Process (ChatGPT)

```
User: "Research the competitive landscape for quantum computing startups
      focused on error correction. I need a comprehensive report with
      funding rounds, key personnel, and technical differentiators."

         │
         ▼
┌─────────────────────────────────────────┐
│ Step 1: CLARIFICATION (GPT-4.1)         │
│ - Intermediate model asks follow-up     │
│   questions about preferences, goals,   │
│   or constraints                        │
│ - "Do you want to focus on US-only or   │
│   global? Should I include university   │
│   spin-offs?"                           │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Step 2: PROMPT REWRITING (GPT-4.1)      │
│ - Takes original input + clarifications │
│ - Produces a detailed, expanded prompt  │
│   for the research model                  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Step 3: DEEP RESEARCH (o3 model)        │
│ - Receives fully-formed prompt           │
│ - Plans research strategy (which sources,│
│   what order, what depth)                │
│ - Executes searches across web, files,  │
│   connected apps                         │
│ - Synthesizes findings into report      │
│ - Decides when coverage is "complete"    │
└─────────────────────────────────────────┘
         │
         ▼
User: Structured report with TOC, citations, sources
```

> "Deep Research in ChatGPT follows a three step process: 1. Clarification... 2. Prompt rewriting... 3. Deep research..."  
> — OpenAI API docs, `developers.openai.com/api/docs/guides/deep-research`

### 2.3 The API Path (No Clarification)

Via the Responses API, the developer sends a **fully-formed prompt** directly to the deep research model. There is no clarification step — the model simply starts researching based on what it receives.

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="o3",  # or o4-mini, etc.
    input="Research the competitive landscape for quantum computing...",
    # No intermediate clarification — the model starts immediately
)
```

This is the **developer-facing** version: the developer is responsible for providing all context up front, and the model is responsible for planning, searching, and stopping.

### 2.4 How Deep Research Decides "Done"

Deep Research's completion logic is **not publicly documented**. What we can infer from the behavior:

1. **Coverage-based stopping**: The model tracks which sources it has visited and stops when it believes it has covered the "important" ones. It may use a coverage heuristic (e.g., "I've seen 15 sources from 5 different categories, that's enough").

2. **Quality threshold**: The model may stop when the synthesis reaches a certain quality bar (e.g., "the report is comprehensive enough to answer the user's question").

3. **Time/resource budget**: There may be an internal time limit (Deep Research tasks can take 5–30 minutes; there's likely a ceiling).

4. **No user-defined condition**: The user cannot say "stop when you've found 3 companies with Series B funding." The system decides.

> **Assessment**: This is the **weakest part** of OpenAI's goal-oriented architecture. The user has no visibility into or control over the completion criteria. For a research task, this may be acceptable (the system is a better judge of "comprehensive" than the user). For a coding task, it would be unacceptable (the user knows exactly what "done" means).

### 2.5 The Research Plan: User-Reviewable

One redeeming feature: before starting, ChatGPT Deep Research shows a **proposed research plan** that the user can review and modify. This gives the user some control over the scope and direction, even if not the completion criteria.

```
ChatGPT: "I'll research this by:
  1. Searching for quantum computing startups focused on error correction
  2. Looking up funding rounds on Crunchbase and PitchBook
  3. Identifying key personnel from LinkedIn and company websites
  4. Comparing technical approaches from academic papers and patents
  5. Synthesizing into a structured report

  [Start Research] [Modify Plan] [Cancel]"
```

> "ChatGPT creates a proposed research plan. You can review and modify it before the research begins."  
> — OpenAI Deep Research help docs (2026-06-05)

---

## 3. Tasks: Scheduled Execution Without Convergence

### 3.1 Overview

ChatGPT Tasks (launched 2024, expanded 2025) is a **scheduled execution** system, not a goal-oriented convergence system. The user sets a task to run at a specific time (e.g., "Every morning at 9 AM, summarize my emails"), and the agent executes it once per schedule. There is no loop, no evaluator, and no convergence.

### 3.2 The Tasks Model Problem

A significant user complaint (OpenAI community forum, May 2026) is that Tasks uses a **weak model** that cannot do thorough research. Users want o3-level research for scheduled tasks, but the system uses a cheaper, faster model that produces shallow output.

> "The problem is that scheduled tasks use a very weak model that doesn't do thorough research. I would like it to do o3-level research where it makes multiple google searches and compiles a good answer. Right now it only cites a single reddit post in its answer and it's completely useless for my purposes."  
> — OpenAI Community Forum (2026-05-26)

This reveals a key tension in OpenAI's architecture: **scheduled tasks are not goal-oriented**. They are single-shot executions with a schedule trigger. There is no convergence loop, no evaluator, and no completion criteria beyond "the task ran."

### 3.3 Tasks vs. Goals

| Feature | Tasks | Codex Goals | Deep Research |
|---------|-------|-------------|---------------|
| Trigger | Time-based (cron-like) | Condition-based | Intent-based |
| Convergence | None — single shot | Yes — loop until condition met | Yes — system decides when "enough" |
| Evaluator | None | Lightweight model | Internal (undocumented) |
| User control | Schedule only | Condition + constraints | Plan review only |
| Model strength | Weak (user complaint) | Full GPT-4.1/o3 | o3 (strong) |
| Completion criteria | "Ran at scheduled time" | User-defined condition | System-inferred |

---

## 4. OpenAI's Philosophical Architecture: Intent vs. Terminal State

### 4.1 The Core Difference

Across all three products, OpenAI's architecture is **intent-driven** rather than **terminal-state-driven**:

| Level | User Provides | System Does | Example |
|-------|--------------|-------------|---------|
| **Codex Goals** | Explicit terminal state + evidence | Plans path, executes, checks | `/goal all tests pass` |
| **Deep Research** | Research intent + (optional) plan | Plans, searches, decides coverage | "Research quantum startups" |
| **Tasks** | Execution intent + schedule | Runs once at scheduled time | "Daily news summary" |
| **Traditional Chat** | Next-step prompt | Responds once, waits | "Write a function" |

OpenAI's bet is that **the system is better at defining completion criteria than the user** for open-ended tasks (research, exploration), while the user should define completion for closed-ended tasks (coding, testing). This is a **sensible bifurcation** but creates inconsistency: users must learn two different mental models.

### 4.2 No Universal `/goal` Strategy

OpenAI has not shipped a universal `/goal` command that works across ChatGPT, Codex, and the API. Each product has its own completion logic:
- Codex: explicit `/goal`
- Deep Research: implicit coverage-based stopping
- Tasks: no convergence — single-shot scheduled execution
- ChatGPT: no goal — single-turn or multi-turn with user-managed continuation

> **Assessment**: OpenAI's fragmented approach is a **strategic weakness**. Users cannot transfer goal-setting skills between products. Anthropic's unified `/goal` command (same syntax, same evaluator model, same behavior across all Claude Code surfaces) is more learnable and predictable.

### 4.3 The OpenAI Cookbook Pattern: "When to Use a Goal"

OpenAI's documentation is more **prescriptive** about when to use Goals:

**Use a Goal when:**
- Performance optimization
- Flaky test investigation
- Dependency migrations
- Bug hunts that require reproduction
- Multi-step refactors
- Benchmark-driven tuning
- Research tasks requiring a final artifact

**Use a normal prompt when:**
- One-off edits
- Inspections
- Explanations
- Focused changes

> "Use a Goal when the task has a clear finish line but the path to that finish line is uncertain. A normal prompt remains the right tool for a one-off edit."  
> — OpenAI Codex Goals cookbook (2026-05-09)

This is **good product design** — it helps users avoid over-applying the feature. Anthropic's documentation is less prescriptive, which may lead to misuse (e.g., `/goal` for tasks that don't need convergence).

---

## 5. Cost and Rate Limit Implications

### 5.1 Codex Goals Cost Model

OpenAI does not publish a detailed cost breakdown for Codex Goals. Inferences:
- The **worker** model (GPT-4.1 or o3) consumes the majority of tokens
- The **evaluator** is a lightweight model, but its cost is not separately tracked
- **Thread persistence** implies some storage cost for the goal state object, but this is likely negligible
- **No native budget cap** is documented, similar to Claude Code

### 5.2 Deep Research Cost Model

Deep Research is **expensive** by design:
- Uses the o3 model (high-capability, high-cost)
- Can run for 5–30 minutes
- Makes many web searches and reads many documents
- OpenAI charges per "task" for ChatGPT Plus users, with a monthly allowance

> "Deep research usage varies by plan. Your in-product usage counter shows your remaining tasks. For plans with a fixed monthly allowance, it resets every 30 days from the date of your first use."  
> — OpenAI Deep Research help docs (2026-06-05)

### 5.3 Tasks Cost Model

Tasks are **cheap** (hence the user complaint about weak output):
- Single-shot execution
- Uses a lightweight model
- No convergence loop = no repeated token burn

The trade-off is quality: the model doesn't have the time or capability to do thorough work.

---

## 6. Security and Safety

### 6.1 Codex Goals Security Model

Codex inherits the same security model as the broader OpenAI platform:
- **API key authentication** — standard OpenAI API key management
- **Rate limiting** — per-model RPM and TPM limits
- **No explicit sandbox** — Codex runs in the user's local environment with the user's permissions
- **Trust model** — the user must trust the agent to run commands and edit files

OpenAI's documentation mentions **no specific security features** for Goals beyond the standard platform protections. This is a **gap** — Anthropic's explicit trust dialog, hooks system, and sandboxing are more robust.

### 6.2 Deep Research Security Model

Deep Research has **read-only access** to connected apps (Google Drive, SharePoint, etc.). It does not use write actions. This is a **deliberate safety boundary**:

> "Deep research only uses read actions from connected apps. It does not use app write actions as part of research."  
> — OpenAI Deep Research help docs (2026-06-05)

However, Deep Research can **generate and publish reports** — the output is user-visible and user-controllable. The risk is lower than a coding agent that can modify files.

### 6.3 The OpenAI Safety Gap: No Explicit Goal-Level Permissions

Neither Codex Goals nor Deep Research has **goal-level permission controls**. For example:
- No way to restrict which files a goal can modify
- No way to restrict which commands a goal can run
- No way to set a "dry run" mode where the goal plans but doesn't execute
- No way to require human approval for specific actions within a goal

Anthropic's hooks system (`PreToolUse`, `PostToolUse`, `deny-first` rules) provides these controls. OpenAI's approach is **simpler but less secure** for high-risk operations.

---

## 7. Research Questions Answered (This File)

| Question | Answer | Confidence |
|----------|--------|------------|
| What is OpenAI's current status on explicit `/goal`? | **Shipped in Codex** (v0.128.0, April 2026), but **not universal** — ChatGPT and Deep Research use implicit completion. No roadmap for universal `/goal` has been published. | **VERIFIED** for Codex; **INFERENCE** for broader strategy |
| How does OpenAI handle impossible goals? | **Codex**: Native BLOCKED state — reports blocker, waits for user input. **Deep Research**: System decides when to stop, may return partial report. **Tasks**: No convergence — just runs once. | **VERIFIED** for Codex; **INFERENCE** for Deep Research |
| How does OpenAI manage cost in goal loops? | **No native budget cap** documented. Codex mentions "budget limit" as a stop condition but mechanism is unspecified. Deep Research uses per-task allowances. Tasks are cheap but weak. | **VERIFIED** (lack of documentation) |
| What are the security implications? | **Standard OpenAI API security** — no goal-specific sandboxing or permission controls. Deep Research is read-only for connected apps. Less granular than Anthropic's hooks system. | **VERIFIED** |

---

## Next File

→ `04-strengths-weaknesses.md` — Detailed SWOT analysis of both systems, with critical assessment of marketing claims vs. reality.
