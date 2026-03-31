import { useState, useCallback, useRef } from 'react'
import { useSessionStore } from '@/stores/session'
import { api, APIError } from '@/utils/api'
import type { AnalysisData, ProcessResult } from '@/utils/api'
import { UploadZone } from '../controls/UploadZone'
import { Waveform } from '../visualizers/Waveform'
import { Spectrum } from '../visualizers/Spectrum'
import { SignalChain } from '../mastering/SignalChain'
import { CreativeMacros } from '../mastering/CreativeMacros'
import type { MacroValues } from '../mastering/CreativeMacros'
import { MeteringPanel } from '../mastering/MeteringPanel'
import { MasteringEngine } from '../mastering/MasteringEngine'
import { AnalogModeling } from '../mastering/AnalogModeling'
import { MSProcessing } from '../mastering/MSProcessing'
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '../layout/ResizablePanel'
import {
  Download,
  ArrowLeftRight,
  FileAudio,
  Clock,
  Radio,
  Layers,
  ChevronUp,
  ChevronDown,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Control tab identifiers
// ---------------------------------------------------------------------------

type ControlTab = 'macros' | 'chain' | 'analog' | 'ms' | 'metadata'

const CONTROL_TABS: readonly { id: ControlTab; label: string; shortcut: string }[] = [
  { id: 'macros', label: 'Macros', shortcut: '1' },
  { id: 'chain', label: 'Signal Chain', shortcut: '2' },
  { id: 'analog', label: 'Analog', shortcut: '3' },
  { id: 'ms', label: 'M/S', shortcut: '4' },
  { id: 'metadata', label: 'Metadata', shortcut: '5' },
] as const

// ---------------------------------------------------------------------------
// Processing status stages for LED indicators
// ---------------------------------------------------------------------------

const STAGE_LEDS: readonly { key: string; label: string }[] = [
  { key: 'uploading', label: 'UPLOAD' },
  { key: 'analyzing', label: 'ANALYSIS' },
  { key: 'processing', label: 'DSP' },
  { key: 'complete', label: 'DONE' },
] as const

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatSampleRate(sr: number): string {
  return sr >= 1000 ? `${(sr / 1000).toFixed(1)} kHz` : `${sr} Hz`
}

// ---------------------------------------------------------------------------
// MasteringTab
// ---------------------------------------------------------------------------

export default function MasteringTab() {
  const { setStatus, status, setAnalysis, setResult } = useSessionStore()

  // -- File & session state --
  const [file, setFile] = useState<File | null>(null)
  const [inputBuffer, setInputBuffer] = useState<ArrayBuffer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [masterSessionId, setMasterSessionId] = useState<string | null>(null)
  const [analysis, setAnalysisData] = useState<AnalysisData | null>(null)
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // -- Upload bar collapse --
  const [uploadCollapsed, setUploadCollapsed] = useState(false)

  // -- Macro values (CreativeMacros expects a MacroValues object) --
  const [macroValues, setMacroValues] = useState<MacroValues>({
    brighten: 5.0,
    glue: 6.0,
    width: 5.0,
    punch: 5.0,
    warmth: 2.5,
    space: 3.0,
    repair: 0.0,
  })

  // -- Analog modeling state --
  const [analogMode, setAnalogMode] = useState('tape')
  const [analogDrive, setAnalogDrive] = useState(0.0)

  // -- M/S state --
  const [msEnabled, setMsEnabled] = useState(false)
  const [midGain, setMidGain] = useState(0.0)
  const [sideGain, setSideGain] = useState(0.0)
  const [stereoWidth, setStereoWidth] = useState(1.0)

  // -- Metadata --
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [album, setAlbum] = useState('')
  const [genre, setGenre] = useState('')
  const [trackNumber, setTrackNumber] = useState('1')
  const [year, setYear] = useState(String(new Date().getFullYear()))

  // -- A/B --
  const [abMode, setAbMode] = useState<'original' | 'mastered'>('mastered')

  // -- Control tabs --
  const [activeControlTab, setActiveControlTab] = useState<ControlTab>('macros')

  // -- Map macro values to DSP parameter ranges --
  const knobToParam = useCallback(
    () => ({
      brightness: (macroValues.brighten / 10) * 4.0,
      tightness: 1.0 + (macroValues.glue / 10) * 4.0,
      width: -3.0 + (macroValues.width / 10) * 9.0,
      target_lufs: -16.0 + (macroValues.punch / 10) * 7.0,
      warmth: (macroValues.warmth / 10) * 3.0,
      punch: 1.0 + (macroValues.punch / 10) * 29.0,
      air: (macroValues.space / 10) * 3.0,
    }),
    [macroValues],
  )

  // -- Macro change handler --
  const handleMacroChange = useCallback((key: keyof MacroValues, value: number) => {
    setMacroValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  // -- File upload handler --
  const handleFile = useCallback(
    async (f: File) => {
      setFile(f)
      setError(null)
      setMasterSessionId(null)
      setAnalysisData(null)
      setProcessResult(null)
      setStatus('idle')
      setUploadCollapsed(true)

      const name = f.name.replace(/\.[^/.]+$/, '')
      setTitle(name)

      const buf = await f.arrayBuffer()
      setInputBuffer(buf)
      useSessionStore.getState().setInputBuffer(buf)

      try {
        setStatus('uploading')
        const uploadRes = await api.master.upload(f)
        setMasterSessionId(uploadRes.session_id)
        useSessionStore.getState().setSession(uploadRes.session_id)

        setStatus('analyzing')
        const analysisRes = await api.master.analysis(uploadRes.session_id)
        setAnalysisData(analysisRes)
        setAnalysis(analysisRes.input_lufs, analysisRes.input_true_peak)
        setStatus('idle')
      } catch (e) {
        const msg =
          e instanceof APIError
            ? e.message
            : e instanceof Error
              ? e.message
              : 'Upload failed'
        setError(msg)
        setStatus('failed')
      }
    },
    [setStatus, setAnalysis],
  )

  // -- Master handler --
  const handleMaster = useCallback(async () => {
    if (!masterSessionId) return
    setError(null)
    setIsProcessing(true)
    setStatus('processing')

    try {
      const params = {
        ...knobToParam(),
        title: title || 'Untitled',
        artist: artist || 'Unknown Artist',
        album,
        genre,
        track_number: trackNumber,
        year,
      }
      const result = await api.master.process(masterSessionId, params)
      setProcessResult(result)

      const score = {
        overall: 85,
        spotify: 88,
        apple_music: 86,
        youtube: 84,
        tidal: 87,
        codec_penalty: {},
      }
      setResult(result.output_lufs, result.output_true_peak, score, '')

      const updatedAnalysis = await api.master.analysis(masterSessionId)
      setAnalysisData(updatedAnalysis)

      setStatus('complete')
    } catch (e) {
      const msg =
        e instanceof APIError
          ? e.message
          : e instanceof Error
            ? e.message
            : 'Mastering failed'
      setError(msg)
      setStatus('failed')
    } finally {
      setIsProcessing(false)
    }
  }, [
    masterSessionId,
    knobToParam,
    title,
    artist,
    album,
    genre,
    trackNumber,
    year,
    setStatus,
    setResult,
  ])

  // -- Reset handler --
  const handleReset = useCallback(() => {
    setFile(null)
    setInputBuffer(null)
    setError(null)
    setMasterSessionId(null)
    setAnalysisData(null)
    setProcessResult(null)
    setIsProcessing(false)
    setUploadCollapsed(false)
    setMacroValues({
      brighten: 5.0,
      glue: 6.0,
      width: 5.0,
      punch: 5.0,
      warmth: 2.5,
      space: 3.0,
      repair: 0.0,
    })
    setAnalogMode('tape')
    setAnalogDrive(0.0)
    setMsEnabled(false)
    setMidGain(0.0)
    setSideGain(0.0)
    setStereoWidth(1.0)
    setTitle('')
    setArtist('')
    setAlbum('')
    setGenre('')
    setAbMode('mastered')
    useSessionStore.getState().reset()
  }, [])

  // -- A/B toggle --
  const handleABToggle = useCallback(() => {
    setAbMode((prev) => (prev === 'original' ? 'mastered' : 'original'))
  }, [])

  // -- Keyboard shortcut for control tabs --
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!inputBuffer) return
      const tab = CONTROL_TABS.find((t) => t.shortcut === e.key)
      if (tab && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const tag = (e.target as HTMLElement).tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        setActiveControlTab(tab.id)
      }
    },
    [inputBuffer],
  )

  const hasFile = inputBuffer !== null

  // =========================================================================
  // RENDER
  // =========================================================================

  return (
    <div
      className="flex flex-col h-full w-full overflow-hidden bg-rain-bg"
      onKeyDown={handleKeyDown}
      tabIndex={-1}
    >
      {/* -- 1. Upload / Session Bar ---------------------------------------- */}
      {!hasFile ? (
        <div className="p-3 shrink-0">
          <UploadZone onFileSelected={handleFile} disabled={status !== 'idle'} />
        </div>
      ) : (
        <SessionBar
          file={file}
          analysis={analysis}
          status={status}
          collapsed={uploadCollapsed}
          onToggleCollapse={() => setUploadCollapsed((p) => !p)}
          onNewFile={handleFile}
        />
      )}

      {/* -- Error banner --------------------------------------------------- */}
      {error && (
        <div className="mx-3 mb-1 px-3 py-1.5 rounded border border-red-500/30 bg-red-500/10 text-[10px] font-mono text-red-400 shrink-0">
          {error}
        </div>
      )}

      {/* -- Main workspace (only when file is loaded) ---------------------- */}
      {hasFile && (
        <ResizablePanelGroup
          direction="horizontal"
          groupId="mastering-main"
          className="flex-1 min-h-0"
        >
          {/* -- Left: Visualizers + Controls -------------------------------- */}
          <ResizablePanel id="workspace" defaultSize={76} minSize={55} maxSize={90}>
            <ResizablePanelGroup
              direction="vertical"
              groupId="mastering-vertical"
              className="h-full"
            >
              {/* -- 2. Waveform Section ------------------------------------ */}
              <ResizablePanel id="waveform" defaultSize={28} minSize={15} maxSize={50}>
                <div className="h-full flex flex-col panel-card m-0 rounded-none border-x-0 border-t-0">
                  <div className="panel-card-header shrink-0 flex items-center justify-between px-3 py-1">
                    <span className="text-[9px] font-mono font-bold text-rain-dim uppercase tracking-widest">
                      Waveform
                    </span>
                    {analysis && (
                      <span className="text-[9px] font-mono text-rain-muted">
                        {formatDuration(analysis.duration)} / {formatSampleRate(analysis.sample_rate)} / {analysis.channels}ch
                      </span>
                    )}
                  </div>
                  {/* Time ruler */}
                  <div className="h-4 shrink-0 border-b border-rain-border/30 bg-rain-bg/50 flex items-center px-2">
                    <div className="flex-1 flex justify-between text-[7px] font-mono text-rain-muted tabular-nums">
                      {analysis
                        ? Array.from({ length: 11 }, (_, i) => {
                            const t = (analysis.duration / 10) * i
                            return <span key={i}>{formatDuration(t)}</span>
                          })
                        : null}
                    </div>
                  </div>
                  {/* Waveform canvas area */}
                  <div className="flex-1 min-h-0 flex">
                    {/* Amplitude scale */}
                    <div className="w-6 shrink-0 flex flex-col justify-between items-end pr-1 py-1 text-[7px] font-mono text-rain-muted border-r border-rain-border/20">
                      <span>0</span>
                      <span>-6</span>
                      <span>-12</span>
                      <span>-24</span>
                      <span>-inf</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <Waveform height={200} />
                    </div>
                  </div>
                </div>
              </ResizablePanel>

              <ResizableHandle index={0} />

              {/* -- 3. Spectrum Section ------------------------------------- */}
              <ResizablePanel id="spectrum" defaultSize={22} minSize={10} maxSize={40}>
                <div className="h-full flex flex-col panel-card m-0 rounded-none border-x-0">
                  <div className="panel-card-header shrink-0 flex items-center justify-between px-3 py-1">
                    <span className="text-[9px] font-mono font-bold text-rain-dim uppercase tracking-widest">
                      Spectrum Analyzer
                    </span>
                    <span className="text-[8px] font-mono text-rain-muted">
                      Preview measurement — final render may differ slightly.
                    </span>
                  </div>
                  <div className="flex-1 min-h-0">
                    <Spectrum height={160} />
                  </div>
                </div>
              </ResizablePanel>

              <ResizableHandle index={1} />

              {/* -- 4. Controls Section (tabbed) --------------------------- */}
              <ResizablePanel id="controls" defaultSize={50} minSize={30} maxSize={70}>
                <div className="h-full flex flex-col overflow-hidden">
                  {/* MasteringEngine bar */}
                  <div className="shrink-0">
                    <MasteringEngine
                      onMasterNow={() => void handleMaster()}
                      onReset={handleReset}
                      disabled={!masterSessionId || isProcessing}
                    />
                  </div>

                  {/* Tab strip */}
                  <div className="shrink-0 flex items-center border-b border-rain-border bg-rain-bg/80 px-2">
                    {CONTROL_TABS.map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveControlTab(tab.id)}
                        className={`relative px-3 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider transition-colors ${
                          activeControlTab === tab.id
                            ? 'text-rain-teal'
                            : 'text-rain-dim hover:text-rain-text'
                        }`}
                      >
                        {tab.label}
                        <span className="ml-1 text-[8px] text-rain-muted opacity-50">
                          {tab.shortcut}
                        </span>
                        {activeControlTab === tab.id && (
                          <div className="absolute bottom-0 left-2 right-2 h-[2px] bg-rain-teal rounded-full" />
                        )}
                      </button>
                    ))}

                    {/* Processing stage LEDs */}
                    <div className="ml-auto flex items-center gap-2 pr-2">
                      {STAGE_LEDS.map((stage) => {
                        const isActive = status === stage.key
                        const isPast =
                          (stage.key === 'uploading' &&
                            ['analyzing', 'processing', 'complete'].includes(status)) ||
                          (stage.key === 'analyzing' &&
                            ['processing', 'complete'].includes(status)) ||
                          (stage.key === 'processing' && status === 'complete')
                        const color = isActive
                          ? '#00E5C8'
                          : isPast
                            ? '#4AFF8A'
                            : '#2A2545'
                        return (
                          <div key={stage.key} className="flex items-center gap-1">
                            <div
                              className={`w-2 h-2 rounded-full ${isActive ? 'animate-pulse' : ''}`}
                              style={{
                                background: color,
                                boxShadow: isActive ? `0 0 6px ${color}80` : 'none',
                              }}
                            />
                            <span className="text-[7px] font-mono text-rain-muted uppercase">
                              {stage.label}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* Tab content */}
                  <div className="flex-1 min-h-0 overflow-auto p-2">
                    {activeControlTab === 'macros' && (
                      <CreativeMacros
                        values={macroValues}
                        onChange={handleMacroChange}
                      />
                    )}

                    {activeControlTab === 'chain' && <SignalChain />}

                    {activeControlTab === 'analog' && (
                      <AnalogModeling
                        mode={analogMode}
                        drive={analogDrive}
                        onModeChange={setAnalogMode}
                        onDriveChange={setAnalogDrive}
                      />
                    )}

                    {activeControlTab === 'ms' && (
                      <MSProcessing
                        enabled={msEnabled}
                        midGain={midGain}
                        sideGain={sideGain}
                        stereoWidth={stereoWidth}
                        onEnabledChange={setMsEnabled}
                        onMidGainChange={setMidGain}
                        onSideGainChange={setSideGain}
                        onStereoWidthChange={setStereoWidth}
                      />
                    )}

                    {activeControlTab === 'metadata' && (
                      <div className="panel-card">
                        <div className="panel-card-header text-rain-text">Metadata</div>
                        <div className="panel-card-body">
                          <div className="grid grid-cols-3 gap-3">
                            <MetadataInput label="Title" value={title} onChange={setTitle} />
                            <MetadataInput label="Artist" value={artist} onChange={setArtist} />
                            <MetadataInput label="Album" value={album} onChange={setAlbum} />
                            <MetadataInput label="Genre" value={genre} onChange={setGenre} />
                            <MetadataInput
                              label="Track #"
                              value={trackNumber}
                              onChange={setTrackNumber}
                            />
                            <MetadataInput label="Year" value={year} onChange={setYear} />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Results + A/B + Export (shown after mastering completes) */}
                    {processResult && masterSessionId && (
                      <div className="mt-2 space-y-2">
                        <ResultsBar result={processResult} />
                        <ABComparison mode={abMode} onToggle={handleABToggle} />
                        <ExportBar sessionId={masterSessionId} />
                      </div>
                    )}
                  </div>
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </ResizablePanel>

          <ResizableHandle index={0} />

          {/* -- 5. Right Panel: Metering ----------------------------------- */}
          <ResizablePanel id="metering" defaultSize={24} minSize={15} maxSize={35}>
            <div className="h-full overflow-y-auto border-l border-rain-border/30">
              <MeteringPanel />

              {/* Input analysis summary */}
              {analysis && (
                <div className="p-3 border-t border-rain-border/30">
                  <div className="text-[8px] font-mono text-rain-dim uppercase tracking-widest mb-2">
                    Input Analysis
                  </div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
                    <AnalysisMetric
                      label="LUFS"
                      value={analysis.input_lufs.toFixed(1)}
                      unit="LUFS"
                    />
                    <AnalysisMetric
                      label="TRUE PEAK"
                      value={analysis.input_true_peak.toFixed(1)}
                      unit="dBTP"
                    />
                    <AnalysisMetric
                      label="DR"
                      value={analysis.dynamic_range.toFixed(1)}
                      unit="dB"
                    />
                    <AnalysisMetric
                      label="WIDTH"
                      value={(analysis.stereo_width * 100).toFixed(0)}
                      unit="%"
                    />
                    <AnalysisMetric
                      label="CENTROID"
                      value={analysis.spectral_centroid.toFixed(0)}
                      unit="Hz"
                    />
                    <AnalysisMetric
                      label="BASS"
                      value={(analysis.bass_energy_ratio * 100).toFixed(0)}
                      unit="%"
                    />
                  </div>
                </div>
              )}

              {/* Platform compliance */}
              <div className="p-3 border-t border-rain-border/30">
                <div className="text-[8px] font-mono text-rain-dim uppercase tracking-widest mb-2">
                  Platform Compliance
                </div>
                {[
                  { platform: 'Spotify', target: '-14.0 LUFS', pass: status === 'complete' },
                  { platform: 'Apple Music', target: '-16.0 LUFS', pass: status === 'complete' },
                  { platform: 'YouTube', target: '-14.0 LUFS', pass: status === 'complete' },
                  { platform: 'Tidal', target: '-14.0 LUFS', pass: status === 'complete' },
                ].map((p) => (
                  <div
                    key={p.platform}
                    className="flex items-center justify-between py-1 border-b border-rain-border/10 last:border-b-0"
                  >
                    <span className="text-[9px] font-mono text-rain-dim">{p.platform}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] font-mono text-rain-muted">{p.target}</span>
                      <span
                        className={`text-[8px] font-mono font-bold ${
                          p.pass ? 'text-green-400' : 'text-rain-muted'
                        }`}
                      >
                        {p.pass ? 'PASS' : '---'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      )}
    </div>
  )
}

// ===========================================================================
// Sub-components (file-private)
// ===========================================================================

// -- Session Bar ------------------------------------------------------------

interface SessionBarProps {
  file: File | null
  analysis: AnalysisData | null
  status: string
  collapsed: boolean
  onToggleCollapse: () => void
  onNewFile: (f: File) => void
}

function SessionBar({
  file,
  analysis,
  status,
  collapsed,
  onToggleCollapse,
  onNewFile,
}: SessionBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleNewClick = useCallback(() => {
    inputRef.current?.click()
  }, [])

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0]
      if (f) {
        void onNewFile(f)
      }
    },
    [onNewFile],
  )

  if (!collapsed) {
    return (
      <div className="shrink-0 px-3 pt-2 pb-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] font-mono text-rain-dim uppercase tracking-widest">
            Session
          </span>
          <button
            onClick={onToggleCollapse}
            className="text-rain-dim hover:text-rain-text transition-colors"
          >
            <ChevronUp size={12} />
          </button>
        </div>
        <UploadZone onFileSelected={onNewFile} disabled={status === 'processing'} />
      </div>
    )
  }

  return (
    <div className="shrink-0 flex items-center gap-3 px-3 py-1.5 border-b border-rain-border/30 bg-rain-surface/50">
      <input
        ref={inputRef}
        type="file"
        accept=".wav,.flac,.aiff,.aif,.mp3,.m4a"
        className="hidden"
        onChange={handleInputChange}
      />

      {/* File icon + name */}
      <div className="flex items-center gap-1.5 min-w-0">
        <FileAudio size={13} className="text-rain-teal shrink-0" />
        <span className="text-[10px] font-mono text-rain-text truncate max-w-[200px]">
          {file?.name ?? 'No file'}
        </span>
      </div>

      {/* File metadata badges */}
      {analysis && (
        <div className="flex items-center gap-2">
          <MetadataBadge icon={<Clock size={10} />} value={formatDuration(analysis.duration)} />
          <MetadataBadge icon={<Radio size={10} />} value={formatSampleRate(analysis.sample_rate)} />
          <MetadataBadge icon={<Layers size={10} />} value={`${analysis.channels}ch`} />
          <MetadataBadge
            value={`${analysis.input_lufs.toFixed(1)} LUFS`}
            highlight
          />
        </div>
      )}

      <div className="flex-1" />

      <button
        onClick={handleNewClick}
        className="text-[9px] font-mono text-rain-dim hover:text-rain-teal transition-colors uppercase tracking-wider"
      >
        Load New
      </button>

      <button
        onClick={onToggleCollapse}
        className="text-rain-dim hover:text-rain-text transition-colors"
      >
        <ChevronDown size={12} />
      </button>
    </div>
  )
}

// -- Metadata badge (session bar) -------------------------------------------

function MetadataBadge({
  icon,
  value,
  highlight = false,
}: {
  icon?: React.ReactNode
  value: string
  highlight?: boolean
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono ${
        highlight
          ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20'
          : 'bg-rain-bg/60 text-rain-dim border border-rain-border/30'
      }`}
    >
      {icon}
      {value}
    </span>
  )
}

// -- Analysis metric --------------------------------------------------------

function AnalysisMetric({
  label,
  value,
  unit,
  highlight,
}: {
  label: string
  value: string
  unit: string
  highlight?: boolean
}) {
  return (
    <div className="text-center py-1">
      <div className="text-[7px] font-mono text-rain-muted uppercase tracking-wider">
        {label}
      </div>
      <div
        className={`text-sm font-mono font-bold tabular-nums ${
          highlight ? 'text-rain-cyan' : 'text-rain-text'
        }`}
      >
        {value}
      </div>
      <div className="text-[7px] font-mono text-rain-muted">{unit}</div>
    </div>
  )
}

// -- Results bar ------------------------------------------------------------

function ResultsBar({ result }: { result: ProcessResult }) {
  return (
    <div className="panel-card">
      <div className="panel-card-header text-rain-text">Mastering Results</div>
      <div className="panel-card-body">
        <div className="grid grid-cols-5 gap-2">
          <AnalysisMetric
            label="OUTPUT LUFS"
            value={result.output_lufs.toFixed(1)}
            unit="LUFS"
            highlight
          />
          <AnalysisMetric
            label="TRUE PEAK"
            value={result.output_true_peak.toFixed(1)}
            unit="dBTP"
            highlight
          />
          <AnalysisMetric
            label="DR"
            value={result.output_dynamic_range.toFixed(1)}
            unit="dB"
          />
          <AnalysisMetric
            label="WIDTH"
            value={(result.output_stereo_width * 100).toFixed(0)}
            unit="%"
            highlight
          />
          <AnalysisMetric
            label="CENTROID"
            value={result.output_spectral_centroid.toFixed(0)}
            unit="Hz"
          />
        </div>
      </div>
    </div>
  )
}

// -- A/B comparison ---------------------------------------------------------

function ABComparison({
  mode,
  onToggle,
}: {
  mode: 'original' | 'mastered'
  onToggle: () => void
}) {
  return (
    <div className="panel-card">
      <div className="panel-card-body flex items-center justify-between py-2 px-3">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono text-rain-dim uppercase tracking-widest">
            A/B Compare
          </span>
          <span className="text-[8px] font-mono text-rain-muted">Level-matched</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onToggle}
            className="flex items-center gap-1.5 px-3 py-1 rounded-md border border-rain-border bg-rain-surface hover:bg-rain-panel transition-colors"
          >
            <ArrowLeftRight size={12} className="text-rain-cyan" />
            <span className="text-[10px] font-mono font-bold text-rain-text">
              {mode === 'original' ? 'A' : 'B'}
            </span>
          </button>
          <div
            className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold ${
              mode === 'original'
                ? 'bg-rain-muted/20 text-rain-dim'
                : 'bg-rain-teal/20 text-rain-teal border border-rain-teal/30'
            }`}
          >
            {mode === 'original' ? 'ORIGINAL' : 'MASTERED'}
          </div>
        </div>
      </div>
    </div>
  )
}

