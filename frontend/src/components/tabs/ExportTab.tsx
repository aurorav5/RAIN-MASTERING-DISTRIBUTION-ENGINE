import { useState } from 'react'
import { useSessionStore } from '@/stores/session'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/utils/api'
import { Download } from 'lucide-react'

const FORMATS = ['WAV', 'FLAC', 'MP3', 'AAC'] as const
const BIT_DEPTHS = ['16-bit', '24-bit', '32-bit float'] as const
const SAMPLE_RATES = ['44100', '48000', '88200', '96000'] as const
const MP3_BITRATES = ['128', '192', '256', '320'] as const

export default function ExportTab() {
  const { status, rainCertId } = useSessionStore()
  const { tierGte } = useAuthStore()
  const [format, setFormat] = useState<typeof FORMATS[number]>('WAV')
  const [bitDepth, setBitDepth] = useState<typeof BIT_DEPTHS[number]>('24-bit')
  const [sampleRate, setSampleRate] = useState<typeof SAMPLE_RATES[number]>('48000')
  const [mp3Bitrate, setMp3Bitrate] = useState<typeof MP3_BITRATES[number]>('320')
  const [normalize, setNormalize] = useState(true)
  const [dither, setDither] = useState(true)
  const [embedCert, setEmbedCert] = useState(true)

  const canExport = status === 'complete' && tierGte('spark')

  return (
    <div className="p-2 space-y-3 w-full">
      {/* Format selector */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            OUTPUT FORMAT
          </span>
        </div>
        <div className="panel-card-body space-y-4">
          <div className="flex gap-2">
            {FORMATS.map(f => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={`flex-1 h-9 rounded text-[10px] font-mono font-bold tracking-wider border transition-colors ${
                  format === f
                    ? 'bg-rain-purple/20 border-rain-purple/40 text-rain-purple'
                    : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Bit depth (WAV/FLAC only) */}
          {(format === 'WAV' || format === 'FLAC') && (
            <div className="space-y-1">
              <span className="text-[9px] font-mono text-rain-dim">BIT DEPTH</span>
              <div className="flex gap-2">
                {BIT_DEPTHS.map(bd => (
                  <button
                    key={bd}
                    onClick={() => setBitDepth(bd)}
                    className={`flex-1 h-7 rounded text-[9px] font-mono tracking-wider border transition-colors ${
                      bitDepth === bd
                        ? 'bg-rain-cyan/20 border-rain-cyan/40 text-[#00D4FF]'
                        : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                    }`}
                  >
                    {bd}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* MP3 bitrate */}
          {format === 'MP3' && (
            <div className="space-y-1">
              <span className="text-[9px] font-mono text-rain-dim">BITRATE (kbps)</span>
              <div className="flex gap-2">
                {MP3_BITRATES.map(br => (
                  <button
                    key={br}
                    onClick={() => setMp3Bitrate(br)}
                    className={`flex-1 h-7 rounded text-[9px] font-mono tracking-wider border transition-colors ${
                      mp3Bitrate === br
                        ? 'bg-rain-magenta/20 border-rain-magenta/40 text-rain-magenta'
                        : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                    }`}
                  >
                    {br}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Sample rate */}
          <div className="space-y-1">
            <span className="text-[9px] font-mono text-rain-dim">SAMPLE RATE</span>
            <select
              value={sampleRate}
              onChange={(e) => setSampleRate(e.target.value as typeof SAMPLE_RATES[number])}
              className="w-full bg-rain-bg border border-rain-border rounded px-2 py-1.5 text-rain-text text-[10px] font-mono"
            >
              {SAMPLE_RATES.map(sr => (
                <option key={sr} value={sr}>{Number(sr).toLocaleString()} Hz</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Options */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            OPTIONS
          </span>
        </div>
        <div className="panel-card-body space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={normalize}
              onChange={(e) => setNormalize(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <span className="text-[10px] font-mono text-rain-text">Normalize to target LUFS</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={dither}
              onChange={(e) => setDither(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <span className="text-[10px] font-mono text-rain-text">Apply TPDF dither (16-bit)</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={embedCert}
              onChange={(e) => setEmbedCert(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-rain-text">Embed RAIN-CERT</span>
              {rainCertId && (
                <span className="text-[8px] font-mono text-rain-dim">{rainCertId}</span>
              )}
            </div>
          </label>
        </div>
      </div>

      {/* Export buttons — WAV and MP3 from prototype backend */}
      {canExport && useSessionStore.getState().sessionId ? (
        <div className="flex gap-3">
          <a
            href={api.master.downloadUrl(useSessionStore.getState().sessionId!, format === 'WAV' ? 'wav' : 'mp3')}
            download
            className="flex-1 flex items-center justify-center gap-2 h-10 rounded bg-gradient-to-r from-rain-purple to-rain-magenta text-white font-mono text-xs tracking-widest font-bold hover:opacity-90 transition-opacity"
          >
            <Download size={14} />
            EXPORT {format}
          </a>
        </div>
      ) : (
        <button
          disabled={!canExport}
          className={`w-full h-10 rounded font-mono text-xs tracking-widest font-bold transition-all ${
            canExport
              ? 'bg-gradient-to-r from-rain-purple to-rain-magenta text-white hover:opacity-90'
              : 'bg-rain-panel border border-rain-border text-rain-muted cursor-not-allowed'
          }`}
        >
          {status !== 'complete' ? 'MASTER FIRST' : !tierGte('spark') ? 'UPGRADE TO EXPORT' : 'EXPORT'}
        </button>
      )}
    </div>
  )
}
