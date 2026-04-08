import { useState, useCallback } from 'react'
import { Loader2, Headphones, Globe } from 'lucide-react'
import { useSessionStore } from '@/stores/session'
import { useAuthStore } from '@/stores/auth'

export default function SpatialTab() {
  const [msEnabled, setMsEnabled] = useState(false)
  const [midGain, setMidGain] = useState(0)
  const [sideGain, setSideGain] = useState(0)
  const [stereoWidth, setStereoWidth] = useState(1.0)
  const [correlationMode, setCorrelationMode] = useState<'normal' | 'wide' | 'mono'>('normal')

  // Atmos state
  const [atmosProcessing, setAtmosProcessing] = useState(false)
  const [atmosError, setAtmosError] = useState<string | null>(null)
  const [atmosResult, setAtmosResult] = useState<{
    objectCount: number
    genreTemplate: string
    hasBinaural: boolean
  } | null>(null)
  const sessionId = useSessionStore(s => s.sessionId)
  const token = useAuthStore(s => s.accessToken)
  const baseUrl = (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000/api/v1'

  const handleApplySpatial = useCallback(async () => {
    if (!sessionId) return
    setAtmosProcessing(true)
    setAtmosError(null)
    try {
      const res = await fetch(`${baseUrl}/sessions/${sessionId}/spatial`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          ms_enabled: msEnabled,
          mid_gain: midGain,
          side_gain: sideGain,
          stereo_width: stereoWidth,
          binaural_preview: true,
        }),
      })
      if (!res.ok) throw new Error()
      const result = await res.json()
      setAtmosResult({
        objectCount: result.object_count ?? 0,
        genreTemplate: result.genre_template ?? 'default',
        hasBinaural: !!result.binaural_preview_url,
      })
    } catch {
      setAtmosError('Dolby Atmos processing requires Studio Pro tier and GPU backend.')
    } finally {
      setAtmosProcessing(false)
    }
  }, [sessionId, token, baseUrl, msEnabled, midGain, sideGain, stereoWidth])

  return (
    <div className="p-2 space-y-3 w-full">
      {/* M/S Processing */}
      <div className="panel-card">
        <div className="panel-card-header flex items-center justify-between">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            MID / SIDE PROCESSING
          </span>
          <button
            onClick={() => setMsEnabled(!msEnabled)}
            className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold transition-colors ${
              msEnabled
                ? 'bg-rain-purple/20 border border-rain-purple/40 text-rain-purple'
                : 'bg-rain-bg border border-rain-border text-rain-muted'
            }`}
          >
            {msEnabled ? 'ON' : 'OFF'}
          </button>
        </div>
        <div className="panel-card-body space-y-4">
          {/* Mid Gain */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-rain-dim">MID GAIN</span>
              <span className="text-[9px] font-mono text-rain-text tabular-nums">
                {midGain > 0 ? '+' : ''}{midGain.toFixed(1)} dB
              </span>
            </div>
            <input
              type="range"
              min="-6"
              max="6"
              step="0.1"
              value={midGain}
              onChange={(e) => setMidGain(Number(e.target.value))}
              disabled={!msEnabled}
              className="rain-slider w-full"
            />
          </div>

          {/* Side Gain */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-rain-dim">SIDE GAIN</span>
              <span className="text-[9px] font-mono text-rain-text tabular-nums">
                {sideGain > 0 ? '+' : ''}{sideGain.toFixed(1)} dB
              </span>
            </div>
            <input
              type="range"
              min="-6"
              max="6"
              step="0.1"
              value={sideGain}
              onChange={(e) => setSideGain(Number(e.target.value))}
              disabled={!msEnabled}
              className="rain-slider w-full"
            />
          </div>
        </div>
      </div>

      {/* Stereo Width */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            STEREO WIDTH
          </span>
        </div>
        <div className="panel-card-body space-y-4">
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-rain-dim">WIDTH</span>
              <span className="text-[9px] font-mono text-rain-text tabular-nums">
                {(stereoWidth * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="2"
              step="0.01"
              value={stereoWidth}
              onChange={(e) => setStereoWidth(Number(e.target.value))}
              className="rain-slider w-full"
            />
            <div className="flex justify-between text-[8px] font-mono text-rain-muted">
              <span>MONO</span>
              <span>STEREO</span>
              <span>WIDE</span>
            </div>
          </div>

          {/* Correlation Mode */}
          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">CORRELATION MODE</span>
            <div className="flex gap-2">
              {(['normal', 'wide', 'mono'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setCorrelationMode(mode)}
                  className={`flex-1 h-7 rounded text-[9px] font-mono tracking-wider border transition-colors ${
                    correlationMode === mode
                      ? 'bg-rain-cyan/20 border-rain-cyan/40 text-[#00D4FF]'
                      : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                  }`}
                >
                  {mode.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Phase Correlation Meter placeholder */}
          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">PHASE CORRELATION</span>
            <div className="h-4 bg-rain-bg border border-rain-border rounded overflow-hidden relative">
              <div className="absolute inset-y-0 left-1/2 w-px bg-rain-border" />
              <div
                className="absolute inset-y-0 bg-gradient-to-r from-red-500/60 via-yellow-500/60 to-green-500/60"
                style={{ left: '20%', right: '20%' }}
              />
              <div
                className="absolute top-0 bottom-0 w-1 bg-rain-lime rounded"
                style={{ left: '72%' }}
              />
            </div>
            <div className="flex justify-between text-[8px] font-mono text-rain-muted">
              <span>-1</span>
              <span>0</span>
              <span>+1</span>
            </div>
          </div>
        </div>
      </div>

      {/* Atmos Spatial Audio */}
      <div className="panel-card">
        <div className="panel-card-header flex items-center justify-between">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            SPATIAL AUDIO
          </span>
          <span className="text-[8px] font-mono px-2 py-0.5 border border-rain-purple/30 bg-rain-purple/10 text-rain-purple rounded">
            STUDIO PRO
          </span>
        </div>
        <div className="panel-card-body space-y-4">
          <p className="text-[10px] text-rain-dim">
            Apply spatial audio processing with ITD/ILD binaural rendering. Genre-specific object placement.
          </p>

          <button
            className="btn-ghost text-xs py-2 px-4 w-full flex items-center justify-center gap-2"
            onClick={handleApplySpatial}
            disabled={atmosProcessing || !sessionId}
          >
            {atmosProcessing ? (
              <><Loader2 size={12} className="animate-spin" /> Processing...</>
            ) : (
              <><Globe size={12} /> Apply Spatial</>
            )}
          </button>

          {atmosError && (
            <div className="text-[10px] font-mono text-rain-magenta bg-rain-magenta/10 border border-rain-magenta/20 rounded px-3 py-2">
              {atmosError}
            </div>
          )}

          {atmosResult && (
            <div className="space-y-2 pt-3 border-t border-rain-border">
              <div className="flex justify-between text-[10px]">
                <span className="text-rain-dim">Objects</span>
                <span className="font-mono text-rain-white">{atmosResult.objectCount}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-rain-dim">Template</span>
                <span className="font-mono text-rain-white">{atmosResult.genreTemplate}</span>
              </div>
              <div className="flex justify-between text-[10px]">
                <span className="text-rain-dim">Binaural Preview</span>
                <span className="font-mono text-rain-teal">
                  {atmosResult.hasBinaural ? (
                    <span className="flex items-center gap-1"><Headphones size={10} /> Ready</span>
                  ) : 'N/A'}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
