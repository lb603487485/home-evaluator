import { useEffect, useReducer, useState } from 'react'
import {
  evaluate, fetchCommunities, fetchMethodology, postFeedback, type Methodology,
} from './api'
import ChatInput from './components/ChatInput'
import FeedbackStrip from './components/FeedbackStrip'
import HeroCard from './components/HeroCard'
import SessionList from './components/SessionList'
import SubjectForm from './components/SubjectForm'
import Transcript from './components/Transcript'
import {
  INITIAL_RUN, loadSessions, persistSessions, sessionsReducer, type Session,
} from './sessions'
import type { CommunityInfo, SubjectProperty } from './types'

export default function App() {
  const [communities, setCommunities] = useState<CommunityInfo[]>([])
  const [state, dispatch] = useReducer(sessionsReducer, undefined, loadSessions)
  const [formCollapsed, setFormCollapsed] = useState(false)
  const [prefill, setPrefill] = useState<SubjectProperty | null>(null)
  const [now, setNow] = useState(() => Date.now())

  const [methodology, setMethodology] = useState<Methodology | null>(null)

  useEffect(() => {
    fetchCommunities().then(setCommunities).catch(console.error)
    fetchMethodology().then(setMethodology).catch(console.error)
  }, [])

  useEffect(() => { persistSessions(state) }, [state])

  const anyRunning = state.order.some(id => state.byId[id].run.phase === 'running')
  useEffect(() => {
    if (!anyRunning) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [anyRunning])

  // One evaluation = one session. The SSE stream dispatches against the captured
  // id, so runs continue while another session is on screen.
  const startRun = (subject: SubjectProperty,
                    opts?: { whatIfOf?: string; nameSuffix?: string }) => {
    const id = crypto.randomUUID()
    const session: Session = {
      id,
      name: (subject.address || `${subject.community} · ${subject.property_type}`)
        + (opts?.nameSuffix ?? ''),
      createdAt: Date.now(),
      subject,
      run: { ...INITIAL_RUN, phase: 'running' },
      qa: [],
      seenDone: true,
      whatIfOf: opts?.whatIfOf,
    }
    dispatch({ type: 'create', session })
    setFormCollapsed(true)
    evaluate(subject, ev => dispatch({ type: 'run-event', id, action: ev }))
      .catch(err => dispatch({
        type: 'run-event', id, action: { type: 'fail', message: String(err) },
      }))
  }

  // Local save first, then fire-and-forget to the durable log: each line carries
  // the valuation as displayed at rating time, so it's self-contained later.
  const submitFeedback = (s: Session,
                          fb: { rating: number; comment: string; userEstimate?: number }) => {
    dispatch({ type: 'feedback', id: s.id, feedback: { ...fb, at: Date.now() } })
    const v = s.run.valuation
    postFeedback({
      session_id: s.id,
      rating: fb.rating,
      comment: fb.comment,
      user_estimate: fb.userEstimate ?? null,
      snapshot: {
        subject: s.subject,
        estimate: v?.estimate ?? null,
        low: v?.low ?? null,
        high: v?.high ?? null,
        confidence: v?.confidence ?? null,
        comps: s.run.comps.map(c => ({ address_key: c.comp.address_key, score: c.score })),
        flags: (v?.flags ?? []).map(f => f.code),
      },
    })
  }

  const active = state.activeId ? state.byId[state.activeId] : null

  return (
    <div className="p-4">
      <header className="mb-4 flex items-baseline justify-between">
        <h1 className="text-xl font-bold text-stone-800">
          home-evaluator
          <span className="ml-2 text-sm font-normal text-stone-400">
            comp-analysis agent · synthetic Calgary data
          </span>
        </h1>
      </header>

      <div className="grid gap-4 lg:h-[calc(100vh-6.5rem)] lg:grid-cols-[20rem_15rem_1fr] lg:grid-rows-[minmax(0,1fr)]">
        <div className="min-h-0 overflow-y-auto">
          <SubjectForm
            communities={communities} disabled={false}
            collapsed={formCollapsed} onToggle={() => setFormCollapsed(c => !c)}
            onSubmit={startRun} prefill={prefill}
          />
        </div>
        <div className="min-h-0 overflow-y-auto">
          <SessionList sessions={state} now={now}
            onSelect={id => dispatch({ type: 'select', id })} />
        </div>

        {active ? (
          <div className="flex min-h-0 flex-col gap-3">
            {active.run.phase === 'error' && (
              <div className="shrink-0 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {active.run.error}
              </div>
            )}
            <div className="shrink-0">
              <div className="mb-1 flex justify-end">
                <button
                  type="button"
                  title="copy this session's subject into the form to tweak and re-evaluate"
                  className="text-xs font-medium text-orange-700 hover:underline"
                  onClick={() => {
                    setPrefill({ ...active.subject }) // fresh object so the effect re-fires
                    setFormCollapsed(false)
                  }}
                >
                  ✎ edit in form
                </button>
              </div>
              <HeroCard session={active} now={now} methodology={methodology} />
            </div>
            {active.run.phase === 'done' && active.run.valuation && (
              <div className="shrink-0">
                <FeedbackStrip session={active}
                  onSubmit={fb => submitFeedback(active, fb)} />
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-y-auto pr-1">
              <Transcript session={active} />
            </div>
            <ChatInput
              session={active}
              onMessage={(id, role, text) =>
                dispatch({ type: 'qa', id, msg: { role, text, ts: Date.now() } })}
              onWhatIf={(parent, modified, label) =>
                startRun(modified, {
                  whatIfOf: parent.id,
                  nameSuffix: ` (what-if: ${label.slice(0, 32)})`,
                })}
              onRevalue={(id, valuation) =>
                dispatch({ type: 'revalue', id, valuation })}
            />
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-stone-300 p-8 text-center text-sm text-stone-400">
            Fill the form (or take a preset) and hit Evaluate — each home becomes a
            session: watch the agent search, review and value it live, then ask
            follow-up questions.
          </div>
        )}
      </div>
    </div>
  )
}
