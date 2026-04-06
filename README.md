# R∞N — RAIN AI Mastering Engine

**Professional AI-powered audio mastering platform by [ARCOVEL Technologies International](mailto:engineering@arcovel.com)**

> *"Rain doesn't live in the cloud."*
> The render engine runs on your machine. Audio never leaves your device during processing.

---

## What is RAIN?

RAIN (R∞N) is a full-stack AI mastering platform that brings studio-grade audio mastering to independent artists and labels. It combines a local-first DSP engine with cloud-based AI inference, cryptographic provenance certificates, and direct streaming platform distribution — all in one product.

**Beyond LANDR. Beyond iZotope. Beyond anything that came before.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (React 19 + Vite 7)                                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Web Audio   │  │ ONNX Runtime │  │  RainDSP (C++/WASM)    │ │
│  │ API (route) │  │ Web (infer.) │  │  64-bit, deterministic  │ │
│  └─────────────┘  └──────────────┘  └────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │ API (FastAPI)
┌────────────────────────────▼────────────────────────────────────┐
│  Backend (Python 3.12 + FastAPI)                                │
│  ┌──────────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Master       │  │ QC Engine │  │ RAIN-CERT│  │ DDEX ERN │  │
│  │ Engine (DSP) │  │ 18 checks │  │ Ed25519  │  │ 4.3.2    │  │
│  └──────────────┘  └───────────┘  └──────────┘  └──────────┘  │
│  ┌──────────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Feature Ext. │  │ Heuristic │  │ LabelGrid│  │ Stripe   │  │
│  │ 43-dim vector│  │ Params    │  │ Distrib. │  │ Billing  │  │
│  └──────────────┘  └───────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
    PostgreSQL 18         Valkey 9.0           MinIO / S3
