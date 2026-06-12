import { useState } from 'react'
import { extract } from '../api'
import type { CommunityInfo, SubjectProperty } from '../types'

const PRESETS: Record<string, SubjectProperty> = {
  'Evanston detached': {
    community: 'Evanston', address: '310 Evanston Dr NW', property_type: 'detached',
    beds: 3, baths: 2.5,
    sqft: 1850, year_built: 2020, lot_sqft: 4000, garage_stalls: 2, notes: '',
  },
  'Bearspaw acreage': {
    community: 'Bearspaw', address: '', property_type: 'detached', beds: 4, baths: 3.5,
    sqft: 3000, year_built: 2005, lot_sqft: 150000, garage_stalls: 3, notes: '',
  },
  'With notes': {
    community: 'Evanston', address: '', property_type: 'detached', beds: 3, baths: 2.5,
    sqft: 1850, year_built: 2020, lot_sqft: 4000, garage_stalls: 2,
    notes: 'backs onto golf course, unfinished basement, original windows',
  },
}

interface Props {
  communities: CommunityInfo[]
  disabled: boolean
  collapsed?: boolean
  onToggle?: () => void
  onSubmit: (subject: SubjectProperty) => void
  prefill?: SubjectProperty | null // "edit in form": copy a session's subject in
}

