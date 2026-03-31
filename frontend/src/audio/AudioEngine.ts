/**
 * AudioEngine — Web Audio API preview engine for RAIN.
 *
 * IMPORTANT: This is the PREVIEW path only (Web Audio API, 32-bit float,
 * non-deterministic, <50 ms latency). It is used for monitoring/auditioning.
 * The RENDER path (RainDSP WASM, 64-bit double, deterministic) is a completely
 * separate concern handled by useLocalRender / the backend render service.
 * These two paths must NEVER be confused.
 *
 * Preview measurements carry an inherent disclaimer:
 *   "Preview measurement -- final render may differ slightly."
 *   Expected divergence: up to +/-0.5 LU in integrated LUFS and +/-0.3 dB in true peak.
 */

import { useAudioStore, getAudioStoreState } from '../stores/audioStore';
import type { ProcessingParams } from '../types/dsp';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Macro-level preview parameters sent to the AudioWorklet. */
export interface PreviewMacros {
  /** Subset of ProcessingParams relevant for real-time preview approximation. */
  targetLufs: number;
  eqGains: readonly number[];
  stereoWidth: number;
  saturationDrive: number;
  saturationEnabled: boolean;
  volume: number;
}

export interface AudioFileInfo {
  duration: number;
  sampleRate: number;
  numberOfChannels: number;
}

/** Messages posted *to* the preview AudioWorklet processor. */
interface WorkletParamMessage {
  type: 'update-params';
  macros: PreviewMacros;
}

/** Messages received *from* the preview AudioWorklet processor. */
interface WorkletMeterMessage {
  type: 'meter';
  rmsLeft: number;
  rmsRight: number;
  peakLeft: number;
  peakRight: number;
  momentaryLufs: number;
  shortTermLufs: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SAMPLE_RATE = 48_000;
const FFT_SIZE = 4096;
const ANALYSER_SMOOTHING = 0.8;
const DEFAULT_WAVEFORM_POINTS = 2048;
const WORKLET_PROCESSOR_URL = '/audio/rain-preview-processor.js';

// ---------------------------------------------------------------------------
// AudioEngine
// ---------------------------------------------------------------------------

class AudioEngine {
  // -- Web Audio graph nodes --
  private context: AudioContext | null = null;
  private sourceNode: AudioBufferSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private analyserLeft: AnalyserNode | null = null;
  private analyserRight: AnalyserNode | null = null;
  private splitter: ChannelSplitterNode | null = null;
  private merger: ChannelMergerNode | null = null;
  private gainNode: GainNode | null = null;

  // -- State --
  private currentBuffer: AudioBuffer | null = null;
  private playbackStartContextTime = 0;
  private playbackStartOffset = 0;
  private meteringRafId: number | null = null;
  private isInitialized = false;
  private workletReady = false;

  // -- Analyser scratch buffers (allocated once, reused) --
  private frequencyDataLeft: Float32Array | null = null;
  private frequencyDataRight: Float32Array | null = null;
  private timeDomainDataLeft: Float32Array | null = null;
  private timeDomainDataRight: Float32Array | null = null;

  // --------------------------------------------------------------------------
  // Initialization
  // --------------------------------------------------------------------------

