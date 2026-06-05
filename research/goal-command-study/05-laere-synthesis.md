# Laere Synthesis: A Hybrid Goal-Oriented Architecture

> Research File: `05-laere-synthesis.md`  
> Research Agent: Cipher Laere (Laere Enterprises)  
> Date: 2026-06-05  
> Status: Complete  
> Sources: All prior files in this series, plus Laere Enterprise context (Orthia, Grace, Cipher agent definitions), OpenClaw taskflow system documentation, and multi-agent orchestration patterns from arXiv:2604.14228v1 and aaia.app security research (2026-01-13)

---

## Executive Summary

Anthropic and OpenAI have each shipped half of the right architecture. Anthropic has the right **evaluator separation** (Haiku) and **security integration** (hooks, trust dialog), but lacks **persistence**, **budget management**, and **stuck-loop detection**. OpenAI has the right **rich goal contracts** (six elements), **blocked-state failure mode**, and **anti-spin protection**, but lacks **evaluator transparency**, **universal scope**, and **goal-level security**.

Laere Enterprises should synthesize a **hybrid goal-oriented architecture** that takes the best of both and adds capabilities specific to Laere's multi-agent system (Orthia, Grace, Cipher, and future agents). This document proposes that architecture, defines the Laere Goal Contract (LGC), and maps it to Laere's existing agent roles.

---

## 1. Design Principles for Laere's Goal Architecture

Based on the research in this series, we define five design principles:

### Principle 1: Explicit Evaluator Separation (From Anthropic)

The worker model and the evaluator model **must be different models**. This is non-negotiable. It prevents completion bias, enables cost optimization (cheap evaluator, capable worker), and allows independent debugging.

**Laere specific:** Orthia (main agent) and Grace (research agent) should be workers. A dedicated **Goal Evaluator** (a lightweight, fast model) should be the judge. The evaluator should be **swappable** — different tasks may need different evaluation strictness.

### Principle 2: Rich Goal Contracts (From OpenAI)

A goal is not a string. It is a **structured contract** with at minimum:
- Outcome (what "done" means)
- Verification (how to prove it)
- Constraints (what must not change)
- Boundaries (what the agent may touch)
- Budget (max turns, max tokens, max time, max cost)
- Failure mode (what to do when stuck)
- Checkpoints (when to pause for human review)

**Laere specific:** The contract should be **machine-readable** (JSON/YAML) so that agents can programmatically read, modify, and report on it. It should be **versioned** so that goal evolution is tracked.

### Principle 3: Multi-Agent Goal Awareness (Laere Innovation)

Goals should be **visible across agents**. If Grace starts a research goal, Orthia should be able to see its status, check its progress, and interrupt it if needed. If Cipher produces a research artifact, Orthia should verify that the artifact meets the goal's verification criteria before routing it to Shawn.

This requires a **shared goal registry** — not just per-session or per-thread state, but a **workspace-level** goal store that all agents can read and write.

### Principle 4: Progressive Autonomy with Human Checkpoints (Laere Innovation)

