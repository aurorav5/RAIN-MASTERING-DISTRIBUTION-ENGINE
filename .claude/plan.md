# RAIN Platform Spec v1.0 — Implementation Plan

## Source: RAIN-PLATFORM-SPEC-v1.0.docx (31 March 2026)

This plan implements the **RAIN Platform Spec v1.0** against the current `rain/full-upgrade` branch. The prototype mastering engine (Phase 1-5 from previous session) is already working. This plan addresses the **gaps between the spec and what's built**.

---

## What Already Exists (from prototype build + 12 PARTs)

| Area | Status | Notes |
|------|--------|-------|
| FastAPI backend with 13 routers | ✅ Built | Auth, upload, sessions, billing, AIE, distribution, score, etc. |
| Python mastering engine (7-stage) | ✅ Built | EQ, multiband comp, stereo widening, limiter, LUFS targeting |
| Metadata engine (strip/rewrite) | ✅ Built | ID3v2.4 MP3, BWF WAV, zero residual tags |
| Master API routes (upload/process/download) | ✅ Built | 4 endpoints, in-memory session store |
| React frontend (14 tabs) | ✅ Built | MasteringTab wired to real backend, all tabs interactive |
| RainDSP C++ engine (blueprint) | ✅ Committed | PART-2/3 code in rain-dsp/ |
| RainNet v2 model definition | ✅ Committed | PART-4 code in ml/ |
| RAIN-CERT Ed25519 | ✅ Committed | PART-8 |
| DDEX ERN 4.3 + LabelGrid | ✅ Committed | PART-9 |
| Tauri desktop + JUCE plugin | ✅ Committed | PART-11 |
| Docker + Prometheus + E2E tests | ✅ Committed | PART-12 |

## What the Platform Spec Requires That's Missing

### Critical Gaps (Must Build)

1. **16-Stage Mastering Chain** — Current prototype has 7 stages. Spec defines 16 stages including: format normalization, provenance record, feature extraction (43-dim vector), AI inference, reference matching, spectral repair, source separation, per-stem repair, per-stem processing, master bus, loudness targeting, spatial rendering, QC validation (18 checks), forensics (watermark), and output (8 export variants).

2. **43-Dimensional Feature Vector** — Spec requires: Loudness (5), Dynamics (6), Spectral (16), Stereo (7), Transient (5), Tonal (4). Current analysis only measures ~6 features.

3. **18 QC Automated Checks** — Spec defines clipping detection, ISP detection, phase cancellation, codec pre-ringing, pops/clicks, bad edits, DC offset, silence trim, sample rate mismatch, bit depth truncation, loudness compliance, true peak ceiling, LRA compliance, mono compatibility, sibilance, rumble, stereo balance, and PEAQ.

4. **6-Band Multiband Compression** — Spec defines Linkwitz-Riley 8th-order crossovers at 40, 160, 600, 2500, 8000 Hz. Current prototype uses 3-band at 200, 4000 Hz.

5. **SAIL Limiter** — Stem-Aware Intelligent Limiter with per-stem priority weighting (float[6]) and selective gain reduction. Not implemented in prototype.

6. **27 Platform Loudness Targets** — Spec lists Spotify, Apple Music, Dolby Atmos, YouTube, Tidal, CD, Broadcast, Vinyl, Audiobook. Current prototype targets one LUFS value.

7. **Heuristic Fallback (ProcessingParams)** — Must produce the canonical 46-parameter ProcessingParams dict deterministically from (genre, platform) pairs.

8. **C2PA v2.2 Provenance** — Required for EU AI Act Article 50 (August 2, 2026 deadline). Not implemented.

9. **7 User Tiers** — Spec defines Casual, Creator, Independent Artist, Producer, Studio, Label/Distributor, Enterprise. Current code has 6 tiers (free, spark, creator, artist, studio_pro, enterprise).

### High-Priority Gaps

10. **Feature Extraction Service** — 43-dim vector needed for RainNet inference input
11. **Platform-Specific Export Variants** — 8 output types (streaming, hi-res, Atmos, vinyl, DDP, binaural, podcast, developer)
12. **10 Non-Negotiable Rules Enforcement** — sail_stem_gains[6] fencepost fix, K-weight sign test, WASM hash verification
13. **BS-RoFormer Separation Pipeline** — 12-stem cascaded pipeline (server-side GPU)
14. **EmotionNet Integration** — Valence/arousal prediction, tension arc modeling
15. **AnalogNet Hardware Emulation** — 16 WaveNet TCN models