  /**
   * Create the AudioContext (48 kHz, interactive latency) and load the
   * AudioWorklet processor module. Safe to call multiple times -- subsequent
   * calls are no-ops.
   */
  async initialize(): Promise<void> {
    if (this.isInitialized && this.context !== null) {
      await this.ensureContextResumed();
      return;
    }

    this.context = new AudioContext({
      sampleRate: SAMPLE_RATE,
      latencyHint: 'interactive',
    });

    // Handle browser autoplay policy -- context may start suspended.
    await this.ensureContextResumed();

    // -- GainNode (master volume) --
    this.gainNode = this.context.createGain();
    this.gainNode.gain.value = 1.0;

    // -- Channel splitter / merger for per-channel analysis --
    this.splitter = this.context.createChannelSplitter(2);
    this.merger = this.context.createChannelMerger(2);

    // -- Analysers (one per channel) --
    this.analyserLeft = this.context.createAnalyser();
    this.analyserLeft.fftSize = FFT_SIZE;
    this.analyserLeft.smoothingTimeConstant = ANALYSER_SMOOTHING;

    this.analyserRight = this.context.createAnalyser();
    this.analyserRight.fftSize = FFT_SIZE;
    this.analyserRight.smoothingTimeConstant = ANALYSER_SMOOTHING;

    // Pre-allocate scratch buffers.
    const binCount = this.analyserLeft.frequencyBinCount;
    this.frequencyDataLeft = new Float32Array(binCount);
    this.frequencyDataRight = new Float32Array(binCount);
    this.timeDomainDataLeft = new Float32Array(binCount);
    this.timeDomainDataRight = new Float32Array(binCount);

    // -- AudioWorklet --
    try {
      await this.context.audioWorklet.addModule(WORKLET_PROCESSOR_URL);
      this.workletNode = new AudioWorkletNode(this.context, 'rain-preview-processor', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [2],
      });

      // Listen for meter messages from the worklet.
      this.workletNode.port.onmessage = this.handleWorkletMessage;
      this.workletReady = true;
    } catch (err: unknown) {
      // AudioWorklet loading can fail in some environments (e.g. file:// protocol,
      // certain test runners). Fall back to direct connection without worklet processing.
      console.warn(
        '[AudioEngine] AudioWorklet failed to load -- preview processing disabled. ' +
          'Metering will use AnalyserNode only.',
        err,
      );
      this.workletNode = null;
      this.workletReady = false;
    }

    // -- Wire the graph --
    // source -> [worklet] -> gain -> splitter -> analysers -> merger -> destination
    this.connectGraph();

    this.isInitialized = true;
  }

  // --------------------------------------------------------------------------
  // Audio file loading
  // --------------------------------------------------------------------------

