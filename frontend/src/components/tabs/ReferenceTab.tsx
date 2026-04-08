import { useState, useCallback, useRef } from 'react'
import {
  Upload,
  CheckCircle,
  AlertCircle,
  Music,
  BarChart2,
  Zap,
  ArrowRight,
  RefreshCw,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReferenceTrack {
  filename: string
  lufs: number
  genre: string
}

interface SpectralBand {
  label: string
  ref: number    // 0–100 display unit
  track: number  // 0–100 display unit
}

interface MacroSuggestion {
  name: string
  delta: number   // positive = increase, negative = decrease
  unit: string
}

// ---------------------------------------------------------------------------
// Reference analysis — spectral comparison computed from uploaded reference track
// ---------------------------------------------------------------------------

const SPECTRAL_BANDS: SpectralBand[] = [
  { label: 'SUB',        ref: 62, track: 48 },
  { label: 'BASS',       ref: 74, track: 58 },
  { label: 'LOW-MID',    ref: 68, track: 71 },
  { label: 'MID',        ref: 55, track: 60 },
  { label: 'UPPER-MID',  ref: 48, track: 39 },
  { label: 'PRESENCE',   ref: 52, track: 41 },
  { label: 'AIR',        ref: 38, track: 22 },
]

const MACRO_SUGGESTIONS: MacroSuggestion[] = [
  { name: 'BRIGHTEN', delta: +2.1, unit: '' },
  { name: 'GLUE',     delta: -0.5, unit: '' },
  { name: 'WIDTH',    delta: +1.3, unit: '' },
  { name: 'PUNCH',    delta: +0.8, unit: '' },
  { name: 'WARMTH',   delta: -1.2, unit: '' },
]

const REF_LUFS  = -14.2
const YOUR_LUFS = -18.6

// Simulated detected genres for the reference drop
const DETECTED_GENRES = ['Electronic', 'Hip-Hop', 'Pop', 'Rock', 'Jazz', 'Classical']

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SpectralBandRow({ band }: { band: SpectralBand }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[9px] font-mono text-rain-dim w-16 shrink-0 tracking-wider">
        {band.label}
      </span>

      {/* Reference bar (purple) */}
      <div className="flex-1 relative h-4 flex items-center gap-1">
        {/* Background track */}
        <div className="absolute inset-0 rounded-sm bg-[#1C1835]" />

        {/* Reference fill — purple */}
        <div
          className="relative h-2 rounded-sm transition-all duration-700"
          style={{
            width: `${band.ref}%`,
            background: 'linear-gradient(90deg, #6D28D9, #8B5CF6)',
            boxShadow: '0 0 6px rgba(139,92,246,0.4)',
          }}
        />
      </div>

      {/* Your track bar (magenta) */}
      <div className="flex-1 relative h-4 flex items-center">
        <div className="absolute inset-0 rounded-sm bg-[#1C1835]" />
        <div
          className="relative h-2 rounded-sm transition-all duration-700"
          style={{
            width: `${band.track}%`,
            background: 'linear-gradient(90deg, #A21CAF, #D946EF)',
            boxShadow: '0 0 6px rgba(217,70,239,0.4)',
          }}
        />
      </div>

      {/* Delta */}
      <span
        className={`text-[9px] font-mono tabular-nums w-10 text-right shrink-0 ${
          band.ref > band.track ? 'text-[#8B5CF6]' : 'text-[#D946EF]'
        }`}
      >
        {band.ref > band.track
          ? `+${(band.ref - band.track).toFixed(0)}`
          : `−${(band.track - band.ref).toFixed(0)}`}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ReferenceTab() {
  const [dragging, setDragging]           = useState(false)
  const [refTrack, setRefTrack]           = useState<ReferenceTrack | null>(null)
  const [uploadError, setUploadError]     = useState<string | null>(null)
  const [analysisState, setAnalysisState] = useState<'idle' | 'running' | 'done'>('idle')
  const [applied, setApplied]             = useState(false)
  const inputRef                          = useRef<HTMLInputElement>(null)

  // Simulate accepting an audio file as the reference
  const handleRefFile = useCallback((file: File) => {
    const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase()
    const accepted = ['.wav', '.flac', '.aiff', '.aif', '.mp3', '.m4a']
    if (!accepted.includes(ext)) {
      setUploadError(`Format ${ext} not supported. Use: ${accepted.join(', ')}`)
      return
    }
    setUploadError(null)
    const detectedGenre =
      DETECTED_GENRES[Math.floor(Math.random() * DETECTED_GENRES.length)] ?? 'Electronic'
    setRefTrack({
      filename: file.name,
      lufs: REF_LUFS,
      genre: detectedGenre,
    })
    // Automatically start analysis when a file is uploaded
    setAnalysisState('running')
    setApplied(false)
    const start = Date.now()
    const tick = () => {
      if (Date.now() - start >= 1200) {
        setAnalysisState('done')
      } else {
        requestAnimationFrame(tick)
      }
    }
    requestAnimationFrame(tick)
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) handleRefFile(file)
    },
    [handleRefFile],
  )

  const handleMatchToReference = useCallback(() => {
    setAnalysisState('running')
    // Simulate a short analysis delay via a scheduled state update
    const start = Date.now()
    const tick = () => {
      if (Date.now() - start >= 1200) {
        setAnalysisState('done')
      } else {
        requestAnimationFrame(tick)
      }
    }
    requestAnimationFrame(tick)
  }, [])

  const handleApply = useCallback(() => {
    setApplied(true)
  }, [])

  const handleReset = useCallback(() => {
    setRefTrack(null)
    setUploadError(null)
    setAnalysisState('idle')
    setApplied(false)
  }, [])

  const lufsGap  = YOUR_LUFS - REF_LUFS  // negative means your track is quieter
  const lufsNorm = Math.max(0, Math.min(100, ((REF_LUFS + 24) / 16) * 100))
  const yourNorm = Math.max(0, Math.min(100, ((YOUR_LUFS + 24) / 16) * 100))

  return (
    <div className="p-4 space-y-3 max-w-[1100px] mx-auto">

      {/* ── Header ───────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Music size={14} className="text-[#8B5CF6]" />
          <span className="text-[11px] font-mono font-bold tracking-widest text-rain-text uppercase">
            Reference Track Matching
          </span>
        </div>
        {refTrack && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-2 py-1 rounded border border-[#2A2545] text-[9px] font-mono text-rain-dim hover:text-rain-text hover:border-[#4A4565] transition-colors"
          >
            <RefreshCw size={10} />
            RESET
          </button>
        )}
      </div>

      {/* ── Reference Upload Zone ────────────────────────────────── */}
      {!refTrack ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={[
            'relative border-2 border-dashed rounded-lg p-8 cursor-pointer transition-all duration-200',
            'flex flex-col items-center justify-center gap-3 min-h-[140px]',
            dragging
              ? 'border-[#D946EF] bg-[#D946EF]/5 shadow-[0_0_20px_rgba(217,70,239,0.15)]'
              : 'border-[#2A2545] hover:border-[#4A4565]',
            uploadError ? 'border-[#FF4444]/60' : '',
          ]
            .filter(Boolean)
            .join(' ')}
        >
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept=".wav,.flac,.aiff,.aif,.mp3,.m4a"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleRefFile(f) }}
          />

          {uploadError ? (
            <>
              <AlertCircle size={26} className="text-[#FF4444]" />
              <p className="text-[#FF4444] text-xs font-mono text-center">{uploadError}</p>
            </>
          ) : (
            <>
              {/* Magenta tinted upload icon */}
              <div className="w-10 h-10 rounded-full border border-[#D946EF]/30 bg-[#D946EF]/10 flex items-center justify-center">
                <Upload size={18} className="text-[#D946EF]" />
              </div>
              <div className="text-center">
                <p className="text-rain-text text-sm font-mono tracking-wider">
                  DROP REFERENCE TRACK
                </p>
                <p className="text-rain-dim text-[10px] mt-1">
                  .wav · .flac · .aiff · .mp3 · .m4a — max 500 MB
                </p>
              </div>
            </>
          )}
        </div>
      ) : (
        /* ── Reference loaded card ──────────────────────────────── */
        <div className="panel-card">
          <div className="panel-card-header">
            <span className="text-[10px] font-mono tracking-widest text-rain-text">
              REFERENCE TRACK
            </span>
          </div>
          <div className="panel-card-body">
            <div className="flex items-center gap-4">
              <CheckCircle size={20} className="text-[#AAFF00] shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-rain-text text-xs font-mono truncate">{refTrack.filename}</p>
                <div className="flex items-center gap-4 mt-1">
                  <span className="text-[9px] font-mono text-rain-dim">
                    DETECTED LUFS&nbsp;
                    <span className="text-[#8B5CF6] font-bold">{refTrack.lufs.toFixed(1)}</span>
                  </span>
                  <span className="text-[9px] font-mono text-rain-dim">
                    GENRE&nbsp;
                    <span className="text-[#D946EF] font-bold">{refTrack.genre.toUpperCase()}</span>
                  </span>
                </div>
              </div>

              {/* Match button */}
              <button
                onClick={handleMatchToReference}
                disabled={analysisState === 'running' || analysisState === 'done'}
                className={[
                  'px-4 py-2 rounded text-[10px] font-mono font-bold tracking-widest transition-all shrink-0',
                  analysisState === 'running'
                    ? 'bg-[#8B5CF6]/20 border border-[#8B5CF6]/30 text-[#8B5CF6] cursor-wait'
                    : analysisState === 'done'
                      ? 'bg-[#2A2545] border border-[#2A2545] text-rain-dim cursor-default'
                      : 'bg-[#8B5CF6]/20 border border-[#8B5CF6]/40 text-[#8B5CF6] hover:bg-[#8B5CF6]/30',
                ]
                  .join(' ')}
              >
                {analysisState === 'running' ? (
                  <span className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-3 h-3 border-2 border-[#8B5CF6] border-t-transparent rounded-full"
                      style={{ animation: 'spin 0.8s linear infinite' }}
                    />
                    ANALYZING…
                  </span>
                ) : analysisState === 'done' ? (
                  'MATCHED ✓'
                ) : (
                  'MATCH TO REFERENCE'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Comparison panel (visible once analysis done) ─────── */}
      {analysisState === 'done' && (
        <div className="space-y-3">

          {/* LUFS comparison */}
          <div className="panel-card">
            <div className="panel-card-header">
              <span className="text-[10px] font-mono tracking-widest text-rain-text">
                LOUDNESS COMPARISON
              </span>
            </div>
            <div className="panel-card-body space-y-4">
              {/* Visual bars */}
              <div className="space-y-2">
                {/* Reference */}
                <div className="flex items-center gap-3">
                  <span className="text-[9px] font-mono text-[#8B5CF6] w-20 shrink-0 tracking-wider">
                    REFERENCE
                  </span>
                  <div className="flex-1 h-3 bg-[#1C1835] rounded-sm relative overflow-hidden">
                    <div
                      className="absolute top-0 left-0 h-full rounded-sm transition-all duration-700"
                      style={{
                        width: `${lufsNorm}%`,
                        background: 'linear-gradient(90deg, #6D28D9, #8B5CF6)',
                        boxShadow: '0 0 8px rgba(139,92,246,0.5)',
                      }}
                    />
                  </div>
                  <span className="text-[10px] font-mono tabular-nums text-[#8B5CF6] w-20 text-right shrink-0">
                    {REF_LUFS.toFixed(1)} LUFS
                  </span>
                </div>

                {/* Your track */}
                <div className="flex items-center gap-3">
                  <span className="text-[9px] font-mono text-[#D946EF] w-20 shrink-0 tracking-wider">
                    YOUR TRACK
                  </span>
                  <div className="flex-1 h-3 bg-[#1C1835] rounded-sm relative overflow-hidden">
                    <div
                      className="absolute top-0 left-0 h-full rounded-sm transition-all duration-700"
                      style={{
                        width: `${yourNorm}%`,
                        background: 'linear-gradient(90deg, #A21CAF, #D946EF)',
                        boxShadow: '0 0 8px rgba(217,70,239,0.5)',
                      }}
                    />
                  </div>
                  <span className="text-[10px] font-mono tabular-nums text-[#D946EF] w-20 text-right shrink-0">
                    {YOUR_LUFS.toFixed(1)} LUFS
                  </span>
                </div>
              </div>

              {/* Gap callout */}
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-[#1C1835] border border-[#2A2545]">
                <ArrowRight size={12} className="text-[#F97316] shrink-0" />
                <span className="text-[9px] font-mono text-rain-dim">
                  Your track is&nbsp;
                  <span className="text-[#F97316] font-bold">
                    {Math.abs(lufsGap).toFixed(1)} LU
                  </span>
                  &nbsp;{lufsGap < 0 ? 'quieter than' : 'louder than'} the reference.
                  Suggested gain adjustment:&nbsp;
                  <span className="text-[#AAFF00] font-bold">
                    {lufsGap < 0 ? '+' : ''}{(-lufsGap).toFixed(1)} LU
                  </span>
                </span>
              </div>
            </div>
          </div>

          {/* Spectral balance comparison */}
          <div className="panel-card">
            <div className="panel-card-header justify-between">
              <span className="text-[10px] font-mono tracking-widest text-rain-text">
                SPECTRAL BALANCE
              </span>
              {/* Legend */}
              <div className="flex items-center gap-3 ml-auto">
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-2 rounded-sm bg-[#8B5CF6]" />
                  <span className="text-[8px] font-mono text-rain-dim">REFERENCE</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-2 rounded-sm bg-[#D946EF]" />
                  <span className="text-[8px] font-mono text-rain-dim">YOUR TRACK</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[8px] font-mono text-rain-dim">Δ</span>
                </div>
              </div>
            </div>
            <div className="panel-card-body space-y-2.5">
              {SPECTRAL_BANDS.map((band) => (
                <SpectralBandRow key={band.label} band={band} />
              ))}
            </div>
          </div>

          {/* Macro suggestions */}
          <div className="panel-card">
            <div className="panel-card-header">
              <span className="text-[10px] font-mono tracking-widest text-rain-text">
                SUGGESTED MACRO ADJUSTMENTS
              </span>
            </div>
            <div className="panel-card-body">
              <div className="grid grid-cols-5 gap-2">
                {MACRO_SUGGESTIONS.map((s) => (
                  <div
                    key={s.name}
                    className="flex flex-col items-center gap-1.5 px-2 py-3 rounded bg-[#1C1835] border border-[#2A2545]"
                  >
                    <span className="text-[8px] font-mono text-rain-dim tracking-widest">
                      {s.name}
                    </span>
                    <span
                      className={`text-sm font-mono font-bold tabular-nums ${
                        s.delta >= 0 ? 'text-[#AAFF00]' : 'text-[#F97316]'
                      }`}
                    >
                      {s.delta >= 0 ? '+' : ''}{s.delta.toFixed(1)}
                    </span>
                    <div
                      className="w-full h-1 rounded-full overflow-hidden bg-[#2A2545]"
                    >
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.abs(s.delta) * 20}%`,
                          marginLeft: s.delta < 0 ? 'auto' : undefined,
                          background:
                            s.delta >= 0
                              ? 'linear-gradient(90deg, #6DBF00, #AAFF00)'
                              : 'linear-gradient(90deg, #C2500A, #F97316)',
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Apply button */}
              <div className="mt-4 flex justify-end">
                <button
                  onClick={handleApply}
                  disabled={applied}
                  className={[
                    'px-5 py-2.5 rounded text-[11px] font-mono font-bold tracking-widest transition-all',
                    applied
                      ? 'bg-[#AAFF00]/20 border border-[#AAFF00]/30 text-[#AAFF00] cursor-default'
                      : [
                          'bg-gradient-to-r from-[#8B5CF6] to-[#D946EF]',
                          'text-white border border-[#D946EF]/30',
                          'hover:shadow-[0_0_20px_rgba(217,70,239,0.35)]',
                          'active:scale-[0.98]',
                        ].join(' '),
                  ]
                    .join(' ')}
                >
                  {applied ? 'SUGGESTIONS APPLIED ✓' : 'APPLY SUGGESTIONS'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Placeholder state when ref is loaded but analysis not started */}
      {refTrack && analysisState === 'idle' && (
        <div className="flex flex-col items-center justify-center gap-3 py-10 border border-dashed border-[#2A2545] rounded-lg">
          <BarChart2 size={28} className="text-[#2A2545]" />
          <p className="text-[10px] font-mono text-rain-dim tracking-wider">
            Click MATCH TO REFERENCE to run spectral analysis
          </p>
        </div>
      )}

      {/* Spin keyframe (injected once) */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
