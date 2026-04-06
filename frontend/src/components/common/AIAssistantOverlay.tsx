/**
 * AI Assistant Overlay — Passive detection with confidence-driven surfacing.
 *
 * THREE interaction levels based on confidence:
 *
 * 1. HIGH confidence (>0.8): Apply automatically with undo
 *    "Low-end buildup corrected" [Undo]
 *
 * 2. MEDIUM confidence (0.5-0.8): Subtle indicator, user confirms
 *    Small badge on the AI bubble → expand → "Fix?" button
 *
 * 3. LOW confidence (<0.5): Passive indicator only
 *    Dim dot on bubble → expand → "Possible issue — check?"
 *
 * The bubble is CALM. No popups, no chat spam, no interruption.
 * Attention is earned, not demanded.
 */

import { useState, useCallback, useEffect } from 'react'
import { Sparkles, X, ChevronRight, Zap, Undo2 } from 'lucide-react'
import { useSessionStore } from '@/stores/session'
import type { MacroValues } from '@/stores/session'
import { useNavigate } from 'react-router-dom'

// ---------------------------------------------------------------------------
// Issue type
// ---------------------------------------------------------------------------

interface DetectedIssue {
  id: string
  title: string
  description: string
  fixMacros: Partial<MacroValues>
  confidence: number    // 0-1
  category: 'frequency' | 'dynamics' | 'stereo' | 'ai_artifact' | 'loudness' | 'info'
}

// ---------------------------------------------------------------------------
// Confidence-driven UX decisions
// ---------------------------------------------------------------------------

type InteractionLevel = 'auto' | 'confirm' | 'passive'

function getInteractionLevel(confidence: number): InteractionLevel {
  if (confidence >= 0.8) return 'auto'
  if (confidence >= 0.5) return 'confirm'
  return 'passive'
}

// ---------------------------------------------------------------------------
// Passive detection (runs on session state changes)
// ---------------------------------------------------------------------------

