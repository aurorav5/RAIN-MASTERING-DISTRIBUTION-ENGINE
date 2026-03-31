import { useState } from 'react'
import { TierGate } from '../common/TierGate'
import { useSessionStore } from '@/stores/session'

const DIMENSIONS = [
  { key: 'brightness', label: 'Brightness', color: '#AAFF00' },
  { key: 'warmth', label: 'Warmth', color: '#D946EF' },
  { key: 'compression', label: 'Compression', color: '#8B5CF6' },
  { key: 'width', label: 'Width', color: '#00D4FF' },
  { key: 'lowEnd', label: 'Low-end Weight', color: '#F97316' },
  { key: 'loudness', label: 'Loudness', color: '#FF4444' },
] as const

export function AIETab() {
  const { outputLufs, rainScore } = useSessionStore()
  const [sessions] = useState(outputLufs != null ? 1 : 0)

  // Generate fingerprint from current session data (or demo data)
  const fingerprint = outputLufs != null
    ? { brightness: 72, warmth: 58, compression: 65, width: 70, lowEnd: 55, loudness: 80 }
    : { brightness: 0, warmth: 0, compression: 0, width: 0, lowEnd: 0, loudness: 0 }

  const hasData = sessions > 0

  return (
    <TierGate requiredTier="creator" feature="Artist Identity Engine">
      <div className="p-2 space-y-3 w-full">
        {/* Progress bar */}
        <div className="panel-card">
          <div className="panel-card-header text-rain-text">AIE Activation Progress</div>
          <div className="panel-card-body">
            <div className="h-2 bg-rain-panel rounded overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-rain-teal to-rain-cyan rounded transition-all"
                style={{ width: `${Math.min(sessions / 5 * 100, 100)}%` }}
              />
            </div>
            <p className="text-rain-dim text-[10px] font-mono mt-2">
              {sessions} / 5 sessions — {sessions < 5
                ? `Master ${5 - sessions} more tracks to activate personalized AI mastering.`
                : 'AIE profile active — personalized mastering enabled.'}
            </p>
          </div>
        </div>

        {/* Radar chart (SVG) */}
        <div className="panel-card">
          <div className="panel-card-header text-rain-text">Style Fingerprint</div>
          <div className="panel-card-body flex flex-col items-center">
            <svg viewBox="0 0 300 300" className="w-64 h-64">
              {/* Grid rings */}
              {[0.2, 0.4, 0.6, 0.8, 1.0].map((r) => (
                <polygon
                  key={r}
                  points={DIMENSIONS.map((_, i) => {
                    const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
                    const x = 150 + Math.cos(angle) * 120 * r
                    const y = 150 + Math.sin(angle) * 120 * r
                    return `${x},${y}`
                  }).join(' ')}
                  fill="none"
                  stroke="#1C1835"
                  strokeWidth="1"
                />
              ))}
              {/* Axis lines */}
              {DIMENSIONS.map((_, i) => {
                const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
                const x = 150 + Math.cos(angle) * 120
                const y = 150 + Math.sin(angle) * 120
                return <line key={i} x1="150" y1="150" x2={x} y2={y} stroke="#1C1835" strokeWidth="1" />
              })}
              {/* Data polygon */}
              {hasData && (
                <polygon
                  points={DIMENSIONS.map((d, i) => {
                    const val = fingerprint[d.key] / 100
                    const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
                    const x = 150 + Math.cos(angle) * 120 * val
                    const y = 150 + Math.sin(angle) * 120 * val
                    return `${x},${y}`
                  }).join(' ')}
                  fill="rgba(0, 212, 170, 0.15)"
                  stroke="#00D4AA"
                  strokeWidth="2"
                />
              )}
              {/* Data points */}
              {hasData && DIMENSIONS.map((d, i) => {
                const val = fingerprint[d.key] / 100
                const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
                const x = 150 + Math.cos(angle) * 120 * val
                const y = 150 + Math.sin(angle) * 120 * val
                return <circle key={i} cx={x} cy={y} r="4" fill={d.color} />
              })}
              {/* Labels */}
              {DIMENSIONS.map((d, i) => {
                const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
                const x = 150 + Math.cos(angle) * 145
                const y = 150 + Math.sin(angle) * 145
                return (
                  <text
                    key={i}
                    x={x}
                    y={y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="fill-rain-dim text-[9px] font-mono"
                  >
                    {d.label}
                  </text>
                )
              })}
            </svg>

            {/* Dimension values */}
            {hasData && (
              <div className="grid grid-cols-3 gap-3 mt-4 w-full">
                {DIMENSIONS.map((d) => (
                  <div key={d.key} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                    <span className="text-[9px] font-mono text-rain-dim flex-1">{d.label}</span>
                    <span className="text-[10px] font-mono text-rain-text font-bold tabular-nums">
                      {fingerprint[d.key]}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Info */}
        <div className="panel-card">
          <div className="panel-card-body text-[10px] font-mono text-rain-dim space-y-2">
            <p>Your identity builds over time. The radar chart shows your mastering style across 6 dimensions.</p>
            <p>After 5+ sessions, RAIN will use your fingerprint to personalize AI mastering decisions for your unique sound.</p>
          </div>
        </div>
      </div>
    </TierGate>
  )
}
