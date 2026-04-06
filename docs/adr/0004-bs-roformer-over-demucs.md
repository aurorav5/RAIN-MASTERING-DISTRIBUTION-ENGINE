# ADR-0004: BS-RoFormer for Source Separation over Demucs v4

## Status
Accepted

## Context
RAIN's SAIL (Stem-Aware Intelligent Limiting) feature requires high-quality source separation into a 12-stem taxonomy (vocals, lead vocals, backing vocals, drums, kick, snare, cymbals, bass, guitars, keys, synths, other). The quality of the separation directly determines mastering output quality: any bleed between stems compounds into limiter pumping, mud in the low end, and stereo imaging artifacts.

Benchmark candidates on the MUSDB18-HQ and SDXDB23 datasets:

| Model | Vocals SDR | Bass SDR | Drums SDR | Notes |
|---|---|---|---|---|
| Demucs v4 htdemucs_ft | ~9.2 | ~10.8 | ~10.4 | Strong baseline, widely used |
| Spleeter (2-stem / 4-stem) | ~6.7 | ~5.5 | ~6.6 | Legacy, low quality |
| BS-RoFormer (SW variant) | 11.30 | 14.62 | 14.11 | State of the art, 2024 |

BS-RoFormer (Band-Split RoFormer with Sliding Window) leads by 2-4 dB SDR across all three primary stems — a substantial perceptual gap. For drums (14.11 vs 10.4) and bass (14.62 vs 10.8), the delta is large enough to be audible as reduced artifact bleed in the SAIL-processed output.

## Decision
BS-RoFormer is the authoritative source-separation model for RAIN. It runs server-side (see ADR-0003) on GPU workers. The 12-stem pipeline is a cascaded 4-pass arrangement:

1. Pass 1: Primary 4-stem separation (vocals / drums / bass / other)
2. Pass 2: Vocal split (lead vs backing)
3. Pass 3: Drum kit decomposition (kick, snare, cymbals)
4. Pass 4: "Other" bus decomposition (guitars, keys, synths, residual)

Each pass uses a BS-RoFormer variant tuned for that stem family. Demucs v4 htdemucs_6s is retained as a documented fallback only and is not in the production path.

## Consequences

**Positive:**
- +2-4 dB SDR improvement across vocals/bass/drums translates directly into cleaner SAIL output and more headroom during stem-aware limiting.
- 12-stem output unlocks fine-grained SAIL controls (per-element gain) that 4-stem separation cannot support.
- State-of-the-art positioning on marketing claims (publishable SDR scores).

**Negative:**
- BS-RoFormer inference is ~2-3x slower than Demucs v4 per stem; the 4-pass cascade multiplies that cost. Separation becomes the dominant GPU time consumer.
- Model size (280-370 MB per checkpoint) pushes past the ONNX RT Web budget, forcing server-only deployment and therefore tier-gating of the feature.
- Cold-start time on GPU workers is longer (model load per pass).

**Neutral:**
- Requires RunPod Serverless burst capacity (see ADR-0006) to absorb bursts without over-provisioning Hetzner GPU baseline.
- Locks RAIN into a specific architecture; future separation improvements require BS-RoFormer-lineage models or a full migration.

## Alternatives Considered

1. **Demucs v4 htdemucs_ft.** Rejected as primary. Strong but 2-4 dB behind BS-RoFormer on the stems that matter most for mastering (vocals, bass, drums). Retained as fallback for documentation purposes.
2. **Spleeter.** Rejected. SDR scores (~6-7 dB) are insufficient for professional mastering output; the separation bleed would defeat the purpose of SAIL.
3. **Open-Unmix (UMX-L).** Rejected. Competitive with Demucs v3 but clearly behind Demucs v4 and BS-RoFormer.
4. **HTDemucs + fine-tuned split heads.** Considered. Would reduce inference cost vs. cascaded BS-RoFormer but requires RAIN to train and maintain custom heads. Not worth the engineering investment given the SDR gap.
