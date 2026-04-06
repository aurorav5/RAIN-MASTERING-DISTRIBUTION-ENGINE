# ADR-0013: LarsNet Drum Separation License Blocker

## Status
Accepted

## Context
RAIN's 12-stem separation pipeline (spec section 4) requires sub-separation of the drum bus into kick, snare, hats, and percussion. The leading open model for this is **LarsNet** from Polimi-ISPL (arXiv:2312.09663), trained on the 1,224-hour StemGMD dataset.

LarsNet outputs 5 drum stems (kick, snare, toms, hi-hat, cymbals) with state-of-the-art quality. No pip package exists — it requires cloning the GitHub repo and downloading a 562 MB checkpoint from Google Drive.

**The blocker:** LarsNet's model weights are released under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial). RAIN is a commercial product. Using LarsNet weights in production would violate the license.

## Decision
1. **Spectral band-splitting fallback** is the interim Pass 3 implementation:
   - Kick: lowpass < 200 Hz
   - Snare: bandpass 200-5000 Hz
   - Hats: highpass > 5000 Hz
   - Percussion: residual (input - kick - snare - hats)

   This is acoustically reasonable but not ML-quality. It ships today with no license risk.

2. **Before production drum separation via ML**, one of these paths must be taken:
   - **Option A:** Contact Polimi-ISPL (Politecnico di Milano) to negotiate a commercial license for LarsNet weights.
   - **Option B:** Train a custom drum separator on the StemGMD dataset (CC BY 4.0 — the *dataset* is permissively licensed, only the *model weights* are NC).
   - **Option C:** Use a BS-RoFormer or MelBand RoFormer checkpoint fine-tuned on drum stems via ZFTurbo's Music-Source-Separation-Training repo (MIT training code, model weights from community — check per-model license).

3. **No LarsNet weights will be bundled, downloaded, or loaded in RAIN** until a commercial license is secured or an alternative model is trained.

## Consequences

**Positive:**
- No license liability — RAIN ships legally clean
- Spectral fallback provides reasonable drum sub-separation for most material
- StemGMD dataset (CC BY 4.0) enables training a custom model with no license constraints

**Negative:**
- Spectral band-splitting produces audible artifacts on complex drum mixes (e.g., toms bleed into snare band, cymbals bleed into hats)
- Training a custom model requires GPU time (~24-48 hours on A100) + engineering effort (~1-2 weeks)
- LarsNet commercial licensing timeline is unknown (academic lab, no published pricing)

**Neutral:**
- The anvuew dereverb MelBand RoFormer (Pass 4) is **GPL-3.0** — server-side inference-only use is generally acceptable, but should be reviewed by legal before production deployment.
- BS-RoFormer SW and Karaoke models (Passes 1-2) have no restrictive license — community/MIT weights.

## Alternatives Considered
- **Use LarsNet anyway and deal with license later:** Rejected. CC BY-NC violation is clear and enforceable. No "ask forgiveness" approach for a commercial SaaS product.
- **Skip drum sub-separation entirely:** Rejected. 12-stem is the spec's flagship differentiator. The spectral fallback is acceptable for launch; ML-quality must follow.
- **Use Demucs for drum sub-separation:** Demucs doesn't sub-separate drums — it outputs a single "drums" stem. Same limitation as Pass 1 without the cascade.
