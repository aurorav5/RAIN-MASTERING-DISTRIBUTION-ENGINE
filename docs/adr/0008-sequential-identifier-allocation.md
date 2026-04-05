# ADR-0008: Sequential Allocation of ISRC and UPC Identifiers

## Status
Accepted

## Context
RAIN's Distribution Intelligence feature generates industry-standard identifiers for outgoing releases:

- **ISRC** (International Standard Recording Code, ISO 3901): 12 characters, structured as `CC-XXX-YY-NNNNN` — country code, registrant code, year, five-digit designation code. The designation code MUST be unique within a registrant-year and is typically assigned sequentially.
- **UPC/EAN** (GS1 GTIN-12/13): barcode identifier for the release, allocated out of a GS1-assigned prefix block.

Both identifier classes are governed by allocation blocks issued by their respective authorities (IFPI for ISRC registrant codes; GS1 for UPC prefixes). Distributors (LabelGrid, Quansic, TuneCore, DistroKid, etc.) validate that submitted identifiers:

1. Fall inside the declared registrant/prefix block.
2. Are unique within the block.
3. Are not duplicated across submissions.

Distributors routinely reject randomly-generated identifiers because random allocation makes it impossible to prove the identifier falls inside an allocated block without an external registry lookup. A submitted ISRC that looks random is assumed to be fabricated until proven otherwise.

Beyond distributor rejection, sequential allocation is auditable (you can prove block exhaustion), gap-free (you can detect missing allocations), and trivially rate-limitable.

## Decision
ISRC designation codes and UPC check-digit-bearing sequences are allocated strictly sequentially from a database counter per registrant-year (ISRC) or per GS1 prefix (UPC). Allocation uses a single atomic SQL statement:

```sql
INSERT INTO identifier_counters (scope, next_value)
VALUES (:scope, 1)
ON CONFLICT (scope) DO UPDATE
  SET next_value = identifier_counters.next_value + 1
RETURNING next_value - 1 AS allocated;
```

The `scope` key encodes `(registrant_code, year)` for ISRC and `(gs1_prefix)` for UPC. Allocation is transactional, monotonic, and gap-free. Random allocation is explicitly prohibited in the distribution codebase.

## Consequences

**Positive:**
- Distributor acceptance rate is high: identifiers fall verifiably inside registered blocks with no gaps.
- Atomic counter pattern is concurrency-safe under PostgreSQL's default isolation — no double-allocation under load.
- Block exhaustion is predictable: `next_value` vs. block ceiling gives capacity forecasting.
- Audit trail is natural: gaps indicate lost allocations or bugs; duplicates indicate counter corruption.

**Negative:**
- Counter is a write-serialization point under very high allocation rates. At RAIN's projected volume, this is not a bottleneck, but a high-volume label integration would require per-scope counter sharding.
- Sequential allocation leaks volume information to competitors who can inspect multiple RAIN-submitted ISRCs and infer the allocation rate.
- Block transitions (e.g., new year) require administrative action: the scope key changes, and the new scope starts at 1.

**Neutral:**
- Binds RAIN to IFPI/GS1 allocation discipline: block boundaries must be respected and registered.

## Alternatives Considered

1. **Random allocation within block.** Rejected. Distributors reject random-looking codes; proof-of-membership in the allocated block is non-trivial; duplicates are possible without a dedupe table that effectively reconstructs a counter.
2. **UUID-based identifiers.** Rejected. ISO 3901 and GS1 specifications MANDATE the structured format; UUIDs are not a legal ISRC or UPC.
3. **Centralized external allocation service (IFPI portal, GS1 registrar).** Rejected as the primary path. RAIN's registrant blocks are pre-allocated; per-identifier external calls add latency and a third-party availability dependency. External registration happens in bulk after the fact.
4. **Hash-based allocation (H(session_id) mod block_size).** Rejected. Collisions are guaranteed at scale; gap detection becomes impossible; reversibility leaks session information.
