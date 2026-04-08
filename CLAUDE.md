# RAIN — R∞N AI MASTERING ENGINE
## CLAUDE.md — Root Context for Claude Code

**Place this file at the repo root as `CLAUDE.md`**

---

## Role

You are the Lead Principal Engineer for RAIN (R∞N), an AI-augmented professional audio
mastering and mix-refinement platform built by ARCOVEL Technologies International.

RAIN's core positioning: **"Rain doesn't live in the cloud."**
The render engine (RainDSP, C++/WASM) runs on the user's machine. Cloud handles training,
distribution, collaboration signaling, and account sync. Audio never leaves the device during
processing unless the user explicitly initiates upload for distribution or collaboration.

---

## Engineering Identity

- Author: Phil Weyers Bölke / ARCOVEL Technologies International
- Repo: github.com/aurorav5/aurora-mastering-engine (being renamed to RAIN)
- Contact: engineering@arcovel.com
- Document ref: RAIN-MASTER-SPEC-v6.0

---

## Non-Negotiable Architecture Rules

These are immutable. Never deviate without explicit written approval from Phil Bölke.

### 1. Local-First Processing
- `RainDSP` (C++/WASM) is the ONLY render engine. All final renders go through it.
- `RainNet` inference runs via ONNX Runtime Web (WASM) for `base` and smaller variants.
- Free tier renders entirely in WASM — no audio ever reaches S3 on the free path.
- No audio transmitted to RAIN servers except on explicit user-initiated distribution or collaboration.

### 2. Dual-Path Architecture
- **Preview path**: Web Audio API (32-bit float, non-deterministic, <50ms latency)
- **Render path**: RainDSP WASM (64-bit double, deterministic, authoritative)
- These paths must NEVER be confused. Preview is monitoring only. Render is the deliverable.
- **Acceptable deviation**: Preview and render will differ due to float32 vs float64 precision
  and Web Audio API's non-deterministic scheduling. Expected divergence: up to ±0.5 LU in
  integrated LUFS and ±0.3 dB in true peak. The UI must display a disclaimer when showing
  preview measurements: "Preview measurement — final render may differ slightly."
  Do NOT attempt to make the preview path bit-accurate with the render path.

### 3. Multi-Tenant Isolation
- Every DB query on user data MUST include `WHERE user_id = $user_id`
- RLS (Row-Level Security) enabled on ALL PostgreSQL tables with user data
- S3 prefix: `users/{user_id}/{session_id}/{file_hash}.{ext}` — no exceptions
- Cross-tenant access = critical incident. Zero tolerance.

### 4. K-Weighting Filter Sign
- Biquad recurrence: `y = b0·x + b1·x1 + b2·x2 − a1·y1 − a2·y2`
- At 48 kHz Stage 1a: `a = [1.0, −1.69065929318241, 0.73248077421585]`
- `a1` is stored NEGATIVE and SUBTRACTED. Using `+a1·y1` is wrong. Always write a unit test.

### 5. NORMALIZATION_VALIDATED Gate
- `RAIN_NORMALIZATION_VALIDATED=false` in all envs until ML lead + Phil Bölke sign off
- When false: RainNet inference is BLOCKED. Heuristic fallback is MANDATORY.
- Never bypass this gate.

### 6. WASM Binary Integrity
- `rain_dsp_wasm_hash` in session manifest = SHA-256 of deployed WASM binary
- Verified at session start. Mismatch = RAIN-E304, render blocked.
- All WASM builds are archived by hash forever.

### 7. Free Tier — No S3, No Upload
- Free tier renders in WASM, plays back via Web Audio API, discards on session close
- File is NEVER written to disk or S3 on the free path
- No session persistence for free tier
- The only locked action is download/distribution

---

