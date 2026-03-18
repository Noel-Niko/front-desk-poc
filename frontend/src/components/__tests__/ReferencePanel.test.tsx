import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ReferencePanel } from '../ReferencePanel'
import type { Citation } from '@/types/api'

describe('ReferencePanel', () => {
  it('renders "References" heading', () => {
    render(<ReferencePanel citations={[]} childName={null} />)
    expect(screen.getByText('References')).toBeInTheDocument()
  })

  it('renders handbook citations as links', () => {
    const citations: Citation[] = [
      { page: 43, section: 'Illness Policy', text: 'Children with fever must stay home' },
      { page: 31, section: 'Hours', text: 'Open 7 AM to 5:30 PM' },
    ]
    render(<ReferencePanel citations={citations} childName={null} />)
    expect(screen.getByText(/Illness Policy/)).toBeInTheDocument()
    expect(screen.getByText(/p\. 43/)).toBeInTheDocument()
    expect(screen.getByText(/Hours/)).toBeInTheDocument()
  })

  it('deduplicates citations by page', () => {
    const citations: Citation[] = [
      { page: 43, section: 'Illness Policy', text: 'text 1' },
      { page: 43, section: 'Illness Policy', text: 'text 2' },
    ]
    render(<ReferencePanel citations={citations} childName={null} />)
    const links = screen.getAllByText(/p\. 43/)
    expect(links).toHaveLength(1)
  })

  it('shows child name when authenticated', () => {
    render(<ReferencePanel citations={[]} childName="Sofia Martinez" />)
    expect(screen.getByText(/Sofia Martinez/)).toBeInTheDocument()
  })

  it('shows empty state when no citations', () => {
    render(<ReferencePanel citations={[]} childName={null} />)
    expect(screen.getByText(/no references yet/i)).toBeInTheDocument()
  })
})
