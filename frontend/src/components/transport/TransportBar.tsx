import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import {
  Play,
  Pause,
  Square,
  SkipBack,
  SkipForward,
  Rewind,
  FastForward,
  Repeat,
  Circle,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { previewEngine } from '@/utils/preview-engine'
import { useSessionStore } from '@/stores/session'
import { useAudioStore } from '@/stores/audioStore'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TimeDisplayMode = 'timecode' | 'samples'
type ABState = 'A' | 'B'

interface SessionFileInfo {
  fileName: string
  sampleRate: number
  bitDepth: number
  channels: number
  duration: number
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const METER_MIN_DB = -60
const METER_MAX_DB = 0
const METER_CLIP_DB = -0.3
const METER_YELLOW_DB = -12
const METER_ORANGE_DB = -6

const DEFAULT_FILE_INFO: SessionFileInfo = {
  fileName: 'No file loaded',
  sampleRate: 0,
  bitDepth: 0,
  channels: 0,
  duration: 0,
}

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

function formatTimecode(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 1000)
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
}

function formatSamples(seconds: number, sampleRate: number): string {
  if (sampleRate === 0) return '000000000'
  const samples = Math.floor(seconds * sampleRate)
  return String(samples).padStart(9, '0')
}

function dbToMeterFraction(db: number): number {
  if (db <= METER_MIN_DB) return 0
  if (db >= METER_MAX_DB) return 1
  return (db - METER_MIN_DB) / (METER_MAX_DB - METER_MIN_DB)
}

function volumeToDb(normalizedVolume: number): number {
  if (normalizedVolume <= 0) return -Infinity
  // 0..1 maps to -60..+6 dB
  return normalizedVolume * 66 - 60
}

function dbToVolumeNormalized(db: number): number {
  return (db + 60) / 66
}

function formatVolumeDb(db: number): string {
  if (db <= -60) return '-inf'
  const sign = db >= 0 ? '+' : ''
  return `${sign}${db.toFixed(1)}`
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Large monospace timecode / sample display */
function TimecodeDisplay({
  currentTime,
  duration,
  mode,
  sampleRate,
  onToggleMode,
}: {
  currentTime: number
  duration: number
  mode: TimeDisplayMode
  sampleRate: number
  onToggleMode: () => void
}) {
  const display =
    mode === 'timecode'
      ? formatTimecode(currentTime)
      : formatSamples(currentTime, sampleRate)

  const totalDisplay =
    mode === 'timecode'
      ? formatTimecode(duration)
      : formatSamples(duration, sampleRate)

  return (
    <button
      type="button"
      onClick={onToggleMode}
      className="flex flex-col items-end justify-center px-3 py-1 rounded
                 bg-[#060A06] border border-rain-border/40 min-w-[140px]
                 cursor-pointer select-none hover:border-rain-teal/30 transition-colors"
      title={`Click to switch to ${mode === 'timecode' ? 'samples' : 'timecode'} display`}
    >
      <span className="font-mono text-[17px] leading-tight tracking-wider text-rain-teal tabular-nums">
        {display}
      </span>
      <span className="font-mono text-[10px] leading-tight text-rain-dim tabular-nums">
        {duration > 0 ? totalDisplay : mode === 'timecode' ? '--:--.---' : '---------'}
      </span>
    </button>
  )
}

/** Single transport control button */
function TransportButton({
  onClick,
  disabled = false,
  active = false,
  activeColor = 'teal',
  title,
  shortcut,
  size = 'normal',
  children,
}: {
  onClick: () => void
  disabled?: boolean
  active?: boolean
  activeColor?: 'teal' | 'red'
  title: string
  shortcut?: string
  size?: 'normal' | 'large'
  children: React.ReactNode
}) {
  const sizeClasses = size === 'large' ? 'w-11 h-11' : 'w-9 h-9'
  const activeStyles =
    active && activeColor === 'teal'
      ? 'bg-rain-teal/20 text-rain-teal border-rain-teal/40'
      : active && activeColor === 'red'
        ? 'bg-rain-red/20 text-rain-red border-rain-red/40'
        : 'text-rain-silver border-rain-border/30 hover:text-rain-white hover:border-rain-border/60'

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={shortcut ? `${title} [${shortcut}]` : title}
      className={`
        relative flex items-center justify-center rounded
        ${sizeClasses} ${activeStyles}
        border bg-rain-surface/60
        transition-all duration-100
        disabled:opacity-30 disabled:cursor-not-allowed
        active:scale-95
      `}
    >
      {children}
      {shortcut && (
        <span className="absolute -bottom-3.5 left-1/2 -translate-x-1/2
                         text-[8px] font-mono text-rain-muted opacity-0
                         group-hover:opacity-100 pointer-events-none
                         transition-opacity">
          {shortcut}
        </span>
      )}
    </button>
  )
}

/** Horizontal L/R peak meters */
function PeakMeters({ leftDb, rightDb }: { leftDb: number; rightDb: number }) {
  return (
    <div className="flex flex-col gap-0.5 w-[100px] justify-center">
      <MeterBar label="L" db={leftDb} />
      <MeterBar label="R" db={rightDb} />
    </div>
  )
}

function MeterBar({ label, db }: { label: string; db: number }) {
  const fraction = dbToMeterFraction(db)
  const isClipping = db > METER_CLIP_DB

  // Determine bar color based on level
  let barColor = 'bg-rain-green'
  if (db > METER_ORANGE_DB) barColor = 'bg-rain-red'
  else if (db > METER_YELLOW_DB) barColor = 'bg-rain-amber'

  return (
    <div className="flex items-center gap-1">
      <span className="text-[8px] font-mono text-rain-dim w-2 text-right">{label}</span>
      <div className="flex-1 h-[5px] bg-[#060A06] rounded-sm overflow-hidden relative">
        <div
          className={`absolute inset-y-0 left-0 ${barColor} rounded-sm transition-[width] duration-75`}
          style={{ width: `${fraction * 100}%` }}
        />
      </div>
      <div
        className={`w-1.5 h-1.5 rounded-full ${
          isClipping ? 'bg-rain-red' : 'bg-rain-muted/30'
        }`}
        title={isClipping ? 'CLIP' : 'OK'}
      />
    </div>
  )
}

/** A/B comparison toggle */
function ABToggle({
  state,
  onToggle,
  disabled,
}: {
  state: ABState
  onToggle: () => void
  disabled: boolean
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      title="Toggle A/B comparison [A]"
      className={`
        flex items-center gap-0.5 px-2 py-1 rounded border text-[11px] font-mono font-semibold
        transition-all duration-100 select-none
        ${disabled ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer active:scale-95'}
        ${
          state === 'A'
            ? 'bg-rain-surface/60 text-rain-silver border-rain-border/40'
            : 'bg-rain-teal/15 text-rain-teal border-rain-teal/40'
        }
      `}
    >
      <span className={state === 'A' ? 'text-rain-white' : 'text-rain-dim'}>A</span>
      <span className="text-rain-muted">/</span>
      <span className={state === 'B' ? 'text-rain-teal' : 'text-rain-dim'}>B</span>
    </button>
  )
}

/** Mini waveform overview strip with playhead */
function WaveformOverview({
  peaks,
  currentTime,
  duration,
  loopEnabled,
  loopStart,
  loopEnd,
  onSeek,
}: {
  peaks: Float32Array | null
  currentTime: number
  duration: number
  loopEnabled: boolean
  loopStart: number
  loopEnd: number
  onSeek: (fraction: number) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Draw waveform
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    const w = rect.width
    const h = rect.height
    const centerY = h / 2

    // Clear
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#060A06'
    ctx.fillRect(0, 0, w, h)

    // Center line
    ctx.strokeStyle = 'rgba(0, 212, 170, 0.06)'
    ctx.lineWidth = 0.5
    ctx.beginPath()
    ctx.moveTo(0, centerY)
    ctx.lineTo(w, centerY)
    ctx.stroke()

    if (!peaks || peaks.length === 0) return

    const step = Math.max(1, Math.floor(peaks.length / w))
    ctx.fillStyle = 'rgba(0, 212, 170, 0.5)'

    for (let x = 0; x < w; x++) {
      const idx = Math.floor(x * (peaks.length / w))
      let maxVal = 0
      for (let j = 0; j < step && idx + j < peaks.length; j++) {
        const val = Math.abs(peaks[idx + j] ?? 0)
        if (val > maxVal) maxVal = val
      }
      const barH = maxVal * h * 0.85
      ctx.fillRect(x, centerY - barH / 2, 1, barH)
    }

    // Draw loop region if enabled
    if (loopEnabled && duration > 0) {
      const loopStartX = (loopStart / duration) * w
      const loopEndX = (loopEnd / duration) * w
      ctx.fillStyle = 'rgba(0, 212, 170, 0.08)'
      ctx.fillRect(loopStartX, 0, loopEndX - loopStartX, h)
      ctx.strokeStyle = 'rgba(0, 212, 170, 0.25)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(loopStartX, 0)
      ctx.lineTo(loopStartX, h)
      ctx.moveTo(loopEndX, 0)
      ctx.lineTo(loopEndX, h)
      ctx.stroke()
    }
  }, [peaks, loopEnabled, loopStart, loopEnd, duration])

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const container = containerRef.current
      if (!container || duration <= 0) return
      const rect = container.getBoundingClientRect()
      const fraction = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
      onSeek(fraction)
    },
    [duration, onSeek]
  )

  const playheadPosition = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div
      ref={containerRef}
      onClick={handleClick}
      className="flex-1 h-8 bg-[#060A06] border border-rain-border/20 rounded overflow-hidden
                 relative cursor-crosshair select-none"
    >
      <canvas ref={canvasRef} className="w-full h-full" />
      {/* Playhead */}
      {duration > 0 && (
        <div
          className="absolute top-0 bottom-0 w-px bg-rain-white pointer-events-none"
          style={{
            left: `${playheadPosition}%`,
            boxShadow: '0 0 4px rgba(208, 224, 208, 0.6)',
          }}
        />
      )}
      {/* Empty state */}
      {!peaks && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[9px] font-mono text-rain-muted">NO WAVEFORM</span>
        </div>
      )}
    </div>
  )
}

