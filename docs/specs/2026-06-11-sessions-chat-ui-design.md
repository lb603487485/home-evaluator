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
  as today; the per-dimension similarity breakdown moves from hover-tooltip into the expanded
  row ("why this comp ranks here")

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

## 8. Stretch queue (approved 2026-06-11 evening; run only after F1–F4 land in box, in order, stop when the clock says)

| # | Item | Box | Design |
|---|---|---|---|
| S1 | **Comp challenge → agent re-review** | 1.0h | Third `/api/ask` response type, `comp_challenge`: the user disputes a comp in chat ("comp 3 backs onto a highway"); backend re-runs the **existing** review logic for that one comp with the claim appended as a signal. Agent agrees → existing engine recompute path (re-adjust, re-reconcile, regrade confidence, re-run risk rules), hero card updates, both challenge and reversal logged. Agent disagrees → keeps/demotes with stated reasons, objection recorded in the report. The human contributes evidence and challenge — never the number, never the verdict directly. (Replaces the rejected one-click override: a click that flips a verdict with no argument makes agent judgment decoration. Production note for README: licensed sign-off with mandatory written justification remains the legal backstop.) |
| S2 | **Market-norm baseline divergence flag** | 0.5h | New engine function: median $/sqft of recent same-type community sales × subject sqft. New registered risk rule: estimate diverging > tolerance from that yardstick → caution flag carrying both numbers; silent under a minimum sample (≥5 sales) so thin markets don't flag on noise. Labeled "market-norm baseline ($/sqft)" — never "AVM". Demonstrates the AVM-divergence seam honestly (README: production swaps the baseline for a GBM AVM on licensed solds; rule and wiring unchanged). A *trained* fake-AVM stays rejected: trained on our synthetic data it would just be the generator checking itself. |
| S3 | **ML calibration pipeline demo** | 0.75h | Fit hedonic regression (numpy lstsq, no new deps) on synthetic sales → table of fitted per-factor $ rates vs hand-set `engine/config.py` rates → optional eval rerun with fitted rates. Framed transparently: demonstrates the calibration *mechanism* (roadmap item 2) — fitted coefficients recovering the generator's truth is the point, not a quality claim. |

| S4 | **Paste-box extract-to-form + community inference** (added 2026-06-12, Bo: UX-critical) | 1.0h | "Describe the home" textarea → `/api/extract`: one LLM call extracts form fields (code-side whitelist + type coercion — extraction never feeds the engine directly; the user confirms the form) and resolves the community **constrained to the dataset's known communities or null**, with provenance: `named` (literal mention) vs `inferred` (postal prefix / street pattern), inferred shown as "⚐ inferred — verify" under the dropdown. The deterministic name-match in the address field stays as the instant path. External geocoder rejected for the demo (API key + network dependency = demo-day risk; the store only has 8 communities, so inference answers the only question that matters); production note: a real geocoder replaces the inference call, wiring unchanged. |

