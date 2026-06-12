# Sessions + Chat-Hybrid UI + Address Intake — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-home evaluation sessions with a chat-style transcript, pinned hero valuation card, address intake with community auto-fill, and follow-up Q&A with what-if re-runs — per `docs/specs/2026-06-11-sessions-chat-ui-design.md`.

**Architecture:** Engine and graph untouched (one intake-prompt line added). Backend grows one optional schema field and one stateless `/api/ask` endpoint. The frontend reducer is lifted into a multi-session store keyed by session id; SSE streams dispatch into the store regardless of which session is visible. Transcript/hero render from the same RunState the reducer already builds.

**Tech Stack:** FastAPI + pydantic + LangChain (existing `agent/llm.py` helpers) · Vite/React/TS/Tailwind v4 · pytest with `AGENT_NO_LLM=1` + fake models.

**Time boxes (strict, cut ladder in spec §7):** F1 0.5h · F2 1.25h · F3 0.75h · F4 0.5h. Stretch S1–S3 only after F4, in order.

---

## Resume protocol (mid-task interruption / usage-limit stop)

This plan is the single source of truth for progress. Rules while executing:

1. **Tick checkboxes in THIS file** (`- [ ]` → `- [x]`) the moment a step completes, and
   **commit the plan file together with each task's code commit** — progress tracking is
   never left uncommitted.
2. **Append one line to the Execution Log** (bottom of this file) at every task boundary and
   whenever something surprising happens: what landed, what's mid-flight, exact next action.
3. **Never leave a task half-done at a known stopping point** — finishing the current *step*
   and committing beats starting the next one.

**To resume in a fresh session:** read this file top-to-bottom (checkboxes + Execution Log),
then `git log --oneline -10` (each task = one commit, messages quoted in the steps),
`git status && git diff` (any WIP past the last commit), and re-establish green:
`cd backend && uv run pytest -q` · `cd frontend && npx tsc -b --noEmit`. The first unticked
checkbox is the next action. Spec: `docs/specs/2026-06-11-sessions-chat-ui-design.md`.
Time accounting continues in `TIMELOG.md` (block boundaries, usage-gap time excluded).

---

## F1 — Address intake

### Task 1: `address` on SubjectProperty + intake cross-check line

**Files:**
- Modify: `backend/data/schema.py:44-53` (SubjectProperty)
- Modify: `backend/agent/prompts/intake.md`
- Test: `backend/tests/test_schema.py` (append)

- [x] **Step 1: Failing test** — append to `backend/tests/test_schema.py`:

```python
def test_subject_address_optional_passthrough():
    from data.schema import SubjectProperty
    s = SubjectProperty(community="Evanston", property_type="detached", beds=3,
                        baths=2.5, sqft=1850, year_built=2020)
    assert s.address == ""
    s2 = s.model_copy(update={"address": "310 Evanston Dr NW"})
    assert "310 Evanston Dr NW" in s2.model_dump_json()
```

- [x] **Step 2: Run** `cd backend && uv run pytest tests/test_schema.py -k address -x` → FAIL (no field `address`).

- [x] **Step 3: Implement** — in `backend/data/schema.py` add one line to `SubjectProperty` after `community: str`:

```python
class SubjectProperty(BaseModel):
    community: str
    address: str = ""  # display + cross-check only; never feeds the engine math
    property_type: str
    ...
```

(No other backend change needed for passthrough: `intake_node` already sends `subject.model_dump_json()` to the LLM, and `narrate._data_block` already sends `state["subject"].model_dump()` — the address rides along automatically.)

- [x] **Step 4:** `uv run pytest tests/test_schema.py -x` → PASS.

- [x] **Step 5: Intake prompt cross-check** — append to `backend/agent/prompts/intake.md`:

```markdown
- If SUBJECT.address names a community different from SUBJECT.community, add a
  concern: "address mentions <X> but community is <Y>". The form's community field
  is authoritative; never suggest changing it.
```