```

### Dual-Path Design

| Path | Engine | Precision | Purpose |
|---|---|---|---|
| **Preview** | Web Audio API | 32-bit float | Real-time monitoring, < 50ms latency |
| **Render** | RainDSP WASM | 64-bit double | Deterministic, authoritative output |

Same input + same params + same WASM binary = **bit-identical output**, every time.

---

## Features

### Core Mastering
- **7-stage DSP chain**: normalize → EQ → multiband compress → stereo widening → limiting → export
- **43-dimensional feature extraction** across 6 groups: Loudness (5), Dynamics (6), Spectral (16), Stereo (7), Transient (5), Tonal (4)
- **18 automated QC checks** with auto-remediation for critical issues
- **27 platform loudness targets**: Spotify −14 LUFS, Apple Music −16, Dolby Atmos −18, CD −9, vinyl, broadcast, podcast, and more
- **46-parameter ProcessingParams schema** — heuristic fallback when ML gate is closed

### Stem Mastering
- Demucs v4 `htdemucs_6s` — 6-stem separation (vocals, drums, bass, guitar, piano, other)
- Per-stem EQ (3-band), gain faders, solo/mute
- SAIL (Stem-Aware Intelligent Limiting) — `sail_stem_gains[6]` applied post-separation

### Provenance & Compliance
- **RAIN-CERT**: Ed25519-signed provenance certificates — input hash, output hash, WASM binary hash, processing params
- **C2PA v2.2**: CBOR-encoded Content Provenance manifests with AI disclosure assertions
- **DDEX ERN 4.3.2**: Full AI involvement disclosure (September 2025 standard)
- **EU AI Act Article 50**: Machine-readable AI marking, compliant before August 2, 2026 deadline

### Distribution
- Direct-to-DSP delivery via LabelGrid API
- ISRC generation (ISO 3901), UPC/EAN-13 with check digit
- Per-platform loudness targeting and codec-aware mastering
- 4-step distribution wizard: Platforms → Metadata → Review → Status

### Artist Identity Engine (AIE)
- 6-dimensional style fingerprint: Brightness, Warmth, Compression, Width, Low-end, Loudness
- Mastering history with approval feedback loop
- Style evolution charting across sessions
- Custom preference rules (JSON) that persist across sessions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19.2 · Vite 7.3 · TypeScript 5 · Tailwind 4.2 · Framer Motion 12 |
| State | Zustand 5 · TanStack Query 5 |
| Render Engine | RainDSP (C++20/WASM via Emscripten) |
| ML Inference | ONNX Runtime Web 1.24 (WebGPU → WASM fallback) |
| Backend API | FastAPI 0.109+ · Python 3.12 |
| Database | PostgreSQL 18 with RLS |
| Cache/Queue | Valkey 9.0 (BSD-3-Clause Redis fork) |
| Object Storage | S3-compatible (MinIO in dev) |
| Provenance | Ed25519 · C2PA v2.2 · CBOR (RFC 7049) |
| Distribution | DDEX ERN 4.3.2 · LabelGrid API |
| Billing | Stripe |
| Desktop | Tauri 2.0 (Studio Pro+) |
| DAW Plugin | JUCE 8 VST3/AU/AAX (Studio Pro+) |
| Analytics | PostHog (optional) |
| Observability | Prometheus · Grafana · structlog · Sentry |

---

## Pricing

| Tier | Price | Downloads | Key Features |
|---|---|---|---|
| **Free** | $0 | 0 (listen only) | WASM mastering, real-time preview, RAIN Score |
| **Spark** | $9/mo | 50 | Full resolution export, WAV/FLAC/MP3, Simple Mode |
| **Creator** | $29/mo | 10 renders | Stem separation, Claude AI (10/mo), Artist Identity Engine |
| **Artist** | $59/mo | 25 renders | DAW plugin, Distribution Intelligence, RAIN-CERT |
| **Studio Pro** | $149/mo | 75 renders | Dolby Atmos, DDEX/DDP, vinyl mastering, collaboration |
| **Enterprise** | Custom | Unlimited | Custom RainNet LoRA, white-label API, dedicated support |

Annual discount: ~20%. Contact: [engineering@arcovel.com](mailto:engineering@arcovel.com?subject=RAIN%20Enterprise%20Inquiry)

---

## Getting Started

### Prerequisites

- Docker Desktop 4.x+
- Node.js 20+
- Python 3.12+

### Prototype (Docker — fastest path)

```bash
git clone https://github.com/aurorav5/rain-blueprint.git
cd rain-blueprint
git checkout rain/full-upgrade

# Start the full stack (PostgreSQL 18 + Valkey 9 + backend + frontend)
docker compose -f docker-compose.prototype.yml up --build

# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Required for development (already defaulted in prototype)
RAIN_ENV=development
DATABASE_URL=postgresql+asyncpg://rain_app:rain_dev@localhost:5432/rain
REDIS_URL=redis://localhost:6379/0

# Required for production
JWT_SECRET_KEY=<openssl rand -hex 32>
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_SPARK_MONTHLY=price_...
STRIPE_PRICE_CREATOR_MONTHLY=price_...
STRIPE_PRICE_ARTIST_MONTHLY=price_...
STRIPE_PRICE_STUDIO_PRO_MONTHLY=price_...

# Optional
RAIN_CERT_SIGNING_KEY=<Ed25519 PEM from C2PA-recognized CA>
ANTHROPIC_API_KEY=sk-ant-...
VITE_POSTHOG_KEY=phc_...
```

---

## API Reference

Core endpoints (full docs at `/docs` when running):

```
POST   /api/v1/master/upload              Upload audio for mastering
GET    /api/v1/master/{id}/analysis       43-dim feature vector + loudness analysis
POST   /api/v1/master/{id}/process        Run full mastering chain
GET    /api/v1/master/{id}/download/wav   Download WAV 24-bit/48kHz
GET    /api/v1/master/{id}/download/mp3   Download MP3 320kbps/44.1kHz
GET    /api/v1/master/{id}/qc             18-check QC report
GET    /api/v1/master/{id}/cert           RAIN-CERT Ed25519 certificate
GET    /api/v1/master/{id}/c2pa           C2PA v2.2 manifest
GET    /api/v1/master/pubkey              Ed25519 public key for cert verification

