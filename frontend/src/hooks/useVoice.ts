import { useState, useRef, useCallback } from 'react'
import type { Citation, ServerEvent } from '@/types/api'

type VoiceState = 'idle' | 'connecting' | 'listening' | 'processing'

interface UseVoiceProps {
  sessionId: string | null
  onTranscript: (text: string, isFinal: boolean) => void
  onResponse: (text: string, citations: Citation[]) => void
}

interface UseVoiceReturn {
  state: VoiceState
  interimText: string
  start: () => Promise<void>
  stop: () => void
}

export function useVoice({ sessionId, onTranscript, onResponse }: UseVoiceProps): UseVoiceReturn {
  const [state, setState] = useState<VoiceState>('idle')
  const [interimText, setInterimText] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)

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

      // Connect WebSocket to voice endpoint
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${wsProtocol}//${window.location.host}/api/voice`)
      wsRef.current = ws

      ws.onopen = () => {
        setState('listening')
        // Send config message
        ws.send(JSON.stringify({ type: 'config', session_id: sessionId }))

        // Set up audio processing
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
        const data = JSON.parse(event.data) as ServerEvent
        if (data.type === 'transcript') {
          setInterimText(data.text)
          onTranscript(data.text, data.is_final)
          if (data.is_final) {
            setInterimText('')
            setState('processing')
          }
        } else if (data.type === 'response') {
          onResponse(data.text, data.citations)
          setState('listening')
        } else if (data.type === 'error') {
          console.error('Voice error:', data.message)
          setState('idle')
        }
      }

      ws.onclose = () => {
        setState('idle')
        cleanup()
      }

      ws.onerror = () => {
        setState('idle')
        cleanup()
      }
    } catch {
      setState('idle')
    }
  }, [sessionId, onTranscript, onResponse])

  const cleanup = useCallback(() => {
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    cleanup()
    setState('idle')
    setInterimText('')
  }, [cleanup])

  return { state, interimText, start, stop }
}