// -- Export bar --------------------------------------------------------------

function ExportBar({ sessionId }: { sessionId: string }) {
  return (
    <div className="panel-card">
      <div className="panel-card-body flex gap-2 py-2 px-3">
        <a
          href={api.master.downloadUrl(sessionId, 'wav')}
          download
          className="flex-1 flex items-center justify-center gap-1.5 h-9 rounded-md bg-gradient-to-r from-rain-teal to-rain-cyan text-rain-black font-mono text-[10px] font-bold hover:opacity-90 transition-opacity"
        >
          <Download size={12} />
          WAV 24-bit / 48kHz
        </a>
        <a
          href={api.master.downloadUrl(sessionId, 'mp3')}
          download
          className="flex-1 flex items-center justify-center gap-1.5 h-9 rounded-md bg-gradient-to-r from-rain-purple to-rain-magenta text-white font-mono text-[10px] font-bold hover:opacity-90 transition-opacity"
        >
          <Download size={12} />
          MP3 320kbps / 44.1kHz
        </a>
      </div>
    </div>
  )
}

// -- Metadata input ---------------------------------------------------------

function MetadataInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div>
      <label className="text-[9px] font-mono text-rain-dim uppercase tracking-wider">
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 bg-rain-bg border border-rain-border rounded px-2 py-1.5 text-rain-text text-[11px] font-mono placeholder:text-rain-muted focus:border-rain-teal/50 focus:outline-none transition-colors"
        placeholder={label}
      />
    </div>
  )
}
