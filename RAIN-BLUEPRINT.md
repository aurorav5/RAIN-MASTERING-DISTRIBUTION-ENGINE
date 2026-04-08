# RAIN (R∞N): Complete technical blueprint for an AI audio mastering platform

**RAIN is technically achievable with today's open-source ML models, C++20/WASM tooling, and cloud infrastructure — but the browser-first architecture requires careful separation between lightweight client-side DSP and heavy server-side ML inference.** The most critical insight across all 17 research areas: BS-RoFormer has definitively surpassed Demucs for source separation, SonicMaster (August 2025) is the first unified neural repair model for music, and the EU AI Act Article 50 deadline of August 2, 2026 makes C2PA implementation non-negotiable. The total infrastructure cost ranges from **€15–25/month** for a hobby deployment to **€1,800–2,200/month** for enterprise-scale label operations on Hetzner, roughly 5–10× cheaper than equivalent AWS deployments. What follows is a dense, actionable technical blueprint for every component.

---

## BS-RoFormer dominates source separation, but 12 stems require a cascaded pipeline

The source separation landscape has consolidated around **BS-RoFormer** (Band-Split RoPE Transformer), which won SDX'23 and continues to lead benchmarks. The best community model, **BS-RoFormer SW**, delivers 6-stem separation with SDR scores of **11.30 dB** (vocals), **14.62 dB** (bass), **14.11 dB** (drums) — substantially outperforming Meta's Demucs v4 htdemucs_ft across every stem. The primary training and inference framework is ZFTurbo's Music-Source-Separation-Training repository (1,200+ stars), which supports BS-RoFormer, MelBand RoFormer, HTDemucs, SCNet, Apollo, BSMamba2, and Conformer architectures. Over **70 pretrained models** are available via the `melband-roformer-infer` and `bs-roformer-infer` PyPI packages.

Achieving the target 12-stem separation requires a **four-pass cascade**. Pass 1 uses BS-RoFormer SW to produce 6 stems (vocals, drums, bass, guitar, piano, other). Pass 2 splits vocals into lead and backing using the MVSep Karaoke BS-RoFormer (SDR 10.41). Pass 3 separates drums into kick, snare, hats, and percussion via the DrumSep ensemble or LarsNet (purpose-built for 5 drum stems using the 1,224-hour StemGMD dataset). Pass 4 processes the "other" stem through specialized MelBand Roformer models — anvuew's dereverb model (SDR 19.17) extracts room/ambience, and residual subtraction yields effects/other. The MSR Challenge 2025 winner validated this cascaded approach with all checkpoints open-sourced at github.com/ModistAndrew/xlance-msr.

**Browser deployment of separation models is not practical.** BS-RoFormer at 72–93M parameters produces 280–370 MB ONNX files, far exceeding browser inference budgets. WASM inference would be 10–50× slower than GPU. The recommendation is server-side GPU inference on **NVIDIA A10G or better**, with lightweight models like Moises-Light (5M params, ~20 MB ONNX) reserved for potential browser-side preview quality. ZFTurbo's repo already includes ONNX and TensorRT conversion scripts.

---

## Neural audio repair is converging on unified models, but music-specific restoration remains immature

The research landscape divides sharply: most restoration models target speech, not music. **UNIVERSE++** (107.5M params, handles 55 distortion types) is speech-only. **VoiceFixer**, **Resemble Enhance**, **DeepFilterNet**, and Adobe Podcast Enhance are all speech-focused. The critical exception is **SonicMaster** (August 2025), a VAE + flow-matching generative model with MM-DiT blocks that handles dereverberation, EQ correction, declipping, dynamic-range expansion, and stereo enhancement on **stereo 44.1 kHz music** using text-prompt control. Trained on ~25,000 curated Jamendo tracks, it is the first unified music restoration framework.

For browser-deployable repair, **DeepFilterNet v3** stands alone as viable: just **~2M parameters**, official ONNX export, a Rust core achieving RTF < 0.02 on mobile CPU, and the ability to run in-browser via WASM. Its 2025 dereverberation extension adds music applicability. For declipping, **CQT-Diff** (Aalto University) uses a diffusion model with invertible Constant-Q Transform, specifically targeting music — but at 84 seconds per inference, it's server-only. The Demucs-based **DDD** declipping model achieves real-time processing on speech and could be retrained on music data.

