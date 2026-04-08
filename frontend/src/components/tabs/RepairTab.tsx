import { useState, useCallback } from 'react'
import {
  Scissors,
  Wind,
  MousePointer2,
  Mic2,
  Waves,
  Layers,
  Play,
  CheckCircle,
  AlertTriangle,
  Info,
  Lock,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RepairTool {
  id: string
  label: string
  description: string
  icon: React.ReactNode
  accentColor: string
  requiresBadge?: 'stems' | 'studio-pro'
  controls: ToolControl[]
}

type ToolControl =
  | { kind: 'slider'; name: string; label: string; min: number; max: number; step: number; defaultVal: number; unit: string }
  | { kind: 'slider-freq'; name: string; label: string; min: number; max: number; step: number; defaultVal: number; unit: string }

interface ToolState {
  enabled: boolean
  values: Record<string, number>
}

interface RepairIssue {
  severity: 'error' | 'warn' | 'info'
  message: string
  detail: string
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const REPAIR_TOOLS: RepairTool[] = [
  {
    id: 'de-clip',
    label: 'DE-CLIP',
    description: 'Reconstruct inter-sample peaks',
    icon: <Scissors size={14} />,
    accentColor: '#FF4444',
    controls: [
      { kind: 'slider', name: 'strength', label: 'STRENGTH', min: 0, max: 100, step: 1, defaultVal: 60, unit: '%' },
    ],
  },
  {
    id: 'de-noise',
    label: 'DE-NOISE',
    description: 'Adaptive spectral subtraction',
    icon: <Wind size={14} />,
    accentColor: '#8B5CF6',
    controls: [
      { kind: 'slider', name: 'threshold', label: 'THRESHOLD', min: -60, max: -30, step: 1, defaultVal: -45, unit: ' dB' },
    ],
  },
  {
    id: 'de-click',
    label: 'DE-CLICK',
    description: 'Transient artifact removal',
    icon: <MousePointer2 size={14} />,
    accentColor: '#F97316',
    controls: [
      { kind: 'slider', name: 'sensitivity', label: 'SENSITIVITY', min: 0, max: 100, step: 1, defaultVal: 50, unit: '%' },
    ],
  },
  {
    id: 'de-ess',
    label: 'DE-ESS',
    description: 'Dynamic sibilance control',
    icon: <Mic2 size={14} />,
    accentColor: '#D946EF',
    controls: [
      { kind: 'slider-freq', name: 'frequency', label: 'FREQUENCY', min: 4000, max: 12000, step: 100, defaultVal: 7500, unit: ' Hz' },
      { kind: 'slider', name: 'depth', label: 'DEPTH', min: 0, max: 24, step: 0.5, defaultVal: 8, unit: ' dB' },
    ],
  },
  {
    id: 'de-reverb',
    label: 'DE-REVERB',
    description: 'Neural reverb reduction',
    icon: <Waves size={14} />,
    accentColor: '#00D4FF',
    requiresBadge: 'stems',
    controls: [
      { kind: 'slider', name: 'strength', label: 'STRENGTH', min: 0, max: 100, step: 1, defaultVal: 40, unit: '%' },
    ],
  },
  {
    id: 'hole-fill',
    label: 'HOLE-FILL',
    description: 'Harmonic interpolation',
    icon: <Layers size={14} />,
    accentColor: '#AAFF00',
    requiresBadge: 'studio-pro',
    controls: [
      { kind: 'slider', name: 'strength', label: 'STRENGTH', min: 0, max: 100, step: 1, defaultVal: 50, unit: '%' },
    ],
  },
]

// Mock repair report issues
const REPAIR_ISSUES: RepairIssue[] = [
  { severity: 'error', message: '3 clipping events detected',       detail: 'Peak reconstruction required at 0:14.2, 1:03.8, 2:47.1' },
  { severity: 'warn',  message: 'Moderate sibilance at 8.2 kHz',    detail: 'Avg excess: +4.3 dB over 860 ms · 12 occurrences' },
  { severity: 'warn',  message: 'Broadband noise floor: −52 dB',    detail: 'Profile detected: room hiss + 60 Hz hum harmonic series' },
  { severity: 'info',  message: 'No click artifacts found',         detail: 'Transient scan passed — 0 anomalies' },
  { severity: 'info',  message: 'Reverb tail: est. 1.8 s RT60',     detail: 'Recommend De-Reverb strength 35–50 % for transparency' },
]

// ---------------------------------------------------------------------------
// Default state factory
// ---------------------------------------------------------------------------

function makeDefaultStates(): Record<string, ToolState> {
  return Object.fromEntries(
    REPAIR_TOOLS.map((t) => [
      t.id,
      {
        enabled: false,
        values: Object.fromEntries(t.controls.map((c) => [c.name, c.defaultVal])),
      },
    ]),
  )
}

// ---------------------------------------------------------------------------
// Badge component
// ---------------------------------------------------------------------------

function Badge({ kind }: { kind: 'stems' | 'studio-pro' }) {
  if (kind === 'stems') {
    return (
      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[7px] font-mono font-bold tracking-wider bg-[#00D4FF]/10 border border-[#00D4FF]/30 text-[#00D4FF]">
        <span>STEMS ≥ 0.60</span>
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[7px] font-mono font-bold tracking-wider bg-[#AAFF00]/10 border border-[#AAFF00]/30 text-[#AAFF00]">
      <Lock size={8} />
      STUDIO PRO
    </span>
  )
}

// ---------------------------------------------------------------------------
// Issue row
// ---------------------------------------------------------------------------

function IssueRow({ issue }: { issue: RepairIssue }) {
  const icons: Record<RepairIssue['severity'], React.ReactNode> = {
    error: <AlertTriangle size={12} className="text-[#FF4444] shrink-0 mt-px" />,
    warn:  <AlertTriangle size={12} className="text-[#F97316] shrink-0 mt-px" />,
    info:  <Info          size={12} className="text-[#8B5CF6] shrink-0 mt-px" />,
  }
  const textColors: Record<RepairIssue['severity'], string> = {
    error: 'text-[#FF4444]',
    warn:  'text-[#F97316]',
    info:  'text-[#8B5CF6]',
  }
  const bgColors: Record<RepairIssue['severity'], string> = {
    error: 'bg-[#FF4444]/5 border-[#FF4444]/20',
    warn:  'bg-[#F97316]/5 border-[#F97316]/20',
    info:  'bg-[#8B5CF6]/5 border-[#8B5CF6]/20',
  }

  return (
    <div className={`flex gap-2.5 px-3 py-2.5 rounded border ${bgColors[issue.severity]}`}>
      {icons[issue.severity]}
      <div className="min-w-0">
        <p className={`text-[10px] font-mono font-bold ${textColors[issue.severity]}`}>
          {issue.message}
        </p>
        <p className="text-[9px] font-mono text-rain-dim mt-0.5">{issue.detail}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Repair tool card
// ---------------------------------------------------------------------------

function RepairToolCard({
  tool,
  state,
  onToggle,
  onValueChange,
}: {
  tool: RepairTool
  state: ToolState
  onToggle: () => void
  onValueChange: (name: string, val: number) => void
}) {
  const isLocked = tool.requiresBadge === 'studio-pro'

  return (
    <div
      className={[
        'panel-card transition-all duration-200',
        state.enabled && !isLocked
          ? 'shadow-[0_0_14px_rgba(139,92,246,0.12)]'
          : '',
        isLocked ? 'opacity-60' : '',
      ].join(' ')}
    >
      {/* Card header */}
      <div className="panel-card-header justify-between">
        <div className="flex items-center gap-2">
          <span style={{ color: tool.accentColor }}>{tool.icon}</span>
          <span className="text-[10px] font-mono font-bold tracking-widest text-rain-text">
            {tool.label}
          </span>
          {tool.requiresBadge && <Badge kind={tool.requiresBadge} />}
        </div>

        {/* Toggle */}
        <button
          onClick={isLocked ? undefined : onToggle}
          disabled={isLocked}
          className={[
            'relative w-9 h-5 rounded-full border transition-all duration-200 shrink-0',
            isLocked
              ? 'cursor-not-allowed border-[#2A2545] bg-[#1C1835]'
              : state.enabled
                ? 'border-transparent cursor-pointer'
                : 'border-[#2A2545] bg-[#1C1835] cursor-pointer hover:border-[#4A4565]',
          ].join(' ')}
          style={
            state.enabled && !isLocked
              ? { background: `linear-gradient(135deg, ${tool.accentColor}99, ${tool.accentColor})`, borderColor: `${tool.accentColor}66` }
              : {}
          }
          aria-label={state.enabled ? 'Disable' : 'Enable'}
        >
          <span
            className={[
              'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-200',
              state.enabled && !isLocked ? 'left-[18px]' : 'left-0.5',
            ].join(' ')}
          />
        </button>
      </div>

      {/* Card body */}
      <div className="panel-card-body space-y-3">
        <p className="text-[9px] font-mono text-rain-dim tracking-wide">{tool.description}</p>

        {tool.controls.map((ctrl) => {
          const val = state.values[ctrl.name] ?? ctrl.defaultVal
          const pct = ((val - ctrl.min) / (ctrl.max - ctrl.min)) * 100

          const displayVal =
            ctrl.kind === 'slider-freq' && val >= 1000
              ? `${(val / 1000).toFixed(1)} kHz`
              : `${val}${ctrl.unit}`

          return (
            <div key={ctrl.name} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[8px] font-mono text-rain-dim tracking-wider">
                  {ctrl.label}
                </span>
                <span
                  className="text-[9px] font-mono tabular-nums"
                  style={{ color: state.enabled && !isLocked ? tool.accentColor : '#4A4565' }}
                >
                  {displayVal}
                </span>
              </div>
              <div className="relative h-1.5 rounded-full bg-[#2A2545]">
                <div
                  className="absolute left-0 top-0 h-full rounded-full transition-all"
                  style={{
                    width: `${pct}%`,
                    background: state.enabled && !isLocked
                      ? `linear-gradient(90deg, ${tool.accentColor}88, ${tool.accentColor})`
                      : '#2A2545',
                  }}
                />
              </div>
              <input
                type="range"
                min={ctrl.min}
                max={ctrl.max}
                step={ctrl.step}
                value={val}
                disabled={isLocked || !state.enabled}
                onChange={(e) => onValueChange(ctrl.name, Number(e.target.value))}
                className="rain-slider w-full opacity-0 absolute"
                style={{ marginTop: '-10px', cursor: isLocked ? 'not-allowed' : 'pointer' }}
              />
              {/* Accessible range (overlaid) */}
              <input
                type="range"
                min={ctrl.min}
                max={ctrl.max}
                step={ctrl.step}
                value={val}
                disabled={isLocked || !state.enabled}
                onChange={(e) => onValueChange(ctrl.name, Number(e.target.value))}
                className="rain-slider w-full"
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type AnalysisState = 'idle' | 'running' | 'done'

export default function RepairTab() {
  const [toolStates, setToolStates]       = useState<Record<string, ToolState>>(makeDefaultStates)
  const [analysisState, setAnalysisState] = useState<AnalysisState>('idle')
  const [progress, setProgress]           = useState(0)

  const toggleTool = useCallback((id: string) => {
    setToolStates((prev) => ({
      ...prev,
      [id]: { ...prev[id]!, enabled: !prev[id]!.enabled },
    }))
  }, [])

  const setToolValue = useCallback((id: string, name: string, val: number) => {
    setToolStates((prev) => ({
      ...prev,
      [id]: {
        ...prev[id]!,
        values: { ...prev[id]!.values, [name]: val },
      },
    }))
  }, [])

  const handleRunAnalysis = useCallback(() => {
    if (analysisState !== 'idle') return
    setAnalysisState('running')
    setProgress(0)

    const startTime = performance.now()
    const duration  = 2200

    const tick = () => {
      const elapsed = performance.now() - startTime
      const pct     = Math.min(100, Math.round((elapsed / duration) * 100))
      setProgress(pct)
      if (pct < 100) {
        requestAnimationFrame(tick)
      } else {
        setAnalysisState('done')
      }
    }
    requestAnimationFrame(tick)
  }, [analysisState])

  const handleReset = useCallback(() => {
    setToolStates(makeDefaultStates())
    setAnalysisState('idle')
    setProgress(0)
  }, [])

  const enabledCount = Object.values(toolStates).filter((s) => s.enabled).length

  // Progress bar stage labels
  const stageLabel =
    progress < 20 ? 'INITIALIZING…'  :
    progress < 45 ? 'SCANNING ARTIFACTS…' :
    progress < 70 ? 'SPECTRAL ANALYSIS…'  :
    progress < 90 ? 'BUILDING REPORT…'    :
    'FINALIZING…'

  return (
    <div className="p-4 space-y-3 max-w-[1100px] mx-auto">

      {/* ── Header ───────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Scissors size={14} className="text-[#D946EF]" />
          <span className="text-[11px] font-mono font-bold tracking-widest text-rain-text uppercase">
            Spectral Repair
          </span>
          {enabledCount > 0 && (
            <span className="px-1.5 py-0.5 rounded text-[8px] font-mono font-bold bg-[#D946EF]/15 border border-[#D946EF]/30 text-[#D946EF]">
              {enabledCount} ACTIVE
            </span>
          )}
        </div>

        {analysisState === 'done' && (
          <button
            onClick={handleReset}
            className="px-2 py-1 rounded border border-[#2A2545] text-[9px] font-mono text-rain-dim hover:text-rain-text hover:border-[#4A4565] transition-colors"
          >
            RESET
          </button>
        )}
      </div>

      {/* ── 2×3 Tool Grid ────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3">
        {REPAIR_TOOLS.map((tool) => (
          <RepairToolCard
            key={tool.id}
            tool={tool}
            state={toolStates[tool.id]!}
            onToggle={() => toggleTool(tool.id)}
            onValueChange={(name, val) => setToolValue(tool.id, name, val)}
          />
        ))}
      </div>

      {/* ── Run Analysis button ───────────────────────────────────── */}
      {analysisState !== 'done' && (
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleRunAnalysis}
            disabled={analysisState === 'running'}
            className={[
              'w-full max-w-sm py-3 rounded text-[11px] font-mono font-bold tracking-widest transition-all',
              analysisState === 'running'
                ? 'bg-[#D946EF]/10 border border-[#D946EF]/20 text-[#D946EF] cursor-wait'
                : [
                    'bg-gradient-to-r from-[#8B5CF6] to-[#D946EF]',
                    'text-white border border-[#D946EF]/30',
                    'hover:shadow-[0_0_24px_rgba(217,70,239,0.35)]',
                    'active:scale-[0.99]',
                  ].join(' '),
            ].join(' ')}
          >
            {analysisState === 'running' ? (
              <span className="flex items-center justify-center gap-2">
                <span
                  className="inline-block w-3.5 h-3.5 border-2 border-[#D946EF] border-t-transparent rounded-full"
                  style={{ animation: 'spin 0.8s linear infinite' }}
                />
                {stageLabel}
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <Play size={12} />
                RUN REPAIR ANALYSIS
              </span>
            )}
          </button>

          {/* Progress bar */}
          {analysisState === 'running' && (
            <div className="w-full max-w-sm space-y-1">
              <div className="h-1.5 rounded-full bg-[#1C1835] overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-100"
                  style={{
                    width: `${progress}%`,
                    background: 'linear-gradient(90deg, #8B5CF6, #D946EF)',
                    boxShadow: '0 0 8px rgba(217,70,239,0.5)',
                  }}
                />
              </div>
              <div className="flex justify-between">
                <span className="text-[8px] font-mono text-rain-dim">{stageLabel}</span>
                <span className="text-[8px] font-mono text-rain-dim tabular-nums">{progress}%</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Repair Report ─────────────────────────────────────────── */}
      {analysisState === 'done' && (
        <div className="panel-card">
          <div className="panel-card-header justify-between">
            <span className="text-[10px] font-mono tracking-widest text-rain-text">
              REPAIR REPORT
            </span>
            <div className="flex items-center gap-1.5 ml-auto">
              <CheckCircle size={12} className="text-[#AAFF00]" />
              <span className="text-[9px] font-mono text-[#AAFF00]">ANALYSIS COMPLETE</span>
            </div>
          </div>
          <div className="panel-card-body space-y-2">
            {REPAIR_ISSUES.map((issue, i) => (
              <IssueRow key={i} issue={issue} />
            ))}

            {/* Summary line */}
            <div className="pt-2 border-t border-[#2A2545] flex items-center justify-between">
              <span className="text-[9px] font-mono text-rain-dim">
                {REPAIR_ISSUES.filter((i) => i.severity === 'error').length} critical&nbsp;·&nbsp;
                {REPAIR_ISSUES.filter((i) => i.severity === 'warn').length} warnings&nbsp;·&nbsp;
                {REPAIR_ISSUES.filter((i) => i.severity === 'info').length} informational
              </span>
              <button
                onClick={() => {
                  setAnalysisState('idle')
                  setProgress(0)
                  alert('Repairs applied to preview path. Re-master to apply to render output.')
                }}
                className="px-4 py-2 rounded text-[10px] font-mono font-bold tracking-widest bg-gradient-to-r from-[#8B5CF6] to-[#D946EF] text-white border border-[#D946EF]/30 hover:shadow-[0_0_20px_rgba(217,70,239,0.35)] transition-all active:scale-[0.98]"
              >
                APPLY REPAIRS
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Spin keyframe */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