- [x] **Step 6: Full backend suite + commit**

```bash
uv run pytest -q   # expect 85 pass
git add data/schema.py agent/prompts/intake.md tests/test_schema.py
git commit -m "feat: optional subject address — schema passthrough + intake cross-check"
```

### Task 2: Address field + community auto-fill + mismatch warning (frontend)

**Files:**
- Modify: `frontend/src/types.ts:3-13` (add `address: string` to SubjectProperty)
- Modify: `frontend/src/components/SubjectForm.tsx`

- [x] **Step 1:** `types.ts` — add `address: string` after `community` in `SubjectProperty`.

- [x] **Step 2:** `SubjectForm.tsx` — add `address: ''` to every `PRESETS` entry (give 'Evanston detached' `address: '310 Evanston Dr NW'` so the demo auto-fill fires). Add above the Community label:

```tsx
const matched = communities.find(c =>
  subject.address.toLowerCase().includes(c.community.toLowerCase()))?.community
const mismatch = matched && matched !== subject.community

// in JSX, before the Community label:
<label className={label}>Address (optional)</label>
<input type="text" className={field} value={subject.address} disabled={disabled}
  placeholder="e.g. 310 Evanston Dr NW"
  onChange={e => {
    const address = e.target.value
    const hit = communities.find(c =>
      address.toLowerCase().includes(c.community.toLowerCase()))
    set(hit ? { address, community: hit.community } : { address })
  }} />
{mismatch && (
  <p className="mt-1 text-xs text-amber-600">
    ⚠ address mentions <b>{matched}</b> — community is set to <b>{subject.community}</b>
  </p>
)}
```

Note: auto-fill must also keep `property_type` valid — reuse the same logic as the community `<select>` `onChange` (if the new community's types don't include the current type, switch to its first type).

- [x] **Step 3: Verify** — `cd frontend && npx tsc -b --noEmit` → clean. Manual: typing "12 Tuscany Hills Rd NW" flips the dropdown to Tuscany; then choosing Evanston manually shows the amber warning.

- [x] **Step 4: Commit** — `git commit -am "feat: address input with community auto-fill + mismatch warning"`

**F1 box check (0.5h).** Over → cut ladder step 4 is not relevant here; simply ship Task 1 only (backend field) and move on.

---

## F2 — Sessions, background runs, transcript, hero card

### Task 3: Session store (multi-run state + localStorage)

**Files:**
- Create: `frontend/src/sessions.ts`
- Modify: `frontend/src/App.tsx` (gutted: store moves out, layout changes in Task 5)

`sessions.ts` — the existing `reducer` from `App.tsx:32-76` moves here verbatim as `runReducer` (same `RunState`/`Action` types, plus two additions: store `lastSearch` on `search_update` and `exclusions` on `comps` — see Task 4 backend note). Wrapped in a sessions-level reducer:

```ts
import type { ScoredComp, ReviewVerdict, AdjustedComp, ValuationPayload,
  SubjectProperty, AgentEvent, SearchUpdate } from './types'

export interface ChatMsg { role: 'user' | 'agent'; text: string; ts: number }

export interface Session {
  id: string
  name: string                      // address if set, else "community · type"
  createdAt: number
  evaluatedAt?: number              // set on 'done'
  subject: SubjectProperty
  run: RunState                     // existing shape + lastSearch?: SearchUpdate
  qa: ChatMsg[]
  seenDone: boolean                 // false ⇒ green "done ●" badge in the list
  whatIfOf?: string                 // parent session id for what-if spawns
}

export interface SessionsState {
  order: string[]                   // newest first
  byId: Record<string, Session>
  activeId: string | null
}

export type SessionsAction =
  | { type: 'create'; session: Session }
  | { type: 'select'; id: string }
  | { type: 'run-event'; id: string; action: RunAction }   // RunAction = old Action
  | { type: 'qa'; id: string; msg: ChatMsg }

export function sessionsReducer(s: SessionsState, a: SessionsAction): SessionsState
```

