# ADR-0007: Six-Tier Pricing Architecture

## Status
Accepted

## Context
RAIN serves a wide audience range — bedroom producers trialing AI mastering, working musicians with monthly release cadence, serious home-studio engineers, professional mastering engineers, and enterprise labels. Collapsing this range into three tiers (common industry default: free / pro / enterprise) creates two failure modes:

1. **Compression at the low end.** Bedroom producers and monthly-cadence creators have radically different willingness-to-pay. One "pro" tier forces a choice between pricing out hobbyists or underpricing the creator segment.
2. **Feature incoherence at the high end.** Professional engineers need Atmos, DDP, vinyl chains, and collaboration; enterprise wants custom RainNet + white-label API. Bundling both into one "enterprise" tier makes pricing opaque and muddies the feature narrative.

The six-tier model maps cleanly to distinct customer segments, each with a clear jobs-to-be-done profile, and enables tier-gated routing at the infrastructure level (see ADR-0012).

## Decision
RAIN ships six paid tiers (plus a listening-only free tier):

| Tier | Price | Downloads/mo | Segment |
|---|---|---|---|
| Free | $0 | 0 (listen only) | Trial / discovery |
| Spark | $9/mo | 50 | Hobbyists, occasional release |
| Creator | $29/mo | 10 full renders | Monthly-release creators |
| Artist | $59/mo | 25 full renders | Working musicians |
| Studio Pro | $149/mo | 75 full renders | Professional engineers |
| Enterprise | ~$499+ | Unlimited | Labels, white-label API |

Each tier is gated at three independent layers:

- **Queue routing**: free/spark → `cpu_standard`; creator → `gpu_priority_low`; artist → `gpu_priority_medium`; studio_pro/enterprise → `gpu_priority_high`.
- **Rate limits**: per-tier request ceilings on the API gateway.
- **Feature gating**: every feature declares `require_min_tier` (e.g., stems require Creator+, Atmos requires Studio Pro+).

Overage rates: Spark $0.49, Creator $5.99, Artist $2.99, Studio Pro $1.49 per additional download. Annual discount ~20%.

## Consequences

**Positive:**
- Clean per-segment narrative: each tier has a distinct target buyer and a distinct reason to upgrade.
- Infrastructure-level tier awareness enables fair GPU allocation under load (paid tiers never starve due to free traffic).
- Six tiers create five upgrade nudges, improving LTV progression: Free→Spark→Creator→Artist→Studio Pro→Enterprise.
- Per-tier feature gating keeps the feature matrix explicit in code (`require_min_tier`), preventing accidental leakage of paid features to lower tiers.

**Negative:**
- More pricing surface to A/B test, more landing-page variants, more support questions ("which tier is right for me?").
- Six-tier billing logic is more complex than three-tier: more Stripe price IDs, more overage calculations, more upgrade/downgrade paths.
- Middle tiers (Creator, Artist) risk cannibalizing each other if feature differentiation is not crisp.

**Neutral:**
- Forces every feature PR to answer "what tier?" up front — no feature can merge without a `require_min_tier` declaration.
- Queue architecture (ADR-0012) is directly shaped by the tier count.

## Alternatives Considered

1. **Three-tier (free / pro / enterprise).** Rejected. Compresses the low end (hobbyist vs. creator) and muddles the high end (engineer vs. label).
2. **Usage-based only (pay per render, no subscriptions).** Rejected. Breaks subscription forecasting, adds billing friction on every export, and is hostile to the Studio Pro segment which values predictable monthly spend.
3. **Four-tier (free / creator / pro / enterprise).** Considered. Cleaner but still underserves the hobbyist segment at $9/mo and blurs the engineer/label distinction.
4. **Eight-tier (creator sub-tiers).** Rejected. Added complexity without a corresponding segment differentiation.