The recommended pipeline splits into three tiers. **Tier 1 (browser/WASM)** runs DeepFilterNet for denoising, a lightweight de-clicker, and spectral gating for de-essing. **Tier 2 (server GPU, near-real-time)** handles DDD for declipping, AERO/AudioSR for bandwidth extension, and DeepFilterNet with dereverb. **Tier 3 (server GPU, batch)** deploys SonicMaster for unified restoration when maximum quality is needed. No single model handles everything for music — **de-essing has no dedicated neural model** and is best implemented as a frequency-band dynamic processor in the DSP engine.

---

## RTNeural enables real-time analog hardware emulation in WASM with sub-millisecond latency

Neural amp modeling has matured into a production-ready technology. **NAM** (Neural Amp Modeler) uses WaveNet-based architectures requiring only **3 minutes of audio per hardware configuration** for training, producing models with 5K–300K parameters that achieve perceptual quality indistinguishable from real hardware in MUSHRA listening tests. The training pipeline captures a chirp-and-noise sweep signal played through the target hardware, with both DI and output recorded simultaneously. Training takes 5–20 minutes on a consumer GPU.

**RTNeural** (github.com/jatinchowdhury18/RTNeural) is the inference engine of choice — a lightweight C++ library with three backends: Eigen (larger networks), XSIMD (smaller networks with direct SIMD), and **STL (standard library, zero dependencies, ideal for WASM)**. It supports Dense, Conv1D, GRU, and LSTM layers with zero memory allocation during inference. Over a dozen commercial audio plugins already use RTNeural, including AIDA-X, ChowTapeModel, and GuitarML's suite.

For WASM deployment, **NAM "Nano" and "Feather" models** (5K–50K parameters) are the targets. The DAFx25 benchmark on the SSL G-Bus Compressor (2,528-hour dataset) showed GCN (gated WaveNet) consistently outperforming other architectures, while LSTM at just **8K parameters** achieved competitive results. With WASM SIMD and Relaxed SIMD (FMA instructions), models running at 10× real-time natively should achieve real-time in WASM given the ~2–4× overhead. Realistically, **10–20 hardware emulations** are achievable: LA-2A (TCN/LSTM), 1176 (LSTM with FiLM conditioning), Pultec EQP-1A (lightweight WaveNet), SSL Bus Compressor (GCN with TVFiLM), Neve 1073 (WaveNet), and Studer A800 tape (WaveNet with multi-parameter conditioning). Each model is 100 KB–2 MB — storage is trivial.

---

## Codec pre-optimization has no existing tools but a clear research path through differentiable proxies

No commercial or open-source "codec-aware mastering" tools exist. However, Google Research's **Sandwiched Compression** framework (2022–2024) demonstrates up to **9 dB quality gains or 30% bitrate reduction** by wrapping standard codecs between neural pre- and post-processors trained through differentiable codec proxies. The architecture trains a neural pre-processor jointly with a differentiable approximation of the target codec (Ogg Vorbis for Spotify, AAC for Apple, Opus for YouTube), using straight-through estimators for gradient flow through quantization steps. At inference, only the pre-processor runs — no post-processor needed on the listener's end.

The implementation path uses **EnCodec** (Meta) or **DAC** (Descript Audio Codec) architectures as templates for building differentiable audio codec proxies, **auraloss** (github.com/csteinmetz1/auraloss) for perceptual loss functions, and **DeepAFx-ST** (Adobe Research) for the differentiable signal processing framework. Pre-processing should be subtle — small EQ adjustments, micro-dynamic shaping, inter-sample peak management — not audible changes to the master. A simpler non-ML alternative: spectral dithering above the codec's masking threshold, transient pre-emphasis to compensate for temporal smearing, and high-frequency pre-emphasis to counter codec rolloff.

---

## Reference matching builds on iZotope's published DAFx research and open-source Matchering