`run-event` routes through `runReducer` for `byId[a.id].run`; on a `done` event it also stamps `evaluatedAt: Date.now()` and `seenDone: activeId === a.id`. `select` marks the target's `seenDone = true`. Persistence (same file):

```ts
const KEY = 'home-evaluator-sessions-v1'
export function loadSessions(): SessionsState        // try/catch JSON.parse, else empty
export function persistSessions(s: SessionsState)    // keep newest 30 sessions whose
                                                     // run.phase === 'done' | 'error'
```

`App.tsx` calls `persistSessions` in a `useEffect` on state change. Background continuation works because `run(subject)` captures the session id in its closure: `evaluate(subject, ev => dispatch({ type: 'run-event', id, action: ev }))` — the stream dispatches no matter which session is displayed.

- [x] **Step 1:** Write `sessions.ts` as above (move + extend reducer).
- [x] **Step 2:** `npx tsc -b --noEmit` → clean (App.tsx still compiles using the moved types).
- [x] **Step 3:** Commit — `"refactor: lift run reducer into multi-session store with persistence"`

### Task 4: Exclusions in the comps event (backend, additive)

**Files:**
- Modify: `backend/app/api.py:64-65` (score branch)
- Modify: `frontend/src/types.ts` (comps event payload)
- Test: `backend/tests/test_api.py` (append)

- [x] **Step 1: Failing test:**

```python
async def test_comps_event_carries_exclusions(client):
    r = await client.post("/api/evaluate", json=SUBJECT)
    text = r.text
    comps_data = next(l for l in text.splitlines()
                      if l.startswith("data:") and '"exclusions"' in l)
    assert comps_data  # additive field present on the comps event
```

- [x] **Step 2:** Run it → FAIL. **Implement** in `api.py` score branch:

```python
elif node == "score":
    yield node_event("search", "done")
    yield sse_event("comps", {
        "items": [s.model_dump(mode="json") for s in delta["scored"]],
        "exclusions": delta.get("exclusions") or []})
```

- [x] **Step 3:** `uv run pytest tests/test_api.py -x` → PASS. Update `types.ts` comps event: `{ type: 'comps'; data: { items: ScoredComp[]; exclusions?: { address_key: string; reason: string }[] } }`; store them in `RunState`. Commit — `"feat: exclusion summaries on comps event (additive)"`

### Task 5: Layout + SessionList + Transcript + HeroCard

**Files:**
- Create: `frontend/src/components/SessionList.tsx`
- Create: `frontend/src/components/Transcript.tsx`
- Create: `frontend/src/components/HeroCard.tsx`
- Modify: `frontend/src/App.tsx` (new layout), `frontend/src/components/CompTable.tsx` (Adjusted $ column + similarity breakdown), `frontend/src/components/SubjectForm.tsx` (collapsible)
- Delete usage (not file): `AgentTimeline`, `ValuationBanner` imports from App

**App layout** (replaces `App.tsx:111-133`):

```tsx
<div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
  <div className="space-y-3">
    <SubjectForm communities={communities} collapsed={formCollapsed}
      onToggle={() => setFormCollapsed(c => !c)} disabled={false} onSubmit={startRun} />
    <SessionList sessions={state} onSelect={id => dispatch({ type: 'select', id })} />
  </div>
  {active ? <SessionPane session={active} ... /> : <IdlePlaceholder />}
</div>
```

`startRun` creates the session (id `crypto.randomUUID()`, name from address || `${community} · ${property_type}`), dispatches `create` + `select`, collapses the form, and starts `evaluate()` with the closure-captured id. The form is **never disabled** (multiple concurrent runs allowed); `collapsed` renders just a `▸ Subject form` header bar.

