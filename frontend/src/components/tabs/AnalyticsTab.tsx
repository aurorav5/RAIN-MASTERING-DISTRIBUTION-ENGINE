import { useState } from 'react'

// Demo data — connects to session history API when available
const MOCK_SESSIONS = [
  { id: 'ses_001', date: '2026-03-28', track: 'Midnight Drive', genre: 'Electronic', score: 94, lufs: -14.0 },
  { id: 'ses_002', date: '2026-03-27', track: 'Golden Hour', genre: 'Pop', score: 91, lufs: -13.8 },
  { id: 'ses_003', date: '2026-03-26', track: 'Bass Culture', genre: 'Hip-Hop', score: 88, lufs: -14.2 },
  { id: 'ses_004', date: '2026-03-25', track: 'Velvet Sky', genre: 'R&B', score: 96, lufs: -14.0 },
  { id: 'ses_005', date: '2026-03-24', track: 'Storm Front', genre: 'Rock', score: 85, lufs: -13.5 },
] as const

// Demo data — connects to session history API when available
const GENRE_DIST = [
  { genre: 'Electronic', pct: 35, color: '#8B5CF6' },
  { genre: 'Pop', pct: 25, color: '#D946EF' },
  { genre: 'Hip-Hop', pct: 20, color: '#F97316' },
  { genre: 'R&B', pct: 12, color: '#00D4FF' },
  { genre: 'Rock', pct: 8, color: '#AAFF00' },
] as const

