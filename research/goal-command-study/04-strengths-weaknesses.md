# Strengths and Weaknesses: Anthropic vs. OpenAI Goal-Oriented Architectures

> Research File: `04-strengths-weaknesses.md`  
> Research Agent: Cipher Laere (Laere Enterprises)  
> Date: 2026-06-05  
> Status: Complete  
> Sources: All prior files in this series, plus arXiv:2604.14228v1 (Claude Code architecture), juejin.cn cost analysis (2026-05-16), SitePoint rate limits (2026-03-13), Faros token limits (2025-12-04), apiyi.com risk analysis (2026-05-13), OpenAI community forum (2026-05-26), aaia.app security research (2026-01-13)

---

## Executive Summary

Both Anthropic and OpenAI have shipped `/goal` or goal-oriented features in mid-2026, but neither implementation is without significant flaws. Anthropic's approach excels in transparency, evaluator separation, and user control, but lacks native state persistence, budget management, and stuck-loop detection. OpenAI's approach offers richer goal contracts, thread persistence, and a blocked-state failure mode, but suffers from opaque evaluator architecture, fragmented product strategy, and weaker security granularity. This document provides a rigorous SWOT analysis, calls out marketing fluff, and identifies specific gaps that Laere's hybrid architecture should address.

---

## 1. Anthropic Claude Code `/goal`: Strengths

### 1.1 Architectural Elegance: Worker-Evaluator Separation

The single most important design decision in Anthropic's `/goal` is the **explicit separation of the worker model from the evaluator model**. This is not a convenience — it is a structural safeguard against a class of failure modes that every other agent system suffers from.

**Why it matters:** When the same model both performs work and judges whether the work is complete, it suffers from **completion bias** — the tendency to interpret ambiguous evidence as confirming success. The model that wrote the code "wants" to believe the tests pass. The evaluator, having written nothing, has no ego in the game.

> "The model doing the work isn't the model judging whether it's done. The judge is fresh every turn, doesn't have the ego of having written the code, and gets one job: read the transcript, return yes or no plus a one-line reason."  
> — findskill.ai, "Claude Code /goal: Set a Finish Line, Walk Away" (2026-05-13)

**Evidence of effectiveness:** The community has not reported widespread "evaluator hallucination" (false positives) for well-written conditions. The failure mode is primarily false negatives (evaluator correctly says NO, but the worker is stuck), not false positives.

### 1.2 Evaluator Transparency: Haiku is Explicit and Auditable

Anthropic explicitly names **Haiku** as the default evaluator. This matters for:
- **Cost prediction**: Users know exactly what each evaluator call costs (~$1/$5 per million tokens)
- **Capability calibration**: Users know Haiku's limitations (no deep reasoning, 200K context, SWE-bench 73.3%)
- **Debugging**: When the evaluator is wrong, users can reproduce its behavior by calling Haiku directly
- **Fairness**: No suspicion that the evaluator is a special, undisclosed model

Compare to OpenAI, where the evaluator model is **undocumented**. Users cannot verify its behavior, predict its cost, or debug its failures.

### 1.3 Simple, Learnable Interface

The `/goal` command has exactly one required argument: a condition string. There are no configuration files, no JSON schemas, no setup overhead. This is the **minimum viable interface** for goal-oriented execution:

```
/goal all tests in test/auth pass and the lint step is clean
```

The 4,000-character limit is generous enough for compound conditions but small enough to prevent users from writing novel-length requirements. The interface is **discoverable** — it appears in the same command surface as every other Claude Code command.

### 1.4 Session-Scoped Simplicity

The goal is **session-scoped** — it lives in the current session and dies when the session ends. This is a **feature, not a bug**, for short-lived tasks (10–30 minutes). It means:
- No accidental long-running goals from yesterday's session
- No cross-session pollution of goals
- Simple mental model: one session = one goal = one task

For long-lived tasks, `--resume` can restore the session. This is a reasonable trade-off.