**SessionList** — one entry per `order`: name (truncate), digest line: `cad.format(estimate) · confidence · h:mm` when done; `⏳ <last timeline text trimmed>… ${elapsed}s` when running (elapsed via 1s `setInterval` tick); green `done ●` badge when `!seenDone && phase==='done'`; amber border on `phase==='error'`; `(what-if)` suffix when `whatIfOf`. Active entry: indigo border.

**SessionPane** (inside App.tsx, small): vertical flex — `HeroCard` (or progress strip) pinned, then `Transcript` (scrolls), then `ChatInput` (Task 7; placeholder div until then).

**HeroCard** (`HeroCard.tsx`) — props `{ session }`. While `run.phase === 'running'`: slim strip `⏳ {last timeline item} · {elapsed}s`. When `run.valuation` with non-null estimate:

- Subject recap: `{address && address + ' · '}{community} · {property_type} · {beds} bd / {baths} ba · {sqft} sqft · built {year_built}{garage_stalls ? ' · ' + garage_stalls + ' garage' : ''}`
- Estimate (text-2xl font-extrabold) · confidence pill (reuse colors from `ValuationBanner.tsx:32-37`) · `range {cad(low)} – {cad(high)}`
- **Key factors** line, computed:

```ts
const kept = valuation.adjustments ?? []
const spreadPct = valuation.low && valuation.estimate
  ? Math.round(1000 * (valuation.high! - valuation.low!) / valuation.estimate!) / 10 : null
const largest = kept.flatMap(a => Object.entries(a.adjustments))
  .reduce((m, [k, v]) => Math.abs(v) > Math.abs(m[1]) ? [k, v] : m, ['', 0])
const c = run.lastSearch?.criteria
// → "{kept.length} comps kept · within {c.radius_km} km / {c.days} days
//    · spread {spreadPct}% · largest adjustment: {largest[0]} {cad(largest[1])}"
```

- Flags as full sentences: reuse `FlagChips` but always render the message list (drop the title-only pills behavior — pass a `verbose` prop).
- Timestamps: `Evaluated {new Date(evaluatedAt).toLocaleString()} · comps as-of {date} · run took {totalS}s`
- `▸ show {n} comps + adjustment ladders` toggle → renders existing `<CompTable …/>` inline.

Null-estimate case: keep `ValuationBanner.tsx:13-22`'s message ("No usable comparable sales…") inside the card.

**Transcript** (`Transcript.tsx`) — props `{ session }`. Renders, in order:

1. User bubble (right-aligned, `bg-blue-100 rounded-2xl rounded-br-sm`): `📋 {subject recap} · "{notes}"` + time.
2. Agent bubbles (left, white border) derived from `run.timeline` + stored data — friendly mapping (pure function `transcriptLines(run): string[]` in the same file):
   - `intake: done — sig1, sig2` → `Noted: sig1, sig2.` (skip if no detail)
   - `search_update` (use stored `lastSearch`/timeline search items) → `Searching {community} — {radius_km} km, last {days} days… found {found}.`
   - widen items → `Widening the search: {reason}`
   - `exclusions.length > 0` → `Excluded {n}: {reasons joined}.`
   - reviews complete → `Reviewed {total}: kept {keeps}, demoted {demotes}, excluded {excludes}.`
   - fallback items keep the amber `fallback` badge treatment from `AgentTimeline.tsx:24-31`.
3. Narrative as one agent bubble with `react-markdown` (reuse `NarrativePanel` internals — render `<NarrativePanel narrative={…} streaming={…}/>` inside a bubble shell, heading removed via prop).
4. `qa` messages as user/agent bubbles (Task 7 fills them).

**CompTable** — two edits: add `Adjusted $` column after `Sold` (value `adjustments[address_key]?.adjusted_price`, em-dash when absent); in the expanded row's left pane, above the ladder, render the breakdown that's currently only a tooltip (`CompTable.tsx` similarity cell `title`): `score_parts` as small `dim: pts` chips.

