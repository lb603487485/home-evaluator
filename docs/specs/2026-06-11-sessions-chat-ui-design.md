# Sessions + Chat-Hybrid UI + Address Intake — design addendum

**Date:** 2026-06-11 · **Status:** approved (Bo, 7:04 PM EDT, via brainstorm with browser mockups, design v3)
**Parent spec:** `2026-06-10-comp-analysis-agent-design.md` — everything there stands unless named here.

## 1. Why

Bo's asks after using the shipped UI: (1) intake a detailed address, with the community derived
from it; (2) better UI; (3) results that lead with the key factors; (4) a chat-like feel —
settled as a hybrid; plus two requirements added during design: one session per home with
follow-up Q&A ("memory"), and visible evaluation timestamps. Background runs: a user can leave
a session mid-evaluation and return to the finished result.

## 2. What does not change

- `backend/engine/`: untouched. Graph structure: unchanged (the only node edit is the intake
  signal-mining check learning about the address field, §5). Eval numbers (MAPE 2.2%, 20/20
  ±10%) remain valid; we rerun once anyway as a guard.
- The guardrail: the LLM never produces a number the engine didn't compute — extended to the
  new Q&A and what-if surfaces.
- Single-shot pipeline. No multi-turn intake loop. The form remains the input contract
  (free-text chat intake rejected: less credible for lending, ~4–6h, new failure modes).
- Stateless backend across runs. Session memory lives client-side and is sent with each
  follow-up question.

## 3. UX design (approved mockup v3)

**Layout.** Left column: subject form on top (collapses to a slim bar while a run is active),
scrollable newest-first **session list** below — each entry a digest: address/name ·
`$712k · A · 6:42 PM`, or `⏳ reviewing comps… 23s`, or a green `done ●` badge if it finished
while not being viewed. Right pane: the active session.

**Session pane.** Pinned at top: a slim progress strip while running, which becomes the
**hero valuation card** when the valuation lands:

- Subject recap line: address · community · type · beds/baths · sqft · **built YYYY** · garage
- Estimate (large) · confidence badge · P25–P75 range
- **Key factors** one-liner: comps kept · radius/days used · price spread % · largest adjustment
- Risk flags as full sentences (not tooltips)
- `Evaluated <date time> · comps as-of <date> · run took <N>s`
- Expandable: comp table (gains an **Adjusted $** column) + adjustment ladders + provenance,
  as today

Below the pinned card, the **transcript** scrolls: the submitted subject as a user message
(digest includes "built YYYY" and notes), agent progress as friendly messages derived from
existing SSE events, the narrative streaming as the agent's closing message, then Q&A.
Event→message mapping: `node` + `search_update` → search/widen lines with criteria and reasons;
`reviews` → "kept N, demoted M (reason)"; `narrative_delta` → streamed message. If exclusion
counts aren't already in an event payload, add an additive `exclusions` summary field to the
`comps` event (non-breaking).

**Chat input** under the transcript, enabled when the run is `done`: "Ask about this
evaluation…".

## 4. Sessions & background runs (frontend)

- A session manager owns one reducer state per session id (today's reducer, lifted out of the
  component). SSE streams dispatch into the store regardless of which session is displayed —
  switching never interrupts a run; multiple runs can be in flight.
- Completed sessions persist to localStorage (cap ~30, newest kept). Known limit, stated in
  README: a full browser refresh kills in-flight runs (finished ones survive); the production
  fix is server-side run state, not built now.
- What-if sessions carry a `whatIfOf` link and a derived name:
  `"310 Evanston Dr (what-if: +finished bsmt)"`.

## 5. Address intake

- `SubjectProperty` gains `address: str = ""` (optional, passthrough). It is echoed in the
  form, transcript digest, hero recap, and narrative context. It **never feeds the engine** —
  community + attributes remain the only inputs to the math.
- **Community auto-fill** (deterministic, no LLM): case-insensitive containment match of the
  typed address against the community names from `GET /api/communities`; on match the dropdown
  auto-selects, stays editable.
- **Wrong address handling:**

| Case | Behavior |
|---|---|
| Address names community X, dropdown says Y | Inline form warning before submit; intake node extends its existing contradiction check to address-vs-community → signal surfaces in transcript + flags. Evaluation runs; **the dropdown is the authority** |
| No community recognized ("123 Fake St", typos) | No auto-fill; user selects manually; address rides along as a label only |
| Plausible but wrong house | Undetectable by design anywhere; mitigated by echoing the address prominently in three places |

- Production note for README: geocoder validates address → lat/lon → feeds the **existing**
  haversine distance filter (`engine/filters.py`); zero engine changes.

## 6. Follow-up Q&A + what-if re-runs

New endpoint, not a graph node (single LLM call): **`POST /api/ask`**

- Request: `{ question, history: [{role, text}], context }` where `context` is the session's
  result bundle (subject, valuation, scored comps, reviews, risk flags, search log,
  notes signals, narrative). Backend stays stateless.
- Response (JSON, non-streamed):
  - `{ "type": "answer", "text": … }` — grounded in context numbers only, or
  - `{ "type": "what_if", "text": …, "modified_subject": SubjectProperty }` — only the fields
    the user named may differ; the **field diff is computed in code** server-side (never
    trusted from the LLM) and returned as `changes: [{field, from, to}]`.
- Frontend on `what_if`: render the diff chip in the transcript, spawn a linked session with
  `modified_subject`, run the normal `/api/evaluate` flow. A what-if is a full audited
  evaluation — never an LLM-adjusted number.
- Prompt: `backend/agent/prompts/ask.md`. Model: `ASK_MODEL` env, default Sonnet. Token cap.
  TODAY injected (per the as-of-date rule). LLM failure → `{"type":"answer"}` apology text,
  HTTP 200 — degrade, never 500 (house convention).

## 7. Time boxes & cut ladder

Budget after the design block: 4.5h logged of 12h cap → 5.5h build + 2.0h reserve remain;
video keeps its protected 1.5h. Boxes are set at observed velocity (T0–T10 ran 5–10× under
spec estimates), with the conservative risk absorbed by the ladder, not the boxes:

| Block | Box |
|---|---|
| F1 address field + auto-fill + warnings + intake cross-check + tests | 0.5h |
| F2 sessions + background runs + transcript + hero card + comp-table column | 1.25h |
| F3 `/api/ask` + Q&A UI + what-if spawn + tests | 0.75h |
| F4 verify (live script + eval rerun) + README/demo-notes updates | 0.5h |
| **Total** | **3.0h** |

Cut ladder, invoked in order the moment a box blows:
1. What-if execution → answer pre-fills the form and says "press Evaluate" (keep Q&A answers)
2. Drop `/api/ask` entirely — sessions, transcript, hero, address still ship
3. localStorage persistence → sessions live until refresh
4. Form collapse → form just stays put

## 8. Verification

- **pytest:** address passthrough + presence in narrative context; intake address-vs-community
  signal (fake LLM); `/api/ask` answer and what_if branches (fake LLM); diff computation;
  `modified_subject` validates; LLM-failure fallback returns 200.
- **Live script:** two concurrent sessions; switch away mid-run and return (done badge);
  refresh (completed sessions survive); mismatch warning; what-if end-to-end (diff chip →
  linked session → result); timestamps + duration visible.
- **Eval guard:** `uv run python -m eval.eval` — expect identical results (engine untouched).