export default function SubjectForm({
  communities, disabled, collapsed = false, onToggle, onSubmit, prefill = null,
}: Props) {
  const [subject, setSubject] = useState<SubjectProperty>(PRESETS['Evanston detached'])

  // "edit in form": adopt a new prefill during render (App passes a fresh
  // object per click, so identity change = new request)
  const [lastPrefill, setLastPrefill] = useState<SubjectProperty | null>(null)
  if (prefill && prefill !== lastPrefill) {
    setLastPrefill(prefill)
    setSubject(prefill)
  }
  const [pasteText, setPasteText] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [inferred, setInferred] =
    useState<{ value: string; reason: string } | null>(null)
  const [extractNote, setExtractNote] = useState('')

  const fillFromText = async () => {
    const text = pasteText.trim()
    if (!text || extracting) return
    setExtracting(true)
    setExtractNote('')
    try {
      const res = await extract(text)
      const patch: Partial<SubjectProperty> = { ...res.fields }
      if (res.community) {
        patch.community = res.community.value
        const ctypes = communities.find(
          c => c.community === res.community!.value)?.types ?? []
        const type = patch.property_type ?? subject.property_type
        patch.property_type = ctypes.includes(type) ? type : ctypes[0]
        setInferred(res.community.source === 'inferred'
          ? { value: res.community.value, reason: res.community.reason } : null)
      }
      if (!Object.keys(patch).length) {
        setExtractNote('Nothing recognized — fill the form manually.')
      }
      set(patch)
    } catch (err) {
      setExtractNote(`Extraction failed (${String(err)}) — fill the form manually.`)
    } finally {
      setExtracting(false)
    }
  }
  const types = communities.find(c => c.community === subject.community)?.types
    ?? ['detached']

  const set = (patch: Partial<SubjectProperty>) =>
    setSubject(prev => ({ ...prev, ...patch }))

  // deterministic community auto-fill: typed address contains a known community name
  const matched = communities.find(c =>
    subject.address.toLowerCase().includes(c.community.toLowerCase()))?.community
  const mismatch = matched && matched !== subject.community

  const onAddress = (address: string) => {
    const hit = communities.find(c =>
      address.toLowerCase().includes(c.community.toLowerCase()))
    if (!hit) { set({ address }); return }
    const ctypes = hit.types
    set({
      address, community: hit.community,
      property_type: ctypes.includes(subject.property_type)
        ? subject.property_type : ctypes[0],
    })
  }

  const field = 'w-full rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm'
  const label = 'block text-xs font-medium text-stone-500 mt-3 mb-1'

  if (collapsed) {
    return (
      <button
        type="button" onClick={onToggle}
        className="w-full rounded-xl bg-white p-3 text-left text-sm font-semibold text-stone-700 shadow-sm hover:bg-stone-50"
      >
        ▸ Subject form
      </button>
    )
  }

  return (
    <form
      className="rounded-xl bg-white p-4 shadow-sm"
      onSubmit={e => { e.preventDefault(); onSubmit(subject) }}
    >
      <h2
        className={`text-sm font-semibold text-stone-700 ${onToggle ? 'cursor-pointer select-none' : ''}`}
        onClick={onToggle}
      >
        {onToggle ? '▾ ' : ''}Subject property
      </h2>

      <div className="mt-2 flex flex-wrap gap-1">
        {Object.entries(PRESETS).map(([name, preset]) => (
          <button
            key={name} type="button" disabled={disabled}
            className="rounded-full border border-stone-300 px-2 py-0.5 text-xs text-stone-600 hover:bg-stone-100"
            onClick={() => setSubject(preset)}
          >
            {name}
          </button>
        ))}
      </div>

      <label className={label}>Describe the home (paste a sentence, listing line, or address)</label>
      <textarea
        className={`${field} h-14 resize-none`} value={pasteText} disabled={disabled}
        placeholder={'e.g. "88 9 St NE, Calgary, 3 bed 2.5 bath bungalow, ~1400 sqft, built 1952"'}
        onChange={e => setPasteText(e.target.value)}
      />
      <button
        type="button" disabled={disabled || extracting || !pasteText.trim()}
        className="mt-1 w-full rounded-md border border-orange-300 bg-orange-50 py-1 text-xs font-semibold text-orange-700 hover:bg-orange-100 disabled:opacity-50"
        onClick={() => void fillFromText()}
      >
        {extracting ? 'Extracting…' : 'Fill form from text'}
      </button>
      {extractNote && <p className="mt-1 text-xs text-amber-600">{extractNote}</p>}

      <label className={label}>Address (optional)</label>
      <input
        type="text" className={field} value={subject.address} disabled={disabled}
        placeholder="e.g. 310 Evanston Dr NW"
        onChange={e => onAddress(e.target.value)}
      />
      {mismatch && (
        <p className="mt-1 text-xs text-amber-600">
          ⚠ address mentions <b>{matched}</b> — community is set to <b>{subject.community}</b>
        </p>
      )}

      <label className={label}>Community</label>
      <select
        className={field} value={subject.community} disabled={disabled}
        onChange={e => {
          const community = e.target.value
          const ctypes = communities.find(c => c.community === community)?.types ?? []
          setInferred(null)
          set({ community, property_type: ctypes.includes(subject.property_type) ? subject.property_type : ctypes[0] })
        }}
      >
        {communities.map(c => (
          <option key={c.community} value={c.community}>
            {c.community} ({c.sales} sales)
          </option>
        ))}
      </select>
      {inferred && subject.community === inferred.value && (
        <p className="mt-1 text-xs text-amber-600">
          ⚐ inferred from the address ({inferred.reason}) — verify
        </p>
      )}

      <label className={label}>Property type</label>
      <select
        className={field} value={subject.property_type} disabled={disabled}
        onChange={e => set({ property_type: e.target.value })}
      >
        {types.map(t => <option key={t} value={t}>{t}</option>)}
      </select>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={label}>Beds</label>
          <input type="number" min={0} className={field} value={subject.beds}
            disabled={disabled} onChange={e => set({ beds: +e.target.value })} />
        </div>
        <div>
          <label className={label}>Baths</label>
          <input type="number" min={0} step={0.5} className={field} value={subject.baths}
            disabled={disabled} onChange={e => set({ baths: +e.target.value })} />
        </div>
        <div>
          <label className={label}>Sqft</label>
          <input type="number" min={200} className={field} value={subject.sqft}
            disabled={disabled} onChange={e => set({ sqft: +e.target.value })} />
        </div>
        <div>
          <label className={label}>Year built</label>
          <input type="number" min={1900} max={2026} className={field} value={subject.year_built}
            disabled={disabled} onChange={e => set({ year_built: +e.target.value })} />
        </div>
        <div>
          <label className={label}>Lot sqft</label>
          <input type="number" min={0} className={field} value={subject.lot_sqft ?? ''}
            placeholder="n/a" disabled={disabled}
            onChange={e => set({ lot_sqft: e.target.value === '' ? null : +e.target.value })} />
        </div>
        <div>
          <label className={label}>Garage stalls</label>
          <input type="number" min={0} max={6} className={field} value={subject.garage_stalls}
            disabled={disabled} onChange={e => set({ garage_stalls: +e.target.value })} />
        </div>
      </div>

      <label className={label}>Notes (free text — the agent mines these)</label>
      <textarea
        className={`${field} h-20 resize-none`} value={subject.notes} disabled={disabled}
        placeholder="e.g. backs onto golf course, unfinished basement"
        onChange={e => set({ notes: e.target.value })}
      />

      <button
        type="submit" disabled={disabled}
        className="mt-4 w-full rounded-lg bg-orange-600 py-2 text-sm font-semibold text-white hover:bg-orange-700 disabled:opacity-50"
      >
        {disabled ? 'Evaluating…' : 'Evaluate'}
      </button>
    </form>
  )
}