- [x] **Step 1:** Write `SessionList.tsx`, `HeroCard.tsx`, `Transcript.tsx`; rewire `App.tsx`; edit `CompTable.tsx`, `SubjectForm.tsx` (collapse prop).
- [x] **Step 2:** `npx tsc -b --noEmit` → clean.
- [x] **Step 3: Live check** (backend on :8000, `npm run dev`): run the Evanston preset → transcript builds, hero appears with key factors + timestamps; start a Bearspaw run, switch to Evanston mid-run, switch back → Bearspaw finished with `done ●` badge having appeared in the list; reload page → both sessions still listed and openable.
- [x] **Step 4:** Commit — `"feat: per-home sessions with background runs, chat transcript, pinned hero valuation card"`

**F2 box check (1.25h).** Over → cut ladder: (3) drop localStorage (skip `loadSessions`/`persistSessions`), (4) drop form collapse.

---

## F3 — `/api/ask`: Q&A + what-if

### Task 6: Backend endpoint

**Files:**
- Create: `backend/agent/prompts/ask.md`
- Modify: `backend/agent/llm.py` (add `"ask"` to the per-node model defaults map, default Sonnet — same pattern as the existing `narrate` entry)
- Modify: `backend/app/api.py` (new route + request model)
- Test: `backend/tests/test_ask.py`

`prompts/ask.md`:

```markdown
You are the appraisal assistant for a completed comparable-sales evaluation.
Answer questions about THIS evaluation only, grounded in the CONTEXT JSON.
Hard rules:
- Never state a number that is not present in CONTEXT (you may restate/round them).
- If asked something CONTEXT cannot answer, say so plainly.
- If the user proposes a CHANGE to the subject property ("what if …"), do NOT
  estimate the effect. Return a what_if with the full modified subject: copy
  CONTEXT.subject and change ONLY the fields the user explicitly named
  (free-text traits like "finished basement" go into notes, appended).
Reply with a single JSON object, nothing else:
  {"type": "answer", "text": "..."}
  or {"type": "what_if", "text": "<one line saying you'll re-evaluate>",
      "modified_subject": { ...full SubjectProperty... }}
```

`api.py` additions:

```python
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
    history: list[dict] = []          # [{role, text}] prior Q&A, oldest first
    context: dict                     # session bundle, see test below

class SubjectChange(BaseModel):
    field: str
    before: object
    after: object

@router.post("/ask")
async def ask(req: AskRequest) -> dict:
    from datetime import date
    from agent import llm
    if not llm.llm_enabled():
        return {"type": "answer",
                "text": "Follow-up answers need the LLM (set ANTHROPIC_API_KEY)."}
    try:
        history = "\n".join(f"{m['role']}: {m['text']}" for m in req.history[-6:])
        message = await llm.get_model("ask", max_tokens=700).ainvoke([
            ("system", llm.load_prompt("ask")),
            ("user", f"TODAY: {date.today()}\n\nCONTEXT:\n"
                     f"{json.dumps(req.context, default=str)}\n\n"
                     f"PRIOR Q&A:\n{history or '(none)'}\n\n"
                     f"QUESTION: {req.question}")])
        data = llm.parse_json_block(llm.message_text(message.content))
        if data.get("type") != "what_if":
            return {"type": "answer", "text": str(data.get("text", ""))}
        modified = SubjectProperty(**data["modified_subject"])
        original = SubjectProperty(**req.context["subject"])
        changes = [SubjectChange(field=f, before=getattr(original, f),
                                 after=getattr(modified, f)).model_dump()
                   for f in SubjectProperty.model_fields
                   if getattr(original, f) != getattr(modified, f)]
        if not changes:
            return {"type": "answer", "text": str(data.get("text", ""))}
        return {"type": "what_if", "text": str(data.get("text", "")),
                "modified_subject": modified.model_dump(), "changes": changes}
    except Exception as exc:
        return {"type": "answer",
                "text": f"(assistant unavailable — {exc}; the tables above stand)"}
```

