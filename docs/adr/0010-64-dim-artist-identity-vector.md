# ADR-0010: 64-Dimensional Artist Identity Vector (AIE)

## Status
Accepted

## Context
The Artist Identity Engine (AIE) learns an individual artist's mastering preferences across sessions and nudges default ProcessingParams toward their personal sonic signature on each new track. This is the "mastering that sounds like YOU" feature — a durable moat against commodity AI mastering.

Two architectural choices shape the AIE: dimensionality and update rule.

**Dimensionality.** Too few dimensions (e.g., 8-16) cannot represent the full range of mastering preferences — EQ shape, dynamics profile, stereo behavior, coloring, genre inclination, and metadata preferences all need representation. Too many dimensions (e.g., 512+) sparsify the per-dimension signal, slow convergence, and inflate storage. Spotify's taste-profile embedding uses 80 dimensions as a well-documented reference point; RAIN targets the mastering-preference domain, which is narrower than general music taste.

**Update rule.** Batch retraining on the full per-artist history per session is wasteful. Exponential Moving Average (EMA) updates give a cheap, online, stable drift mechanism. The EMA coefficient α controls the stability/responsiveness tradeoff: high α (0.9-0.95) is stable and slow to drift; low α (0.5-0.7) is responsive but noisy.

**Cold-start.** A new artist has no history. The vector must be seeded without overfitting to the first session, which may be unrepresentative.

## Decision
The AIE artist vector is 64-dimensional, updated per session via per-dimension EMA.

**Dimension decomposition (semantic, documented):**
- dims 0-9: EQ preferences (band-shape centroids and gains)
- dims 10-19: dynamics preferences (compression ratio, attack/release, multiband balance)
- dims 20-29: stereo/width preferences (M/S balance, stereo width envelope)
- dims 30-39: coloring preferences (saturation mode, drive, analog character)
- dims 40-49: genre inclination (soft one-hot over RAIN's genre taxonomy)
- dims 50-63: meta preferences (target LUFS, true peak ceiling, vinyl propensity, platform bias)

**Update rule (per dimension):**
```
v_new[i] = α · v_old[i] + (1 − α) · observed[i]
```

- α = 0.90 for stable artists (≥5 sessions, consistent genre)
- α = 0.60 for cold-start (<5 sessions) — faster drift toward the emerging signature

**Cold-start seeding.** A new artist vector is initialized from the genre-weighted mean of the population AIE vectors, NOT from zero. The first session's observed params then drift the vector under α=0.60.

## Consequences

**Positive:**
- 64 dimensions is sufficient to represent mastering preferences across the full EQ/dynamics/stereo/coloring/genre/meta surface without sparsity.
- Per-dimension EMA is O(64) per session — trivially cheap at any scale.
- Cold-start seeding from population means gives new artists a reasonable vector immediately, avoiding the "random defaults for the first 3 sessions" UX.
- Semantic decomposition makes the vector inspectable and debuggable — each segment maps to a known DSP subsystem.

**Negative:**
- 64 is a design choice without a formal optimality proof. If future signal reveals that 48 or 96 is better, migration requires re-embedding every historical session.
- Per-dimension EMA assumes dimensions are independent. In reality, EQ and dynamics co-vary; the independence assumption loses a small amount of signal.
- Genre-weighted cold-start inherits population bias: new artists in underrepresented genres get weaker seeds.

**Neutral:**
- Inspired by Spotify's 80-dim taste profile, scaled down for the narrower mastering-preference domain.
- Keeps the AIE readable to humans (64 floats per artist) rather than opaque (a 1024-dim deep-learned embedding).

## Alternatives Considered

1. **Learned deep embedding (e.g., 128-dim from a neural encoder).** Rejected for v1. Harder to debug, slower to update, and overkill for the per-artist preference-drift use case. Kept as a future option if the hand-designed vector plateaus.
2. **Batch retrain per artist.** Rejected. Quadratically expensive as session count grows, offers no meaningful quality advantage over EMA at this scale.
3. **Single α for all artists.** Rejected. Cold-start artists need higher responsiveness than stable long-term artists; a single α compromises both.
4. **Zero-initialized cold-start.** Rejected. Produces poor first-session recommendations, damaging new-user retention.
5. **32-dim or 128-dim vector.** Considered. 32 underrepresents the coloring + genre + meta dimensions; 128 sparsifies the per-dimension signal given the session-count distribution. 64 was chosen as the balance.
