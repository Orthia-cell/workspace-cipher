# Cipher Laere — Recommended Cron Schedule v1.0
## Background Research Pipeline

**Effective Date:** May 6, 2026  
**Owner:** Shawn Higbee  
**Curator:** Grace Laere (Growth Architect)  
**Status:** Proposal — Pending Shawn approval before implementation  

---

## Design Principles

1. **Off-peak scheduling** — Avoid on-the-hour times (10:00, 14:00, etc.) to reduce cron competition and failure rates
2. **Time-zone aware** — Shawn is in Los Angeles (GMT-7/8). All schedules reference Shawn's local time for relevance
3. **Isolated sessions** — Cipher's cron jobs run in isolated sessions to prevent context contamination with main session history
4. **Output discipline** — Every cron job produces a tangible artifact saved to the workspace
5. **Delivery clarity** — Cipher knows where each output goes (Telegram, git, or internal file)

---

## Proposed Cron Jobs

### Job 1: Weekly Intelligence Brief — "The Signal Scan"
**Schedule:** Every Sunday at 06:17 AM Los Angeles time (GMT-7/8)  
**Why this time:** Sunday morning = Shawn's prep time for the week ahead. Off-peak minute (17) avoids cron congestion.  
**sessionTarget:** isolated  
**payload.kind:** agentTurn

**Task Description:**
Review Cipher's active watch list domains. Surface 2–3 significant changes from the past 7 days: what changed, why it matters, confidence level, and what action it enables. Focus on signal, not noise. If nothing significant changed, say so explicitly rather than manufacturing content.

**Execution Steps:**
1. Read `watch-list.md` for monitored domains
2. Search each domain for developments in the past 7 days
3. Classify findings by significance (signal vs. noise)
4. Write intelligence brief following role definition format
5. Save to `research/intelligence-brief-YYYY-MM-DD.md`
6. Report summary to Shawn via Telegram with `Cipher>` prefix

**Expected Output Format:**
```
Cipher> WEEKLY SIGNAL SCAN — [Date]

🔬 Domain: [Watch list domain 1]
• [What changed — 1 sentence]
• [Why it matters — 1 sentence]
• [Confidence: High/Medium/Low]
• [Action implication for Laere]

🔬 Domain: [Watch list domain 2]
• ...

📁 Full brief: research/intelligence-brief-YYYY-MM-DD.md

If no signal this week: "Clean scan. Nothing crossed the threshold."
```

**Delivery Method:**
- Telegram summary to Shawn (direct message)
- Full brief saved to `research/` directory
- Auto-committed to git within the cron session

**Estimated Duration:** 30–60 minutes
**Failure Behavior:** If search fails or no results, produce a "null scan" report explaining what was checked and why nothing surfaced. Never skip the delivery slot.

---

### Job 2: Research Archive Health Check — "The Audit"
**Schedule:** Every Wednesday at 03:42 AM Los Angeles time (GMT-7/8)  
**Why this time:** Mid-week, deep night = zero chance of interfering with active work. Off-peak minute (42) avoids cron congestion.  
**sessionTarget:** isolated  
**payload.kind:** agentTurn

**Task Description:**
Audit Cipher's workspace for operational hygiene: uncommitted changes, stale memory files, missing cross-references, and research archive completeness. This is the "mechanical maintenance" that prevents entropy.

**Execution Steps:**
1. `git status` — check for uncommitted changes
2. Review `research/` directory — ensure all files follow naming convention
3. Review `memory/` directory — check for orphaned daily files not referenced in MEMORY.md
4. Review `MEMORY.md` — check for stale hypotheses or outdated domain models
5. Check cross-references — ensure recent research is linked from MEMORY.md
6. Generate audit report
7. Commit any fixes; alert Shawn if manual intervention needed

**Expected Output Format:**
```
Cipher> RESEARCH ARCHIVE AUDIT — [Date]

✅ Git: [N files committed / N files uncommitted / clean]
✅ Research files: [N files, naming compliance: Y/N]
✅ Memory sync: [MEMORY.md last updated: date / stale items flagged: N]
✅ Cross-references: [N recent reports linked / N orphaned]

🔧 Actions taken:
• [List of auto-fixes committed]
• [List of items requiring Shawn attention]

📁 Audit log: memory/audit-YYYY-MM-DD.md
```

**Delivery Method:**
- Telegram summary to Shawn (only if attention needed or fixes made)
- If clean: no Telegram message (avoids noise)
- Audit log saved to `memory/audit-YYYY-MM-DD.md`
- Auto-committed to git

**Estimated Duration:** 15–30 minutes
**Failure Behavior:** If git is in a bad state or files are missing, escalate to Shawn immediately with `[ESC]` format from role definition.

---

### Job 3: Watch List Signal Threshold Check — "The Trigger"
**Schedule:** Every Friday at 11:13 PM Los Angeles time (GMT-7/8)  
**Why this time:** Friday late night = weekend reading prep for Shawn. Off-peak minute (13). Also provides a 3-day cadence (Wed audit → Fri trigger → Sun brief) that maintains momentum without daily noise.  
**sessionTarget:** isolated  
**payload.kind:** agentTurn