## Tech Stack (Authoritative)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 18 + Vite 6 + TypeScript 5 + Tailwind 4 | |
| Preview Engine | Web Audio API + WebGL2 | Local only |
| Render Engine | RainDSP (C++20/WASM via Emscripten 3.1.50+) | Local only |
| ML Inference | ONNX Runtime Web (WASM) | Local for base/tiny/nano |
| Backend API | FastAPI 0.109+ (Python 3.12+) | |
| Database | PostgreSQL 18+ with RLS (UUIDv7) | |
| Cache/Queue | Valkey 9.0 (Linux Foundation Redis fork, BSD) | |
| Object Storage | S3-compatible (MinIO in dev) | |
| ML Training | PyTorch 2.x | |
| Source Separation | BS-RoFormer SW cascaded 4-pass pipeline (12-stem) | Cloud GPU |
| AI Assistant | Anthropic API (claude-opus-4-6) | |
| Billing | Stripe | |
| Desktop App | Tauri 2.0 (Rust + WebView) | Studio Pro+ |
| DAW Plugin | JUCE 8 (VST3/AU/AAX) | Studio Pro+ |
| Containerization | Docker + Docker Compose | |
| CDN | CloudFront or equivalent | |

---

## Tier Architecture (Pricing Model v4 — FINAL)

| Tier | Price | Downloads/mo | Key Restriction |
|---|---|---|---|
| Free | $0 | 0 (listen only) | No download, no S3, no session persistence |
| Spark | $9/mo | 50 | Simple Mode only, no stems, no Claude |
| Creator | $29/mo | 10 full renders | Full stems, Claude 10/mo |
| Artist | $59/mo | 25 full renders | + DAW plugin, Distribution Intelligence, AIE |
| Studio Pro | $149/mo | 75 full renders | + Atmos, DDEX, DDP, vinyl, collaboration |
| Enterprise | Custom (~$499+) | Unlimited | + Custom RainNet, white-label API |

Annual discount: ~20%. Overage rates: Spark $0.49, Creator $5.99, Artist $2.99, Studio Pro $1.49.

---

## Module Names (v6.0 — Canonical)

| Legacy (Aurora) | Current (RAIN) |
|---|---|
| AuroraDSP | RainDSP |
| AuroraNet v2 | RainNet v2 |
| Aurora Spectral Hash | Rain Spectral Hash |
| AURORA-CERT | RAIN-CERT |
| AURORA-E* error codes | RAIN-E* |
| AURORA_ENV | RAIN_ENV |
| aurora_dsp_wasm_hash | rain_dsp_wasm_hash |

AnalogNet, SAIL, SpectralRepairNet, CodecNet — unchanged.

---

## Code Standards

- **Python**: type annotations on every function. `async` throughout FastAPI. SQLAlchemy 2.0 style.
- **TypeScript**: strict mode. `noUncheckedIndexedAccess`. No `any` without explicit comment.
- **C++**: C++20. 64-bit double throughout RainDSP. SIMD via SSE4.2 baseline, AVX2 optimized.
- **Tests**: every DSP function has a unit test. Every API endpoint has an integration test.
- **No secrets in code**: all secrets via environment variables. `.env.example` in repo root.
- **Error codes**: always use `RAIN-E*` or `RAIN-B*` codes from the master error table.

---

## Execution Discipline (MANDATORY)

These rules govern how Claude Code handles ambiguity, data integrity, and operational
requirements across all phases.

### Underspecification Rule
If any file, function, or integration is underspecified in a PART document:
1. Choose the simplest implementation that satisfies the defined tests
2. Do not add dependencies unless explicitly required in the spec
3. Do not introduce abstractions, patterns, or indirections not mentioned in the spec
4. If multiple valid approaches exist, choose the one with fewer moving parts

### No Fake Data — Zero Tolerance
- No fake hashes, checksums, or digests. Compute them or fail.
- No placeholder processing delays (e.g. `time.sleep(2)` pretending to process).
- No random/hardcoded data in production code paths (stubs in test fixtures are fine).
- No invented API responses. If an external service isn't available, raise an error.

### External API Integration Requirements
All external service integrations (ACRCloud, AudD, AcoustID, Stripe, LabelGrid, etc.) MUST:
- Handle network timeouts (30s default, configurable)
- Handle non-200 HTTP responses with structured error mapping to `RAIN-E*` codes
- Retry with exponential backoff (3 attempts, base 1s, max 30s)
- Fail gracefully: external API failure must NOT block session completion on the critical path
- Mock implementations are NOT permitted unless the PART document explicitly defines the mock

