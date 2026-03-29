import { useState, useRef, useCallback, useEffect } from 'react'
import { Play, Square, SkipBack, SkipForward, Volume2 } from 'lucide-react'
import { previewEngine } from '@/utils/preview-engine'
import { useSessionStore } from '@/stores/session'

export function TransportBar() {
  const { inputBuffer, status, outputLufs, inputLufs, inputTruePeak } = useSessionStore()
  const [playing, setPlaying] = useState(false)
  const [volume, setVolume] = useState(80)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const animRef = useRef<number>(0)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const spectrumRef = useRef<HTMLCanvasElement>(null)

  // Draw main waveform
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !inputBuffer) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const data = new Float32Array(inputBuffer.slice(0, Math.min(inputBuffer.byteLength, 44100 * 4 * 30)))
    const w = canvas.width
    const h = canvas.height
    const centerY = h / 2
    const step = Math.max(1, Math.floor(data.length / w))

    ctx.clearRect(0, 0, w, h)

    // Background
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h)
    bgGrad.addColorStop(0, '#0D120D')
    bgGrad.addColorStop(0.5, '#0A0F0A')
    bgGrad.addColorStop(1, '#0D120D')
    ctx.fillStyle = bgGrad
    ctx.fillRect(0, 0, w, h)

    // Center line
    ctx.strokeStyle = 'rgba(0, 212, 170, 0.08)'
    ctx.lineWidth = 0.5
    ctx.beginPath()
    ctx.moveTo(0, centerY)
    ctx.lineTo(w, centerY)
    ctx.stroke()

    // Waveform with gradient
    for (let i = 0; i < w; i++) {
      const idx = i * step
      const val = idx < data.length ? Math.abs(data[idx] ?? 0) : 0
      const barH = val * h * 0.8

      const gradient = ctx.createLinearGradient(0, centerY - barH / 2, 0, centerY + barH / 2)
      gradient.addColorStop(0, `rgba(0, 229, 200, ${0.3 + val * 0.6})`)
      gradient.addColorStop(0.5, `rgba(0, 212, 170, ${0.5 + val * 0.5})`)
      gradient.addColorStop(1, `rgba(0, 229, 200, ${0.3 + val * 0.6})`)

      ctx.fillStyle = gradient
      ctx.fillRect(i, centerY - barH / 2, 1, barH)
    }
  }, [inputBuffer])

  // Mini spectrum analyzer
  useEffect(() => {
    const canvas = spectrumRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width
    const h = canvas.height
    ctx.fillStyle = '#0A0F0A'
    ctx.fillRect(0, 0, w, h)

    // Draw mini bars
    const bars = 16
    const barW = w / bars
    for (let i = 0; i < bars; i++) {
      const v = 0.2 + Math.random() * 0.6
      const barH = v * h * 0.8
      const hue = 160 + (i / bars) * 40
      ctx.fillStyle = `hsla(${hue}, 80%, 50%, ${0.4 + v * 0.4})`
      ctx.fillRect(i * barW + 1, h - barH, barW - 2, barH)
    }
  }, [inputBuffer, status])

  const togglePlay = useCallback(async () => {
    if (!inputBuffer) return
    if (playing) {
      previewEngine.stop()
      setPlaying(false)
      cancelAnimationFrame(animRef.current)
    } else {
      await previewEngine.init()
      await previewEngine.loadAudioFile(inputBuffer)
      previewEngine.play()
      setPlaying(true)
      setDuration(previewEngine.currentTime ?? 0)
    }
  }, [playing, inputBuffer])

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="shrink-0">
      {/* Transport bar */}
      <div className="h-14 bg-rain-surface/80 backdrop-blur-md border-b border-rain-border/30 flex items-center gap-3 px-4">
        {/* Controls */}
        <div className="flex items-center gap-1.5">
          <button className="transport-btn" onClick={() => setCurrentTime(0)}>
            <SkipBack size={12} />
          </button>
          <button
            className={`transport-btn w-10 h-10 ${playing ? 'playing' : ''}`}
            onClick={() => void togglePlay()}
            disabled={!inputBuffer}
          >
            {playing ? <Square size={14} /> : <Play size={14} fill="currentColor" />}
          </button>
          <button className="transport-btn">
            <SkipForward size={12} />
          </button>
        </div>

        {/* Waveform */}
        <div className="flex-1 h-10 bg-rain-bg border border-rain-border/20 rounded-lg overflow-hidden relative">
          <canvas ref={canvasRef} width={1200} height={40} className="w-full h-full" />
          {duration > 0 && (
            <div
              className="absolute top-0 bottom-0 w-px bg-rain-teal"
              style={{ left: `${(currentTime / duration) * 100}%`, boxShadow: '0 0 6px rgba(0,212,170,0.6)' }}
            />
          )}
          {!inputBuffer && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-[10px] font-mono text-rain-muted">
                Drop audio or click to browse &mdash; WAV &middot; FLAC &middot; MP3 &middot; AIFF &middot; OGG &middot; AAC
              </span>
            </div>
          )}
        </div>

        {/* File info */}
        <div className="text-right min-w-[100px]">
          <div className="text-[10px] font-mono text-rain-dim tabular-nums">{formatTime(currentTime)}</div>
          <div className="text-[9px] font-mono text-rain-muted">
            {duration > 0 ? formatTime(duration) : '--:--'}
          </div>
        </div>

        {/* Volume */}
        <div className="flex items-center gap-2 w-28">
          <Volume2 size={12} className="text-rain-dim shrink-0" />
          <input
            type="range" min="0" max="100" value={volume}
            onChange={(e) => {
              const v = Number(e.target.value)
              setVolume(v)
              previewEngine.setVolume((v / 100) * 2 - 1)
            }}
            className="rain-slider flex-1"
          />
        </div>

        {/* Ready indicator */}
        <div className="flex flex-col items-end gap-0.5">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${inputBuffer ? 'bg-rain-green animate-pulse' : 'bg-rain-muted'}`} />
            <span className="text-[9px] font-mono text-rain-dim">{inputBuffer ? 'READY' : 'IDLE'}</span>
          </div>
          {inputBuffer && (
            <span className="text-[8px] font-mono text-rain-muted">WAVE &middot; STEREO</span>
          )}
        </div>

        {/* Mini spectrum */}
        <div className="w-12 h-8 rounded overflow-hidden border border-rain-border/10">
          <canvas ref={spectrumRef} width={48} height={32} className="w-full h-full" />
        </div>
      </div>

      {/* Metrics readout bar */}
      <div className="metrics-bar">
        <div className="metric-item">
          <span className="metric-label">ID</span>
          <span className="metric-value text-rain-amber">{Math.floor(Math.random() * 99999999).toString().padStart(8, '0')}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">LUFS</span>
          <span className={`metric-value ${(inputLufs ?? -14) < -16 ? '' : (inputLufs ?? -14) > -10 ? 'danger' : 'warn'}`}>
            {inputLufs !== null ? inputLufs.toFixed(1) : '--.-'}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">PEAK</span>
          <span className={`metric-value ${(inputTruePeak ?? -1) > -0.5 ? 'danger' : ''}`}>
            {inputTruePeak !== null ? `${inputTruePeak.toFixed(2)}dB` : '--.--dB'}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">CREST</span>
          <span className="metric-value">
            {inputLufs !== null && inputTruePeak !== null
              ? `${(inputTruePeak - inputLufs).toFixed(1)}dB`
              : '--.--dB'}
          </span>
        </div>
        <div className="metric-item">
          <span className="metric-label">QC</span>
          <span className="metric-value">0.00000</span>
        </div>
        <div className="flex-1" />
        {outputLufs !== null && (
          <div className="metric-item">
            <span className="metric-label">OUT</span>
            <span className="metric-value">{outputLufs.toFixed(1)} LUFS</span>
          </div>
        )}
      </div>
    </div>
  )
}
