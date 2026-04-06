import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { TierGate } from '../common/TierGate'

// ─── Types ───────────────────────────────────────────────────────────────────

type AIETab = 'fingerprint' | 'history' | 'evolution' | 'preferences'

interface Fingerprint {
  brightness: number
  warmth: number
  compression: number
  width: number
  lowEnd: number
  loudness: number
}

interface Session {
  id: number
  title: string
  date: string
  genre: string
  lufs: number
  approved: boolean
  fingerprint: Fingerprint
  rating: number
}

type SaturationMode = 'tape' | 'tube' | 'transistor'

interface Preferences {
  truePeakCeiling: number   // -6 to 0 dBTP
  bassMonoBelow: number     // 40–200 Hz
  minLRA: number            // 2–12 LU
  saturationMode: SaturationMode
  customRules: string
}

// ─── Constants ───────────────────────────────────────────────────────────────

const MOCK_SESSIONS: Session[] = [
  {
    id: 1, title: 'Summer Anthem', date: '2026-03-15', genre: 'Electronic',
    lufs: -14.0, approved: true, rating: 0,
    fingerprint: { brightness: 78, warmth: 52, compression: 68, width: 74, lowEnd: 60, loudness: 82 },
  },
  {
    id: 2, title: 'Midnight Drive', date: '2026-02-28', genre: 'Hip-Hop',
    lufs: -13.5, approved: true, rating: 0,
    fingerprint: { brightness: 65, warmth: 71, compression: 75, width: 58, lowEnd: 82, loudness: 85 },
  },
  {
    id: 3, title: 'Crystal Clear', date: '2026-02-10', genre: 'Pop',
    lufs: -14.0, approved: true, rating: 0,
    fingerprint: { brightness: 85, warmth: 45, compression: 55, width: 80, lowEnd: 48, loudness: 78 },
  },
  {
    id: 4, title: 'Deep House Vol.3', date: '2026-01-22', genre: 'Electronic',
    lufs: -12.0, approved: false, rating: 0,
    fingerprint: { brightness: 60, warmth: 68, compression: 80, width: 65, lowEnd: 88, loudness: 90 },
  },
  {
    id: 5, title: 'Acoustic Sessions', date: '2025-12-30', genre: 'Folk',
    lufs: -16.0, approved: true, rating: 0,
    fingerprint: { brightness: 55, warmth: 88, compression: 42, width: 45, lowEnd: 38, loudness: 62 },
  },
]

const DIMENSIONS: { key: keyof Fingerprint; label: string; color: string }[] = [
  { key: 'brightness',  label: 'Brightness', color: '#AAFF00' },
  { key: 'warmth',      label: 'Warmth',     color: '#D946EF' },
  { key: 'compression', label: 'Compress.',  color: '#8B5CF6' },
  { key: 'width',       label: 'Width',      color: '#00D4FF' },
  { key: 'lowEnd',      label: 'Low-end',    color: '#F97316' },
  { key: 'loudness',    label: 'Loudness',   color: '#FF4444' },
]

const GENRE_COLORS: Record<string, string> = {
  'Electronic': '#00D4AA', 'Hip-Hop': '#8B5CF6', 'Pop': '#FA2D48',
  'Rock': '#F97316', 'Folk': '#AAFF00', 'R&B': '#D946EF',
  'Classical': '#4A9EFF', 'Jazz': '#FFD700', 'Country': '#FF9900',
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function avgFingerprint(sessions: Session[]): Fingerprint {
  const n = sessions.length
  if (n === 0) return { brightness: 0, warmth: 0, compression: 0, width: 0, lowEnd: 0, loudness: 0 }
  const sum = sessions.reduce<Fingerprint>(
    (acc, s) => ({
      brightness:  acc.brightness  + s.fingerprint.brightness,
      warmth:      acc.warmth      + s.fingerprint.warmth,
      compression: acc.compression + s.fingerprint.compression,
      width:       acc.width       + s.fingerprint.width,
      lowEnd:      acc.lowEnd      + s.fingerprint.lowEnd,
      loudness:    acc.loudness    + s.fingerprint.loudness,
    }),
    { brightness: 0, warmth: 0, compression: 0, width: 0, lowEnd: 0, loudness: 0 }
  )
  return {
    brightness:  Math.round(sum.brightness  / n),
    warmth:      Math.round(sum.warmth      / n),
    compression: Math.round(sum.compression / n),
    width:       Math.round(sum.width       / n),
    lowEnd:      Math.round(sum.lowEnd      / n),
    loudness:    Math.round(sum.loudness    / n),
  }
}

// Build radar polygon points string from a fingerprint
function radarPoints(fp: Fingerprint, cx: number, cy: number, radius: number): string {
  return DIMENSIONS.map((d, i) => {
    const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
    const val = fp[d.key] / 100
    const x = cx + Math.cos(angle) * radius * val
    const y = cy + Math.sin(angle) * radius * val
    return `${x},${y}`
  }).join(' ')
}

function relativeDate(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / (1000 * 3600 * 24))
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  const weeks = Math.floor(days / 7)
  if (weeks === 1) return '1 week ago'
  if (weeks < 5) return `${weeks} weeks ago`
  const months = Math.floor(days / 30)
  return `${months} months ago`
}

