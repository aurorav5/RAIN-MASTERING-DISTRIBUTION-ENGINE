/* eslint-disable @typescript-eslint/no-explicit-any */
// Web Speech API type shims (not all browsers ship these)
declare global {
  interface Window {
    SpeechRecognition: any
    webkitSpeechRecognition: any
  }
}
type SpeechRecognition = any
type SpeechRecognitionEvent = any

/**
 * RAIN Voice Command System
 *
 * Browser-native voice recognition for hands-free mastering.
 * Uses Web Speech API (SpeechRecognition) — no external services.
 * Audio never leaves the device.
 *
 * Commands:
 *   "play" / "pause" / "stop"          → transport controls
 *   "master" / "master now"            → trigger mastering
 *   "brighten up" / "more punch"       → macro adjustments
 *   "set [macro] to [number]"          → precise macro control
 *   "go to mastering" / "go to stems"  → tab navigation
 *   "undo" / "reset"                   → state management
 *   "what's the LUFS"                  → readout queries
 */

import { useEffect, useRef, useCallback, useState } from 'react'

// Supported voice commands and their intents
type VoiceIntent =
  | { type: 'transport'; action: 'play' | 'pause' | 'stop' | 'rewind' | 'forward' }
  | { type: 'master'; action: 'start' | 'reset' }
  | { type: 'macro'; name: string; action: 'increase' | 'decrease' | 'set'; value?: number }
  | { type: 'navigate'; tab: string }
  | { type: 'query'; subject: string }
  | { type: 'unknown'; transcript: string }

interface UseVoiceCommandsOptions {
  /** Called when a command is recognized */
  onCommand: (intent: VoiceIntent) => void
  /** Called with real-time partial transcript */
  onTranscript?: (text: string, isFinal: boolean) => void
  /** Enable/disable listening */
  enabled?: boolean
  /** Language (default: en-US) */
  language?: string
  /** Continuous listening (default: true) */
  continuous?: boolean
}

interface VoiceCommandState {
  isListening: boolean
  isSupported: boolean
  lastTranscript: string
  error: string | null
}

// ─── Command Parser ────────────────────────────

const MACRO_NAMES = ['brighten', 'glue', 'width', 'punch', 'warmth', 'space', 'repair'] as const
const TAB_NAMES = ['mastering', 'stems', 'spatial', 'reference', 'repair', 'qc', 'identity', 'collab', 'export', 'distribute', 'settings'] as const

function parseCommand(transcript: string): VoiceIntent {
  const t = transcript.toLowerCase().trim()

  // Transport
  if (/^(play|resume|go)$/.test(t)) return { type: 'transport', action: 'play' }
  if (/^(pause|hold)$/.test(t)) return { type: 'transport', action: 'pause' }
  if (/^(stop|halt)$/.test(t)) return { type: 'transport', action: 'stop' }
  if (/^(rewind|back|skip back)/.test(t)) return { type: 'transport', action: 'rewind' }
  if (/^(forward|skip forward|skip ahead)/.test(t)) return { type: 'transport', action: 'forward' }

  // Master
  if (/^(master|master now|start master|run master)/.test(t)) return { type: 'master', action: 'start' }
  if (/^(reset|undo|clear)$/.test(t)) return { type: 'master', action: 'reset' }

  // Macro adjustments
  for (const macro of MACRO_NAMES) {
    // "set brighten to 7"
    const setMatch = t.match(new RegExp(`set\\s+${macro}\\s+(?:to\\s+)?(\\d+(?:\\.\\d+)?)`, 'i'))
    if (setMatch) {
      return { type: 'macro', name: macro, action: 'set', value: parseFloat(setMatch[1] ?? '5') }
    }

    // "more brighten" / "brighten up" / "increase brighten"
    if (t.match(new RegExp(`(more|increase|up|raise|boost)\\s+${macro}|${macro}\\s+(up|more|higher)`, 'i'))) {
      return { type: 'macro', name: macro, action: 'increase' }
    }

    // "less brighten" / "brighten down" / "decrease brighten"
    if (t.match(new RegExp(`(less|decrease|down|lower|reduce)\\s+${macro}|${macro}\\s+(down|less|lower)`, 'i'))) {
      return { type: 'macro', name: macro, action: 'decrease' }
    }
  }

  // Navigation
  for (const tab of TAB_NAMES) {
    if (t.match(new RegExp(`(go to|open|show|switch to)\\s+${tab}`, 'i'))) {
      return { type: 'navigate', tab }
    }
  }

  // Queries
  if (/what('s| is) the (lufs|loudness)/.test(t)) return { type: 'query', subject: 'lufs' }
  if (/what('s| is) the (peak|true peak)/.test(t)) return { type: 'query', subject: 'truepeak' }
  if (/what('s| is) the (score|rain score)/.test(t)) return { type: 'query', subject: 'score' }

  return { type: 'unknown', transcript: t }
}

// ─── Hook ──────────────────────────────────────

export function useVoiceCommands(options: UseVoiceCommandsOptions): VoiceCommandState {
  const { onCommand, onTranscript, enabled = false, language = 'en-US', continuous = true } = options
  const [state, setState] = useState<VoiceCommandState>({
    isListening: false,
    isSupported: false,
    lastTranscript: '',
    error: null,
  })

  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const onCommandRef = useRef(onCommand)
  const onTranscriptRef = useRef(onTranscript)
  onCommandRef.current = onCommand
  onTranscriptRef.current = onTranscript

  // Check browser support
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || (window as unknown as { webkitSpeechRecognition: typeof window.SpeechRecognition }).webkitSpeechRecognition
    setState(s => ({ ...s, isSupported: !!SpeechRecognition }))
  }, [])

  const startListening = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || (window as unknown as { webkitSpeechRecognition: typeof window.SpeechRecognition }).webkitSpeechRecognition
    if (!SpeechRecognition) return

    const recognition = new SpeechRecognition()
    recognition.continuous = continuous
    recognition.interimResults = true
    recognition.lang = language
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setState(s => ({ ...s, isListening: true, error: null }))
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const result = event.results[event.results.length - 1]
      const transcript = result[0].transcript

      if (result.isFinal) {
        const intent = parseCommand(transcript)
        onCommandRef.current(intent)
        setState(s => ({ ...s, lastTranscript: transcript }))
      }

      onTranscriptRef.current?.(transcript, result.isFinal)
    }

    recognition.onerror = (event: any) => {
      // "no-speech" and "aborted" are normal — don't treat as errors
      if (event.error === 'no-speech' || event.error === 'aborted') return
      setState(s => ({ ...s, error: event.error }))
    }

    recognition.onend = () => {
      setState(s => ({ ...s, isListening: false }))
      // Auto-restart if still enabled
      if (enabled) {
        try { recognition.start() } catch { /* already started */ }
      }
    }

    try {
      recognition.start()
      recognitionRef.current = recognition
    } catch {
      setState(s => ({ ...s, error: 'Failed to start recognition' }))
    }
  }, [continuous, language, enabled])

  useEffect(() => {
    if (enabled) {
      startListening()
    } else {
      recognitionRef.current?.stop()
      recognitionRef.current = null
    }

    return () => {
      recognitionRef.current?.stop()
      recognitionRef.current = null
    }
  }, [enabled, startListening])

  return state
}

// ─── Voice Indicator Component ──────────────────

export { parseCommand }
export type { VoiceIntent, VoiceCommandState }
