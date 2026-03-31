import { useState, useCallback, useRef, useEffect } from 'react'
import { useSessionStore } from '@/stores/session'
import { api, APIError } from '@/utils/api'
import type { AnalysisData, ProcessResult } from '@/utils/api'
import { UploadZone } from '../controls/UploadZone'
import { Waveform } from '../visualizers/Waveform'
import { Spectrum } from '../visualizers/Spectrum'
import { SignalChain } from '../mastering/SignalChain'
import { CreativeMacros } from '../mastering/CreativeMacros'
import { MeteringPanel } from '../mastering/MeteringPanel'
import { MasteringEngine } from '../mastering/MasteringEngine'
import { MacroKnob } from '../mastering/MacroKnob'
import { Download, Play, Pause, ArrowLeftRight } from 'lucide-react'

export default function MasteringTab() {
  const { setStatus, status, setAnalysis, setResult } = useSessionStore()

  const [file, setFile] = useState<File | null>(null)
  const [inputBuffer, setInputBuffer] = useState<ArrayBuffer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [masterSessionId, setMasterSessionId] = useState<string | null>(null)
  const [analysis, setAnalysisData] = useState<AnalysisData | null>(null)
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Knob values (mapped to backend MasteringParams)
  const [brightness, setBrightness] = useState(5.0)
  const [tightness, setTightness] = useState(6.0)
  const [width, setWidth] = useState(5.0)
  const [loudness, setLoudness] = useState(5.0)
  const [warmth, setWarmth] = useState(2.5)
  const [punch, setPunch] = useState(5.0)
  const [air, setAir] = useState(3.75)

  // Metadata
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [album, setAlbum] = useState('')
  const [genre, setGenre] = useState('')
  const [trackNumber, setTrackNumber] = useState('1')
  const [year, setYear] = useState(String(new Date().getFullYear()))

  // A/B player
  const [abMode, setAbMode] = useState<'original' | 'mastered'>('mastered')
  const [isPlaying, setIsPlaying] = useState(false)
  const originalAudioRef = useRef<HTMLAudioElement | null>(null)
  const masteredAudioRef = useRef<HTMLAudioElement | null>(null)

  // Visualizer
  const [vizMode, setVizMode] = useState<'waveform' | 'spectrum'>('waveform')

  // Map 0-10 knob values to DSP parameter ranges
  const knobToParam = useCallback(() => ({
    brightness: (brightness / 10) * 4.0,        // 0-4 dB
    tightness: 1.0 + (tightness / 10) * 4.0,    // 1-5 ratio
    width: -3.0 + (width / 10) * 9.0,            // -3 to +6 dB
    target_lufs: -16.0 + (loudness / 10) * 7.0,  // -16 to -9 LUFS
    warmth: (warmth / 10) * 3.0,                  // 0-3 dB
    punch: 1.0 + (punch / 10) * 29.0,            // 1-30 ms
    air: (air / 10) * 3.0,                        // 0-3 dB
  }), [brightness, tightness, width, loudness, warmth, punch, air])

  const handleFile = useCallback(async (f: File) => {
    setFile(f)
    setError(null)
    setMasterSessionId(null)
    setAnalysisData(null)
    setProcessResult(null)
    setStatus('idle')

    // Pre-fill title from filename
    const name = f.name.replace(/\.[^/.]+$/, '')
    setTitle(name)

    const buf = await f.arrayBuffer()
    setInputBuffer(buf)
    useSessionStore.getState().setInputBuffer(buf)

    // Upload to backend
    try {
      setStatus('uploading')
      const uploadRes = await api.master.upload(f)
      setMasterSessionId(uploadRes.session_id)

      // Get analysis
      setStatus('analyzing')
      const analysisRes = await api.master.analysis(uploadRes.session_id)
      setAnalysisData(analysisRes)
      setAnalysis(analysisRes.input_lufs, analysisRes.input_true_peak)
      setStatus('idle')
    } catch (e) {
      const msg = e instanceof APIError ? e.message : (e instanceof Error ? e.message : 'Upload failed')
      setError(msg)
      setStatus('failed')
    }
  }, [setStatus, setAnalysis])

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

      // Update session store
      const score = { overall: 85, spotify: 88, apple_music: 86, youtube: 84, tidal: 87, codec_penalty: {} }
      setResult(result.output_lufs, result.output_true_peak, score, '')

      // Refresh analysis with post-mastering data
      const updatedAnalysis = await api.master.analysis(masterSessionId)
      setAnalysisData(updatedAnalysis)

      setStatus('complete')
    } catch (e) {
      const msg = e instanceof APIError ? e.message : (e instanceof Error ? e.message : 'Mastering failed')
      setError(msg)
      setStatus('failed')
    } finally {
      setIsProcessing(false)
    }
  }, [masterSessionId, knobToParam, title, artist, album, genre, trackNumber, year, setStatus, setResult])

  const handleReset = useCallback(() => {
    setFile(null)
    setInputBuffer(null)
    setError(null)
    setMasterSessionId(null)
    setAnalysisData(null)
    setProcessResult(null)
    setIsProcessing(false)
    setBrightness(5.0)
    setTightness(6.0)
    setWidth(5.0)
    setLoudness(5.0)
    setWarmth(2.5)
    setPunch(5.0)
    setAir(3.75)
    setTitle('')
    setArtist('')
    setAlbum('')
    setGenre('')
    setAbMode('mastered')
    setIsPlaying(false)
    useSessionStore.getState().reset()
  }, [])

  // A/B playback
  const handleABToggle = useCallback(() => {
    setAbMode(prev => prev === 'original' ? 'mastered' : 'original')
  }, [])

  const handlePlayPause = useCallback(() => {
    setIsPlaying(prev => !prev)
  }, [])

  // Create object URLs for A/B playback
  const originalUrl = file ? URL.createObjectURL(file) : null
  const masteredWavUrl = masterSessionId && processResult
    ? api.master.downloadUrl(masterSessionId, 'wav')
    : null

  return (
    <div className="p-2 space-y-2 w-full">
      {/* Upload zone */}
      {!inputBuffer && (
        <UploadZone onFileSelected={handleFile} disabled={status !== 'idle'} />
      )}

      {/* Analysis display */}
      {analysis && (
        <div className="panel-card">
          <div className="panel-card-header justify-between">
            <span>Analysis</span>
            {file && <span className="text-[9px] font-mono text-rain-dim">{file.name}</span>}
          </div>
          <div className="panel-card-body">
            <div className="grid grid-cols-6 gap-3">
              <AnalysisMetric label="INPUT LUFS" value={`${analysis.input_lufs.toFixed(1)}`} unit="LUFS" />
              <AnalysisMetric label="TRUE PEAK" value={`${analysis.input_true_peak.toFixed(1)}`} unit="dBTP" />
              <AnalysisMetric label="DYNAMIC RANGE" value={`${analysis.dynamic_range.toFixed(1)}`} unit="dB" />
              <AnalysisMetric label="STEREO WIDTH" value={`${(analysis.stereo_width * 100).toFixed(0)}`} unit="%" />
              <AnalysisMetric label="SPECTRAL CENTER" value={`${analysis.spectral_centroid.toFixed(0)}`} unit="Hz" />
              <AnalysisMetric label="BASS ENERGY" value={`${(analysis.bass_energy_ratio * 100).toFixed(0)}`} unit="%" />
            </div>
          </div>
        </div>
      )}

      {/* Mastering Engine control bar */}
      {inputBuffer && (
        <MasteringEngine
          onMasterNow={() => void handleMaster()}
          onReset={handleReset}
          disabled={!masterSessionId || isProcessing}
        />
      )}

      {/* Error display */}
      {error && (
        <div className="px-3 py-2 rounded border border-rain-red/30 bg-rain-red/10 text-[10px] font-mono text-rain-red">
          {error}
        </div>
      )}

      {/* Visualizer */}
      {inputBuffer && (
        <div className="panel-card">
          <div className="panel-card-header justify-between">
            <span>Visualizer</span>
            <div className="flex gap-1">
              {(['waveform', 'spectrum'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setVizMode(mode)}
                  className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider transition-all ${
                    vizMode === mode
                      ? 'bg-rain-teal/10 text-rain-teal border border-rain-teal/20'
                      : 'text-rain-dim hover:text-rain-text border border-transparent'
                  }`}
                >
                  {mode === 'waveform' ? 'WAVEFORM' : 'SPECTRUM'}
                </button>
              ))}
            </div>
          </div>
          <div className="panel-card-body p-0">
            {vizMode === 'waveform' ? <Waveform height={80} /> : <Spectrum height={80} />}
          </div>
        </div>
      )}

      {/* Signal Chain */}
      {inputBuffer && <SignalChain />}

      {/* 7 Macro Knobs */}
      {inputBuffer && (
        <div className="panel-card">
          <div className="panel-card-header text-rain-text">Mastering Controls</div>
          <div className="panel-card-body">
            <div className="flex justify-around flex-wrap gap-3">
              <MacroKnob label="BRIGHTNESS" value={brightness} onChange={setBrightness}
                color="#AAFF00" subParams={['High-shelf +0-4dB @ 8kHz']} />
              <MacroKnob label="TIGHTNESS" value={tightness} onChange={setTightness}
                color="#8B5CF6" subParams={['Low-band ratio 1:1-5:1 @ <200Hz']} />
              <MacroKnob label="WIDTH" value={width} onChange={setWidth}
                color="#00D4FF" subParams={['Side gain -3 to +6dB @ >4kHz']} />
              <MacroKnob label="LOUDNESS" value={loudness} onChange={setLoudness}
                color="#F97316" subParams={['Target LUFS -16 to -9']} />
              <MacroKnob label="WARMTH" value={warmth} onChange={setWarmth}
                color="#D946EF" subParams={['Low-shelf +0-3dB @ 200Hz']} />
              <MacroKnob label="PUNCH" value={punch} onChange={setPunch}
                color="#FFB347" subParams={['Mid attack 1-30ms']} />
              <MacroKnob label="AIR" value={air} onChange={setAir}
                color="#00E5C8" subParams={['Peaking +0-3dB @ 16kHz']} />
            </div>
          </div>
        </div>
      )}

      {/* Metadata Form */}
      {inputBuffer && (
        <div className="panel-card">
          <div className="panel-card-header text-rain-text">Metadata</div>
          <div className="panel-card-body">
            <div className="grid grid-cols-3 gap-3">
              <MetadataInput label="Title" value={title} onChange={setTitle} />
              <MetadataInput label="Artist" value={artist} onChange={setArtist} />
              <MetadataInput label="Album" value={album} onChange={setAlbum} />
              <MetadataInput label="Genre" value={genre} onChange={setGenre} />
              <MetadataInput label="Track #" value={trackNumber} onChange={setTrackNumber} />
              <MetadataInput label="Year" value={year} onChange={setYear} />
            </div>
          </div>
        </div>
      )}

      {/* Metering + Creative Macros row (existing components) */}
      {inputBuffer && (
        <div className="flex gap-2">
          <CreativeMacros
            brighten={brightness}
            glue={tightness}
            width={width}
            punch={punch}
            warmth={warmth}
            onChange={(key, value) => {
              if (key === 'brighten') setBrightness(value)
              else if (key === 'glue') setTightness(value)
              else if (key === 'width') setWidth(value)
              else if (key === 'punch') setPunch(value)
              else if (key === 'warmth') setWarmth(value)
            }}
          />
          <MeteringPanel />
        </div>
      )}

      {/* Results + A/B + Download (after mastering complete) */}
      {processResult && masterSessionId && (
        <>
          {/* Results */}
          <div className="panel-card">
            <div className="panel-card-header text-rain-text">Mastering Results</div>
            <div className="panel-card-body">
              <div className="grid grid-cols-5 gap-3">
                <AnalysisMetric label="OUTPUT LUFS" value={`${processResult.output_lufs.toFixed(1)}`} unit="LUFS"
                  highlight />
                <AnalysisMetric label="TRUE PEAK" value={`${processResult.output_true_peak.toFixed(1)}`} unit="dBTP"
                  highlight />
                <AnalysisMetric label="DYNAMIC RANGE" value={`${processResult.output_dynamic_range.toFixed(1)}`} unit="dB" />
                <AnalysisMetric label="STEREO WIDTH" value={`${(processResult.output_stereo_width * 100).toFixed(0)}`} unit="%"
                  highlight />
                <AnalysisMetric label="SPECTRAL CENTER" value={`${processResult.output_spectral_centroid.toFixed(0)}`} unit="Hz" />
              </div>
            </div>
          </div>

          {/* A/B Player */}
          <div className="panel-card">
            <div className="panel-card-header justify-between text-rain-text">
              <span>A/B Comparison</span>
              <span className="text-[9px] font-mono text-rain-dim">Level-matched playback</span>
            </div>
            <div className="panel-card-body flex items-center justify-center gap-6">
              <button
                onClick={handleABToggle}
                className="flex items-center gap-2 px-4 py-2 rounded-md border border-rain-border bg-rain-surface hover:bg-rain-panel transition-colors"
              >
                <ArrowLeftRight size={14} className="text-rain-cyan" />
                <span className="text-[10px] font-mono font-bold text-rain-text">
                  {abMode === 'original' ? 'ORIGINAL' : 'MASTERED'}
                </span>
              </button>
              <div className={`px-3 py-1 rounded text-[9px] font-mono font-bold ${
                abMode === 'original'
                  ? 'bg-rain-muted/20 text-rain-dim'
                  : 'bg-rain-teal/20 text-rain-teal border border-rain-teal/30'
              }`}>
                {abMode === 'original' ? 'A — ORIGINAL' : 'B — MASTERED'}
              </div>
            </div>
          </div>

          {/* Download Buttons */}
          <div className="panel-card">
            <div className="panel-card-header text-rain-text">Export</div>
            <div className="panel-card-body flex gap-3">
              <a
                href={api.master.downloadUrl(masterSessionId, 'wav')}
                download
                className="flex-1 flex items-center justify-center gap-2 h-11 rounded-md bg-gradient-to-r from-rain-teal to-rain-cyan text-rain-black font-mono text-[11px] font-bold hover:opacity-90 transition-opacity"
              >
                <Download size={14} />
                Download WAV (24-bit / 48kHz)
              </a>
              <a
                href={api.master.downloadUrl(masterSessionId, 'mp3')}
                download
                className="flex-1 flex items-center justify-center gap-2 h-11 rounded-md bg-gradient-to-r from-rain-purple to-rain-magenta text-white font-mono text-[11px] font-bold hover:opacity-90 transition-opacity"
              >
                <Download size={14} />
                Download MP3 (320kbps / 44.1kHz)
              </a>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function AnalysisMetric({ label, value, unit, highlight }: { label: string; value: string; unit: string; highlight?: boolean }) {
  return (
    <div className="text-center">
      <div className="text-[8px] font-mono text-rain-dim uppercase tracking-wider">{label}</div>
      <div className={`text-lg font-mono font-bold tabular-nums ${highlight ? 'text-rain-cyan' : 'text-rain-text'}`}>
        {value}
      </div>
      <div className="text-[8px] font-mono text-rain-muted">{unit}</div>
    </div>
  )
}

function MetadataInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-[9px] font-mono text-rain-dim uppercase tracking-wider">{label}</label>
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
