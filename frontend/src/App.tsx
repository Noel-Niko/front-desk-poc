import { useEffect, useRef, useState } from 'react'
import { Header } from '@/components/Header'
import { ChatMessage } from '@/components/ChatMessage'
import { ChatInput } from '@/components/ChatInput'
import { PinModal } from '@/components/PinModal'
import { ReferencePanel } from '@/components/ReferencePanel'
import { useChat } from '@/hooks/useChat'

export default function App() {
  const { messages, citations, childName, loading, error, send, submitCode, initSession } =
    useChat()
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const [pinOpen, setPinOpen] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)
  const [pinLoading, setPinLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    initSession()
  }, [initSession])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(text: string) {
    // Check if user is trying to enter a security code
    if (/^\d{4}$/.test(text.trim())) {
      handlePinSubmit(text.trim())
      return
    }
    await send(text)
  }

  async function handlePinSubmit(code: string) {
    setPinLoading(true)
    setPinError(null)
    const result = await submitCode(code)
    setPinLoading(false)
    if (result.verified) {
      setPinOpen(false)
      setPinError(null)
    } else {
      setPinError(result.error ?? 'Invalid code')
    }
  }

  return (
    <div className="h-screen flex flex-col">
      <Header
        voiceEnabled={voiceEnabled}
        onToggleVoice={() => setVoiceEnabled((v) => !v)}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Chat panel */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-4">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}

            {loading && (
              <div className="flex items-start mb-4">
                <span className="text-xs font-medium text-blurple mb-1">Ollie</span>
                <div className="bg-white border border-barnacle rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm ml-0 mt-1">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-blurple rounded-full animate-bounce" />
                    <span className="w-2 h-2 bg-blurple rounded-full animate-bounce [animation-delay:0.1s]" />
                    <span className="w-2 h-2 bg-blurple rounded-full animate-bounce [animation-delay:0.2s]" />
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="mx-4 mb-4 p-3 bg-sangria/10 border border-sangria/30 rounded-xl text-sm text-sangria">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Security code button */}
          {!childName && (
            <div className="px-4 pb-2">
              <button
                onClick={() => setPinOpen(true)}
                className="text-xs text-blurple hover:text-barney underline"
              >
                Have a security code? Enter it to access child info
              </button>
            </div>
          )}

          <ChatInput onSend={handleSend} disabled={loading} />
        </main>

        {/* Reference panel (hidden on small screens) */}
        <div className="hidden md:block w-80">
          <ReferencePanel citations={citations} childName={childName} />
        </div>
      </div>

      <PinModal
        open={pinOpen}
        onSubmit={handlePinSubmit}
        onClose={() => setPinOpen(false)}
        error={pinError}
        loading={pinLoading}
      />
    </div>
  )
}
