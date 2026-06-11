export interface TimelineItem {
  kind: 'node' | 'search' | 'fallback'
  text: string
}

interface Props {
  items: TimelineItem[]
  running: boolean
}

const STYLES: Record<TimelineItem['kind'], string> = {
  node: 'text-slate-600',
  search: 'text-indigo-700',
  fallback: 'text-amber-700',
}

export default function AgentTimeline({ items, running }: Props) {
  if (!items.length && !running) return null
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-700">Agent timeline</h2>
      <ul className="mt-2 space-y-1 font-mono text-xs">
        {items.map((item, i) => (
          <li key={i} className={STYLES[item.kind]}>
            {item.kind === 'fallback' && (
              <span className="mr-1 rounded bg-amber-100 px-1 py-0.5 text-[10px] font-semibold text-amber-800">
                fallback
              </span>
            )}
            {item.text}
          </li>
        ))}
        {running && <li className="animate-pulse text-slate-400">working…</li>}
      </ul>
    </div>
  )
}
