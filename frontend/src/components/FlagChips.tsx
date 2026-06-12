import type { RiskFlag } from '../types'

const SEVERITY_STYLES: Record<RiskFlag['severity'], string> = {
  info: 'bg-sky-100 text-sky-800 border-sky-200',
  caution: 'bg-amber-100 text-amber-800 border-amber-200',
  warning: 'bg-red-100 text-red-800 border-red-200',
}

export default function FlagChips({ flags }: { flags: RiskFlag[] }) {
  if (!flags.length) return null
  return (
    <div className="mt-3 space-y-1">
      <div className="flex flex-wrap gap-1.5">
        {flags.map(flag => (
          <span
            key={flag.code} title={flag.message}
            className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${SEVERITY_STYLES[flag.severity]}`}
          >
            {flag.code}
          </span>
        ))}
      </div>
      <ul className="text-xs text-stone-500">
        {flags.map(flag => <li key={flag.code}>• {flag.message}</li>)}
      </ul>
    </div>
  )
}
