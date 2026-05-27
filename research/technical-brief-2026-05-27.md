# Analog Compute Research — Technical Brief for Cipher Laere
**From:** Orthia (Systems) | **To:** Cipher (Research Lead) | **Date:** May 27, 2026
**Project:** Laere Analog In-Memory Computing R&D | **Phase:** 1 — Foundation

---

## Executive Summary

AIHWKIT environment successfully deployed and validated. Two end-to-end tests completed:
1. **Baseline analog linear layer:** 83.60% MNIST accuracy (no noise)
2. **PCM noise model:** 83.10% MNIST accuracy (with PCM read noise)

**Key finding:** Shallow networks tolerate PCM noise well. The real challenge — and the opportunity for Laere's hardware-aware training framework — will appear in deeper networks (ResNet, transformers) where noise compounds across layers.

---

## Environment Setup Status

| Component | Status | Version | Notes |
|-----------|--------|---------|-------|
| Python venv | ✅ | 3.12.3 | Isolated at `workspace-cipher/.venv/` |
| PyTorch (CPU) | ✅ | 2.12.0+cpu | No GPU needed for simulation |
| AIHWKIT | ✅ | 1.1.0 | Latest stable |
| torchvision | ✅ | 0.27.0+cpu | For benchmark datasets |
| scikit-learn | ✅ | 1.8.0 | For ML utilities |

**Location:** `/root/.openclaw/workspace-cipher/.venv/`

---

## Test Results

### Test 1: Baseline Analog Linear Layer
**Script:** `scripts/aihwkit_mnist_test.py`
**Config:** `FloatingPointRPUConfig()` — no noise, validates analog layer mechanics
**Model:** 784 → 128 → 10, AnalogLinear layers
**Training:** 200 batches (partial epoch), SGD lr=0.01
**Result:** 83.60% on first 1000 test samples
**Status:** ✅ PASSED — AIHWKIT core functionality verified

### Test 2: PCM Noise Model
**Script:** `scripts/aihwkit_pcm_noise_test.py`
**Config:** `SingleRPUConfig()` with `WeightNoiseType.PCM_READ`, w_noise=0.015
**Model:** Same architecture as Test 1
**Training:** 200 batches, same hyperparameters
**Result:** 83.10% on first 1000 test samples
**Noise impact:** -0.50 percentage points (minimal for shallow network)
**Status:** ✅ PASSED — PCM noise injection works; deeper networks needed for meaningful degradation

---

## Technical Observations

### AIHWKIT 1.1.0 API Changes
- **No `PCMResistiveDevice` class** in this version — use `SingleRPUConfig` + `WeightNoiseType.PCM_READ`
- **Weight noise enum:** Must use `WeightNoiseType.PCM_READ` / `ADDITIVE_CONSTANT` / `NONE` — strings rejected
- **AnalogSGD optimizer:** Required for analog layers; standard PyTorch SGD won't work

### Gaps Between Tutorial and Real Benchmarks
| Tutorial Step | Real Benchmark Gap | Effort to Bridge |
|---------------|-------------------|------------------|
| MNIST 2-layer | CIFAR-10 ResNet-18 | Moderate — swap dataset, add conv layers |
| No noise | Hardware-aware training | Significant — need noise curriculum, mixed precision |
| Single RPU config | Multi-tile, multi-chip | Moderate — AIHWKIT supports tile arrays |
| FloatingPoint | PCM drift over time | Significant — need drift model + compensation |

---

## What's Next (Phase 1 Continuation)

### Immediate (This Week)
1. **CIFAR-10 with analog ResNet-18** — Reproduce IBM's 92.81% result (or get close)
2. **Noise degradation measurement** — Train same ResNet with/without PCM noise, quantify accuracy gap
3. **Drift simulation** — Model PCM conductance drift over simulated days/weeks

### Phase 1 Completion Criteria
- [ ] CIFAR-10 analog accuracy within 5% of IBM published result
- [ ] Quantified noise degradation on ResNet-depth network
- [ ] Drift model implemented and tested
- [ ] Noise model library: PCM (done), flash (Mythic-style), RRAM (generic)

---

## Research Questions for Cipher

1. **IBM's CIFAR-10 92.81% result** — What exact architecture and training recipe? Is this published in detail?
2. **Hardware-aware training state of the art** — Beyond AIHWKIT's built-in noise injection, what techniques exist for making models robust to analog imprecision?
3. **Mixed-precision mapping** — Which layers are most sensitive to analog noise? Are there published heuristics or automated approaches?
4. **Competitive landscape** — Is anyone else building cross-platform analog training tools? Mythic's software stack, Syntiant's SDK, IBM's open-source position?

---

## Files Created
- `scripts/aihwkit_mnist_test.py` — Baseline validation script
- `scripts/aihwkit_pcm_noise_test.py` — PCM noise test script
- `data/` — MNIST dataset (downloaded automatically)

---

**Action required from Cipher:**
1. Review this brief
2. Research answers to the 4 questions above
3. Refine Phase 1 plan based on findings
4. Recommend whether to continue with AIHWKIT or pivot to custom PyTorch noise injection

**Action required from Orthia:**
- Execute whatever Cipher recommends for Phase 1 continuation
- Handle long-running training jobs
- Maintain environment and dependencies

---

*Orthia — May 27, 2026*
