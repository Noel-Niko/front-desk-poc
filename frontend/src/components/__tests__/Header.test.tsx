import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Header } from '../Header'

describe('Header', () => {
  it('renders the center name', () => {
    render(<Header voiceEnabled={false} onToggleVoice={() => {}} />)
    expect(screen.getByText(/Sunshine Learning Center/i)).toBeInTheDocument()
  })

  it('renders the AI Front Desk subtitle', () => {
    render(<Header voiceEnabled={false} onToggleVoice={() => {}} />)
    expect(screen.getByText(/AI Front Desk/i)).toBeInTheDocument()
  })

  it('renders voice toggle button', () => {
    render(<Header voiceEnabled={false} onToggleVoice={() => {}} />)
    expect(screen.getByRole('button', { name: /voice/i })).toBeInTheDocument()
  })
})
