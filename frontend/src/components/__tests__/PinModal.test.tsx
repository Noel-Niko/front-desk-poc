import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { PinModal } from '../PinModal'

describe('PinModal', () => {
  it('renders 4 digit input boxes', () => {
    render(<PinModal open={true} onSubmit={vi.fn()} onClose={vi.fn()} error={null} loading={false} />)
    const inputs = screen.getAllByRole('textbox')
    expect(inputs).toHaveLength(4)
  })

  it('does not render when open is false', () => {
    const { container } = render(
      <PinModal open={false} onSubmit={vi.fn()} onClose={vi.fn()} error={null} loading={false} />,
    )
    expect(container.querySelector('[data-testid="pin-modal"]')).not.toBeInTheDocument()
  })

  it('calls onSubmit with 4-digit code when all digits entered', () => {
    const onSubmit = vi.fn()
    render(<PinModal open={true} onSubmit={onSubmit} onClose={vi.fn()} error={null} loading={false} />)
    const inputs = screen.getAllByRole('textbox')
    fireEvent.change(inputs[0], { target: { value: '7' } })
    fireEvent.change(inputs[1], { target: { value: '2' } })
    fireEvent.change(inputs[2], { target: { value: '9' } })
    fireEvent.change(inputs[3], { target: { value: '1' } })
    expect(onSubmit).toHaveBeenCalledWith('7291')
  })

  it('displays error message when provided', () => {
    render(
      <PinModal open={true} onSubmit={vi.fn()} onClose={vi.fn()} error="Invalid code" loading={false} />,
    )
    expect(screen.getByText('Invalid code')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    render(
      <PinModal open={true} onSubmit={vi.fn()} onClose={vi.fn()} error={null} loading={true} />,
    )
    expect(screen.getByText(/verifying/i)).toBeInTheDocument()
  })
})