### 1.5 Integration with Existing Security Infrastructure

`/goal` inherits Claude Code's **hooks system**, **trust dialog**, **permission modes**, and **sandboxing**. It is not a new security surface — it is a new command on an existing security surface. This means:
- Existing `.claudeignore` rules apply to goal-driven file edits
- Existing `PostToolUse` hooks auto-run lint/type-checking after goal-driven edits
- Existing `PreToolUse` hooks can deny dangerous commands even within a goal loop
- The trust dialog prevents accidental goal activation in untrusted workspaces

> "`/goal` runs only in workspaces where you've accepted the trust dialog. It's unavailable when `disableAllHooks` is set..."  
> — Anthropic Claude Code docs (2026-06-01)

### 1.6 Community Ecosystem and Best Practices

The Anthropic community has rapidly developed best practices for `/goal`:
- **CLAUDE.md** files for consistent cross-turn context
- **PostToolUse hooks** for auto-validation after every edit
- **Auto mode + `/goal`** as the canonical unattended pattern
- **Sequential goal decomposition** for compound tasks
- **Turn caps** (`stop after 20 turns`) as a cost-safety pattern

This ecosystem maturity is a real strength — users are not figuring it out alone.

---

## 2. Anthropic Claude Code `/goal`: Weaknesses

### 2.1 No Native State Persistence

The session-scoped model is elegant for short tasks, but **brittle for long tasks**:
- Session crashes lose the goal (and the conversation history that the evaluator needs)
- Context compaction can drop critical evidence that the evaluator needs
- `--resume` restores the session but does not guarantee the goal is still active or the context is intact
- No way to explicitly save/restore a goal state

**Real-world impact:** A 14-hour migration that crashes on turn 89 loses all progress context. The user must restart with a new goal, potentially re-exploring the same solution space.

> **Marketing fluff to call out:** Anthropic's documentation mentions `--resume` as a recovery mechanism, but `--resume` is a session feature, not a goal feature. It does not save the goal state explicitly. The gap is real.

### 2.2 No Native Budget or Turn Cap Management

This is the **most critical weakness**. Anthropic provides:
- No per-goal token budget
- No per-goal turn cap (must be written into the condition string)
- No real-time cost alerts during goal execution
- No automatic "cost so far" reporting
- No progress-based kill switch

The community has documented **$200 burned in 14 hours** by an aggressive `/goal` loop:

> "14 小时烧光 200 美金：Codex 和 Claude 的 /goal 命令打开了'放手跑'模式"  
> — juejin.cn (2026-05-16)

The workaround — `stop after N turns` in the condition string — is **user-managed, not system-managed**. This is like asking a compiler to prevent infinite loops by requiring the programmer to add a counter. It is a primitive safety mechanism.

**The deeper problem:** Even with a turn cap, there is no **cost-per-turn tracking**. A single turn with Opus on a large codebase can cost $5–$10. A 20-turn cap could still burn $100–$200. The user cannot know the cost until they check the dashboard afterward.

### 2.3 No Stuck-Loop Detection

Anthropic's `/goal` has **no mechanism to detect when the worker is making no progress**. The evaluator will say "NO" for the same reason 20 times in a row. The worker will try the same fix 20 times. Neither the system nor the user is alerted until the turn cap is reached or the budget is exhausted.

This is a **convergence failure mode** that is trivial to detect:
- Compare the last N turns' outputs
- If the test failures are identical, the worker is stuck
- If the file diffs are identical (or oscillating A→B→A), the worker is looping
- Alert the user and suggest `/goal clear` or a different strategy

This feature does not exist. It should.

> **Assessment:** This is a genuine safety gap. A stuck loop is not just a cost problem — it is a **security problem** if the stuck loop is making destructive edits (e.g., repeatedly deleting and recreating a file, corrupting git history).

### 2.4 Evaluator Cannot Verify What the Worker Doesn't Surface

