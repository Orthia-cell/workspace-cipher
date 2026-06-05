# Implementation Plan: Adopting Goal-Oriented Workflows in Laere

> Research File: `06-implementation-plan.md`  
> Research Agent: Cipher Laere (Laere Enterprises)  
> Date: 2026-06-05  
> Status: Complete  
> Sources: All prior files in this series, OpenClaw documentation, Laere workspace structure (AGENTS.md, SOUL.md, USER.md), and the Laere multi-agent context protocol

---

## Executive Summary

This document provides a concrete, phased implementation plan for bringing goal-oriented workflows into Laere Enterprises' multi-agent system. The plan is designed for OpenClaw's existing architecture (agents, skills, memory, cron/heartbeat) and respects Shawn's working style (parallel work, agent autonomy, proactive action). It is organized into five phases, from a minimal viable goal system to a fully orchestrated multi-agent goal platform.

---

## 1. Current State: Laere's Architecture

### 1.1 Existing Infrastructure

Laere already has the building blocks for goal-oriented work:

| Component | What It Does | How It Maps to Goals |
|-----------|-------------|----------------------|
| **Agents** | Orthia (main), Grace (research), Cipher (research) | Workers that would receive and execute goals |
| **AGENTS.md** | Defines agent roles, bootstrap, memory | Would be extended with goal-specific agent behaviors |
| **SOUL.md** | Orthia's identity, personality, interaction style | Would include goal-state awareness (e.g., "I am monitoring 3 active goals") |
| **USER.md** | Shawn's profile, preferences, availability | Would include default autonomy level and budget preferences |
| **Memory** | `MEMORY.md` (long-term), `memory/YYYY-MM-DD.md` (daily), `memory/facts/` | Would include goal history, outcomes, lessons learned |
| **Skills** | `feishu-*`, `github`, `weather`, etc. | Would be referenced in goal boundaries ("allowed skills") |
| **Cron/Heartbeat** | Periodic checks, proactive actions | Would be extended to check goal registry for stuck goals |
| **TaskFlow** | Durable flows for multi-step work | Natural fit for goal orchestration and sub-goal dependencies |
| **Subagents** | Spawn agents for specific tasks | Natural fit for sub-goals and parallel work |

### 1.2 What's Missing

- **No goal registry** — goals are implicit in conversation, not explicit in files
- **No goal contract** — no structured format for defining outcomes, constraints, budgets
- **No evaluator** — agents judge their own completion (completion bias)
- **No budget management** — no turn caps, token limits, or cost tracking per task
- **No stuck detection** — no way to detect when an agent is looping
- **No checkpoints** — no automatic human review gates
- **No cross-agent visibility** — Grace doesn't know what Cipher is working on

---

## 2. Phase 0: Foundation (Week 1–2)

### 2.1 Create the Goal Registry

**File:** `/.laere/goals/registry.json`  
**Owner:** Orthia (creates and maintains)

```json
{
  "registry_version": "1.0",
  "last_updated": "2026-06-05T13:00:00-07:00",
  "active_goals": [],
  "completed_goals": [],
  "failed_goals": [],
  "agent_assignments": {
    "Orthia": [],
    "Grace": [],
    "Cipher": []
  }
}
```

**Action items:**
1. Orthia creates `/.laere/goals/` directory structure
2. Orthia creates the registry file with schema validation
3. Orthia adds a heartbeat check (every 30 minutes) to read the registry and report stuck goals
4. All agents update their `AGENTS.md` to reference the goal registry location

### 2.2 Define the Minimal LGC Schema

**File:** `/.laere/schemas/lgc-v1.0.yaml`  
**Owner:** Orthia (creates), Cipher (reviews)

Start with the minimal viable schema (the full schema from `05-laere-synthesis.md` can be adopted incrementally):