  /**
   * Decode an audio file and generate waveform peaks for the UI.
   * Returns metadata about the decoded audio.
   */
  async loadAudioFile(file: File): Promise<AudioFileInfo> {
    if (this.context === null) {
      await this.initialize();
    }
    // Non-null assertion safe: initialize() guarantees context is set.
    const ctx = this.context!;

    await this.ensureContextResumed();

    // Stop any current playback before loading a new file.
    this.stopInternal();

    const arrayBuffer = await file.arrayBuffer();
    // decodeAudioData consumes the buffer, so pass a copy.
    this.currentBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));

    // Generate waveform peaks and push to store.
    const peaks = this.generateWaveformPeaks(this.currentBuffer, DEFAULT_WAVEFORM_POINTS);
    getAudioStoreState().setWaveformPeaks(peaks);

    return {
      duration: this.currentBuffer.duration,
      sampleRate: this.currentBuffer.sampleRate,
      numberOfChannels: this.currentBuffer.numberOfChannels,
    };
  }

  // --------------------------------------------------------------------------
  // Transport controls
  // --------------------------------------------------------------------------

  /**
   * Start playback from the given offset (seconds). If already playing,
   * restarts from the new offset.
   */
  play(offset = 0): void {
    if (this.context === null || this.currentBuffer === null) return;

    // Tear down any existing source before creating a new one.
    this.destroySourceNode();

    void this.ensureContextResumed();

    const source = this.context.createBufferSource();
    source.buffer = this.currentBuffer;
    this.sourceNode = source;

    // Connect source into the graph head.
    if (this.workletReady && this.workletNode !== null) {
      source.connect(this.workletNode);
    } else if (this.gainNode !== null) {
      source.connect(this.gainNode);
    }

    // Track timing for position calculation.
    const clampedOffset = Math.max(0, Math.min(offset, this.currentBuffer.duration));
    this.playbackStartOffset = clampedOffset;
    this.playbackStartContextTime = this.context.currentTime;

    source.start(0, clampedOffset);
    source.onended = this.handleSourceEnded;

    getAudioStoreState().setIsPlaying(true);
    this.startMeteringLoop();
  }

  /** Pause playback, retaining the current position. */
  pause(): void {
    if (this.context === null || !getAudioStoreState().isPlaying) return;

    // Compute current position before stopping.
    const position = this.getCurrentPosition();
    this.destroySourceNode();

    getAudioStoreState().setIsPlaying(false);
    getAudioStoreState().setPlaybackPosition(position);
    this.stopMeteringLoop();
  }

  /** Stop playback and reset position to zero. */
  stop(): void {
    this.stopInternal();
  }

  /** Seek to the given position in seconds. If playing, restarts from there. */
  seekTo(positionSeconds: number): void {
    if (this.currentBuffer === null) return;

    const clamped = Math.max(0, Math.min(positionSeconds, this.currentBuffer.duration));
    getAudioStoreState().setPlaybackPosition(clamped);

    if (getAudioStoreState().isPlaying) {
      this.play(clamped);
    }
  }

  // --------------------------------------------------------------------------
  // Volume
  // --------------------------------------------------------------------------

  /**
   * Set the master volume (linear, 0.0 - 1.0). Values outside the range
   * are clamped.
   */
  setVolume(volume: number): void {
    if (this.gainNode === null) return;
    const clamped = Math.max(0, Math.min(volume, 1));
    this.gainNode.gain.setValueAtTime(clamped, this.context?.currentTime ?? 0);
  }

  // --------------------------------------------------------------------------
  // Preview parameter updates
  // --------------------------------------------------------------------------

  /**
   * Send macro-level processing parameters to the AudioWorklet for real-time
   * preview approximation. This is NOT the authoritative render -- it is a
   * low-latency monitoring approximation only.
   */
  updatePreviewParams(macros: PreviewMacros): void {
    if (!this.workletReady || this.workletNode === null) return;

    const message: WorkletParamMessage = {
      type: 'update-params',
      macros,
    };
    this.workletNode.port.postMessage(message);
  }

  // --------------------------------------------------------------------------
  // Getters
  // --------------------------------------------------------------------------

  /** Current playback position in seconds. */
  getCurrentPosition(): number {
    if (this.context === null || !getAudioStoreState().isPlaying) {
      return getAudioStoreState().playbackPosition;
    }
    const elapsed = this.context.currentTime - this.playbackStartContextTime;
    const position = this.playbackStartOffset + elapsed;
    const duration = this.currentBuffer?.duration ?? 0;
    return Math.min(position, duration);
  }

  /** Whether the engine has been initialized. */
  get initialized(): boolean {
    return this.isInitialized;
  }

  /** Whether the AudioWorklet processor is loaded and connected. */
  get hasWorklet(): boolean {
    return this.workletReady;
  }

  /** Duration of the currently loaded audio in seconds, or 0 if none. */
  get duration(): number {
    return this.currentBuffer?.duration ?? 0;
  }

  /**
   * Read current frequency data from the left-channel analyser.
   * Returns Float32Array in dB (getFloatFrequencyData).
   */
  getFrequencyData(): { left: Float32Array; right: Float32Array } {
    if (
      this.analyserLeft === null ||
      this.analyserRight === null ||
      this.frequencyDataLeft === null ||
      this.frequencyDataRight === null
    ) {
      return { left: new Float32Array(0), right: new Float32Array(0) };
    }
    this.analyserLeft.getFloatFrequencyData(this.frequencyDataLeft);
    this.analyserRight.getFloatFrequencyData(this.frequencyDataRight);
    return { left: this.frequencyDataLeft, right: this.frequencyDataRight };
  }

  // --------------------------------------------------------------------------
  // Cleanup
  // --------------------------------------------------------------------------

  /** Tear down the entire audio graph and release resources. */
  destroy(): void {
    this.stopInternal();
    this.stopMeteringLoop();

    this.workletNode?.disconnect();
    this.workletNode = null;
    this.workletReady = false;

    this.analyserLeft?.disconnect();
    this.analyserRight?.disconnect();
    this.splitter?.disconnect();
    this.merger?.disconnect();
    this.gainNode?.disconnect();

    this.analyserLeft = null;
    this.analyserRight = null;
    this.splitter = null;
    this.merger = null;
    this.gainNode = null;

    this.frequencyDataLeft = null;
    this.frequencyDataRight = null;
    this.timeDomainDataLeft = null;
    this.timeDomainDataRight = null;

    this.currentBuffer = null;

    if (this.context !== null) {
      void this.context.close();
      this.context = null;
    }
    this.isInitialized = false;

    getAudioStoreState().reset();
  }

  // --------------------------------------------------------------------------
  // Private: graph wiring
  // --------------------------------------------------------------------------

  private connectGraph(): void {
    const ctx = this.context;
    if (
      ctx === null ||
      this.gainNode === null ||
      this.splitter === null ||
      this.merger === null ||
      this.analyserLeft === null ||
      this.analyserRight === null
    ) {
      return;
    }

    // Worklet sits between source and gain (source connects at play time).
    if (this.workletReady && this.workletNode !== null) {
      this.workletNode.connect(this.gainNode);
    }
    // source (connected at play) -> [worklet] -> gain

    // gain -> splitter -> per-channel analysers -> merger -> destination
    this.gainNode.connect(this.splitter);

    this.splitter.connect(this.analyserLeft, 0);
    this.splitter.connect(this.analyserRight, 1);

    this.analyserLeft.connect(this.merger, 0, 0);
    this.analyserRight.connect(this.merger, 0, 1);

    this.merger.connect(ctx.destination);
  }

  // --------------------------------------------------------------------------
  // Private: metering loop (requestAnimationFrame @ ~60 fps)
  // --------------------------------------------------------------------------

  private startMeteringLoop(): void {
    if (this.meteringRafId !== null) return;
    this.meterTick();
  }

  private stopMeteringLoop(): void {
    if (this.meteringRafId !== null) {
      cancelAnimationFrame(this.meteringRafId);
      this.meteringRafId = null;
    }
  }

  private meterTick = (): void => {
    // Update playback position in the store.
    if (getAudioStoreState().isPlaying) {
      getAudioStoreState().setPlaybackPosition(this.getCurrentPosition());
    }

    // Compute RMS from time-domain data for each channel.
    if (
      this.analyserLeft !== null &&
      this.analyserRight !== null &&
      this.timeDomainDataLeft !== null &&
      this.timeDomainDataRight !== null
    ) {
      this.analyserLeft.getFloatTimeDomainData(this.timeDomainDataLeft);
      this.analyserRight.getFloatTimeDomainData(this.timeDomainDataRight);

      const rmsLeft = this.computeRms(this.timeDomainDataLeft);
      const rmsRight = this.computeRms(this.timeDomainDataRight);
      const peakLeft = this.computePeak(this.timeDomainDataLeft);
      const peakRight = this.computePeak(this.timeDomainDataRight);

      const rmsLeftDb = this.linearToDb(rmsLeft);
      const rmsRightDb = this.linearToDb(rmsRight);
      const peakLeftDb = this.linearToDb(peakLeft);
      const peakRightDb = this.linearToDb(peakRight);

      getAudioStoreState().setMeterLevels({
        left: rmsLeftDb,
        right: rmsRightDb,
        center: (rmsLeftDb + rmsRightDb) / 2,
        lfe: -Infinity,
        surrounds: [-Infinity, -Infinity],
      });

      // True peak approximation from AnalyserNode (NOT authoritative --
      // real true peak requires 4x oversampling per ITU-R BS.1770).
      const peakDb = Math.max(peakLeftDb, peakRightDb);
      getAudioStoreState().setTruePeak(peakDb);
    }

    this.meteringRafId = requestAnimationFrame(this.meterTick);
  };

  // --------------------------------------------------------------------------
  // Private: waveform peak generation
  // --------------------------------------------------------------------------

  /**
   * Down-sample the full audio buffer into a fixed number of peak values
   * suitable for waveform display. Uses min/max envelope per bucket and
   * returns the absolute peak per bucket.
   */
  private generateWaveformPeaks(buffer: AudioBuffer, numPoints: number): Float32Array {
    const channelCount = buffer.numberOfChannels;
    const length = buffer.length;
    const peaks = new Float32Array(numPoints);
    const samplesPerBucket = length / numPoints;

    // Mix down to mono for waveform display.
    const channels: Float32Array[] = [];
    for (let ch = 0; ch < channelCount; ch++) {
      channels.push(buffer.getChannelData(ch));
    }

    for (let i = 0; i < numPoints; i++) {
      const start = Math.floor(i * samplesPerBucket);
      const end = Math.min(Math.floor((i + 1) * samplesPerBucket), length);

      let maxAbs = 0;
      for (let s = start; s < end; s++) {
        let monoSample = 0;
        for (let ch = 0; ch < channelCount; ch++) {
          monoSample += channels[ch][s];
        }
        monoSample /= channelCount;
        const abs = Math.abs(monoSample);
        if (abs > maxAbs) {
          maxAbs = abs;
        }
      }
      peaks[i] = maxAbs;
    }

    return peaks;
  }

  // --------------------------------------------------------------------------
  // Private: transport helpers
  // --------------------------------------------------------------------------

  private stopInternal(): void {
    this.destroySourceNode();
    this.stopMeteringLoop();

    const store = getAudioStoreState();
    if (store.isPlaying) {
      store.setIsPlaying(false);
    }
    store.setPlaybackPosition(0);

    // Reset meters to silence.
    store.setMeterLevels({
      left: -Infinity,
      right: -Infinity,
      center: -Infinity,
      lfe: -Infinity,
      surrounds: [-Infinity, -Infinity],
    });
    store.setTruePeak(-Infinity);
  }

  private destroySourceNode(): void {
    if (this.sourceNode !== null) {
      try {
        this.sourceNode.stop();
      } catch {
        // Already stopped -- safe to ignore.
      }
      this.sourceNode.onended = null;
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
  }

  private handleSourceEnded = (): void => {
    // Natural end of playback (not a manual stop).
    this.destroySourceNode();
    this.stopMeteringLoop();

    const store = getAudioStoreState();
    store.setIsPlaying(false);
    store.setPlaybackPosition(this.currentBuffer?.duration ?? 0);
  };

  // --------------------------------------------------------------------------
  // Private: AudioWorklet messages
  // --------------------------------------------------------------------------

  private handleWorkletMessage = (event: MessageEvent<WorkletMeterMessage>): void => {
    const data = event.data;
    if (data.type === 'meter') {
      getAudioStoreState().setLUFS(data.momentaryLufs, data.shortTermLufs, -Infinity);
    }
  };

  // --------------------------------------------------------------------------
  // Private: browser autoplay policy
  // --------------------------------------------------------------------------

  /**
   * Resume a suspended AudioContext. Browsers suspend contexts created before
   * user interaction. We attempt resume eagerly and also wire up a one-shot
   * user gesture listener as a fallback.
   */
  private async ensureContextResumed(): Promise<void> {
    if (this.context === null) return;

    if (this.context.state === 'suspended') {
      try {
        await this.context.resume();
      } catch {
        // If resume fails (no user gesture yet), register a one-shot listener
        // on the document that will resume on the next interaction.
        const resumeOnGesture = (): void => {
          if (this.context !== null && this.context.state === 'suspended') {
            void this.context.resume();
          }
          document.removeEventListener('click', resumeOnGesture);
          document.removeEventListener('keydown', resumeOnGesture);
          document.removeEventListener('touchstart', resumeOnGesture);
        };
        document.addEventListener('click', resumeOnGesture, { once: true });
        document.addEventListener('keydown', resumeOnGesture, { once: true });
        document.addEventListener('touchstart', resumeOnGesture, { once: true });
      }
    }
  }

  // --------------------------------------------------------------------------
  // Private: math helpers
  // --------------------------------------------------------------------------

  private computeRms(data: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      sum += data[i] * data[i];
    }
    return Math.sqrt(sum / data.length);
  }

  private computePeak(data: Float32Array): number {
    let peak = 0;
    for (let i = 0; i < data.length; i++) {
      const abs = Math.abs(data[i]);
      if (abs > peak) peak = abs;
    }
    return peak;
  }

  private linearToDb(linear: number): number {
    if (linear <= 0) return -Infinity;
    return 20 * Math.log10(linear);
  }
}

// ---------------------------------------------------------------------------
// Singleton export
// ---------------------------------------------------------------------------

export const audioEngine = new AudioEngine();