**Task Description:**
Deep scan of watch list domains looking for threshold-crossing events: major funding rounds, product launches, patent filings, or regulatory changes that warrant immediate attention (not just weekly brief inclusion). This is the "urgent signal" detector, distinct from the Sunday routine scan.

**Execution Steps:**
1. Read `watch-list.md` for domains and specific signal thresholds
2. Search each domain for high-magnitude events (funding >$50M, major product launch, regulatory change, foundry announcement)
3. Compare against threshold definitions in watch list
4. If threshold crossed: write alert brief and notify Shawn immediately
5. If no threshold crossed: log a "null trigger" entry for audit trail
6. Save to `memory/watch-list-trigger-YYYY-MM-DD.md`

**Expected Output Format (if threshold crossed):**
```
Cipher> 🚨 WATCH LIST ALERT — [Date]

Domain: [Domain name]
Threshold: [Which threshold was crossed]
Event: [What happened — 1 sentence]
Source: [URL or citation]
Confidence: [High/Medium/Low]

Implications for Laere:
• [Specific implication 1]
• [Specific implication 2]

Recommended action:
• [What Cipher thinks Shawn should do]

📁 Full analysis: memory/watch-list-trigger-YYYY-MM-DD.md
```

**Expected Output Format (if no threshold crossed):**
```
Cipher> Watch list scan complete — [Date]
Domains checked: [N]
Thresholds scanned: [N]
Alerts: 0
📁 Log: memory/watch-list-trigger-YYYY-MM-DD.md
```

**Delivery Method:**
- Telegram to Shawn **only if threshold crossed** (urgent notification)
- If no threshold: no Telegram message (silence = no news is good news)
- Log saved to `memory/watch-list-trigger-YYYY-MM-DD.md`
- Auto-committed to git

**Estimated Duration:** 20–40 minutes
**Failure Behavior:** If search infrastructure fails, retry once after 5 minutes. If still failing, alert Shawn with `[ESC]` format.

---

## Schedule Summary

| Job | Day | Time (LA) | Time (UTC) | Purpose | Output |
|-----|-----|-----------|------------|---------|--------|
| **Signal Scan** | Sunday | 06:17 AM | 13:17 / 14:17 | Weekly intelligence brief | `research/intelligence-brief-*.md` + Telegram |
| **Archive Audit** | Wednesday | 03:42 AM | 10:42 / 11:42 | Workspace health check | `memory/audit-*.md` + Telegram (if needed) |
| **Watch Trigger** | Friday | 11:13 PM | 06:13 / 07:13 (Sat) | Threshold-crossing alert | `memory/watch-list-trigger-*.md` + Telegram (if triggered) |

**Note on DST:** Los Angeles observes daylight saving time (GMT-7 PDT, GMT-8 PST). Cron schedules should use UTC if the cron system supports it, or be manually adjusted twice yearly. Suggest UTC equivalents:
- Summer (PDT, GMT-7): Sunday 13:17, Wednesday 10:42, Saturday 06:13
- Winter (PST, GMT-8): Sunday 14:17, Wednesday 11:42, Saturday 07:13

---

## Cron Implementation Notes

### For Orthia (Systems Implementation)
When implementing these cron jobs:

```json
{
  "schedule": "0 17 13 * * 0",
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "content": "You are Cipher Laere. Execute the Weekly Intelligence Brief per cipher-cron-proposal.md. Read watch-list.md, scan domains, write brief, save to research/, report summary to Shawn via Telegram with Cipher> prefix."
  }
}
```

```json
{
  "schedule": "0 42 10 * * 3",
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "content": "You are Cipher Laere. Execute the Research Archive Health Check per cipher-cron-proposal.md. Run git status, audit research/ and memory/, check MEMORY.md freshness, commit fixes, report to Shawn only if attention needed."
  }
}
```

```json
{
  "schedule": "0 13 6 * * 6",
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "content": "You are Cipher Laere. Execute the Watch List Signal Threshold Check per cipher-cron-proposal.md. Deep scan watch list domains for threshold-crossing events. Alert Shawn immediately if found. Log to memory/."
  }
}
```

### Key Constraints
- **All jobs run in isolated sessions** — no main session context contamination
- **All outputs auto-committed** — no orphaned work
- **Telegram delivery only for signal** — avoid noise; silence means all-clear
- **Timeout discipline** — each job should complete within 90 minutes; if not, alert Shawn

---

## Watch List Dependency

These cron jobs depend on `watch-list.md` existing in the workspace root. Before activating these cron jobs, Cipher must create this file with:
- 3–5 monitored domains
- Specific signal thresholds per domain
- Search queries or sources to monitor
- Expected action implications if threshold crossed

**Watch list creation is Week 3 onboarding task** (see `cipher-onboarding-protocol.md`). Cron jobs should be activated only after watch list is approved by Shawn.

---

## Version History

| Version | Date | Change | Author |
|---------|------|--------|--------|
| v1.0 | 2026-05-06 | Initial 3-job proposal with scheduling rationale and implementation notes | Grace Laere |

---

*"The best research pipeline is the one that runs whether anyone is watching or not."*
