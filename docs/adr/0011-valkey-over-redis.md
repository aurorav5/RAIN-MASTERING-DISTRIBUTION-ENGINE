# ADR-0011: Valkey over Redis

## Status
Accepted

## Context
In March 2024, Redis Ltd. relicensed Redis from BSD to the dual RSALv2/SSPLv1 licenses, removing the open-source designation and introducing restrictions on managed-service offerings by third parties. In response, the Linux Foundation forked Redis 7.2.4 under the original BSD license as Valkey, with backing from AWS, Google Cloud, Oracle, Ericsson, and Snap.

RAIN uses a Redis-protocol cache and queue backing store for:
- Celery task broker and result backend
- FastAPI rate limiting
- Session-derived ephemeral state (WASM hash pinning, live collaboration cursors)
- Feature flag caching

The decision is whether to continue on Redis (now source-available) or adopt the Linux Foundation fork.

Benchmark differences (Valkey 8+ / Redis 7.2): Valkey has landed performance work (I/O threading, command pipelining improvements) showing approximately 37% higher SET throughput vs. Redis 7.2 at equivalent hardware. Protocol compatibility is drop-in: Valkey accepts the RESP2/RESP3 protocol unchanged and all standard Redis commands behave identically.

## Decision
RAIN uses Valkey in place of Redis across all environments (dev, staging, production).

Client libraries continue to be the standard Redis client libraries (redis-py, ioredis) — no client changes are required because Valkey is protocol-compatible. Infrastructure references to "Redis" in documentation have been renamed to "Valkey"; the `REDIS_URL` environment variable name is retained for client-library compatibility but points to a Valkey instance.

## Consequences

**Positive:**
- License clarity: BSD license, actively stewarded by the Linux Foundation, no SSPL/RSALv2 restrictions on hosted offerings or enterprise distribution.
- 37% higher SET throughput gives headroom on the broker and rate-limit hot paths without scaling up instance size.
- Drop-in protocol compatibility means zero client-library migration and zero query-layer change.
- Broad industry alignment (AWS ElastiCache, Google Memorystore, Oracle OCI all offer Valkey) — future managed-service migration paths remain open.

**Negative:**
- Valkey is younger than Redis; some third-party modules and ecosystem tools still target Redis and may lag on Valkey support.
- Internal team familiarity is with "Redis" — documentation and onboarding must re-train the terminology.
- A small risk that Valkey and Redis diverge enough over time that protocol compatibility breaks for advanced features (streams, modules). Mitigated by pinning to the subset RAIN actually uses (pub/sub, lists, strings, hashes, sorted sets).

**Neutral:**
- Existing Celery, rate-limit, and cache code paths are unchanged.
- Environment variable name `REDIS_URL` is retained to avoid a mechanical rename across ~50 call sites.

## Alternatives Considered

1. **Stay on Redis (RSALv2/SSPLv1).** Rejected. License restrictions complicate any future managed-service offering or enterprise distribution, and RAIN gains nothing by staying.
2. **Migrate to KeyDB.** Considered. Multi-threaded Redis fork with good performance but smaller community and narrower industry backing than the Linux Foundation's Valkey.
3. **Migrate to Dragonfly.** Considered. Faster than both Redis and Valkey but architecturally different (not a drop-in Redis clone in all edge cases), and BSL-licensed (source-available, not open-source).
4. **Replace with a message-broker + cache split (e.g., RabbitMQ + Memcached).** Rejected. Doubles the infrastructure surface, requires Celery broker reconfiguration, and provides no benefit RAIN actually needs.
