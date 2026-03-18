/**
 * React hook wrapping GaplessAudioPlayer for TTS audio playback.
 *
 * Lazily creates the player on first use and provides
 * enqueue/flush/destroy callbacks for the voice pipeline.
 */

import { useRef, useCallback } from 'react'
import { GaplessAudioPlayer } from '@/services/audioPlayer'

export function useAudio(sampleRate: number = 24000) {
  const playerRef = useRef<GaplessAudioPlayer | null>(null)

  const getPlayer = useCallback(() => {
    if (!playerRef.current) {
      playerRef.current = new GaplessAudioPlayer(sampleRate)
    }
    return playerRef.current
  }, [sampleRate])

  const ensureResumed = useCallback(async () => {
    await getPlayer().ensureResumed()
  }, [getPlayer])

  const enqueueChunk = useCallback(
    (chunk: ArrayBuffer) => {
      getPlayer().enqueueChunk(chunk)
    },
    [getPlayer],
  )

  const flush = useCallback(() => {
    getPlayer().flush()
  }, [getPlayer])

  const isPlaying = useCallback(() => {
    return playerRef.current?.playing ?? false
  }, [])

  const destroy = useCallback(async () => {
    if (playerRef.current) {
      await playerRef.current.destroy()
      playerRef.current = null
    }
  }, [])

  return { ensureResumed, enqueueChunk, flush, isPlaying, destroy, getPlayer }
}
