import { useState } from 'react'
import { cad, type Methodology } from '../api'
import type { Session } from '../sessions'
import CompTable from './CompTable'
import FlagChips from './FlagChips'

const CONFIDENCE_STYLES: Record<string, string> = {
  A: 'bg-emerald-100 text-emerald-800',
  B: 'bg-amber-100 text-amber-800',
  C: 'bg-red-100 text-red-800',
}

const fmtSigned = (n: number) => (n > 0 ? '+' : '') + cad.format(n)

interface Props {
  session: Session
  now: number
  methodology?: Methodology | null
}

export default function HeroCard({ session, now, methodology }: Props) {
  const { run, subject } = session
  const [showComps, setShowComps] = useState(false)
  const [showGrade, setShowGrade] = useState(false)

  // slim progress strip until the valuation lands
  if (run.phase === 'running' && !run.valuation) {
    const last = run.timeline[run.timeline.length - 1]?.text ?? 'starting…'
    const elapsed = Math.max(0, Math.round((now - session.createdAt) / 1000))
    return (
      <div className="rounded-xl border border-orange-200 bg-orange-100 px-4 py-2 text-sm text-orange-800">
        <span className="animate-pulse">⏳</span> {last} · {elapsed}s
      </div>
    )
  }
  if (!run.valuation) return null

  const v = run.valuation
  const recap = [
    subject.address || null, subject.community, subject.property_type,
    `${subject.beds} bd / ${subject.baths} ba`, `${subject.sqft.toLocaleString()} sqft`,
    `built ${subject.year_built}`,
    subject.garage_stalls ? `${subject.garage_stalls} garage` : null,
  ].filter(Boolean).join(' · ')

  const stamp = session.evaluatedAt && (
    <div className="mt-2 text-xs text-stone-500">
      Evaluated <b>{new Date(session.evaluatedAt).toLocaleString([], {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</b>
      {' · '}comps as-of {new Date(session.evaluatedAt).toLocaleDateString([], {
        month: 'short', day: 'numeric' })}
      {run.totalS != null && <> · run took {run.totalS}s</>}
    </div>
  )

  if (v.estimate == null) {
    return (
      <div className="rounded-xl border-2 border-orange-400 bg-gradient-to-b from-orange-100 to-white p-4 shadow-md">
        <div className="text-xs text-stone-500">Subject: {recap}</div>
        <p className="mt-2 text-sm text-stone-600">
          No usable comparable sales survived review — no estimate produced.
        </p>
        <FlagChips flags={v.flags} />
        {stamp}
      </div>
    )
  }

  const kept = v.adjustments ?? []
  const spreadPct = v.low != null && v.high != null && v.estimate
    ? Math.round(1000 * (v.high - v.low) / v.estimate) / 10 : null
  const largest = kept
    .flatMap(a => Object.entries(a.adjustments))
    .reduce<[string, number]>((m, [k, x]) => (Math.abs(x) > Math.abs(m[1]) ? [k, x] : m),
      ['', 0])
  const c = run.lastSearch?.criteria
  const factors = [
    `${kept.length} comps kept`,
    c && `within ${c.radius_km} km / ${c.days} days`,
    spreadPct != null && `price spread ${spreadPct}%`,
    largest[0] && `largest adjustment: ${largest[0]} ${fmtSigned(largest[1])}`,
  ].filter(Boolean).join(' · ')

  const span = (v.high ?? 0) - (v.low ?? 0)
  const pct = span > 0 ? ((v.estimate - v.low!) / span) * 100 : 50

  return (
    <div className="rounded-xl border-2 border-orange-400 bg-gradient-to-b from-orange-100 to-white p-4 shadow-md">
      <div className="text-xs text-stone-500">Subject: {recap}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-3xl font-extrabold text-stone-900">{cad.format(v.estimate)}</span>
        <span className="relative">
          <button
            type="button"
            title="Confidence grade: comp count, dispersion, similarity — click for thresholds"
            className={`rounded-lg px-2.5 py-0.5 text-base font-bold ${CONFIDENCE_STYLES[v.confidence ?? 'C']}`}
            onClick={() => setShowGrade(g => !g)}
          >
            {v.confidence}
          </button>
          {showGrade && methodology && v.confidence && (
            <span className="absolute left-0 top-full z-10 mt-1 block w-72 rounded-lg border border-stone-200 bg-white p-2 text-xs font-normal text-stone-700 shadow-lg">
              <b>Confidence {v.confidence}</b> — {methodology.confidence[v.confidence]}
            </span>
          )}
        </span>
        <span className="text-sm text-stone-600">
          range {cad.format(v.low!)} – {cad.format(v.high!)}
        </span>
      </div>
      <div className="mt-2">
        <div className="relative h-1.5 rounded-full bg-orange-200">
          <div className="absolute -top-1 h-3.5 w-1 rounded bg-orange-600"
            style={{ left: `${pct}%` }} />
        </div>
      </div>
      <div className="mt-2 text-sm text-stone-700">
        <b>Key factors:</b> {factors}
      </div>
      {run.originalValuation && (
        <div className="mt-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-800">
          ⚖ Reviewer challenge applied — revised from{' '}
          {run.originalValuation.estimate != null
            ? cad.format(run.originalValuation.estimate) : 'no estimate'}
          {' '}({run.originalValuation.confidence}). The exchange is in the chat below.
        </div>
      )}
      <FlagChips flags={v.flags} meanings={methodology?.flags} />
      {stamp}
      <button
        type="button" onClick={() => setShowComps(s => !s)}
        className="mt-2 text-xs font-medium text-orange-700 hover:underline"
      >
        {showComps ? '▾ hide' : '▸ show'} comp table — {kept.length} kept of {run.comps.length} scored, with adjustment ladders
      </button>
      {showComps && (
        <div className="mt-2 max-h-[45vh] overflow-y-auto">
          <CompTable comps={run.comps} reviews={run.reviews} adjustments={run.adjustments} />
        </div>
      )}
    </div>
  )
}