The evaluator's **read-only, transcript-bound** design is architecturally sound but creates a **user-responsibility gap**. The user must ensure that the worker runs the right verification commands and includes the output in the transcript. If the worker "forgets" to run the tests, the evaluator has no way to know.

This is a **leaky abstraction** — the user must understand the evaluator's limitations to write effective conditions. A user who writes `/goal the code is correct` without specifying a test command will get a loop that produces no verifiable evidence and eventually hallucinates success.

### 2.5 No Rich Goal Metadata

Anthropic's flat condition string (up to 4,000 characters) is simple but **underspecified**. It cannot express:
- **Iteration policy** (how should the worker choose the next action?)
- **Blocked stop condition** (what should the worker report if it gets stuck?)
- **File boundaries** (which files should the worker not touch?)
- **Tool boundaries** (which commands should not be run?)
- **Progress checkpoints** (where should the worker save intermediate state?)

These must be inferred from the condition text or written in `CLAUDE.md` or hooks. OpenAI's six-element goal contract is more expressive, though more complex.

### 2.6 Rate Limit and Context Window Pressure

`/goal` amplifies existing rate limit problems:
- A 10-turn goal can generate 80–120 API calls in a short burst
- At Pro's 50 RPM, this exhausts the per-minute budget in ~2 minutes
- The 5-hour rolling window (44K tokens for Pro) can be consumed by a single aggressive goal
- Opus 4.7 costs ~1.7x Sonnet 4.6, so goals with Opus exhaust budgets faster

The user has no way to **pace** the goal loop — it runs at maximum speed until completion or exhaustion.

> "A single user-visible command in Claude Code can generate multiple API calls due to tool use, so a 'lint, fix, test, fix' cycle might produce 8 to 12 API calls within 60 seconds."  
> — SitePoint, "Claude Code Rate Limits Explained" (2026-03-13)

---

## 3. OpenAI Codex Goals: Strengths

### 3.1 Thread-Persistent Goal State

Codex Goals are **persisted in the thread**, not just the session. This means:
- Goal survives session crashes
- Goal survives `/goal pause` and `/goal resume`
- Goal metadata is preserved across context compaction
- Goal can be resumed days later

This is a **genuine architectural advantage** for long-running tasks (multi-day migrations, complex refactors). The user does not need to remember the exact condition wording or reconstruct the conversation history.

### 3.2 Native Blocked State: Graceful Failure

Codex has a **BLOCKED state** — when the worker cannot make progress, it transitions to BLOCKED and reports the blocker to the user. The user can then provide new input to unblock it. This is a **graceful failure mode** that Anthropic lacks.

Example:
```
Worker: Cannot proceed — test failures are caused by a dependency
        version mismatch (lodash 3.x vs 4.x). The migration guide
        requires manual intervention.

Codex: [BLOCKED] Dependency version mismatch detected.
        Attempted: upgrade package.json, update imports, run tests.
        Blocker: lodash 3.x → 4.x breaking changes not fully automated.
        Next input needed: Confirm manual migration strategy or
        provide compatible dependency version.

User: [provides input] → Goal resumes as ACTIVE
```

This is **user-friendly** and **safe** — the system doesn't burn tokens looping on an impossible problem.

### 3.3 Conservative Continuation Dispatcher

The anti-spin protection is a **real, implemented feature** that prevents the most common failure mode of autonomous loops: the model generating text that looks like work but isn't actually doing anything.

```python
# Codex's continuation gate (inferred)
if last_turn_tool_calls == 0:
    suppress_next_continuation()  # Don't spin
```

This is simple but effective. If the worker says "I think I need to analyze the code more carefully" without actually reading a file or running a command, the loop stops. The user must manually continue.

### 3.4 Rich Goal Contract: Six Elements

The six-element goal structure is **more expressive** than Anthropic's flat string:

```
1. Outcome: what should be true
2. Verification surface: how to prove it
3. Constraints: what must not regress
4. Boundaries: which files/tools/data may be used
5. Iteration policy: how to choose next action
6. Blocked stop condition: what to report when stuck
```

This allows **fine-grained control** over the agent's behavior. For example, the iteration policy can instruct the worker to "try the most likely fix first, then explore edge cases" — a strategy that Anthropic's flat condition cannot express.

However, the six-element structure is **recommended, not enforced**. The user can still write a simple string. This is the right design: simple tasks stay simple, complex tasks get structure.

### 3.5 Event-Driven, Not Loop-Driven

Codex's continuation is **event-driven** (checks at safe boundaries) rather than **loop-driven** (blindly repeats). This means:
- No polling or busy-waiting
- No continuation while user input is queued
- No continuation while other work is pending
- Respects the user's interaction flow

This is a **more polite, more robust** design than a simple `while not done: turn()` loop.

### 3.6 Deep Research's Research Plan Review

Before starting, ChatGPT Deep Research shows a **proposed research plan** that the user can review and modify. This gives the user **control over scope and direction**, even if not over completion criteria. It is a **meaningful user-empowerment feature** that Anthropic's `/goal` does not have (the goal starts immediately).

---

## 4. OpenAI Codex Goals: Weaknesses

### 4.1 Opaque Evaluator Architecture

OpenAI does not document:
- Which model evaluates the goal
- How the evaluator is prompted
- What the evaluator's context window is
- How the evaluator handles ambiguous conditions
- How to debug evaluator failures

This is **not just a transparency issue** — it is a **trust and reliability issue**. Users cannot:
- Predict evaluator cost (is it GPT-4.1-mini at $0.40/$1.60? or a custom model?)
- Reproduce evaluator behavior for debugging
- Verify that the evaluator is fair and not biased toward declaring success
- Tune the evaluator's sensitivity (e.g., "be strict about test failures")

> **Marketing fluff to call out:** OpenAI's documentation says "Goals are implemented as persisted thread state" — but it doesn't say what the evaluator is, how it works, or what its failure modes are. This is "trust us, it works" engineering, not "here's how you verify it" engineering.

### 4.2 No Universal `/goal` Across Products

OpenAI's `/goal` is **Codex-only**. It does not exist in:
- ChatGPT (no goal command at all)
- Deep Research (system decides when done)
- Tasks (single-shot, no convergence)
- The API (no explicit goal mechanism; developers must build their own)

This means:
- Users cannot transfer goal-setting skills between products
- There is no consistent mental model for "when to use a goal"
- Each product has its own completion semantics
- Enterprise users cannot standardize on a single goal-oriented workflow

Anthropic's `/goal` is **Claude Code-wide** — same syntax, same evaluator, same behavior across interactive, non-interactive, and Remote Control modes.

### 4.3 No Native Sandbox or Goal-Level Permissions

Codex Goals run in the user's local environment with **no additional sandboxing** beyond the standard Codex security model. There are no:
- Goal-specific file boundaries
- Goal-specific command allowlists
- Goal-specific network restrictions
- Goal-specific human-in-the-loop gates

Anthropic's hooks system (`PreToolUse`, `PostToolUse`, `deny-first` rules) provides **granular, per-action security controls** that Codex Goals lack. A goal in Codex can delete any file the user has permissions to delete, with no additional gate.

> **Security assessment:** This is a **meaningful gap**. For a goal that runs for 10 turns unattended, the cumulative risk of a destructive action is higher than for a single turn. Codex should provide goal-level permission boundaries.

### 4.4 Tasks Uses Weak Model: Strategic Confusion

ChatGPT Tasks is **not a goal-oriented system** — it is a scheduled execution system. But users expect it to be, because it has the word "task" in the name and it runs automatically. The complaint that Tasks uses a "very weak model" reveals a **product strategy confusion**:

> "The problem is that scheduled tasks use a very weak model that doesn't do thorough research. I would like it to do o3-level research where it makes multiple google searches and compiles a good answer."  
> — OpenAI Community Forum (2026-05-26)