The most rigorous published approach to automated reference matching comes from iZotope's **DAFx 2022 paper**: "A Direct Microdynamics Adjusting Processor with Matching Paradigm" by Shahan Nercessian et al. Rather than using a traditional compressor (which has poor gradient characteristics), they designed a processor that directly adjusts microdynamics via the **Loudness Dynamic Range (LDR)** metric — the 95th percentile of the difference between slow loudness (3-second window) and fast loudness (25 ms window). The processor is implemented as a differentiable recurrent layer with natural gradient-descent convergence, extended for multiband operation in Ozone 10's Impact module.

For tonal matching, the standard approach computes long-term averaged spectra of both target and reference (30+ seconds), derives the difference curve, and fits it to parametric EQ bands — **~50% match with moderate smoothing** captures the "tonal shape" without introducing artifacts. Stereo width matching uses mid/side energy ratios across frequency bands, with the critical insight that sub-bass should be mostly mono. **Matchering 2.0** (github.com/sergree/matchering, GPLv3) provides an open-source Python implementation matching four dimensions: RMS level, frequency response, peak amplitude, and stereo width.

For emotion-aware processing, **MERT-v1-95M** (m-a-p/MERT-v1-95M on HuggingFace) provides the feature extraction backbone — a BERT-style transformer achieving SOTA on 14 MIR tasks. **Music2Emo** (February 2025, github.com/AMAAI-Lab/Music2Emotion) builds on MERT embeddings to deliver unified categorical and dimensional emotion recognition (PR-AUC 0.1543, ROC-AUC 0.7810 on MTG-Jamendo). **CLAP** (laion/clap-htsat-fused) enables zero-shot classification via text prompts like "aggressive and dark." For real-time browser inference, **Essentia.js** already demonstrates viable mood classification and genre tagging. The emotion-to-DSP mapping follows a valence/arousal framework: high arousal + low valence (aggressive) maps to boosted 2–5 kHz presence, aggressive limiting, and wider stereo; low arousal + high valence (calm) maps to gentle high shelving, light compression, and conservative loudness targets.

---

## Dolby Atmos rendering runs feasibly in browser WASM with libspatialaudio and SADIE II HRTFs

The best open-source spatial audio renderer for WASM compilation is **libspatialaudio** (github.com/videolabs/libspatialaudio, LGPL v2.1): pure C++ with minimal dependencies, supporting HOA up to 3rd order, VBAP object panning, direct speakers, binaural rendering via SOFA HRTFs, and ADM/IAMF compatibility. **Google OBR** (Open Binaural Renderer, Apache 2.0) explicitly renders 7.1.4 channel-based audio, 1st–4th order Ambisonics, and object-based audio to binaural, using Ambisonics as an intermediate representation.

For HRTFs, **SADIE II** (University of York) is the optimal choice for music production: 1,550 measurement directions for mannequins, both KU100 and KEMAR, diffuse-field compensated and minimum-phase versions at 44.1/48/96 kHz in SOFA format. Perceptual studies showed **KU100 was most preferred** overall. The rendering pipeline uses Uniform Partitioned Overlap-Save (UPOLS) convolution with 128-sample partitions matching the Web Audio API quantum.

The performance budget is achievable. At 48 kHz with 128-sample buffers (2.67 ms deadline), rendering a full **7.1.4 bed requires ~400–800 μs** with WASM SIMD — well within budget. Each additional object costs ~30–50 μs including HRTF convolution via the HOA path. A conservative estimate allows **20–30 simultaneous objects** in real-time, aligning with the Dolby Atmos consumer spec of 16 dynamic objects plus 7.1.2 bed. Total memory footprint: ~15–20 MB for HRTF data and object state. ADM BWF export uses EBU's standardized XML schema (ITU-R BS.2076) stored in `axml` and `chna` chunks of BW64 files, with the EBU ADM Renderer (github.com/ebu/ebu_adm_renderer) serving as algorithmic reference.

---

## C2PA v2.2 and EU AI Act compliance form an August 2026 hard deadline

