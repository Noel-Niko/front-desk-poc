import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { Header } from '../Header'

describe('Header', () => {
  const defaultProps = {
    voiceEnabled: false,
    onToggleVoice: vi.fn(),
    onEndChat: vi.fn(),
  }

  it('renders the center name', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText(/Sunshine Learning Center/i)).toBeInTheDocument()
  })

  it('renders the AI Front Desk subtitle', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByText(/AI Front Desk/i)).toBeInTheDocument()
  })

  it('renders voice toggle button', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByRole('button', { name: /voice/i })).toBeInTheDocument()
  })

  it('renders end chat button', () => {
    render(<Header {...defaultProps} />)
    expect(screen.getByRole('button', { name: /end chat/i })).toBeInTheDocument()
  })

  it('calls onEndChat when end chat button is clicked', () => {
    const onEndChat = vi.fn()
    render(<Header {...defaultProps} onEndChat={onEndChat} />)
    fireEvent.click(screen.getByRole('button', { name: /end chat/i }))
    expect(onEndChat).toHaveBeenCalledOnce()
  })
})
