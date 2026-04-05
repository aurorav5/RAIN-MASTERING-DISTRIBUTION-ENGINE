# ADR-0006: Hetzner + Coolify Infrastructure over AWS

## Status
Accepted

## Context
RAIN's server-side workload is dominated by GPU inference (BS-RoFormer, SonicMaster, MERT), a PostgreSQL + Valkey (see ADR-0011) control plane, S3-compatible object storage, and Celery worker queues. Hyperscaler pricing (AWS, GCP, Azure) on this profile is 5-10x more expensive than European bare-metal providers for equivalent compute. At RAIN's projected paid-tier activity, AWS GPU on-demand pricing alone would consume the entire Creator-tier margin.

The counterweight to bare-metal cost savings is operational overhead: hyperscalers provide managed databases, managed object storage, managed queues, and managed deploy pipelines. A bare-metal provider gives none of these.

Coolify (self-hosted Heroku-equivalent) closes most of that gap: it provides deploy pipelines, one-click service provisioning, backup automation, and TLS certificate management on top of a Hetzner VPS or dedicated server.

## Decision
RAIN runs on Hetzner with Coolify orchestration as the primary infrastructure, with RunPod Serverless for GPU burst capacity.

**Baseline (Hetzner):**
- GEX44 (Intel, RTX 4000 Ada 20 GB VRAM) — baseline GPU worker for BS-RoFormer and SonicMaster inference
- CX/CCX-series VPS — FastAPI backend, Celery workers (CPU queues), PostgreSQL 18.3, Valkey, MinIO
- Coolify for deployment, TLS, backups, service health

**Burst (RunPod Serverless):**
- On-demand GPU workers (RTX 4090, A100) for spike traffic (queue depth > threshold)
- Triggered by autoscaler on `gpu_priority_high` queue saturation

**Cost trajectory:**
- Hobby / closed beta: €15-25/month
- Spark + Creator public launch: €80-150/month
- Artist + Studio Pro at scale: €400-800/month
- Enterprise / white-label: €1.8-2.2k/month

## Consequences

**Positive:**
- 5-10x lower infrastructure cost vs. AWS for the same workload profile. Preserves Creator-tier margin.
- Hetzner GPU pricing on GEX44 (RTX 4000 Ada) is roughly €180/month fixed — predictable, no per-second billing surprises.
- Coolify gives most hyperscaler-equivalent UX (deploy, rollback, TLS, backups) without vendor lock-in.
- RunPod Serverless absorbs bursts without provisioning idle GPU capacity, balancing fixed + variable cost.

**Negative:**
- No managed PostgreSQL: backup, PITR, replication, and failover are RAIN's responsibility.
- Hetzner uptime SLA is lower than AWS (99.9% vs 99.99%); RAIN must engineer resilience (replicas, standby, cross-region backup) explicitly.
- Coolify is a smaller ecosystem than Terraform/AWS CDK; hiring DevOps talent familiar with it is harder.
- Bare-metal hardware failures require manual ticket flow with Hetzner support, not API-initiated instance replacement.

**Neutral:**
- Forces RAIN to own its infra competence rather than outsourcing it to a cloud provider.
- Creates portability: nothing in the stack is hyperscaler-specific, so migration to any other provider (OVH, Scaleway, DigitalOcean) is mechanical.

## Alternatives Considered

1. **AWS (EC2 + RDS + S3 + SageMaker).** Rejected. 5-10x cost vs. Hetzner at equivalent compute. Creator-tier margin cannot absorb AWS GPU pricing.
2. **GCP (GKE + Cloud SQL + Vertex AI).** Rejected. Similar cost profile to AWS, plus steeper lock-in on managed AI services.
3. **Pure-serverless (RunPod + Supabase + Vercel).** Considered. Lowers DevOps burden further but sacrifices control over data residency and fixes per-request cost that's unfavorable at steady-state paid-tier volume.
4. **Self-managed Kubernetes on Hetzner.** Rejected for now. k8s operational overhead is higher than Coolify for a single-digit-service deployment. Revisit at >20 services or multi-region.
5. **OVH / Scaleway instead of Hetzner.** Considered. Price-competitive but GPU SKU availability and support responsiveness were weaker at the time of decision.
