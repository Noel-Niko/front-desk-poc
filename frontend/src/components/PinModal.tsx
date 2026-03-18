import { useRef, useEffect, type ChangeEvent } from 'react'
import { useState } from 'react'

interface PinModalProps {
  open: boolean
  onSubmit: (code: string) => void
  onClose: () => void
  error: string | null
  loading: boolean
}

export function PinModal({ open, onSubmit, onClose, error, loading }: PinModalProps) {
  const [digits, setDigits] = useState(['', '', '', ''])
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (open) {
      setDigits(['', '', '', ''])
      // Focus first input after render
      setTimeout(() => inputRefs.current[0]?.focus(), 50)
    }
  }, [open])

  function handleChange(index: number, e: ChangeEvent<HTMLInputElement>) {
    const val = e.target.value.replace(/\D/g, '').slice(-1)
    const newDigits = [...digits]
    newDigits[index] = val
    setDigits(newDigits)

    if (val && index < 3) {
      inputRefs.current[index + 1]?.focus()
    }

    // Auto-submit when all 4 digits filled
    if (val && index === 3) {
      const code = newDigits.join('')
      if (code.length === 4) {
        onSubmit(code)
      }
    }
  }

  if (!open) return null

  return (
    <div
      data-testid="pin-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-blackout/50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl p-8 shadow-lg max-w-sm w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-blackout text-center mb-2">
          Enter Security Code
        </h2>
        <p className="text-sm text-blueberry text-center mb-6">
          Enter your 4-digit code to access child information
        </p>

        {loading ? (
          <p className="text-center text-blurple font-medium">Verifying...</p>
        ) : (
          <div className="flex justify-center gap-3 mb-4">
            {digits.map((digit, i) => (
              <input
                key={i}
                ref={(el) => { inputRefs.current[i] = el }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleChange(i, e)}
                role="textbox"
                className="w-14 h-14 text-center text-2xl font-bold border-2 border-barnacle rounded-xl bg-bubble text-blackout focus:border-blurple focus:ring-2 focus:ring-blurple/20 focus:outline-none"
              />
            ))}
          </div>
        )}

        {error && (
          <p className="text-sm text-sangria text-center mt-2">{error}</p>
        )}
      </div>
    </div>
  )
}
