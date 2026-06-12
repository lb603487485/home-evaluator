import { useState } from 'react'
import { ask } from '../api'
import type { Session } from '../sessions'
import type { SubjectProperty } from '../types'

interface Props {
  session: Session
  onMessage: (sessionId: string, role: 'user' | 'agent', text: string) => void
  onWhatIf: (parent: Session, modified: SubjectProperty, label: string) => void
}

export default function ChatInput({ session, onMessage, onWhatIf }: Props) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const ready = session.run.phase === 'done'

  const send = async () => {
    const question = text.trim()
    if (!question || busy || !ready) return
    setText('')
    setBusy(true)
    onMessage(session.id, 'user', question)
    try {
      const { run } = session
      const res = await ask({
        question,
        history: session.qa.map(m => ({ role: m.role, text: m.text })),
        context: {
          subject: session.subject,
          valuation: run.valuation,
          comps: run.comps.slice(0, 12).map(s => ({
            address: s.comp.address, score: s.score, score_parts: s.score_parts,
            sold_price: s.comp.sold_price, sold_date: s.comp.sold_date,
          })),
          reviews: Object.values(run.reviews),
          exclusions: run.exclusions,
          search: run.lastSearch,
          narrative: run.narrative,
        },
      })
      if (res.type === 'what_if' && res.modified_subject) {
        const diff = (res.changes ?? [])
          .map(c => `${c.field}: ${String(c.before) || '∅'} → ${String(c.after)}`)
          .join(' · ')
        onMessage(session.id, 'agent', `${res.text}\n↳ ${diff}`)
        onWhatIf(session, res.modified_subject, diff)
      } else {
        onMessage(session.id, 'agent', res.text)
      }
    } catch (err) {
      onMessage(session.id, 'agent', `(request failed — ${String(err)})`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      className="flex gap-2"
      onSubmit={e => { e.preventDefault(); void send() }}
    >
      <input
        type="text" value={text} disabled={!ready || busy}
        placeholder={ready
          ? 'Ask about this evaluation… (“why B?” · “what if it had a double garage?”)'
          : 'available when the evaluation finishes'}
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:bg-slate-50"
        onChange={e => setText(e.target.value)}
      />
      <button
        type="submit" disabled={!ready || busy || !text.trim()}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {busy ? '…' : 'Ask'}
      </button>
    </form>
  )
}