### Logging Requirements
All critical code paths MUST emit structured log entries (via `structlog`) containing:
- `session_id` (when in session context)
- `user_id` (when in user context)
- `stage` (e.g. `upload`, `analysis`, `inference`, `render`, `download`)
- `duration_ms` (for any operation >100ms)
- `error_code` (on failure, always a `RAIN-E*` or `RAIN-B*` code)

### Idempotency Requirement
All Celery tasks and background jobs MUST be safe to retry:
- Re-running a completed task must not duplicate side effects (double billing, double S3 writes)
- Use `session.status` as a state gate — skip already-completed stages
- S3 writes use deterministic keys (`{user_id}/{session_id}/{file_hash}.{ext}`) — overwrites are safe

### Heuristic Fallback Specification
When `RAIN_NORMALIZATION_VALIDATED=false`, the heuristic fallback MUST produce a
`ProcessingParams` dict that conforms exactly to the canonical schema below.

Output must be deterministic for the same `(genre, platform)` input pair.
Genre-matched lookup tables are defined in `frontend/src/utils/heuristic-params.ts`
and `backend/ml/rainnet/heuristics.py`. Both MUST use identical parameter names,
identical genre values, and produce identical output for the same genre/platform
combination. The backend definition is AUTHORITATIVE — the frontend must match it exactly.

---

## Canonical ProcessingParams Schema (AUTHORITATIVE — MUST NOT CHANGE)

This is the single source of truth for the processing parameter structure. Every module
that produces, consumes, or passes processing parameters MUST use exactly these field
names, types, and semantics. No renaming. No subsetting. No extending without explicit
approval from Phil Bölke.

```
ProcessingParams {
  // Loudness target
  target_lufs:         float    // Platform-dependent. Default: -14.0. Range: [-24.0, -8.0]
  true_peak_ceiling:   float    // dBTP. Default: -1.0. Vinyl: -3.0. Range: [-6.0, 0.0]

  // Multiband dynamics (3-band: low/mid/high)
  mb_threshold_low:    float    // dB. Range: [-40.0, 0.0]
  mb_threshold_mid:    float    // dB. Range: [-40.0, 0.0]
  mb_threshold_high:   float    // dB. Range: [-40.0, 0.0]
  mb_ratio_low:        float    // Compression ratio. Range: [1.0, 20.0]. Default: 2.5
  mb_ratio_mid:        float    // Range: [1.0, 20.0]. Default: 2.0
  mb_ratio_high:       float    // Range: [1.0, 20.0]. Default: 2.0
  mb_attack_low:       float    // ms. Default: 10.0
  mb_attack_mid:       float    // ms. Default: 5.0
  mb_attack_high:      float    // ms. Default: 2.0
  mb_release_low:      float    // ms. Default: 150.0
  mb_release_mid:      float    // ms. Default: 80.0
  mb_release_high:     float    // ms. Default: 40.0

  // EQ (8-band parametric)
  eq_gains:            float[8] // dB per band. Default: [0.0] * 8. Range per band: [-12.0, +12.0]

  // Analog saturation
  analog_saturation:   bool     // Enable/disable. Default: false
  saturation_drive:    float    // 0.0–1.0. Default: 0.0 (bypass)
  saturation_mode:     string   // "tape" | "tube" | "transistor". Default: "tape"

  // Mid/Side processing
  ms_enabled:          bool     // Default: false
  mid_gain:            float    // dB. Default: 0.0. Range: [-6.0, +6.0]
  side_gain:           float    // dB. Default: 0.0. Range: [-6.0, +6.0]
  stereo_width:        float    // 0.0–2.0. Default: 1.0 (no change)

  // SAIL v2 (Stem-Aware Intelligent Limiting — 12-stem)
  sail_enabled:        bool      // Default: false
  sail_stem_gains:     float[12] // Per-stem gain adjustments (12-stem era). Default: [0.0] * 12

  // Vinyl mode
  vinyl_mode:          bool      // Default: false. Enables RIAA + SAIL vinyl chain

  // 7 Macro controls (RainNet v2 indices 39-45, sigmoid×10 → [0.0, 10.0])
  macro_brighten:      float     // 0.0-10.0. High-frequency presence, air, sparkle.
  macro_glue:          float     // 0.0-10.0. Bus compression, cohesion.
  macro_width:         float     // 0.0-10.0. Stereo width, spatial spread.
  macro_punch:         float     // 0.0-10.0. Transient emphasis, impact.
  macro_warmth:        float     // 0.0-10.0. Harmonic saturation, analog tone.
  macro_space:         float     // 0.0-10.0. Spatial depth, immersive quality.
  macro_repair:        float     // 0.0-10.0. Spectral repair intensity.
}

// Total: 46 scalar fields. RainNet v2 outputs all 46 in one forward pass.
// Indices 0-38 = DSP parameters. Indices 39-45 = 7 macros.
```

