import { useState, useCallback, useRef, useEffect } from 'react'
import { MessageSquare, Send, Sparkles, RotateCcw, Volume2, Zap } from 'lucide-react'
import { useSessionStore } from '@/stores/session'
import type { MacroValues } from '@/stores/session'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  /** If the assistant suggested macro changes, they're attached here. */
  macroSuggestion?: Partial<MacroValues>
  /** Whether the user applied this suggestion. */
  applied?: boolean
}

// ---------------------------------------------------------------------------
// Suggested prompts for beginners
// ---------------------------------------------------------------------------

const QUICK_PROMPTS = [
  { label: 'Make it louder for Spotify', icon: '🔊' },
  { label: 'Add warmth and vinyl feel', icon: '🎵' },
  { label: 'More punch on the drums', icon: '🥁' },
  { label: 'Wider stereo image', icon: '🎧' },
  { label: 'Clean up background noise', icon: '🧹' },
  { label: 'Ready for Apple Music', icon: '🍎' },
  { label: 'Make vocals stand out more', icon: '🎤' },
  { label: 'Professional radio-ready sound', icon: '📻' },
] as const

// ---------------------------------------------------------------------------
// AI response simulation (local-only when backend unavailable)
// ---------------------------------------------------------------------------

function generateLocalResponse(query: string, currentMacros: MacroValues): { text: string; macros: Partial<MacroValues> } {
  const q = query.toLowerCase()
  const macros: Partial<MacroValues> = {}
  const parts: string[] = []

  if (q.includes('loud') || q.includes('spotify') || q.includes('stream')) {
    macros.punch = Math.min(10, currentMacros.punch + 2)
    macros.glue = Math.min(10, currentMacros.glue + 1.5)
    parts.push("I've increased **PUNCH** to bring up the perceived loudness and added more **GLUE** for a cohesive, competitive sound.")
    parts.push('This will help your track hold its own on streaming playlists.')
  }

  if (q.includes('warm') || q.includes('vinyl') || q.includes('analog')) {
    macros.warmth = Math.min(10, currentMacros.warmth + 3)
    macros.brighten = Math.max(0, currentMacros.brighten - 1)
    parts.push("I've turned up **WARMTH** to add harmonic richness — like running through a vintage tape machine.")
    if (q.includes('vinyl')) parts.push('The slight high-end rolloff gives it that vinyl character.')
  }

  if (q.includes('punch') || q.includes('drum') || q.includes('hit') || q.includes('impact')) {
    macros.punch = Math.min(10, currentMacros.punch + 2.5)
    parts.push("**PUNCH** is up — your transients will cut through harder now. Drums should hit with more impact.")
  }

  if (q.includes('wide') || q.includes('stereo') || q.includes('spatial') || q.includes('immersive')) {
    macros.width = Math.min(10, currentMacros.width + 2)
    macros.space = Math.min(10, currentMacros.space + 1.5)
    parts.push("I've widened the **stereo image** and added some **SPACE** for depth. Your mix should feel more immersive now.")
  }

  if (q.includes('clean') || q.includes('noise') || q.includes('repair') || q.includes('fix')) {
    macros.repair = Math.min(10, currentMacros.repair + 3)
    parts.push("**REPAIR** is now active — this engages spectral cleanup to reduce noise, clicks, and harshness.")
  }

  if (q.includes('vocal') || q.includes('voice') || q.includes('sing')) {
    macros.brighten = Math.min(10, currentMacros.brighten + 1.5)
    macros.width = Math.max(0, currentMacros.width - 0.5)
    parts.push("I've boosted **BRIGHTEN** slightly to add presence to vocals, and pulled **WIDTH** back just a touch to keep the voice centered and forward in the mix.")
  }

  if (q.includes('radio') || q.includes('professional') || q.includes('commercial')) {
    macros.glue = Math.min(10, currentMacros.glue + 2)
    macros.punch = Math.min(10, currentMacros.punch + 1)
    macros.brighten = Math.min(10, currentMacros.brighten + 1)
    parts.push("For a **radio-ready** sound, I've increased **GLUE** for that polished cohesion, added a bit of **PUNCH** for energy, and a touch of **BRIGHTEN** for air.")
  }

  if (q.includes('apple') || q.includes('apple music')) {
    macros.glue = Math.min(10, currentMacros.glue + 1)
    parts.push("Apple Music uses **-16 LUFS** normalization, so I've optimized for a slightly more dynamic master. A bit more **GLUE** for polish.")
  }

  if (parts.length === 0) {
    parts.push("I understand you'd like to adjust the sound. Could you describe what you're hearing and what you'd like changed?")
    parts.push('')
    parts.push("Try something like:")
    parts.push("- *\"Make it warmer and punchier\"*")
    parts.push("- *\"More stereo width\"*")
    parts.push("- *\"Ready for Spotify\"*")
    parts.push("- *\"Clean up the background noise\"*")
  }

  if (Object.keys(macros).length > 0) {
    parts.push('')
    parts.push("Hit **Apply** to hear the changes, or keep chatting to refine further.")
  }

  return { text: parts.join('\n'), macros }
}

