import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useSessionStore } from '@/stores/session'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/utils/api'
import { Download, Lock, ChevronDown, ChevronUp, HelpCircle } from 'lucide-react'

const FORMATS = ['WAV', 'FLAC', 'MP3', 'AAC'] as const
const BIT_DEPTHS = ['16-bit', '24-bit', '32-bit float'] as const
const SAMPLE_RATES = ['44100', '48000', '88200', '96000'] as const
const MP3_BITRATES = ['128', '192', '256', '320'] as const

// File size estimates (hardcoded UI values, not real calculation)
const FILE_SIZE_ESTIMATES: Record<string, string> = {
  'WAV-16-bit-44100': 'WAV 16-bit/44.1kHz: ~31 MB (3:20)',
  'WAV-16-bit-48000': 'WAV 16-bit/48kHz: ~34 MB (3:20)',
  'WAV-16-bit-88200': 'WAV 16-bit/88.2kHz: ~61 MB (3:20)',
  'WAV-16-bit-96000': 'WAV 16-bit/96kHz: ~67 MB (3:20)',
  'WAV-24-bit-44100': 'WAV 24-bit/44.1kHz: ~46 MB (3:20)',
  'WAV-24-bit-48000': 'WAV 24-bit/48kHz: ~52 MB (3:20)',
  'WAV-24-bit-88200': 'WAV 24-bit/88.2kHz: ~91 MB (3:20)',
  'WAV-24-bit-96000': 'WAV 24-bit/96kHz: ~100 MB (3:20)',
  'WAV-32-bit float-44100': 'WAV 32f/44.1kHz: ~62 MB (3:20)',
  'WAV-32-bit float-48000': 'WAV 32f/48kHz: ~67 MB (3:20)',
  'WAV-32-bit float-88200': 'WAV 32f/88.2kHz: ~122 MB (3:20)',
  'WAV-32-bit float-96000': 'WAV 32f/96kHz: ~134 MB (3:20)',
  'FLAC-16-bit-44100': 'FLAC 16-bit/44.1kHz: ~18 MB (3:20)',
  'FLAC-16-bit-48000': 'FLAC 16-bit/48kHz: ~20 MB (3:20)',
  'FLAC-16-bit-88200': 'FLAC 16-bit/88.2kHz: ~36 MB (3:20)',
  'FLAC-16-bit-96000': 'FLAC 16-bit/96kHz: ~39 MB (3:20)',
  'FLAC-24-bit-44100': 'FLAC 24-bit/44.1kHz: ~27 MB (3:20)',
  'FLAC-24-bit-48000': 'FLAC 24-bit/48kHz: ~30 MB (3:20)',
  'FLAC-24-bit-88200': 'FLAC 24-bit/88.2kHz: ~54 MB (3:20)',
  'FLAC-24-bit-96000': 'FLAC 24-bit/96kHz: ~59 MB (3:20)',
  'FLAC-32-bit float-44100': 'FLAC 32f/44.1kHz: ~35 MB (3:20)',
  'FLAC-32-bit float-48000': 'FLAC 32f/48kHz: ~38 MB (3:20)',
  'FLAC-32-bit float-88200': 'FLAC 32f/88.2kHz: ~71 MB (3:20)',
  'FLAC-32-bit float-96000': 'FLAC 32f/96kHz: ~77 MB (3:20)',
  'MP3-128': 'MP3 128kbps: ~3 MB (3:20)',
  'MP3-192': 'MP3 192kbps: ~5 MB (3:20)',
  'MP3-256': 'MP3 256kbps: ~6 MB (3:20)',
  'MP3-320': 'MP3 320kbps: ~8 MB (3:20)',
  'AAC-128': 'AAC 128kbps: ~3 MB (3:20)',
  'AAC-192': 'AAC 192kbps: ~4 MB (3:20)',
  'AAC-256': 'AAC 256kbps: ~6 MB (3:20)',
  'AAC-320': 'AAC 320kbps: ~7 MB (3:20)',
}