function detectFromAnalysis(
  inputLufs: number | null,
  macros: MacroValues,
): DetectedIssue[] {
  if (inputLufs === null) return []
  const issues: DetectedIssue[] = []

  if (inputLufs > -8) {
    issues.push({
      id: 'hot_input',
      title: 'Very Loud Input',
      description: `Input at ${inputLufs.toFixed(1)} LUFS — already near clipping. Reducing punch to preserve headroom.`,
      fixMacros: { punch: Math.max(0, macros.punch - 2) },
      confidence: 0.85,
      category: 'loudness',
    })
  }

  if (inputLufs < -28) {
    issues.push({
      id: 'quiet_input',
      title: 'Quiet Input',
      description: `Input at ${inputLufs.toFixed(1)} LUFS — plenty of headroom available.`,
      fixMacros: { punch: Math.min(10, macros.punch + 1.5), glue: Math.min(10, macros.glue + 1) },
      confidence: 0.65,
      category: 'loudness',
    })
  }

  return issues
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AIAssistantOverlay() {
  const navigate = useNavigate()
  const { inputLufs, fileName, macros, setMacros } = useSessionStore()

  const [isOpen, setIsOpen] = useState(false)
  const [appliedIds, setAppliedIds] = useState<Set<string>>(new Set())
  const [undoStack, setUndoStack] = useState<{ id: string; prevMacros: Partial<MacroValues> }[]>([])
  const [autoAppliedIds, setAutoAppliedIds] = useState<Set<string>>(new Set())

  // Detect issues (passive, continuous)
  const issues = detectFromAnalysis(inputLufs, macros)
  const meaningful = issues.filter(i => i.confidence >= 0.5 || Object.keys(i.fixMacros).length > 0)

  // Auto-apply high-confidence fixes (once per issue, with undo)
  useEffect(() => {
    for (const issue of issues) {
      if (
        getInteractionLevel(issue.confidence) === 'auto' &&
        !autoAppliedIds.has(issue.id) &&
        Object.keys(issue.fixMacros).length > 0
      ) {
        // Save current state for undo
        const prevMacros: Partial<MacroValues> = {}
        for (const key of Object.keys(issue.fixMacros) as (keyof MacroValues)[]) {
          prevMacros[key] = macros[key]
        }
        setUndoStack(prev => [...prev, { id: issue.id, prevMacros }])
        setMacros(issue.fixMacros)
        setAutoAppliedIds(prev => new Set([...prev, issue.id]))
        setAppliedIds(prev => new Set([...prev, issue.id]))
      }
    }
  }, [issues, macros, setMacros, autoAppliedIds])

  // Manual apply
  const handleApply = useCallback((issue: DetectedIssue) => {
    const prevMacros: Partial<MacroValues> = {}
    for (const key of Object.keys(issue.fixMacros) as (keyof MacroValues)[]) {
      prevMacros[key] = macros[key]
    }
    setUndoStack(prev => [...prev, { id: issue.id, prevMacros }])
    setMacros(issue.fixMacros)
    setAppliedIds(prev => new Set([...prev, issue.id]))
  }, [macros, setMacros])

  // Undo
  const handleUndo = useCallback((issueId: string) => {
    const entry = undoStack.find(e => e.id === issueId)
    if (entry) {
      setMacros(entry.prevMacros)
      setAppliedIds(prev => { const n = new Set(prev); n.delete(issueId); return n })
      setUndoStack(prev => prev.filter(e => e.id !== issueId))
    }
  }, [undoStack, setMacros])

  // Don't render if no file loaded
  if (!fileName) return null

  // Determine bubble state
  const hasConfirmable = meaningful.some(i => getInteractionLevel(i.confidence) === 'confirm' && !appliedIds.has(i.id))
  const hasAutoApplied = undoStack.length > 0

  return (
    <>
      {/* Floating bubble — calm, not demanding */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-20 right-4 z-50 w-11 h-11 rounded-full bg-rain-surface border border-rain-border/40 shadow-lg hover:border-rain-teal/40 transition-all hover:scale-105 flex items-center justify-center group"
        >
          <Sparkles size={16} className="text-rain-dim group-hover:text-rain-teal transition-colors" />
          {/* Subtle notification — only for confirmable issues */}
          {hasConfirmable && (
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-rain-teal" />
          )}
          {/* Auto-applied indicator */}
          {hasAutoApplied && !hasConfirmable && (
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-green-500/60" />
          )}
        </button>
      )}

      {/* Expanded panel — clean, not noisy */}
      {isOpen && (
        <div className="fixed bottom-20 right-4 z-50 w-72 rounded-xl bg-rain-surface border border-rain-border/40 shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-rain-border/20">
            <span className="text-[10px] font-bold text-rain-dim uppercase tracking-wider">Analysis</span>
            <button onClick={() => setIsOpen(false)} className="text-rain-dim hover:text-rain-text">
              <X size={12} />
            </button>
          </div>

          {/* Issues */}
          <div className="max-h-64 overflow-y-auto px-3 py-2 space-y-2">
            {meaningful.length === 0 ? (
              <p className="text-[10px] text-rain-dim text-center py-3">
                No issues detected. Your track looks good.
              </p>
            ) : (
              meaningful.map(issue => {
                const level = getInteractionLevel(issue.confidence)
                const isApplied = appliedIds.has(issue.id)

                return (
                  <div key={issue.id} className="rounded-lg border border-rain-border/20 p-2.5 bg-rain-panel/30">
                    <p className="text-[10px] font-bold text-rain-text mb-1">{issue.title}</p>
                    <p className="text-[9px] text-rain-dim leading-relaxed mb-1.5">{issue.description}</p>

                    {Object.keys(issue.fixMacros).length > 0 && (
                      <div className="flex items-center gap-2">
                        {isApplied ? (
                          <>
                            <span className="text-[8px] font-mono text-green-400">
                              {level === 'auto' ? 'Auto-applied' : 'Applied'}
                            </span>
                            <button
                              onClick={() => handleUndo(issue.id)}
                              className="text-[8px] text-rain-dim hover:text-rain-text flex items-center gap-0.5"
                            >
                              <Undo2 size={8} /> Undo
                            </button>
                          </>
                        ) : level === 'confirm' ? (
                          <button
                            onClick={() => handleApply(issue)}
                            className="text-[9px] font-bold text-rain-teal hover:text-rain-cyan flex items-center gap-1"
                          >
                            <Zap size={9} /> Fix
                          </button>
                        ) : (
                          <span className="text-[8px] text-rain-dim italic">Low confidence — check manually</span>
                        )}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>

          {/* Footer */}
          <div className="px-3 py-1.5 border-t border-rain-border/20">
            <button
              onClick={() => { setIsOpen(false); navigate('/app/collab') }}
              className="w-full text-center text-[9px] text-rain-dim hover:text-rain-teal transition-colors flex items-center justify-center gap-1 py-1"
            >
              Open AI chat <ChevronRight size={10} />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
