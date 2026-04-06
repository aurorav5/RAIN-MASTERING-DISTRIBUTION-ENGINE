import { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import { Check, Globe } from 'lucide-react'

// ─── Platform data (unchanged) ───────────────────────────────────────────────

const PLATFORMS = [
  { id: 'spotify',       name: 'Spotify',               lufs: -14, codec: '3d',  color: '#1DB954', tier: 1 },
  { id: 'apple_music',   name: 'Apple Music',            lufs: -16, codec: '5d',  color: '#FA2D48', tier: 1 },
  { id: 'youtube_music', name: 'YouTube Music',          lufs: -14, codec: '3d',  color: '#FF0000', tier: 1 },
  { id: 'tidal',         name: 'Tidal HiFi',             lufs: -14, codec: '5d',  color: '#00D4FF', tier: 1 },
  { id: 'amazon',        name: 'Amazon Music HD',        lufs: -14, codec: '5d',  color: '#FF9900', tier: 1 },
  { id: 'deezer',        name: 'Deezer',                 lufs: -15, codec: '5d',  color: '#A238FF', tier: 2 },
  { id: 'tiktok',        name: 'TikTok / CapCut',        lufs: -14, codec: '7d',  color: '#FF0050', tier: 2 },
  { id: 'instagram',     name: 'Instagram / Facebook',   lufs: -14, codec: '7d',  color: '#E1306C', tier: 2 },
  { id: 'pandora',       name: 'Pandora',                lufs: -14, codec: '9d',  color: '#005483', tier: 2 },
  { id: 'soundcloud',    name: 'SoundCloud',             lufs: -14, codec: '5d',  color: '#FF5500', tier: 2 },
  { id: 'qobuz',         name: 'Qobuz',                  lufs: -14, codec: '5d',  color: '#4A9EFF', tier: 3 },
  { id: 'shazam',        name: 'Shazam / Apple',         lufs: -16, codec: '5d',  color: '#0088FF', tier: 3 },
  { id: 'tencent',       name: 'Tencent Music',          lufs: -14, codec: '54d', color: '#12B7F5', tier: 3 },
  { id: 'netease',       name: 'NetEase Music',          lufs: -14, codec: '44d', color: '#C20C0C', tier: 3 },
  { id: 'anghami',       name: 'Anghami',                lufs: -14, codec: '7d',  color: '#8B5CF6', tier: 3 },
  { id: 'jiosaavn',      name: 'JioSaavn',               lufs: -14, codec: '7d',  color: '#2BC5B4', tier: 3 },
  { id: 'boomplay',      name: 'Boomplay',               lufs: -14, codec: '5d',  color: '#4AFF8A', tier: 3 },
  { id: 'audiomack',     name: 'Audiomack',              lufs: -14, codec: '7d',  color: '#FFA500', tier: 3 },
  { id: 'napster',       name: 'Napster',                lufs: -14, codec: '5d',  color: '#888888', tier: 3 },
  { id: 'kkbox',         name: 'KKBOX',                  lufs: -14, codec: '7d',  color: '#09CEF6', tier: 3 },
] as const

type PlatformId = (typeof PLATFORMS)[number]['id']

const GENRES = [
  'Electronic', 'Hip-Hop', 'Pop', 'Rock', 'R&B',
  'Classical', 'Jazz', 'Country', 'Latin', 'Podcast', 'Other',
] as const

// ─── Types ───────────────────────────────────────────────────────────────────

type WizardStep = 1 | 2 | 3 | 4
type DeliveryStatus = 'pending' | 'processing' | 'live'

interface Metadata {
  title: string
  artist: string
  album: string
  genre: string
  releaseDate: string
  isrc: string
  upc: string
  explicit: boolean
  aiGenerated: boolean
  copyright: string
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatISRC(raw: string): string {
  const cleaned = raw.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 12)
  const parts = [
    cleaned.slice(0, 2),
    cleaned.slice(2, 5),
    cleaned.slice(5, 7),
    cleaned.slice(7, 12),
  ].filter(Boolean)
  return parts.join('-')
}

function formatUPC(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, 13)
}

