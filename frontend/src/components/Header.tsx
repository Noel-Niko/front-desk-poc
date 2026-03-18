interface HeaderProps {
  voiceEnabled: boolean
  onToggleVoice: () => void
}

export function Header({ voiceEnabled, onToggleVoice }: HeaderProps) {
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
      <button
        onClick={onToggleVoice}
        aria-label={voiceEnabled ? 'Switch to text input' : 'Switch to voice input'}
        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
          voiceEnabled
            ? 'bg-blurple text-white'
            : 'bg-barnacle text-blueberry hover:bg-butterfly'
        }`}
      >
        {voiceEnabled ? '🎙️ Voice' : '⌨️ Text'}
      </button>
    </header>
  )
}
