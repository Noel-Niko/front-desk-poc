import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useVoice } from '../useVoice'

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = []
  readyState = 1 // OPEN
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: ((e: unknown) => void) | null = null
  send = vi.fn()
  close = vi.fn()
  constructor() {
    MockWebSocket.instances.push(this)
  }
}

// Mock navigator.mediaDevices
const mockStream = {
  getTracks: () => [{ stop: vi.fn() }],
}

beforeEach(() => {
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
  vi.stubGlobal('navigator', {
    mediaDevices: {
      getUserMedia: vi.fn().mockResolvedValue(mockStream),
    },
  })
})

describe('useVoice', () => {
  it('starts in idle state', () => {
    const { result } = renderHook(() => useVoice({ sessionId: 'test-session', onTranscript: vi.fn(), onResponse: vi.fn() }))
    expect(result.current.state).toBe('idle')
  })

  it('has a start function', () => {
    const { result } = renderHook(() => useVoice({ sessionId: 'test-session', onTranscript: vi.fn(), onResponse: vi.fn() }))
    expect(typeof result.current.start).toBe('function')
  })

  it('has a stop function', () => {
    const { result } = renderHook(() => useVoice({ sessionId: 'test-session', onTranscript: vi.fn(), onResponse: vi.fn() }))
    expect(typeof result.current.stop).toBe('function')
  })

  it('exposes interim transcript text', () => {
    const { result } = renderHook(() => useVoice({ sessionId: 'test-session', onTranscript: vi.fn(), onResponse: vi.fn() }))
    expect(result.current.interimText).toBe('')
  })
})
