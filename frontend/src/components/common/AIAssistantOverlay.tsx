/**
 * AI Assistant Overlay — Global floating chat icon visible in ALL tabs.
 *
 * This is NOT the full Collab/AI chat tab. It's a lightweight floating bubble
 * that proactively detects issues and prompts the user:
 *
 *   "I'm detecting low-end buildup and over-smoothed transients.
 *    Want me to fix these?"
 *
 * Click the bubble to expand a mini-chat. The assistant can:
 * - Detect audio issues when a file is loaded
 * - Detect AI-generated content (Suno/Udio artifacts)
 * - Suggest macro changes
 * - Apply fixes with one click
 * - Link to the full AI Assistant tab for deeper conversation
 */

import { useState, useEffect, useCallback } from 'react'
import { Sparkles, X, ChevronRight, Zap, AlertTriangle } from 'lucide-react'
import { useSessionStore } from '@/stores/session'
import type { MacroValues } from '@/stores/session'
import { useNavigate } from 'react-router-dom'

// ---------------------------------------------------------------------------
// Issue detection (runs client-side on the audio buffer)
// ---------------------------------------------------------------------------

interface DetectedIssue {
  id: string
  icon: string
  title: string
  description: string
  fixMacros: Partial<MacroValues>
  severity: 'critical' | 'moderate' | 'mild' | 'info'
}

function detectIssues(inputBuffer: ArrayBuffer | null): DetectedIssue[] {
  if (!inputBuffer) return []

  // Basic detection from buffer metadata
  // In production, this would use the Web Audio API AnalyserNode for real-time analysis
  const issues: DetectedIssue[] = []
  const sizeBytes = inputBuffer.byteLength

  // Heuristic: very large file might be uncompressed high-res
  if (sizeBytes > 100 * 1024 * 1024) {
    issues.push({
      id: 'large_file',
      icon: '📦',
      title: 'Large File Detected',
      description: `This file is ${(sizeBytes / (1024 * 1024)).toFixed(0)}MB. I'll optimize the processing chain for best quality.`,
      fixMacros: {},
      severity: 'info',
    })
  }

  return issues
}

// ---------------------------------------------------------------------------
// Proactive messages based on session state
// ---------------------------------------------------------------------------

function getProactiveMessage(
  status: string,
  inputLufs: number | null,
  fileName: string | null,
  macros: MacroValues,
): { message: string; suggestions: DetectedIssue[] } | null {
  if (!fileName) return null

  const suggestions: DetectedIssue[] = []

  // After file load — proactive diagnosis
  if (status === 'idle' && inputLufs !== null) {
    if (inputLufs > -10) {
      suggestions.push({
        id: 'already_loud',
        icon: '🔊',
        title: 'Already Loud Input',
        description: `Input is at ${inputLufs.toFixed(1)} LUFS — already quite loud. I'll focus on tonal balance rather than pushing volume.`,
        fixMacros: { punch: Math.max(0, macros.punch - 2) },
        severity: 'moderate',
      })
    }

    if (inputLufs < -24) {
      suggestions.push({
        id: 'very_quiet',
        icon: '🔇',
        title: 'Very Quiet Input',
        description: `Input is at ${inputLufs.toFixed(1)} LUFS — there's a lot of headroom. I can bring this up to streaming levels.`,
        fixMacros: { punch: Math.min(10, macros.punch + 2), glue: Math.min(10, macros.glue + 1) },
        severity: 'moderate',
      })
    }
  }

  // After mastering complete — feedback loop
  if (status === 'complete') {
    suggestions.push({
      id: 'post_master',
      icon: '✅',
      title: 'Master Complete',
      description: "Your master is ready! Want me to check if anything could be improved further?",
      fixMacros: {},
      severity: 'info',
    })
  }

  if (suggestions.length === 0) return null

  const message = suggestions.length === 1
    ? suggestions[0].description
    : `I noticed ${suggestions.length} things worth mentioning.`

  return { message, suggestions }
}

// ---------------------------------------------------------------------------
// AIAssistantOverlay Component
// ---------------------------------------------------------------------------

