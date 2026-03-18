import { useState, useCallback } from 'react'
import type { Message, Citation } from '@/types/api'
import { createSession, sendMessage, verifyCode } from '@/services/api'

interface UseChatReturn {
  messages: Message[]
  citations: Citation[]
  sessionId: string | null
  childName: string | null
  loading: boolean
  error: string | null
  send: (text: string) => Promise<void>
  submitCode: (code: string) => Promise<{ verified: boolean; error: string | null }>
  initSession: () => Promise<void>
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [citations, setCitations] = useState<Citation[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [childName, setChildName] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const initSession = useCallback(async () => {
    try {
      const res = await createSession()
      setSessionId(res.session_id)
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content:
            "Hi! I'm Ollie, your AI Front Desk assistant at Sunshine Learning Center. I can help you with center policies, hours, enrollment info, or — if you have a security code — check on your child's day. How can I help you today?",
          citations: [],
          tool_used: null,
          transferred: false,
          transfer_reason: null,
          timestamp: new Date().toISOString(),
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create session')
    }
  }, [])

  const send = useCallback(
    async (text: string) => {
      if (!sessionId) return
      setError(null)

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: text,
        citations: [],
        tool_used: null,
        transferred: false,
        transfer_reason: null,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])
      setLoading(true)

      try {
        const res = await sendMessage(sessionId, text)
        const assistantMsg: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: res.message,
          citations: res.citations,
          tool_used: res.tool_used,
          transferred: res.transferred,
          transfer_reason: res.transfer_reason,
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, assistantMsg])
        if (res.citations.length > 0) {
          setCitations((prev) => [...prev, ...res.citations])
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to send message')
      } finally {
        setLoading(false)
      }
    },
    [sessionId],
  )

  const submitCode = useCallback(
    async (code: string): Promise<{ verified: boolean; error: string | null }> => {
      if (!sessionId) return { verified: false, error: 'No session' }
      try {
        const res = await verifyCode(sessionId, code)
        if (res.verified && res.child_name) {
          setChildName(res.child_name)
          const sysMsg: Message = {
            id: `sys-${Date.now()}`,
            role: 'assistant',
            content: `Security code verified! I can now access information for ${res.child_name} (${res.classroom}). What would you like to know?`,
            citations: [],
            tool_used: null,
            transferred: false,
            transfer_reason: null,
            timestamp: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, sysMsg])
        }
        return { verified: res.verified, error: res.error }
      } catch (e) {
        return { verified: false, error: e instanceof Error ? e.message : 'Verification failed' }
      }
    },
    [sessionId],
  )

  return { messages, citations, sessionId, childName, loading, error, send, submitCode, initSession }
}
