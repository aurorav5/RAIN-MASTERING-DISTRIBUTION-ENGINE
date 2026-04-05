# ADR-0009: Canonical ProcessingParams Schema

## Status
Accepted

## Context
RAIN's `ProcessingParams` structure is the sole interface between three independently-implemented systems:

1. **RainNet** (Python / PyTorch / ONNX) — predicts ProcessingParams from audio features.
2. **Backend API** (Python / FastAPI) — validates, persists, and routes ProcessingParams.
3. **RainDSP** (C++ / WASM) — consumes ProcessingParams to execute the actual DSP chain.

These three systems are written in three different languages, built with three different toolchains, and deployed independently. A single renamed field — `eq_gains` vs `eq_bands`, `target_lufs` vs `lufs_target` — silently breaks the audio pipeline at runtime, because JSON deserialization either produces a default value or raises an error that surfaces only after the render has been attempted.

The canonical schema is defined verbatim in `CLAUDE.md` (root). It specifies every field, type, range, default, and naming convention.

## Decision
The `ProcessingParams` schema is AUTHORITATIVE and IMMUTABLE. Every module that produces, consumes, or passes ProcessingParams MUST use the exact field names, types, and semantics defined in CLAUDE.md. Specifically:

- Field names are frozen. `eq_gains` is canonical — never `eq_bands`, `eq_curve`, or `eq`. `target_lufs` is canonical — never `lufs_target`, `loudness`, or `lufs`.
- All fields must be present in every ProcessingParams dict. No optional fields. No extra fields.
- The frontend TypeScript type `ProcessingParams` in `frontend/src/types/dsp.ts` is a 1:1 mapping of the canonical schema.
- The backend Pydantic model and the C++ struct follow the same 1:1 mapping.
- TypeScript-to-Python type parity is maintained via `openapi-typescript` code generation from the FastAPI OpenAPI schema. Drift between generated types and hand-written types is a build-break.
- Changes to the schema require explicit written approval from Phil Bölke and a coordinated three-way update (frontend + backend + WASM).

## Consequences

**Positive:**
- Eliminates an entire class of runtime bugs: silent key-rename mismatches between systems.
- Enables mechanical code-gen: the OpenAPI schema drives the TypeScript types, and the Python Pydantic model is the source of truth.
- Clear blame line when a bug is found: whichever module deviates from the canonical schema is wrong.
- Simplifies onboarding: new contributors have one document to read (CLAUDE.md) to understand the DSP contract.

**Negative:**
- Schema evolution is slow and coordinated, not unilateral. A new DSP feature requires changes in three codebases in lockstep.
- Field naming debates are frozen: even "better" names cannot be adopted without breaking the contract.
- Strict 1:1 mapping prohibits convenience aliases or language-idiomatic renames that would otherwise be natural (e.g., Python's `snake_case` vs TypeScript's `camelCase` is ignored — everything is snake_case).

**Neutral:**
- Forces a discipline: every PR that touches DSP params is cross-system by definition.
- Makes the schema document a top-tier artifact rather than incidental glue.

## Alternatives Considered

1. **Flexible schema with per-module adapters.** Rejected. Adapters become a dumping ground for silent semantic drift. Every adapter is a place where `eq_gains` can quietly become `eqGains` or `eq_curve`.
2. **Versioned schemas (v1, v2, v3).** Rejected for now. Versioning adds runtime complexity (which version does this session use?) for no current benefit. Can be adopted later if the schema needs a genuine breaking change.
3. **Free-form dict (unstructured JSON).** Rejected. Every consumer would have to hand-roll validation, multiplying the bug surface.
4. **Protobuf / FlatBuffers as canonical source.** Considered. Strong schema enforcement but adds a codegen toolchain across three languages. TypeScript-from-OpenAPI is lighter-weight and sufficient.
