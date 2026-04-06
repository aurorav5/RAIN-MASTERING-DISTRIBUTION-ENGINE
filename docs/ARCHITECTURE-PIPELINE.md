# RAIN Processing Pipeline — Full Architecture

**Document ID:** RAIN-ARCH-PIPELINE-v1.0
**Date:** 1 April 2026

---

## The Complete Pipeline

```
User Language
     │
     ▼
┌─────────────┐
│ INTENT      │  "make it warmer and punchier"
│ ENGINE      │  → classify intent → generate signals → apply restraints
│             │  → {warmth: +2.5, punch: +2.5, brighten: -0.8}
└──────┬──────┘
       │ ControlSignals (bounded deltas + confidence + restraints)
       ▼
┌─────────────┐
│ MACRO       │  Apply deltas to current MacroValues (7 knobs)
│ CONTROLLER  │  {brighten: 4.2, glue: 6.0, width: 5.0, punch: 7.5,
│             │   warmth: 5.0, space: 3.0, repair: 0.0}
└──────┬──────┘
       │ MacroValues (7 × [0.0, 10.0])
       ▼
┌─────────────┐
│ RAINNET v2  │  EfficientNet-B2 + FiLM conditioning
│ (or heuristic│  Genre-aware, platform-aware, artist-identity-aware
│  fallback)  │  → 46 DSP parameters
└──────┬──────┘
       │ ProcessingParams (46 canonical fields)
       ▼
┌─────────────┐
│ PARAMETER   │  Range validation, schema conformance, conflict detection
│ VALIDATION  │  All fields present, all values in range
└──────┬──────┘
       │ Validated ProcessingParams
       ▼
┌─────────────┐
│ RAINDSP     │  C++20/WASM, 64-bit double, deterministic
│ ENGINE      │  EQ → Multiband → M/S → Saturation → SAIL Limiter → Dither
└──────┬──────┘
       │ Processed audio
       ▼
┌─────────────┐
│ RESTRAINT   │  Post-processing verification:
│ VALIDATOR   │  - LUFS within ±0.5 LU of target?
│             │  - True peak below ceiling?
│             │  - Crest factor preserved ≥60% of input?
│             │  - No phase cancellation introduced?
│             │  If ANY fail → reduce gain, retry (max 3 iterations)
└──────┬──────┘
       │ Verified audio
       ▼
┌─────────────┐
│ RAIN SCORE  │  Technical(60) + Dynamic(15) + Translation(10) + Emotional(15)
│ v2          │  → overall: 0-100
│             │  → verdict: "Release-ready" / "Needs work"
│             │  → per-platform compliance
└──────┬──────┘
       │ ScoreBreakdown
       ▼
┌─────────────┐
│ OUTPUT      │  WAV 24-bit/48kHz (archive master)
│             │  MP3 320kbps/44.1kHz (with LUFS correction)
│             │  RAIN-CERT Ed25519 provenance signature
│             │  C2PA v2.2 manifest (EU AI Act Article 50)
└─────────────┘
```

---

## Layer Responsibilities

### 1. Intent Engine (`intent_engine.py`)

**Input:** Natural language string
**Output:** `IntentResult` containing `ControlSignal[]`

The Intent Engine is NOT an LLM prompt wrapper. It is a deterministic
keyword-based classifier with structured signal generation and restraint gates.

When Claude API is available, the Intent Engine uses Claude for ambiguous
queries. But it can function entirely offline with the keyword classifier.

Key design principle: **The Intent Engine decides WHAT to change. RainNet decides HOW MUCH.**

### 2. Restraint System (integrated into Intent Engine)

The Restraint System prevents over-processing. It operates at TWO levels:

**Pre-processing restraints** (Intent Engine):
- Don't push parameters past extremes
- Temper conflicting adjustments (warmth vs brightness)
- Cap stereo width for mono compatibility
- Respect analysis data (don't boost loudness if already hot)

**Post-processing restraints** (Validation):
- LUFS compliance check (±0.5 LU)
- True peak ceiling enforcement (iterative)
- Crest factor preservation (≥60%)
- Phase correlation check

### 3. RAIN Score v2 (`rain_score_v2.py`)

**Input:** Processed audio + optional input audio for comparison
**Output:** `ScoreBreakdown` (0-100 with sub-scores)

Breakdown:
- **Technical** (60 pts): Loudness, True Peak, Spectral Balance, Stereo Field
- **Dynamic Integrity** (15 pts): Crest Preservation, Micro-dynamics
- **Translation** (10 pts): Mono Compatibility, Codec Resilience
- **Emotional Impact** (15 pts): Energy Arc, Tension Index, Presence

The Emotional Impact score uses proxy metrics (energy contour variance,
crest factor as tension proxy, presence band energy ratio). These are NOT
subjective — they're measurable spectral/dynamic properties that correlate
with perceived emotional engagement.

### 4. The User Trust Layer

The trust layer is not code — it's the cumulative effect of:
- Explanations in plain language (not dB values)
- Restraint visibility ("I held back because...")
- Apply/Undo workflow (user always has final say)
- RAIN Score as a confidence metric
- Before/After comparison always available

---

## What's NOT in This Pipeline (Deliberate Exclusions)

1. **Audio generation** — RAIN does not generate music. Suno/Udio own that.
2. **Arrangement augmentation** — Adding instruments/vocals is a separate V3 system.
3. **Inference-time optimization loops** — We predict parameters, we don't iterate.
4. **Subjective quality judgment** — RAIN Score uses proxy metrics, not opinion.

---

## V1 Scope (Current)

- Intent Engine (keyword-based, local-only)
- RainNet heuristic fallback (deterministic)
- Prototype DSP (scipy/numpy)
- RAIN Score v2 (full breakdown)
- Local-first processing (WASM path)

## V2 Scope (Next)

- Intent Engine + Claude API integration
- RainNet trained model (EfficientNet-B2 + FiLM)
- RainDSP WASM engine (C++20, 64-bit double)
- Reference matching (artist style encoding)

## V3 Scope (Future)

- Arrangement Augmentation Module
- Full stem-aware processing (12-stem Demucs)
- Spatial rendering (Dolby Atmos)
- DAW plugin integration
