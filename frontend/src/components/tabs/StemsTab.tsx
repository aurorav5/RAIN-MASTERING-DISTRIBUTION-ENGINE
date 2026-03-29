import { useState } from 'react'
import { TierGate } from '../common/TierGate'

const STEM_SLOTS = [
  { id: 'vocals', label: 'VOCALS', color: '#8B5CF6' },
  { id: 'drums', label: 'DRUMS', color: '#F97316' },
  { id: 'bass', label: 'BASS', color: '#FF4444' },
  { id: 'instruments', label: 'INSTRUMENTS', color: '#00D4FF' },
  { id: 'fx', label: 'FX', color: '#D946EF' },
  { id: 'accompaniment', label: 'ACCOMPANIMENT', color: '#AAFF00' },
] as const

interface StemState {
  muted: boolean
  solo: boolean
  gain: number
}

export default function StemsTab() {
  const [stems, setStems] = useState<Record<string, StemState>>(
    Object.fromEntries(STEM_SLOTS.map(s => [s.id, { muted: false, solo: false, gain: 0 }]))
  )

  const updateStem = (id: string, update: Partial<StemState>) => {
    setStems(prev => ({ ...prev, [id]: { ...prev[id]!, ...update } }))
  }

  return (
    <TierGate requiredTier="creator" feature="Stem mastering">
      <div className="p-2 space-y-3 w-full">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-mono text-rain-dim tracking-widest uppercase">
            6-Stem Separation — Demucs htdemucs_6s
          </h2>
          <button className="px-3 py-1.5 bg-rain-purple/20 border border-rain-purple/30 rounded text-[10px] font-mono text-rain-purple hover:bg-rain-purple/30 transition-colors">
            SEPARATE
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {STEM_SLOTS.map(({ id, label, color }) => {
            const stem = stems[id]!
            return (
              <div key={id} className="panel-card">
                <div className="panel-card-header flex items-center justify-between">
                  <span className="text-[10px] font-mono tracking-widest" style={{ color }}>
                    {label}
                  </span>
                  <span className="text-[9px] font-mono text-rain-muted">
                    {stem.gain > 0 ? '+' : ''}{stem.gain.toFixed(1)} dB
                  </span>
                </div>
                <div className="panel-card-body space-y-3">
                  {/* Waveform placeholder */}
                  <div
                    className="h-12 rounded bg-rain-bg border border-rain-border flex items-center justify-center overflow-hidden"
                  >
                    <div className="flex items-end gap-px h-8">
                      {Array.from({ length: 40 }, (_, i) => (
                        <div
                          key={i}
                          className="w-1 rounded-sm opacity-40"
                          style={{
                            height: `${Math.random() * 100}%`,
                            backgroundColor: color,
                          }}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Mute / Solo buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => updateStem(id, { muted: !stem.muted })}
                      className={`flex-1 h-6 rounded text-[9px] font-mono font-bold tracking-wider border transition-colors ${
                        stem.muted
                          ? 'bg-red-500/20 border-red-500/40 text-red-400'
                          : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                      }`}
                    >
                      M
                    </button>
                    <button
                      onClick={() => updateStem(id, { solo: !stem.solo })}
                      className={`flex-1 h-6 rounded text-[9px] font-mono font-bold tracking-wider border transition-colors ${
                        stem.solo
                          ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400'
                          : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
                      }`}
                    >
                      S
                    </button>
                  </div>

                  {/* Gain slider */}
                  <div className="flex items-center gap-2">
                    <span className="text-[8px] font-mono text-rain-muted w-6">GAIN</span>
                    <input
                      type="range"
                      min="-12"
                      max="12"
                      step="0.1"
                      value={stem.gain}
                      onChange={(e) => updateStem(id, { gain: Number(e.target.value) })}
                      className="rain-slider flex-1"
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </TierGate>
  )
}
