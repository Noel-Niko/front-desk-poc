import { useState } from 'react'

interface RatingModalProps {
  open: boolean
  onSubmit: (data: { rating: number; feedback: string }) => void
  onClose: () => void
}

export function RatingModal({ open, onSubmit, onClose }: RatingModalProps) {
  const [rating, setRating] = useState<number>(0)
  const [feedback, setFeedback] = useState('')

  if (!open) return null

  const handleSubmit = () => {
    if (rating === 0) return
    onSubmit({ rating, feedback })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-center text-lg font-semibold text-gray-800">
          Rate your experience
        </h2>

        {/* Star buttons */}
        <div className="mb-4 flex justify-center gap-2">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              role="button"
              aria-label={`Star ${star}`}
              aria-pressed={star <= rating}
              onClick={() => setRating(star)}
              className={`text-3xl transition-colors ${
                star <= rating ? 'text-yellow-400' : 'text-gray-300'
              }`}
            >
              ★
            </button>
          ))}
        </div>

        {/* Feedback textarea */}
        <textarea
          placeholder="Optional feedback..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={3}
          className="mb-4 w-full rounded-lg border border-gray-200 p-2 text-sm focus:border-blue-400 focus:outline-none"
        />

        {/* Actions */}
        <div className="flex gap-2">
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="flex-1 rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
          >
            Close
          </button>
          <button
            type="button"
            aria-label="Submit"
            disabled={rating === 0}
            onClick={handleSubmit}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  )
}
