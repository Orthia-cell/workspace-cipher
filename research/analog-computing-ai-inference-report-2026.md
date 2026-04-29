# Analog Computing for AI Inference Acceleration
## Research Report — Analog KV Cache Accelerator Project
### April 29, 2026

---

## Executive Summary

The analog computing landscape for AI inference has reached a critical inflection point in 2025-2026. NVIDIA's GTC 2026 declaration that we are entering the "Age of Inference" underscores a fundamental shift: training is a one-time cost, but inference represents a continuous global computational load that will dominate energy consumption and infrastructure investment. The KV cache memory bottleneck is the most acute pain point—modern LLMs require KV cache storage that far outstrips available HBM capacity, causing severe GPU underutilization and making memory, not compute, the binding constraint.

Analog crossbar arrays for in-memory computing (IMC) represent the most promising path to break this bottleneck. Recent breakthroughs, including a Nature-published architecture using capacitor-based gain cells for attention computation (7,000× speedup, 90,000× energy reduction vs. A100), demonstrate that analog IMC is no longer a theoretical curiosity but a viable near-term solution. The field is crowded with multiple emerging memory technologies—memristors (RRAM), phase-change memory (PCM), ferroelectric FETs (FeFETs), and floating-gate arrays—each at different readiness levels. Critically, TSMC's January 2026 patent filing for back-end PCRAM integration signals foundry commitment to analog compute-in-memory. The commercial landscape includes both struggling veterans (Mythic AI pivoted to edge AI, abandoning datacenter analog inference) and well-funded newcomers (Celestial AI's $475M Series C for optoelectronic interconnects, MosAIc's $100M for photonic AI). The window for analog KV cache acceleration is opening now—the technology exists, the problem is well-defined, and the market pull from hyperscalers desperate for inference efficiency is stronger than ever.

---

## 1. Current Analog Computing Landscape for AI (2024-2026)

### 1.1 Key Research Advances

The analog/mixed-signal AI accelerator field has seen explosive activity in 2024-2026. The most significant development is the convergence on hybrid digital/analog architectures that use analog IMC for the dominant matrix-vector multiplication workloads while retaining digital precision for critical operations.

**Major Architecture Milestones:**

- **Analog Attention with Gain Cells (Nature 2025):** A breakthrough paper from KU Leuven/IMEC demonstrated an analog IMC architecture for transformer attention using capacitor-based gain-cell crossbar arrays (IGZO/ITO OSFETs). It achieves **65 ns latency and 6.1 nJ per token** for a single GPT-2 attention head, translating to **7,000× speedup and 90,000× energy reduction** compared to NVIDIA A100. KV cache footprint: as low as 3.1 × 10⁻³ mm² with 3D integration. Uses charge-to-pulse circuits (avoiding ADCs) and hardware-friendly HardSigmoid for sliding window attention.

- **Trilinear CIM (arXiv 2026):** The first architecture to perform complete transformer attention computation exclusively in non-volatile memory (FeFET) cores without runtime reprogramming. Uses FeFET back-gate modulation (not ferroelectric switching) for trilinear attention, achieving **37.5% energy reduction** over bilinear baselines with only 32.4% area overhead. 7nm CMOS + 22nm FeFET BEOL integration.

- **SCARLET (BU/PEAC Lab 2026):** A mixed-precision architecture using Optical PCM (OPCM) crossbars for static weight multiplications and a separate photonic crossbar for dynamic attention operations. Uses approximate floating-point operations for dequantization/element-wise multiplication fusion.

- **Voltmatrix (arXiv 2025):** A capacitor-based analog computing architecture that directly maps neural computations onto analog capacitive crossbar arrays without ADC/DAC converters. Claims to eliminate conversion overhead that plagues other analog approaches.

- **MosAIc (MIT 2025):** Photonic AI chip with modular 2×2 mesh arrays delivering 1.5 TOPS with 0.88 pJ/op. Funded with $100M for photonic AI acceleration.

### 1.2 Company Landscape