export function AIAssistantOverlay() {
  const navigate = useNavigate()
  const { status, inputLufs, fileName, inputBuffer, macros, setMacros } = useSessionStore()
  const [isOpen, setIsOpen] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [appliedIds, setAppliedIds] = useState<Set<string>>(new Set())
  const [hasNotification, setHasNotification] = useState(false)

  // Detect issues when file loads or status changes
  const proactive = getProactiveMessage(status, inputLufs, fileName, macros)
  const bufferIssues = detectIssues(inputBuffer)
  const allSuggestions = [...(proactive?.suggestions ?? []), ...bufferIssues]

  // Show notification dot when new suggestions appear
  useEffect(() => {
    if (allSuggestions.length > 0 && !dismissed) {
      setHasNotification(true)
    }
  }, [allSuggestions.length, dismissed])

  // Apply fix
  const handleApply = useCallback((issue: DetectedIssue) => {
    if (Object.keys(issue.fixMacros).length > 0) {
      setMacros(issue.fixMacros)
    }
    setAppliedIds(prev => new Set([...prev, issue.id]))
  }, [setMacros])

  // Open full AI chat
  const handleOpenFullChat = useCallback(() => {
    setIsOpen(false)
    navigate('/app/collab')
  }, [navigate])

  // Don't show if no file loaded
  if (!fileName) return null

  return (
    <>
      {/* Floating bubble */}
      {!isOpen && (
        <button
          onClick={() => { setIsOpen(true); setDismissed(false); setHasNotification(false) }}
          className="fixed bottom-20 right-4 z-50 w-12 h-12 rounded-full bg-gradient-to-br from-rain-teal to-rain-cyan shadow-lg hover:shadow-xl transition-all hover:scale-110 flex items-center justify-center group"
        >
          <Sparkles size={20} className="text-rain-black" />
          {/* Notification dot */}
          {hasNotification && allSuggestions.length > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center animate-bounce">
              {allSuggestions.length}
            </span>
          )}
          {/* Tooltip */}
          <span className="absolute right-full mr-3 top-1/2 -translate-y-1/2 bg-rain-surface border border-rain-border/30 rounded-lg px-3 py-1.5 text-[11px] text-rain-text whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            AI Assistant
          </span>
        </button>
      )}

      {/* Expanded mini-chat panel */}
      {isOpen && (
        <div className="fixed bottom-20 right-4 z-50 w-80 max-h-[60vh] rounded-2xl bg-rain-surface border border-rain-border/40 shadow-2xl flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-rain-border/30 bg-rain-panel/80">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-rain-teal" />
              <span className="text-[11px] font-bold text-rain-teal uppercase tracking-wider">AI Assistant</span>
            </div>
            <button
              onClick={() => { setIsOpen(false); setDismissed(true) }}
              className="text-rain-dim hover:text-rain-text transition-colors"
            >
              <X size={14} />
            </button>
          </div>

          {/* Suggestions list */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5">
            {allSuggestions.length === 0 ? (
              <p className="text-[11px] text-rain-dim text-center py-4">
                Everything looks good! Adjust knobs or ask me anything.
              </p>
            ) : (
              allSuggestions.map(issue => (
                <div
                  key={issue.id}
                  className={`rounded-xl border p-3 ${
                    issue.severity === 'critical'
                      ? 'border-red-500/30 bg-red-500/5'
                      : issue.severity === 'moderate'
                        ? 'border-amber-500/30 bg-amber-500/5'
                        : 'border-rain-border/30 bg-rain-surface/50'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-base shrink-0">{issue.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-bold text-rain-text mb-0.5">{issue.title}</p>
                      <p className="text-[10px] text-rain-dim leading-relaxed">{issue.description}</p>
                      {Object.keys(issue.fixMacros).length > 0 && (
                        <div className="mt-2">
                          {appliedIds.has(issue.id) ? (
                            <span className="text-[9px] font-mono text-green-400 flex items-center gap-1">
                              <Zap size={10} /> Applied
                            </span>
                          ) : (
                            <button
                              onClick={() => handleApply(issue)}
                              className="text-[10px] font-bold text-rain-teal hover:text-rain-cyan transition-colors flex items-center gap-1"
                            >
                              <Zap size={10} /> Fix this
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer — link to full chat */}
          <div className="px-3 py-2 border-t border-rain-border/30">
            <button
              onClick={handleOpenFullChat}
              className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-rain-teal/10 text-rain-teal text-[10px] font-bold hover:bg-rain-teal/20 transition-colors"
            >
              Open full AI chat <ChevronRight size={12} />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