export default function AnalyticsTab() {
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d')

  return (
    <div className="p-2 space-y-3 w-full">
      {/* Time range selector */}
      <div className="flex items-center gap-2">
        {(['7d', '30d', '90d', 'all'] as const).map(range => (
          <button
            key={range}
            onClick={() => setTimeRange(range)}
            className={`px-3 py-1 rounded text-[9px] font-mono tracking-wider border transition-colors ${
              timeRange === range
                ? 'bg-rain-purple/20 border-rain-purple/40 text-rain-purple'
                : 'bg-rain-bg border-rain-border text-rain-dim hover:text-rain-text'
            }`}
          >
            {range === 'all' ? 'ALL' : range.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'SESSIONS', value: '127', sub: '+12 this week' },
          { label: 'AVG SCORE', value: '91.2', sub: '+2.1 vs last period' },
          { label: 'RENDERS', value: '84', sub: '66% render rate' },
          { label: 'AVG LUFS', value: '-14.0', sub: 'Target aligned' },
        ].map(({ label, value, sub }) => (
          <div key={label} className="panel-card">
            <div className="panel-card-body text-center py-3">
              <span className="text-[8px] font-mono text-rain-dim tracking-widest block mb-1">{label}</span>
              <span className="text-lg font-mono font-bold text-rain-text block">{value}</span>
              <span className="text-[8px] font-mono text-rain-dim">{sub}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Genre distribution */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            GENRE DISTRIBUTION
          </span>
        </div>
        <div className="panel-card-body space-y-2">
          {GENRE_DIST.map(({ genre, pct, color }) => (
            <div key={genre} className="flex items-center gap-3">
              <span className="text-[9px] font-mono text-rain-dim w-20">{genre}</span>
              <div className="flex-1 h-3 bg-rain-bg border border-rain-border rounded overflow-hidden">
                <div
                  className="h-full rounded transition-all"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
              <span className="text-[9px] font-mono text-rain-text tabular-nums w-8 text-right">{pct}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Deep Analysis — 43-dimensional feature data */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            DEEP ANALYSIS
          </span>
        </div>
        <div className="panel-card-body">
          <div className="grid grid-cols-2 gap-3">
            {/* Card 1 — TONAL */}
            <div className="panel-card border-l-2" style={{ borderLeftColor: '#8B5CF6' }}>
              <div className="panel-card-header">
                <span className="text-[9px] font-mono tracking-widest" style={{ color: '#8B5CF6' }}>
                  TONAL
                </span>
              </div>
              <div className="panel-card-body py-2 space-y-1">
                {[
                  { label: 'Estimated Key', value: 'C major (confidence 78%)' },
                  { label: 'BPM',           value: '128 bpm (confidence 94%)' },
                  { label: 'Time Signature',value: '4/4' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-rain-dim">{label}:</span>
                    <span className="text-rain-text">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Card 2 — SPECTRAL */}
            <div className="panel-card border-l-2" style={{ borderLeftColor: '#D946EF' }}>
              <div className="panel-card-header">
                <span className="text-[9px] font-mono tracking-widest" style={{ color: '#D946EF' }}>
                  SPECTRAL
                </span>
              </div>
              <div className="panel-card-body py-2 space-y-1">
                {[
                  { label: 'Centroid', value: '3.2 kHz' },
                  { label: 'Rolloff',  value: '14.8 kHz' },
                  { label: 'Flatness', value: '0.31' },
                  { label: 'THD',      value: '0.8%' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-rain-dim">{label}:</span>
                    <span className="text-rain-text">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Card 3 — STEREO */}
            <div className="panel-card border-l-2" style={{ borderLeftColor: '#00D4FF' }}>
              <div className="panel-card-header">
                <span className="text-[9px] font-mono tracking-widest" style={{ color: '#00D4FF' }}>
                  STEREO
                </span>
              </div>
              <div className="panel-card-body py-2 space-y-1">
                {[
                  { label: 'Width',       value: '0.72' },
                  { label: 'Correlation', value: '0.91' },
                  { label: 'M/S Ratio',   value: '2.4 dB' },
                  { label: 'Balance',     value: '+0.1 dB' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-rain-dim">{label}:</span>
                    <span className="text-rain-text">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Card 4 — DYNAMICS */}
            <div className="panel-card border-l-2" style={{ borderLeftColor: '#F97316' }}>
              <div className="panel-card-header">
                <span className="text-[9px] font-mono tracking-widest" style={{ color: '#F97316' }}>
                  DYNAMICS
                </span>
              </div>
              <div className="panel-card-body py-2 space-y-1">
                {[
                  { label: 'Dynamic Range', value: '12.4 LU' },
                  { label: 'Crest Factor',  value: '14.2 dB' },
                  { label: 'PSR',           value: '16.1 dB' },
                  { label: 'RMS',           value: '-18.3 dBFS' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-rain-dim">{label}:</span>
                    <span className="text-rain-text">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Session history */}
      <div className="panel-card">
        <div className="panel-card-header">
          <span className="text-[10px] font-mono tracking-widest text-rain-text">
            SESSION HISTORY
          </span>
        </div>
        <div className="panel-card-body">
          <table className="w-full text-[10px] font-mono">
            <thead>
              <tr className="text-rain-dim border-b border-rain-border">
                <th className="text-left py-1.5 font-normal tracking-wider">DATE</th>
                <th className="text-left py-1.5 font-normal tracking-wider">TRACK</th>
                <th className="text-left py-1.5 font-normal tracking-wider">GENRE</th>
                <th className="text-right py-1.5 font-normal tracking-wider">LUFS</th>
                <th className="text-right py-1.5 font-normal tracking-wider">SCORE</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_SESSIONS.map(({ id, date, track, genre, score, lufs }) => (
                <tr key={id} className="border-b border-rain-border/50 text-rain-text hover:bg-rain-panel/50 transition-colors">
                  <td className="py-1.5 text-rain-dim">{date}</td>
                  <td className="py-1.5">{track}</td>
                  <td className="py-1.5 text-rain-dim">{genre}</td>
                  <td className="py-1.5 text-right tabular-nums">{lufs.toFixed(1)}</td>
                  <td className="py-1.5 text-right">
                    <span className={`tabular-nums ${score >= 90 ? 'text-rain-lime' : score >= 80 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {score}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
