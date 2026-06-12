import { useEffect, useReducer, useState } from 'react'
import { evaluate, fetchCommunities } from './api'
import ChatInput from './components/ChatInput'
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
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    fetchCommunities().then(setCommunities).catch(console.error)
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

  const active = state.activeId ? state.byId[state.activeId] : null

  return (
    <div className="mx-auto max-w-6xl p-4">
      <header className="mb-4 flex items-baseline justify-between">
        <h1 className="text-xl font-bold text-slate-800">
          home-evaluator
          <span className="ml-2 text-sm font-normal text-slate-400">
            comp-analysis agent · synthetic Calgary data
          </span>
        </h1>
      </header>

      <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
        <div className="space-y-3">
          <SubjectForm
            communities={communities} disabled={false}
            collapsed={formCollapsed} onToggle={() => setFormCollapsed(c => !c)}
            onSubmit={startRun}
          />
          <SessionList sessions={state} now={now}
            onSelect={id => dispatch({ type: 'select', id })} />
        </div>

        {active ? (
          <div className="flex flex-col gap-3">
            {active.run.phase === 'error' && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {active.run.error}
              </div>
            )}
            <HeroCard session={active} now={now} />
            <Transcript session={active} />
            <ChatInput
              session={active}
              onMessage={(id, role, text) =>
                dispatch({ type: 'qa', id, msg: { role, text, ts: Date.now() } })}
              onWhatIf={(parent, modified, label) =>
                startRun(modified, {
                  whatIfOf: parent.id,
                  nameSuffix: ` (what-if: ${label.slice(0, 32)})`,
                })}
            />
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
            Fill the form (or take a preset) and hit Evaluate — each home becomes a
            session: watch the agent search, review and value it live, then ask
            follow-up questions.
          </div>
        )}
      </div>
    </div>
  )
}
