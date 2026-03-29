import { useState, useCallback, useRef, useEffect } from 'react'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import { renderLocal } from '@/hooks/useLocalRender'
import { api, APIError } from '@/utils/api'
import { UploadZone } from '../controls/UploadZone'
import { Waveform } from '../visualizers/Waveform'
import { Spectrum } from '../visualizers/Spectrum'
import { SignalChain } from '../mastering/SignalChain'
import { CreativeMacros } from '../mastering/CreativeMacros'
import { MeteringPanel } from '../mastering/MeteringPanel'
import { AnalogModeling } from '../mastering/AnalogModeling'
import { MSProcessing } from '../mastering/MSProcessing'
import { MasteringEngine } from '../mastering/MasteringEngine'

const PLATFORMS = ['spotify', 'apple_music', 'youtube', 'tidal', 'amazon', 'soundcloud', 'cd', 'vinyl'] as const
const GENRES = ['electronic', 'hiphop', 'rock', 'pop', 'classical', 'jazz', 'default'] as const
type Platform = typeof PLATFORMS[number]
type Genre = typeof GENRES[number]

export default function MasteringTab() {
  const { tier } = useAuthStore()
  const { setStatus, setOutputBuffer, status, outputBuffer, outputLufs } = useSessionStore()

  const [file, setFile] = useState<File | null>(null)
  const [inputBuffer, setInputBuffer] = useState<ArrayBuffer | null>(null)
  const [platform, setPlatform] = useState<Platform>('spotify')
  const [genre, setGenre] = useState<Genre>('default')
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Macro state
  const [vizMode, setVizMode] = useState<'waveform' | 'spectrum' | 'phase'>('waveform')
  const [macros, setMacros] = useState({ brighten: 5.0, glue: 4.2, width: 3.8, punch: 6.1, warmth: 5.5 })
  const [satMode, setSatMode] = useState('tape')
  const [satDrive, setSatDrive] = useState(0.3)
  const [msEnabled, setMsEnabled] = useState(false)
  const [midGain, setMidGain] = useState(0)
  const [sideGain, setSideGain] = useState(0)
  const [stereoWidth, setStereoWidth] = useState(1.0)

  const isFree = tier === 'free'

  const handleFile = useCallback(async (f: File) => {
    setFile(f)
    setError(null)
    const buf = await f.arrayBuffer()
    setInputBuffer(buf)
    setStatus('idle')
    setOutputBuffer(null as unknown as ArrayBuffer)
    // Also push to session store for transport bar
    useSessionStore.getState().setInputBuffer(buf)
  }, [setStatus, setOutputBuffer])

  // WebSocket for paid-tier real-time updates
  useEffect(() => {
    if (!sessionId || isFree) return
    const { accessToken } = useAuthStore.getState()
    const wsUrl = `/api/v1/sessions/${sessionId}/status?token=${accessToken ?? ''}`
    const ws = new WebSocket(wsUrl.replace(/^http/, 'ws'))
    wsRef.current = ws

    ws.onmessage = (evt) => {
      const msg: {
        status: string
        output_lufs?: number | null
        output_true_peak?: number | null
        rain_score?: unknown
        error_code?: string
        error_detail?: string
      } = JSON.parse(evt.data as string)
      setStatus(msg.status as Parameters<typeof setStatus>[0])
      if (msg.status === 'complete' && msg.output_lufs != null) {
        useSessionStore.getState().setResult(
          msg.output_lufs,
          msg.output_true_peak ?? 0,
          msg.rain_score as Parameters<typeof useSessionStore.getState().setResult>[2] ?? { overall: 0, spotify: 0, apple_music: 0, youtube: 0, tidal: 0, codec_penalty: {} },
          ''
        )
      }
    }
    ws.onerror = () => setError('RAIN-E300: WebSocket error')
    ws.onclose = () => { wsRef.current = null }

    return () => { ws.close(); wsRef.current = null }
  }, [sessionId, isFree, setStatus])

  const handleMaster = useCallback(async () => {
    if (!inputBuffer) return
    setError(null)

    if (isFree) {
      // Free tier: pure WASM, zero network
      setStatus('processing')
      try {
        const result = await renderLocal(inputBuffer, genre, platform)
        setOutputBuffer(result.outputBuffer)
        setStatus('complete')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'RAIN-E300: Render failed')
        setStatus('failed')
      }
      return
    }

    // Paid tier: upload to API, stream status via WebSocket
    setStatus('uploading')
    try {
      if (!file) throw new Error('No file selected')
      const session = await api.sessions.create(file, { target_platform: platform, genre, simple_mode: false })
      setSessionId(session.id)
      setStatus('analyzing')
    } catch (e) {
      setError(e instanceof APIError ? e.message : 'RAIN-E200: Upload failed')
      setStatus('failed')
    }
  }, [inputBuffer, file, isFree, platform, genre, setStatus, setOutputBuffer])

  const handleReset = useCallback(() => {
    setFile(null)
    setInputBuffer(null)
    setError(null)
    setSessionId(null)
    setStatus('idle')
    setOutputBuffer(null as unknown as ArrayBuffer)
    setMacros({ brighten: 5.0, glue: 4.2, width: 3.8, punch: 6.1, warmth: 5.5 })
    setSatMode('tape')
    setSatDrive(0.3)
    setMsEnabled(false)
    setMidGain(0)
    setSideGain(0)
    setStereoWidth(1.0)
  }, [setStatus, setOutputBuffer])

  const handleMacroChange = useCallback((key: string, value: number) => {
    setMacros((prev) => ({ ...prev, [key]: value }))
  }, [])

  return (
    <div className="p-2 space-y-2 w-full">
      {/* Row 0: Upload zone (collapsed when file loaded) */}
      {!inputBuffer && (
        <UploadZone onFileSelected={handleFile} disabled={status !== 'idle'} />
      )}

      {/* Row 0.5: Platform / Genre selectors */}
      {inputBuffer && (
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-[9px] font-mono text-rain-dim">PLATFORM</label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value as Platform)}
              className="bg-rain-surface border border-rain-border rounded px-2 py-1 text-rain-text text-[10px] font-mono"
            >
              {PLATFORMS.map(p => <option key={p} value={p}>{p.toUpperCase().replace('_', ' ')}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-[9px] font-mono text-rain-dim">GENRE</label>
            <select
              value={genre}
              onChange={(e) => setGenre(e.target.value as Genre)}
              className="bg-rain-surface border border-rain-border rounded px-2 py-1 text-rain-text text-[10px] font-mono"
            >
              {GENRES.map(g => <option key={g} value={g}>{g.toUpperCase()}</option>)}
            </select>
          </div>
          {error && <span className="text-[9px] font-mono text-rain-red ml-auto">{error}</span>}
        </div>
      )}

      {/* Row 1: Mastering Engine control bar */}
      <MasteringEngine
        onMasterNow={() => void handleMaster()}
        onReset={handleReset}
        disabled={!inputBuffer}
      />

      {/* Row 1.5: Visualizer */}
      <div className="panel-card">
        <div className="panel-card-header justify-between">
          <span>Visualizer</span>
          <div className="flex gap-1">
            {(['waveform', 'spectrum', 'phase'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setVizMode(mode)}
                className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider transition-all ${
                  vizMode === mode
                    ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20'
                    : 'text-rain-dim hover:text-rain-text border border-transparent'
                }`}
              >
                {mode === 'waveform' ? 'WAVE FORM' : mode === 'spectrum' ? 'SPECTRUM' : 'PHASE'}
              </button>
            ))}
          </div>
        </div>
        <div className="panel-card-body p-0">
          {vizMode === 'waveform' && <Waveform height={80} />}
          {vizMode === 'spectrum' && <Spectrum height={80} />}
          {vizMode === 'phase' && <Waveform height={80} />}
        </div>
      </div>

      {/* Row 2: Signal Chain */}
      <SignalChain />

      {/* Row 3: Creative Macros + Metering */}
      <div className="flex gap-2">
        <CreativeMacros
          brighten={macros.brighten}
          glue={macros.glue}
          width={macros.width}
          punch={macros.punch}
          warmth={macros.warmth}
          onChange={handleMacroChange}
        />
        <MeteringPanel />
      </div>

      {/* Row 4: Analog Modeling + M/S Processing */}
      <div className="flex gap-2">
        <AnalogModeling
          mode={satMode}
          drive={satDrive}
          onModeChange={setSatMode}
          onDriveChange={setSatDrive}
        />
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
      </div>

      {/* Free tier disclaimer */}
      {isFree && (
        <p className="text-[9px] font-mono text-rain-muted text-center">
          Preview measurement — final render may differ slightly. Upgrade for full resolution export.
        </p>
      )}
    </div>
  )
}
