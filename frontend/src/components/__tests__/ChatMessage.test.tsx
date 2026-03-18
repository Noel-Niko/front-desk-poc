import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ChatMessage } from '../ChatMessage'
import type { Message } from '@/types/api'

describe('ChatMessage', () => {
  const baseMessage: Message = {
    id: '1',
    role: 'assistant',
    content: 'Hello! How can I help you today?',
    citations: [],
    tool_used: null,
    transferred: false,
    transfer_reason: null,
    timestamp: new Date().toISOString(),
  }

  it('renders assistant message with content', () => {
    render(<ChatMessage message={baseMessage} />)
    expect(screen.getByText('Hello! How can I help you today?')).toBeInTheDocument()
  })

  it('renders user message with different styling', () => {
    const userMsg: Message = { ...baseMessage, id: '2', role: 'user', content: 'What are your hours?' }
    const { container } = render(<ChatMessage message={userMsg} />)
    const bubble = container.querySelector('[data-role="user"]')
    expect(bubble).toBeInTheDocument()
  })

  it('renders assistant message with owl label', () => {
    render(<ChatMessage message={baseMessage} />)
    expect(screen.getByText('Ms. Olivia')).toBeInTheDocument()
  })

  it('renders user message with You label', () => {
    const userMsg: Message = { ...baseMessage, id: '2', role: 'user', content: 'Hi' }
    render(<ChatMessage message={userMsg} />)
    expect(screen.getByText('You')).toBeInTheDocument()
  })

  it('renders citations as clickable links', () => {
    const msg: Message = {
      ...baseMessage,
      content: 'The center opens at 7 AM.',
      citations: [
        { page: 31, section: 'Hours of Operation', text: 'Center hours are 7:00 AM to 5:30 PM' },
      ],
    }
    render(<ChatMessage message={msg} />)
    const link = screen.getByText(/p\.\s*31/)
    expect(link).toBeInTheDocument()
    expect(link.closest('a')).toHaveAttribute('href', '/api/handbook/31')
  })

  it('shows transfer notice when transferred', () => {
    const msg: Message = {
      ...baseMessage,
      transferred: true,
      transfer_reason: 'Billing dispute',
      content: 'Let me connect you with a staff member.',
    }
    render(<ChatMessage message={msg} />)
    expect(screen.getByText(/connect you/i)).toBeInTheDocument()
  })
})
