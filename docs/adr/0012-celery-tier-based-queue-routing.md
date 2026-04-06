# ADR-0012: Celery Tier-Based Queue Routing

## Status
Accepted

## Context
RAIN runs a heterogeneous background workload:

- **CPU-bound tasks**: content scanning, AIE vector updates, RAIN-CERT signing, DDEX payload generation, Chromaprint fingerprinting, Stripe webhook handling.
- **GPU-bound tasks**: BS-RoFormer separation, SonicMaster refinement, MERT embedding, Music2Emo mood tagging.
- **Distribution tasks**: LabelGrid submission, Quansic ISRC lookup, platform-specific payload assembly.
- **Certification tasks**: C2PA manifest construction, AudioSeal watermark embedding, Ed25519 signing.

These workloads have incompatible scheduling requirements. GPU tasks need exclusive CUDA context ownership (CUDA does not tolerate worker forking). CPU tasks benefit from high concurrency. Distribution tasks have external rate limits and long tail latency. Certification tasks are cheap but must be serialized against the Ed25519 key.

In addition, RAIN's six-tier pricing (ADR-0007) requires that paid tiers get priority GPU access under load: an Enterprise render must not queue behind 200 free-tier content scans.

## Decision
RAIN runs six Celery queues with tier-aware routing:

| Queue | Purpose | Workers |
|---|---|---|
| `cpu_standard` | Content scan, AIE update, fingerprinting | CPU, high concurrency (prefork, 4-8 workers) |
| `gpu_priority_low` | Creator-tier GPU inference | GPU, 1 worker, solo pool |
| `gpu_priority_medium` | Artist-tier GPU inference | GPU, 1 worker, solo pool |
| `gpu_priority_high` | Studio Pro + Enterprise GPU inference | GPU, 1 worker, solo pool |
| `distribution` | LabelGrid, Quansic, DDEX push | CPU, low concurrency (network-bound) |
| `certification` | C2PA, AudioSeal, RAIN-CERT signing | CPU, single worker (key serialization) |

**GPU worker configuration** (mandatory):
```
celery worker --pool solo --concurrency 1 --prefetch-multiplier 1
```

- `--pool solo` avoids the prefork pool, which would fork the CUDA context and crash.
- `--concurrency 1` ensures one GPU task at a time per worker.
- `--prefetch-multiplier 1` prevents queue starvation: a busy GPU worker doesn't lock out tasks that could go to an idle peer.

**Tier-to-queue mapping** lives in `app/core/tiers.py` as a single source of truth. Task enqueue code calls `tier_to_gpu_queue(user.tier)` to select the priority queue; it never hard-codes the queue name.

## Consequences

**Positive:**
- Enterprise and Studio Pro GPU jobs get unconditional priority over lower tiers under load — the scheduling guarantee is structural, not a runtime check.
- GPU worker configuration is correct by construction: no CUDA fork crashes, no concurrent-GPU-call races, no prefetch lockouts.
- Queue names are self-documenting: reading the Celery inspect output immediately reveals what's running and at which priority.
- Separate `distribution` and `certification` queues isolate external-API latency and key-serialization constraints from the main render path.

**Negative:**
- Six queues is more operational surface than one. Worker pools must be sized and monitored per queue, and Celery inspect tooling has to cover all of them.
- GPU workers at `--concurrency 1` waste CUDA context capacity on single-stream models; multi-stream batching would be more efficient but is not CUDA-fork-safe in Celery's prefork pool.
- Tier-to-queue mapping must be updated whenever a tier is added, removed, or re-priced (ADR-0007 dependency).

**Neutral:**
- Forces a discipline: every background task declaration names its queue explicitly.
- Makes autoscaling per-queue, which maps naturally to Hetzner baseline + RunPod Serverless burst (ADR-0006).

## Alternatives Considered

1. **Single queue with task priorities.** Rejected. Celery's priority support is broker-dependent and weak on Redis/Valkey compared to RabbitMQ. Even with RabbitMQ priorities, CUDA fork issues and per-tier isolation are not solved by priority alone.
2. **Prefork-pool GPU workers with lazy CUDA init.** Rejected. Empirically fragile: CUDA context inheritance across fork is undefined behavior, and lazy init doesn't fully avoid the crash on some driver/PyTorch versions.
3. **Kubernetes Jobs per render (no persistent workers).** Considered. Cleanest isolation but adds significant cold-start latency per job (model load, CUDA init), unacceptable on the interactive render path.
4. **Unified `gpu` queue without per-tier priority.** Rejected. Breaks the tier guarantees of the pricing architecture (ADR-0007).
5. **Dask / Ray instead of Celery.** Considered. Stronger distributed-compute primitives but larger operational footprint than Celery and no clear advantage for RAIN's straightforward task-queue workload.
