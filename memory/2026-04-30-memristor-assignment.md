# Cipher Research Assignment | April 30, 2026

**Assigned by:** Shawn Higbee (via Orthia routing)
**Agent:** Cipher Laere
**Task ID:** memristor-chips-deep-dive-2026-04-30
**Status:** ASSIGNED → IN PROGRESS
**Methodology:** Recursive Self-Improvement Protocol (3-step cycle)

---

## Research Brief

**Primary Objective:** Comprehensive deep dive into memristor chips — everything there is to know. Shawn has passion for pursuing hardware/chips over pure software/IP. This research must cover the full landscape from physics to product.

**Research Objectives:**
1. **Physics & Fundamentals** — What is a memristor, how does it work, Leon Chua's original theory vs. modern implementations (HP Labs TiO2, HfO2 ReRAM, etc.)
2. **Device Types & Mechanisms** — Metal-oxide ReRAM (HfO2, TaOx, TiO2), PCM, FeFET, MRAM/STT-MRAM, ECRAM, organic memristors. Filament formation, phase change, ferroelectric switching, electrochemical.
3. **Manufacturing & Foundry Status** — Who can actually make these? TSMC, Samsung, Intel, GlobalFoundries, SK hynix, Crossbar, Weebit, Knowm. Process nodes, yield, cost per wafer.
4. **Commercial Products & Companies** — Every company shipping or developing memristor chips. Crossbar, Weebit, Knowm, 4DS Memory, Intrinsic, Aspinity, Innatera, Mythic (analog pivot), Syntiant, BrainChip, others.
5. **Applications** — Neuromorphic computing, AI inference, analog CIM, in-memory computing, storage-class memory, security/PUF, edge AI.
6. **Technical Deep-Dive** — Performance metrics: endurance, retention, speed, power, density, variability (C2C, D2D), temperature sensitivity. Array-level challenges: sneak paths, IR drop, selector devices, 3D stacking.
7. **Timeline to Production** — TRL assessment for each technology. What ships today, what ships in 2 years, 5 years, 10 years.
8. **Investment & Market Landscape** — Funding rounds, acquisitions, partnerships. Market size forecasts. Who's betting on what.

**Deliverable Format (per Cipher SOUL.md standard):**
1. Executive Summary — 3-5 bullets, decision-oriented
2. Key Findings — numbered, with confidence levels
3. Technical Deep-Dive — evidence organized by logic
4. Risk Matrix — what could invalidate this analysis
5. Specific Recommendations — actionable next steps for Laere Enterprise (hardware-focused, not just software)
6. Must-Read Sources — full citations, with quality notes

**Output Filename:** `research/memristor-chips-complete-deep-dive-2026-04-30.md`

**Spawn Configuration:**
- runtime: subagent
- model: kimi-coding/k2p5
- thinking: high
- timeoutSeconds: 600
- label: cipher-memristor-chips
- cwd: /root/.openclaw/workspace-cipher

**Context from Previous Reports:**
- Previous: `research/analog-kv-cache-accelerator-deep-dive-2026-04-30.md`
- Previous: `research/bayesian-optimization-analog-devices-feasibility-2026-04-30.md`
- Key context: ADC/DAC bottleneck kills analog CIM for LLMs; Mythic pivoted to digital; ReRAM has manufacturing precedent but limited analog precision.

**Shawn's Direction:** Passion for pursuing chips. This research should identify the most viable memristor chip path for Laere — whether that's analog CIM, neuromorphic, storage-class memory, or something else entirely.

---

*Assigned: April 30, 2026 12:58 UTC*