**EU AI Act Article 50 takes legal effect on August 2, 2026.** It requires providers of AI systems generating synthetic audio to ensure outputs are **marked in a machine-readable format** and **detectable as artificially generated or manipulated**. The critical nuance for RAIN: AI-assisted mastering that enhances real audio (EQ, dynamics, noise removal) is likely classified as "tool-assisted editing" rather than generation — but the regulatory boundary is being clarified in the Code of Practice (final draft expected June 2026). The safer approach is implementing full marking capabilities regardless.

**C2PA v2.2** (released May 2025) provides the technical framework. The **c2pa-rs** SDK (github.com/contentauth/c2pa-rs, MIT + Apache 2.0) creates and embeds manifests in WAV (RIFF chunk), MP3 (ID3v2 GEOB tag), FLAC (ID3v2 GEOB), M4A (BMFF uuid box), and OGG Vorbis (new in v2.2). For AI mastering, each processing step creates a new manifest referencing the previous as an "ingredient," with `c2pa.actions.v2` assertions recording what AI tools were used. The `digitalSourceType` field distinguishes `trainedAlgorithmicMedia` (fully AI-generated) from AI-assisted processing.

For audio watermarking, **AudioSeal** (github.com/facebookresearch/audioseal, MIT license including model weights) embeds 16-bit messages with 90–100% detection accuracy, surviving compression and re-encoding. It supports streaming inference and 44.1/48 kHz sample rates. **Chromaprint** (LGPL 2.1) generates audio fingerprints in < 100 ms, with a JavaScript port (chromaprint.js) already working in browsers and the C library compilable to WASM via Emscripten with KissFFT backend. The complete provenance implementation: Ed25519 signing of audio content hashes + C2PA manifests + AudioSeal watermarks + Chromaprint fingerprints.

---

## DDEX ERN 4.3, DDP export, and LabelGrid API form the distribution backbone

DDEX ERN 4.3 is the current standard, with all versions below 4.1.1 deprecated since March 2025. The **ddex-suite** Python library (`pip install ddex-parser ddex-builder`) provides ERN 4.3 generation with platform-specific presets for Spotify, Apple, and YouTube, plus validation against official XSD schemas at `ddex.net/xml/ern/43/release-notification.xsd`. Critically, **DDEX adopted AI disclosure fields in September 2025**, coordinated with Spotify — labels specify where and how AI was used across vocals, instrumentation, composition, post-production, and mixing/mastering. Fifteen distributors already support this standard, and Apple Music launched Transparency Tags in March 2026 with four categories.

For DDP export, the format is proprietary (DCA/Doug Carson & Associates) but **cue2ddp** (ddp.andreasruge.de) provides free-to-use CLI tools for Linux/macOS/Windows that create DDP 2.0 from cue/wav images with full PQ subcodes, ISRC, UPC/EAN, CD-Text, and checksums. The programmatic path: generate cue sheets in Python, call cue2ddp via subprocess. For vinyl, pressing plants require **24-bit WAV files, one per side**, at 96 kHz optimal, with bass below 100–200 Hz summed to mono and peaks no higher than -3 dBFS.

**LabelGrid** (labelgrid.com) is the recommended distribution API: full REST API with sandbox, DDEX ERN 4.3 feed import via S3 endpoint, 55+ DSPs, per-track AI disclosure mapping, webhook notifications, and white-label capability. Pricing starts at **$119/month** (Starter API, 5 labels) to $1,830+/month (Custom API, unlimited). Standard DSP delivery takes a 5% fee; direct SOBO deals retain 100%. The universal delivery format recommendation: **24-bit/96 kHz WAV or FLAC** as the single master — each DSP handles its own conversion.

---

## ONNX Runtime Web supports models up to ~500 MB in browser with WebGPU providing 10–20× speedup over WASM

ONNX Runtime Web v1.24.1 (February 2026) provides four backends: WASM (all operators supported), WebGPU (subset of operators, 10–20× faster for compute-heavy models), WebGL (maintenance mode), and WebNN (experimental). The practical browser model size limit is **~500 MB for WASM** (4 GB memory ceiling with 2–3× overhead) and ~1–2 GB for WebGPU. Multi-threaded WASM inference requires `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` headers, with **4 threads + SIMD delivering 26.5× speedup** over single-threaded non-SIMD in IMG.LY benchmarks.