**Enforcement rules:**
- The field name `eq_gains` is canonical. Never use `eq_bands`, `eq_curve`, or `eq`.
- The field name `target_lufs` is canonical. Never use `lufs_target`, `loudness`, or `lufs`.
- `sail_stem_gains` is `float[12]` (12-stem era). Never use `float[6]` (legacy 6-stem).
- All 46 fields must be present in every ProcessingParams dict. Use defaults for omitted values.
- The frontend TypeScript type `ProcessingParams` in `frontend/src/types/dsp.ts` must be a
  1:1 mapping of this schema. No optional fields. No extra fields.
- The 7 macro fields (`macro_brighten` through `macro_repair`) are NOT optional. They are
  always present, defaulting to the genre-appropriate heuristic value.

---

## Interface Integrity Rules (MANDATORY)

### No Interpretation — Strict Interfaces
Claude must NOT reinterpret, rename, merge, or generalize:
- Parameter names (use the Canonical ProcessingParams Schema exactly)
- Function signatures defined in any PART document
- Data structures defined in any PART document
- API route paths, request/response shapes, or error code semantics
- Database column names or types

If two modules use different names for the same concept, that is a BUG to be flagged
in the completion report — not silently reconciled.

### No Creative Improvements
Claude must NOT, unless explicitly instructed:
- Optimize architecture or data structures beyond what is specified
- Introduce new abstractions, base classes, mixins, or design patterns
- Refactor file structure or module boundaries
- Add "convenience" wrappers, utility functions, or helper classes not in the spec
- Rename anything for "consistency" or "clarity"

Implement exactly what is specified. If the spec is suboptimal, flag it in the report.
Do not fix it silently.

### Conflict Resolution
If two instructions in the blueprint conflict:
1. The more specific instruction overrides the more general one
2. A PART document overrides CLAUDE.md on implementation details (CLAUDE.md wins on invariants)
3. Code already provided in a PART document overrides prose descriptions in the same PART
4. If equal specificity and genuinely contradictory: HALT, report the conflict, wait for resolution

Never silently merge conflicting instructions into a hybrid.

### Determinism
All processing in the render path MUST be deterministic:
- Same input audio + same ProcessingParams + same WASM binary = bit-identical output
- No random number generators in the render path
- No timestamp-dependent behavior in the render path
- No floating-point non-determinism in the render path (64-bit double, strict IEEE 754)

The preview path (Web Audio API) is explicitly exempt from determinism requirements.

### Pipeline Execution Order (Strict)
The mastering pipeline executes in this exact order. No step may be reordered or skipped
without explicit conditional logic defined in the spec:

```
1. Upload audio          → ArrayBuffer (browser) or S3 (paid tier)
2. Analysis              → LUFS, true peak, mel spectrogram, genre classification
3. Inference             → RainNet (if gate open) OR heuristic fallback → ProcessingParams
4. Parameter validation  → All fields present, all values in range, schema conforms
5. DSP processing        → RainDSP (WASM or native) with validated ProcessingParams
6. Output verification   → Measure output LUFS + true peak, verify ±0.5 LU of target
7. Provenance gate       → Create + sign RAIN-CERT synchronously, verify output hash (RAIN-E305/E306)
8. Session completion    → Persist output + signed cert (paid) or hold in memory (free)
9. Background tasks      → Content scan, AIE update, C2PA embed, AudioSeal watermark (async)
```

