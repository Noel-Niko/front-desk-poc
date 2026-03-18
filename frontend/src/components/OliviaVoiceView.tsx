/**
 * OliviaVoiceView — centered animated owl with state-driven effects.
 *
 * Replaces the chat messages area when TTS voice mode is active.
 * Shows Ms. Olivia (owl) with animation and glow color
 * driven by the current voice/TTS state.
 *
 * Uses CSS animations instead of Lottie for React 19 compatibility.
 *
 * State priority:
 *   1. ttsState === 'playing'  → Speaking (bounce animation, blurple glow)
 *   2. voiceState === 'listening'   → Listening (gentle pulse, soft red glow)
 *   3. voiceState === 'processing'  → Processing (slow pulse, orange glow)
 *   4. Otherwise                    → Idle (subtle breathing, no glow)
 */

import type { VoiceState, TTSState } from '@/hooks/useVoice'

interface OliviaVoiceViewProps {
  voiceState: VoiceState
  ttsState: TTSState
  interimText: string
}

function getDisplayState(
  voiceState: VoiceState,
  ttsState: TTSState,
): { label: string; animClass: string; glowClass: string } {
  if (ttsState === 'playing') {
    return {
      label: 'Speaking...',
      animClass: 'animate-bounce',
      glowClass: 'shadow-[0_0_40px_rgba(99,102,241,0.4)]',
    }
  }
  if (voiceState === 'listening') {
    return {
      label: 'Listening...',
      animClass: 'animate-pulse',
      glowClass: 'shadow-[0_0_30px_rgba(239,68,68,0.3)]',
    }
  }
  if (voiceState === 'processing') {
    return {
      label: 'Thinking...',
      animClass: 'animate-pulse [animation-duration:2s]',
      glowClass: 'shadow-[0_0_30px_rgba(249,115,22,0.3)]',
    }
  }
  return {
    label: 'Ready',
    animClass: 'animate-pulse [animation-duration:3s]',
    glowClass: '',
  }
}

export default function OliviaVoiceView({
  voiceState,
  ttsState,
  interimText,
}: OliviaVoiceViewProps) {
  const { label, animClass, glowClass } = getDisplayState(voiceState, ttsState)

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-4">
      {/* Owl icon with animation + optional glow */}
      <div
        className={`flex h-48 w-48 items-center justify-center rounded-full bg-gradient-to-br from-indigo-50 to-purple-50 transition-shadow duration-500 md:h-64 md:w-64 ${glowClass}`}
      >
        <span className={`text-8xl md:text-9xl ${animClass}`} role="img" aria-label="Ms. Olivia owl">
          🦉
        </span>
      </div>

      {/* State label */}
      <div className="mt-4 text-center">
        <p className="text-lg font-semibold text-gray-800">Ms. Olivia</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>

      {/* Interim transcript */}
      {interimText && (
        <p className="mt-3 max-w-md animate-pulse truncate text-center text-sm italic text-gray-400">
          &ldquo;{interimText}&rdquo;
        </p>
      )}
    </div>
  )
}
