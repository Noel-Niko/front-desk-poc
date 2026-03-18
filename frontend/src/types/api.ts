/** API types matching backend Pydantic schemas. */

export interface ChatRequest {
  session_id: string
  message: string
}

export interface Citation {
  page: number
  section: string
  text: string
}

export interface ChatResponse {
  session_id: string
  message: string
  citations: Citation[]
  tool_used: string | null
  transferred: boolean
  transfer_reason: string | null
}

export interface VerifyCodeRequest {
  session_id: string
  code: string
}

export interface VerifyCodeResponse {
  verified: boolean
  child_id: number | null
  child_name: string | null
  classroom: string | null
  error: string | null
}

export interface SessionResponse {
  session_id: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  tool_used: string | null
  transferred: boolean
  transfer_reason: string | null
  timestamp: string
}

/** Voice WebSocket message types (server → client). */
export interface TranscriptEvent {
  type: 'transcript'
  text: string
  is_final: boolean
  confidence?: number
}

export interface ResponseEvent {
  type: 'response'
  text: string
  citations: Citation[]
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

/** TTS events (server → client). */
export interface ResponseDeltaEvent {
  type: 'response_delta'
  text: string
}

export interface TTSStartEvent {
  type: 'tts_start'
}

export interface TTSEndEvent {
  type: 'tts_end'
}

export type ServerEvent =
  | TranscriptEvent
  | ResponseEvent
  | ResponseDeltaEvent
  | TTSStartEvent
  | TTSEndEvent
  | ErrorEvent