| Company | Technology | Status | Funding | Notes |
|---------|-----------|--------|---------|-------|
| **Mythic AI** | Analog flash-based IMC | Active but pivoted | $165M raised | Abandoned M1076 datacenter AI processor; pivoted to edge AI (M2000 small model, Vislor AR glasses). Still operates but no longer targeting LLM inference. |
| **MosAIc (MIT spinout)** | Photonic AI | Well-funded | $100M | Modular photonic mesh arrays for AI inference. Lower power than electronic equivalents. |
| **Celestial AI** | Optoelectronic interconnect | Very well-funded | $475M Series C | Photonic Fabric for chip-to-chip communication; acquired Rockley Photonics IP. Not analog compute but solves interconnect bottleneck. |
| **IBM Research** | PCM analog IMC | R&D | Internal | Active patent portfolio on analog PCM for AI (2024 AI accelerator patent co-integrating PCM+MRAM). Demonstrated Projected PCM (Proj-PCM) with 8-bit precision at NeurIPS. |
| **TSMC** | Back-end PCRAM/3D analog | Foundry R&D | Internal | Jan 2026 patent: vertical PCRAM with oxide semiconductor selector in back-end metallization. Also developing 3D XPU TSV Cube (4GB HBM + logic stack). |
| **Samsung** | FeFET/PCM analog | R&D | Internal | Investigating FeFET for next-gen embedded NVM focusing on AI inference cores. Active PCM patent portfolio. |
| **Intel** | PCM multi-step write | R&D | Internal | 2025 patent on two-stage SET algorithm for analog PCM write stability. Focus on write algorithm IP for MLC/analog applications. |
| **GLOBALFOUNDRIES + FMC** | FeFET memory IP | Commercializing | Partnership | Demonstrated FeFET IP blocks for 22nm FDSOI targeting low-power embedded AI. |
| **imec** | FeFET/multibit analog | Research | Research institute | Reported multibit FeFET operation with stable analog conductance tuning for inference acceleration. |
| **SK Hynix** | AI memory / HBM3 | Production | Internal | Developing HBM4 with 48GB capacity and 2TB/s bandwidth. Active in CXL-attached memory. |
| **Kioxia + WD** | 3D NAND for AI | Production | Internal | 218-layer BiCS8 FLASH, exploring ultra-high-density NAND for AI datasets. |

### 1.3 Academic/Research Institutions

- **KU Leuven / IMEC:** Leading analog attention research with gain-cell architectures. Nature paper on analog attention.
- **Penn State:** N. Li's group on PCM for analog IMC (EMA 2025 invited talk). Focus on device-level improvement and system-level schemes.
- **IBM Research:** Continued PCM-based analog computing, projected PCM devices. ISSCC/DAC/VLSI publications.
- **MIT:** Photonic AI (MosAIc), analog photonic accelerators.
- **University of Illinois:** Trilinear CIM architecture (arXiv 2026).
- **Boston University:** SCARLET optical PCM accelerator.
- **Seoul National University / Hanyang University:** Korean leadership in PCM 3D architectures and analog neuromorphic emulation.

---

## 2. KV Cache Optimization Techniques & Analog Fit

### 2.1 Current State-of-the-Art (Digital)

The KV cache problem has spawned a massive optimization literature. Key categories:

| Category | Technique | Description | Analog Compatibility |
|----------|-----------|-------------|---------------------|
| **Quantization** | KV cache INT8/FP8/INT4 | Reduce precision of stored KV tensors | ✅ Excellent — analog IMC naturally operates at reduced precision (2-8 bits) |
| **Pruning/Eviction** | H₂O, FastGen, Radar, NACL, QUEST, TokenSelect | Drop less important KV entries dynamically | ⚠️ Moderate — analog arrays support sparse access but benefit from dense storage |
| **Merging/Compression** | Similarity merging, semantic compression, SnapKV | Consolidate redundant KV entries | ⚠️ Moderate — merging requires read-modify-write which challenges analog non-idealities |
| **Architecture Redesign** | MQA, GQA, MLA (DeepSeek), Linear Attention, SSMs (Mamba) | Reduce KV cache size architecturally | ✅ Excellent — analog KV storage benefits from any size reduction |
| **Paging/Disaggregation** | vLLM paging, prefill-decode disaggregation, cross-engine KV transfer | Manage KV cache as pages, split across GPUs | ❌ Poor — analog arrays are typically local; CXL-attached analog memory is emerging |
| **Prefix Caching** | Cross-query KV reuse for shared prefixes | Persist and reuse KV segments | ✅ Good — analog non-volatility (PCM, FeFET, flash) enables persistent KV stores |
| **Speculative Decoding** | Draft small model, verify with large model | Reduce decode steps | Neutral — analog doesn't directly help but doesn't hurt |

