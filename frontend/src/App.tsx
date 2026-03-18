import { useCallback, useEffect, useRef, useState } from 'react'
import { Header } from '@/components/Header'
import { ChatMessage } from '@/components/ChatMessage'
import { ChatInput } from '@/components/ChatInput'
import { PinModal } from '@/components/PinModal'
import { RatingModal } from '@/components/RatingModal'
import { ReferencePanel } from '@/components/ReferencePanel'
import { useChat } from '@/hooks/useChat'
import { useVoice } from '@/hooks/useVoice'
import { rateSession } from '@/services/api'
import type { Citation, Message } from '@/types/api'

export default function App() {
  const { messages, citations, sessionId, childName, loading, error, send, submitCode, initSession, endSession, resetSession, addMessage, addCitations } =
    useChat()
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const [pinOpen, setPinOpen] = useState(false)
  const [pinError, setPinError] = useState<string | null>(null)
  const [pinLoading, setPinLoading] = useState(false)
  const [ratingOpen, setRatingOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  const handleTranscript = useCallback((text: string, isFinal: boolean) => {
    if (isFinal && text.trim()) {
      const userMsg: Message = {
        id: `voice-${Date.now()}`,
        role: 'user',
        content: text,
        citations: [],
        tool_used: null,
        transferred: false,
        transfer_reason: null,
        timestamp: new Date().toISOString(),
      }
      addMessage(userMsg)
    }
  }, [addMessage])

  const handleVoiceResponse = useCallback((text: string, voiceCitations: Citation[]) => {
    const assistantMsg: Message = {
      id: `voice-resp-${Date.now()}`,
      role: 'assistant',
      content: text,
      citations: voiceCitations,
      tool_used: null,
      transferred: false,
      transfer_reason: null,
      timestamp: new Date().toISOString(),
    }
    addMessage(assistantMsg)
    if (voiceCitations.length > 0) {
      addCitations(voiceCitations)
    }
  }, [addMessage, addCitations])

  const voice = useVoice({
    sessionId,
    onTranscript: handleTranscript,
    onResponse: handleVoiceResponse,
  })

  useEffect(() => {
    initSession()
  }, [initSession])

  useEffect(() => {
    if (!showScrollBtn) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading, showScrollBtn])

  // Detect manual scroll-up to show "scroll to bottom" button
  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return
    function handleScroll() {
      if (!container) return
      const { scrollTop, scrollHeight, clientHeight } = container
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100
      setShowScrollBtn(!isNearBottom)
    }
    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    setShowScrollBtn(false)
  }

  async function handleEndChat() {
    await endSession()
    setRatingOpen(true)
  }

  async function handleRatingSubmit(data: { rating: number; feedback: string }) {
    if (sessionId) {
      await rateSession(sessionId, data.rating, data.feedback || undefined)
    }
    setRatingOpen(false)
    if (voiceEnabled) {
      voice.stop()
      setVoiceEnabled(false)
    }
    await resetSession()
  }

  function handleToggleVoice() {
    if (voiceEnabled) {
      voice.stop()
      setVoiceEnabled(false)
    } else {
      voice.start()
      setVoiceEnabled(true)
    }
  }

  async function handleSend(text: string) {
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
        onToggleVoice={handleToggleVoice}
        onEndChat={handleEndChat}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Chat panel */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Messages area */}
          <div ref={messagesContainerRef} className="relative flex-1 overflow-y-auto p-4">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}

            {loading && (
              <div className="flex flex-col items-start mb-4">
                <span className="text-xs font-medium text-blurple mb-1">Ollie</span>
                <div className="bg-white border border-barnacle rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
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

            {/* Scroll to bottom button */}
            {showScrollBtn && (
              <button
                onClick={scrollToBottom}
                aria-label="Scroll to bottom"
                className="sticky bottom-2 left-1/2 -translate-x-1/2 z-10 rounded-full bg-blurple px-3 py-1.5 text-xs font-medium text-white shadow-md hover:bg-barney transition-colors"
              >
                ↓ New messages
              </button>
            )}
          </div>

          {/* Voice status */}
          {voiceEnabled && (
            <div className="px-4 pb-2">
              <div className="flex items-center gap-2 text-sm">
                <span className={`w-3 h-3 rounded-full ${
                  voice.state === 'listening' ? 'bg-bw-red animate-pulse' :
                  voice.state === 'processing' ? 'bg-bw-orange animate-pulse' :
                  voice.state === 'connecting' ? 'bg-bw-orange' :
                  'bg-gray-300'
                }`} />
                <span className="text-blueberry">
                  {voice.state === 'listening' && 'Listening...'}
                  {voice.state === 'processing' && 'Processing...'}
                  {voice.state === 'connecting' && 'Connecting...'}
                  {voice.state === 'idle' && 'Voice off'}
                </span>
                {voice.interimText && (
                  <span className="text-blueberry/60 italic truncate">
                    {voice.interimText}
                  </span>
                )}
              </div>
            </div>
          )}

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

          {/* Mobile reference panel trigger */}
          {(citations.length > 0 || childName) && (
            <div className="px-4 pb-2 md:hidden">
              <button
                onClick={() => setDrawerOpen(true)}
                className="text-xs text-blurple hover:text-barney underline"
              >
                View references ({citations.length})
              </button>
            </div>
          )}

          <ChatInput onSend={handleSend} disabled={loading || voice.state === 'processing'} />
        </main>

        {/* Reference panel (desktop) */}
        <div className="hidden md:block w-80">
          <ReferencePanel citations={citations} childName={childName} />
        </div>
      </div>

      {/* Mobile reference drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDrawerOpen(false)} />
          <div className="absolute right-0 top-0 bottom-0 w-80 bg-white shadow-xl overflow-y-auto animate-slide-in-right">
            <div className="flex items-center justify-between p-4 border-b border-barnacle">
              <span className="font-medium text-blackout">References</span>
              <button
                onClick={() => setDrawerOpen(false)}
                aria-label="Close references"
                className="text-blueberry hover:text-blackout"
              >
                ✕
              </button>
            </div>
            <ReferencePanel citations={citations} childName={childName} />
          </div>
        </div>
      )}

      <PinModal
        open={pinOpen}
        onSubmit={handlePinSubmit}
        onClose={() => setPinOpen(false)}
        error={pinError}
        loading={pinLoading}
      />

      <RatingModal
        open={ratingOpen}
        onSubmit={handleRatingSubmit}
        onClose={() => {
          setRatingOpen(false)
          resetSession()
        }}
      />
    </div>
  )
}
