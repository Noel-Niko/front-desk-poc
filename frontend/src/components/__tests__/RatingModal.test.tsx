import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { RatingModal } from '../RatingModal'

describe('RatingModal', () => {
  const defaultProps = {
    open: true,
    onSubmit: vi.fn(),
    onClose: vi.fn(),
  }

  it('renders 5 star buttons when open', () => {
    render(<RatingModal {...defaultProps} />)
    const stars = screen.getAllByRole('button', { name: /star/i })
    expect(stars).toHaveLength(5)
  })

  it('is not visible when open is false', () => {
    render(<RatingModal {...defaultProps} open={false} />)
    expect(screen.queryByText(/rate/i)).not.toBeInTheDocument()
  })

  it('highlights stars 1-4 when star 4 is clicked', () => {
    render(<RatingModal {...defaultProps} />)
    const stars = screen.getAllByRole('button', { name: /star/i })
    fireEvent.click(stars[3]) // 0-indexed, so star 4

    // Stars 1-4 should be filled (have aria-pressed="true")
    for (let i = 0; i < 4; i++) {
      expect(stars[i]).toHaveAttribute('aria-pressed', 'true')
    }
    // Star 5 should not be filled
    expect(stars[4]).toHaveAttribute('aria-pressed', 'false')
  })

  it('renders a textarea for optional feedback', () => {
    render(<RatingModal {...defaultProps} />)
    expect(screen.getByPlaceholderText(/feedback/i)).toBeInTheDocument()
  })

  it('calls onSubmit with rating and feedback when submitted', () => {
    const onSubmit = vi.fn()
    render(<RatingModal {...defaultProps} onSubmit={onSubmit} />)

    // Click star 5
    const stars = screen.getAllByRole('button', { name: /star/i })
    fireEvent.click(stars[4])

    // Type feedback
    const textarea = screen.getByPlaceholderText(/feedback/i)
    fireEvent.change(textarea, { target: { value: 'Great service!' } })

    // Submit
    fireEvent.click(screen.getByRole('button', { name: /submit/i }))
    expect(onSubmit).toHaveBeenCalledWith({ rating: 5, feedback: 'Great service!' })
  })

  it('does not allow submit without selecting a rating', () => {
    const onSubmit = vi.fn()
    render(<RatingModal {...defaultProps} onSubmit={onSubmit} />)

    const submitBtn = screen.getByRole('button', { name: /submit/i })
    expect(submitBtn).toBeDisabled()
  })

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn()
    render(<RatingModal {...defaultProps} onClose={onClose} />)

    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
