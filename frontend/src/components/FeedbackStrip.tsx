import { useState } from 'react'
import { cad } from '../api'
import type { Session } from '../sessions'

interface Props {
  session: Session
  onSubmit: (fb: { rating: number; comment: string; userEstimate?: number }) => void
}

const LABELS = ['', 'way off', 'off', 'fair', 'good', 'spot on']

export default function FeedbackStrip({ session, onSubmit }: Props) {
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [estimate, setEstimate] = useState('')

  const fb = session.feedback
  if (fb) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-2 text-xs text-slate-500">
        <span className="text-amber-500">
          {'★'.repeat(fb.rating)}{'☆'.repeat(5 - fb.rating)}
        </span>
        <span className="ml-1">({LABELS[fb.rating]})</span>
        {fb.userEstimate != null && (
          <span> · your estimate {cad.format(fb.userEstimate)}</span>
        )}
        {fb.comment && <span> · “{fb.comment}”</span>}
        <span className="ml-1 text-slate-400">— logged for calibration</span>
      </div>
    )
  }

  return (
    <form
      className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 text-xs"
      onSubmit={e => {
        e.preventDefault()
        if (!rating) return
        onSubmit({
          rating,
          comment: comment.trim(),
          userEstimate: estimate ? Number(estimate) : undefined,
        })
      }}
    >
      <span className="font-semibold text-slate-600">Rate this valuation:</span>
      <span>
        {[1, 2, 3, 4, 5].map(n => (
          <button
            key={n} type="button" aria-label={`${n} star${n > 1 ? 's' : ''}`}
            className={`px-0.5 text-base leading-none ${
              n <= rating ? 'text-amber-500' : 'text-slate-300'}`}
            onClick={() => setRating(n)}
          >
            ★
          </button>
        ))}
      </span>
      {rating > 0 && <span className="text-slate-400">{LABELS[rating]}</span>}
      <input
        className="w-44 rounded border border-slate-200 px-1.5 py-1"
        placeholder="your estimate $ (optional)"
        inputMode="numeric"
        value={estimate}
        onChange={e => setEstimate(e.target.value.replace(/[^0-9]/g, ''))}
      />
      <input
        className="min-w-36 flex-1 rounded border border-slate-200 px-1.5 py-1"
        placeholder="what's good / what's off? (optional)"
        value={comment}
        onChange={e => setComment(e.target.value)}
      />
      <button
        type="submit" disabled={!rating}
        className="rounded bg-indigo-600 px-2.5 py-1 font-semibold text-white disabled:opacity-40"
      >
        Submit
      </button>
    </form>
  )
}
