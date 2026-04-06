import { useState, useCallback, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { TierGate } from '../common/TierGate'

// ─── Types ───────────────────────────────────────────────────────────────────

type SeparationStatus = 'idle' | 'separating' | 'ready'

interface EqBands {
  low: number
  mid: number
  high: number
}

interface StemState {
  id: string
  label: string
  color: string
  muted: boolean
  solo: boolean
  gain: number   // -12 to +12 dB
  pan: number    // -100 to +100
  eq: EqBands
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STEM_DEFS: Omit<StemState, 'muted' | 'solo' | 'gain' | 'pan' | 'eq'>[] = [
  { id: 'vocals',  label: 'VOCALS',  color: '#8B5CF6' },
  { id: 'drums',   label: 'DRUMS',   color: '#F97316' },
  { id: 'bass',    label: 'BASS',    color: '#FF4444' },
  { id: 'guitar',  label: 'GUITAR',  color: '#00D4AA' },
  { id: 'piano',   label: 'PIANO',   color: '#4A9EFF' },
  { id: 'other',   label: 'OTHER',   color: '#AAFF00' },
]

const SEPARATION_STEPS = [
  'Loading model...',
  'Analyzing spectrum...',
  'Extracting stems...',
  'Normalizing...',
]

function makeStem(def: (typeof STEM_DEFS)[number]): StemState {
  return {
    ...def,
    muted: false,
    solo: false,
    gain: 0,
    pan: 0,
    eq: { low: 0, mid: 0, high: 0 },
  }
}

// ─── Waveform SVG ─────────────────────────────────────────────────────────────

function WaveformSvg({ color, seed }: { color: string; seed: number }) {
  // Deterministic pseudo-random sine squiggle per stem
  const points = Array.from({ length: 60 }, (_, i) => {
    const x = (i / 59) * 220
    const phase = (seed * 1.7 + i * 0.4)
    const amp = 14 + Math.sin(phase * 0.9) * 8 + Math.sin(phase * 2.1) * 5
    const y = 20 + Math.sin(phase) * amp
    return `${x},${y}`
  })
  return (
    <svg viewBox="0 0 220 40" className="w-full h-8 opacity-30" preserveAspectRatio="none">
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// ─── EQ Panel ─────────────────────────────────────────────────────────────────

interface EqPanelProps {
  eq: EqBands
  color: string
  onChange: (band: keyof EqBands, val: number) => void
}

function EqPanel({ eq, color, onChange }: EqPanelProps) {
  const bands: { key: keyof EqBands; label: string }[] = [
    { key: 'low',  label: 'LOW SHELF' },
    { key: 'mid',  label: 'MID PEAK'  },
    { key: 'high', label: 'HI SHELF'  },
  ]
  return (
    <motion.div
      key="eq-panel"
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.22, ease: 'easeInOut' }}
      className="overflow-hidden"
    >
      <div
        className="mt-2 rounded-lg p-3 space-y-2"
        style={{ background: `${color}0D`, border: `1px solid ${color}25` }}
      >
        {bands.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-3">
            <span className="text-[9px] font-mono w-16 shrink-0" style={{ color }}>
              {label}
            </span>
            <input
              type="range"
              min={-6}
              max={6}
              step={0.5}
              value={eq[key]}
              onChange={(e) => onChange(key, Number(e.target.value))}
              className="rain-slider flex-1"
            />
            <span className="text-[9px] font-mono tabular-nums w-10 text-right text-rain-silver">
              {eq[key] > 0 ? '+' : ''}{eq[key].toFixed(1)} dB
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function StemsTab() {
  const [separationStatus, setSeparationStatus] = useState<SeparationStatus>('ready')
  const [progress, setProgress] = useState(0)
  const [stepIndex, setStepIndex] = useState(0)
  const [stems, setStems] = useState<StemState[]>(STEM_DEFS.map(makeStem))
  const [activeEqStem, setActiveEqStem] = useState<string | null>(null)
  const [masterGain, setMasterGain] = useState(0)
  const [sailEnabled, setSailEnabled] = useState(false)
  const [inferenceBackend] = useState<'WEBGPU' | 'WASM'>('WEBGPU')

  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Compute which stems are audible considering solo/mute logic
  const hasSolo = stems.some((s) => s.solo)
  const playingStems = new Set<string>(
    stems.filter((s) => {
      if (s.muted) return false
      if (hasSolo && !s.solo) return false
      return true
    }).map((s) => s.id)
  )

  const sail_stem_gains = stems.map((s) => parseFloat(s.gain.toFixed(1)))

  const updateStem = useCallback((id: string, patch: Partial<StemState>) => {
    setStems((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)))
  }, [])

  const updateEq = useCallback((id: string, band: keyof EqBands, val: number) => {
    setStems((prev) =>
      prev.map((s) => (s.id === id ? { ...s, eq: { ...s.eq, [band]: val } } : s))
    )
  }, [])

  const startSeparation = useCallback(() => {
    if (separationStatus === 'separating') return
    setSeparationStatus('separating')
    setProgress(0)
    setStepIndex(0)

    let p = 0
    let step = 0
    progressRef.current = setInterval(() => {
      p += 1.2
      if (p >= 100) {
        p = 100
        clearInterval(progressRef.current!)
        setSeparationStatus('ready')
      } else {
        const newStep = Math.floor((p / 100) * SEPARATION_STEPS.length)
        if (newStep !== step && newStep < SEPARATION_STEPS.length) {
          step = newStep
          setStepIndex(step)
        }
      }
      setProgress(p)
    }, 60)
  }, [separationStatus])

  useEffect(() => {
    return () => {
      if (progressRef.current) clearInterval(progressRef.current)
    }
  }, [])

  const panLabel = (pan: number): string => {
    if (pan < -10) return `L${Math.abs(pan)}`
    if (pan > 10) return `R${pan}`
    return 'C'
  }

  return (
    <TierGate requiredTier="creator" feature="Stem mastering">
      <div className="p-2 space-y-3 w-full">

        {/* ── Top Bar ─────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-xs font-mono text-rain-silver tracking-widest uppercase flex-1">
            6-STEM SEPARATION — DEMUCS HTDEMUCS_6S
          </h2>
          <span className="badge badge-cyan text-[9px]">{inferenceBackend}</span>
          <button
            onClick={startSeparation}
            disabled={separationStatus === 'separating'}
            className="px-4 py-1.5 rounded text-[11px] font-mono font-bold tracking-wider text-rain-black
              bg-gradient-to-r from-rain-teal to-rain-cyan shadow-glow-teal
              hover:from-rain-cyan hover:to-rain-green transition-all
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            SEPARATE
          </button>
        </div>

        {/* ── Separation Phase ─────────────────────────────────────────────── */}
        <AnimatePresence>
          {separationStatus === 'separating' && (
            <motion.div
              key="separation-phase"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="panel-card"
            >
              <div className="panel-card-body space-y-3">
                {/* Progress bar */}
                <div className="h-2 rounded-full overflow-hidden bg-rain-border">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      background: 'linear-gradient(90deg, #00D4AA, #00E5C8)',
                      boxShadow: '0 0 10px rgba(0,212,170,0.5)',
                    }}
                    animate={{ width: `${progress}%` }}
                    transition={{ ease: 'linear', duration: 0.06 }}
                  />
                </div>

                {/* Step label */}
                <AnimatePresence mode="wait">
                  <motion.span
                    key={stepIndex}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.2 }}
                    className="text-[10px] font-mono text-rain-cyan block"
                  >
                    {SEPARATION_STEPS[stepIndex]} — {Math.round(progress)}%
                  </motion.span>
                </AnimatePresence>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Stem Mixer ───────────────────────────────────────────────────── */}
        <div className="space-y-2">
          {stems.map((stem, idx) => {
            const isAudible = playingStems.has(stem.id)
            return (
              <motion.div
                key={stem.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.04, duration: 0.25 }}
                className="panel-card"
              >
                <div className="panel-card-body space-y-0">

                  {/* Row: color dot | label | waveform | M | S | gain | pan | EQ */}
                  <div className="flex items-center gap-2 min-w-0">

                    {/* Color dot + label */}
                    <div className="flex items-center gap-1.5 w-20 shrink-0">
                      <motion.div
                        animate={{ opacity: isAudible ? 1 : 0.3 }}
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: stem.color, boxShadow: isAudible ? `0 0 6px ${stem.color}66` : 'none' }}
                      />
                      <span
                        className="text-[9px] font-mono tracking-widest uppercase font-bold"
                        style={{ color: isAudible ? stem.color : '#3A4A3A' }}
                      >
                        {stem.label}
                      </span>
                    </div>

                    {/* Waveform */}
                    <div className="flex-1 min-w-0 overflow-hidden">
                      <WaveformSvg color={stem.color} seed={idx * 13 + 7} />
                    </div>

                    {/* Mute */}
                    <button
                      onClick={() => updateStem(stem.id, { muted: !stem.muted })}
                      className={`w-6 h-6 rounded text-[9px] font-mono font-bold border transition-colors ${
                        stem.muted
                          ? 'bg-rain-red/20 border-rain-red/40 text-rain-red'
                          : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                      }`}
                    >
                      M
                    </button>

                    {/* Solo */}
                    <button
                      onClick={() => updateStem(stem.id, { solo: !stem.solo })}
                      className={`w-6 h-6 rounded text-[9px] font-mono font-bold border transition-colors ${
                        stem.solo
                          ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400'
                          : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                      }`}
                    >
                      S
                    </button>

                    {/* Gain fader */}
                    <div className="flex items-center gap-1.5 w-36 shrink-0">
                      <span className="text-[8px] font-mono text-rain-muted w-7 shrink-0">GAIN</span>
                      <input
                        type="range"
                        min={-12}
                        max={12}
                        step={0.1}
                        value={stem.gain}
                        onChange={(e) => updateStem(stem.id, { gain: Number(e.target.value) })}
                        className="rain-slider flex-1"
                      />
                      <span className="text-[8px] font-mono tabular-nums w-10 text-right text-rain-silver">
                        {stem.gain > 0 ? '+' : ''}{stem.gain.toFixed(1)}dB
                      </span>
                    </div>

                    {/* Pan */}
                    <div className="flex items-center gap-1 w-24 shrink-0">
                      <span className="text-[8px] font-mono text-rain-muted w-6 shrink-0">PAN</span>
                      <input
                        type="range"
                        min={-100}
                        max={100}
                        step={1}
                        value={stem.pan}
                        onChange={(e) => updateStem(stem.id, { pan: Number(e.target.value) })}
                        className="rain-slider flex-1"
                      />
                      <span className="text-[8px] font-mono tabular-nums w-8 text-right text-rain-silver">
                        {panLabel(stem.pan)}
                      </span>
                    </div>

                    {/* EQ toggle */}
                    <button
                      onClick={() => setActiveEqStem(activeEqStem === stem.id ? null : stem.id)}
                      className={`w-7 h-6 rounded text-[8px] font-mono border transition-colors shrink-0 ${
                        activeEqStem === stem.id
                          ? 'border-rain-teal/50 text-rain-teal bg-rain-teal/10'
                          : 'border-rain-border text-rain-dim hover:text-rain-text'
                      }`}
                      title="EQ"
                    >
                      EQ
                    </button>
                  </div>

                  {/* EQ Panel */}
                  <AnimatePresence>
                    {activeEqStem === stem.id && (
                      <EqPanel
                        eq={stem.eq}
                        color={stem.color}
                        onChange={(band, val) => updateEq(stem.id, band, val)}
                      />
                    )}
                  </AnimatePresence>

                </div>
              </motion.div>
            )
          })}
        </div>

        {/* ── Global Controls Bar ──────────────────────────────────────────── */}
        <div className="panel-card">
          <div className="panel-card-header">GLOBAL CONTROLS</div>
          <div className="panel-card-body flex flex-wrap items-center gap-4">

            {/* Master gain */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-mono text-rain-silver uppercase tracking-wider">MASTER</span>
              <input
                type="range"
                min={-12}
                max={12}
                step={0.1}
                value={masterGain}
                onChange={(e) => setMasterGain(Number(e.target.value))}
                className="rain-slider w-28"
              />
              <span className="text-[9px] font-mono tabular-nums text-rain-silver">
                {masterGain > 0 ? '+' : ''}{masterGain.toFixed(1)} dB
              </span>
            </div>

            {/* Apply to master */}
            <div className="relative group">
              <button className="px-3 py-1.5 rounded text-[10px] font-mono font-bold text-rain-black
                bg-gradient-to-r from-rain-teal to-rain-cyan hover:from-rain-cyan hover:to-rain-green transition-all">
                APPLY TO MASTER
              </button>
              <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block z-10 w-max max-w-xs">
                <div className="bg-rain-surface border border-rain-border rounded px-3 py-2">
                  <code className="text-[9px] font-mono text-rain-cyan">
                    sail_stem_gains = [{sail_stem_gains.join(', ')}]
                  </code>
                </div>
              </div>
            </div>

            {/* SAIL toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <div
                onClick={() => setSailEnabled((v) => !v)}
                className={`w-10 h-5 rounded-full border transition-colors cursor-pointer relative ${
                  sailEnabled
                    ? 'bg-rain-teal/30 border-rain-teal/50'
                    : 'bg-rain-bg border-rain-border'
                }`}
              >
                <motion.div
                  animate={{ x: sailEnabled ? 20 : 2 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  className="absolute top-0.5 w-4 h-4 rounded-full"
                  style={{ background: sailEnabled ? '#00D4AA' : '#3A4A3A' }}
                />
              </div>
              <span className="text-[10px] font-mono text-rain-silver">SAIL ENABLED</span>
            </label>

            {/* Gain array display */}
            <code className="text-[9px] font-mono text-rain-muted ml-auto">
              sail_stem_gains = [{sail_stem_gains.join(', ')}]
            </code>
          </div>
        </div>

      </div>
    </TierGate>
  )
}
