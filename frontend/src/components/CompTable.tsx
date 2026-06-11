import { Fragment, useState } from 'react'
import { cad } from '../api'
import type { AdjustedComp, ReviewVerdict, ScoredComp } from '../types'

const VERDICT_STYLES: Record<string, string> = {
  keep: 'bg-emerald-100 text-emerald-800',
  demote: 'bg-amber-100 text-amber-800',
  exclude: 'bg-red-100 text-red-800',
}

const SOURCE_STYLES: Record<string, string> = {
  mls: 'bg-indigo-100 text-indigo-700',
  land_titles: 'bg-emerald-100 text-emerald-700',
  assessment: 'bg-amber-100 text-amber-700',
}

interface Props {
  comps: ScoredComp[]
  reviews: Record<string, ReviewVerdict>
  adjustments: Record<string, AdjustedComp>
}

export default function CompTable({ comps, reviews, adjustments }: Props) {
  const [open, setOpen] = useState<string | null>(null)
  if (!comps.length) return null

  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Address</th>
            <th className="px-3 py-2 text-right">Sold</th>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Attrs</th>
            <th className="px-3 py-2 text-right">Similarity</th>
            <th className="px-3 py-2">Review</th>
          </tr>
        </thead>
        <tbody>
          {comps.map((scored, i) => {
            const c = scored.comp
            const review = reviews[c.address_key]
            const adj = adjustments[c.address_key]
            const expanded = open === c.address_key
            const parts = Object.entries(scored.score_parts)
              .map(([dim, pts]) => `${dim}: ${pts}`).join('\n')
            return (
              <Fragment key={c.address_key}>
                <tr
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                  onClick={() => setOpen(expanded ? null : c.address_key)}
                >
                  <td className="px-3 py-2 text-slate-400">{i + 1}</td>
                  <td className="px-3 py-2 font-medium">{c.address}</td>
                  <td className="px-3 py-2 text-right">
                    {c.sold_price != null ? cad.format(c.sold_price) : '—'}
                  </td>
                  <td className="px-3 py-2 text-slate-500">{c.sold_date}</td>
                  <td className="px-3 py-2 text-slate-500">
                    {c.beds}{c.beds_bsmt ? `+${c.beds_bsmt}` : ''}bd · {c.baths}ba · {c.sqft} sqft
                  </td>
                  <td className="px-3 py-2 text-right font-semibold" title={parts}>
                    {scored.score}
                  </td>
                  <td className="px-3 py-2">
                    {review && (
                      <span
                        title={review.reason}
                        className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${review.unreviewed ? 'bg-slate-100 text-slate-500' : VERDICT_STYLES[review.verdict]}`}
                      >
                        {review.unreviewed ? 'unreviewed' : review.verdict}
                      </span>
                    )}
                  </td>
                </tr>
                {expanded && (
                  <tr className="border-t border-slate-100 bg-slate-50/60">
                    <td colSpan={7} className="px-6 py-3">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <h4 className="text-xs font-semibold uppercase text-slate-400">
                            Adjustment ladder
                          </h4>
                          {adj ? (
                            <table className="mt-1 text-xs">
                              <tbody>
                                <tr>
                                  <td className="pr-4 text-slate-500">sold price</td>
                                  <td className="text-right">{cad.format(adj.sold_price)}</td>
                                </tr>
                                {Object.entries(adj.adjustments).map(([term, amount]) => (
                                  <tr key={term}>
                                    <td className="pr-4 text-slate-500">{term}</td>
                                    <td className={`text-right ${amount > 0 ? 'text-emerald-700' : amount < 0 ? 'text-red-700' : 'text-slate-400'}`}>
                                      {amount === 0 ? '—' : (amount > 0 ? '+' : '') + cad.format(amount)}
                                    </td>
                                  </tr>
                                ))}
                                <tr className="border-t border-slate-200 font-semibold">
                                  <td className="pr-4">adjusted</td>
                                  <td className="text-right">{cad.format(adj.adjusted_price)}</td>
                                </tr>
                              </tbody>
                            </table>
                          ) : (
                            <p className="mt-1 text-xs text-slate-400">
                              not part of the final valuation set
                            </p>
                          )}
                          {review?.reason && (
                            <p className="mt-2 text-xs italic text-slate-500">
                              “{review.reason}”
                            </p>
                          )}
                        </div>
                        <div>
                          <h4 className="text-xs font-semibold uppercase text-slate-400">
                            Field provenance
                          </h4>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {Object.entries(c.sources).map(([field, source]) => (
                              <span key={field}
                                className={`rounded px-1.5 py-0.5 text-[10px] ${SOURCE_STYLES[source] ?? 'bg-slate-100 text-slate-600'}`}>
                                {field}: {source}
                              </span>
                            ))}
                          </div>
                          {c.conflicts.length > 0 && (
                            <ul className="mt-2 text-xs text-amber-700">
                              {c.conflicts.map((conflict, j) => (
                                <li key={j}>
                                  ⚠ {conflict.field}: {JSON.stringify(conflict.values)} →
                                  resolved with {conflict.resolved_with}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