**FP16 quantization is the sweet spot for WebGPU** — 2× size reduction, faster inference on GPU hardware, and near-lossless quality. For WASM, **UINT8 dynamic quantization** provides 4× reduction but requires validation with audio-specific metrics (SDR, PESQ) as audio is more sensitive to quantization artifacts than vision. ONNX Runtime **cannot run directly in AudioWorklet** (GitHub issue #13072) — the recommended architecture uses a dedicated Web Worker running ONNX inference, communicating with the AudioWorklet via SharedArrayBuffer or MessageChannel for zero-copy transfer.

The model optimization pipeline: PyTorch → `torch.onnx.export(dynamo=True)` → ONNX Runtime graph optimization → quantization (FP16 for WebGPU, UINT8 for WASM) → optional ORT format conversion (~3 MB minimal WASM binary). Cache models via the Cache API or Origin Private File System (OPFS) to avoid redownloading.

---

## The C++20 RainDSP engine compiles cleanly to WASM with native f64 support and SIMD

Emscripten fully supports C++20 via `-std=c++20`: concepts, ranges, coroutines, `std::span`, constexpr improvements, and three-way comparison all work. Notably, `emscripten::val` supports C++20 `co_await` for JavaScript Promises. WASM natively provides **f64 operations at no scalar performance penalty** — CPUs execute f64 and f32 scalar operations at identical throughput. The tradeoff appears only in SIMD: 128-bit WASM SIMD packs 2× f64 versus 4× f32, halving vectorized throughput. For professional mastering with 48-bit mantissa precision, this is worthwhile.

For the **look-ahead brickwall limiter**, the algorithm uses a monotonic deque for O(1) moving-maximum gain reduction computation, cascaded box filters (3–4 passes) for smooth artifact-free gain curves, and a release envelope limiting gain increase rate. Total latency equals the look-ahead time (5–30 ms). The **multiband compressor** uses Linkwitz-Riley 4th-order crossovers (two cascaded 2nd-order Butterworth at Q = 0.7071) in a tree structure, requiring allpass compensation on non-split paths. Four bands (sub/low-mid/high-mid/high) is optimal for mastering. **True peak detection** per ITU-R BS.1770-4 uses 4× oversampling with the standard's specified 48-tap FIR filter, implementable as 4 polyphase sub-filters of ~12 taps each. **Loudness measurement** uses K-weighting (high shelf + high-pass biquad cascade) with dual gating (absolute at -70 LKFS, relative at -10 LU below running average).

The recommended build configuration: `em++ -std=c++20 -O3 -msimd128 -mrelaxed-simd -flto -fno-exceptions -fno-rtti -sAUDIO_WORKLET -sWASM_WORKERS -sSHARED_MEMORY -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=64MB -sMAXIMUM_MEMORY=2GB -sMALLOC=emmalloc --closure 1`. Reference projects to study: **Faust** (DSP memory management patterns, denormal handling), **web-synth** (AudioWorklet + WASM SIMD integration), and **Dreamtonics/juce_emscripten** (commercially shipping JUCE-to-WASM port).

---

## Hetzner plus Coolify delivers 5–10× cost savings versus AWS with viable GPU options

**Coolify** (44,700+ GitHub stars) is an open-source self-hosted PaaS that wraps Docker, Traefik, and multi-node orchestration — explicitly recommending Hetzner Cloud. It handles auto-SSL via Let's Encrypt, zero-downtime rolling deploys, database provisioning, S3 backups, and team collaboration with no per-seat cost. Hetzner offers dedicated GPU servers: the **GEX44** (NVIDIA RTX 4000 SFF Ada, 20 GB VRAM, Intel i5-13500) at **€184/month** with waived setup fee, and the **GEX131** (NVIDIA RTX PRO 6000 Blackwell, 96 GB VRAM) at approximately €600–800/month. No GPU cloud instances exist — elastic GPU scaling requires external providers.

**PostgreSQL 18** (GA September 2025, currently 18.3) brings native **UUIDv7** for timestamp-ordered primary keys and **OAuth 2.0 authentication** for SSO integration. **Valkey** (Linux Foundation Redis fork, BSD 3-Clause) delivers 37% higher SET throughput than Redis 8.0, works as a drop-in replacement with all Redis clients, and functions with Celery via the `celery[redis]` bundle. **Hetzner Object Storage** at €4.99/month for 1 TB storage + 1 TB egress is 4× cheaper than AWS S3 for storage and 50× cheaper for egress.

The cost trajectory: **€15–25/month** for a hobby MVP (everything on a single CX32 at €6.80 plus base storage), **€310–360/month** at 1,000 users (dedicated CCX instances, GEX44 GPU, RunPod burst), and **€1,800–2,200/month** for enterprise (redundant API servers, read replicas, GEX131 GPU, RunPod burst pool). The hybrid GPU strategy uses Hetzner GEX44 for baseline inference plus **RunPod Serverless** (RTX 4090 at ~$0.44/hr, A100 at ~$1.10/hr) for elastic burst capacity, avoiding over-provisioning.

---

## The free tier runs entirely in WASM with zero server cost

The multi-tenant architecture serves three tiers through a single PostgreSQL database with Row Level Security (RLS). **Free tier** users never touch the server: all audio processing happens client-side via the WASM DSP engine (EQ, compression, limiting, loudness measurement, spectral analysis, format conversion via ffmpeg.wasm), with files stored in browser IndexedDB. When a free user triggers an AI feature (stem separation, AI mastering, neural repair), the UI prompts for upgrade. **Pro tier** adds cloud GPU processing through shared Celery worker pools with rate limiting (10 tasks/minute). **Enterprise tier** gets dedicated GPU instances, custom model training, SSO (SAML via pysaml2 / OIDC via authlib), white-label domain routing through Coolify/Traefik, and dedicated PostgreSQL schemas.

Celery task routing uses separate queues per tier and workload type: enterprise tasks route to `gpu_priority_high`, pro tasks to `gpu_priority_medium`, and free analysis tasks to `cpu_standard`. GPU workers run with `--concurrency 1` and `--prefetch-multiplier 1` to avoid CUDA memory conflicts. Autoscaling monitors Valkey queue depth every 30 seconds, triggering RunPod serverless endpoints for burst and Hetzner Cloud API for sustained scaling.

---

## The artist identity engine uses a 64-dimensional EMA vector with Bayesian cold-start

The 64-dimensional preference vector decomposes into **16 EQ dimensions** (8 frequency band preferences, 4 Q/bandwidth, tonal balance target, mid-side tendency), **12 dynamics dimensions** (ratio, attack, release, loudness target, multiband, transient handling), **6 stereo/spatial dimensions**, **8 coloring/saturation dimensions** (tape, tube, console character), **10 genre/context dimensions** (genre embedding, era preference, reference track cluster centroid), and **12 meta-preferences** (conservative vs. aggressive tendency, platform optimization priority, revision behavior).

Updates use per-dimension adaptive EMA: **α = 0.85–0.95** for stable long-term preferences, **α = 0.5–0.7** during cold-start (sessions 1–5). Observations are weighted by confidence: explicit user adjustments (1.0), accepted AI suggestions without modification (0.6), implicit signals like not re-mastering (0.3). The cold-start strategy combines **genre-based initialization** (centroid of declared genre cluster), **reference track analysis** (feature extraction mapped to vector space), and **active learning A/B comparisons** probing the most uncertain dimensions first. This approach mirrors Spotify's taste profile system, which uses 80-dimensional embeddings aggregated over three time scales.

---

## Loudness penalty prediction requires platform-specific rules beyond simple LUFS measurement

Platform normalization is more nuanced than a single LUFS target. **Spotify** normalizes to -14 LUFS (Normal mode) in both directions, applying a limiter (5 ms attack, 100 ms decay, -1 dBTP) only in Loud mode (-11 LUFS). **Apple Music Sound Check** targets **-16 LUFS** with bidirectional normalization but never uses limiting. **YouTube** normalizes **downward only** to -14 LUFS — a track at -20 LUFS plays at -20 LUFS. **Tidal** uses **album-only normalization** at -14 LUFS, downward only, even for individual tracks in shuffle mode. The calculation: `penalty = platform_target - measured_LUFS_I`, clamped by platform rules (direction limits, peak headroom for upward gain, limiter application). Implementation uses **libebur128** (C, MIT license) or **pyloudnorm** (Python) for BS.1770-4 measurement, with a configurable platform rules engine that updates without code changes.

---

## Eleven codebase issues require immediate triage with authentication as the top priority

The recommended fix order prioritizes security and stability. **Unauthenticated routes** (CRITICAL): apply auth as a global FastAPI dependency via `app = FastAPI(dependencies=[Depends(require_auth)])`, with public routes on a separate router explicitly excluded. **Blocking librosa** (CRITICAL): replace `librosa.load()` with `soundfile.sf.read()` for simple loading; use `ProcessPoolExecutor` (not ThreadPoolExecutor — GIL prevents CPU-bound parallelism in threads) for spectrogram computation; offload operations >2 seconds to Celery. **In-memory sessions** (HIGH): migrate to Valkey-backed session store with TTL using `redis.asyncio`, enabling horizontal scaling. **Auth refresh** (HIGH): implement refresh tokens in httpOnly cookies with rotation — issue new refresh token on every use, detect reuse as a theft indicator, revoke the entire token family. **Rate limiting** (HIGH): deploy SlowAPI with Valkey backend for distributed per-tier limits (20/hour free, 5,000/hour studio_pro). **Tier naming** (HIGH): create a shared Python package with canonical Enum definitions, generate TypeScript types from the FastAPI OpenAPI spec via `openapi-typescript`. **ISRC/UPC** (HIGH): NEVER generate randomly — these are globally unique identifiers from allocated ranges (ISRC registrant codes via RIAA at $95, UPC blocks from GS1), requiring atomic sequential counters with `INSERT ... ON CONFLICT DO UPDATE RETURNING`.

For the **Demucs stub**, implement as a Celery task with a custom Task class that loads the model once per worker process via a `_model` class attribute, using `--pool solo` or `--concurrency 1` to avoid CUDA fork issues. The **LoRA training stub** uses HuggingFace PEFT with per-organization GPU allocation routed through separate Celery queues. **Alembic migration recovery**: squash existing migrations, generate a single "initial_schema" from current models, stamp existing databases to the new head, and add a CI step running `alembic check` (Alembic 1.9+) to prevent future drift.

---

## Conclusion: pragmatic priorities and what to build first

RAIN's architecture splits cleanly into two execution domains that should be developed in parallel. The **browser-side domain** (RainDSP WASM engine, neural analog models via RTNeural, Essentia.js for emotion/genre classification, lightweight DeepFilterNet for denoising, loudness measurement, reference matching DSP, and spatial audio via libspatialaudio) provides the zero-cost free tier and low-latency processing for all tiers. The **server-side domain** (BS-RoFormer cascaded separation, SonicMaster unified repair, MERT/Music2Emo feature extraction, codec pre-optimization, C2PA manifest generation, DDEX ERN 4.3 export, and Claude Sonnet for AI co-mastering decisions) handles the heavy ML inference and compliance workflows.

Three items carry hard external deadlines: **EU AI Act Article 50 compliance by August 2, 2026** (implement C2PA + AudioSeal + multi-layer marking now), **DDEX AI disclosure standard** (already adopted by 15+ distributors — implement in the DDEX pipeline immediately), and **ISRC/UPC sequential allocation** (random generation produces invalid codes that distributors will reject). The highest-impact engineering work is fixing the 11 codebase issues (especially authentication and blocking I/O), standing up the Celery + Valkey task queue on Hetzner, and implementing the BS-RoFormer separation pipeline as the flagship differentiating feature. The neural analog modeling, codec pre-optimization, and artist identity engine are powerful differentiators but can ship iteratively after the core pipeline is solid.