# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for RAIN (R∞N). Each ADR documents a significant architectural choice, the context behind it, the decision itself, and the consequences. ADRs are immutable once accepted; revisions are made by superseding an existing ADR with a new one.

## Index

| ADR | Title | Status | Summary |
|---|---|---|---|
| [0001](0001-local-first-processing.md) | Local-First Processing via RainDSP WASM | Accepted | RainDSP C++/WASM is the only render engine; audio never leaves the device on the free path. |
| [0002](0002-dual-path-preview-render.md) | Dual-Path Preview (Web Audio) and Render (WASM) | Accepted | Preview uses float32 Web Audio; render uses float64 WASM; divergence up to ±0.5 LU is accepted, not unified. |
| [0003](0003-browser-server-ml-split.md) | Browser vs Server ML Model Split | Accepted | Models fitting the ~500 MB WASM / 1-2 GB WebGPU budget run in-browser; larger models run server-side. |
| [0004](0004-bs-roformer-over-demucs.md) | BS-RoFormer for Source Separation over Demucs v4 | Accepted | +2-4 dB SDR vs Demucs on vocals/bass/drums; 4-pass cascade for 12 stems, server-side GPU. |
| [0005](0005-c2pa-audioseal-provenance.md) | C2PA + AudioSeal + Chromaprint + RAIN-CERT Provenance Stack | Accepted | Four-layer provenance meeting EU AI Act Article 50 by 2026-08-02. |
| [0006](0006-hetzner-coolify-infrastructure.md) | Hetzner + Coolify Infrastructure over AWS | Accepted | Hetzner baseline + RunPod Serverless burst; 5-10x cheaper than AWS at equivalent compute. |
| [0007](0007-six-tier-pricing-architecture.md) | Six-Tier Pricing Architecture | Accepted | free / spark / creator / artist / studio_pro / enterprise, each with queue, rate, and feature gating. |
| [0008](0008-sequential-identifier-allocation.md) | Sequential Allocation of ISRC and UPC Identifiers | Accepted | Atomic per-scope counter via INSERT ON CONFLICT; random allocation is rejected by distributors. |
| [0009](0009-processing-params-canonical-schema.md) | Canonical ProcessingParams Schema | Accepted | Field names are immutable across frontend/backend/WASM; code-gen via openapi-typescript. |
| [0010](0010-64-dim-artist-identity-vector.md) | 64-Dimensional Artist Identity Vector (AIE) | Accepted | 64 dims with semantic decomposition; per-dim EMA α=0.90 stable / α=0.60 cold-start. |
| [0011](0011-valkey-over-redis.md) | Valkey over Redis | Accepted | Linux Foundation BSD fork, 37% faster SET throughput, drop-in protocol compatible. |
| [0012](0012-celery-tier-based-queue-routing.md) | Celery Tier-Based Queue Routing | Accepted | Six queues; GPU workers run `--pool solo --concurrency 1 --prefetch-multiplier 1`. |
| [0013](0013-larsnet-license.md) | LarsNet Drum Separation License Blocker | Accepted | CC BY-NC 4.0 blocks commercial use; spectral fallback interim; custom training or license required. |

## Format

Each ADR follows the standard template:

- **Status**: Accepted, Proposed, or Superseded by ADR-XXXX
- **Context**: the forces at play and the problem being solved
- **Decision**: what was decided
- **Consequences**: positive, negative, and neutral outcomes
- **Alternatives Considered**: other options and why they were rejected
