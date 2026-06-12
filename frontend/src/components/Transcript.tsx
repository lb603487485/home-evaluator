import ReactMarkdown from 'react-markdown'
import { caveatCount, splitNarrative } from '../narrative'
import type { Session } from '../sessions'
import type { RunState } from '../sessions'
import NarrativePanel from './NarrativePanel'

const USER_BUBBLE =
  'self-end max-w-[85%] rounded-2xl rounded-br-sm bg-orange-100 px-3 py-2 text-sm text-stone-800'
const AGENT_BUBBLE =
  'self-start max-w-[85%] rounded-2xl rounded-bl-sm border border-stone-200 bg-white px-3 py-2 text-sm text-stone-700'

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
        {subject.notes && <span className="text-stone-600"> · “{subject.notes}”</span>}
        <span className="ml-1 text-xs text-stone-500">
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

      {(run.narrative || run.phase === 'running') && run.valuation && (() => {
        // while streaming (or when the sections are missing) keep the flat
        // bubble; the structured view appears once the narrative is complete
        const sections = run.phase === 'running' ? null : splitNarrative(run.narrative)
        if (!sections) {
          return (
            <div className={AGENT_BUBBLE}>
              🤖 <span className="text-xs font-semibold uppercase text-stone-400">Appraiser narrative</span>
              <NarrativePanel bare narrative={run.narrative}
                streaming={run.phase === 'running' && run.narrative.length > 0} />
            </div>
          )
        }
        const nCaveats = caveatCount(sections.caveats)
        const detailRow =
          'rounded-lg border border-stone-200 bg-white px-3 py-2'
        const summaryRow =
          'cursor-pointer select-none text-xs font-semibold uppercase text-stone-500'
        return (
          <div className="self-start flex w-[85%] max-w-[85%] flex-col gap-1.5">
            <div className="rounded-xl border border-stone-200 border-l-4 border-l-orange-600 bg-white px-3 py-2 text-sm text-stone-800 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase text-orange-700">
                  🤖 Conclusion
                </span>
                {run.valuation.confidence && (
                  <span className="rounded-full bg-orange-600 px-2 py-0.5 text-[10px] font-bold text-white">
                    Confidence {run.valuation.confidence}
                  </span>
                )}
              </div>
              <div className="prose prose-sm mt-1 max-w-none text-stone-800">
                <ReactMarkdown>{sections.conclusion}</ReactMarkdown>
              </div>
            </div>
            {sections.how && (
              <details className={detailRow}>
                <summary className={summaryRow}>How we got here</summary>
                <div className="prose prose-sm mt-1 max-w-none text-stone-700">
                  <ReactMarkdown>{sections.how}</ReactMarkdown>
                </div>
              </details>
            )}
            {sections.caveats && (
              <details className={detailRow}>
                <summary className={summaryRow}>
                  Caveats{nCaveats > 0 && (
                    <span className="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                      {nCaveats}
                    </span>
                  )}
                </summary>
                <div className="prose prose-sm mt-1 max-w-none text-stone-700">
                  <ReactMarkdown>{sections.caveats}</ReactMarkdown>
                </div>
              </details>
            )}
          </div>
        )
      })()}

      {session.qa.map((m, i) => (
        <div key={`qa${i}`} className={m.role === 'user' ? USER_BUBBLE : AGENT_BUBBLE}>
          {m.role === 'agent' && '🤖 '}{m.text}
        </div>
      ))}
    </div>
  )
}
