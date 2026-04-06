# RAIN Schema Naming Conventions

**Document ID:** RAIN-SCHEMA-NAMING-v1.0
**Date:** 1 April 2026

---

## Three Naming Conventions

RAIN uses three distinct parameter naming conventions across different layers:

### 1. Canonical ProcessingParams (Production DSP)

**Location:** `CLAUDE.md`, `frontend/src/types/dsp.ts`, `backend/app/services/heuristic_params.py`

27 canonical fields mapping 1:1 to RainDSP WASM engine parameters. Frozen schema.

Key names: `target_lufs`, `eq_gains` (float[8]), `sail_stem_gains` (float[6]), `saturation_mode` ("tape"|"tube"|"transistor")

### 2. Creative Macros (Frontend UI)

**Location:** `frontend/src/stores/session.ts` (MacroValues), `CreativeMacros.tsx`

7 user-facing controls:

| Macro | Range | Maps to |
|-------|-------|---------|
| `brighten` | 0-10 | HF presence, air |
| `glue` | 0-10 | Bus compression |
| `width` | 0-10 | Stereo width |
| `punch` | 0-10 | Transient emphasis |
| `warmth` | 0-10 | Analog saturation |
| `space` | 0-10 | Spatial depth |
| `repair` | 0-10 | Spectral repair |

### 3. Prototype MasteringParams (Python DSP)

**Location:** `backend/app/services/master_engine.py`

7 prototype controls: `brightness`, `tightness`, `width`, `loudness`, `warmth`, `punch`, `air`

These map approximately to Creative Macros but with different names (historical).

## Migration Path

When RainDSP WASM replaces the prototype scipy engine:
1. **Creative Macros** stay (user-facing)
2. **ProcessingParams** stay (DSP-facing)
3. **MasteringParams** retire — replaced by macro->ProcessingParams mapping via RainNet/heuristic