// ─── Radar Chart SVG ─────────────────────────────────────────────────────────

function RadarChart({
  fingerprint,
  genreAvg,
  showGenreAvg,
}: {
  fingerprint: Fingerprint
  genreAvg: Fingerprint
  showGenreAvg: boolean
}) {
  const cx = 150, cy = 150, radius = 110
  const [drawn, setDrawn] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setDrawn(true), 50)
    return () => clearTimeout(t)
  }, [])

  const gridRings = [0.2, 0.4, 0.6, 0.8, 1.0]

  return (
    <svg viewBox="0 0 300 300" className="w-64 h-64">
      {/* Grid rings */}
      {gridRings.map((r) => (
        <polygon
          key={r}
          points={DIMENSIONS.map((_, i) => {
            const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
            return `${cx + Math.cos(angle) * radius * r},${cy + Math.sin(angle) * radius * r}`
          }).join(' ')}
          fill="none"
          stroke="#1C2E1C"
          strokeWidth="1"
        />
      ))}
      {/* Ring labels */}
      {gridRings.map((r) => (
        <text key={`rl${r}`} x={cx + 3} y={cy - radius * r + 3}
          className="fill-rain-muted" style={{ fontSize: 7 }}>
          {r * 100}
        </text>
      ))}
      {/* Axis lines */}
      {DIMENSIONS.map((d, i) => {
        const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
        return (
          <line
            key={i}
            x1={cx} y1={cy}
            x2={cx + Math.cos(angle) * radius}
            y2={cy + Math.sin(angle) * radius}
            stroke="#1C2E1C" strokeWidth="1"
          />
        )
      })}

      {/* Genre average polygon */}
      <AnimatePresence>
        {showGenreAvg && (
          <motion.polygon
            key="genre-avg"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            points={radarPoints(genreAvg, cx, cy, radius)}
            fill="rgba(139,92,246,0.08)"
            stroke="#8B5CF6"
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
        )}
      </AnimatePresence>

      {/* User fingerprint polygon — animated from center */}
      <motion.polygon
        key="user-fp"
        initial={{ points: radarPoints({ brightness: 0, warmth: 0, compression: 0, width: 0, lowEnd: 0, loudness: 0 }, cx, cy, radius) }}
        animate={{ points: drawn ? radarPoints(fingerprint, cx, cy, radius) : radarPoints({ brightness: 0, warmth: 0, compression: 0, width: 0, lowEnd: 0, loudness: 0 }, cx, cy, radius) }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
        fill="rgba(0,212,170,0.12)"
        stroke="#00D4AA"
        strokeWidth="2"
      />

      {/* Data points */}
      {DIMENSIONS.map((d, i) => {
        const val = fingerprint[d.key] / 100
        const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
        const x = cx + Math.cos(angle) * radius * val
        const y = cy + Math.sin(angle) * radius * val
        return (
          <motion.circle
            key={i}
            initial={{ r: 0 }}
            animate={{ r: drawn ? 4 : 0 }}
            transition={{ delay: i * 0.1, duration: 0.3 }}
            cx={x} cy={y}
            fill={d.color}
          />
        )
      })}

      {/* Axis labels */}
      {DIMENSIONS.map((d, i) => {
        const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
        const lx = cx + Math.cos(angle) * (radius + 20)
        const ly = cy + Math.sin(angle) * (radius + 20)
        return (
          <text
            key={i}
            x={lx} y={ly}
            textAnchor="middle" dominantBaseline="middle"
            style={{ fontSize: 9, fill: '#8A9A8A', fontFamily: 'monospace' }}
          >
            {d.label}
          </text>
        )
      })}
    </svg>
  )
}