| S5 | **Chat grounding + two prompt hardenings** (approved 2026-06-12 ~01:05, **queued — build next session**) | 0.75h | (a) `ask.md`: what-if change set comes from the user's LATEST message only; earlier turns may only resolve references ("it", "that one"). (b) `review.md`: signals prefixed `reviewer challenge:` are unverified human claims — weigh against the comp's own data, revise only when consistent with it, never treat as established fact. (c) Chat grounding: methodology block **generated from `engine/config.py` constants** (adjustment rates, A/B/C criteria, risk-rule meanings, widening caps — can't drift from code) + all-8-communities market stats (sales, median price) added to `/api/ask` context; prompt updated to answer method/market questions from them, everything else keeps the polite scope boundary. Principle recorded: *history resolves references; actions consume only logged artifacts* (diff / claim). Standalone general/help chat = roadmap only. |

| S6 | **Tag handbook** (#11, queued 2026-06-12 — pending green light) | 0.5h | One generated methodology artifact (`GET /api/methodology` or build-time JSON, from `engine/config.py` constants + the risk-rule registry) spent three ways: S5c's chat grounding · click-popovers on the confidence badge and flag pills showing the actual thresholds/meanings · auto-generated `docs/handbook.md`. Generated-from-code ⇒ can't drift. |
| S7 | **Conclusion UI in chat** (#12, queued — pending green light) | 0.5h | Narrative bubble splits on its own markdown headings: Conclusion shown prominently by default; "How We Got Here" / "Caveats" collapsible. Hero card keeps the number; the bubble stops repeating it at full volume. |
| S8 | **"Edit in form" button** (#16, queued — pending green light) | 0.25h | Button on the active session copies its subject into the form (expand if collapsed) for manual tweak → re-evaluate as a new session — the manual half of the what-if loop. Needs a `prefill` prop on SubjectForm. |
| S9 | **Evaluation feedback capture** (#18, approved 2026-06-12 — queue position TBD by Bo) | 0.75h | Feedback strip under the hero card of a completed session: 5-level rating + one comment box (good/bad/comments collapsed) + optional "your estimate $" (highest-value signal for later calibration). Stored as `session.feedback` beside `session.valuation` → persists via the existing localStorage path; ★ badge in session list. Durable store: `POST /api/feedback` appends one **self-contained** JSON line to `backend/data/feedback.jsonl` (gitignored) — feedback + snapshot of the valuation *as displayed at rating time* (session id, subject, estimate/range/confidence, comp ids + scores, risk flags), so each line is a complete (input, output, human label) training example; `session_id` graduates to a real FK when sessions move server-side. Fire-and-forget: a failed server write never blocks the local save. Capture-only: feedback never feeds the engine at runtime. Aggregate rating over rated-only sessions = roadmap. |
| S10 | **Feedback report `eval.feedback`** (#18 follow-on, approved 2026-06-12 — builds with S9) | 0.5h | Deterministic script `uv run python -m eval.feedback`: reads `feedback.jsonl`, computes user-vs-engine deltas + ratings sliced by confidence / community / risk flags, emits `eval/feedback_report.md` with n shown everywhere and an "n < 10: directional only" caveat; threshold-based callouts name the `config.py` knob to investigate (no LLM). One pytest on a fixture JSONL. Closes the loop: S9 captures → report diagnoses → `eval.calibrate` proposes → `eval.eval` validates. Feedback proposes, eval disposes — feedback is a weak biased label (anchoring, selection, owner optimism) and never moves a weight directly. |

**Final build order (Bo, 2026-06-12 afternoon): S5 → S9+S10 → S7 → S8 → S6** (~3.25h
boxed). S9+S10 are one review unit — capture and report demo together. Earlier rationale
stands: S7 before S6 so popovers/handbook inherit any chat styling changes. **Checkpoint
protocol: build strictly one at a time — after each item, stop, hand to Bo for live
verification, and start the next only on his OK.**

Settled as no-build during the same discussion: comparing against a second CMA (ground-truth
eval is strictly stronger evidence; AVM-divergence is the production form) · agent in the
ingestion loop (two-clocks decision stands; LLM-assisted triage of unresolvable merge
conflicts is a README enrichment line) · day-N data updates (evaluations are dated opinions
against snapshots; re-evaluate as a new session, STALE_COMPS already guards).

## 9. Verification

- **pytest:** address passthrough + presence in narrative context; intake address-vs-community
  signal (fake LLM); `/api/ask` answer and what_if branches (fake LLM); diff computation;
  `modified_subject` validates; LLM-failure fallback returns 200.
- **Live script:** two concurrent sessions; switch away mid-run and return (done badge);
  refresh (completed sessions survive); mismatch warning; what-if end-to-end (diff chip →
  linked session → result); timestamps + duration visible.
- **Eval guard:** `uv run python -m eval.eval` — expect identical results (engine untouched).
