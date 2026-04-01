import { create } from 'zustand'

export type SessionStatus = 'idle' | 'uploading' | 'analyzing' | 'processing' | 'complete' | 'failed'

interface RainScore {
  overall: number
  spotify: number
  apple_music: number
  youtube: number
  tidal: number
  codec_penalty: Record<string, number>
}

export interface MacroValues {
  brighten: number
  glue: number
  width: number
  punch: number
  warmth: number
  space: number
  repair: number
}

interface SessionState {
  // Session identity
  sessionId: string | null
  status: SessionStatus
  progress: number

  // Audio buffers
  inputBuffer: ArrayBuffer | null
  outputBuffer: ArrayBuffer | null

  // File info (persists across tab switches)
  fileName: string | null
  fileDuration: number
  fileSampleRate: number
  fileBitDepth: number
  fileChannels: number

  // Analysis
  inputLufs: number | null
  inputTruePeak: number | null
  outputLufs: number | null
  outputTruePeak: number | null
  rainScore: RainScore | null
  rainCertId: string | null
  errorCode: string | null

  // Macro values (persist across tab switches)
  macros: MacroValues

  // Processing flag
  isProcessing: boolean

  // Actions
  setSession: (id: string) => void
  setStatus: (status: SessionStatus, progress?: number) => void
  setInputBuffer: (buf: ArrayBuffer) => void
  setOutputBuffer: (buf: ArrayBuffer) => void
  setFileInfo: (name: string, duration: number, sampleRate: number, bitDepth: number, channels: number) => void
  setAnalysis: (lufs: number, tp: number) => void
  setResult: (outputLufs: number, outputTp: number, score: RainScore, certId: string) => void
  setError: (code: string) => void
  setMacros: (macros: Partial<MacroValues>) => void
  setIsProcessing: (v: boolean) => void
  /** Reset processing state only — preserves loaded file, macros, and file info. */
  resetProcessing: () => void
  /** Full reset — clears everything including loaded audio. */
  reset: () => void
}

const DEFAULT_MACROS: MacroValues = {
  brighten: 5.0,
  glue: 6.0,
  width: 5.0,
  punch: 5.0,
  warmth: 2.5,
  space: 3.0,
  repair: 0.0,
}

export const useSessionStore = create<SessionState>()((set) => ({
  sessionId: null, status: 'idle', progress: 0,
  inputBuffer: null, outputBuffer: null,
  fileName: null, fileDuration: 0, fileSampleRate: 48000, fileBitDepth: 24, fileChannels: 2,
  inputLufs: null, inputTruePeak: null,
  outputLufs: null, outputTruePeak: null,
  rainScore: null, rainCertId: null, errorCode: null,
  macros: { ...DEFAULT_MACROS },
  isProcessing: false,
  setSession: (id) => set({ sessionId: id, status: 'uploading' }),
  setStatus: (status, progress = 0) => set({ status, progress }),
  setInputBuffer: (buf) => set({ inputBuffer: buf }),
  setOutputBuffer: (buf) => set({ outputBuffer: buf }),
  setFileInfo: (name, duration, sampleRate, bitDepth, channels) =>
    set({ fileName: name, fileDuration: duration, fileSampleRate: sampleRate, fileBitDepth: bitDepth, fileChannels: channels }),
  setAnalysis: (lufs, tp) => set({ inputLufs: lufs, inputTruePeak: tp }),
  setResult: (outputLufs, outputTp, score, certId) =>
    set({ outputLufs, outputTruePeak: outputTp, rainScore: score, rainCertId: certId, status: 'complete', isProcessing: false }),
  setError: (code) => set({ errorCode: code, status: 'failed', isProcessing: false }),
  setMacros: (partial) => set((s) => ({ macros: { ...s.macros, ...partial } })),
  setIsProcessing: (v) => set({ isProcessing: v }),
  resetProcessing: () => set({
    sessionId: null, status: 'idle', progress: 0,
    outputBuffer: null,
    outputLufs: null, outputTruePeak: null,
    rainScore: null, rainCertId: null, errorCode: null,
    isProcessing: false,
  }),
  reset: () => set({
    sessionId: null, status: 'idle', progress: 0,
    inputBuffer: null, outputBuffer: null,
    fileName: null, fileDuration: 0, fileSampleRate: 48000, fileBitDepth: 24, fileChannels: 2,
    inputLufs: null, inputTruePeak: null,
    outputLufs: null, outputTruePeak: null,
    rainScore: null, rainCertId: null, errorCode: null,
    macros: { ...DEFAULT_MACROS },
    isProcessing: false,
  }),
}))