(`import json` at top of `api.py`. The diff is computed in code from the validated models — never trusted from the LLM, per spec §6.)

- [x] **Step 1: Failing tests** — `backend/tests/test_ask.py`, fake-model pattern from `tests/test_llm_nodes.py` (monkeypatch `agent.llm.get_model` / `llm_enabled`):

```python
import os
os.environ["AGENT_NO_LLM"] = "1"
import httpx, pytest
from app.main import app

CONTEXT = {"subject": dict(community="Evanston", property_type="detached", beds=3,
                           baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                           garage_stalls=2, notes="", address=""),
           "valuation": {"estimate": 712000}}

@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

async def test_ask_no_llm_degrades_to_200(client):
    r = await client.post("/api/ask", json={"question": "why A?", "context": CONTEXT})
    assert r.status_code == 200 and r.json()["type"] == "answer"

async def test_ask_what_if_diff_computed_in_code(client, monkeypatch):
    from agent import llm
    class Fake:
        async def ainvoke(self, _):
            class M: content = ('{"type": "what_if", "text": "re-running",'
                                '"modified_subject": ' + __import__("json").dumps(
                                    {**CONTEXT["subject"], "sqft": 2400}) + '}')
            return M()
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: Fake())
    r = await client.post("/api/ask", json={"question": "what if 2400 sqft?",
                                            "context": CONTEXT})
    body = r.json()
    assert body["type"] == "what_if"
    assert body["changes"] == [{"field": "sqft", "before": 1850, "after": 2400}]

async def test_ask_llm_error_degrades(client, monkeypatch):
    from agent import llm
    class Boom:
        async def ainvoke(self, _): raise RuntimeError("kaput")
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    monkeypatch.setattr(llm, "get_model", lambda *a, **k: Boom())
    r = await client.post("/api/ask", json={"question": "?", "context": CONTEXT})
    assert r.status_code == 200 and "unavailable" in r.json()["text"]
```

- [x] **Step 2:** Run → FAIL (404). **Implement** as above (+ `ask.md`, + llm.py default). Run → PASS.
- [x] **Step 3:** Full suite `uv run pytest -q` → all green. Commit — `"feat: /api/ask — grounded Q&A + what-if with code-computed subject diff"`

### Task 7: Chat input + what-if spawn (frontend)

**Files:**
- Modify: `frontend/src/api.ts` (add `ask()`)
- Create: `frontend/src/components/ChatInput.tsx`
- Modify: `frontend/src/App.tsx` (wire into SessionPane), `frontend/src/sessions.ts` (qa action already exists)

`api.ts`:

```ts
export async function ask(body: {
  question: string
  history: { role: string; text: string }[]
  context: unknown
}): Promise<{ type: 'answer' | 'what_if'; text: string;
              modified_subject?: SubjectProperty;
              changes?: { field: string; before: unknown; after: unknown }[] }> {
  const res = await fetch('/api/ask', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!res.ok) throw new Error(`ask: HTTP ${res.status}`)
  return res.json()
}
```

`ChatInput` — text input + send, disabled unless `run.phase === 'done'` (placeholder "Ask about this evaluation…", while running: "available when the evaluation finishes"). On send: push user `ChatMsg`, call `ask()` with context bundle built from the session:

```ts
const context = {
  subject: s.subject, valuation: s.run.valuation,
  comps: s.run.comps.map(c => ({ address: c.comp.address, score: c.score,
    sold_price: c.comp.sold_price, sold_date: c.comp.sold_date })),
  reviews: Object.values(s.run.reviews), exclusions: s.run.exclusions,
  search_log: s.run.lastSearch, narrative: s.run.narrative,
}
```

On `answer`: push agent ChatMsg. On `what_if`: push agent ChatMsg of `text` + a diff chip line (`changes.map(c => \`${c.field}: ${c.before} → ${c.after}\`).join(' · ')`), then call the same `startRun(modified_subject, { whatIfOf: s.id, nameSuffix: ' (what-if)' })` used by the form — the spawn IS a normal evaluation session. On fetch error: push agent ChatMsg "(request failed — try again)".