```yaml
lgc_version: "1.0"
goal_id: "auto-generated"
created_by: "agent_or_user"
assigned_to: "agent_name"
status: "active"   # active | paused | completed | failed | cancelled

outcome:
  description: "string"
  verification:
    type: "command_output | file_state | artifact_exists | human_review"
    # type-specific fields

constraints:
  - "string"

budget:
  max_turns: 0      # 0 = unlimited
  max_time_minutes: 0

failure_mode:
  on_stuck:
    action: "pause_and_notify | cancel"
    notify: ["Orthia", "Shawn"]

checkpoints:
  - type: "every_n_turns"
    n: 10
    action: "summarize_and_notify"
    notify: ["Shawn"]
```

### 2.3 Add Goal Awareness to Each Agent

**Orthia:**
- Add to `SOUL.md`: "I monitor the goal registry. I know what each agent is working on. I can create, pause, cancel, and reassign goals."
- Add to `AGENTS.md`: "Goal management is part of my core responsibilities."

**Grace:**
- Add to her agent definition: "I read the goal registry before starting work. I update the registry after each significant step. I report progress via the registry, not just chat."

**Cipher:**
- Same as Grace (this is already the working pattern for this research task).

---

## 3. Phase 1: Basic Goal Contracts (Week 3–4)

### 3.1 Goal Creation Workflow

When Shawn or an agent wants to start a goal-oriented task:

```
1. Orthia (or Shawn) writes a goal contract in /.laere/goals/active/
2. Orthia validates the contract against the schema
3. Orthia assigns the goal to the right agent
4. Orthia updates the registry
5. The assigned agent reads the goal and begins work
6. After each turn, the agent updates the goal status file
7. The evaluator (initially: Orthia or a simple rule check) reviews progress
```

### 3.2 The Goal Status File

Each active goal has a companion status file that the worker updates after every turn:

**File:** `/.laere/goals/active/lgc-XXX.status.yaml`

```yaml
goal_id: "lgc-2026-06-05-001"
last_updated: "2026-06-05T13:15:00-07:00"
turn: 3

progress:
  current_action: "Searching for Anthropic /goal documentation"
  files_created: []
  files_modified: []
  
last_evaluator_result:
  verdict: "CONTINUE"
  reason: "Research is progressing, 2 sources found so far"
  
budget_usage:
  turns: 3
  time_minutes: 15
  
next_action: "Search for OpenAI Codex Goals documentation"
```

### 3.3 Orthia as the Initial Evaluator

In Phase 1, Orthia acts as the **Tier 2 evaluator** (structured judgment):
- Orthia reads the goal status file during each heartbeat
- She compares the current state to the goal contract
- She makes a CONTINUE/PAUSE/CANCEL recommendation
- She notifies Shawn if the goal is stuck or approaching budget

This is **not** the long-term evaluator (we want an independent, lightweight model), but it is **sufficient for Phase 1** because:
- Orthia is already the guardian/router
- She has access to all agent context
- She can make judgment calls about progress
- She can escalate to Shawn when needed

The long-term plan is to replace Orthia's evaluator role with a **dedicated lightweight model** (Phase 3), but Orthia remains the **orchestrator** who reads the evaluator's output and takes action.

### 3.4 First Real Goal: Template Task

Pick a low-risk, well-defined task as the first goal-oriented test:

```yaml
# /.laere/goals/active/lgc-first-test.yaml
lgc_version: "1.0"
goal_id: "lgc-2026-06-05-first-test"
created_by: "Shawn"
assigned_to: "Orthia"
outcome:
  description: "Create a summary of all skills in the workspace"
  verification:
    type: "artifact_exists"
    path: "/workspace/skills-summary.md"
    min_size_bytes: 1000
budget:
  max_turns: 10
  max_time_minutes: 30
failure_mode:
  on_stuck:
    action: "cancel"
    notify: ["Shawn"]
checkpoints:
  - type: "every_n_turns"
    n: 5
    action: "summarize_and_notify"
    notify: ["Shawn"]
```

This is a **safe test** because:
- It is read-only (no file modifications outside the workspace)
- It has a clear, verifiable outcome
- It has a tight budget
- It can be completed in 10 turns or less

---

## 4. Phase 2: Budget and Stuck Detection (Week 5–6)

