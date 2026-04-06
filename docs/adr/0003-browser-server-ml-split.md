# ADR-0003: Browser vs Server ML Model Split

## Status
Accepted

## Context
RAIN runs a substantial ML stack: genre classification, mastering parameter prediction (RainNet), analog circuit emulation, speech denoising, source separation, reference matching, and conversational AI assistance. These models vary by four orders of magnitude in parameter count and compute cost. Running all of them in the browser is infeasible; running all of them on the server undermines the local-first architecture (see ADR-0001).

The hard constraint is ONNX Runtime Web's deployment budget:
- WASM execution provider: ~500 MB practical ceiling for model + runtime memory
- WebGPU execution provider: 1-2 GB depending on device, with tensor dispose requirements

Models exceeding these limits MUST run server-side. Models that fit MUST run client-side to preserve the local-first guarantee.

## Decision
ML models are split by parameter count and deployment target:

**Browser-side (ONNX Runtime Web, WASM or WebGPU):**
- RainNet base and tiny variants — mastering parameter prediction
- RTNeural analog emulations — tape, tube, transistor saturation models
- DeepFilterNet (~2M params) — speech/noise separation, vocal cleanup
- Essentia.js — feature extraction, key/tempo detection, spectral descriptors

**Server-side (Python + PyTorch/ONNX Runtime on GPU workers):**
- BS-RoFormer (280-370 MB) — 4-stem and 12-stem source separation
- SonicMaster — reference-aware mastering refinement
- MERT — music understanding embeddings
- Music2Emo — emotion/mood tagging
- Claude Sonnet (Anthropic API) — conversational assistant, mastering explanations

Routing: any request requiring a server-side model is gated by tier (see ADR-0007) and queued on the appropriate GPU queue (see ADR-0012).

## Consequences

**Positive:**
- RainNet inference stays local, preserving the free-tier privacy guarantee for the core mastering flow.
- The ~500 MB ONNX RT Web WASM budget is respected; pages don't OOM.
- Server GPU compute is reserved for models that genuinely cannot fit in-browser (separation, reference matching), keeping cloud cost proportional to paid-tier activity.
- Clear routing rule for future models: "Does it fit in 500 MB WASM or 1-2 GB WebGPU? If yes, browser. If no, server."

**Negative:**
- Users on the free tier cannot access source separation, reference matching, or conversational AI — these are tier-gated features.
- Two ML toolchains to maintain: ONNX export for browser models, PyTorch/ONNX for server models.
- Model upgrades that grow past the browser budget require migration to server-side and a tier policy change.

**Neutral:**
- Forces explicit tier-gating (see ADR-0007) of every server-dependent feature.
- Makes the "which tier can do what" matrix a direct function of model size.

## Alternatives Considered

1. **All models server-side.** Rejected. Breaks the local-first architecture (ADR-0001), forces audio upload on every session, and makes the free tier economically impossible.
2. **All models browser-side.** Rejected. BS-RoFormer alone exceeds the WASM budget by ~2x. MERT and SonicMaster are also out of budget. Claude Sonnet is an API-only model.
3. **WebGPU-first for all browser models.** Considered. WebGPU gives more headroom (1-2 GB) but has uneven device support and stricter tensor lifecycle requirements. RAIN uses WebGPU where advantageous but keeps WASM as the default execution provider.
4. **Self-host Claude-equivalent LLM.** Rejected. No open-weight model in the relevant size class matches Claude's quality on mastering explanations, and self-hosting a 70B+ model on GPU is cost-prohibitive compared to per-token API billing.
