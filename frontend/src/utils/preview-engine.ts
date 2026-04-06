export class PreviewEngine {
  private context: AudioContext | null = null
  private sourceNode: AudioBufferSourceNode | null = null
  private gainNode: GainNode | null = null
  private analyserNode: AnalyserNode | null = null
  private currentBuffer: AudioBuffer | null = null
  private playStartContextTime = 0
  private playStartOffset = 0
  private _isPlaying = false

  async init(): Promise<void> {
    this.context = new AudioContext({ sampleRate: 48000 })
    this.gainNode = this.context.createGain()
    this.analyserNode = this.context.createAnalyser()
    this.analyserNode.fftSize = 2048
    this.gainNode.connect(this.analyserNode)
    this.analyserNode.connect(this.context.destination)
  }

  async loadAudioFile(file: File | ArrayBuffer): Promise<{ duration: number; sampleRate: number }> {
    if (this.context === null) await this.init()
    const buffer = file instanceof File ? await file.arrayBuffer() : file
    this.currentBuffer = await this.context!.decodeAudioData(buffer.slice(0))
    return { duration: this.currentBuffer.duration, sampleRate: this.currentBuffer.sampleRate }
  }

  play(startTime = 0): void {
    if (this.context === null || this.currentBuffer === null) return
    if (this.context.state === 'suspended') void this.context.resume()
    this.stop()
    this.sourceNode = this.context.createBufferSource()
    this.sourceNode.buffer = this.currentBuffer
    this.sourceNode.connect(this.gainNode!)
    this.sourceNode.start(0, startTime)
    this.playStartContextTime = this.context.currentTime
    this.playStartOffset = startTime
    this._isPlaying = true
    this.sourceNode.onended = () => { this._isPlaying = false }
  }

  /** Pause playback and return the current position (seconds). */
  pause(): number {
    if (!this._isPlaying || this.context === null) return this.playStartOffset
    const elapsed = this.context.currentTime - this.playStartContextTime
    const pos = this.playStartOffset + elapsed
    this.stop()
    this.playStartOffset = pos
    return pos
  }

  /** Resume from where pause() left off. */
  resume(fromPosition?: number): void {
    this.play(fromPosition ?? this.playStartOffset)
  }

  stop(): void {
    try { this.sourceNode?.stop() } catch { /* already stopped */ }
    this.sourceNode?.disconnect()
    this.sourceNode = null
    this._isPlaying = false
  }

  get isPlaying(): boolean { return this._isPlaying }

  /** Current playback position in seconds. */
  get position(): number {
    if (!this._isPlaying || this.context === null) return this.playStartOffset
    return this.playStartOffset + (this.context.currentTime - this.playStartContextTime)
  }

  get duration(): number { return this.currentBuffer?.duration ?? 0 }

  setVolume(db: number): void {
    if (this.gainNode !== null) {
      this.gainNode.gain.value = Math.pow(10, db / 20)
    }
  }

  getFrequencyData(): Uint8Array {
    if (this.analyserNode === null) return new Uint8Array(0)
    const data = new Uint8Array(this.analyserNode.frequencyBinCount)
    this.analyserNode.getByteFrequencyData(data)
    return data
  }

  getWaveformData(): Uint8Array {
    if (this.analyserNode === null) return new Uint8Array(0)
    const data = new Uint8Array(this.analyserNode.frequencyBinCount)
    this.analyserNode.getByteTimeDomainData(data)
    return data
  }

  get currentTime(): number {
    return this.context?.currentTime ?? 0
  }

  destroy(): void {
    this.stop()
    void this.context?.close()
    this.context = null
  }
}

export const previewEngine = new PreviewEngine()