// ─── Star Rating ──────────────────────────────────────────────────────────────

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          onClick={() => onChange(star)}
          className={`text-sm transition-colors ${star <= value ? 'text-yellow-400' : 'text-rain-muted hover:text-yellow-400/60'}`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

// ─── Mini Radar Thumbnail ─────────────────────────────────────────────────────

function MiniRadar({ fp, color }: { fp: Fingerprint; color: string }) {
  const cx = 40, cy = 40, radius = 32
  return (
    <svg viewBox="0 0 80 80" className="w-12 h-12">
      {[0.33, 0.66, 1].map((r) => (
        <polygon
          key={r}
          points={DIMENSIONS.map((_, i) => {
            const angle = (Math.PI * 2 * i) / DIMENSIONS.length - Math.PI / 2
            return `${cx + Math.cos(angle) * radius * r},${cy + Math.sin(angle) * radius * r}`
          }).join(' ')}
          fill="none" stroke="#1C2E1C" strokeWidth="0.5"
        />
      ))}
      <polygon
        points={radarPoints(fp, cx, cy, radius)}
        fill={`${color}22`} stroke={color} strokeWidth="1"
      />
    </svg>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function AIETab() {
  const [activeTab, setActiveTab] = useState<AIETab>('fingerprint')
  const [sessions, setSessions] = useState<Session[]>(MOCK_SESSIONS)
  const [compareMode, setCompareMode] = useState(false)
  const [expandedSession, setExpandedSession] = useState<number | null>(null)
  const [historyFilter, setHistoryFilter] = useState<'all' | 'approved' | 'rejected' | string>('all')
  const [preferences, setPreferences] = useState<Preferences>({
    truePeakCeiling: -1.0,
    bassMonoBelow: 80,
    minLRA: 6,
    saturationMode: 'tape',
    customRules: '{\n  "never_boost_above_khz": 12,\n  "min_dynamic_range": 8\n}',
  })

  const approvedSessions = sessions.filter((s) => s.approved)
  const userFingerprint = avgFingerprint(approvedSessions)
  const genreAvg: Fingerprint = { brightness: 70, warmth: 60, compression: 65, width: 68, lowEnd: 62, loudness: 75 }

  const tabs: { id: AIETab; label: string }[] = [
    { id: 'fingerprint', label: 'FINGERPRINT' },
    { id: 'history',     label: 'HISTORY'     },
    { id: 'evolution',   label: 'EVOLUTION'   },
    { id: 'preferences', label: 'PREFERENCES' },
  ]

  function setRating(sessionId: number, rating: number) {
    setSessions((prev) => prev.map((s) => s.id === sessionId ? { ...s, rating } : s))
  }

  // Build Recharts data
  const evolutionData = sessions
    .slice()
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .map((s) => ({
      name: new Date(s.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      ...Object.fromEntries(DIMENSIONS.map((d) => [d.key, s.fingerprint[d.key]])),
    }))

  // Filter sessions for history tab
  const filteredSessions = sessions.filter((s) => {
    if (historyFilter === 'approved') return s.approved
    if (historyFilter === 'rejected') return !s.approved
    if (historyFilter !== 'all') return s.genre === historyFilter
    return true
  })

  const uniqueGenres = Array.from(new Set(sessions.map((s) => s.genre)))

  const prefSliderClass = "rain-slider flex-1"

  return (
    <TierGate requiredTier="creator" feature="Artist Identity Engine">
      <div className="p-2 space-y-3 w-full">

        {/* ── Inner tab bar ─────────────────────────────────────────────── */}
        <div className="flex gap-1 border-b border-rain-border pb-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`tab-3d ${activeTab === t.id ? 'active' : ''}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait">

          {/* ── TAB 1: FINGERPRINT ──────────────────────────────────────── */}
          {activeTab === 'fingerprint' && (
            <motion.div
              key="fingerprint"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="space-y-3"
            >
              {/* Status bar */}
              <div className="flex items-center justify-between p-3 rounded-lg glass-panel">
                <div className="flex items-center gap-2">
                  <motion.div
                    animate={{ opacity: [0.6, 1, 0.6] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                    className="w-2 h-2 rounded-full bg-rain-green"
                    style={{ boxShadow: '0 0 6px rgba(74,255,138,0.6)' }}
                  />
                  <span className="text-[10px] font-mono text-rain-green font-bold">
                    {approvedSessions.length}/5 tracks analyzed — Identity Active
                  </span>
                </div>
                <button
                  onClick={() => setCompareMode((v) => !v)}
                  className={`px-3 py-1 rounded text-[9px] font-mono border transition-colors ${
                    compareMode
                      ? 'border-rain-purple/50 text-rain-purple bg-rain-purple/10'
                      : 'border-rain-border text-rain-dim hover:text-rain-text'
                  }`}
                >
                  Compare to Genre
                </button>
              </div>

              {/* Radar + dimension cards */}
              <div className="panel-card">
                <div className="panel-card-header">Style Fingerprint</div>
                <div className="panel-card-body flex flex-col items-center gap-4">
                  <RadarChart
                    fingerprint={userFingerprint}
                    genreAvg={genreAvg}
                    showGenreAvg={compareMode}
                  />

                  {compareMode && (
                    <div className="flex items-center gap-4 text-[9px] font-mono">
                      <span className="flex items-center gap-1">
                        <span className="w-6 h-0.5 bg-rain-teal inline-block" />
                        <span className="text-rain-teal">Your style</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-6 border-t border-rain-purple border-dashed inline-block" />
                        <span className="text-rain-purple">Genre average</span>
                      </span>
                    </div>
                  )}

                  {/* 2×3 dimension cards */}
                  <div className="grid grid-cols-3 gap-2 w-full">
                    {DIMENSIONS.map((d) => (
                      <div key={d.key} className="p-2 rounded glass-panel space-y-1">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                          <span className="text-[9px] font-mono text-rain-silver">{d.label}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full bg-rain-border overflow-hidden">
                            <motion.div
                              className="h-full rounded-full"
                              style={{ backgroundColor: d.color }}
                              initial={{ width: 0 }}
                              animate={{ width: `${userFingerprint[d.key]}%` }}
                              transition={{ duration: 0.8, ease: 'easeOut' }}
                            />
                          </div>
                          <span className="text-[10px] font-mono font-bold tabular-nums text-rain-text w-8 text-right">
                            {userFingerprint[d.key]}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* ── TAB 2: HISTORY ──────────────────────────────────────────── */}
          {activeTab === 'history' && (
            <motion.div
              key="history"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="space-y-3"
            >
              {/* Filter bar */}
              <div className="flex flex-wrap gap-1.5 items-center">
                {(['all', 'approved', 'rejected'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setHistoryFilter(f)}
                    className={`px-3 py-1 rounded text-[9px] font-mono border uppercase font-bold transition-colors ${
                      historyFilter === f
                        ? 'bg-rain-teal/10 text-rain-teal border-rain-teal/20'
                        : 'border-rain-border text-rain-dim hover:text-rain-text'
                    }`}
                  >
                    {f}
                  </button>
                ))}
                <div className="relative">
                  <select
                    value={historyFilter}
                    onChange={(e) => setHistoryFilter(e.target.value)}
                    className="bg-rain-bg border border-rain-border rounded px-3 py-1 text-[9px] font-mono text-rain-dim
                      focus:border-rain-teal/40 focus:outline-none appearance-none pr-6 cursor-pointer"
                  >
                    <option value="all">All genres</option>
                    {uniqueGenres.map((g) => (
                      <option key={g} value={g}>{g}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Session list */}
              <div className="space-y-2">
                {filteredSessions.map((s) => (
                  <div key={s.id} className="panel-card">
                    <div
                      className="panel-card-body cursor-pointer"
                      onClick={() => setExpandedSession(expandedSession === s.id ? null : s.id)}
                    >
                      <div className="flex items-center gap-3 flex-wrap">
                        {/* Title + genre */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-rain-text">{s.title}</span>
                            <span
                              className="badge text-[8px]"
                              style={{
                                color: GENRE_COLORS[s.genre] ?? '#8A9A8A',
                                background: `${GENRE_COLORS[s.genre] ?? '#8A9A8A'}15`,
                                border: `1px solid ${GENRE_COLORS[s.genre] ?? '#8A9A8A'}30`,
                              }}
                            >
                              {s.genre}
                            </span>
                          </div>
                          <div className="text-[9px] font-mono text-rain-dim mt-0.5">{relativeDate(s.date)}</div>
                        </div>

                        {/* LUFS */}
                        <span className="badge badge-outline text-[9px] tabular-nums">{s.lufs.toFixed(1)} LUFS</span>

                        {/* Status */}
                        <span className={`badge text-[9px] ${s.approved ? 'badge-green' : 'badge-red'}`}>
                          {s.approved ? 'APPROVED' : 'REJECTED'}
                        </span>

                        {/* Star rating */}
                        <StarRating
                          value={s.rating}
                          onChange={(v) => { setRating(s.id, v) }}
                        />

                        {/* Expand toggle */}
                        <motion.span
                          animate={{ rotate: expandedSession === s.id ? 180 : 0 }}
                          className="text-rain-muted text-xs"
                        >
                          ▼
                        </motion.span>
                      </div>
                    </div>

                    {/* Expanded: mini radar */}
                    <AnimatePresence>
                      {expandedSession === s.id && (
                        <motion.div
                          key="mini-radar"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden border-t border-rain-border/50"
                        >
                          <div className="px-3 py-3 flex items-center gap-4">
                            <MiniRadar fp={s.fingerprint} color={GENRE_COLORS[s.genre] ?? '#00D4AA'} />
                            <div className="grid grid-cols-3 gap-x-4 gap-y-1">
                              {DIMENSIONS.map((d) => (
                                <div key={d.key} className="flex items-center gap-1.5">
                                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                                  <span className="text-[8px] font-mono text-rain-dim">{d.label}</span>
                                  <span className="text-[9px] font-mono text-rain-text tabular-nums ml-auto">{s.fingerprint[d.key]}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* ── TAB 3: EVOLUTION ────────────────────────────────────────── */}
          {activeTab === 'evolution' && (
            <motion.div
              key="evolution"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="space-y-3"
            >
              <div className="panel-card">
                <div className="panel-card-header">Style Evolution — All Dimensions</div>
                <div className="panel-card-body">
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={evolutionData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                      <CartesianGrid stroke="#1E2E1E" strokeDasharray="3 3" />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: '#5A6A5A', fontSize: 9, fontFamily: 'monospace' }}
                        axisLine={{ stroke: '#1E2E1E' }}
                        tickLine={false}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: '#5A6A5A', fontSize: 9, fontFamily: 'monospace' }}
                        axisLine={{ stroke: '#1E2E1E' }}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{
                          background: '#111A11',
                          border: '1px solid rgba(0,212,170,0.15)',
                          borderRadius: 8,
                          fontSize: 10,
                          fontFamily: 'monospace',
                          color: '#D0E0D0',
                        }}
                        labelStyle={{ color: '#00D4AA', marginBottom: 4 }}
                      />
                      {/* Annotation line on session 2→3 */}
                      <ReferenceLine
                        x={evolutionData[1]?.name}
                        stroke="#8B5CF6"
                        strokeDasharray="4 3"
                        label={{ value: 'More compression', fill: '#8B5CF6', fontSize: 8, dx: 4 }}
                      />
                      {DIMENSIONS.map((d) => (
                        <Line
                          key={d.key}
                          type="monotone"
                          dataKey={d.key}
                          stroke={d.color}
                          strokeWidth={1.5}
                          dot={{ fill: d.color, r: 3 }}
                          activeDot={{ r: 5 }}
                          name={d.label}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>

                  {/* Legend */}
                  <div className="flex flex-wrap gap-3 mt-3">
                    {DIMENSIONS.map((d) => (
                      <div key={d.key} className="flex items-center gap-1.5">
                        <span className="w-3 h-0.5 rounded-full inline-block" style={{ backgroundColor: d.color }} />
                        <span className="text-[9px] font-mono text-rain-silver">{d.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="panel-card">
                <div className="panel-card-body">
                  <p className="text-[10px] font-mono text-rain-dim italic">
                    Your style is trending brighter and wider over time.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* ── TAB 4: PREFERENCES ──────────────────────────────────────── */}
          {activeTab === 'preferences' && (
            <motion.div
              key="preferences"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="space-y-3"
            >
              <div className="panel-card">
                <div className="panel-card-header">Explicit Preference Overrides</div>
                <div className="panel-card-body space-y-4">

                  {/* True peak ceiling */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-mono text-rain-silver uppercase tracking-wider">
                        True peak ceiling
                      </label>
                      <span className="text-[10px] font-mono text-rain-teal tabular-nums">
                        {preferences.truePeakCeiling.toFixed(1)} dBTP
                      </span>
                    </div>
                    <input
                      type="range"
                      min={-6}
                      max={0}
                      step={0.1}
                      value={preferences.truePeakCeiling}
                      onChange={(e) =>
                        setPreferences((p) => ({ ...p, truePeakCeiling: Number(e.target.value) }))
                      }
                      className={prefSliderClass}
                    />
                  </div>

                  {/* Bass mono below */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-mono text-rain-silver uppercase tracking-wider">
                        Bass mono below
                      </label>
                      <span className="text-[10px] font-mono text-rain-teal tabular-nums">
                        {preferences.bassMonoBelow} Hz
                      </span>
                    </div>
                    <input
                      type="range"
                      min={40}
                      max={200}
                      step={5}
                      value={preferences.bassMonoBelow}
                      onChange={(e) =>
                        setPreferences((p) => ({ ...p, bassMonoBelow: Number(e.target.value) }))
                      }
                      className={prefSliderClass}
                    />
                  </div>

                  {/* Minimum LRA */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-mono text-rain-silver uppercase tracking-wider">
                        Minimum LRA
                      </label>
                      <span className="text-[10px] font-mono text-rain-teal tabular-nums">
                        {preferences.minLRA} LU
                      </span>
                    </div>
                    <input
                      type="range"
                      min={2}
                      max={12}
                      step={0.5}
                      value={preferences.minLRA}
                      onChange={(e) =>
                        setPreferences((p) => ({ ...p, minLRA: Number(e.target.value) }))
                      }
                      className={prefSliderClass}
                    />
                  </div>

                  {/* Saturation mode */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-mono text-rain-silver uppercase tracking-wider">
                      Preferred saturation
                    </label>
                    <div className="flex gap-2">
                      {(['tape', 'tube', 'transistor'] as SaturationMode[]).map((mode) => (
                        <label key={mode} className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="radio"
                            name="satMode"
                            value={mode}
                            checked={preferences.saturationMode === mode}
                            onChange={() => setPreferences((p) => ({ ...p, saturationMode: mode }))}
                            className="accent-rain-teal"
                          />
                          <span className={`text-[10px] font-mono capitalize ${
                            preferences.saturationMode === mode ? 'text-rain-teal' : 'text-rain-dim'
                          }`}>
                            {mode}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Custom rules */}
              <div className="panel-card">
                <div className="panel-card-header">Custom Rules (JSON)</div>
                <div className="panel-card-body">
                  <textarea
                    value={preferences.customRules}
                    onChange={(e) => setPreferences((p) => ({ ...p, customRules: e.target.value }))}
                    rows={5}
                    className="input-field font-mono text-xs resize-y"
                    spellCheck={false}
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button className="btn-primary">Save Preferences</button>
                <button
                  className="text-[10px] font-mono text-rain-dim hover:text-rain-teal transition-colors underline underline-offset-2"
                  onClick={() =>
                    setPreferences({
                      truePeakCeiling: -1.0,
                      bassMonoBelow: 80,
                      minLRA: 6,
                      saturationMode: 'tape',
                      customRules: '{\n  "never_boost_above_khz": 12,\n  "min_dynamic_range": 8\n}',
                    })
                  }
                >
                  Reset to AI Defaults
                </button>
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </TierGate>
  )
}