GET    /api/v1/qc/platforms               27 platform loudness targets

POST   /api/v1/separate/upload            Queue stem separation
WS     /api/v1/separate/{id}/ws           WebSocket progress stream
GET    /api/v1/separate/{id}/stems        Get separated stem download URLs

POST   /api/v1/releases/                  Create DDEX ERN 4.3.2 release

POST   /api/v1/billing/checkout-session   Stripe checkout
GET    /api/v1/billing/subscription       Current tier/status
POST   /api/v1/billing/portal-session     Subscription management

POST   /api/v1/waitlist/join              Join beta waitlist
GET    /api/v1/waitlist/count             Total waitlist count
```

---

## Non-Negotiable Architecture Rules

These are immutable. See `CLAUDE.md` for the full specification.

1. **Local-First Processing** — RainDSP WASM is the only render engine. Audio never reaches S3 on the free path.
2. **Dual-Path Architecture** — Preview (Web Audio API, 32-bit) and Render (RainDSP, 64-bit) are always separate codepaths.
3. **Multi-Tenant Isolation** — Every DB query includes `WHERE user_id = $user_id`. RLS enabled on all tables.
4. **K-Weighting Sign Convention** — `y = b0·x + b1·x₁ + b2·x₂ − a1·y₁ − a2·y₂`. `a1` stored negative, subtracted.
5. **NORMALIZATION_VALIDATED Gate** — `RAIN_NORMALIZATION_VALIDATED=false` blocks RainNet inference. Heuristic fallback is mandatory.
6. **WASM Binary Integrity** — `rain_dsp_wasm_hash` verified at session start. Mismatch = `RAIN-E304`, render blocked.
7. **Free Tier — No S3** — Free renders in WASM, held in memory, discarded on session close. Never written to disk or S3.

---

## Project Structure

```
rain/
├── backend/                  FastAPI application
│   ├── app/
│   │   ├── api/routes/       API endpoints (auth, master, qc, billing, ...)
│   │   ├── core/             Config, database, security, observability
│   │   ├── models/           SQLAlchemy ORM models
│   │   ├── schemas/          Pydantic request/response schemas
│   │   └── services/         Business logic (DSP, QC, provenance, DDEX, ...)
│   └── tests/                pytest test suite
├── frontend/                 React SPA
│   └── src/
│       ├── components/       UI components (tabs, layout, controls, audio)
│       ├── stores/           Zustand stores (auth, session)
│       ├── utils/            API client, analytics, heuristic params
│       └── views/            Page-level views (AppLayout, LandingPage, Auth)
├── rain-dsp/                 C++20 DSP engine (WASM build)
├── ml/                       PyTorch training, ONNX export
├── docker/                   Dockerfiles (backend, frontend, worker)
├── monitoring/               Prometheus + Grafana config
└── docker-compose.yml        Full production stack
```

---

## Compliance

| Standard | Status |
|---|---|
| EU AI Act Article 50 (Aug 2, 2026) | ✅ C2PA v2.2 + DDEX AI disclosure in every export |
| DDEX ERN 4.3.2 | ✅ Full AI involvement fields per Sep 2025 standard |
| C2PA v2.2 | ✅ CBOR-encoded manifests, Ed25519 signed |
| ISO 3901 (ISRC) | ✅ Generated per standard |
| EBU R 128 / ITU-R BS.1770-4 | ✅ K-weighted LUFS targeting |
| AES17 True Peak | ✅ 4× oversampling limiter |

---

## License

Proprietary — © 2026 ARCOVEL Technologies International. All rights reserved.

Contact [engineering@arcovel.com](mailto:engineering@arcovel.com) for licensing inquiries.
