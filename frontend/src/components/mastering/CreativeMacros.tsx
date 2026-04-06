import { useState, useMemo, useCallback } from 'react'
import { MacroKnob } from './MacroKnob'
import type { MacroValues } from '@/stores/session'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Source of the current macro values. */
export type MacroSource = 'MODEL' | 'HEURISTIC' | 'MANUAL'

export type { MacroValues }

export interface CreativeMacrosProps {
  /** Current macro values (0.0 - 10.0 each). */
  values: MacroValues
  /** Called when any macro knob changes. */
  onChange: (key: keyof MacroValues, value: number) => void
  /** Detected genre/style from analysis, if available. */
  genre?: string | undefined
  /** How the current values were derived. */
  source?: MacroSource | undefined
  /** Model/heuristic confidence (0 - 100). Only shown when source is MODEL or HEURISTIC. */
  confidence?: number | undefined
  /** Callback for the AI Suggest button. */
  onAiSuggest?: (() => void) | undefined
  /** Whether an AI suggestion request is in flight. */
  aiSuggestLoading?: boolean | undefined
}

// ---------------------------------------------------------------------------
// Macro definitions (all 7 canonical macros)
// ---------------------------------------------------------------------------

interface MacroDef {
  key: keyof MacroValues
  label: string
  color: string
  description: string
}

const MACROS: readonly MacroDef[] = [
  {
    key: 'brighten',
    label: 'BRIGHTEN',
    color: '#AAFF00',
    description: 'High-frequency presence, air, sparkle',
  },
  {
    key: 'glue',
    label: 'GLUE',
    color: '#8B5CF6',
    description: 'Bus compression, cohesion, unified mix feel',
  },
  {
    key: 'width',
    label: 'WIDTH',
    color: '#00D4FF',
    description: 'Stereo width, spatial spread',
  },
  {
    key: 'punch',
    label: 'PUNCH',
    color: '#F97316',
    description: 'Transient emphasis, impact, drum presence',
  },
  {
    key: 'warmth',
    label: 'WARMTH',
    color: '#D946EF',
    description: 'Harmonic saturation, analog tone',
  },
  {
    key: 'space',
    label: 'SPACE',
    color: '#06B6D4',
    description: 'Spatial depth, reverb, immersive quality',
  },
  {
    key: 'repair',
    label: 'REPAIR',
    color: '#10B981',
    description: 'Spectral repair intensity (noise reduction, de-click, de-ess)',
  },
] as const

// ---------------------------------------------------------------------------
// Tension pairs -- warns when conflicting macros are both cranked (> 7)
// ---------------------------------------------------------------------------

interface TensionPair {
  keys: [keyof MacroValues, keyof MacroValues]
  message: string
}

const TENSION_PAIRS: readonly TensionPair[] = [
  { keys: ['brighten', 'warmth'], message: 'High shelf + THD boost may cause harshness' },
  { keys: ['glue', 'width'], message: 'Heavy compression + wide stereo may cause instability' },
  { keys: ['glue', 'punch'], message: 'Bus compression + transient boost creates conflicting dynamics' },
  { keys: ['warmth', 'punch'], message: 'Saturation + transient emphasis may over-distort attacks' },
  { keys: ['brighten', 'repair'], message: 'Air boost + spectral repair may cancel each other' },
  { keys: ['space', 'punch'], message: 'Reverb depth + transient emphasis may blur impact' },
] as const

const TENSION_THRESHOLD = 7.0

/** Total possible macro intensity (7 macros x 10.0 max). */
const MAX_TOTAL_INTENSITY = 70.0

// ---------------------------------------------------------------------------
// Source badge styles
// ---------------------------------------------------------------------------

