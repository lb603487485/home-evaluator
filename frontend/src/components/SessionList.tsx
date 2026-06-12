import { cad } from '../api'
import type { SessionsState } from '../sessions'

interface Props {
  sessions: SessionsState
  now: number // 1s tick from App while anything is running
  onSelect: (id: string) => void
}

const fmtTime = (ts?: number) =>
  ts ? new Date(ts).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''

export default function SessionList({ sessions, now, onSelect }: Props) {
  if (!sessions.order.length) return null
  return (
    <div className="space-y-2">
      <h2 className="text-[11px] font-semibold uppercase tracking-wide text-stone-400">
        Sessions ({sessions.order.length})
      </h2>
      {sessions.order.map(id => {
        const s = sessions.byId[id]
        const active = sessions.activeId === id
        const v = s.run.valuation
        const last = s.run.timeline[s.run.timeline.length - 1]?.text ?? 'starting'
        return (
          <button
            key={id} type="button" onClick={() => onSelect(id)}
            className={`block w-full rounded-lg border p-2 text-left text-xs shadow-sm ${
              active ? 'border-orange-600 bg-orange-100'
              : s.run.phase === 'error' ? 'border-red-200 bg-white hover:bg-red-50'
              : 'border-stone-200 bg-white hover:bg-stone-50'}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-semibold text-stone-700">{s.name}</span>
              {s.feedback && (
                <span className="shrink-0 text-amber-500" title={`rated ${s.feedback.rating}/5`}>
                  ★{s.feedback.rating}
                </span>
              )}
              {!s.seenDone && s.run.phase === 'done' && (
                <span className="shrink-0 rounded-full bg-emerald-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                  done ●
                </span>
              )}
            </div>
            <div className="mt-0.5 truncate text-stone-500">
              {s.run.phase === 'running' &&
                `⏳ ${last} · ${Math.max(0, Math.round((now - s.createdAt) / 1000))}s`}
              {s.run.phase === 'done' && (v?.estimate != null
                ? `${cad.format(v.estimate)} · ${v.confidence} · ${fmtTime(s.evaluatedAt)}`
                : `no estimate · ${fmtTime(s.evaluatedAt)}`)}
              {s.run.phase === 'error' && (
                <span className="text-red-600">failed — {s.run.error?.slice(0, 60)}</span>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
