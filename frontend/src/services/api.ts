/** API client for the backend. All calls go through Vite proxy → localhost:8000. */

import type {
  ChatRequest,
  ChatResponse,
  SessionResponse,
  VerifyCodeRequest,
  VerifyCodeResponse,
} from '@/types/api'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export async function createSession(): Promise<SessionResponse> {
  return request<SessionResponse>('/session/new')
}

export async function sendMessage(
  sessionId: string,
  message: string,
): Promise<ChatResponse> {
  const body: ChatRequest = { session_id: sessionId, message }
  return request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function verifyCode(
  sessionId: string,
  code: string,
): Promise<VerifyCodeResponse> {
  const body: VerifyCodeRequest = { session_id: sessionId, code }
  return request<VerifyCodeResponse>('/verify-code', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function handbookPageUrl(page: number): string {
  return `${BASE}/handbook/${page}`
}