### 4.1 Turn and Token Budget Enforcement

**Implementation:**
- The agent reads `budget.max_turns` from the goal contract before each turn
- If `turn >= max_turns`, the agent stops, marks the goal as FAILED (budget_exceeded), and notifies Orthia
- Orthia updates the registry and notifies Shawn
- Token budget is harder (requires API introspection), but turn count is trivial to implement

**Simplest implementation:**
```python
# Pseudocode for agent turn budget check
before_turn(goal):
    if goal.status != "active":
        return  # Don't start
    if goal.budget.max_turns > 0 and goal.current_turn >= goal.budget.max_turns:
        goal.status = "failed"
        goal.failure_reason = "budget_exceeded: max_turns"
        notify(Orthia, f"Goal {goal.id} failed: exceeded {goal.budget.max_turns} turns")
        return
    goal.current_turn += 1
    # Proceed with turn
```

### 4.2 Stuck-Loop Detection (Simple Version)

**Implementation:**
- Compare the last 3 evaluator reasons
- If they are identical (or semantically similar), flag as STUCK
- Orthia reviews and either:
  - Cancels the goal
  - Modifies the goal contract (e.g., broader constraints, different approach)
  - Reassigns to a different agent
  - Asks Shawn for input

**Simplest implementation:**
```python
# Pseudocode for stuck detection
def detect_stuck(goal):
    reasons = goal.evaluator.reason_history[-3:]
    if len(reasons) < 3:
        return False
    # Simple check: identical reasons
    if reasons[0] == reasons[1] == reasons[2]:
        return True
    # Slightly smarter: same key phrase (e.g., "3 tests still failing")
    # This can be done with simple string matching or a lightweight model
    return False

if detect_stuck(goal):
    goal.status = "paused"
    notify(Orthia, f"Goal {goal.id} appears stuck: same reason for 3 turns")
```

### 4.3 Cost Tracking (Manual Phase)

In Phase 2, cost tracking is **manual** — the agent estimates tokens used per turn and writes it to the status file. This is not precise, but it is **good enough** to catch runaway goals:

```yaml
budget_usage:
  turns: 15
  time_minutes: 45
  estimated_tokens: 180000
  estimated_cost_usd: 9.00
```

In Phase 4, this will be replaced with automatic API-level cost tracking.

---

## 5. Phase 3: Independent Evaluator (Week 7–8)

### 5.1 Why an Independent Evaluator Matters

Orthia evaluating her own agents' work has a **conflict of interest**:
- She may be too lenient (wants to see her agents succeed)
- She may be too strict (overly cautious)
- She cannot evaluate her own work (if she is the worker)
- She consumes context window tokens that could be used for the worker's reasoning

### 5.2 Implementing a Lightweight Evaluator

