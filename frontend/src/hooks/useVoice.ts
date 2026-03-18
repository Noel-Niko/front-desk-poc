import { useState, useRef, useCallback } from 'react'
import type { Citation, ServerEvent } from '@/types/api'
import { useAudio } from '@/hooks/useAudio'

export type VoiceState = 'idle' | 'connecting' | 'listening' | 'processing'
export type TTSState = 'idle' | 'playing'

interface UseVoiceProps {
  sessionId: string | null
  ttsEnabled: boolean
  ttsSpeed: number
  onTranscript: (text: string, isFinal: boolean) => void
  onResponse: (text: string, citations: Citation[]) => void
  onResponseDelta?: (text: string) => void
}

interface UseVoiceReturn {
  state: VoiceState
  ttsState: TTSState
  interimText: string
  start: () => Promise<void>
  stop: () => void
}

export function useVoice({
  sessionId,
  ttsEnabled,
  ttsSpeed,
  onTranscript,
  onResponse,
  onResponseDelta,
}: UseVoiceProps): UseVoiceReturn {
  const [state, setState] = useState<VoiceState>('idle')
  const [ttsState, setTTSState] = useState<TTSState>('idle')
  const [interimText, setInterimText] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const audio = useAudio()

  const start = useCallback(async () => {
    if (!sessionId) return
    setState('connecting')

    try {
      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
        },
      })
      streamRef.current = stream

      // Ensure audio player is ready (requires user gesture)
      await audio.ensureResumed()

      // Connect WebSocket to voice endpoint
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${wsProtocol}//${window.location.host}/api/voice`)
      wsRef.current = ws
      ws.binaryType = 'arraybuffer'

      ws.onopen = () => {
        setState('listening')
        // Send config message with TTS settings
        ws.send(
          JSON.stringify({
            type: 'config',
            session_id: sessionId,
            tts_enabled: ttsEnabled,
            tts_speed: ttsSpeed,
          }),
        )

        // Set up audio processing for mic input
        const audioContext = new AudioContext({ sampleRate: 16000 })
        audioContextRef.current = audioContext
        const source = audioContext.createMediaStreamSource(stream)
        const processor = audioContext.createScriptProcessor(4096, 1, 1)

        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const pcmData = e.inputBuffer.getChannelData(0)
            // Convert float32 to int16
            const int16 = new Int16Array(pcmData.length)
            for (let i = 0; i < pcmData.length; i++) {
              int16[i] = Math.max(-32768, Math.min(32767, Math.round(pcmData[i] * 32767)))
            }
            ws.send(int16.buffer)
          }
        }

        source.connect(processor)
        processor.connect(audioContext.destination)
      }

      ws.onmessage = (event) => {
        // Binary frame = TTS audio chunk from Cartesia
        if (event.data instanceof ArrayBuffer) {
          audio.enqueueChunk(event.data)
          return
        }

        const data = JSON.parse(event.data) as ServerEvent
        if (data.type === 'transcript') {
          setInterimText(data.text)
          onTranscript(data.text, data.is_final)
          if (data.is_final) {
            setInterimText('')
            setState('processing')

            // Barge-in: if TTS is playing when user speaks, stop it
            if (audio.isPlaying()) {
              audio.flush()
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'tts_interrupt' }))
              }
              setTTSState('idle')
            }
          }
        } else if (data.type === 'response_delta') {
          onResponseDelta?.(data.text)
        } else if (data.type === 'tts_start') {
          setTTSState('playing')
        } else if (data.type === 'tts_end') {
          setTTSState('idle')
          setState('listening')
        } else if (data.type === 'response') {
          onResponse(data.text, data.citations)
          // If TTS is not active, transition back to listening
          if (ttsState === 'idle') {
            setState('listening')
          }
        } else if (data.type === 'error') {
          console.error('Voice error:', data.message)
          setState('idle')
        }
      }

      ws.onclose = () => {
        setState('idle')
        setTTSState('idle')
        cleanup()
      }

      ws.onerror = () => {
        setState('idle')
        setTTSState('idle')
        cleanup()
      }
    } catch {
      setState('idle')
    }
  }, [sessionId, ttsEnabled, ttsSpeed, onTranscript, onResponse, onResponseDelta, audio])

  const cleanup = useCallback(() => {
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    audio.flush()
  }, [audio])

  const stop = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    cleanup()
    setState('idle')
    setTTSState('idle')
    setInterimText('')
  }, [cleanup])

  return { state, ttsState, interimText, start, stop }
}