OpenAI has three execution patterns with three different completion models and three different model strengths:
- **Goals** (Codex): strong model, convergence loop, explicit condition
- **Deep Research** (ChatGPT): strong model, coverage-based stopping, no user condition
- **Tasks** (ChatGPT): weak model, no convergence, scheduled execution

This is **strategic fragmentation**. Users don't know which tool to use for which task. Anthropic's approach — one `/goal` command that works the same way everywhere — is more coherent.

### 4.5 Deep Research's Undocumented Completion Logic

Deep Research's stopping criteria are **completely opaque**:
- Is it coverage-based? ("I've seen 15 sources, that's enough")
- Is it quality-based? ("The report is comprehensive enough")
- Is it time-based? ("5 minutes have passed, wrap up")
- Is it user-preference-based? ("The user said 'brief', so I'll stop sooner")
- Is it all of the above? In what weights?

Users have **no control** and **no visibility**. They cannot:
- Set a minimum number of sources
- Set a maximum research time
- Set a specific depth level
- Require coverage of specific topics
- Verify that the research was actually "complete"

> **Critical assessment:** This is a **trust failure**. A research system that decides when it's done without telling the user how it decided is not verifiable. For enterprise use cases (due diligence, legal research, scientific review), this is unacceptable. Anthropic's `/goal` is better here because the user defines the finish line — even if the finish line is "find 10 sources on X and summarize them."

### 4.6 No Per-Goal Cost Tracking

Like Anthropic, OpenAI provides **no per-goal cost breakdown**. Users cannot see:
- How much the goal cost so far
- How much each turn cost
- How much the evaluator cost
- Projected total cost at current pace
- Cost per unit of work (e.g., "$0.50 per test fixed")

This is a **shared weakness** — both systems treat cost as a post-hoc analytics problem, not a real-time control problem.

---

## 5. Comparative SWOT Summary

### Anthropic Claude Code `/goal`

| **Strengths** | **Weaknesses** |
|---------------|----------------|
| Explicit worker-evaluator separation (Haiku) | No native state persistence (session-scoped) |
| Evaluator model is transparent and auditable | No native budget/turn cap management |
| Simple, learnable interface | No stuck-loop detection |
| Session-scoped simplicity (no accidental long-running goals) | Evaluator cannot verify what worker doesn't surface |
| Integrates with existing security infrastructure (hooks, trust dialog) | No rich goal metadata (flat string only) |
| Mature community best practices | Rate limit and context window pressure |
| **Opportunities** | **Threats** |
| Add thread persistence for long-running goals | Competitors (OpenAI, Google) may ship better persistence |
| Add stuck-loop detection and progress tracking | Cost overruns damage user trust and adoption |
| Add per-goal cost tracking and alerting | Rate limits make goal loops impractical for power users |
| Add richer goal metadata (optional structured format) | Evaluator hallucination on vague goals damages reputation |

### OpenAI Codex Goals

| **Strengths** | **Weaknesses** |
|---------------|----------------|
| Thread-persistent goal state | Opaque evaluator architecture (undocumented model) |
| Native BLOCKED state for graceful failure | No universal `/goal` across products (fragmented strategy) |
| Conservative continuation dispatcher (anti-spin) | No native sandbox or goal-level permissions |
| Rich six-element goal contract | Tasks uses weak model — strategic confusion |
| Event-driven continuation (respects user interaction) | Deep Research completion logic is completely opaque |
| Deep Research plan review before execution | No per-goal cost tracking |
| **Opportunities** | **Threats** |
| Document the evaluator model and make it configurable | Anthropic's simpler model may win adoption |
| Unify goal semantics across Codex, ChatGPT, and API | Opaque completion logic damages enterprise trust |
| Add goal-level sandboxing and permissions | Cost overruns without transparency |
| Add explicit completion criteria to Deep Research | Community frustration with fragmented product strategy |

