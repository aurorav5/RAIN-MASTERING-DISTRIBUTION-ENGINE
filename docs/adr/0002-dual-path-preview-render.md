# ADR-0002: Dual-Path Preview (Web Audio) and Render (WASM)

## Status
Accepted

## Context
RAIN must give users immediate, interactive auditory feedback as they tweak mastering parameters (EQ curves, multiband thresholds, saturation drive, stereo width). "Mastering without real-time monitoring" is not a product. At the same time, the authoritative deliverable — the file the user downloads, distributes, or certifies — must be deterministic and bit-identical across clients.

These two goals impose contradictory constraints:

- **Real-time monitoring** requires low-latency scheduling, tolerates non-determinism, and benefits from the browser's native audio graph (Web Audio API). Web Audio uses 32-bit float internally and schedules on an independent audio thread with non-deterministic timing.
- **Authoritative render** requires 64-bit double precision, strict IEEE 754, deterministic scheduling, and bit-identical output across CPU architectures. This is RainDSP's WASM engine.

Attempting to unify these paths — either by running WASM in real-time or by making Web Audio deterministic — is a category error. Web Audio scheduling is non-deterministic by W3C specification, and WASM DSP at 64-bit double in real-time exceeds the latency budget for interactive monitoring on typical hardware.

## Decision
RAIN ships two distinct audio paths, formally separated:

- **Preview path**: Web Audio API, 32-bit float, non-deterministic scheduling, <50 ms latency. Used exclusively for in-session monitoring. Metering values shown alongside preview are labeled "Preview measurement — final render may differ slightly."
- **Render path**: RainDSP WASM, 64-bit double, strict IEEE 754, deterministic. Used exclusively for the authoritative output. All measurements on the manifest, RAIN-CERT, and DDEX payload come from this path.

The two paths are allowed to diverge within documented bounds:
- Integrated LUFS: up to ±0.5 LU between preview and render
- True peak: up to ±0.3 dBTP between preview and render

No attempt is made to make the paths bit-identical. The UI discloses this divergence wherever preview measurements are shown.

## Consequences

**Positive:**
- Interactive parameter tweaking stays responsive on typical consumer hardware.
- Authoritative renders remain deterministic, auditable, and reproducible from the WASM hash.
- Measurement honesty: users are told when they're looking at preview numbers vs. final numbers.
- Simplifies the WASM engine: it never has to meet real-time latency budgets.

**Negative:**
- Two DSP implementations to maintain for the same processing block (EQ, multiband, limiter, etc.). Preview implementation lives in Web Audio nodes; render implementation lives in C++.
- User education burden: some users will misread preview LUFS as final LUFS. Mitigated by UI disclaimers and by always showing the post-render measurement after completion.
- QA must test both paths independently and verify that divergence stays within the ±0.5 LU / ±0.3 dBTP envelope.

**Neutral:**
- Forces a clean mental model: "Preview is what you hear, Render is what you ship."

## Alternatives Considered

1. **Single-path (WASM for both preview and render).** Rejected. WASM DSP at 64-bit double cannot meet <50 ms interactive latency for full-chain processing on typical consumer hardware. Dropping to 32-bit float in WASM would give up the determinism guarantee for the render path.
2. **Single-path (Web Audio for both).** Rejected. Web Audio is non-deterministic and float32. The render deliverable would not be bit-identical across clients, breaking RAIN-CERT provenance and the hash-pinned manifest.
3. **Bit-identical dual-path (WASM-accurate preview).** Rejected. The engineering cost of making Web Audio's non-deterministic scheduler emit the same samples as strict IEEE 754 double-precision WASM is prohibitive, and the W3C spec does not guarantee the behavior across browsers.
4. **AudioWorklet-only path with shared WASM.** Considered. AudioWorklet can host WASM, but real-time scheduling constraints still force a precision compromise. Kept as a future optimization for specific blocks, not as a unifying architecture.