/** Rotary volume knob with dB readout */
function VolumeKnob({
  volumeDb,
  onVolumeChange,
  muted,
  onToggleMute,
}: {
  volumeDb: number
  onVolumeChange: (db: number) => void
  muted: boolean
  onToggleMute: () => void
}) {
  const knobRef = useRef<HTMLDivElement>(null)
  const dragStartRef = useRef<{ startY: number; startDb: number } | null>(null)

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      dragStartRef.current = { startY: e.clientY, startDb: volumeDb }

      const handleMouseMove = (ev: MouseEvent) => {
        if (!dragStartRef.current) return
        const delta = (dragStartRef.current.startY - ev.clientY) * 0.5
        const newDb = Math.max(-60, Math.min(6, dragStartRef.current.startDb + delta))
        onVolumeChange(newDb)
      }

      const handleMouseUp = () => {
        dragStartRef.current = null
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }

      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    },
    [volumeDb, onVolumeChange]
  )

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault()
      const delta = e.deltaY > 0 ? -1 : 1
      const newDb = Math.max(-60, Math.min(6, volumeDb + delta))
      onVolumeChange(newDb)
    },
    [volumeDb, onVolumeChange]
  )

  // Rotation: -60dB = -135deg, +6dB = +135deg
  const rotation = ((volumeDb + 60) / 66) * 270 - 135

  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={onToggleMute}
        className="text-rain-dim hover:text-rain-white transition-colors"
        title="Mute [M]"
      >
        {muted ? <VolumeX size={13} /> : <Volume2 size={13} />}
      </button>

      <div
        ref={knobRef}
        onMouseDown={handleMouseDown}
        onWheel={handleWheel}
        className="w-7 h-7 rounded-full bg-rain-surface border border-rain-border/50
                   cursor-ns-resize relative flex items-center justify-center
                   hover:border-rain-teal/30 transition-colors select-none"
        title="Volume — drag or scroll to adjust"
      >
        {/* Knob indicator line */}
        <div
          className="absolute w-px h-2.5 bg-rain-teal origin-bottom"
          style={{
            transform: `rotate(${rotation}deg)`,
            bottom: '50%',
            left: 'calc(50% - 0.5px)',
          }}
        />
        {/* Center dot */}
        <div className="w-1 h-1 rounded-full bg-rain-border" />
      </div>

      <span
        className={`font-mono text-[10px] tabular-nums w-10 text-right ${
          muted ? 'text-rain-red' : 'text-rain-dim'
        }`}
      >
        {muted ? 'MUTE' : `${formatVolumeDb(volumeDb)}dB`}
      </span>
    </div>
  )
}