function getFileSizeEstimate(
  format: typeof FORMATS[number],
  bitDepth: typeof BIT_DEPTHS[number],
  sampleRate: typeof SAMPLE_RATES[number],
  mp3Bitrate: typeof MP3_BITRATES[number],
): string {
  if (format === 'MP3') return FILE_SIZE_ESTIMATES[`MP3-${mp3Bitrate}`] ?? ''
  if (format === 'AAC') return FILE_SIZE_ESTIMATES[`AAC-${mp3Bitrate}`] ?? ''
  return FILE_SIZE_ESTIMATES[`${format}-${bitDepth}-${sampleRate}`] ?? ''
}

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

  // C2PA section state
  const [certExplainerOpen, setCertExplainerOpen] = useState(false)

  // DDEX AI disclosure state
  const [ddexVocals, setDdexVocals] = useState(false)
  const [ddexInstrumentation, setDdexInstrumentation] = useState(false)
  const [ddexComposition, setDdexComposition] = useState(false)
  const [ddexLyrics, setDdexLyrics] = useState(false)

  const canExport = status === 'complete' && tierGte('spark')
  const fileSizeEstimate = getFileSizeEstimate(format, bitDepth, sampleRate, mp3Bitrate)
  const certIdDisplay = rainCertId ? rainCertId.slice(0, 12) : null

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

          {/* File size estimate */}
          {fileSizeEstimate && (
            <div className="text-[9px] font-mono text-rain-dim bg-rain-panel/50 rounded px-2 py-1.5 border border-rain-border/50">
              {fileSizeEstimate}
            </div>
          )}
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

      {/* ========= C2PA PROVENANCE BADGE SECTION ========= */}
      <div className="panel-card border border-rain-teal/20 shadow-[0_0_12px_rgba(0,212,170,0.06)]">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            RAIN-CERT PROVENANCE
          </span>
        </div>
        <div className="panel-card-body space-y-3">
          {/* Toggle */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={embedCert}
              onChange={(e) => setEmbedCert(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <span className="text-[10px] font-mono text-rain-text">Sign with RAIN-CERT</span>
          </label>

          {/* Manifest preview card */}
          <AnimatePresence>
            {embedCert && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2, ease: 'easeInOut' }}
                className="overflow-hidden"
              >
                <div className="rounded border border-rain-teal/20 bg-rain-panel/60 shadow-[0_0_8px_rgba(0,212,170,0.05)]">
                  {/* Card header */}
                  <div className="flex items-center gap-2 px-3 py-2 border-b border-rain-teal/10">
                    <Lock size={10} className="text-rain-teal shrink-0" />
                    <span className="text-[9px] font-mono tracking-widest text-rain-teal">
                      RAIN-CERT MANIFEST PREVIEW
                    </span>
                  </div>

                  {/* Manifest rows */}
                  <div className="px-3 py-2 space-y-1">
                    {[
                      ['Creator', 'dev-user-phil'],
                      ['Tool', 'RAIN v6.0.0 (RainDSP WASM + FastAPI)'],
                      ['AI Role', 'Post-production mastering (parameter)'],
                      ['Timestamp', '2026-03-31T12:00:00Z'],
                      ['Source hash', 'sha256:abc123def456789a...'],
                      ['Processing hash', 'sha256:def456abc789012b...'],
                    ].map(([label, value]) => (
                      <div key={label} className="flex items-start gap-2">
                        <span className="text-[10px] font-mono text-rain-dim w-28 shrink-0">{label}:</span>
                        <span className="text-[10px] font-mono text-rain-text break-all">{value}</span>
                      </div>
                    ))}

                    {certIdDisplay && (
                      <div className="flex items-start gap-2">
                        <span className="text-[10px] font-mono text-rain-dim w-28 shrink-0">Cert ID:</span>
                        <span className="text-[10px] font-mono text-rain-teal">{certIdDisplay}...</span>
                      </div>
                    )}

                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-mono text-rain-dim w-28 shrink-0">Signature:</span>
                      <span className="text-[10px] font-mono text-rain-green">Ed25519 ✓</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-mono text-rain-dim w-28 shrink-0">EU AI Act:</span>
                      <span className="text-[10px] font-mono text-rain-green">Article 50 compliant ✓</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-mono text-rain-dim w-28 shrink-0">C2PA:</span>
                      <span className="text-[10px] font-mono text-rain-text">v2.2 manifest embedded</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-mono text-rain-dim w-28 shrink-0">DDEX AI:</span>
                      <span className="text-[10px] font-mono text-rain-text">Post-production = YES</span>
                    </div>
                  </div>

                  {/* Expandable explainer */}
                  <div className="border-t border-rain-teal/10">
                    <button
                      onClick={() => setCertExplainerOpen(prev => !prev)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-[9px] font-mono text-rain-dim hover:text-rain-teal transition-colors"
                    >
                      <HelpCircle size={9} />
                      <span>What is RAIN-CERT?</span>
                      {certExplainerOpen
                        ? <ChevronUp size={9} className="ml-auto" />
                        : <ChevronDown size={9} className="ml-auto" />}
                    </button>
                    <AnimatePresence>
                      {certExplainerOpen && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.15, ease: 'easeInOut' }}
                          className="overflow-hidden"
                        >
                          <p className="px-3 pb-3 text-[9px] font-mono text-rain-dim leading-relaxed">
                            RAIN-CERT is a cryptographic provenance certificate embedded in your audio file.
                            It records the exact processing parameters, WASM binary version, and AI model involvement.
                            Ed25519-signed — any tampering invalidates the signature.
                            Required for EU AI Act Article 50 compliance (August 2026).
                          </p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ========= DDEX AI DISCLOSURE SECTION ========= */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            DDEX ERN 4.3.2 AI DISCLOSURE
          </span>
        </div>
        <div className="panel-card-body space-y-2">
          {/* Vocals */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={ddexVocals}
              onChange={(e) => setDdexVocals(e.target.checked)}
              className="w-3 h-3 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <span className="text-[10px] font-mono text-rain-dim">Vocals: user declared</span>
          </label>

          {/* Instrumentation */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={ddexInstrumentation}
              onChange={(e) => setDdexInstrumentation(e.target.checked)}
              className="w-3 h-3 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <span className="text-[10px] font-mono text-rain-dim">Instrumentation: user declared</span>
          </label>

          {/* Composition */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={ddexComposition}
              onChange={(e) => setDdexComposition(e.target.checked)}
              className="w-3 h-3 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <span className="text-[10px] font-mono text-rain-dim">Composition: user declared</span>
          </label>

          {/* Post-production — locked on */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={true}
              readOnly
              className="w-3 h-3 rounded border-rain-border bg-rain-bg accent-rain-teal cursor-not-allowed"
            />
            <span className="text-[10px] font-mono text-rain-text">Post-production (Mastering)</span>
            <Lock size={8} className="text-rain-teal" />
            <span className="text-[8px] font-mono bg-rain-teal/10 border border-rain-teal/20 text-rain-teal px-1.5 py-0.5 rounded">
              RAIN v6.0.0
            </span>
          </div>

          {/* Lyrics */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={ddexLyrics}
              onChange={(e) => setDdexLyrics(e.target.checked)}
              className="w-3 h-3 rounded border-rain-border bg-rain-bg accent-rain-purple"
            />
            <span className="text-[10px] font-mono text-rain-dim">Lyrics: user declared</span>
          </label>

          {/* Compliance badges */}
          <div className="flex items-center gap-2 pt-1">
            <span className="text-[8px] font-mono bg-rain-green/10 border border-rain-green/20 text-rain-green px-2 py-0.5 rounded-full">
              EU AI Act Ready
            </span>
            <span className="text-[8px] font-mono bg-rain-blue/10 border border-rain-blue/20 text-rain-blue px-2 py-0.5 rounded-full">
              DDEX Compliant
            </span>
          </div>
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
