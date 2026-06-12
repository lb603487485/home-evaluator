import { useState } from 'react'
import { cad } from '../api'
import type { Session } from '../sessions'
import CompTable from './CompTable'
import FlagChips from './FlagChips'

const CONFIDENCE_STYLES: Record<string, string> = {
  A: 'bg-emerald-100 text-emerald-800',
  B: 'bg-amber-100 text-amber-800',
  C: 'bg-red-100 text-red-800',
}

const fmtSigned = (n: number) => (n > 0 ? '+' : '') + cad.format(n)

export default function HeroCard({ session, now }: { session: Session; now: number }) {
  const { run, subject } = session
  const [showComps, setShowComps] = useState(false)

  // slim progress strip until the valuation lands
  if (run.phase === 'running' && !run.valuation) {
    const last = run.timeline[run.timeline.length - 1]?.text ?? 'starting…'
    const elapsed = Math.max(0, Math.round((now - session.createdAt) / 1000))
    return (
      <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm text-indigo-800">
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
    <div className="mt-2 text-xs text-slate-500">
      Evaluated <b>{new Date(session.evaluatedAt).toLocaleString([], {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</b>
      {' · '}comps as-of {new Date(session.evaluatedAt).toLocaleDateString([], {
        month: 'short', day: 'numeric' })}
      {run.totalS != null && <> · run took {run.totalS}s</>}
    </div>
  )

  if (v.estimate == null) {
    return (
      <div className="rounded-xl border-2 border-slate-300 bg-white p-4 shadow-sm">
        <div className="text-xs text-slate-500">Subject: {recap}</div>
        <p className="mt-2 text-sm text-slate-600">
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
    <div className="rounded-xl border-2 border-indigo-500 bg-gradient-to-b from-indigo-50 to-white p-4 shadow-md">
      <div className="text-xs text-slate-500">Subject: {recap}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-3xl font-extrabold text-slate-900">{cad.format(v.estimate)}</span>
        <span
          title="Confidence grade: comp count, dispersion, similarity"
          className={`rounded-lg px-2.5 py-0.5 text-base font-bold ${CONFIDENCE_STYLES[v.confidence ?? 'C']}`}
        >
          {v.confidence}
        </span>
        <span className="text-sm text-slate-600">
          range {cad.format(v.low!)} – {cad.format(v.high!)}
        </span>
      </div>
      <div className="mt-2">
        <div className="relative h-1.5 rounded-full bg-indigo-100">
          <div className="absolute -top-1 h-3.5 w-1 rounded bg-indigo-600"
            style={{ left: `${pct}%` }} />
        </div>
      </div>
      <div className="mt-2 text-sm text-slate-700">
        <b>Key factors:</b> {factors}
      </div>
      <FlagChips flags={v.flags} />
      {stamp}
      <button
        type="button" onClick={() => setShowComps(s => !s)}
        className="mt-2 text-xs font-medium text-indigo-700 hover:underline"
      >
        {showComps ? '▾ hide' : '▸ show'} comp table — {kept.length} kept of {run.comps.length} scored, with adjustment ladders
      </button>
      {showComps && (
        <div className="mt-2">
          <CompTable comps={run.comps} reviews={run.reviews} adjustments={run.adjustments} />
        </div>
      )}
    </div>
  )
}