**Option A: Use a cheap model via API call**
- Call a lightweight model (e.g., Kimi's k2p6 or an equivalent fast/cheap model) via the existing API
- Send the goal contract + last N turns of context
- Receive a CONTINUE/PAUSE/CANCEL verdict + reason
- Cost: ~$0.01–$0.05 per evaluation (negligible compared to worker cost)

**Option B: Use a rule-based evaluator for simple checks**
- For goals with command-based verification (e.g., "npm test exits 0"), just run the command and check the exit code
- No LLM needed — zero cost, instant result
- Use LLM evaluator only for judgment-based goals (e.g., "research is comprehensive")

**Recommended approach:**
```
Tier 1 (Rule-based): Run for all goals, zero cost
  - Check budget limits
  - Check file existence
  - Check command exit codes
  - Check boundary violations

Tier 2 (Lightweight LLM): Run for goals that pass Tier 1
  - Evaluate progress quality
  - Detect stuckness
  - Check constraint compliance
  - Generate reason for next turn

Tier 3 (Orthia or strong model): Run only for escalations
  - When Tier 1 and Tier 2 disagree
  - When a checkpoint is reached
  - When the goal is blocked
```

### 5.3 Evaluator Integration

The evaluator runs **after each worker turn**:

```
1. Worker completes turn
2. Worker updates status file
3. System triggers evaluator
4. Evaluator reads goal contract + status file + recent context
5. Evaluator returns verdict + reason
6. System writes evaluator result to status file
7. If verdict == CONTINUE → worker starts next turn
8. If verdict == PAUSE → notify Orthia/Shawn, wait for input
9. If verdict == CANCEL → mark goal FAILED, notify Orthia/Shawn
```

---

## 6. Phase 4: Multi-Agent Goal Orchestration (Week 9–10)

### 6.1 Sub-Goals and Dependencies

Enable complex tasks that require multiple agents:

```yaml
# Example: A research project that needs Grace + Cipher
lgc_version: "1.0"
goal_id: "lgc-2026-06-20-research-project"
assigned_to: "Orthia"  # Orthia orchestrates, doesn't execute

sub_goals:
  - goal_id: "lgc-research-a"
    description: "Find 10 primary sources"
    assigned_to: "Grace"
    depends_on: []
    budget: { max_turns: 20 }
  
  - goal_id: "lgc-research-b"
    description: "Analyze and synthesize findings"
    assigned_to: "Cipher"
    depends_on: ["lgc-research-a"]
    budget: { max_turns: 30 }
  
  - goal_id: "lgc-research-c"
    description: "Review and edit final report"
    assigned_to: "Grace"
    depends_on: ["lgc-research-b"]
    budget: { max_turns: 10 }
```

**Orthia's orchestration logic:**
```python
# Pseudocode for dependency resolution
for sub_goal in goal.sub_goals:
    if sub_goal.depends_on:
        deps_met = all(g.status == "completed" for g in sub_goal.depends_on)
        if not deps_met:
            continue  # Wait for dependencies
    if sub_goal.status == "pending":
        sub_goal.status = "active"
        notify(sub_goal.assigned_to, f"Your sub-goal {sub_goal.id} is ready")
```

### 6.2 Cross-Agent Goal Visibility

Every agent can read the full goal registry. This enables:
- **Grace** to see that Cipher is working on a related goal and avoid duplicate research
- **Cipher** to see that Grace's sub-goal is stuck and offer help
- **Orthia** to detect when two agents are working on conflicting goals and intervene
- **Shawn** to see the full project status at a glance

### 6.3 Goal Handoffs

When a sub-goal completes, its output is automatically made available to the next agent:

```yaml
# In sub-goal lgc-research-a
output:
  artifacts:
    - path: "/workspace/research/sources.md"
    - path: "/workspace/research/summary.md"
  
# In sub-goal lgc-research-b (depends on lgc-research-a)
input:
  inherited_artifacts:
    - from: "lgc-research-a"
      paths: ["/workspace/research/sources.md", "/workspace/research/summary.md"]
```

---

## 7. Phase 5: Advanced Features (Week 11+)

### 7.1 Adaptive Autonomy Levels

Implement the five autonomy levels from `05-laere-synthesis.md`:

```yaml
autonomy_level: 3   # Default for Shawn
```

**Level 1 (Training Wheels):**
- Orthia approves every turn before the worker starts
- Implemented by: worker completes turn, writes status, PAUSEs, waits for Orthia's CONTINUE

**Level 2 (Checkpoint Gates):**
- Orthia approves at configured checkpoints
- Implemented by: worker runs N turns, then PAUSEs at checkpoint

**Level 3 (Alert-on-Stuck):**
- Full autonomy, but PAUSE on stuck detection or budget threshold
- This is the default for most tasks

**Level 4 (Full Unattended):**
- Worker runs to completion or budget exhaustion
- Requires Shawn's explicit opt-in per goal
- Use only for well-understood, low-risk tasks

**Level 5 (Cascade Autonomy):**
- Worker can spawn sub-goals without approval
- Use only for fully trusted agent teams

### 7.2 Progress Dashboard

Create a human-readable summary that Orthia generates during each heartbeat:

```
## Laere Active Goals (2026-06-20 09:00 PDT)

| Goal | Agent | Progress | Budget | Status | Next Action |
|------|-------|----------|--------|--------|-------------|
| lgc-001 | Cipher | 65% | 42/100 turns | ACTIVE | Drafting synthesis |
| lgc-002 | Grace | 30% | 6/20 turns | ACTIVE | Finding sources |
| lgc-003 | Orthia | 100% | 8/10 turns | COMPLETED | — |

**Alerts:**
- lgc-002: Stuck risk LOW (steady progress)
- lgc-001: Next checkpoint at turn 50 (8 turns remaining)

[View Details] [Pause] [Cancel] [Modify]
```

This can be generated as a Markdown file in `/.laere/goals/dashboard.md` that Shawn can read anytime.

### 7.3 Goal History and Learning

Completed goals are archived in `/.laere/goals/completed/` and summarized in `MEMORY.md`:

```
## Goal History (Laere)

- 2026-06-05: Cipher completed "Anthropic vs OpenAI goal research"
  - Outcome: 6 files written, pushed to GitHub
  - Budget: 42/100 turns, $12.50/$50.00
  - Lessons: Turn budget was sufficient. Stuck detection not triggered.
  
- 2026-06-10: Grace failed "Market analysis for X"
  - Outcome: Sources were paywalled, goal blocked
  - Budget: 15/20 turns, $8.00/$30.00
  - Lessons: Should have checked source availability before starting.
           Add "source availability check" as a pre-goal step.
```

This learning loop is critical — it prevents repeated failures and improves goal estimation over time.

### 7.4 Integration with OpenClaw TaskFlow

OpenClaw's TaskFlow system is the natural substrate for goal orchestration:
- A **TaskFlow** can represent a top-level goal
- **Child tasks** can represent sub-goals
- **TaskFlow state** (pending, running, completed, failed) maps to goal status
- **TaskFlow revision** enables checkpointing and rollback
- **TaskFlow delivery** enables notifications to Shawn when goals complete

This integration should be explored once the basic goal registry is stable.

---

## 8. Migration Path: From Today to Goal-Oriented

### 8.1 Immediate Actions (This Week)

1. **Create the directory:** `mkdir -p /workspace/.laere/goals/{active,completed,failed}`
2. **Create the registry:** `/.laere/goals/registry.json`
3. **Create the schema:** `/.laere/schemas/lgc-v1.0.yaml`
4. **Update AGENTS.md:** Add goal management responsibilities to each agent
5. **Update SOUL.md:** Add goal-state awareness to Orthia's identity
6. **Update USER.md:** Add Shawn's default autonomy level and budget preferences

### 8.2 First Goal-Oriented Task (This Week)

Use the **current research task** (this `/goal` study) as the first real goal:

```yaml
lgc_version: "1.0"
goal_id: "lgc-2026-06-05-goal-study"
created_by: "Shawn"
assigned_to: "Cipher"
outcome:
  description: "6 research files written and pushed to GitHub"
  verification:
    type: "artifact_exists"
    paths:
      - "/workspace-cipher/research/goal-command-study/01-comparative-overview.md"
      - "/workspace-cipher/research/goal-command-study/02-anthropic-deep-dive.md"
      - "/workspace-cipher/research/goal-command-study/03-openai-deep-dive.md"
      - "/workspace-cipher/research/goal-command-study/04-strengths-weaknesses.md"
      - "/workspace-cipher/research/goal-command-study/05-laere-synthesis.md"
      - "/workspace-cipher/research/goal-command-study/06-implementation-plan.md"
    min_size_each: 5000
budget:
  max_turns: 100
  max_time_minutes: 240
checkpoints:
  - type: "every_n_turns"
    n: 25
    action: "summarize_and_notify"
    notify: ["Shawn"]
```

**Note:** This goal was already completed before the goal system existed. But we can retroactively create the contract, mark it as completed, and use it as the **template** for future goals.

### 8.3 Next Real Goal (Next Week)

Pick a task from Shawn's backlog that is:
- Well-defined (clear outcome)
- Low-risk (no production system changes)
- Bounded (can be completed in <50 turns)

Examples:
- "Update all README files to reflect new agent names"
- "Audit all cron jobs and document their purpose"
- "Create a skill for [specific Laere workflow]"

These are **training wheels** goals — they teach the system how to work without high stakes.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Goal contracts are too complex** | Medium | Adoption friction | Start with minimal schema, expand incrementally |
| **Evaluators are too slow or expensive** | Low | Cost overrun | Tier 1 rule-based evaluator catches most cases |
| **Stuck detection produces false positives** | Medium | User frustration | Make stuck detection configurable, allow override |
| **Agents don't update status files reliably** | Medium | Registry is stale | Heartbeat check detects stale status, Orthia follows up |
| **Shawn finds checkpoints annoying** | Medium | Autonomy level stays at 4 | Make checkpoints configurable per goal, default to Level 3 |
| **Multi-agent goals create coordination bugs** | Medium | Deadlocks, lost work | Start with single-agent goals, add sub-goals gradually |
| **Cost tracking is inaccurate** | High | Budget enforcement fails | Use turn count as primary budget (accurate), tokens as estimate |

---

## 10. Success Metrics

After 30 days of using the goal system:

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Goals completed within budget** | >80% | Compare actual vs. budget in registry |
| **Goals stuck and detected** | >90% | Stuck detection accuracy (manual review) |
| **Goals cancelled by Shawn** | <20% | Cancellation rate (indicates false starts) |
| **Average goal completion time** | <2 hours | For standard tasks (research, documentation) |
| **Cross-agent goal handoffs** | >5 | Number of sub-goals successfully passed between agents |
| **Shawn satisfaction** | "Useful" | Qualitative — Shawn says it helps, not hinders |

---

## 11. Research Questions Answered (This File)

| Question | Answer | Confidence |
|----------|--------|------------|
| How to adopt goal-oriented workflows in Laere? | **5-phase plan:** Foundation → Basic Contracts → Budget/Stuck Detection → Independent Evaluator → Multi-Agent Orchestration → Advanced Features | **INFERENCE** — Proposed implementation plan |
| What is the first concrete step? | **Create the goal registry and schema this week.** Use the current research task as the first retrospective goal. | **INFERENCE** — Proposed |
| How long until full multi-agent orchestration? | **10 weeks** (phased), with basic functionality in 2 weeks | **INFERENCE** — Estimate based on complexity |
| What is the biggest risk? | **Agents not updating status files reliably** — mitigated by heartbeat checks and Orthia follow-up | **INFERENCE** — Risk assessment |

---

## Appendix: File Structure

```
/workspace/.laere/
├── goals/
│   ├── active/
│   │   ├── lgc-2026-06-05-001.yaml
│   │   ├── lgc-2026-06-05-001.status.yaml
│   │   └── ...
│   ├── completed/
│   │   └── lgc-2026-06-05-001.yaml (moved here when done)
│   ├── failed/
│   │   └── ...
│   └── registry.json
├── schemas/
│   └── lgc-v1.0.yaml
├── dashboard.md
└── history/
    └── 2026-06.md (monthly goal summaries)
```

---

## End of Research Series

This completes the 6-file research series on goal-oriented command architectures. All files are in `/workspace-cipher/research/goal-command-study/`:

1. `01-comparative-overview.md` — Side-by-side comparison of Anthropic and OpenAI
2. `02-anthropic-deep-dive.md` — Claude Code `/goal` architecture, evaluator, feedback loop
3. `03-openai-deep-dive.md` — Codex Goals, Deep Research, Tasks goal-oriented behavior
4. `04-strengths-weaknesses.md` — SWOT analysis, gaps, marketing fluff called out
5. `05-laere-synthesis.md` — Proposed Laere Goal Contract (LGC) and hybrid architecture
6. `06-implementation-plan.md` — Concrete adoption plan for Laere's multi-agent system

Next step: Commit to GitHub and push to `workspace-cipher` repo.