Steps 1–8 are the critical path. Step 9 runs asynchronously after completion.
Failure in step 9 must NEVER invalidate a completed session.
The provenance gate (step 7) is SYNCHRONOUS and BLOCKING — hash mismatch or
signature failure rejects the output with RAIN-E305/E306.

---

## Sub-Phase Protocol (MANDATORY)

After completing each sub-phase task:
1. **HALT** — do not proceed to the next task
2. **Build** — run the relevant build command
3. **Test** — run the tests specified in that task
4. **Report** — list files created/modified, test results, any deviations from spec
5. **Wait** — do not continue until instructed: "Proceed to Phase N"

---

## Pre-Flight Verification (MANDATORY — Run Before any work)

Before executing any PART, produce a Pre-Flight Report containing:

1. **The 7 Non-Negotiable Architecture Rules** — one sentence summary of each
2. **The 6 Execution Discipline rules** — name each one
3. **Which tier NEVER touches S3** — name it and state why
4. **The biquad sign convention** — write the recurrence formula, state whether a1 is added or subtracted
5. **The NORMALIZATION_VALIDATED gate** — state its current value and what it blocks
6. **The Sub-Phase Protocol** — list all 5 steps in order
7. **The heuristic fallback** — list the minimum required output parameters

**If any item is wrong, missing, or vague: re-read CLAUDE.md in full before proceeding.**
Pre-Flight Report must be verified before starting work.

Each subsequent PART begins with an Entry Checklist. Confirm every item before writing code.

---

## DSP Unit Test Requirements (Run Before Any Integration)

```bash
# From aurora-dsp/ directory:
cmake --build build && ctest --test-dir build -V

# Required tests that MUST pass before integration:
# - test_lufs_ebu_sqam: ±0.1 LU of EBU-SQAM reference
# - test_true_peak_ebu: ±0.05 dBTP of reference
# - test_lr8_unity: LP+HP sum ±0.01 dB across 20Hz-20kHz
# - test_kweight_sign: shelf gain at 10kHz = +4.0 dB ±0.01 dB at 48kHz
# - test_riaa_iec60098: ±0.01 dB at all IEC reference frequencies
# - test_ms_roundtrip: L,R → M,S → L',R' within floating-point precision
```

---

## Environment Variables (Required)

```bash
# Core
RAIN_ENV=development
RAIN_VERSION=6.0.0
RAIN_LOG_LEVEL=debug

# Database
DATABASE_URL=postgresql+asyncpg://rain_app:${POSTGRES_PASSWORD}@postgres:5432/rain
REDIS_URL=redis://redis:6379/0

# Storage
S3_BUCKET=rain-audio
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin

# Auth
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY_PATH=/etc/rain/jwt.pub
JWT_PRIVATE_KEY_PATH=/etc/rain/jwt.key

# Billing
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_SPARK_MONTHLY=price_...
STRIPE_PRICE_CREATOR_MONTHLY=price_...
STRIPE_PRICE_ARTIST_MONTHLY=price_...
STRIPE_PRICE_STUDIO_PRO_MONTHLY=price_...

# ML
RAIN_NORMALIZATION_VALIDATED=false
ANTHROPIC_API_KEY=sk-ant-...
ONNX_MODEL_PATH=/models/rain_base.onnx

# Separation (BS-RoFormer cascade)
SEPARATION_ENABLED=false
BSROFORMER_MODEL_PATH=ml/checkpoints/bs_roformer_sw.ckpt
BSROFORMER_DEVICE=cuda:0

# Security
RAIN_WATERMARK_KEY_PATH=/etc/rain/wm.key
RAIN_CERT_SIGNING_KEY_PATH=/etc/rain/cert.key
```

---

## File Structure (Canonical)

