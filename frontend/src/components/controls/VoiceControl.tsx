/**
 * RAIN Voice Control — Mic button + live transcript overlay
 *
 * Sits in the transport bar. Click to toggle voice commands.
 * Shows a pulsing indicator when listening and a transcript toast
 * when a command is recognized.
 */

import { useState, useCallback, useEffect, type FC } from 'react'
import { Mic, MicOff } from 'lucide-react'
import { useVoiceCommands, type VoiceIntent } from '@/hooks/useVoiceCommands'
import { useNavigate } from 'react-router-dom'

interface VoiceControlProps {
  /** Callback for transport commands (play/pause/stop) */
  onTransport?: (action: 'play' | 'pause' | 'stop' | 'rewind' | 'forward') => void
  /** Callback for macro changes */
  onMacro?: (name: string, action: 'increase' | 'decrease' | 'set', value?: number) => void
  /** Callback for master trigger */
  onMaster?: (action: 'start' | 'reset') => void
  /** Callback for readout queries */
  onQuery?: (subject: string) => void
}

export const VoiceControl: FC<VoiceControlProps> = ({
  onTransport,
  onMacro,
  onMaster,
  onQuery,
}) => {
  const [enabled, setEnabled] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [showToast, setShowToast] = useState(false)
  const navigate = useNavigate()

  const handleCommand = useCallback(
    (intent: VoiceIntent) => {
      switch (intent.type) {
        case 'transport':
          onTransport?.(intent.action)
          break
        case 'macro':
          onMacro?.(intent.name, intent.action, intent.value)
          break
        case 'master':
          onMaster?.(intent.action)
          break
        case 'navigate':
          navigate(`/app/${intent.tab}`)
          break
        case 'query':
          onQuery?.(intent.subject)
          break
        case 'unknown':
          break
      }

      // Show toast for recognized commands
      if (intent.type !== 'unknown') {
        setShowToast(true)
        setTimeout(() => setShowToast(false), 2000)
      }
    },
    [onTransport, onMacro, onMaster, onQuery, navigate]
  )

  const handleTranscript = useCallback((text: string, isFinal: boolean) => {
    setTranscript(text)
    if (isFinal) {
      setTimeout(() => setTranscript(''), 2500)
    }
  }, [])

  const { isListening, isSupported } = useVoiceCommands({
    onCommand: handleCommand,
    onTranscript: handleTranscript,
    enabled,
  })

  // Keyboard shortcut: V to toggle voice
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'v' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
        setEnabled(prev => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  if (!isSupported) return null

  return (
    <div className="relative flex items-center gap-2">
      {/* Mic Button */}
      <button
        onClick={() => setEnabled(prev => !prev)}
        className={`transport-btn-3d ${isListening ? 'listening' : ''}`}
        title="Voice commands (V)"
        style={{ width: 36, height: 36 }}
      >
        {isListening ? (
          <Mic size={16} className="text-[var(--rain-accent)]" />
        ) : (
          <MicOff size={16} />
        )}
        {isListening && (
          <span
            className="absolute inset-0 rounded-full border-2 border-[var(--rain-accent)] animate-ping"
            style={{ animationDuration: '1.5s', opacity: 0.3 }}
          />
        )}
        <span className="shortcut-hint">V</span>
      </button>

      {/* Live Transcript */}
      {transcript && (
        <div
          className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-3 py-1.5 rounded-lg
                     bg-black/80 border border-[var(--rain-accent)]/20 backdrop-blur-sm
                     font-mono text-xs text-[var(--rain-accent)] whitespace-nowrap
                     animate-in fade-in slide-in-from-left-2 duration-200"
        >
          {transcript}
          {!showToast && (
            <span className="ml-1 inline-block w-1.5 h-3.5 bg-[var(--rain-accent)] animate-pulse" />
          )}
        </div>
      )}

      {/* Command Confirmation Toast */}
      {showToast && (
        <div
          className="absolute -top-10 left-1/2 -translate-x-1/2 px-3 py-1 rounded
                     bg-[var(--rain-accent)]/10 border border-[var(--rain-accent)]/20
                     text-[var(--rain-accent)] text-[10px] font-semibold uppercase tracking-wider
                     whitespace-nowrap"
        >
          Command received
        </div>
      )}
    </div>
  )
}