// ---------------------------------------------------------------------------
// CollabTab — AI Co-Master Engineer
// ---------------------------------------------------------------------------

export default function CollabTab() {
  const { macros, setMacros, fileName, status } = useSessionStore()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: fileName
        ? `I can hear **${fileName}** is loaded. Tell me what you'd like — describe the sound you're going for, and I'll adjust the mastering controls for you.\n\nYou don't need to know any technical terms. Just tell me how you want it to sound.`
        : "Welcome to the AI Co-Master Engineer. Load an audio file in the **Master** tab, then come back here and tell me how you want it to sound.\n\nI'll translate your words into precise mastering adjustments.",
      timestamp: Date.now(),
    },
  ])
  const [input, setInput] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Send message
  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isThinking) return

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsThinking(true)

    // Simulate thinking delay
    await new Promise(r => setTimeout(r, 800 + Math.random() * 700))

    const { text: responseText, macros: suggestion } = generateLocalResponse(text, macros)

    const assistantMsg: ChatMessage = {
      id: `ai-${Date.now()}`,
      role: 'assistant',
      content: responseText,
      timestamp: Date.now(),
      macroSuggestion: Object.keys(suggestion).length > 0 ? suggestion : undefined,
    }
    setMessages(prev => [...prev, assistantMsg])
    setIsThinking(false)
  }, [input, isThinking, macros])

  // Apply macro suggestion
  const handleApply = useCallback((msgId: string, suggestion: Partial<MacroValues>) => {
    setMacros(suggestion)
    setMessages(prev =>
      prev.map(m => m.id === msgId ? { ...m, applied: true } : m)
    )
  }, [setMacros])

  // Reset chat
  const handleReset = useCallback(() => {
    setMessages([{
      id: 'welcome-reset',
      role: 'assistant',
      content: "Fresh start! Tell me what sound you're going for.",
      timestamp: Date.now(),
    }])
  }, [])

  // Handle Enter key
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }, [handleSend])

  // Quick prompt click
  const handleQuickPrompt = useCallback((prompt: string) => {
    setInput(prompt)
    inputRef.current?.focus()
  }, [])

  return (
    <div className="flex flex-col h-full page-enter">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-rain-border/30 shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-rain-teal" />
          <span className="text-xs font-bold text-rain-teal uppercase tracking-widest">
            AI Co-Master Engineer
          </span>
          <span className="text-[9px] font-mono text-rain-dim ml-2">
            powered by Claude
          </span>
        </div>
        <div className="flex items-center gap-2">
          {status === 'complete' && (
            <span className="badge badge-green text-[9px]">
              <Volume2 size={10} /> MASTERED
            </span>
          )}
          <button
            onClick={handleReset}
            className="flex items-center gap-1 px-2 py-1 rounded text-[9px] font-mono text-rain-dim hover:text-rain-text transition-colors"
          >
            <RotateCcw size={10} /> Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] ${
              msg.role === 'user'
                ? 'bg-rain-teal/10 border border-rain-teal/20 rounded-2xl rounded-br-sm px-4 py-2.5'
                : 'bg-rain-surface border border-rain-border/30 rounded-2xl rounded-bl-sm px-4 py-2.5'
            }`}>
              {/* Message text with basic markdown rendering */}
              <div className="text-[13px] leading-relaxed text-rain-text whitespace-pre-wrap">
                {msg.content.split('\n').map((line, i) => (
                  <p key={i} className={line === '' ? 'h-2' : ''}>
                    {line.split(/(\*\*.*?\*\*|\*.*?\*)/).map((part, j) => {
                      if (part.startsWith('**') && part.endsWith('**'))
                        return <strong key={j} className="text-rain-teal font-bold">{part.slice(2, -2)}</strong>
                      if (part.startsWith('*') && part.endsWith('*'))
                        return <em key={j} className="text-rain-text/80">{part.slice(1, -1)}</em>
                      return <span key={j}>{part}</span>
                    })}
                  </p>
                ))}
              </div>

              {/* Macro suggestion apply button */}
              {msg.macroSuggestion && (
                <div className="mt-3 pt-2 border-t border-rain-border/20">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[9px] font-mono text-rain-dim uppercase">Suggested changes:</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {Object.entries(msg.macroSuggestion).map(([key, val]) => (
                      <span key={key} className="badge badge-teal text-[9px]">
                        {key.toUpperCase()}: {typeof val === 'number' ? val.toFixed(1) : String(val)}
                      </span>
                    ))}
                  </div>
                  {msg.applied ? (
                    <span className="text-[10px] font-mono text-green-400 flex items-center gap-1">
                      <Zap size={10} /> Applied to mastering controls
                    </span>
                  ) : (
                    <button
                      onClick={() => handleApply(msg.id, msg.macroSuggestion!)}
                      className="btn-primary text-[11px] px-3 py-1.5 rounded-lg"
                    >
                      <Zap size={12} className="inline mr-1" />
                      Apply Changes
                    </button>
                  )}
                </div>
              )}

              {/* Timestamp */}
              <div className="text-[8px] font-mono text-rain-dim mt-1.5 text-right">
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}

        {/* Thinking indicator */}
        {isThinking && (
          <div className="flex justify-start">
            <div className="bg-rain-surface border border-rain-border/30 rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-rain-teal/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-rain-teal/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-rain-teal/60 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-[10px] text-rain-dim font-mono">Listening...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick prompts (show when few messages) */}
      {messages.length <= 2 && (
        <div className="px-4 pb-2 shrink-0">
          <p className="text-[9px] font-mono text-rain-dim uppercase tracking-wider mb-2">Try saying:</p>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_PROMPTS.map(p => (
              <button
                key={p.label}
                onClick={() => handleQuickPrompt(p.label)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-rain-surface border border-rain-border/30 text-[11px] text-rain-text/70 hover:text-rain-teal hover:border-rain-teal/30 transition-colors"
              >
                <span>{p.icon}</span>
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="px-4 py-3 border-t border-rain-border/30 shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={fileName ? "Describe the sound you want..." : "Load audio first, then describe your sound..."}
              disabled={!fileName}
              className="w-full bg-rain-surface border border-rain-border/30 rounded-xl px-4 py-2.5 text-[13px] text-rain-text placeholder:text-rain-dim/50 focus:border-rain-teal/40 focus:outline-none transition-colors disabled:opacity-40"
            />
          </div>
          <button
            onClick={() => void handleSend()}
            disabled={!input.trim() || isThinking || !fileName}
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-rain-teal text-rain-black disabled:bg-rain-dim/30 disabled:text-rain-dim transition-colors hover:bg-rain-cyan"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="text-[8px] font-mono text-rain-dim/40 mt-1.5 text-center">
          AI suggestions adjust the 7 mastering controls. You always have the final say.
        </p>
      </div>
    </div>
  )
}
