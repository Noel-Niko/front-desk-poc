const SPEED_PRESETS = [0.8, 1.0, 1.25, 1.5]

interface HeaderProps {
  voiceEnabled: boolean
  onToggleVoice: () => void
  onEndChat?: () => void
  ttsEnabled?: boolean
  onToggleTTS?: () => void
  ttsSpeed?: number
  onCycleSpeed?: () => void
}

export function Header({
  voiceEnabled,
  onToggleVoice,
  onEndChat,
  ttsEnabled = false,
  onToggleTTS,
  ttsSpeed = 1.0,
  onCycleSpeed,
}: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-barnacle shadow-sm">
      <div className="flex items-center gap-3">
        <span className="text-2xl" role="img" aria-label="owl">
          🦉
        </span>
        <div>
          <h1 className="text-lg font-bold text-blackout leading-tight">
            Sunshine Learning Center
          </h1>
          <p className="text-sm text-blueberry">AI Front Desk</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleVoice}
          aria-label={voiceEnabled ? 'Switch to text input' : 'Switch to voice input'}
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            voiceEnabled
              ? 'bg-blurple text-white hover:bg-blurple/80'
              : 'bg-barnacle text-blueberry hover:bg-butterfly'
          }`}
        >
          {voiceEnabled ? '⌨️ Switch to Text' : '🎙️ Switch to Voice'}
        </button>

        {/* TTS toggle — only visible when voice is enabled */}
        {voiceEnabled && onToggleTTS && (
          <button
            onClick={onToggleTTS}
            aria-label={ttsEnabled ? 'Turn off speech' : 'Turn on speech'}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              ttsEnabled
                ? 'bg-blurple text-white hover:bg-blurple/80'
                : 'bg-barnacle text-blueberry hover:bg-butterfly'
            }`}
          >
            {ttsEnabled ? '🔊 Speech On' : '🔇 Speech Off'}
          </button>
        )}

        {/* Speed toggle — only visible when voice + TTS are enabled */}
        {voiceEnabled && ttsEnabled && onCycleSpeed && (
          <button
            onClick={onCycleSpeed}
            aria-label={`TTS speed ${ttsSpeed}x`}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              ttsSpeed !== 1.0
                ? 'bg-blurple text-white'
                : 'bg-barnacle text-blueberry hover:bg-butterfly'
            }`}
          >
            ⏩ {ttsSpeed}×
          </button>
        )}

        {onEndChat && (
          <button
            onClick={onEndChat}
            aria-label="End Chat"
            className="px-3 py-1.5 rounded-full text-sm font-medium bg-barnacle text-blueberry hover:bg-sangria/10 hover:text-sangria transition-colors"
          >
            End Chat
          </button>
        )}
      </div>
    </header>
  )
}

export { SPEED_PRESETS }
