import { useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import {
  Zap, Shield, Cpu, Globe, Music2, Layers, BarChart3,
  ArrowRight, Play, ChevronDown, Disc3, Headphones, Radio
} from 'lucide-react'

const TIERS = [
  { name: 'Free', price: '$0', period: '', desc: 'Listen & preview', features: ['WASM mastering engine', 'Real-time preview', 'RAIN Score analysis', 'No download'], cta: 'Start Free' },
  { name: 'Spark', price: '$9', period: '/mo', desc: '50 downloads', features: ['Full resolution export', 'WAV / FLAC / MP3', 'Session persistence', 'Simple Mode'], cta: 'Get Spark' },
  { name: 'Creator', price: '$29', period: '/mo', desc: 'Full creative control', features: ['Advanced Mode + stems', 'Demucs stem separation', 'Claude AI assists (10/mo)', 'Artist Identity Engine'], cta: 'Go Creator', featured: true },
  { name: 'Artist', price: '$59', period: '/mo', desc: 'Professional distribution', features: ['DAW plugin (VST3/AU/AAX)', 'Distribution Intelligence', 'Full AIE + reference match', 'RAIN-CERT provenance'], cta: 'Go Artist' },
  { name: 'Studio Pro', price: '$149', period: '/mo', desc: 'Studio-grade mastering', features: ['Dolby Atmos upmix', 'DDEX / DDP delivery', 'Vinyl mastering mode', 'Real-time collaboration'], cta: 'Go Pro' },
  { name: 'Enterprise', price: 'Custom', period: '', desc: 'Labels & teams', features: ['Custom RainNet LoRA', 'White-label API', 'Unlimited everything', 'Dedicated support'], cta: 'Contact Sales' },
]

const FEATURES = [
  { icon: Cpu, title: 'Local-First Processing', desc: 'Audio never leaves your device. RainDSP runs in WASM — 64-bit double precision, deterministic rendering. Zero cloud dependency for processing.' },
  { icon: Shield, title: 'RAIN-CERT Provenance', desc: 'Ed25519-signed provenance certificates. Every master is cryptographically verified — input hash, output hash, WASM binary hash, processing params.' },
  { icon: Layers, title: 'Stem-Aware Mastering', desc: 'Demucs v4 htdemucs_6s separation. 12-stem multi-pass extraction. Per-stem gain control with SAIL intelligent limiting.' },
  { icon: Globe, title: 'Platform-Aware Delivery', desc: 'Automatic loudness targeting for Spotify, Apple Music, YouTube, Tidal, Amazon, TikTok, SoundCloud, and vinyl. DDEX ERN 4.3 distribution.' },
  { icon: Music2, title: 'Artist Identity Engine', desc: 'Your mastering fingerprint. 64-dimensional voice vector that learns your preferences. EMA-updated over sessions. Exportable.' },
  { icon: BarChart3, title: 'RAIN Score', desc: 'Platform Survival Score. Composite quality metric across loudness compliance, codec penalty, dynamic range, and stereo integrity.' },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()
  const bgRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isAuthenticated) {
      void navigate('/app')
    }
  }, [isAuthenticated, navigate])

  // Mouse-tracking ambient glow
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (bgRef.current) {
        bgRef.current.style.setProperty('--mouse-x', `${e.clientX}px`)
        bgRef.current.style.setProperty('--mouse-y', `${e.clientY}px`)
      }
    }
    window.addEventListener('mousemove', handler)
    return () => window.removeEventListener('mousemove', handler)
  }, [])

  return (
    <div className="min-h-screen bg-[#08070F] text-rain-text overflow-y-auto overflow-x-hidden">
      {/* Ambient background */}
      <div ref={bgRef} className="ambient-bg" />

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass-subtle">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <span className="rain-logo-xl text-2xl font-black tracking-tight" style={{ fontSize: '24px' }}>
              <span className="rain-logo-r">R</span>
              <span className="rain-logo-inf">&infin;</span>
              <span className="rain-logo-n">N</span>
            </span>
            <div className="hidden md:flex items-center gap-6">
              <a href="#features" className="text-sm text-rain-dim hover:text-rain-text transition-colors">Features</a>
              <a href="#pricing" className="text-sm text-rain-dim hover:text-rain-text transition-colors">Pricing</a>
              <a href="#how-it-works" className="text-sm text-rain-dim hover:text-rain-text transition-colors">How It Works</a>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login" className="btn-ghost text-sm py-2 px-3">Sign In</Link>
            <Link to="/register" className="btn-primary text-sm py-2 px-3">Start Free</Link>
          </div>
        </div>
      </nav>

      {/* ========= HERO ========= */}
      <section className="relative min-h-screen flex flex-col items-center justify-center px-6 pt-16">
        {/* Glow orbs */}
        <div className="hero-glow bg-teal-500" style={{ top: '10%', left: '20%' }} />
        <div className="hero-glow bg-emerald-500" style={{ top: '30%', right: '15%', animationDelay: '-7s' }} />
        <div className="hero-glow bg-cyan-500" style={{ bottom: '20%', left: '40%', animationDelay: '-14s', opacity: 0.08 }} />

        {/* Grid overlay */}
        <div className="grid-overlay" />

        <div className="relative z-10 max-w-4xl mx-auto text-center space-y-8">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-subtle text-xs text-rain-dim">
            <span className="w-2 h-2 rounded-full bg-rain-green animate-pulse" />
            <span>Local-first AI mastering — audio never leaves your device</span>
          </div>

          {/* Logo */}
          <h1 className="rain-logo-xl">
            <span className="rain-logo-r">R</span>
            <span className="rain-logo-inf">&infin;</span>
            <span className="rain-logo-n">N</span>
          </h1>

          {/* Tagline */}
          <p className="text-xl md:text-2xl font-light text-rain-silver leading-relaxed max-w-2xl mx-auto">
            AI-powered mastering engine for professionals.
            <br />
            <span className="text-gradient-infinity font-semibold">From Suno to Spotify in minutes.</span>
          </p>

          <p className="text-sm text-rain-dim max-w-lg mx-auto">
            Professional mastering, stem separation, provenance certification, and direct distribution to every DSP — all from one platform. Rain doesn't live in the cloud.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link to="/register" className="btn-gradient flex items-center gap-3 text-base">
              <Play size={18} fill="white" />
              Start Mastering Free
            </Link>
            <a href="#how-it-works" className="btn-ghost flex items-center gap-2 text-sm">
              See How It Works
              <ArrowRight size={16} />
            </a>
          </div>

          {/* Trust indicators */}
          <div className="flex items-center justify-center gap-8 pt-8 text-rain-muted text-xs">
            <span className="flex items-center gap-2"><Shield size={14} /> Ed25519 verified</span>
            <span className="flex items-center gap-2"><Cpu size={14} /> 64-bit WASM DSP</span>
            <span className="flex items-center gap-2"><Headphones size={14} /> -14 LUFS Spotify</span>
          </div>
        </div>

        {/* Animated waveform */}
        <div className="relative z-10 mt-16 w-full max-w-3xl mx-auto">
          <div className="hero-waveform">
            {Array.from({ length: 80 }).map((_, i) => {
              const hMin = 8 + Math.random() * 15
              const hMax = 30 + Math.random() * 70
              const delay = (i * 0.04) % 1.5
              return (
                <div
                  key={i}
                  className="hero-waveform-bar"
                  style={{
                    '--bar-h-min': `${hMin}px`,
                    '--bar-h-max': `${hMax}px`,
                    animationDelay: `${delay}s`,
                    animationDuration: `${1.2 + Math.random() * 0.8}s`,
                  } as React.CSSProperties}
                />
              )
            })}
          </div>
          {/* Waveform labels */}
          <div className="flex justify-between mt-3 px-4 text-[10px] font-mono text-rain-muted">
            <span>INPUT  -6.2 LUFS</span>
            <span className="text-gradient-infinity font-semibold">RAIN DSP PROCESSING</span>
            <span>OUTPUT  -14.0 LUFS</span>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-rain-muted animate-bounce">
          <ChevronDown size={20} />
        </div>
      </section>

      {/* ========= HOW IT WORKS ========= */}
      <section id="how-it-works" className="relative py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-xs text-rain-teal font-semibold tracking-[0.2em] uppercase mb-3">Pipeline</p>
            <h2 className="text-3xl md:text-4xl font-bold">Upload. Master. Distribute.</h2>
            <p className="text-rain-dim mt-4 max-w-lg mx-auto">Three steps from raw audio to every streaming platform. AI-powered analysis, deterministic rendering, cryptographic certification.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { step: '01', icon: Disc3, title: 'Upload & Analyze', desc: 'Drop your audio — WAV, FLAC, AIFF, MP3. Instant LUFS analysis, genre classification, and mel spectrogram extraction. Free tier runs entirely in-browser.' },
              { step: '02', icon: Radio, title: 'AI Master', desc: 'RainNet v2 conditional transformer generates 32 processing parameters. Multiband compression, linear-phase EQ, analog saturation, SAIL limiting. 64-bit double precision.' },
              { step: '03', icon: Globe, title: 'Certify & Distribute', desc: 'RAIN-CERT provenance signing. Platform-specific loudness targeting. DDEX ERN 4.3 metadata. One-click distribution to Spotify, Apple Music, and 150+ DSPs.' },
            ].map((item) => (
              <div key={item.step} className="feature-card group">
                <div className="flex items-center gap-3 mb-6">
                  <span className="text-3xl font-black text-gradient-infinity">{item.step}</span>
                  <item.icon size={24} className="text-rain-teal" />
                </div>
                <h3 className="text-lg font-bold mb-3">{item.title}</h3>
                <p className="text-sm text-rain-dim leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========= FEATURES ========= */}
      <section id="features" className="relative py-32 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-xs text-rain-teal font-semibold tracking-[0.2em] uppercase mb-3">Capabilities</p>
            <h2 className="text-3xl md:text-4xl font-bold">Built for Professionals</h2>
            <p className="text-rain-dim mt-4 max-w-lg mx-auto">Every feature designed for labels, producers, and engineers who demand precision, provenance, and speed.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="feature-card group">
                <div className="w-12 h-12 rounded-xl glass flex items-center justify-center mb-5 group-hover:shadow-[0_0_20px_rgba(0,212,170,0.2)] transition-shadow">
                  <f.icon size={22} className="text-rain-teal" />
                </div>
                <h3 className="text-base font-bold mb-3">{f.title}</h3>
                <p className="text-sm text-rain-dim leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========= SUNO → RAIN → SPOTIFY ========= */}
      <section className="relative py-32 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xs text-rain-teal font-semibold tracking-[0.2em] uppercase mb-3">The Missing Link</p>
          <h2 className="text-3xl md:text-4xl font-bold mb-6">
            From <span className="text-gradient-warm">Suno</span> to <span className="text-gradient-cool">Spotify</span>
          </h2>
          <p className="text-rain-dim max-w-2xl mx-auto mb-12">
            AI-generated music needs professional mastering, provenance verification, and proper distribution metadata. RAIN bridges the gap — import stems from Suno, master to platform specs, embed AI declarations, and distribute with DDEX compliance.
          </p>

          <div className="flex items-center justify-center gap-4 flex-wrap">
            {['Suno', 'Udio', 'Stems'].map((src) => (
              <div key={src} className="glass px-6 py-3 rounded-xl text-sm font-semibold text-rain-silver">{src}</div>
            ))}
            <ArrowRight size={20} className="text-rain-teal" />
            <div className="glass px-8 py-3 rounded-xl border-rain-teal/30 border">
              <span className="text-lg font-black">
                <span className="rain-logo-r">R</span>
                <span className="rain-logo-inf">&infin;</span>
                <span className="rain-logo-n">N</span>
              </span>
            </div>
            <ArrowRight size={20} className="text-rain-teal" />
            {['Spotify', 'Apple Music', 'Tidal', '150+ DSPs'].map((dst) => (
              <div key={dst} className="glass px-6 py-3 rounded-xl text-sm font-semibold text-rain-silver">{dst}</div>
            ))}
          </div>
        </div>
      </section>

      {/* ========= PRICING ========= */}
      <section id="pricing" className="relative py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs text-rain-teal font-semibold tracking-[0.2em] uppercase mb-3">Pricing</p>
            <h2 className="text-3xl md:text-4xl font-bold">Scale With Your Craft</h2>
            <p className="text-rain-dim mt-4">Annual billing saves ~20%. All tiers include RAIN-CERT provenance.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {TIERS.map((t) => (
              <div key={t.name} className={`pricing-card ${t.featured ? 'featured' : ''}`}>
                <h3 className="text-sm font-bold uppercase tracking-wider mb-2">{t.name}</h3>
                <div className="flex items-baseline gap-1 mb-1">
                  <span className="text-2xl font-black">{t.price}</span>
                  {t.period && <span className="text-xs text-rain-dim">{t.period}</span>}
                </div>
                <p className="text-xs text-rain-dim mb-5">{t.desc}</p>
                <ul className="space-y-2 mb-6">
                  {t.features.map((f) => (
                    <li key={f} className="text-xs text-rain-silver flex items-start gap-2">
                      <Zap size={10} className="text-rain-teal mt-0.5 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/register"
                  className={`block text-center text-xs font-bold py-2.5 rounded-lg transition-all ${
                    t.featured
                      ? 'btn-primary text-xs py-2.5'
                      : 'btn-ghost text-xs py-2.5'
                  }`}
                >
                  {t.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========= CTA FOOTER ========= */}
      <section className="relative py-32 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6">
            Rain doesn't live in the cloud.
          </h2>
          <p className="text-rain-dim mb-10 text-lg">
            Your audio. Your device. Your masters.
            <br />
            Start mastering in seconds — no credit card required.
          </p>
          <Link to="/register" className="btn-gradient inline-flex items-center gap-3 text-lg">
            <Play size={20} fill="white" />
            Start Mastering Free
          </Link>
        </div>
      </section>

      {/* ========= FOOTER ========= */}
      <footer className="border-t border-rain-border/30 py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <span className="text-xl font-black">
              <span className="rain-logo-r">R</span>
              <span className="rain-logo-inf">&infin;</span>
              <span className="rain-logo-n">N</span>
            </span>
            <span className="text-xs text-rain-muted">ARCOVEL Technologies International</span>
          </div>
          <p className="text-xs text-rain-muted">&copy; 2026 ARCOVEL Technologies International. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
