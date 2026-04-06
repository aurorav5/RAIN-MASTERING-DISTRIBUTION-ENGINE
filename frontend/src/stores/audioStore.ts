import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

export interface MeterLevels {
  left: number;
  right: number;
  center: number;
  lfe: number;
  surrounds: number[];
}

export interface AudioStoreState {
  playbackPosition: number;
  isPlaying: boolean;
  meters: MeterLevels;
  momentaryLUFS: number;
  shortTermLUFS: number;
  integratedLUFS: number;
  truePeakDBTP: number;
  waveformPeaks: Float32Array | null;

  setPlaybackPosition: (pos: number) => void;
  setMeterLevels: (meters: MeterLevels) => void;
  setLUFS: (momentary: number, shortTerm: number, integrated: number) => void;
  setTruePeak: (tp: number) => void;
  setIsPlaying: (playing: boolean) => void;
  setWaveformPeaks: (peaks: Float32Array) => void;
  reset: () => void;
}

const DEFAULT_METERS: MeterLevels = {
  left: -Infinity,
  right: -Infinity,
  center: -Infinity,
  lfe: -Infinity,
  surrounds: [-Infinity, -Infinity],
};

const INITIAL_STATE = {
  playbackPosition: 0,
  isPlaying: false,
  meters: { ...DEFAULT_METERS, surrounds: [...DEFAULT_METERS.surrounds] },
  momentaryLUFS: -Infinity,
  shortTermLUFS: -Infinity,
  integratedLUFS: -Infinity,
  truePeakDBTP: -Infinity,
  waveformPeaks: null,
} as const satisfies Omit<
  AudioStoreState,
  'setPlaybackPosition' | 'setMeterLevels' | 'setLUFS' | 'setTruePeak' | 'setIsPlaying' | 'setWaveformPeaks' | 'reset'
>;

export const useAudioStore = create<AudioStoreState>()(
  subscribeWithSelector((set) => ({
    ...INITIAL_STATE,
    meters: { ...DEFAULT_METERS, surrounds: [...DEFAULT_METERS.surrounds] },
    waveformPeaks: null as Float32Array | null,

    setPlaybackPosition: (pos: number) => set({ playbackPosition: pos }),

    setMeterLevels: (meters: MeterLevels) => set({ meters }),

    setLUFS: (momentary: number, shortTerm: number, integrated: number) =>
      set({ momentaryLUFS: momentary, shortTermLUFS: shortTerm, integratedLUFS: integrated }),

    setTruePeak: (tp: number) => set({ truePeakDBTP: tp }),

    setIsPlaying: (playing: boolean) => set({ isPlaying: playing }),

    setWaveformPeaks: (peaks: Float32Array) => set({ waveformPeaks: peaks }),

    reset: () =>
      set({
        playbackPosition: 0,
        isPlaying: false,
        meters: { ...DEFAULT_METERS, surrounds: [...DEFAULT_METERS.surrounds] },
        momentaryLUFS: -Infinity,
        shortTermLUFS: -Infinity,
        integratedLUFS: -Infinity,
        truePeakDBTP: -Infinity,
        waveformPeaks: null,
      }),
  }))
);

/**
 * Direct state access for non-React code (AudioWorklet callbacks, WebGL render loops).
 * Avoids React re-render overhead — read state imperatively.
 */
export const getAudioStoreState = useAudioStore.getState;

// ---------------------------------------------------------------------------
// Selector hooks — granular subscriptions to minimize React re-renders.
// Components using these only re-render when their specific slice changes.
// ---------------------------------------------------------------------------

export const usePlaybackPosition = (): number =>
  useAudioStore((s) => s.playbackPosition);

export const useIsPlaying = (): boolean =>
  useAudioStore((s) => s.isPlaying);

export const useMeterLevels = (): MeterLevels =>
  useAudioStore((s) => s.meters);

export const useLUFSMeters = (): {
  momentary: number;
  shortTerm: number;
  integrated: number;
  truePeak: number;
} =>
  useAudioStore((s) => ({
    momentary: s.momentaryLUFS,
    shortTerm: s.shortTermLUFS,
    integrated: s.integratedLUFS,
    truePeak: s.truePeakDBTP,
  }));
