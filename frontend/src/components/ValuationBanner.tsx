import { cad } from '../api'
import type { ValuationPayload } from '../types'
import FlagChips from './FlagChips'

const CONFIDENCE_STYLES: Record<string, string> = {
  A: 'bg-emerald-100 text-emerald-800',
  B: 'bg-amber-100 text-amber-800',
  C: 'bg-red-100 text-red-800',
}

export default function ValuationBanner({ valuation }: { valuation: ValuationPayload }) {
  const { estimate, low, high, confidence, flags } = valuation
  if (estimate == null) {
    return (
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <p className="text-sm text-slate-600">
          No usable comparable sales survived review — no estimate produced.
        </p>
        <FlagChips flags={flags} />
      </div>
    )
  }
  const span = high! - low!
  const pct = span > 0 ? ((estimate - low!) / span) * 100 : 50
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <div>
          <span className="text-xs uppercase tracking-wide text-slate-400">Estimate</span>
          <div className="text-3xl font-bold text-slate-900">{cad.format(estimate)}</div>
        </div>
        <span
          title="Confidence grade: comp count, dispersion, similarity"
          className={`rounded-lg px-3 py-1 text-lg font-bold ${CONFIDENCE_STYLES[confidence ?? 'C']}`}
        >
          {confidence}
        </span>
      </div>
      <div className="mt-4">
        <div className="relative h-2 rounded-full bg-slate-200">
          <div className="absolute inset-y-0 rounded-full bg-indigo-200"
            style={{ left: 0, right: 0 }} />
          <div className="absolute -top-1 h-4 w-1 rounded bg-indigo-600"
            style={{ left: `${pct}%` }} />
        </div>
        <div className="mt-1 flex justify-between text-xs text-slate-500">
          <span>{cad.format(low!)}</span>
          <span className="text-slate-400">weighted P25–P75</span>
          <span>{cad.format(high!)}</span>
        </div>
      </div>
      <FlagChips flags={flags} />
    </div>
  )
}
