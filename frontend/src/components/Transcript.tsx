import type { Session } from '../sessions'
import type { RunState } from '../sessions'
import NarrativePanel from './NarrativePanel'

const USER_BUBBLE =
  'self-end max-w-[85%] rounded-2xl rounded-br-sm bg-blue-100 px-3 py-2 text-sm text-slate-800'
const AGENT_BUBBLE =
  'self-start max-w-[85%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700'

interface Line {
  key: string
  text: string
  fallback?: boolean
}

/** Map raw timeline/stored data to friendly agent messages. */
function agentLines(run: RunState): Line[] {
  const lines: Line[] = []
  run.timeline.forEach((item, i) => {
    const key = `t${i}`
    if (item.kind === 'fallback') {
      lines.push({ key, text: item.text, fallback: true })
    } else if (item.text.startsWith('intake: done — ')) {
      lines.push({ key, text: `Noted: ${item.text.slice('intake: done — '.length)}.` })
    } else if (item.text.startsWith('widen: done — ')) {
      lines.push({ key, text: `Widening the search — ${item.text.slice('widen: done — '.length)}` })
    } else if (item.kind === 'search') {
      lines.push({
        key,
        text: item.text
          .replace(/^search round 0: /, 'Initial search: found ')
          .replace(/^search round (\d+): /, 'Search round $1 (widened): found '),
      })
    }
    // bare "node: started/done" items are noise in a transcript — skipped
  })
  if (run.exclusions.length) {
    const counts = new Map<string, number>()
    for (const e of run.exclusions) {
      const r = e.reason.split(' (')[0].replaceAll('_', ' ')
      counts.set(r, (counts.get(r) ?? 0) + 1)
    }
    const parts = [...counts].map(([r, n]) => (n > 1 ? `${r} ×${n}` : r)).join(', ')
    lines.push({ key: 'excl', text: `Excluded ${run.exclusions.length} before scoring: ${parts}.` })
  }
  const reviews = Object.values(run.reviews)
  if (reviews.length) {
    const n = (verdict: string) => reviews.filter(r => !r.unreviewed && r.verdict === verdict).length
    const bits = [`kept ${n('keep')}`]
    if (n('demote')) bits.push(`demoted ${n('demote')}`)
    if (n('exclude')) bits.push(`excluded ${n('exclude')}`)
    if (reviews.some(r => r.unreviewed)) bits.push(`${reviews.filter(r => r.unreviewed).length} unreviewed`)
    lines.push({ key: 'rev', text: `Reviewed ${reviews.length} comps: ${bits.join(', ')}.` })
  }
  return lines
}

export default function Transcript({ session }: { session: Session }) {
  const { run, subject } = session
  const recap = [
    subject.address || null, subject.community, subject.property_type,
    `${subject.beds} bd`, `${subject.baths} ba`, `${subject.sqft.toLocaleString()} sqft`,
    `built ${subject.year_built}`,
  ].filter(Boolean).join(' · ')

  return (
    <div className="flex flex-col gap-2">
      <div className={USER_BUBBLE}>
        📋 {recap}
        {subject.notes && <span className="text-slate-600"> · “{subject.notes}”</span>}
        <span className="ml-1 text-xs text-slate-500">
          {' · '}
          {new Date(session.createdAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
        </span>
      </div>

      {agentLines(run).map(line => (
        <div key={line.key} className={AGENT_BUBBLE}>
          🤖 {line.text}
          {line.fallback && (
            <span className="ml-1.5 rounded bg-amber-100 px-1 text-[10px] text-amber-800">
              fallback
            </span>
          )}
        </div>
      ))}

      {(run.narrative || run.phase === 'running') && run.valuation && (
        <div className={AGENT_BUBBLE}>
          🤖 <span className="text-xs font-semibold uppercase text-slate-400">Appraiser narrative</span>
          <NarrativePanel bare narrative={run.narrative}
            streaming={run.phase === 'running' && run.narrative.length > 0} />
        </div>
      )}

      {session.qa.map((m, i) => (
        <div key={`qa${i}`} className={m.role === 'user' ? USER_BUBBLE : AGENT_BUBBLE}>
          {m.role === 'agent' && '🤖 '}{m.text}
        </div>
      ))}
    </div>
  )
}