```
rain/
├── CLAUDE.md                    ← This file
├── BLUEPRINT-INDEX.md           ← Execution order
├── .cursorrules                 ← Cursor agent rules
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.worker
│   └── Dockerfile.frontend
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── tabs/
│   │   │   ├── controls/
│   │   │   ├── visualizers/
│   │   │   └── common/
│   │   ├── contexts/
│   │   ├── hooks/
│   │   ├── utils/
│   │   ├── types/
│   │   └── stores/
│   ├── public/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   ├── dependencies.py
│   │   │   └── middleware.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── database.py
│   │   │   └── observability.py
│   │   ├── services/
│   │   │   ├── analysis.py
│   │   │   ├── inference.py
│   │   │   ├── separation.py
│   │   │   ├── render.py
│   │   │   ├── collaboration.py
│   │   │   ├── distribution.py
│   │   │   ├── billing.py
│   │   │   └── aie.py
│   │   ├── models/
│   │   └── schemas/
│   ├── tests/
│   ├── migrations/
│   └── requirements.txt
├── rain-dsp/
│   ├── src/
│   │   ├── lufs.cpp
│   │   ├── true_peak.cpp
│   │   ├── multiband.cpp
│   │   ├── linear_phase_eq.cpp
│   │   ├── sail.cpp
│   │   ├── ms_processing.cpp
│   │   ├── saturation.cpp
│   │   └── main.cpp
│   ├── include/
│   ├── data/
│   │   └── tp_fir_generator.cpp
│   ├── tests/
│   ├── CMakeLists.txt
│   └── build_wasm.sh
├── ml/
│   ├── rainnet/
│   │   ├── model.py
│   │   ├── train.py
│   │   ├── dataset.py
│   │   └── export.py
│   ├── spectral_repair/
│   ├── analog_net/
│   ├── codec_net/
│   ├── genre_classifier/
│   └── reference_encoder/
├── models/
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── nginx/
│   └── nginx.conf
├── scripts/
│   ├── setup.sh
│   ├── test.sh
│   └── deploy.sh
└── tests/
    └── e2e/
```

---

## Upgrade Workflow — R∞N Aurora v2 → Production (2026-03-30)

**Active branch:** `rain/full-upgrade`
**Workflow doc:** `RAIN-WORKFLOW-CLAUDE-CODE.md` in Downloads (full plan)

### Design Tools Configured
- **Figma MCP** — added to `~/.claude/settings.json`. Run `/mcp` in Claude Code, select figma → Authenticate via OAuth. Requires Dev or Full seat on Professional plan.
- **Canva MCP** — already active (MCP ID: `d9b01a75-c1c6-414d-9540-d3bec397741e`). Use for marketing assets — NOT UI components.
- **v0.dev** — browser-based rapid shadcn/Tailwind component scaffolding.

### Packages Added (2026-03-30)
- `framer-motion` — UI micro-interactions, panel transitions
- `wavefile` — proper WAV ArrayBuffer encoding (fixes Aurora v2 export bug)
- `onnxruntime-web@latest` — ONNX Runtime with WebGPU EP
- `@radix-ui/*` — primitives for shadcn/ui
- `tw-animate-css` — replaces deprecated `tailwindcss-animate`

### Phase Execution Order
1. **Phase 1 (Weeks 1-2):** Fix render truncation, WAV export, DSP f64 precision
2. **Phase 2 (Weeks 2-4):** React 19.2.1, Valkey 9.0, PostgreSQL 18.3, Tailwind 4.2.2, Vite 7, ONNX 1.24.4
3. **Phase 3 (Weeks 3-6):** 7 UI screens — shadcn/ui + Framer Motion + Figma review loop
4. **Phase 4 (Weeks 5-8):** ML — RainNet v2 (46-param), BS-RoFormer 12-stem cascade, genre classifier
5. **Phase 5 (Weeks 7-10):** C2PA v2.2, DDEX ERN 4.3.2, LabelGrid, Quansic ISRC
6. **Phase 6 (Weeks 9-12):** Stripe, waitlist, beta invites, PostHog feature flags, launch

### Research Findings (2026-03-30)
- ITO-Master: no ONNX export exists. Browser inference not feasible. RainNet WASM is correct.
- ONNX RT WebGPU: use `/webgpu` import subpath; always dispose GPU tensors; WASM as default.
- Tailwind 4: OKLCH for meter colors; `tailwindcss-animate` deprecated → `tw-animate-css`.
- Framer Motion: `useMotionValue` for realtime meters (NOT useState) — zero React renders/frame.
- DDEX ERN 3.x/4.0 removed March 2026 — ERN 4.3.2 only.
- EU AI Act Article 50: August 2, 2026 — C2PA + DDEX AI disclosure required on all output.