---

## Implementation Order (6 Batches)

### Batch 1: Upgrade Mastering Engine to 16-Stage Spec (THIS SESSION)
**Files:** `backend/app/services/master_engine.py`, new `backend/app/services/feature_extraction.py`, new `backend/app/services/qc_engine.py`

- Expand from 7 to 16 stages in master_engine.py
- Implement 43-dimensional feature extraction
- Implement 18 QC automated checks
- Upgrade to 6-band multiband compression (LR8 crossovers at 40/160/600/2500/8000 Hz)
- Add SAIL limiter with stem priority weighting
- Add 27 platform loudness targets
- Add all 8 export format variants (streaming MP3, hi-res WAV, vinyl pre-master, etc.)

### Batch 2: Heuristic Fallback + ProcessingParams Schema
**Files:** `backend/app/services/heuristic_params.py`, `backend/app/schemas/processing_params.py`

- Implement canonical 46-parameter ProcessingParams schema
- Genre × Platform lookup tables (deterministic)
- Validate against CLAUDE.md schema exactly
- Ensure frontend TypeScript type matches 1:1

### Batch 3: QC Engine + Platform Compliance
**Files:** `backend/app/services/qc_engine.py`, `backend/app/api/routes/qc.py`

- All 18 automated QC checks
- Auto-remediation for critical checks (clipping, ISP, loudness, true peak)
- Advisory checks (PEAQ ODG)
- QC report generation

### Batch 4: Provenance Chain (RAIN-CERT + C2PA)
**Files:** `backend/app/services/provenance.py`, update `metadata_engine.py`

- Ed25519 signing at each processing step
- C2PA v2.2 manifest generation (CBOR-encoded)
- Hash chain from upload through every transformation
- EU AI Act Article 50 compliance metadata

### Batch 5: Frontend — Full Spec Compliance
**Files:** Multiple frontend components

- Wire QC tab to real 18-check results
- Wire Export tab to 8 format variants
- Add platform loudness target selector (27 platforms)
- Add 43-dimension analysis display
- Update tier system to 7 tiers per spec

### Batch 6: Infrastructure Fixes + Non-Negotiable Rules
**Files:** Multiple backend/frontend

- Fix sail_stem_gains fencepost (range(5) → range(6))
- Add K-weight sign convention unit test
- Add WASM hash verification test
- Verify ProcessingParams schema compliance everywhere
- Ensure no fake data in production paths

---

## Files to Create/Modify

### New Files
- `backend/app/services/feature_extraction.py` — 43-dim feature vector
- `backend/app/services/qc_engine.py` — 18 automated QC checks
- `backend/app/services/heuristic_params.py` — Canonical ProcessingParams + genre/platform lookup
- `backend/app/services/provenance.py` — RAIN-CERT + C2PA
- `backend/app/services/platform_targets.py` — 27 platform loudness targets
- `backend/app/api/routes/qc.py` — QC API endpoints
- `backend/app/schemas/processing_params.py` — Pydantic schema for 46-param ProcessingParams
- `backend/tests/test_kweight_sign.py` — K-weight biquad sign convention test
- `backend/tests/test_sail_stem_gains.py` — sail_stem_gains[6] test
- `backend/tests/test_qc_checks.py` — QC engine tests

### Modified Files
- `backend/app/services/master_engine.py` — Expand to 16 stages
- `backend/app/services/metadata_engine.py` — Add C2PA manifests
- `backend/app/api/routes/master.py` — Add QC results, platform targets, export variants
- `backend/app/main.py` — Add QC router
- `frontend/src/utils/api.ts` — Add QC and platform target endpoints
- `frontend/src/components/tabs/QCTab.tsx` — Wire to real 18-check data
- `frontend/src/components/tabs/ExportTab.tsx` — Wire to 8 format variants
- `frontend/src/types/dsp.ts` — Update ProcessingParams to 46 fields

## Execution starts with Batch 1.