---

## 6. What Both Systems Get Wrong

### 6.1 Cost is an Afterthought

Neither system treats cost as a **first-class control variable**. The user should be able to:
- Set a max dollar cost per goal
- Set a max token cost per goal
- Set a max time per goal
- Get real-time alerts at 50%, 75%, 90% of budget
- Choose a "cost-efficient" mode (Haiku worker for simple tasks, Sonnet for complex)
- See a post-goal cost breakdown (worker tokens, evaluator tokens, tool call costs)

**Neither system does this.** Both require the user to manually monitor the dashboard or include a turn cap in the condition string. This is **primitive** for 2026.

### 6.2 No Progress Dashboard

Neither system provides a **real-time progress view** beyond "turn count and token spend." The user should be able to see:
- What the worker has accomplished so far (checklist of sub-goals)
- What the evaluator's last N reasons were (progression or repetition?)
- Whether the worker is making progress or stuck (detect oscillation)
- Estimated completion time (based on current pace)
- Risk indicators ("worker has modified 12 files in the last 3 turns, possible scope creep")

### 6.3 No Evaluator Calibration

Neither system lets the user **tune the evaluator's strictness**:
- "Strict mode" — evaluator requires 100% test pass, no warnings
- "Lenient mode" — evaluator allows 95% test pass, some lint warnings
- "Custom mode" — user provides a custom evaluation script

Anthropic's Haiku is fixed. OpenAI's evaluator is unknown. Both should be configurable.

### 6.4 No Multi-Goal Orchestration

Neither system supports **multiple concurrent or sequential goals** within a single session/thread:
- No way to queue goals ("after goal A finishes, start goal B")
- No way to run goals in parallel ("migrate module A and module B simultaneously")
- No way to define goal dependencies ("goal B depends on goal A's output")
- No way to define a goal hierarchy ("parent goal: refactor auth; sub-goals: update tests, update docs, update config")

For enterprise workflows, this is a **major gap**. A migration is not a single goal — it is a project with milestones, dependencies, and parallel workstreams.

### 6.5 No Human-in-the-Loop Checkpoints

Neither system supports **automatic human checkpoints**:
- "Pause every 5 turns and show me what changed"
- "Pause before modifying any file in `src/critical/`"
- "Pause before running any command that costs >$0.01 in API calls"
- "Pause if the evaluator's reason has been the same for 3 turns"

Anthropic's permission system provides per-action gates, but these are **reactive** (the user must approve each action). There are no **proactive** checkpoints that pause the goal to let the user review progress.

---

## 7. Research Questions Answered (This File)

| Question | Answer | Confidence |
|----------|--------|------------|
| How do goal-oriented workflows handle cost management? | **Both systems fail here.** No native per-goal budget, no real-time cost tracking, no stuck-loop detection. Anthropic's Haiku evaluator is cheap; OpenAI's evaluator is unknown. Turn caps are user-managed. | **VERIFIED** — Multiple community cost reports, official docs |
| What are the security implications? | **Anthropic is stronger** — inherits hooks, trust dialog, sandboxing, deny-first rules. **OpenAI is weaker** — no goal-specific permissions, no sandbox, standard API security only. Both lack progress-based kill switches. | **VERIFIED** — arXiv paper, security research, official docs |
| Where does each approach excel? | **Anthropic**: transparency, evaluator separation, simplicity, security integration. **OpenAI**: persistence, blocked state, rich contracts, anti-spin. | **VERIFIED** — Comparative analysis |
| Where does each approach fail? | **Anthropic**: no persistence, no budget management, no stuck detection, flat goal format. **OpenAI**: opaque evaluator, fragmented strategy, no sandbox, undocumented completion logic. | **VERIFIED** — Comparative analysis |

---

## Next File

→ `05-laere-synthesis.md` — Proposed hybrid methodology that takes the best of both systems and adds Laere-specific improvements.