- [x] **Step 1:** Implement; `npx tsc -b --noEmit` clean.
- [x] **Step 2: Live check** (needs `ANTHROPIC_API_KEY` in `backend/.env`): ask "why this confidence grade?" → grounded answer cites the comp count/spread from context. Ask "what if it were 2400 sqft?" → diff chip + linked session appears and runs.
- [x] **Step 3:** Commit — `"feat: per-session follow-up chat with what-if spawned re-evaluations"`

**F3 box check (0.75h).** Over → cut ladder: (1) drop the what-if branch frontend handling (render it as a plain answer + tell the user to edit the form), (2) drop ChatInput entirely.

---

## F4 — Verification + docs

- [x] **Step 1:** `cd backend && uv run pytest -q` → all green (expect ~90).
- [x] **Step 2:** `uv run python -m eval.eval` → identical table to `backend/eval/results.md` (engine untouched).
- [x] **Step 3:** Live script (servers up, browser): ① Evanston preset → transcript + hero card (key factors, flags as sentences, evaluated-at + duration, built-year in recap). ② Start Bearspaw, switch away mid-run, return on `done ●`. ③ Reload → done sessions survive. ④ Address "12 Tuscany Hills Rd NW" → auto-fill; force mismatch → amber warning; submit → intake concern appears in transcript. ⑤ Q&A grounded answer. ⑥ What-if → diff chip → linked session result. Screenshot ①+⑥ → `docs/images/`.
- [x] **Step 4:** README: update UI section + screenshots; add production notes (geocoder → existing haversine filter; server-side run state for refresh-proof in-flight runs; sign-off backstop note). Update `docs/demo-notes.md` §1 (transcript/what-if video beats) + §3; `TIMELOG.md` rows per block.
- [x] **Step 5:** Commit — `"docs: README + demo notes for sessions/chat/address UX"`

---

## Stretch (only after F4; spec §8 designs govern; stop when the clock says)

### S1 — Comp challenge → agent re-review (1.0h box)

**Files:** `backend/app/api.py` (extend `/api/ask`), `backend/agent/nodes/review.py` (reuse its single-comp review fn), `backend/engine/valuation.py` (already-pure recompute fn), `frontend` ChatInput handling, `backend/tests/test_ask.py`.

Mechanic: `ask.md` gains a third reply shape `{"type": "comp_challenge", "address_key": "...", "claim": "..."}` (only when the user disputes a specific comp). Backend: re-run the review-node LLM call for that comp with `claim` appended to the signals; if the verdict becomes exclude/demote, recompute `valuate(kept_minus, …)` via the existing pure functions on adjusted comps from context, and return `{type: "comp_challenge", verdict, reason, revaluation: {estimate, low, high, confidence, flags}}`. Frontend: transcript logs challenge + outcome; hero card gets an "override applied — see chat" marker and the new numbers, original valuation retained in `run.valuation` history (`run.revaluations: []` appended, never mutated). Tests: fake-LLM agree-path (verdict flips, numbers change deterministically) and defend-path (verdict keep, numbers unchanged).

### S2 — Market-norm baseline divergence flag (0.5h box)

**Files:** `backend/engine/baseline.py` (new: `median_ppsf(records, property_type, today, days) -> float | None`, ≥5 sales guard), `backend/engine/risk_rules.py` (register `BASELINE_DIVERGENCE`, caution, tolerance ±15% in `engine/config.py`), `backend/agent/graph.py` valuate wiring passes candidates, `backend/tests/test_risk_rules.py`. Flag evidence: `{baseline, estimate, gap_pct, sample_n}`. UI: nothing — flags already render.

### S3 — ML calibration demo (0.75h box)

