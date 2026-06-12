# Design deep-dive — home-evaluator

The long-form companion to the [README](../README.md): the full problem understanding,
the approach from both an **agent** and a **product** perspective, the complete decision
log with rejected alternatives, and the roadmap of what's deliberately *not* built yet.
Written for presentation and Q&A use — every claim here is backed by code, tests, or the
eval table in this repo.

- [1. What I understood the problem to be](#1-what-i-understood-the-problem-to-be)
- [2. The approach](#2-the-approach)
  - [2.1 As a product](#21-as-a-product--a-defensible-number)
  - [2.2 As an agent](#22-as-an-agent--judgment-inside-a-code-gated-action-space)
  - [2.3 The data layer](#23-the-data-layer--two-clocks-one-canonical-record)
  - [2.4 Measurement — how ML, the AVM, and the eval combine](#24-measurement--how-ml-the-avm-and-the-eval-combine)
- [3. What's included](#3-whats-included--the-features-i-decided-to-keep)
- [4. Decision log — trade-offs and rejected alternatives](#4-decision-log--trade-offs-and-rejected-alternatives)
- [5. Roadmap — what I'd build next (none of it built yet)](#5-roadmap--what-id-build-next-none-of-it-built-yet)
- [6. How it was built — process](#6-how-it-was-built--process)

---

## 1. What I understood the problem to be

KV Capital underwrites loans to Alberta home builders. The underwriting bottleneck is
**comp analysis**: to value a property, an analyst searches three places by hand — MLS,
land titles, assessment rolls — three portals, three address formats, cross-referenced by
eye. Three things make this genuinely hard, not just tedious:

1. **Each source alone is incomplete.** MLS misses private sales; land titles record
   every transfer but carry no interior attributes; assessments cover every property but
   have no sale prices. No single feed can answer "what is this home worth."
2. **Some signals only exist *across* sources.** A non-arm's-length transfer (a family
   sale at 60% of value that would poison a comp set) is detected by comparing the
   land-titles price against the assessed value — neither source alone shows it.
3. **The data is locked up.** Alberta sold prices sit behind Pillar 9 (MLS) and land
   titles; Calgary open data has no sales and no interior attributes (verified). The
   lock-up *is* the business problem — and it dictated the synthetic-data decision below.

And the output side has a constraint that shapes everything: **a lender needs a
defensible number**, not a plausible one. Every dollar of the estimate must trace to a
named comp and a tested formula; uncertainty must surface as explicit confidence grades
and risk flags; a human reviewer must be able to interrogate and challenge the result.
That constraint is why this is a *hybrid* agent and not an LLM that outputs a price.

## 2. The approach

### 2.1 As a product — a defensible number

The deliverable is an **audited valuation**: estimate + P25–P75 range + A/B/C confidence
+ risk flags + an appraiser-style narrative, where the transcript is rendered from
structured events emitted by code *as each step ran* — not an LLM retelling its work
after the fact. Explanation and action are one artifact; they cannot diverge.

The human stays in the loop through **typed, visible doors** — never silent ones:

- **The form is the input contract.** Free-text paste-box extraction *proposes* form
  values (community inference constrained to the dataset's known list, labeled
  "⚐ inferred — verify"); the human confirms before anything runs. A typo can never
  silently move a valuation.
- **Disagreement is argued, not clicked.** A reviewer who disputes a comp states a claim
  ("comp 2 backs onto a highway"); the agent re-reviews that comp with the claim as
  evidence and either revises (engine recomputes; the reversal is logged with the
  original preserved) or defends its verdict (the objection stays in the record). A
  one-click override was explicitly rejected: a click that flips a verdict with no
  argument makes agent judgment decoration. This mirrors real appraisal review —
  comments go back to the appraiser, who revises or rebuts.
- **Feedback is captured, never auto-applied.** Ratings, comments, and the user's own
  estimate become durable training examples; they *localize* error for offline diagnosis
  but never move a weight at runtime (§2.4).
- **Chat answers are grounded or declined.** Method and market questions are answered
  from config-generated methodology and the store's actual stats; open-ended real-estate
  opinions are politely declined — ungrounded claims sitting next to audited numbers
  would blur the product's trust boundary.

The unit of work is a **per-home session**: form in, transcript out, pinned hero
valuation card, follow-up Q&A, what-if re-runs that spawn linked (fully audited)
sessions, background runs that finish while you look at another home. Full free-text
chat *intake* was rejected the night before the deadline: structured fields are the
lender-grade input contract, and the session transcript already gives the agent feel
without a multi-turn intake loop's failure modes.

### 2.2 As an agent — judgment inside a code-gated action space

**The one-line rule: the LLM never produces a number the engine didn't compute.** The
engine (`backend/engine/`, zero LLM imports) owns filtering, similarity scoring,
adjustments, valuation, confidence, and the risk-rule registry — pure, deterministic,
unit-tested Python. The LLM contributes judgment (search strategy, comp review, notes
interpretation) and language (the narrative).

**The graph.** Six LangGraph nodes; each is code or LLM for a stated reason:

| Node | Kind | Model | Why this kind |
|---|---|---|---|
| intake | LLM | Haiku | mining free-text notes for signals is a language task; it never alters the form's numbers |
| search | code + LLM | Sonnet | filtering is predicates; *widening strategy* is a judgment call among trade-offs |
| score | pure code | — | similarity must be auditable math (8 weighted dimensions, per-dimension breakdown) |
| review | LLM ×8 | Haiku (parallel Send fan-out) | per-comp judgment over deterministic pre-checks; volume → cheap model |
| valuate | pure code | — | the number. Adjustments, weighted median, confidence, risk rules — tested code only |
| narrate | LLM | Sonnet (streamed) | language; hard rule: only numbers present in the data block |

Per-node model selection is env-driven (`INTAKE_MODEL`, `SEARCH_MODEL`, `REVIEW_MODEL`,
`NARRATE_MODEL`, `ASK_MODEL`, `EXTRACT_MODEL`): Haiku where volume, Sonnet where
judgment — a cost/latency dial, swappable without code changes. End-to-end ~13s with
streaming.

**Three LLM-integration modes, chosen per job — this is the durable design idea:**

1. **Tool-calling where the model chooses *actions*.** Search widening is genuine
   tool-calling — but the engine pre-computes what every candidate move would find,
   never offers a capped move, and never offers "accept" when a move provably yields
   comps and the set is empty. The model picks the trade-off; the engine guarantees the
   choice is sane. (This gate exists because the eval *caught* the un-gated agent
   accepting an empty comp set — see §2.4.)
2. **Context injection where facts must always be present.** Chat grounding (methodology
   generated from `engine/config.py` constants + all-community market stats) is injected
   into every `/api/ask` call, not exposed as tools — a tool the model may not call can
   silently skip grounding; injected context is structurally always there. Right answer
   *while grounding is small* (~1.5k tokens); the flip condition is on the roadmap (§5).
3. **Typed JSON-to-code where anything *mutates results*.** What-ifs return a
   code-computed field diff; challenges carry a distilled claim into a re-review plus
   engine recompute. Chat has **no write path** to results except these two audited
   doors. The principle: *history resolves references; actions consume only logged
   artifacts.*

**Statelessness and memory policy.** The backend is stateless across runs — valuations
must be independent and reproducible (an audit requirement). Conversational memory
exists *within* a session (the chat carries its history); memory *across* sessions and
runs is deliberately absent: every answer must be reproducible from that home's report
alone. Silent context is the enemy of a defensible number.

**Graceful degradation.** Every LLM node has a deterministic fallback — a failed call
degrades the result (marked in the UI), never 500s the request. Without an API key the
whole pipeline runs end-to-end in deterministic mode.

**Field lessons that became rules** (each found live, then locked in code or prompts):
the as-of date is injected into every prompt (a review once called an April 2026 sale
"in the future"); widening reasons are captured at decision time — the same string that
drove the action is the one displayed; review/widening rationales are honestly framed as
contemporaneous self-reports, with the guarantees kept *structural* (code-gated action
space + eval) rather than resting on LLM self-explanation faithfulness.

### 2.3 The data layer — two clocks, one canonical record

**Two clocks.** Data is acquired at *ingestion time* (offline batch; production =
scheduled syncs of licensed feeds — never query-time scraping). The agent at *query
time* searches the local merged store in milliseconds. All three real production
channels were verified to exist and be batch-shaped (Calgary open-data Socrata API ·
Alberta land-titles Volume Data Access · Pillar 9 RESO Web API), so the `CompSource`
adapter interface is a real seam, not hand-waving.

**The synthetic world.** Real Alberta sold prices are inaccessible, so the prototype
synthesizes a seeded Calgary world with a known **ground-truth price model**: 8 real
communities with distinct profiles, ~2,650 sales over 24 months, ~6,300 properties,
real geometry (haversine radius search). Three differently-shaped source files (realtor
address formats vs legal descriptions vs assessment abbreviations, "3+1" bed notation,
private sales missing from MLS) are merged by a unit-tested normalized address key into
one canonical record with **field-level provenance** — every comp can say "price from
land titles, sqft from MLS."

**Precedence, recorded.** Land-titles price > MLS (registered legal record); assessment
year-built > realtor-entered MLS. Disagreements beyond tolerance become `DATA_CONFLICT`
flags — recorded, never silently resolved. Edge cases are *planted* (non-arm's-length
transfers, a 5-sales-in-24-months thin market, luxury outlier variance, quick flips,
cross-source conflicts, a stale-comps pocket) so the agent's handling of each is a
testable assertion, not an anecdote.

### 2.4 Measurement — how ML, the AVM, and the eval combine

The motto: **adjustable everywhere, automatic nowhere.** Every weight and rate is a
named constant in `engine/config.py`; every retune is a human decision validated against
ground truth. Four instruments work together:

1. **The eval harness is the arbiter** (`eval.eval`). 20 held-out subjects priced by
   the ground-truth model: LLM-on **MAPE 2.2%, 20/20 within ±10%, median |error| 1.4%**
   vs deterministic baseline 2.1% / 19/19 (Bearspaw: no estimate). Scenario asserts pin
   the planted edge cases. The headline story: on the thin-market acreage the
   deterministic widening found nothing; the LLM, choosing from engine-projected move
   yields, recovered 2 comps and estimated within +3.6% — graded C with four caveat
   flags. LLM judgment didn't degrade accuracy; it recovered an estimate, with the
   caveats attached. The eval also caught a live agent bug (accepting an empty comp set
   when a move provably yielded comps) — that regression became the action-space
   guardrail: ground truth → scenario assert → caught regression → code-enforced fix.
2. **Calibration proposes rates** (`eval.calibrate`). A hedonic regression over the
   2,603 scorable sales recovers the per-factor rates (**R² 0.976**: bed $8,185 vs
   config $8,000 · garage $11,596 vs $10,000 · lot `$/sqft` exact · trend ≈1.1%/q vs
   1.2%). On synthetic data this proves the *mechanism*, deliberately not quality — the
   same code fits the real market once licensed solds exist.
3. **The AVM stand-in cross-checks, never replaces** (`BASELINE_DIVERGENCE` risk rule).
   A transparent median-`$/sqft` market-norm yardstick flags when the estimate diverges
   >15% (silent under 5 sales — thin-market yardsticks are noise). A GBM trained on our
   own synthetic data was rejected as theater: trained on data our price model
   generated, it would always agree and the flag would never fire. The honest yardstick
   genuinely diverges on planted cases and exercises the exact production seam — an
   independent estimator whose *disagreement becomes a risk flag*, never a replacement
   estimate.
4. **User feedback localizes error** (`/api/feedback` + `eval.feedback`). Each rating
   snapshots the valuation *as displayed at rating time* into a self-contained
   (input, output, human label) JSONL line; a deterministic report slices user-vs-engine
   deltas by confidence grade, community, and risk flag — n shown everywhere, "n < 10:
   directional only" — and names the `config.py` knob to investigate. Feedback is a
   weak, biased label (anchoring on the shown estimate, selection effects, owner
   optimism), so it never moves a weight at runtime.

The loop, end to end: **feedback captures → the report diagnoses → calibration proposes
→ the eval disposes.** The LLM lives under the same constitution as the ML: judgment
and cross-checks in, unilateral numbers out.

## 3. What's included — the features I decided to keep

Everything below shipped, is live-verified, and stays in the submission. (The demo video
can't reach all of it in 3 minutes; "carrier" says where each feature is demonstrated.)

| # | Feature | What it proves | Carrier |
|---|---|---|---|
| 1 | Multi-source ingestion: 3 source shapes → canonical record, field-level provenance, recorded conflicts | the actual business pain, demonstrated not claimed | video + README |
| 2 | Deterministic engine: filters, 8-dim similarity, adjustment ladders, weighted-median valuation, A/B/C confidence, risk-rule registry | every dollar traceable; registry = expandability | video + README |
| 3 | Agentic widening: LLM picks one move per round from engine-projected yields, ≤2 rounds, reasons logged verbatim | judgment inside a code-gated action space | video (Bearspaw) |
| 4 | Per-comp review: parallel fan-out, deterministic pre-checks, keep/demote/exclude with one-line reasons | cheap-model volume judgment, auditable verdicts | video |
| 5 | Streamed narrative: appraiser-style, only numbers from the data block | language layer under the no-invented-numbers rule | video |
| 6 | Paste-box extraction: free text → form prefill; community inference constrained to the known list, labeled "inferred — verify" | extraction proposes, never feeds the engine | video |
| 7 | Per-home sessions: background runs, done-badges, localStorage persistence, warm 3-column UI | session = the future DB schema | video |
| 8 | Grounded follow-up chat: config-generated methodology + market stats injected; out-of-scope declined | answers from the engine's constants, not vibes | video (S5 script) |
| 9 | What-if re-runs: code-computed field diff → linked, fully audited evaluation | chat has no write path except audited doors | video |
| 10 | Comp challenge → re-review: claim as evidence → revise (engine recompute, original preserved) or defend | human contributes evidence, agent judges, engine computes | video |
| 11 | Feedback capture + report: 5★/comment/own-estimate → JSONL training lines → sliced diagnosis naming config knobs | the underwriter feedback loop, capture→diagnose | video + README |
| 12 | Eval harness vs ground truth + scenario asserts | provable quality; caught a real agent bug | video (table) + README |
| 13 | Hedonic calibration demo (R² 0.976) | the ML-calibrates-engine roadmap as running code | README |
| 14 | Tag handbook: auto-generated `docs/handbook.md` + `GET /api/methodology` + UI popovers on the confidence badge and flag pills — one artifact from engine constants, drift-guarded by a pytest | docs can't lie | README + UI |
| 15 | LangGraph Studio support + LangSmith tracing | every widening tool-call inspectable | README |

128 backend tests green; TypeScript compile clean; everything above verified live in the
browser before its checkpoint.

## 4. Decision log — trade-offs and rejected alternatives

Format: **decision** · *rejected alternative* · why. Chronological raw log with dates:
[`demo-notes.md`](demo-notes.md) §2.

### Agent-design decisions

- **Hybrid LangGraph: deterministic engine + LLM judgment nodes** · *pure-LLM agent* ·
  a lender needs every dollar traceable to a named comp and a tested formula; the LLM
  judges and narrates, the engine computes.
- **No RAG/vector retrieval over comps** · *embeddings + cosine similarity* · exact
  predicates and auditable scoring beat cosine similarity for structured numeric data;
  semantic re-ranking belongs later, over unstructured listing remarks, as an
  enrichment signal — not the foundation.
- **Widening LLM chooses from engine-projected counts** · *letting it reason blind* ·
  live verification caught it picking radius widening twice on plausible-but-wrong
  intuition (0 comps where the dumb fallback found 1). Now the engine pre-computes
  every move's yield; the model picks the trade-off.
- **Widening action space is code-gated** · *trusting the prompt alone* · the eval
  caught the agent accepting an EMPTY comp set while a move provably projected 1 comp.
  The engine no longer offers "accept" in that situation, capped moves aren't offered
  at all, and accept decisions are logged.
- **Chat grounding by context injection, not tools** · *callable
  methodology/market-stats tools* · an uncalled tool silently skips grounding with no
  failure signal; injected context is structurally always present. Holds while
  grounding is ~1.5k tokens; the flip condition is a roadmap item (§5).
- **Chat memory scoped to the session; no cross-session/cross-run memory** · *an agent
  that remembers across homes* · every answer must be reproducible from that home's
  report alone (audit). Cross-session features return as *explicit* commands
  (compare-two-sessions), never implicit recall.
- **Stateless backend across runs** · *cross-run memory/learning* · valuations must be
  independent and reproducible; learning happens offline, between versions.
- **Widening capped at 2 rounds; review fan-out capped at top-8** · *unbounded loops* ·
  bounded cost, latency, and audit size; deterministic fallback if the LLM fails.
- **Per-node model selection via env** · *one model everywhere* · Haiku where volume
  (intake, review fan-out), Sonnet where judgment (search, narrate, ask, extract) —
  cost/latency control without code changes.
- **As-of date injected into every prompt** · *assuming the model knows "now"* · a
  review verdict once called an April 2026 sale "in the future."

### Product & UX decisions

- **Chat-hybrid UI: form in, transcript out** · *full free-text chat intake* ·
  structured fields are the lender-grade input contract (a typo must not move a
  valuation); the per-home transcript + follow-up Q&A deliver the agent feel without a
  multi-turn intake loop's new failure modes (~4–6h, rejected the night before the
  deadline).
- **Human disagreement = challenge → agent re-review** · *a one-click exclude/override
  button* · a click that overrules the agent with no argument makes agent judgment
  decoration; stating a claim that the agent weighs as evidence mirrors real appraisal
  review. Production backstop: licensed sign-off with mandatory written justification.
- **What-if = visible field diff + fresh linked run** · *chat silently mutating inputs,
  or the LLM "adjusting" the estimate* · the diff is computed in code, shown in the
  transcript, and run as a full audited evaluation.
- **Extract-to-form with constrained community inference** · *full chat intake, or an
  external geocoder API* · the paste box prefills the *form* and the human confirms it;
  inference is constrained to the dataset's 8 communities or null, labeled. An external
  geocoder would add an API key + network dependency on demo day to answer a question
  the 8-community store doesn't ask; production swaps the inference call for a real
  geocoder, wiring unchanged.
- **Address is display + cross-check, never an engine input** · *pretending to geocode
  synthetic geography* · community auto-fill is deterministic; mismatches are flagged
  twice (form warning + intake contradiction signal); a wrong address can never move
  the number. Production: geocoder → lat/lon → the *existing* haversine filter.
- **Method/market questions answered in-session, grounded; opinions declined** · *a
  separate general chat, or free general-knowledge answers* · questions arise in
  context ("why a B?" while looking at a B); ungrounded opinions next to audited
  numbers would blur the trust boundary.
- **Warm Listen360-style re-theme + 3-column layout, app-wide** · *cool slate (the
  original recommendation), or a half-warm chat pane* · picked from live browser
  mockups; a half-warm app reads as mismatch, not choice. Functional work was
  sequenced ahead of polish so cap pressure would drop polish first.

### Data & ML decisions

- **Synthetic data with a ground-truth price model** · *scraping/sourcing real data* ·
  real Alberta sold prices are inaccessible (that lock-up is the business problem);
  bonus: provable eval against known truth.
- **Two clocks: ingestion-time batch, query-time local search** · *live query-time
  retrieval* · milliseconds, reproducible, audit-safe; no query-time scraping ever.
- **Source precedence rules, conflicts recorded** · *trusting one source, or averaging* ·
  land titles is the registered legal record; assessments beat realtor-entered years;
  disagreements become flags, never silent fixes.
- **Fuzzy entity resolution out** · *ML/fuzzy address matching* · we control the
  synthetic mess; a normalized-exact address join suffices and is unit-testable.
- **ML calibrates the engine, never replaces it** · *training models on our synthetic
  data, or a black-box AVM as the estimate* · synthetic-trained ML would reverse-
  engineer our own generator (circular metrics); a lender needs traceability. The
  four-rung upgrade ladder is in §5.
- **AVM stand-in = transparent `$/sqft` market norm** · *a GBM trained on synthetic data
  as an "independent" cross-check* · it would always agree with the generator that made
  the data — the divergence flag would never fire; theater. The honest yardstick
  exercises the real seam.
- **Similarity recency weight kept at 20/100** · *weighting recent sales harder* · the
  engine already corrects old prices forward via the trend index; recency's job is only
  the uncertainty correction can't fix. More recency starves thin markets of comps.
  Per-market learned profiles are the real answer (roadmap); deadline-day retunes on
  vibes are how you make things worse.
- **User feedback = capture-only weak label** · *ratings tuning the engine directly, or
  skipping feedback* · anchoring, selection, and owner optimism make it a biased label;
  it localizes error. Feedback proposes, eval disposes.

### Process decisions

- **12h hard cap, strict time boxes, pre-named escape hatches, 2h reserve** ·
  *flexible scope* · the deadline is firm; every block declared its cut ladder before
  starting; overruns bill the reserve, and polish is sequenced behind function.
- **Checkpoint protocol: one unit at a time, human verification between** · *batching
  the stretch queue* · each unit was live-verified in the browser and reviewed before
  the next began.
- **TDD on engine and API surfaces; eval rerun as a guard after UX changes** ·
  *test-after* · the eval harness caught a real agent regression mid-build; tests are
  the contract that let 5–10× under-estimate velocity stay safe.

## 5. Roadmap — what I'd build next (none of it built yet)

Everything in this section is **designed but deliberately not built** — each item has
its seam already in place, so it's an extension, not a rewrite.

### Product roadmap

- **Server-side sessions with accounts.** Today's localStorage `Session` object is
  already the schema (subject, run state, chat, timestamps, what-if lineage); a
  `sessions` table keyed by (account, session) takes it verbatim, and persistence is
  isolated behind two functions in `sessions.ts` that become `GET/PUT /api/sessions`.
  Buys cross-device access, underwriters reviewing an analyst's session (the challenge
  log as a review artifact), and provenance for the tuning loop. The valuation
  endpoints stay stateless either way; server-stored sessions bring the usual
  lending-data obligations (retention, access control, encryption at rest).
- **Server-side run state** so an in-flight evaluation survives a browser refresh
  (finished sessions already do).
- **Chat grounding graduates to a read-only retrieval tool layer** when grounding
  outgrows the prompt: comp-store queries ("every sale on this street"), handbook
  search, live HPI lookups become tools the model calls on demand (natural shape: an
  MCP server over engine functions). The division of labor is the durable part — always-
  needed facts stay injected, the model chooses retrievals, anything that mutates
  results stays a typed action executed by audited code. The migration changes
  plumbing, never the trust boundary.
- **Explicit cross-session features, demand-driven**: a compare-two-sessions command
  (user selects both — two auditable contexts, not implicit recall); recurring
  challenge patterns feeding the offline tuning loop. Implicit cross-session memory
  stays out.
- **Standalone help/methodology chat** outside any session.
- **Formal sign-off step** (licensed reviewer, mandatory written justification) as the
  legal backstop behind challenge → re-review.

### ML roadmap — four rungs, in order, each behind the eval

Same constitution as the LLM: models **calibrate and cross-check** the explainable
engine; they never replace it. Verified-workable, in order of increasing ambition:

1. **Subscribe the trend index to a real HPI** (CREA/Teranet) — `MARKET_TREND_QOQ`
   already anticipates it; config change, no engine change.
2. **Fit adjustment coefficients by hedonic regression on licensed solds** (~25–30k
   Calgary sales/yr) — the adjustment ladder is already linear, so fitted coefficients
   are a drop-in config change. The mechanism already runs in this repo
   (`eval/calibration.md`, R² 0.976 on synthetic truth).
3. **A real AVM (e.g., GBM) as a divergence tripwire** — one appended risk rule + one
   context field; the `BASELINE_DIVERGENCE` wiring is the slot it drops into.
4. **Learn similarity weights from KV's own appraisal archive** (which comps human
   appraisers actually chose — a proprietary label source no competitor has). Furthest
   out; needs a PDF-extraction pipeline.

Confidence calibration belongs on this list too: the A/B/C grades are heuristic cuts
(comp count, IQR, similarity floor), not calibrated probabilities — eval case 5 carries
an A grade with the table's largest error (+7.9%). Calibrating the cuts against a larger
eval set is the obvious next step.

### Production data plan

All three real channels exist and are batch-shaped — exactly the ingestion model this
repo implements; each becomes a `CompSource` adapter, merge/provenance unchanged:

- **Calgary assessments** — free open data with a Socrata API, works today.
- **Alberta land titles** — Volume Data Access products: bulk, database-ready, standard
  paid contract.
- **Pillar 9 (MLS)** — RESO Web API under a negotiated data license; sold-data access
  is commercially gated but a well-trodden vendor path.

Plus a geocoder turning the subject address into lat/lon for the *existing* haversine
filter (today the search anchors at the community center; the address is display +
cross-check only).

### Hardening backlog (honest list, found in a pre-submission review pass)

- Code-enforce that a what-if's `modified_subject` differs only in user-named fields
  (today the latest-message scoping is prompt-enforced; the diff itself is already
  code-computed).
- Preserve market-baseline context when a comp challenge triggers revaluation.

### Deliberately cut (and why it's safe to cut)

- **Borrower/owner legal status, liens, credit** — a different underwriting step with
  different data; the risk-rule registry (`TITLE_ENCUMBRANCE`, `OWNER_LEGAL_STATUS`,
  `FORCED_SALE_DISCOUNT` as future rules) is the door it walks back in through.
- **Commercial properties** — residential only.
- **Live data connectors** — production path documented and verified instead.
- **A second CMA comparison** — ground-truth eval is strictly stronger evidence;
  AVM-divergence is the production form of an independent cross-check.
- **Agent in the ingestion loop** — two-clocks stands; LLM-assisted triage of
  unresolvable merge conflicts is a future enrichment.

## 6. How it was built — process

12-hour hard cap against a firm deadline, tracked wall-clock (including human thinking
and review time) in [`TIMELOG.md`](../TIMELOG.md). The mechanics that made it work:

- **Spec first, then strict time boxes with pre-named escape hatches.** Every block
  declared its cut ladder before starting (e.g., "what-if execution → prefill the form
  and say press Evaluate"); an overrun invokes the hatch immediately rather than Friday
  night. No hatch was ever pulled — blocks ran 3–10× under their boxes.
- **Checkpointed stretch queue.** After the core, features shipped strictly one
  review unit at a time (grounded chat → feedback loop → visual unit → …), each
  live-verified in the browser and human-reviewed before the next started. Functional
  work was sequenced ahead of polish so cap pressure would drop polish first.
- **The eval as a regression guard.** Engine-touching and even UX changes ended with an
  eval rerun; it caught a live agent-judgment bug (the empty-comp-set accept) that
  became a permanent code guardrail.
- **Decisions logged at the boundary.** Every block updated the time log and the
  decision log ([`demo-notes.md`](demo-notes.md)) while context was fresh — this
  document is assembled from those records, not from memory.