### 2.2 How Analog Memory Fits

Analog IMC offers unique advantages for KV cache that digital techniques cannot match:

1. **In-place attention computation:** The KV cache is not just storage—it must participate in Q·Kᵀ and attention·V operations. Analog crossbars can compute dot products in-place (via Ohm's Law / charge sharing), eliminating the memory-bandwidth-bound movement of KV tensors to compute units. This is the critical advantage.

2. **Natural precision matching:** Analog IMC operates at 2-8 bit equivalent precision. KV cache quantization to INT4/INT8 (now standard in vLLM, TensorRT-LLM) maps naturally onto analog conductance states.

3. **Energy reduction:** Data movement dominates energy in digital systems. Analog IMC eliminates KV-to-compute movement entirely. The Nature gain-cell paper reports **90,000× energy reduction** vs. A100 for attention computation.

4. **Non-volatility for persistent KV:** PCM, FeFET, and flash-based analog arrays retain KV state without power. This enables cross-query prefix caching and warm-start inference without reload penalties.

5. **3D stacking for density:** Analog crossbars can be stacked vertically (e.g., TSMC's back-end PCRAM, 3D XPU). The Nature paper reports KV cache footprint of 3.1 × 10⁻³ mm² using 3D integration—orders of magnitude denser than SRAM-based caches.

### 2.3 Key Insight: The "All-in-Memory" vs. Hybrid Tradeoff

Current state-of-the-art analog accelerators face a fundamental tension:
- **NVM-only approaches** (PCM, RRAM, FeFET) excel at static weight storage but suffer from write endurance limitations for dynamic KV cache updates
- **Hybrid approaches** (X-Former, 2023) use NVM tiles for static projection weights but retreat to digital CMOS for attention computation, sacrificing area/efficiency
- **Gain-cell (capacitor-based) approaches** (Nature 2025) solve this by using volatile but refreshable analog storage for KV cache, enabling in-place attention without NVM endurance penalties
- **Trilinear CIM (2026)** solves it by using FeFET back-gate modulation (non-destructive, non-ferroelectric-switching) for attention computation

This suggests **capacitor-based or carefully designed FeFET approaches** are the most promising for KV cache specifically, where frequent writes are inherent.

---

## 3. Analog Memory Cell Technology Comparison

### 3.1 Technology Readiness Assessment

| Technology | Maturity | Write Endurance | Retention | Multi-level Precision | CMOS Compatibility | Best Use Case |
|-----------|----------|-----------------|-----------|----------------------|-------------------|---------------|
| **SRAM-based CIM** | Production-ready | Unlimited | Volatile | 8-12 bit | Excellent | Near-term digital CIM, edge inference |
| **Flash/Floating-Gate (Mythic-style)** | Commercial products exist | 10⁵-10⁶ | Non-volatile | 4-8 bit | Excellent | Static weights, edge AI (proven in production) |
| **FeFET** | Prototype/foundry IP | 10⁸-10¹¹ | Non-volatile | 2-4 bit per cell | Very Good (22nm FDSOI demonstrated) | Analog IMC, embedded NVM, near-term production |
| **PCM (Phase-Change Memory)** | R&D / prototype chips | 10⁸-10¹² | Non-volatile | 4-8 bit (with Proj-PCM) | Good (GST integration challenges) | Analog IMC, neuromorphic, IBM's focus |
| **RRAM/Memristor** | R&D / limited prototypes | 10⁶-10¹² | Non-volatile | 2-5 bit | Moderate (selector device challenges) | Research, niche applications |
| **Capacitor/Gain-Cell (OSFET)** | Research (Nature paper) | Effectively unlimited (refresh-based) | Volatile (or DRAM-like) | 4-8 bit | Good (IGZO/ITO integration) | KV cache specifically (frequent writes) |
| **Voltaic Shift Register** | Prior research (your work) | — | — | — | — | Candidate for analog signal processing |
| **Photonic/Optical** | Early commercial (MosAIc) | N/A | N/A | Analog optical | Poor (hybrid packaging) | Interconnect and specific MAC operations |

### 3.2 Detailed Analysis

#### Flash/Floating-Gate (Mythic AI)
- **Maturity:** Highest among NVM analog options. Mythic shipped the M1076 (76 TOPS at 3W) and has the M2000 in production for edge AI.
- **Limitation:** Write endurance (~10⁵ cycles) makes it unsuitable for KV cache that updates every token. Write latency is also slow (ms-scale for flash programming).
- **Verdict:** Proven for static weights, unsuitable for dynamic KV cache without major architectural changes.

#### FeFET (Ferroelectric FET)
- **Maturity:** GLOBALFOUNDRIES+FMC have 22nm FDSOI FeFET IP blocks. imec reports multibit analog operation. Samsung investigating scalable integration.
- **Advantages:** Fast write (<50ns), low power, non-destructive read at sub-coercive voltages, excellent CMOS compatibility. Multi-level states via partial polarization switching.
- **Endurance:** 10⁸-10¹¹ cycles (NaMLab/Leti demonstrated >10¹¹). This is sufficient for inference workloads.
- **Trilinear CIM innovation:** The 2026 TrilinearCIM paper shows FeFET back-gate modulation can perform attention without ferroelectric switching—bypassing endurance concerns entirely.
- **Verdict:** **Closest to production for analog KV cache** among NVM options. Fast write, good endurance, foundry support.

#### PCM (Phase-Change Memory)
- **Maturity:** IBM demonstrated 8-bit Proj-PCM at NeurIPS. Intel, Samsung active. TSMC filed Jan 2026 patent for back-end PCRAM.
- **Advantages:** Large resistance window (3-4 orders of magnitude), non-volatile, good retention. IBM's Proj-PCM solves conductance drift.
- **Challenges:** Write latency (~µs), high programming current/power, resistance drift over time, limited endurance for frequent writes. GST integration is thermally challenging.
- **Verdict:** Excellent for static weights and persistent storage. The write energy/latency makes it challenging for per-token KV cache updates. Better suited for model weights than KV cache.

#### RRAM/Memristor
- **Maturity:** Active research but limited commercial deployment. Selector device (1T1R, OTS) remains a challenge for large arrays.
- **Advantages:** Simple two-terminal device, nanosecond reads, small cell size.
- **Challenges:** Device variability, stuck-at-faults, limited endurance, programming complexity. Crossbar sneak paths require selectors.
- **Verdict:** Not production-ready for precision analog computing. HP's original memristor (2008) never reached commercial scale.

#### Capacitor/Gain-Cell (OSFET-based)
- **Maturity:** Research stage (Nature 2025 paper from KU Leuven/IMEC).
- **Advantages:** **Unlimited endurance** (volatile, refresh-based), fast access, in-place dot product via charge sharing, no ADC needed (charge-to-pulse circuits). IGZO/ITO OSFETs enable 3D stacking.
- **Challenges:** Volatile (requires refresh, like DRAM), capacitor leakage requires periodic refresh or calibration, OSFET device maturity.
- **Verdict:** **Theoretically ideal for KV cache** due to unlimited writes and in-place compute. The Nature paper's 7,000× speedup validates the concept. OSFET device maturity is the key risk.

### 3.3 Technology Readiness Ranking (for KV Cache Specifically)

1. **FeFET** — Best balance of write speed, endurance, and foundry readiness. Trilinear CIM shows path to attention computation without ferroelectric switching.
2. **Capacitor/Gain-Cell (OSFET)** — Best theoretical fit for KV cache (unlimited writes, in-place compute), but OSFET device maturity is unproven at scale.
3. **SRAM-based CIM** — Production-ready but lacks density advantage and non-volatility. Good near-term stepping stone.
4. **PCM** — Excellent for persistent storage and static weights, but write speed/energy limits KV cache applicability.
5. **Flash/Floating-Gate** — Proven but write endurance fundamentally unsuitable for per-token KV updates.
6. **RRAM/Memristor** — Too immature for precision analog KV cache at scale.

---

## 4. Commercial Viability Signals

### 4.1 Funding and Investment

| Company | Round | Amount | Year | Investors | Signal |
|---------|-------|--------|------|-----------|--------|
| **Celestial AI** | Series C | $475M | 2025 | Samsung, Intel, KDDI, IAG Capital | Strong hyperscaler interest in next-gen interconnect |
| **MosAIc (MIT)** | — | $100M | 2025 | — | Photonic AI gaining serious funding |
| **Mythic AI** | Total raised | $165M | 2020-2022 | — | Survived but pivoted away from LLM inference |

### 4.2 NVIDIA's Position

NVIDIA's research direction signals both threat and opportunity:
- **Rubin architecture (2026-2027):** Targets inference efficiency but is still fundamentally digital with HBM
- **NVSwitch/NVLink:** Pushing interconnect bandwidth, not solving memory capacity
- **No public analog CIM research** from NVIDIA (unlike IBM, Intel, TSMC)
- **Opportunity:** NVIDIA is focused on digital scaling. Analog KV cache could be a differentiation vector that NVIDIA is not pursuing internally.

### 4.3 Hyperscaler Interest

| Hyperscaler | Signal | Assessment |
|-------------|--------|------------|
| **Google** | CXL memory expansion, TPU inference scaling | Interested in memory expansion; no public analog CIM investment |
| **Meta** | LLaMA 4 (iRoPE, FP8), aggressive inference cost reduction | Strong need for KV cache efficiency; analog would align with cost goals |
| **Microsoft/OpenAI** | GPT-4 inference scaling, MAUI project | Massive inference load = strong pull for any efficiency gain |
| **Amazon** | Trainium/Inferentia, custom silicon | Building custom chips; potential analog CIM acquirer/partner |

### 4.4 Foundry/Fabrication Signals

- **TSMC (Jan 2026):** Vertical PCRAM with back-end oxide semiconductor selector. This is a major signal—TSMC is investing in analog CIM-compatible process integration.
- **TSMC 3D XPU (2025):** 3D TSV Cube with 4GB HBM + logic. Stacking expertise directly applicable to 3D analog crossbars.
- **GLOBALFOUNDRIES (2025):** 22nm FDSOI FeFET IP blocks with FMC. Production-ready FeFET available now.
- **Samsung:** Active PCM patent portfolio + FeFET investigation. Strong in HBM (HBM4 with 48GB).
- **Intel:** Multi-step SET algorithm for analog PCM. Focus on write algorithm IP.

### 4.5 Patent Landscape (Key Signal)

The 2026 patent landscape analysis reveals:
- **PCM patents are shifting from binary storage to analog IMC** (IBM, Intel, TSMC, Samsung)
- **FeFET is the fastest-growing analog memory patent category**
- **"Analog compute vector is the primary R&D investment signal"** — patent filings clearly show the industry pivot
- **TSMC's back-end PCRAM filing (Jan 2026)** is a watershed moment for foundry acceptance

---

## 5. Competitive Landscape Map

```
                              INFERENCE ACCELERATION LANDSCAPE 2026
                                      
    DIGITAL/Near-Term              HYBRID                    ANALOG/Emerging
    ─────────────────────          ────────────              ─────────────────
    
    ┌─────────────┐               ┌─────────────┐            ┌─────────────┐
    │ NVIDIA H100   │               │ X-Former    │            │ Gain-Cell   │
    │ /B100/Rubin   │               │ (Hybrid NVM+│            │ Attention   │
    │               │               │  CMOS)      │            │ (Nature 2025) │
    │ Quantization  │               ├─────────────┤            ├─────────────┤
    │ FlashAttention│               │ SCARLET     │            │ Trilinear   │
    │ vLLM paging   │               │ (OPCM+      │            │ CIM (2026)  │
    │               │               │  Photonic)  │            ├─────────────┤
    │ HBM3E/4       │               ├─────────────┤            │ Mythic M2000│
    │ CXL memory    │               │ SRAM-CIM    │            │ (Edge AI)   │
    └─────────────┘               │ (Samsung,   │            ├─────────────┤
                                  │  TSMC)      │            │ Voltmatrix  │
                                  └─────────────┘            │ (Capacitor) │
                                                             ├─────────────┤
                                                             │ MosAIc      │
                                                             │ (Photonic)  │
                                                             └─────────────┘
    
    Maturity: ●●●●●                ●●●○○                    ●●○○○
    KV Cache Fit: ●●●○○             ●●●●○                     ●●●●●
    
    (● = strong, ○ = weak)
```

### Key Insight

The center of gravity is shifting. Digital techniques (quantization, paging, FlashAttention) are mature but incremental. The hybrid zone (SRAM-CIM, X-Former) is the current frontier. Pure analog attention (gain-cell, Trilinear CIM) represents the next leap but requires device-level breakthroughs.

---

## 6. Recommendations for Analog KV Cache Accelerator Project

### 6.1 Immediate Actions (Next 3-6 Months)

1. **Validate the gain-cell approach with OSFET devices:** The Nature 2025 paper provides a complete architecture. Replicate or extend this work with hardware-aware training on modern models (LLaMA, Mistral, not just GPT-2). The 7,000× speedup claim is compelling but needs validation on production-relevant model sizes.

2. **Engage with foundry partners on FeFET access:** GLOBALFOUNDRIES has 22nm FDSOI FeFET IP blocks available now. imec and TSMC are advancing FeFET. A FeFET-based KV cache using Trilinear CIM's back-gate modulation approach (avoiding ferroelectric switching) could be taped out within 12-18 months.

3. **Quantify the "analog advantage" for KV cache specifically:** Build a detailed model comparing:
   - Digital baseline (HBM-based KV cache on A100/H100)
   - Analog gain-cell KV cache (Nature paper parameters)
   - FeFET KV cache (Trilinear CIM parameters)
   Include: area, energy per token, latency, accuracy degradation, refresh overhead

4. **File provisional patents on hybrid digital/analog KV cache architectures:** The space is hot. Key IP angles:
   - Capacitor-based KV storage with in-place attention
   - FeFET back-gate modulation for attention without ferroelectric switching
   - 3D-stacked analog KV cache with digital control/logic
   - Hardware-aware training algorithms for analog KV non-idealities

### 6.2 Medium-Term Strategy (6-18 Months)

5. **Build a small-scale prototype:** Target a single attention head or small model (GPT-2 scale) on an analog test chip. Partner with:
   - **imec** (gain-cell expertise, access to OSFET devices)
   - **GLOBALFOUNDRIES** (22nm FeFET MPW)
   - **TSMC** (if relationship allows; their back-end PCRAM is 2026+)

6. **Develop hardware-aware training toolchain:** The Nature paper showed that fine-tuning with scaling factors to account for capacitor leakage and gain-cell nonlinearity can preserve accuracy. This is a critical software layer—analog KV cache requires co-designed algorithms, not just hardware.

7. **Explore CXL-attached analog memory:** If analog KV cache is volatile (capacitor-based), it needs to be close to the compute. CXL 3.0 enables memory expansion. An analog CXL memory device could be a commercialization path that doesn't require GPU integration.

8. **Monitor Mythic AI closely:** They have the most analog AI chip production experience (flash-based). Even though they pivoted to edge, their engineering team and IP portfolio (200+ patents) could be an acquisition/acqui-hire target if the analog KV cache thesis proves out.

### 6.3 Long-Term Positioning (18-36 Months)

9. **Target the "GPU-free inference" narrative:** Papers like "PIM Is All You Need" (2025) argue for processing-in-memory as a way to escape GPU dependence. Analog KV cache fits this narrative perfectly—if KV cache and attention can run in analog memory, the GPU becomes less central to inference.

10. **Position for hyperscaler engagement:** Meta, Microsoft, and Amazon are all building custom silicon. An analog KV cache IP block ( licensable FeFET or gain-cell macro) could be integrated into their inference chips. The business model should be IP licensing + hardware-aware software, not necessarily full chip production.

---

## 7. Critical Papers and Reports to Read

### Must-Read Papers (5-10)

1. **"Analog in-memory Computing Attention Mechanism for Fast and Energy-efficient Large Language Models"** — *Nature* (2025). The foundational paper for analog attention. KU Leuven/IMEC. Gain-cell crossbar arrays with 7,000× speedup, 90,000× energy reduction.

2. **"Trilinear Compute-in-Memory Architecture for Energy-Efficient Transformer Acceleration"** — arXiv:2604.07628 (Apr 2026). First complete attention in NVM cores without runtime reprogramming. FeFET back-gate modulation. 37.5% energy reduction.

3. **"X-Former: In-Memory Acceleration of Transformers"** — (Sridharan et al., 2023). The hybrid baseline that analog approaches must beat. Shows why NVM-only is insufficient and hybrid is necessary.

4. **"Accurate deep neural network inference using computational phase-change memory"** — *Nature Communications* (2020). Joshi et al., IBM Research. Proj-PCM with 8-bit precision. The IBM analog PCM foundation.

5. **"BEOL Ferroelectric Compute-in-Memory Ising Machine"** — arXiv:2512.17165 (Dec 2025). 32×256 FeFET CiM chip fabricated in 180nm CMOS. Demonstrates real FeFET analog compute hardware.

6. **"Energy Efficient Dual Designs of FeFET-Based Analog In-Memory Computing with Inherent Shift-Add Capability"** — DAC 2024. FeFET IMC with 1.56× energy efficiency improvement over state-of-the-art.

7. **"Voltmatrix: A Capacitor-Based Analog Computing Architecture"** — arXiv:2504.06704 (Apr 2025). ADC-free capacitor crossbar approach.

8. **"PIM Is All You Need: Processing-in-Memory with CXL for GPU-Free LLM Inference"** — HotChips 2025 (Aug 2025). CXL-attached PIM for LLM inference. Commercialization perspective on PIM for inference.

9. **"Hardware Acceleration for Neural Networks: A Comprehensive Survey"** — arXiv:2512.23914 (Dec 2025). Broad survey covering analog memory/communication challenges, attention workloads, and end-to-end speedup dependencies.

10. **"The Role of Phase-Change Memory in Edge Computing and Analog In-Memory Computing"** — *Sensors* (2025). Comprehensive overview of PCM for AIMC, including recent chip demonstrations.

### Additional Important References

- **"Disc-type Phase-change Memory Devices for Analog In-memory Computing"** — IBM Research, IEDM 2025. New PCM device architecture for AIMC with ~40 µA/µW programming.
- **"Multi-level FeFET-based cells for signed analog computation and content-addressable search"** — Xu et al., Apr 2025. UniCAIM architecture with KV cache management.
- **TSMC Patent CN [Jan 2026]:** Vertical PCRAM with oxide semiconductor selector. Critical foundry signal.
- **IBM Patent (2024):** Co-integrated PCM+MRAM at same metal level for analog matrix-vector multiply.
- **"SCARLET: A Scalable OPCM-Based Accelerator"** — BU/PEAC Lab 2026. Mixed-precision optical PCM + photonic crossbar for full decoder layers.
- **Mythic AI M1076 / M2000 whitepapers** — Only production analog AI chips to date. Learn from their limitations.

---

## 8. Key Risks and Open Questions

| Risk | Severity | Mitigation |
|------|----------|------------|
| **OSFET device maturity** | High | FeFET backup path (GLOBALFOUNDRIES 22nm available now) |
| **Analog accuracy degradation** | Medium | Hardware-aware training, calibration, periodic refresh |
| **Endurance for NVM KV cache** | High | Use gain-cell (volatile) or FeFET back-gate modulation (non-destructive) |
| **Integration with existing software stack** | Medium | Build vLLM/TensorRT-LLM compatible analog backend |
| **Foundry willingness to support** | Medium | TSMC's Jan 2026 filing is encouraging; GF has FeFET now |
| **Digital CMOS catch-up** | Medium | Digital techniques (quantization, paging) are improving rapidly. Analog must deliver 10×+ advantage to justify disruption. |
| **Patent landscape** | Low-Medium | IBM, TSMC, Samsung actively patenting. File early, focus on KV-specific architectures. |

---

## Appendix: Search Sources and Methods

This report synthesizes findings from:
- 20+ targeted web searches across analog computing, KV cache optimization, and specific technologies
- arXiv preprints (2024-2026)
- Nature and Nature Communications papers
- IEEE conference proceedings (DAC, ISSCC, IEDM, VLSI)
- Patent landscape analyses (PatSnap 2026)
- Company press releases and funding announcements
- Industry reports from NextBigFuture, EE Times, IEEE Spectrum

*Report compiled by subagent for Analog KV Cache Accelerator project.*