**Files:** `backend/eval/calibrate.py` (numpy `lstsq` hedonic fit on scorable records: price ~ sqft + beds + baths + garage + age + lot + days-ago), output markdown table fitted-vs-`config.ADJ` rates → `backend/eval/calibration.md`; optional eval rerun with fitted rates via env flag. README ML-roadmap section links the table.

---

## Self-review notes

- Spec §3–§6 requirements each map to Tasks 1–7; §5 table covered by Tasks 1–2; timestamps covered in Task 5 (HeroCard + SessionList); "comps as-of" renders the evaluated date (same-day snapshot — dataset is static).
- Types consistent: `Session.run` is the old `RunState` + `lastSearch` + `exclusions`; `startRun(subject, opts?)` is the single entry for form, presets, and what-if spawns.
- Known accepted limits (spec'd): in-flight runs die on full page reload; narrative not regenerated after re-review (S1) — marker + chat message instead.

---

## Execution Log

> One line per task boundary or surprise: timestamp · what landed · next action.

- 2026-06-11 19:55 — Plan written and committed. Next: Task 1 (backend address field, failing test first).
- 2026-06-11 20:00 — Task 1 done: subject.address field + intake cross-check prompt line, 86 tests green. Next: Task 2 (frontend address + auto-fill).
- 2026-06-11 20:05 — Task 2 done: address input + deterministic auto-fill + mismatch warning, tsc clean. F1 closed under box. Next: Task 3 (session store).
- 2026-06-11 20:12 — Task 4 done (pulled before Task 3 so types compile in one pass): exclusions on comps event (search-node accumulate, incomplete filtered, cap 20), 87 tests. Next: Task 3 sessions.ts.
- 2026-06-11 20:16 — Task 3 done: sessions.ts store (runReducer moved+extended, sessionsReducer, localStorage best-effort). App.tsx swaps over in Task 5. Next: Task 5 (layout + components).
- 2026-06-11 20:14 — Task 5 done: SessionList/HeroCard/Transcript + App rewire, CompTable adjusted-$ column + similarity chips, form collapse; orphaned AgentTimeline/ValuationBanner removed. Live-verified: auto-fill, mismatch warning, background run + done badge, reload persistence. Bonus fix: narrative double-emit in api.py (latent, LLM-on only). F2 well in box. Next: Task 6 (/api/ask).
- 2026-06-11 20:22 — Task 6 done: /api/ask (answer + what_if branches, code-computed diff, no-change demotes to answer, 200-on-failure), ask.md prompt, ASK default Sonnet. 92 tests. Next: Task 7 (ChatInput + what-if spawn).
- 2026-06-11 20:36 — Task 7 done: ChatInput + ask() client + what-if spawn. Live-verified: grounded confidence answer (cites conflicts + demoted comp score), what-if garage 2→3 spawned linked session, engine moved estimate +$10k, diff recorded in parent transcript. Also: persistSessions empty-state clobber guard. F3 in box. Next: F4 verify + docs.
- CORRECTION: Execution Log times for Tasks 5–7 above were wrong — a ~3h usage-limit gap hit at the Task-5 commit (20:10→23:05). Real times: Task 5 committed 23:25, Task 6 23:27, Task 7 23:32, F4 23:35–23:55. Resume protocol worked as designed.
- 2026-06-11 23:55 — F4 done: 93 tests, eval guard 20/20, intake address-only gap fixed live, screenshots, README/demo-notes/TIMELOG updated. F1–F4 COMPLETE (~1.0h actual vs 3.0h boxed). Next: stretch S1 (comp challenge → re-review) if Bo wants it.
- 2026-06-12 00:05 — S1 done (~0.3h vs 1.0h box): comp_challenge branch in /api/ask (reuses review_comp_node + new graph.apply_reviews + engine valuate/risk rules, all stateless), ask.md third shape w/ challenge-vs-question rule, frontend revalue action + hero ⚖ marker + original preserved. 96 tests. Live: highway challenge → exclude → revised card. Next: S2 baseline divergence rule.
