import { useState } from 'react'
import type { RiskFlag } from '../types'

const SEVERITY_STYLES: Record<RiskFlag['severity'], string> = {
  info: 'bg-sky-100 text-sky-800 border-sky-200',
  caution: 'bg-amber-100 text-amber-800 border-amber-200',
  warning: 'bg-red-100 text-red-800 border-red-200',
}

interface Props {
  flags: RiskFlag[]
  meanings?: Record<string, string> // rule meanings from /api/methodology
}

export default function FlagChips({ flags, meanings }: Props) {
  const [open, setOpen] = useState<string | null>(null)
  if (!flags.length) return null
  return (
    <div className="mt-3 space-y-1">
      <div className="flex flex-wrap gap-1.5">
        {flags.map(flag => (
          <span key={flag.code} className="relative">
            <button
              type="button" title={flag.message}
              className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${SEVERITY_STYLES[flag.severity]} ${meanings?.[flag.code] ? 'cursor-pointer' : ''}`}
              onClick={() => setOpen(o => (o === flag.code ? null : flag.code))}
            >
              {flag.code}
            </button>
            {open === flag.code && meanings?.[flag.code] && (
              <span className="absolute left-0 top-full z-10 mt-1 block w-64 rounded-lg border border-stone-200 bg-white p-2 text-xs font-normal normal-case text-stone-700 shadow-lg">
                <b>{flag.code}</b> — {meanings[flag.code]}
              </span>
            )}
          </span>
        ))}
      </div>
      <ul className="text-xs text-stone-500">
        {flags.map(flag => <li key={flag.code}>• {flag.message}</li>)}
      </ul>
    </div>
  )
}
