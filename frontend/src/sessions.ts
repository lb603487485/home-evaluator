// Multi-session store: one RunState per home, SSE streams dispatch by session id
// so runs continue in the background while another session is on screen.

import type {
  AdjustedComp, AgentEvent, Exclusion, ReviewVerdict, ScoredComp, SearchUpdate,
  SubjectProperty, ValuationPayload,
} from './types'

export interface TimelineItem {
  kind: 'node' | 'search' | 'fallback'
  text: string
}

export interface RunState {
  phase: 'idle' | 'running' | 'done' | 'error'
  timeline: TimelineItem[]
  comps: ScoredComp[]
  exclusions: Exclusion[]
  reviews: Record<string, ReviewVerdict>
  adjustments: Record<string, AdjustedComp>
  valuation: ValuationPayload | null
  originalValuation?: ValuationPayload | null  // pre-challenge record, never mutated
  narrative: string
  lastSearch?: SearchUpdate
  searchLog: SearchUpdate[]
  error?: string
  totalS?: number
}

export type RunAction = { type: 'start' } | { type: 'fail'; message: string } | AgentEvent

export const INITIAL_RUN: RunState = {
  phase: 'idle', timeline: [], comps: [], exclusions: [], reviews: {},
  adjustments: {}, valuation: null, narrative: '', searchLog: [],
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'start':
      return { ...INITIAL_RUN, phase: 'running' }
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
      return {
        ...state,
        lastSearch: action.data,
        searchLog: [...state.searchLog, action.data],
        timeline: [...state.timeline, { kind: 'search', text }],
      }
    }
    case 'comps':
      return {
        ...state,
        comps: action.data.items,
        exclusions: action.data.exclusions ?? state.exclusions,
      }
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

export interface ChatMsg {
  role: 'user' | 'agent'
  text: string
  ts: number
}

export interface Feedback {
  rating: number                // 1–5
  comment: string
  userEstimate?: number
  at: number
}

export interface Session {
  id: string
  name: string                  // address if set, else "community · type"
  createdAt: number
  evaluatedAt?: number          // stamped on the 'done' event
  subject: SubjectProperty
  run: RunState
  qa: ChatMsg[]
  seenDone: boolean             // false ⇒ green "done ●" badge in the list
  whatIfOf?: string             // parent session id for what-if spawns
  feedback?: Feedback           // capture-only; never feeds the engine
}

export interface SessionsState {
  order: string[]               // newest first
  byId: Record<string, Session>
  activeId: string | null
}

export const NO_SESSIONS: SessionsState = { order: [], byId: {}, activeId: null }

export type SessionsAction =
  | { type: 'create'; session: Session }
  | { type: 'select'; id: string }
  | { type: 'run-event'; id: string; action: RunAction }
  | { type: 'qa'; id: string; msg: ChatMsg }
  | { type: 'revalue'; id: string; valuation: ValuationPayload }
  | { type: 'feedback'; id: string; feedback: Feedback }

export function sessionsReducer(s: SessionsState, a: SessionsAction): SessionsState {
  switch (a.type) {
    case 'create':
      return {
        order: [a.session.id, ...s.order],
        byId: { ...s.byId, [a.session.id]: a.session },
        activeId: a.session.id,
      }
    case 'select': {
      const target = s.byId[a.id]
      if (!target) return s
      return {
        ...s,
        activeId: a.id,
        byId: { ...s.byId, [a.id]: { ...target, seenDone: true } },
      }
    }
    case 'run-event': {
      const target = s.byId[a.id]
      if (!target) return s
      const done = a.action.type === 'done'
      return {
        ...s,
        byId: {
          ...s.byId,
          [a.id]: {
            ...target,
            run: runReducer(target.run, a.action),
            evaluatedAt: done ? Date.now() : target.evaluatedAt,
            seenDone: done ? s.activeId === a.id : target.seenDone,
          },
        },
      }
    }
    case 'qa': {
      const target = s.byId[a.id]
      if (!target) return s
      return {
        ...s,
        byId: { ...s.byId, [a.id]: { ...target, qa: [...target.qa, a.msg] } },
      }
    }
    case 'revalue': {
      const target = s.byId[a.id]
      if (!target) return s
      const run = {
        ...target.run,
        originalValuation: target.run.originalValuation ?? target.run.valuation,
        valuation: a.valuation,
        adjustments: Object.fromEntries(
          (a.valuation.adjustments ?? []).map(adj => [adj.address_key, adj])),
      }
      return { ...s, byId: { ...s.byId, [a.id]: { ...target, run } } }
    }
    case 'feedback': {
      const target = s.byId[a.id]
      if (!target) return s
      return { ...s, byId: { ...s.byId, [a.id]: { ...target, feedback: a.feedback } } }
    }
  }
}

// --- persistence: finished sessions only (an in-flight SSE stream can't be revived) ---

const KEY = 'home-evaluator-sessions-v1'

export function loadSessions(): SessionsState {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return NO_SESSIONS
    const saved = JSON.parse(raw) as SessionsState
    if (!Array.isArray(saved.order) || !saved.byId) return NO_SESSIONS
    return { ...saved, activeId: saved.order[0] ?? null }
  } catch {
    return NO_SESSIONS
  }
}

export function persistSessions(s: SessionsState): void {
  // nothing to record — and writing would clobber saved sessions if this
  // render cycle started from a failed load (e.g. transient storage denial)
  if (!s.order.length) return
  const keep = s.order
    .filter(id => ['done', 'error'].includes(s.byId[id]?.run.phase))
    .slice(0, 30)
  try {
    localStorage.setItem(KEY, JSON.stringify({
      order: keep,
      byId: Object.fromEntries(keep.map(id => [id, s.byId[id]])),
      activeId: null,
    }))
  } catch { /* storage full or blocked — persistence is best-effort */ }
}