function getSourceStyle(source: MacroSource): { bg: string; fg: string } {
  switch (source) {
    case 'MODEL':
      return { bg: 'rgba(16,185,129,0.15)', fg: '#10B981' }
    case 'HEURISTIC':
      return { bg: 'rgba(251,146,60,0.15)', fg: '#FBB440' }
    case 'MANUAL':
      return { bg: 'rgba(255,255,255,0.06)', fg: '#6B7280' }
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreativeMacros({
  values,
  onChange,
  genre,
  source = 'MANUAL',
  confidence,
  onAiSuggest,
  aiSuggestLoading = false,
}: CreativeMacrosProps) {
  const [hoveredMacro, setHoveredMacro] = useState<string | null>(null)

  // Compute all active tension warnings
  const tensionWarnings = useMemo(() => {
    return TENSION_PAIRS.filter(
      ({ keys }) => values[keys[0]] > TENSION_THRESHOLD && values[keys[1]] > TENSION_THRESHOLD,
    )
  }, [values])

  const handleChange = useCallback(
    (key: keyof MacroValues) => (value: number) => {
      onChange(key, value)
    },
    [onChange],
  )

  const totalIntensity = useMemo(
    () => Object.values(values).reduce((a, b) => a + b, 0),
    [values],
  )

  const sourceStyle = getSourceStyle(source)
  const showConfidence = (source === 'MODEL' || source === 'HEURISTIC') && confidence !== undefined

  return (
    <div className="panel-card flex-1">
      {/* ---- Header ---- */}
      <div className="panel-card-header text-rain-text flex items-center justify-between">
        <span className="text-[11px] font-mono font-bold tracking-wider uppercase">
          Creative Macro System
        </span>

        {/* Source / genre badges */}
        <div className="flex items-center gap-2">
          {genre && (
            <span
              className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded"
              style={{ background: 'rgba(255,255,255,0.06)', color: '#9CA3AF' }}
            >
              {genre}
            </span>
          )}
          <span
            className="text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded"
            style={{ background: sourceStyle.bg, color: sourceStyle.fg }}
          >
            {source}
            {showConfidence && (
              <span style={{ opacity: 0.7 }}>{' '}{confidence}%</span>
            )}
          </span>
        </div>
      </div>

      {/* ---- Body ---- */}
      <div className="panel-card-body">
        {/* Tension warning banners */}
        {tensionWarnings.length > 0 && (
          <div className="space-y-1 mb-3">
            {tensionWarnings.map(({ keys, message }) => (
              <div
                key={`${keys[0]}-${keys[1]}`}
                className="flex items-center gap-2 px-3 py-1.5 rounded border text-[9px] font-mono"
                style={{
                  background: 'rgba(251,146,60,0.10)',
                  borderColor: 'rgba(251,146,60,0.35)',
                  color: '#FBB440',
                }}
              >
                <TensionIcon />
                <span>{message}</span>
              </div>
            ))}
          </div>
        )}

        {/* ---- 7 Macro knobs row ---- */}
        <div className="flex justify-around items-start gap-1">
          {MACROS.map((macro) => (
            <div
              key={macro.key}
              className="relative flex flex-col items-center"
              onMouseEnter={() => setHoveredMacro(macro.key)}
              onMouseLeave={() => setHoveredMacro(null)}
            >
              {/* Tooltip on hover */}
              {hoveredMacro === macro.key && (
                <div
                  className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap z-50 px-2 py-1 rounded text-[9px] font-mono pointer-events-none"
                  style={{
                    background: '#1C1835',
                    border: '1px solid rgba(255,255,255,0.12)',
                    color: '#9CA3AF',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
                  }}
                >
                  {macro.description}
                </div>
              )}

              {/* Label above knob */}
              <span
                className="text-[9px] font-mono font-bold tracking-widest uppercase mb-1.5"
                style={{ color: macro.color, opacity: 0.85 }}
              >
                {macro.label}
              </span>

              {/* Rotary knob (72px) */}
              <MacroKnob
                label={macro.label}
                value={values[macro.key]}
                onChange={handleChange(macro.key)}
                color={macro.color}
                size={72}
                showLabel={false}
              />

              {/* Value readout below knob */}
              <span
                className="text-[10px] font-mono font-bold mt-1"
                style={{ color: values[macro.key] > 0 ? macro.color : '#4B5563', opacity: 0.9 }}
              >
                {values[macro.key].toFixed(1)}
              </span>
            </div>
          ))}
        </div>

        {/* ---- Bottom bar ---- */}
        <div
          className="flex items-center justify-between mt-4 pt-3"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
        >
          {/* AI Suggest button */}
          <button
            type="button"
            onClick={onAiSuggest}
            disabled={aiSuggestLoading || !onAiSuggest}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:enabled:brightness-125"
            style={{
              background: 'rgba(20,184,166,0.12)',
              color: '#14B8A6',
              border: '1px solid rgba(20,184,166,0.25)',
            }}
            onMouseEnter={(e) => {
              if (!aiSuggestLoading && onAiSuggest) {
                e.currentTarget.style.background = 'rgba(20,184,166,0.22)'
                e.currentTarget.style.borderColor = 'rgba(20,184,166,0.45)'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(20,184,166,0.12)'
              e.currentTarget.style.borderColor = 'rgba(20,184,166,0.25)'
            }}
          >
            {aiSuggestLoading ? (
              <>
                <LoadingSpinner />
                Analyzing...
              </>
            ) : (
              <>
                <AiIcon />
                AI Suggest
              </>
            )}
          </button>

          {/* Total macro intensity readout */}
          <div className="text-[9px] font-mono text-rain-dim">
            Total intensity:{' '}
            <span
              className="font-bold"
              style={{ color: totalIntensity > 50 ? '#FBB440' : '#6B7280' }}
            >
              {totalIntensity.toFixed(1)}
            </span>
            <span> / {MAX_TOTAL_INTENSITY.toFixed(1)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline SVG icons (no external dependencies)
// ---------------------------------------------------------------------------

function AiIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M6 1L7.2 4.8L11 6L7.2 7.2L6 11L4.8 7.2L1 6L4.8 4.8L6 1Z"
        fill="currentColor"
        opacity="0.9"
      />
    </svg>
  )
}

function LoadingSpinner() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="animate-spin"
    >
      <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" opacity="0.25" />
      <path d="M6 1A5 5 0 0 1 11 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function TensionIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="flex-shrink-0"
    >
      <path
        d="M5.134 1.866a1 1 0 0 1 1.732 0l4.134 7.166A1 1 0 0 1 10.134 10.5H1.866a1 1 0 0 1-.866-1.468l4.134-7.166Z"
        fill="currentColor"
        opacity="0.8"
      />
      <text x="6" y="9" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#1C1835">!</text>
    </svg>
  )
}
