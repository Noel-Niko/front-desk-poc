import { useState, type KeyboardEvent } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled: boolean
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState('')

  function handleSend() {
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex items-center gap-2 p-4 bg-white border-t border-barnacle">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type a message..."
        disabled={disabled}
        className="flex-1 px-4 py-2 rounded-full border border-barnacle bg-bubble text-blackout text-sm placeholder:text-butterfly focus:outline-none focus:border-blurple focus:ring-2 focus:ring-blurple/20 disabled:opacity-50"
      />
      <button
        onClick={handleSend}
        disabled={disabled}
        aria-label="Send"
        className="px-4 py-2 bg-blurple text-white text-sm font-medium rounded-full hover:bg-barney transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Send
      </button>
    </div>
  )
}