// Estimated reach based on selected platforms (rough monthly active users)
const REACH_MAP: Partial<Record<PlatformId, number>> = {
  spotify: 640, apple_music: 88, youtube_music: 80, tidal: 6, amazon: 68,
  deezer: 16, tiktok: 150, instagram: 140, pandora: 50, soundcloud: 70,
  qobuz: 2, shazam: 200, tencent: 100, netease: 80, anghami: 8,
  jiosaavn: 50, boomplay: 10, audiomack: 15, napster: 1, kkbox: 8,
}

function estimatedReach(ids: Set<string>): string {
  let m = 0
  for (const id of ids) {
    m += (REACH_MAP[id as PlatformId] ?? 0)
  }
  if (m >= 1000) return `${(m / 1000).toFixed(1)}B`
  return `${m}M`
}

// ─── Stepper Header ───────────────────────────────────────────────────────────

const STEP_LABELS: Record<WizardStep, string> = {
  1: 'PLATFORMS',
  2: 'METADATA',
  3: 'REVIEW',
  4: 'STATUS',
}

function StepHeader({ step }: { step: WizardStep }) {
  return (
    <div className="flex items-center gap-0 mb-5">
      {([1, 2, 3, 4] as WizardStep[]).map((s, idx) => (
        <div key={s} className="flex items-center flex-1">
          {/* Circle */}
          <div className="relative flex items-center justify-center">
            <motion.div
              animate={{
                background: step > s
                  ? 'linear-gradient(135deg,#00D4AA,#00E5C8)'
                  : step === s
                    ? 'rgba(0,212,170,0.15)'
                    : 'rgba(30,46,30,0.5)',
                borderColor: step >= s ? '#00D4AA' : '#1E2E1E',
              }}
              className="w-8 h-8 rounded-full border-2 flex items-center justify-center"
              transition={{ duration: 0.25 }}
            >
              <AnimatePresence mode="wait">
                {step > s ? (
                  <motion.span
                    key="check"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                  >
                    <Check size={14} className="text-rain-black" />
                  </motion.span>
                ) : (
                  <motion.span
                    key="num"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className={`text-[11px] font-mono font-bold ${step === s ? 'text-rain-teal' : 'text-rain-muted'}`}
                  >
                    {s}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.div>
            <span
              className={`absolute top-9 text-[9px] font-mono tracking-wider whitespace-nowrap ${
                step === s ? 'text-rain-teal' : 'text-rain-muted'
              }`}
            >
              {STEP_LABELS[s]}
            </span>
          </div>

          {/* Connector */}
          {idx < 3 && (
            <div className="flex-1 h-px mx-1 overflow-hidden bg-rain-border">
              <motion.div
                className="h-full bg-rain-teal"
                animate={{ width: step > s ? '100%' : '0%' }}
                transition={{ duration: 0.4, ease: 'easeInOut' }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Slide variants ───────────────────────────────────────────────────────────

const slideVariants = {
  enter: (dir: number) => ({ x: dir * 60, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit:  (dir: number) => ({ x: dir * -60, opacity: 0 }),
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function DistributeTab() {
  const { tierGte } = useAuthStore()
  const { rainCertId } = useSessionStore()

  const [step, setStep] = useState<WizardStep>(1)
  const [prevStep, setPrevStep] = useState<WizardStep>(1)
  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<string>>(
    new Set(['spotify', 'apple_music', 'youtube_music', 'tidal', 'amazon'])
  )
  const [tierFilter, setTierFilter] = useState<number | 'all' | 'none'>('all')
  const [metadata, setMetadata] = useState<Metadata>({
    title: '', artist: '', album: '', genre: 'Electronic',
    releaseDate: '', isrc: '', upc: '',
    explicit: false, aiGenerated: true, copyright: '',
  })
  const [termsChecked, setTermsChecked] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [deliveryStatus, setDeliveryStatus] = useState<Map<string, DeliveryStatus>>(new Map())

  const canDistribute = tierGte('studio_pro')
  const slideDir = step > prevStep ? 1 : -1

  function goTo(next: WizardStep) {
    setPrevStep(step)
    setStep(next)
  }

  // Mock delivery status animation on step 4
  useEffect(() => {
    if (step !== 4 || !submitted) return
    const ids = Array.from(selectedPlatforms)

    const init = new Map<string, DeliveryStatus>()
    for (const id of ids) init.set(id, 'pending')
    setDeliveryStatus(new Map(init))

    const t1 = setTimeout(() => {
      setDeliveryStatus((prev) => {
        const next = new Map(prev)
        for (const id of ids) next.set(id, 'processing')
        return next
      })
    }, 2000)

    const t2 = setTimeout(() => {
      setDeliveryStatus((prev) => {
        const next = new Map(prev)
        // First half go live
        ids.slice(0, Math.ceil(ids.length / 2)).forEach((id) => next.set(id, 'live'))
        return next
      })
    }, 4000)

    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [step, submitted, selectedPlatforms])

  const togglePlatform = useCallback((id: string) => {
    setSelectedPlatforms((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const selectTier = useCallback((tier: number | 'all' | 'none') => {
    setTierFilter(tier)
    if (tier === 'all') setSelectedPlatforms(new Set(PLATFORMS.map((p) => p.id)))
    else if (tier === 'none') setSelectedPlatforms(new Set())
    else setSelectedPlatforms(new Set(PLATFORMS.filter((p) => p.tier <= (tier as number)).map((p) => p.id)))
  }, [])

  const filteredPlatforms = PLATFORMS.filter((p) =>
    tierFilter === 'all' || tierFilter === 'none' ? true : p.tier <= (tierFilter as number)
  )

  function patchMeta(patch: Partial<Metadata>) {
    setMetadata((prev) => ({ ...prev, ...patch }))
  }

  function handleSubmit() {
    setSubmitted(true)
    goTo(4)
  }

  const statusColor: Record<DeliveryStatus, string> = {
    pending:    'text-rain-amber',
    processing: 'text-rain-cyan',
    live:       'text-rain-green',
  }
  const statusBadge: Record<DeliveryStatus, string> = {
    pending:    'badge-amber',
    processing: 'badge-cyan',
    live:       'badge-green',
  }

  const certId = rainCertId ?? 'RAIN-CERT-DEMO-0000'

  // Est live date (14 days from now)
  const estLive = new Date(Date.now() + 14 * 24 * 3600 * 1000).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })

  return (
    <div className="p-2 w-full page-enter">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Globe size={14} className="text-rain-teal" />
        <span className="text-xs font-semibold text-rain-teal uppercase tracking-widest">Distribute</span>
      </div>

      {/* Stepper */}
      <StepHeader step={step} />
      <div className="mt-8" />

      {/* Step content */}
      <div className="overflow-hidden relative">
        <AnimatePresence custom={slideDir} mode="wait">
          <motion.div
            key={step}
            custom={slideDir}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.28, ease: 'easeInOut' }}
          >

            {/* ── STEP 1: PLATFORMS ──────────────────────────────────────── */}
            {step === 1 && (
              <div className="panel-card">
                <div className="panel-card-header justify-between flex">
                  <span>Target Platforms</span>
                  <div className="flex items-center gap-1.5">
                    {[1, 2, 3].map((t) => (
                      <button
                        key={t}
                        onClick={() => selectTier(t)}
                        className={`px-2 py-1 rounded text-[9px] font-mono font-bold tracking-wider transition-all ${
                          tierFilter === t
                            ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20'
                            : 'text-rain-dim hover:text-rain-text border border-transparent'
                        }`}
                      >
                        T{t}
                      </button>
                    ))}
                    <button
                      onClick={() => selectTier('all')}
                      className={`px-2 py-1 rounded text-[9px] font-mono font-bold tracking-wider transition-all ${
                        tierFilter === 'all'
                          ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20'
                          : 'text-rain-dim hover:text-rain-text border border-transparent'
                      }`}
                    >
                      ALL
                    </button>
                    <button
                      onClick={() => selectTier('none')}
                      className={`px-2 py-1 rounded text-[9px] font-mono font-bold tracking-wider transition-all ${
                        tierFilter === 'none'
                          ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20'
                          : 'text-rain-dim hover:text-rain-text border border-transparent'
                      }`}
                    >
                      NONE
                    </button>
                  </div>
                </div>
                <div className="panel-card-body space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                    {filteredPlatforms.map((platform) => (
                      <button
                        key={platform.id}
                        onClick={() => togglePlatform(platform.id)}
                        disabled={!canDistribute}
                        className={`platform-card ${selectedPlatforms.has(platform.id) ? 'selected' : ''}`}
                      >
                        <span className="platform-dot" style={{ backgroundColor: platform.color }} />
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-semibold text-rain-text truncate">{platform.name}</div>
                          <div className="text-[9px] font-mono text-rain-dim">{platform.lufs} LUFS</div>
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-lg glass-panel">
                    <div>
                      <div className="text-[9px] font-mono text-rain-dim uppercase tracking-wider mb-1">
                        Est. reach
                      </div>
                      <div className="text-2xl font-black text-rain-teal">
                        {estimatedReach(selectedPlatforms)} monthly active users
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-black text-rain-teal">{selectedPlatforms.size}</div>
                      <div className="text-[9px] font-mono text-rain-dim uppercase">Platforms</div>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <button
                      onClick={() => goTo(2)}
                      disabled={selectedPlatforms.size === 0}
                      className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      NEXT →
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ── STEP 2: METADATA ───────────────────────────────────────── */}
            {step === 2 && (
              <div className="panel-card">
                <div className="panel-card-header justify-between flex">
                  <span>Release Metadata</span>
                  <span className="badge badge-cyan text-[8px]">DDEX ERN 4.3.2 AI disclosure auto-populated</span>
                </div>
                <div className="panel-card-body space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                        Release Title <span className="text-rain-red">*</span>
                      </label>
                      <input
                        type="text"
                        placeholder="Track title"
                        value={metadata.title}
                        onChange={(e) => patchMeta({ title: e.target.value })}
                        className="input-field"
                      />
                    </div>
                    <div>
                      <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                        Artist Name <span className="text-rain-red">*</span>
                      </label>
                      <input
                        type="text"
                        placeholder="Primary artist"
                        value={metadata.artist}
                        onChange={(e) => patchMeta({ artist: e.target.value })}
                        className="input-field"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                        ISRC
                      </label>
                      <input
                        type="text"
                        placeholder="XX-XXX-XX-XXXXX"
                        value={metadata.isrc}
                        onChange={(e) => patchMeta({ isrc: formatISRC(e.target.value) })}
                        className="input-field font-mono text-sm"
                        maxLength={15}
                      />
                    </div>
                    <div>
                      <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                        UPC / EAN
                      </label>
                      <input
                        type="text"
                        placeholder="0000000000000"
                        value={metadata.upc}
                        onChange={(e) => patchMeta({ upc: formatUPC(e.target.value) })}
                        className="input-field font-mono text-sm"
                        maxLength={13}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                      Album Title
                    </label>
                    <input
                      type="text"
                      placeholder="Optional"
                      value={metadata.album}
                      onChange={(e) => patchMeta({ album: e.target.value })}
                      className="input-field"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                        Genre
                      </label>
                      <select
                        value={metadata.genre}
                        onChange={(e) => patchMeta({ genre: e.target.value })}
                        className="input-field"
                      >
                        {GENRES.map((g) => <option key={g}>{g}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                        Release Date
                      </label>
                      <input
                        type="date"
                        value={metadata.releaseDate}
                        onChange={(e) => patchMeta({ releaseDate: e.target.value })}
                        className="input-field"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-[9px] font-mono text-rain-silver block mb-1 uppercase tracking-wider">
                      Copyright
                    </label>
                    <input
                      type="text"
                      placeholder="© 2026 Artist Name"
                      value={metadata.copyright}
                      onChange={(e) => patchMeta({ copyright: e.target.value })}
                      className="input-field"
                    />
                  </div>

                  <div className="flex flex-wrap items-center gap-4">
                    <label className="flex items-center gap-2 text-xs text-rain-silver cursor-pointer">
                      <input
                        type="checkbox"
                        checked={metadata.explicit}
                        onChange={(e) => patchMeta({ explicit: e.target.checked })}
                        className="accent-rain-teal"
                      />
                      Explicit content
                    </label>
                    <label className="flex items-center gap-2 text-xs text-rain-silver cursor-pointer">
                      <input
                        type="checkbox"
                        checked={metadata.aiGenerated}
                        onChange={(e) => patchMeta({ aiGenerated: e.target.checked })}
                        className="accent-rain-teal"
                      />
                      AI-processed: mastering (RAIN)
                    </label>
                  </div>

                  <div className="flex justify-between pt-2">
                    <button onClick={() => goTo(1)} className="btn-ghost">← BACK</button>
                    <button
                      onClick={() => goTo(3)}
                      disabled={!metadata.title || !metadata.artist}
                      className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      NEXT →
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ── STEP 3: REVIEW ─────────────────────────────────────────── */}
            {step === 3 && (
              <div className="panel-card">
                <div className="panel-card-header">Review & Submit</div>
                <div className="panel-card-body space-y-4">
                  {/* Summary */}
                  <div className="p-4 rounded-lg glass-panel space-y-1">
                    <div className="text-xs font-semibold text-rain-text">
                      {metadata.title || '(untitled)'} — {metadata.artist || '(unknown artist)'}
                    </div>
                    {metadata.album && (
                      <div className="text-[10px] font-mono text-rain-silver">{metadata.album}</div>
                    )}
                    <div className="flex flex-wrap gap-2 mt-2">
                      <span className="badge badge-teal">{selectedPlatforms.size} Platforms</span>
                      <span className="badge badge-outline">{metadata.genre}</span>
                      {metadata.releaseDate && (
                        <span className="badge badge-outline">{metadata.releaseDate}</span>
                      )}
                      {metadata.explicit && <span className="badge badge-red">EXPLICIT</span>}
                    </div>
                  </div>

                  {/* Cert badges */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="flex items-center gap-2 p-3 rounded-lg glass-panel">
                      <div className="w-5 h-5 rounded-full bg-rain-green/20 border border-rain-green/40 flex items-center justify-center shrink-0">
                        <Check size={10} className="text-rain-green" />
                      </div>
                      <div>
                        <div className="text-[9px] font-mono font-bold text-rain-green">RAIN-CERT Signed</div>
                        <div className="text-[8px] font-mono text-rain-muted">{certId}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 p-3 rounded-lg glass-panel">
                      <div className="w-5 h-5 rounded-full bg-rain-cyan/20 border border-rain-cyan/40 flex items-center justify-center shrink-0">
                        <Check size={10} className="text-rain-cyan" />
                      </div>
                      <div className="text-[9px] font-mono font-bold text-rain-cyan">C2PA v2.2 Manifest attached</div>
                    </div>
                    <div className="flex items-center gap-2 p-3 rounded-lg glass-panel">
                      <div className="w-5 h-5 rounded-full bg-rain-purple/20 border border-rain-purple/40 flex items-center justify-center shrink-0">
                        <Check size={10} className="text-rain-purple" />
                      </div>
                      <div className="text-[9px] font-mono font-bold text-rain-purple">DDEX ERN 4.3.2 Ready</div>
                    </div>
                  </div>

                  {/* Cost */}
                  <div className="p-3 rounded-lg glass-panel flex items-center justify-between">
                    <span className="text-[10px] font-mono text-rain-silver uppercase tracking-wider">Distribution Cost</span>
                    <span className="text-xl font-black text-rain-teal">$0 / platform</span>
                  </div>

                  {/* Terms */}
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={termsChecked}
                      onChange={(e) => setTermsChecked(e.target.checked)}
                      className="accent-rain-teal mt-0.5"
                    />
                    <span className="text-[10px] text-rain-silver leading-relaxed">
                      I confirm this release complies with platform policies and AI disclosure requirements.
                    </span>
                  </label>

                  <div className="flex justify-between pt-2">
                    <button onClick={() => goTo(2)} className="btn-ghost">← BACK</button>
                    <button
                      onClick={handleSubmit}
                      disabled={!termsChecked || !canDistribute}
                      className="btn-gradient disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      SUBMIT FOR DISTRIBUTION
                    </button>
                  </div>

                  {!canDistribute && (
                    <p className="text-[10px] font-mono text-rain-amber text-center">
                      Distribution requires <span className="text-rain-teal font-bold">Studio Pro</span>+ tier.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* ── STEP 4: STATUS ─────────────────────────────────────────── */}
            {step === 4 && (
              <div className="panel-card">
                <div className="panel-card-header">Delivery Status</div>
                <div className="panel-card-body space-y-4">
                  {/* Per-platform table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-[10px] font-mono">
                      <thead>
                        <tr className="text-rain-muted uppercase tracking-wider border-b border-rain-border">
                          <th className="text-left py-2 pr-3">Platform</th>
                          <th className="text-left py-2 pr-3">Submitted</th>
                          <th className="text-left py-2 pr-3">Status</th>
                          <th className="text-left py-2">Est. Live</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Array.from(selectedPlatforms).map((id) => {
                          const p = PLATFORMS.find((pl) => pl.id === id)
                          if (!p) return null
                          const ds = deliveryStatus.get(id) ?? 'pending'
                          return (
                            <tr key={id} className="border-b border-rain-border/50">
                              <td className="py-1.5 pr-3 flex items-center gap-1.5">
                                <span
                                  className="w-2 h-2 rounded-full shrink-0"
                                  style={{ backgroundColor: p.color }}
                                />
                                {p.name}
                              </td>
                              <td className="py-1.5 pr-3 text-rain-silver">
                                {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                              </td>
                              <td className="py-1.5 pr-3">
                                <AnimatePresence mode="wait">
                                  <motion.span
                                    key={ds}
                                    initial={{ opacity: 0, scale: 0.8 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.8 }}
                                    transition={{ duration: 0.2 }}
                                    className={`badge ${statusBadge[ds]} text-[8px] ${statusColor[ds]}`}
                                  >
                                    {ds.toUpperCase()}
                                  </motion.span>
                                </AnimatePresence>
                              </td>
                              <td className="py-1.5 text-rain-dim">{estLive}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* ISRC link */}
                  {metadata.isrc && (
                    <p className="text-[9px] font-mono text-rain-dim">
                      Track your release · ISRC: <span className="text-rain-teal">{metadata.isrc}</span>
                    </p>
                  )}

                  <button
                    onClick={() => {
                      setSubmitted(false)
                      setTermsChecked(false)
                      setMetadata({
                        title: '', artist: '', album: '', genre: 'Electronic',
                        releaseDate: '', isrc: '', upc: '',
                        explicit: false, aiGenerated: true, copyright: '',
                      })
                      setSelectedPlatforms(new Set(['spotify', 'apple_music', 'youtube_music', 'tidal', 'amazon']))
                      goTo(1)
                    }}
                    className="btn-ghost w-full"
                  >
                    Distribute Another Track
                  </button>
                </div>
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
