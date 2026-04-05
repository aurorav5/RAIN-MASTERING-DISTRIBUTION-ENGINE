# ADR-0001: Local-First Processing via RainDSP WASM

## Status
Accepted

## Context
RAIN ("Rain doesn't live in the cloud") competes in a crowded AI-mastering market where every serious competitor (LANDR, eMastered, CloudBounce, iZotope Ozone Online, BandLab) uploads user audio to cloud GPU clusters for processing. This creates three existential problems for RAIN:

1. **Competitive threat**: Server-side rendering is a commodity. Audio upload is a privacy liability, and round-trip latency on large WAV files is a UX tax. A local-first engine is the only defensible moat.
2. **Privacy**: Professional mastering engineers, labels, and A-list artists refuse to upload unreleased masters to third-party servers. The ability to guarantee "audio never leaves your machine" is table stakes for the Studio Pro and Enterprise tiers.
3. **Cost**: Server-side mastering of a 4-minute WAV file at 48 kHz / 24-bit incurs ~50 MB of S3 ingress plus ~50 MB egress per render. At free-tier scale, this is unsustainable. Cloud GPU per-minute billing makes free renders economically impossible for any server-rendered architecture.

## Decision
All final renders execute in the C++/WASM RainDSP engine on the client device. The WASM binary is the ONLY render engine. No server-side mastering path exists. Specifically:

- RainDSP is compiled to WebAssembly via Emscripten 3.1.50+ and distributed as a versioned binary.
- Every deployed WASM binary is pinned by SHA-256 hash (`rain_dsp_wasm_hash`) and archived forever.
- Session manifests record the hash at render time; mismatch raises RAIN-E304 and blocks the render.
- The free tier renders entirely in-browser. Audio is held in an `ArrayBuffer`, played via Web Audio API, and discarded on session close. No S3 write, no disk write, no session persistence.
- Audio reaches RAIN servers only when the user explicitly initiates distribution (DDEX push) or collaboration (shared session).

## Consequences

**Positive:**
- Zero S3 egress and zero cloud GPU cost on the free tier, enabling sustainable unit economics at scale.
- Deterministic, bit-identical output across all clients running the same WASM binary hash (64-bit double, strict IEEE 754, no RNG in render path).
- Provable privacy guarantee: the hash manifest is cryptographic evidence that the audio was rendered locally.
- Differentiated positioning against LANDR, eMastered, CloudBounce, BandLab — all of which are cloud-only.

**Negative:**
- Client device capability becomes a dependency. Low-end mobile devices may struggle with long-form 48 kHz stereo renders.
- WASM binary size is a page-load cost (mitigated by aggressive caching + CDN).
- Debugging production DSP bugs is harder: logs must be shipped from the client, and reproduction requires the exact WASM hash.
- Release engineering is more complex: every WASM rebuild invalidates in-flight sessions whose manifests pin a prior hash.

**Neutral:**
- Forces ML inference tiers to be split (see ADR-0003): only models that fit in ONNX Runtime Web's WASM/WebGPU budget can run locally.
- Preview and render diverge slightly due to float32 vs float64 precision differences (see ADR-0002).

## Alternatives Considered

1. **Server-side rendering (cloud GPU).** Rejected. Economically infeasible at free-tier scale, privacy-hostile for the Studio Pro audience, and commodity offering with no differentiation.
2. **Native desktop-only engine (no browser path).** Rejected. Raises the free-to-paid conversion barrier. Browser-first onboarding is required for the Spark and Creator tier funnel.
3. **Hybrid (preview local, render server-side).** Rejected. Keeps the S3 egress cost, keeps the privacy liability, and creates a confusing dual-engine story.
4. **WebGPU-first render path (skip WASM).** Rejected. WebGPU lacks the strict IEEE 754 determinism guarantees RAIN requires for bit-identical output across clients. WASM with 64-bit double is the only deterministic target today.
