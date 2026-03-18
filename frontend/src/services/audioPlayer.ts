/**
 * GaplessAudioPlayer — plays PCM16 audio chunks with zero-gap scheduling.
 *
 * Designed for streaming TTS: Cartesia sends raw PCM16 at 24kHz,
 * this player converts to Float32 and schedules via Web Audio API.
 *
 * Key design:
 *   - Sample-based integer timing (nextPlaySample) prevents float drift
 *   - GainNode for instant barge-in silencing (no pops)
 *   - AudioContext at 24kHz to match Cartesia output (no resampling)
 */

export class GaplessAudioPlayer {
  private audioContext: AudioContext
  private nextPlaySample: number = 0
  private startTimeSeconds: number = 0
  private isPlaying: boolean = false
  private activeSources: Set<AudioBufferSourceNode> = new Set()
  private sampleRate: number
  private gainNode: GainNode

  constructor(sampleRate: number = 24000) {
    this.sampleRate = sampleRate
    this.audioContext = new AudioContext({ sampleRate })
    this.gainNode = this.audioContext.createGain()
    this.gainNode.connect(this.audioContext.destination)
  }

  async ensureResumed(): Promise<void> {
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume()
    }
  }

  enqueueChunk(pcm16Chunk: ArrayBuffer): void {
    const float32 = this.pcm16ToFloat32(pcm16Chunk)
    const audioBuffer = this.audioContext.createBuffer(1, float32.length, this.sampleRate)
    audioBuffer.getChannelData(0).set(float32)

    const source = this.audioContext.createBufferSource()
    source.buffer = audioBuffer
    source.connect(this.gainNode)

    this.activeSources.add(source)
    source.onended = () => {
      source.disconnect()
      this.activeSources.delete(source)
    }

    const currentTime = this.audioContext.currentTime

    if (!this.isPlaying) {
      this.startTimeSeconds = currentTime + 0.01
      this.nextPlaySample = 0
      this.isPlaying = true
    }

    // Track time in samples (integer) to avoid float drift
    const scheduledTime = this.startTimeSeconds + this.nextPlaySample / this.sampleRate

    if (scheduledTime < currentTime) {
      // We've fallen behind — reset timing
      this.startTimeSeconds = currentTime + 0.005
      this.nextPlaySample = 0
    }

    const finalTime = this.startTimeSeconds + this.nextPlaySample / this.sampleRate
    source.start(finalTime)
    this.nextPlaySample += float32.length
  }

  flush(): void {
    // Instant silence via gain (no click/pop)
    this.gainNode.gain.setValueAtTime(0, this.audioContext.currentTime)
    for (const source of this.activeSources) {
      try {
        source.stop()
        source.disconnect()
      } catch {
        // Already stopped
      }
    }
    this.activeSources.clear()
    // Restore gain after cleanup
    this.gainNode.gain.setValueAtTime(1, this.audioContext.currentTime + 0.02)
    this.isPlaying = false
    this.nextPlaySample = 0
  }

  get playing(): boolean {
    return this.activeSources.size > 0
  }

  async destroy(): Promise<void> {
    this.flush()
    await this.audioContext.close()
  }

  private pcm16ToFloat32(pcm16: ArrayBuffer): Float32Array {
    const int16 = new Int16Array(pcm16)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768
    }
    return float32
  }
}