/** Session file info display */
function SessionInfo({ info }: { info: SessionFileInfo }) {
  if (info.sampleRate === 0) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] font-mono text-rain-muted">NO SESSION</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-start gap-0">
      <span
        className="text-[10px] font-mono text-rain-silver truncate max-w-[120px]"
        title={info.fileName}
      >
        {info.fileName}
      </span>
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] font-mono text-rain-dim">
          {(info.sampleRate / 1000).toFixed(1)}kHz
        </span>
        <span className="text-[9px] font-mono text-rain-muted">/</span>
        <span className="text-[9px] font-mono text-rain-dim">{info.bitDepth}bit</span>
        <span className="text-[9px] font-mono text-rain-muted">/</span>
        <span className="text-[9px] font-mono text-rain-dim">
          {info.channels === 1 ? 'MONO' : info.channels === 2 ? 'STEREO' : `${info.channels}ch`}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main TransportBar component
// ---------------------------------------------------------------------------

export function TransportBar() {
  const { inputBuffer, outputBuffer, status } = useSessionStore()
  const {
    playbackPosition,
    isPlaying,
    meters,
    setPlaybackPosition,
    setIsPlaying,
    waveformPeaks,
  } = useAudioStore()

  // Local state
  const [timeMode, setTimeMode] = useState<TimeDisplayMode>('timecode')
  const [abState, setABState] = useState<ABState>('A')
  const [loopEnabled, setLoopEnabled] = useState(false)
  const [loopStart] = useState(0)
  const [loopEnd, setLoopEnd] = useState(0)
  const [volumeDb, setVolumeDb] = useState(0)
  const [muted, setMuted] = useState(false)
  const [duration, setDuration] = useState(0)
  const [fileInfo, setFileInfo] = useState<SessionFileInfo>(DEFAULT_FILE_INFO)

  const animRef = useRef<number>(0)
  const playStartTimeRef = useRef(0)
  const playStartOffsetRef = useRef(0)

  const hasInput = inputBuffer !== null
  const hasOutput = outputBuffer !== null

  // Derive file info from buffer when loaded
  useEffect(() => {
    if (!inputBuffer) {
      setFileInfo(DEFAULT_FILE_INFO)
      setDuration(0)
      setLoopEnd(0)
      return
    }

    // We parse basic info -- the preview engine gives us duration/sampleRate on load
    void (async () => {
      try {
        await previewEngine.init()
        const result = await previewEngine.loadAudioFile(inputBuffer)
        setDuration(result.duration)
        setLoopEnd(result.duration)
        setFileInfo({
          fileName: 'Untitled', // session store does not carry file name
          sampleRate: result.sampleRate,
          bitDepth: 32, // Web Audio always decodes to float32
          channels: 2,
          duration: result.duration,
        })
      } catch {
        // Decoding failed -- leave defaults
      }
    })()
  }, [inputBuffer])

  // Animation loop for playback position
  useEffect(() => {
    if (!isPlaying) {
      cancelAnimationFrame(animRef.current)
      return
    }

    const tick = () => {
      const elapsed = (performance.now() - playStartTimeRef.current) / 1000
      const pos = playStartOffsetRef.current + elapsed
      if (pos >= duration && duration > 0) {
        if (loopEnabled) {
          // Restart from loop start
          playStartTimeRef.current = performance.now()
          playStartOffsetRef.current = loopStart
          previewEngine.stop()
          previewEngine.play(loopStart)
        } else {
          handleStop()
          return
        }
      }
      setPlaybackPosition(Math.min(pos, duration))
      animRef.current = requestAnimationFrame(tick)
    }
    animRef.current = requestAnimationFrame(tick)

    return () => cancelAnimationFrame(animRef.current)
  }, [isPlaying, duration, loopEnabled, loopStart, setPlaybackPosition])

  // Apply volume changes
  useEffect(() => {
    previewEngine.setVolume(muted ? -Infinity : volumeDb)
  }, [volumeDb, muted])

  // ---------------------------------------------------------------------------
  // Transport actions
  // ---------------------------------------------------------------------------

  const handlePlay = useCallback(async () => {
    if (!hasInput) return
    if (isPlaying) return

    try {
      await previewEngine.init()
      await previewEngine.loadAudioFile(inputBuffer)
      previewEngine.play(playbackPosition)
      playStartTimeRef.current = performance.now()
      playStartOffsetRef.current = playbackPosition
      setIsPlaying(true)
    } catch {
      // Audio context or decode failure
    }
  }, [hasInput, isPlaying, inputBuffer, playbackPosition, setIsPlaying])

  const handlePause = useCallback(() => {
    previewEngine.stop()
    setIsPlaying(false)
  }, [setIsPlaying])

  const handleStop = useCallback(() => {
    previewEngine.stop()
    setIsPlaying(false)
    setPlaybackPosition(0)
    playStartOffsetRef.current = 0
  }, [setIsPlaying, setPlaybackPosition])

  const handlePlayPause = useCallback(() => {
    if (isPlaying) {
      handlePause()
    } else {
      void handlePlay()
    }
  }, [isPlaying, handlePause, handlePlay])

  const handlePrevious = useCallback(() => {
    // Go to beginning, or if at beginning, stay
    setPlaybackPosition(0)
    playStartOffsetRef.current = 0
    if (isPlaying) {
      previewEngine.stop()
      previewEngine.play(0)
      playStartTimeRef.current = performance.now()
    }
  }, [isPlaying, setPlaybackPosition])

  const handleNext = useCallback(() => {
    // Jump to end
    if (duration > 0) {
      const endPos = Math.max(0, duration - 0.01)
      setPlaybackPosition(endPos)
      if (isPlaying) {
        handleStop()
      }
    }
  }, [duration, isPlaying, handleStop, setPlaybackPosition])

  const handleRewind = useCallback(() => {
    const newPos = Math.max(0, playbackPosition - 5)
    setPlaybackPosition(newPos)
    playStartOffsetRef.current = newPos
    if (isPlaying) {
      previewEngine.stop()
      previewEngine.play(newPos)
      playStartTimeRef.current = performance.now()
    }
  }, [playbackPosition, isPlaying, setPlaybackPosition])

  const handleForward = useCallback(() => {
    const newPos = Math.min(duration, playbackPosition + 5)
    setPlaybackPosition(newPos)
    playStartOffsetRef.current = newPos
    if (isPlaying) {
      previewEngine.stop()
      previewEngine.play(newPos)
      playStartTimeRef.current = performance.now()
    }
  }, [playbackPosition, duration, isPlaying, setPlaybackPosition])

  const handleSeek = useCallback(
    (fraction: number) => {
      const newPos = fraction * duration
      setPlaybackPosition(newPos)
      playStartOffsetRef.current = newPos
      if (isPlaying) {
        previewEngine.stop()
        previewEngine.play(newPos)
        playStartTimeRef.current = performance.now()
      }
    },
    [duration, isPlaying, setPlaybackPosition]
  )

  const handleABToggle = useCallback(() => {
    setABState((prev) => (prev === 'A' ? 'B' : 'A'))
  }, [])

  const handleLoopToggle = useCallback(() => {
    setLoopEnabled((prev) => !prev)
  }, [])

  const handleMuteToggle = useCallback(() => {
    setMuted((prev) => !prev)
  }, [])

  // ---------------------------------------------------------------------------
  // Keyboard shortcuts
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return
      }

      switch (e.key) {
        case ' ':
          e.preventDefault()
          handlePlayPause()
          break
        case 'Enter':
          e.preventDefault()
          handleStop()
          break
        case 'a':
        case 'A':
          handleABToggle()
          break
        case 'l':
        case 'L':
          handleLoopToggle()
          break
        case 'm':
        case 'M':
          handleMuteToggle()
          break
        case 'ArrowLeft':
          e.preventDefault()
          handleRewind()
          break
        case 'ArrowRight':
          e.preventDefault()
          handleForward()
          break
        case 'Home':
          e.preventDefault()
          handlePrevious()
          break
        case 'End':
          e.preventDefault()
          handleNext()
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [
    handlePlayPause,
    handleStop,
    handleABToggle,
    handleLoopToggle,
    handleMuteToggle,
    handleRewind,
    handleForward,
    handlePrevious,
    handleNext,
  ])

  // ---------------------------------------------------------------------------
  // Memoized values
  // ---------------------------------------------------------------------------

  const statusLabel = useMemo(() => {
    switch (status) {
      case 'idle':
        return hasInput ? 'READY' : 'IDLE'
      case 'uploading':
        return 'UPLOADING'
      case 'analyzing':
        return 'ANALYZING'
      case 'processing':
        return 'PROCESSING'
      case 'complete':
        return 'COMPLETE'
      case 'failed':
        return 'FAILED'
      default:
        return 'IDLE'
    }
  }, [status, hasInput])

  const statusColor = useMemo(() => {
    switch (status) {
      case 'complete':
        return 'bg-rain-green'
      case 'failed':
        return 'bg-rain-red'
      case 'analyzing':
      case 'processing':
      case 'uploading':
        return 'bg-rain-amber animate-pulse'
      default:
        return hasInput ? 'bg-rain-green' : 'bg-rain-muted'
    }
  }, [status, hasInput])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="shrink-0">
      {/* Main transport bar — 56px fixed height */}
      <div
        className="h-14 flex items-center gap-2 px-3"
        style={{
          background: '#0A0F0A',
          borderTop: '1px solid rgba(30, 46, 30, 0.5)',
        }}
      >
        {/* Session info + status */}
        <div className="flex items-center gap-2 min-w-[130px]">
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${statusColor}`} />
            <span className="text-[8px] font-mono text-rain-dim tracking-wider">{statusLabel}</span>
          </div>
          <SessionInfo info={fileInfo} />
        </div>

        {/* Divider */}
        <div className="w-px h-7 bg-rain-border/30" />

        {/* Timecode display */}
        <TimecodeDisplay
          currentTime={playbackPosition}
          duration={duration}
          mode={timeMode}
          sampleRate={fileInfo.sampleRate}
          onToggleMode={() => setTimeMode((m) => (m === 'timecode' ? 'samples' : 'timecode'))}
        />

        {/* Divider */}
        <div className="w-px h-7 bg-rain-border/30" />

        {/* Transport controls */}
        <div className="flex items-center gap-1 group">
          <TransportButton onClick={handlePrevious} disabled={!hasInput} title="Return to Zero" shortcut="Home">
            <SkipBack size={13} />
          </TransportButton>

          <TransportButton onClick={handleRewind} disabled={!hasInput} title="Rewind 5s" shortcut="Left">
            <Rewind size={13} />
          </TransportButton>

          <TransportButton onClick={handleStop} disabled={!hasInput} title="Stop" shortcut="Enter">
            <Square size={12} fill="currentColor" />
          </TransportButton>

          <TransportButton
            onClick={handlePlayPause}
            disabled={!hasInput}
            active={isPlaying}
            activeColor="teal"
            title={isPlaying ? 'Pause' : 'Play'}
            shortcut="Space"
            size="large"
          >
            {isPlaying ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
          </TransportButton>

          <TransportButton onClick={handleForward} disabled={!hasInput} title="Forward 5s" shortcut="Right">
            <FastForward size={13} />
          </TransportButton>

          <TransportButton onClick={handleNext} disabled={!hasInput} title="Go to End" shortcut="End">
            <SkipForward size={13} />
          </TransportButton>

          {/* Record button — disabled for mastering workflow */}
          <TransportButton onClick={() => {}} disabled title="Record (not available in mastering)" activeColor="red">
            <Circle size={12} fill="currentColor" />
          </TransportButton>
        </div>

        {/* Divider */}
        <div className="w-px h-7 bg-rain-border/30" />

        {/* Waveform overview strip */}
        <WaveformOverview
          peaks={waveformPeaks}
          currentTime={playbackPosition}
          duration={duration}
          loopEnabled={loopEnabled}
          loopStart={loopStart}
          loopEnd={loopEnd}
          onSeek={handleSeek}
        />

        {/* Divider */}
        <div className="w-px h-7 bg-rain-border/30" />

        {/* Peak meters */}
        <PeakMeters leftDb={meters.left} rightDb={meters.right} />

        {/* Divider */}
        <div className="w-px h-7 bg-rain-border/30" />

        {/* Loop toggle */}
        <TransportButton
          onClick={handleLoopToggle}
          active={loopEnabled}
          activeColor="teal"
          title="Loop"
          shortcut="L"
        >
          <Repeat size={13} />
        </TransportButton>

        {/* A/B toggle */}
        <ABToggle state={abState} onToggle={handleABToggle} disabled={!hasOutput} />

        {/* Divider */}
        <div className="w-px h-7 bg-rain-border/30" />

        {/* Volume knob */}
        <VolumeKnob
          volumeDb={volumeDb}
          onVolumeChange={setVolumeDb}
          muted={muted}
          onToggleMute={handleMuteToggle}
        />
      </div>
    </div>
  )
}
