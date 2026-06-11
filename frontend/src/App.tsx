import { useEffect, useReducer, useState } from 'react'
import { evaluate, fetchCommunities } from './api'
import AgentTimeline, { type TimelineItem } from './components/AgentTimeline'
import CompTable from './components/CompTable'
import NarrativePanel from './components/NarrativePanel'
import SubjectForm from './components/SubjectForm'
import ValuationBanner from './components/ValuationBanner'
import type {
  AdjustedComp, AgentEvent, CommunityInfo, ReviewVerdict, ScoredComp,
  SubjectProperty, ValuationPayload,
} from './types'

interface RunState {
  phase: 'idle' | 'running' | 'done' | 'error'
  timeline: TimelineItem[]
  comps: ScoredComp[]
  reviews: Record<string, ReviewVerdict>
  adjustments: Record<string, AdjustedComp>
  valuation: ValuationPayload | null
  narrative: string
  error?: string
  totalS?: number
}

const INITIAL: RunState = {
  phase: 'idle', timeline: [], comps: [], reviews: {}, adjustments: {},
  valuation: null, narrative: '',
}

type Action = { type: 'start' } | { type: 'fail'; message: string } | AgentEvent

function reducer(state: RunState, action: Action): RunState {
  switch (action.type) {
    case 'start':
      return { ...INITIAL, phase: 'running' }
    case 'fail':
      return { ...state, phase: 'error', error: action.message }
    case 'node': {
      const { node, status, detail } = action.data
      const text = `${node}: ${status}${detail ? ` — ${detail}` : ''}`
      return {
        ...state,
        timeline: [...state.timeline,
          { kind: status === 'fallback' ? 'fallback' : 'node', text }],
      }
    }
    case 'search_update': {
      const { round, found, reason, criteria } = action.data
      const text = `search round ${round}: ${found} comps — ${reason} `
        + `(${criteria.radius_km}km · ${criteria.days}d · ±${Math.round(criteria.sqft_pct * 100)}% sqft · ±${criteria.beds_delta}bd)`
      return { ...state, timeline: [...state.timeline, { kind: 'search', text }] }
    }
    case 'comps':
      return { ...state, comps: action.data.items }
    case 'reviews':
      return {
        ...state,
        reviews: Object.fromEntries(action.data.items.map(r => [r.address_key, r])),
      }
    case 'valuation':
      return {
        ...state,
        valuation: action.data,
        adjustments: Object.fromEntries(
          (action.data.adjustments ?? []).map(a => [a.address_key, a])),
      }
    case 'narrative_delta':
      return { ...state, narrative: state.narrative + action.data.text }
    case 'done':
      return { ...state, phase: 'done', totalS: action.data.timings.total_s }
    case 'error':
      return { ...state, phase: 'error', error: action.data.message }
    default:
      return state
  }
}

export default function App() {
  const [communities, setCommunities] = useState<CommunityInfo[]>([])
  const [state, dispatch] = useReducer(reducer, INITIAL)

  useEffect(() => {
    fetchCommunities().then(setCommunities).catch(console.error)
  }, [])

  const run = async (subject: SubjectProperty) => {
    dispatch({ type: 'start' })
    try {
      await evaluate(subject, dispatch)
    } catch (err) {
      dispatch({ type: 'fail', message: String(err) })
    }
  }

  const running = state.phase === 'running'

  return (
    <div className="mx-auto max-w-6xl p-4">
      <header className="mb-4 flex items-baseline justify-between">
        <h1 className="text-xl font-bold text-slate-800">
          home-evaluator
          <span className="ml-2 text-sm font-normal text-slate-400">
            comp-analysis agent · synthetic Calgary data
          </span>
        </h1>
        {state.totalS != null && (
          <span className="text-xs text-slate-400">run took {state.totalS}s</span>
        )}
      </header>

      <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
        <SubjectForm communities={communities} disabled={running} onSubmit={run} />

        <div className="space-y-4">
          {state.phase === 'error' && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {state.error}
            </div>
          )}
          {state.valuation && <ValuationBanner valuation={state.valuation} />}
          <AgentTimeline items={state.timeline} running={running} />
          <CompTable comps={state.comps} reviews={state.reviews}
            adjustments={state.adjustments} />
          <NarrativePanel narrative={state.narrative}
            streaming={running && state.narrative.length > 0} />
          {state.phase === 'idle' && (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
              Fill the form (or take a preset) and hit Evaluate — the agent's search,
              review, valuation and narrative stream in live.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