The default should not be "run unattended until done." The default should be **progressive autonomy**:
- Level 1: Human approves every turn (training wheels)
- Level 2: Human approves every N turns (review checkpoints)
- Level 3: Human approves only on stuck-loop detection or budget threshold
- Level 4: Full unattended (Shawn's explicit opt-in)

Each level should be **goal-specific**, not session-global. Shawn should be able to set Level 4 for a well-understood refactor and Level 1 for a risky architecture change.

### Principle 5: Transparent, Real-Time Cost and Progress Tracking (Laere Innovation)

Every goal should have a **live dashboard** showing:
- Turns elapsed, turns remaining (if capped)
- Tokens spent, token budget remaining
- Estimated cost so far, cost budget remaining
- Current sub-task, overall progress %
- Last evaluator reason, trend of evaluator reasons (converging or stuck?)
- Risk indicators (scope creep, file touch count, destructive action count)

This should be visible to Shawn and to all agents. It is not an afterthought — it is a **primary UI element** of the goal system.

---

## 2. The Laere Goal Contract (LGC)

### 2.1 Schema Definition

```yaml
# Laere Goal Contract (LGC) — Version 1.0

lgc_version: "1.0"

# --- Core Definition ---
goal_id: "lgc-2026-06-05-001"          # Unique ID, auto-generated
created_by: "Orthia"                    # Agent or user that created the goal
assigned_to: "Cipher"                   # Primary worker agent
created_at: "2026-06-05T13:00:00-07:00"
status: "active"                        # active | paused | blocked | completed | failed | cancelled

# --- Outcome (What "done" means) ---
outcome:
  description: "All tests in test/auth pass and lint is clean"
  verification:
    type: "command_output"              # command_output | file_state | artifact_exists | human_review | agent_eval
    command: "npm test -- test/auth && npm run lint"
    expected_exit_code: 0
    expected_output_contains: "passing"
    timeout_seconds: 120
  # Allow multiple verification methods (all must pass)
  additional_verifications:
    - type: "file_state"
      path: "test/auth/"
      condition: "all files have corresponding .test.js files"

# --- Constraints (What must not change) ---
constraints:
  - "Do not modify any file outside src/auth/ and test/auth/"
  - "Do not upgrade any dependencies"
  - "Do not change the public API surface"
  - "Do not delete existing tests without adding equivalent replacements"

# --- Boundaries (What the agent may touch) ---
boundaries:
  allowed_paths:
    - "src/auth/**"
    - "test/auth/**"
  allowed_commands:
    - "npm test"
    - "npm run lint"
    - "git diff"
    - "git status"
  forbidden_paths:
    - "src/payments/**"
    - "config/production.yml"
  forbidden_commands:
    - "git push"
    - "npm publish"
    - "rm -rf"

# --- Budget (Hard limits) ---
budget:
  max_turns: 20                           # 0 = unlimited
  max_tokens: 500000                    # 0 = unlimited
  max_time_minutes: 60                  # 0 = unlimited
  max_cost_usd: 50.00                   # 0 = unlimited
  # Soft thresholds for alerts
  alert_thresholds:
    turns: 15
    tokens: 400000
    time_minutes: 45
    cost_usd: 40.00

# --- Failure Mode (What to do when stuck) ---
failure_mode:
  stuck_detection:
    enabled: true
    max_repeated_evaluator_reason: 3      # Alert if same reason for N turns
    max_oscillating_changes: 3            # Alert if same file changed back-and-forth
    max_zero_progress_turns: 5            # Alert if no verification improvement for N turns
  on_stuck:
    action: "pause_and_notify"            # pause_and_notify | escalate_to_human | auto_retry_with_new_strategy | cancel
    notify: ["Orthia", "Shawn"]
    message: "Goal appears stuck. Last 3 evaluator reasons are identical. Recommend review."
  on_blocked:
    action: "escalate_to_human"
    report_format: "structured_blocker"   # What the agent should report

# --- Checkpoints (Human review gates) ---
checkpoints:
  - type: "every_n_turns"
    n: 5
    action: "summarize_and_notify"
    notify: ["Shawn"]
    message: "Progress summary after {turns} turns. Modified files: {files}. Test status: {test_status}."
  - type: "before_destructive_action"
    action: "require_human_approval"
    destructive_actions: ["delete_file", "move_file", "rename_class", "change_public_api"]
  - type: "before_boundary_violation"
    action: "require_human_approval"
    # Triggered if agent attempts to touch forbidden_path or run forbidden_command

# --- Iteration Policy (How the worker should choose next actions) ---
iteration_policy:
  strategy: "fix_failures_first"          # fix_failures_first | breadth_first | depth_first | random_exploration
  priority_order:
    - "Fix compilation errors"
    - "Fix failing tests"
    - "Fix lint warnings"
    - "Refactor for clarity"
  record_changes: true                  # Worker should record what changed each turn
  record_experiments: true              # Worker should record what was tried and result

# --- Multi-Agent (Laere-specific) ---
multi_agent:
  shared: true                          # Visible to all agents in workspace
  readable_by: ["Orthia", "Grace", "Cipher"]
  writable_by: ["Orthia", "Cipher"]       # Who can modify the goal state
  # Sub-goals (for complex tasks that need multiple agents)
  sub_goals:
    - goal_id: "lgc-2026-06-05-001-a"
      description: "Update auth module implementation"
      assigned_to: "Cipher"
      depends_on: []                      # No dependencies
    - goal_id: "lgc-2026-06-05-001-b"
      description: "Update auth tests"
      assigned_to: "Grace"
      depends_on: ["lgc-2026-06-05-001-a"]  # Wait for implementation

# --- Metadata ---
metadata:
  tags: ["refactor", "auth", "tests", "high-priority"]
  project: "laere-platform"
  priority: 2                             # 1 = highest
  estimated_effort: "medium"              # small | medium | large | epic
  related_goals: ["lgc-2026-06-04-012"]
```

### 2.2 Why This Schema Matters

The LGC is not just documentation — it is **executable configuration**. Every field is machine-readable and can be used by:
- **Orthia** to route the goal to the right agent, set up monitoring, and enforce checkpoints
- **Grace** to read the goal's status, pick up sub-goals, and report on dependencies
- **Cipher** to read the iteration policy, verify the constraints, and report progress
- **Shawn** to review the goal status, approve checkpoints, and modify the contract mid-flight
- **The system** to enforce boundaries, detect stuckness, and trigger alerts

### 2.3 Comparison to Existing Formats

| Feature | Anthropic Flat String | OpenAI Six-Element Contract | **Laere Goal Contract** |
|---------|----------------------|----------------------------|------------------------|
| Machine-readable | ❌ No | ❌ No (text-only recommendation) | ✅ YAML/JSON schema |
| Budget management | ❌ No | ⚠️ Mentioned but unspecified | ✅ Hard limits + soft alerts |
| Stuck detection | ❌ No | ❌ No | ✅ Configurable detectors |
| Checkpoints | ❌ No | ❌ No | ✅ Multi-type human gates |
| Multi-agent | ❌ No | ❌ No | ✅ Shared registry, sub-goals |
| Boundaries | ❌ No (must use hooks) | ⚠️ Mentioned in contract | ✅ Explicit allowed/forbidden lists |
| Iteration policy | ❌ No | ✅ Yes (OpenAI's best feature) | ✅ Yes, with strategy enum |
| Failure mode | ❌ No | ✅ BLOCKED state (Codex only) | ✅ Multiple actions per trigger |

---

## 3. The Laere Goal Evaluator: Architecture

### 3.1 Evaluator Requirements

Based on the research, the Laere evaluator must:
1. **Be a different model from the worker** (Principle 1)
2. **Be transparent** — name, version, cost, and capabilities must be documented
3. **Be configurable** — different strictness levels for different goals
4. **Be fast** — evaluation should take <1 second and cost <$0.01 per call
5. **Be multi-modal** — it should evaluate not just text but also:
   - File diffs (has the code changed? is it better?)
   - Command outputs (test results, lint results)
   - Agent reports (what the worker says it did)
   - External metrics (benchmark scores, coverage percentages)

### 3.2 Proposed Evaluator Stack

```
┌─────────────────────────────────────────────────────────────┐
│                  LAERE GOAL EVALUATOR                        │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  FAST CHECK     │  │  STRUCTURED     │  │  DEEP       │ │
│  │  (Rule-based)   │  │  EVALUATION     │  │  REVIEW     │ │
│  │                 │  │  (Lightweight   │  │  (Human or  │ │
│  │  - Exit code     │  │  LLM — Haiku    │  │  Strong     │ │
│  │  - File count    │  │  or equivalent) │  │  model)     │ │
│  │  - Byte diff     │  │                 │  │             │ │
│  │  - Regex match   │  │  - Reasoning    │  │  - On       │ │
│  │                 │  │  - Ambiguity    │  │  checkpoint │ │
│  │  Cost: ~$0       │  │  - Quality      │  │  - On stuck │ │
│  │  Time: <10ms     │  │  - Architecture │  │  - On       │ │
│  │                 │  │                 │  │  boundary   │ │
│  │  Runs first      │  │  Cost: ~$0.01   │  │  violation  │ │
│  │  (cheap filter)  │  │  Time: <1s      │  │             │ │
│  │                 │  │                 │  │  Cost:      │ │
│  │                 │  │  Runs second     │  │  variable   │ │
│  │                 │  │  (judgment call) │  │  Time:      │ │
│  │                 │  │                 │  │  minutes    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│                                                             │
│  Verdict: PASS / FAIL / NEEDS_REVIEW / STUCK / BLOCKED      │
│  Reason: "3 tests still failing in test/auth/login.test.js"  │
│  Confidence: 0.95                                           │
│  Action: CONTINUE / PAUSE / ESCALATE / CANCEL               │
└─────────────────────────────────────────────────────────────┘
```

**Tier 1: Fast Check** — Rule-based, zero-cost, runs on every evaluation. Checks things that are unambiguous:
- Did the verification command exit with the expected code?
- Did the expected output string appear?
- Did the worker modify a forbidden file?
- Did the worker run a forbidden command?
- Is the turn count under the budget?

**Tier 2: Structured Evaluation** — Lightweight LLM (Haiku-class) for judgment calls:
- Are the test failures the same as last turn? (stuck detection)
- Is the code quality improving or degrading?
- Does the worker's report match the actual diffs?
- Are the constraints being respected?

**Tier 3: Deep Review** — Human or strong model (Sonnet/Opus) for critical checkpoints:
- Before a destructive action
- When the fast check and structured evaluation disagree
- When the goal reaches a soft budget threshold
- When the user explicitly requests a review

### 3.3 Evaluator Configuration per Goal

```yaml
evaluator:
  model: "haiku-4.5"                  # Swappable
  strictness: "strict"                # strict | normal | lenient | custom
  custom_rules:                         # Optional override
    - "Test coverage must not decrease"
    - "No new warnings in lint output"
  # For Tier 3 (deep review)
  deep_review_model: "sonnet-4.6"
  deep_review_triggers:
    - "budget_threshold: 80%"
    - "checkpoint: before_destructive_action"
    - "disagreement_between_tiers"
```

---

## 4. Multi-Agent Goal Integration

### 4.1 The Shared Goal Registry

All Laere agents share a **workspace-level goal registry** (a file or database that all agents can read):

```
/workspace/.laere/goals/
  ├── active/
  │   ├── lgc-2026-06-05-001.yaml      # Cipher's auth refactor
  │   ├── lgc-2026-06-05-002.yaml      # Grace's market research
  │   └── lgc-2026-06-05-003.yaml      # Orthia's infrastructure audit
  ├── completed/
  │   └── ...
  ├── failed/
  │   └── ...
  └── registry.json                     # Index of all goals
```

### 4.2 Agent-Specific Goal Behaviors

**Orthia (Guardian / Router):**
- Creates goals on behalf of Shawn or on her own initiative
- Routes goals to the right agent (Cipher for code, Grace for research)
- Monitors all active goals for budget violations and stuck loops
- Enforces checkpoints (summarizes progress, notifies Shawn)
- Can pause, cancel, or reassign any goal
- Reads the goal registry every heartbeat to check status

**Grace (Research Agent):**
- Receives research goals from Orthia or Shawn
- Decomposes large research goals into sub-goals (e.g., "research X" → "find 10 sources" → "summarize each" → "synthesize report")
- Reports progress via the goal registry (not just chat messages)
- Handles blocked state by requesting clarification through the registry
- Can spawn sub-agents for parallel research (e.g., one agent per source)

**Cipher (Research Agent — Current Task):**
- Receives research goals from Orthia or Shawn
- Works autonomously within the goal contract boundaries
- Updates the goal registry after each turn with:
  - What was done
  - What the evaluator said
  - What the next turn will attempt
  - Current cost/time/turn count
- Respects checkpoints and pauses for human review
- Can request sub-goals from Orthia (e.g., "I need Grace to research X before I can proceed")

### 4.3 Goal Routing Example

```
Shawn: "I need a comprehensive analysis of how Anthropic and OpenAI
        handle goal-oriented commands. Synthesize a hybrid approach
        for Laere."

Orthia: Creates LGC:
  - goal_id: lgc-2026-06-05-004
  - outcome: "6 research files written in /research/goal-command-study/"
  - verification: "all 6 files exist and are >5000 words each"
  - assigned_to: Cipher
  - budget: max_turns 100, max_time 240 minutes
  - checkpoints: every 20 turns, summarize to Shawn
  - stuck_detection: max_repeated_reason 3

Orthia: Writes LGC to registry. Notifies Cipher.

Cipher: Reads LGC. Begins research. After each turn:
  - Updates registry with progress
  - Runs evaluator (Haiku-class) on transcript
  - If evaluator says CONTINUE → next turn
  - If evaluator says STUCK → registry updates, Orthia notified
  - At turn 20 checkpoint → Orthia summarizes and notifies Shawn
  - At turn 60 → Orthia reviews progress, approves continuation

Cipher: Completes all 6 files. Evaluator verifies existence and length.
  - Registry updates to COMPLETED
  - Orthia reads registry, pushes to GitHub (lazy sync)
  - Orthia notifies Shawn: "Cipher's research is complete. Files committed."

Shawn: Reviews. Approves. Orthia marks goal as CLOSED.
```

### 4.4 Sub-Goal Dependency Management

For complex tasks, the LGC supports **sub-goals with dependencies**:

```yaml
sub_goals:
  - goal_id: "lgc-004-a"
    description: "Research Anthropic /goal"
    assigned_to: "Cipher"
    depends_on: []
  - goal_id: "lgc-004-b"
    description: "Research OpenAI goal-oriented workflows"
    assigned_to: "Cipher"
    depends_on: []
  - goal_id: "lgc-004-c"
    description: "Synthesize Laere hybrid architecture"
    assigned_to: "Cipher"
    depends_on: ["lgc-004-a", "lgc-004-b"]
  - goal_id: "lgc-004-d"
    description: "Review and edit for quality"
    assigned_to: "Grace"
    depends_on: ["lgc-004-c"]
```

Orthia's **dependency resolver** can automatically:
- Start `lgc-004-a` and `lgc-004-b` in parallel (no dependencies)
- Wait for both to complete before starting `lgc-004-c`
- Start `lgc-004-d` only after `lgc-004-c` is done
- Report blockers if any sub-goal fails

---

## 5. Progressive Autonomy Levels

### 5.1 The Five Levels

```yaml
autonomy_level: 3   # 1-5
```

| Level | Name | Behavior | Use Case |
|-------|------|----------|----------|
| **1** | **Training Wheels** | Human approves every turn before the next one begins | New goal types, high-risk operations, untrusted agents |
| **2** | **Checkpoint Gates** | Human approves at configured checkpoints (every N turns, before destructive actions) | Medium-risk tasks, new codebases, complex migrations |
| **3** | **Alert-on-Stuck** | Full autonomy, but pause and notify human on stuck detection, budget threshold, or boundary violation | Standard production work, well-understood tasks |
| **4** | **Full Unattended** | Run to completion or budget exhaustion with no human interaction | Well-understood, low-risk, repetitive tasks (Shawn's explicit opt-in) |
| **5** | **Cascade Autonomy** | Full unattended + can spawn sub-goals without human approval | Only for fully trusted agent teams with proven track records |

### 5.2 Level Promotion and Demotion

Goals should be able to **change level mid-flight**:
- If Level 3 detects a stuck loop, it can **demote to Level 2** (require human checkpoint)
- If a Level 2 goal passes 3 checkpoints without issues, it can **promote to Level 3**
- If a Level 4 goal encounters a boundary violation, it **immediately demotes to Level 1**

This is **adaptive autonomy** — the system learns the risk level of the current task and adjusts accordingly.

---

## 6. Cost and Progress Dashboard

### 6.1 Live Goal Status Format

```yaml
# Auto-generated after each turn
status_snapshot:
  goal_id: "lgc-2026-06-05-004"
  turn: 42
  timestamp: "2026-06-05T15:30:00-07:00"
  
  budget:
    turns: { used: 42, remaining: 58, pct: 42% }
    tokens: { used: 180000, remaining: 320000, pct: 36% }
    time: { used: 42, remaining: 198, pct: 21% }  # minutes
    cost: { used: 12.50, remaining: 37.50, pct: 25% }
  
  progress:
    overall_pct: 65
    current_sub_goal: "lgc-004-c"
    current_task: "Drafting 05-laere-synthesis.md"
    files_modified: ["01-comparative-overview.md", "02-anthropic-deep-dive.md", ...]
    tests_status: "N/A (research task)"
    last_action: "Wrote 05-laere-synthesis.md section 4"
  
  evaluator:
    last_verdict: "CONTINUE"
    last_reason: "2 files remaining, making steady progress"
    reason_history:           # For stuck detection
      - turn_40: "3 files remaining"
      - turn_41: "2 files remaining"
      - turn_42: "2 files remaining"
    stuck_risk: "LOW"          # Computed from reason_history
  
  alerts: []                  # Populated if thresholds crossed
  
  next_checkpoint:
    type: "every_n_turns"
    trigger_turn: 60
    action: "summarize_and_notify"
```

### 6.2 Human-Facing Summary (What Shawn Sees)

```
◎ Goal lgc-2026-06-05-004 (Cipher) — ACTIVE

Progress: 65% | Turn 42/100 | 42 min elapsed / 240 min budget
Cost: $12.50 / $50.00 (25%)

Current: Drafting 05-laere-synthesis.md (2 files remaining)
Last action: Wrote section 4 (Multi-Agent Goal Integration)
Evaluator: CONTINUE — "2 files remaining, making steady progress"
Stuck risk: LOW

Next checkpoint: Turn 60 (18 turns) → Orthia will summarize

[Pause] [Cancel] [Escalate] [Modify Budget] [Add Checkpoint]
```

---

## 7. Security Architecture

### 7.1 Defense in Depth for Goals

```
Layer 1: INPUT SANITIZATION
  - Goal contract is validated against schema before activation
  - Forbidden paths/commands are checked at parse time
  - Budget values are clamped to reasonable ranges

Layer 2: BOUNDARY ENFORCEMENT
  - Every file access is checked against allowed_paths/forbidden_paths
  - Every command execution is checked against allowed_commands/forbidden_commands
  - Violations trigger immediate pause + notification

Layer 3: EVALUATOR VERIFICATION
  - Fast check runs on every turn (rule-based, zero cost)
  - Structured evaluation checks for stuckness and quality
  - Deep review at checkpoints for critical decisions

Layer 4: HUMAN CHECKPOINTS
  - Configurable gates at every N turns, before destructive actions, before boundary violations
  - Human can pause, cancel, or modify the goal at any time

Layer 5: BUDGET KILL SWITCH
  - Hard limits on turns, tokens, time, cost
  - Automatic cancellation when any limit is reached
  - No override without human approval

Layer 6: AUDIT LOG
  - Every turn, every file change, every command, every evaluation is logged
  - Logs are immutable and append-only
  - Available for post-hoc review and incident analysis
```

### 7.2 Sandbox Per Goal

For high-risk goals (Level 1–2), the agent should run in a **sandbox**:
- Git worktree or shallow clone (isolated filesystem)
- Network restrictions (no outbound calls unless explicitly allowed)
- Read-only access to production data
- Command whitelist enforced by the OS, not just the agent

> "A text-based LLM can offend you. A Large Action Model (LAM) can bankrupt you. Security is the primary bottleneck for LAM adoption."  
> — aaia.app, "The Agent Sandbox: Securing Large Action Models" (2026-01-13)

---

## 8. Implementation Priorities

| Priority | Feature | Effort | Impact | Why First? |
|----------|---------|--------|--------|------------|
| **P0** | Goal registry (file-based) | Low | High | Foundation for everything else |
| **P0** | Basic LGC schema (YAML) | Low | High | Defines the contract |
| **P1** | Budget enforcement (turns/tokens) | Low | High | Prevents cost overruns |
| **P1** | Stuck-loop detection | Medium | High | Prevents wasted work |
| **P1** | Checkpoint notifications | Medium | High | Keeps Shawn in the loop |
| **P2** | Evaluator separation (Haiku-class) | Medium | High | Core quality mechanism |
| **P2** | Boundary enforcement | Medium | High | Security |
| **P2** | Sub-goal dependencies | Medium | Medium | Enables complex projects |
| **P3** | Progress dashboard | Medium | Medium | User experience |
| **P3** | Adaptive autonomy levels | Medium | Medium | Trust calibration |
| **P4** | Sandboxing per goal | High | Medium | Security for high-risk tasks |
| **P4** | Deep review (Tier 3 evaluator) | High | Low | Quality assurance |

---

## 9. Research Questions Answered (This File)

| Question | Answer | Confidence |
|----------|--------|------------|
| How could Laere's multi-agent system benefit from goal-oriented architecture? | **Significantly.** Shared goal registry, sub-goal dependencies, agent-specific behaviors, cross-agent visibility, and adaptive autonomy are all enabled by the LGC. | **INFERENCE** — Proposed architecture, not yet implemented |
| Could Grace's research tasks have explicit goal definitions? | **Yes.** The LGC is designed for research tasks — verification can be artifact-based ("report exists and is >5000 words") rather than test-based. | **INFERENCE** — Proposed |
| Could Orthia's routing have goal-based triggers? | **Yes.** Orthia can monitor the goal registry, detect stuck goals, enforce checkpoints, and route sub-goals to the right agents. | **INFERENCE** — Proposed |
| What is the key innovation? | **The Laere Goal Contract (LGC)** — a machine-readable, multi-agent, budget-aware, checkpoint-enabled goal format that neither Anthropic nor OpenAI has. | **INFERENCE** — Proposed |

---

## Next File

→ `06-implementation-plan.md` — Concrete steps for adopting goal-oriented workflows in Laere's agents, including OpenClaw integration, file structures, and migration path.
