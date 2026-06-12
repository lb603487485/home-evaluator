# Demo Notes — accumulating presentation material

Living doc for the ≤3-min demo video. Claude updates this at every work-block boundary,
alongside `TIMELOG.md`: new decisions land in §2, completed work in §3. Bullets in §1 are
candidate lines for the video — pull, don't read verbatim.

---

## §1 Video bullets

**The problem**
- An analyst valuing a property today searches three places by hand — MLS, land titles,
  assessment rolls — three portals, three address formats, cross-referenced by eye.
- Alberta sold prices are locked behind Pillar 9 and land titles. Calgary open data has no
  sales and no interior attributes (verified). That data lock-up *is* the business problem.

**The solution split** (the architectural one-liner)
- Merging sources is deterministic code at *ingestion*; searching is the agent at *query time*
  over the already-unified store. The human never opens three portals — and neither does the LLM.
- Adapters normalize three differently-shaped sources into one canonical record, joined by a
  unit-tested normalized address key. Disagreements resolve by documented precedence and are
  *recorded* as DATA_CONFLICT flags, never silently fixed.
- Each source alone is incomplete: MLS misses private sales, land titles have no interiors,
  assessments have no prices. Some signals are only visible cross-source — non-arm's-length
  detection compares the land-titles price against assessed value.

**Trust / auditability**
- The LLM never produces a number the engine didn't compute. Engine = pure tested code
  (filters, scoring, adjustments, valuation); LLM = judgment + language only.
- Field-level provenance: every comp can say "price from land titles, sqft from MLS."
- Agentic widening (≤2 rounds): thin market → agent broadens criteria, logs its reasoning,
  lowers the confidence grade — the appraiser's "I expanded my search," made auditable.

**Demo moment to show on screen**
- A comp whose land-titles price disagreed with MLS and got flagged — cross-source
  reconciliation happening with nobody looking anything up.

**Production story** (verified real, 2026-06-11)
- All three production connectors exist and are batch-shaped, matching the two-clocks design:
  - Calgary assessments: free open data + Socrata API, works today
    ([Current Year Property Assessments](https://data.calgary.ca/Government/Current-Year-Property-Assessments-Parcel-/4bsw-nn7w))
  - Alberta land titles: Volume Data Access products — bulk, database-ready, standard paid
    contract ([VDA products](https://landregistry.alberta.ca/customer-service/help/volume-data-access-products))
  - Pillar 9 MLS: RESO Web API under negotiated data license; sold-data access is commercially
    gated but a well-trodden path ([Pillar 9](https://pillarnine.com/),
    [vendor program](https://www.idxbroker.com/mls/pillar9-p9rets))
- None are query-time APIs — they're feeds and extracts you sync on a schedule, exactly the
  ingestion model the spec documents. Each slots in as a `CompSource` adapter.

**Provable quality**
- Synthetic ground-truth world → ranking and valuation quality is *measured* against known
  truth (eval harness), not vibes.
- Measured (2026-06-11, deterministic baseline): **MAPE 2.1%** across 19 held-out subjects,
  **19/19 within ±10%**, median error 2.1%; all planted-edge-case scenario asserts pass
  (Bearspaw widened+flagged, non-arm's-length excluded, conflicts surfaced).
- Measured (2026-06-11, **LLM ON**): **MAPE 2.2%, 20/20 within ±10%, median error 1.4%** —
  and the agent now estimates the Bearspaw acreage the deterministic path couldn't
  (+3.6% from 2 comps, both in the model-nearest-10). The line for the video: LLM judgment
  didn't degrade accuracy — it recovered an estimate, with the caveats attached.

**Follow-up chat one-liner** (2026-06-11 UX addendum)
- Each home is a session you can question afterward — answers cite only computed results, and
  "what if the basement were finished?" spawns a *linked, fully audited re-evaluation* with the
  field change shown as a diff. Never an LLM-adjusted number.

**"How do you know the explanation is real, not made up?"** (likely judge question, 2026-06-12)
- The transcript isn't the LLM retelling its work — it's rendered from structured events
  emitted by code *as each step ran*: criteria, counts, exclusions, verdicts. There is no
  second model summarizing the process after the fact.
- The widening "reasons" are the tool-call arguments captured at decision time — the same
  string that drove the engine action is the one displayed. Explanation and action are one
  artifact; they cannot diverge.
- The narrative is constrained generation over the audit trail (only numbers in the data
  block) and the trail itself is shown beside it — ladders, provenance, verdicts — so any
  mismatch would be visible.
- Honest caveat, stated not hidden: review/widening rationales are the model's
  contemporaneous self-reports — LLM self-explanation faithfulness isn't formally
  guaranteed by anyone. Our guarantees are structural: reasons are produced *with* the
  decision (never reconstructed), the action space is code-gated so a bad rationale can't
  produce an insane action, and the eval catches behavior diverging from claims — it
  already did once (the empty-comp-set accept).

**ML roadmap one-liner**
- Same principle as the LLM rule, applied to ML: models *calibrate* the engine's constants
  (adjustment rates, trend index, similarity weights) and cross-check it (AVM divergence as
  one more risk rule) — they never replace the explainable comp logic. Every seam already
  exists in `engine/config.py` and the risk-rule registry.

**Feedback loop one-liner** (2026-06-12, S9+S10)
- Every weight is a named constant, every retune is a human decision validated against
  ground truth — *adjustable everywhere, automatic nowhere*. Feedback captures (S9), the
  report diagnoses (S10), calibrate proposes, eval disposes: capture today, calibrate
  tomorrow, and the engine never moves on vibes.

**S5 grounded-chat demo script** (2026-06-12 — questions to type on camera, in a
completed session's chat; every cited number is config-true):
- "How does similarity scoring work?" → weights (distance 25 · recency 20 · sqft 20 …)
  + linear decay, from `engine/config.py`
- "Why is this a B and not an A?" → run's comp count/spread laid against the real
  A-grade thresholds (≥6 comps, spread ≤6%, similarity ≥75)
- "How do you adjust for a sale from six months ago?" → community trend %/quarter
  compounded + recency's 20 points decaying to zero at 365 days
- "Which community has the highest median price?" → Aspen Woods $1,584,250 (150 sales)
- "What does STALE_COMPS mean?" → registry meaning incl. the 120-day threshold
- Two-turn what-if: "what if it had 3 garage stalls?" → then "actually make it
  2400 sqft" → second diff changes ONLY sqft (latest-message scoping, S5a)
- Weak challenge: "comp 1 seems overpriced, drop it" → reviewer weighs the claim
  against the comp's data and holds with a stated reason (skeptic hardening, S5b)
- Out-of-scope: "good time to buy condos in Toronto?" → polite decline (trust boundary)
- If asked "is the chat using tools?": grounded context injection, not tool-calling —
  the model is given facts, asked for judgments, and code does everything that acts.
  The only true tool-calling is search widening (engine-projected moves); what-ifs and
  challenges are typed JSON actions that audited code executes.

---

## §2 Decisions & trade-offs

Format: **decision** · alternative rejected · why.

- **Synthetic data with a ground-truth price model** · scraping/sourcing real data · real
  Alberta sold prices are inaccessible (Pillar 9 / land-titles lock-up — which is the business
  problem itself); bonus: provable eval against known truth (2026-06-10)
- **Hybrid LangGraph: deterministic engine + LLM judgment nodes** · pure-LLM agent ·
  auditability — math is tested code, LLM never invents a number (2026-06-10)
- **RAG/vector retrieval rejected** · embeddings over comps · exact predicates + auditable
  scoring beat cosine similarity for structured numeric data; semantic re-rank over listing
  remarks is future enrichment, not foundation (2026-06-10)
- **Two clocks: ingestion-time batch sync, query-time local search** · live query-time
  retrieval · fast (ms), reproducible, audit-safe; no query-time browsing/scraping ever
  (2026-06-10)
- **Stateless across runs** · cross-run memory/learning · valuations must be independent and
  reproducible (audit requirement); future: offline feedback loop tuning weights/prompts
  between versions (2026-06-10)
- **Owner legal/liens/credit risk deferred** · including it now · different underwriting step
  with different data; risk-rule registry keeps the door open (2026-06-10)
- **Fuzzy entity resolution out** · ML/fuzzy address matching · we control the synthetic mess;
  normalized-exact address join suffices and is unit-testable (2026-06-10)
- **Vite + React over Next.js** · Next.js · single page, thin client over the API; no SSR/
  routing need (2026-06-10)
- **Per-node model selection via env** · one model everywhere · Haiku where volume (intake,
  review fan-out), Sonnet where judgment (search, narrate); cost/latency control (2026-06-10)
- **Source precedence rules** · trusting one source or averaging · land-titles price > MLS
  price (registered legal record); assessment year-built > realtor-entered MLS; conflicts
  beyond tolerance recorded as flags, never silently resolved (2026-06-10)
- **Agentic widening capped at 2 rounds** · unbounded search loop · bounded cost and latency;
  deterministic fallback if the LLM fails (2026-06-10)
- **Time discipline: 12h hard cap, strict boxes, 2h reserve** · flexible scope · deadline is
  firm; every block has a pre-named escape hatch, overruns bill the reserve (2026-06-10)
- **Production connectors documented + verified, not built** · building live connectors ·
  hackathon scope; verified all three real channels exist and are batch-shaped (see §1
  production story), so the `CompSource` interface is the seam, not hand-waving (2026-06-11)
- **Bearspaw spread calibrated to 2.5 km** · leaving acreages on a 5 km disk · with 5 sales on
  5 km even the capped widening (radius ≤5, ≤2 rounds) usually found *zero* comps; the spec's
  thin-market story is "widen, log, lower confidence" — an estimate with caveats, not a
  shrug. Test bed must produce the designed behavior (2026-06-11)
- **T8 (API) built before T7 (LLM nodes)** · plan order · no ANTHROPIC_API_KEY on this
  machine yet; shipped the fully verifiable surface first, LLM judgment layered on top
  (2026-06-11)
- **Intake LLM never rewrites the subject** · plan's normalized_subject output · guardrail:
  engine inputs come from the form only; the LLM contributes signals/concerns, not numbers —
  same principle as the narrate rule (2026-06-11)
- **Widening LLM chooses from engine-projected counts** · letting it reason blind · live
  verify caught it picking widen_radius twice on plausible-but-wrong intuition → 0 comps
  where the dumb fallback found 1. Now the engine pre-computes what every move would find
  and the LLM picks the best trade-off — judgment grounded in computed facts, the
  hybrid principle applied to search itself. Great video beat: round-2 reason cites
  projected yields (2026-06-11)
- **As-of date injected into every prompt** · assuming the model knows "now" · a review
  verdict called an April 2026 sale "in the future" (knowledge-cutoff artifact); all four
  prompts now carry TODAY (2026-06-11)
- **Widening action space is code-gated** · trusting the prompt alone · the LLM-on eval
  caught the agent accepting an EMPTY comp set while `relax_beds` provably projected 1 —
  a null result chosen over a flagged estimate. Now the engine doesn't offer
  `accept_results` when the set is empty and a move projects comps, capped moves aren't
  offered at all, and accept decisions are logged to the audit trail. The eval harness
  catching a live agent-judgment bug is itself a video beat: ground truth → scenario
  asserts → caught regression → guardrail (2026-06-11)
- **ML calibrates the engine, never replaces it (roadmap, no code now)** · training models on
  our synthetic data, or a black-box AVM as the estimate · synthetic-trained ML would just
  reverse-engineer our own generator (circular metrics); a lender needs every dollar traceable
  to a named comp. Verified-workable upgrades, in order: (1) subscribe `MARKET_TREND_QOQ` to
  CREA/Teranet HPI — config already anticipates it; (2) fit `ADJ` coefficients by hedonic
  regression on licensed Pillar 9 solds (~25–30k Calgary sales/yr; adjustment ladder is
  already linear, so fitted coefficients are a drop-in config change); (3) GBM AVM as a
  divergence tripwire — one appended risk rule + one optional context field; (4) learn
  `WEIGHTS` from comps chosen in KV's own appraisal archive (proprietary label source no
  competitor has) — furthest out, needs PDF extraction pipeline (2026-06-11)
- **Chat-hybrid UI: form in, transcript out** · full free-text chat intake · structured fields
  are the lender-grade input contract (typos must not move a valuation); the per-home session
  transcript + follow-up Q&A give the agent feel without a multi-turn intake loop (~4–6h +
  new failure modes, rejected the night before deadline). Sessions run in the background —
  leave, return, green done-badge (2026-06-11)
- **Address intake is display + cross-check, not geocoding** · pretending to geocode against
  synthetic geography · deterministic community auto-fill from the typed address; mismatches
  flagged twice (form warning + intake contradiction signal); a wrong address can never move
  the number — community + attributes stay the only engine inputs. Production: geocoder →
  lat/lon → the *existing* haversine filter, zero engine changes (2026-06-11)
- **What-if = visible field diff + fresh linked run** · chat silently mutating inputs, or the
  LLM "adjusting" the estimate · `/api/ask` returns a modified subject; the diff is computed
  in code, shown in the transcript, and run as a separate linked session through the normal
  pipeline — every what-if is a full audited evaluation (2026-06-11)
- **Human disagreement = challenge → agent re-review, not click-override** · an exclude
  button that flips verdicts and recomputes · Bo's call: a click that overrules the agent
  with no argument makes agent judgment decoration. The reviewer states a claim in chat; the
  agent re-reviews that comp with the claim as evidence and either revises (engine recomputes,
  reversal logged) or defends (objection recorded in the report) — mirrors real appraisal
  review (comments back to the appraiser, revise-or-rebut). Production backstop: licensed
  sign-off with mandatory written justification (2026-06-11)
- **AVM stand-in = transparent $/sqft market norm, never a trained fake** · GBM trained on
  synthetic data as an "independent" cross-check · trained on data our own price model
  generated, it would always agree — the divergence flag would never fire; theater. A median
  $/sqft yardstick is honest (labeled what it is), genuinely diverges on planted cases, and
  exercises the exact production seam: independent estimator → disagreement becomes a risk
  flag, never a replacement estimate (2026-06-11)
- **Free-text intake = extract-to-form, geocoding = constrained LLM inference** · full
  chat intake, or an external geocoder API · the paste box prefills the *form* and the
  human confirms it before anything runs — extraction proposes, never feeds the engine
  (same pattern as the what-if diff). Community inference is constrained to the dataset's
  8 communities or null, labeled "inferred — verify"; an external geocoder would add an
  API key + network dependency on demo day to answer a question the 8-community store
  doesn't ask. Production swaps the inference call for a real geocoder, wiring unchanged
  (2026-06-12)
- **Chat history resolves references; actions consume only logged artifacts** · letting the
  conversation directly shape what-ifs/re-reviews · "ok, run it" needs history to resolve
  "it" — but the change set must come from the latest message and the re-review sees only
  the distilled, logged claim (never the chat). Conversation carries intent to the doorway;
  only an explicit, visible artifact (field diff / challenge claim) walks through. Dumb
  questions stay inert: chat has no write path to results except the two audited doors
  (2026-06-12)
- **Method/market questions answered in every session chat, grounded** · a separate general
  chat, or free general-knowledge opinions · questions arise in context ("what does B
  mean?" while looking at a B); grounding = methodology generated from config constants +
  the store's community stats, so answers can't drift from code or data. Open-ended
  real-estate opinions stay excluded — ungrounded claims next to audited numbers would blur
  the product's trust boundary. Standalone help chat = production roadmap (2026-06-12)
- **Chat memory scoped to the session; cross-session/cross-run memory excluded by design**
  · agent remembering conversations across homes and runs · every answer must be
  reproducible from that home's report alone (audit); roadmapped as needs-driven:
  explicit compare-two-sessions command + challenge patterns feeding the offline tuning
  loop — implicit memory stays out (2026-06-12)
- **Time-log total = wall-clock union of intervals, with a per-row `Counted` column** ·
  summing raw row durations · parallel/overlapping sessions double-bill the 12h cap (Bo
  caught a real 0.1h double-count). Rows keep their true Duration; `Counted` carries the
  net contribution (overlap attributed to the earliest row), so the total audits as one
  column sum (2026-06-11)
- **User feedback = capture-only signal; weights retune only through the eval loop** ·
  letting ratings tune the engine directly, or skipping feedback entirely · feedback is a
  weak, biased label (anchoring on the shown estimate, selection, owner optimism) — it
  *localizes* error, never moves a weight. S9 captures self-contained (input, output,
  human label) lines to `feedback.jsonl` (snapshot of the valuation as displayed at rating
  time, comp ids + scores included, so each line is a joinless training example); S10's
  deterministic report slices user-vs-engine deltas by confidence/community/flags and
  names the `config.py` knob to investigate; `eval.calibrate` proposes rates,
  `eval.eval` validates against ground truth. Feedback proposes, eval disposes
  (2026-06-12)
- **Chat grounding = context injection, not LLM tools (Bo's question, post-S5)** · exposing
  methodology/market stats as callable tools · a tool the model may not call can silently
  skip grounding — a plausible, ungrounded answer with no failure signal; injected context
  is structurally always present. The data is tiny and static (~1.5k tokens of constants +
  8 stat rows), so retrieval round-trips buy nothing. Division of labor the codebase
  follows: tools where the model *chooses actions* (search widening picks among
  engine-projected moves) · injection where facts must always be present (methodology,
  market stats) · typed-JSON-to-code where anything *mutates results* (what-ifs,
  challenges — the audited doors). Flips when grounding outgrows the prompt (comp-store
  queries, handbook search, HPI lookups): then a read-only retrieval tool layer is right,
  mutations stay code-dispatched. Production-note line for README at S9 (2026-06-12)
- **Similarity recency weight kept at 20/100 (Bo's #17)** · weighting recent sales harder ·
  the engine already *corrects* old prices forward via the trend index, so recency's job is
  only the uncertainty correction can't fix (regime shifts, index lag); more recency weight
  helps hot markets but starves thin ones (Bearspaw) of comps. Right answer is per-market
  learned profiles = roadmap; today's weights validate against ground-truth eval, and
  deadline-day retunes on vibes are how you make things worse (2026-06-12)

---

## §3 Work log

- **2026-06-10** — Design spec written and locked
  (`docs/specs/2026-06-10-comp-analysis-agent-design.md`): scope, architecture, data design,
  agent graph, eval plan, time boxes with escape hatches. CLAUDE.md initialized.
- **2026-06-11** — Data + engine foundation, 70 tests green:
  - T0 backend scaffold (uv, Python 3.12, contracts)
  - T1 canonical `PropertyRecord` schema + address normalization
  - T2 seeded synthetic generator with ground-truth price model; planted edge cases
    (non-arm's-length, thin market, luxury outliers, quick flips, price/year conflicts,
    stale-comps pocket)
  - T3 source adapters + merge with field-level provenance → `comps.parquet`
    (6,290 records, 2,603 scorable)
  - T4 deterministic comp filtering + similarity scoring (`96f037c`)
  - T5 adjustment-based valuation, confidence grading, risk-rule registry (`235b0bb`)
  - Production connector channels verified real (Calgary open data / Alberta VDA / Pillar 9)
  - T6 six-node LangGraph end-to-end in LLM-off mode (`cec2acb`): widening loop with caps,
    Send fan-out review, valuation + risk flags; Evanston = clean A-grade run, Bearspaw =
    2 widening rounds → 1 comp → C-grade with THIN/STALE/EXTRAPOLATION/WIDENED flags
  - T8 FastAPI: `GET /api/communities` + `POST /api/evaluate` SSE stream (`9589296`);
    73 tests green
  - T7 LLM judgment nodes (`a7f0e32`): intake signal mining, widening via genuine
    tool-calling (bind_tools + accept_results, reasons logged verbatim), per-comp review
    with deterministic pre-checks, streamed narration with the only-numbers-from-the-data-
    block rule; every node degrades to its deterministic fallback on LLM failure (tested
    with fake/raising models, 81 tests). Live-LLM run pending an API key
  - T9 single-page Vite UI (`d22237a`): form with demo presets, live agent timeline with
    fallback badges, valuation banner with range bar + confidence + flag chips, comp table
    with expandable adjustment ladder + per-field provenance badges, streaming narrative
    panel. Verified live in the browser (LLM-off), screenshots captured
  - T10 eval harness (`d91c4c1`): 20 held-out subjects → **MAPE 2.1%, 19/19 within ±10%**,
    scenario asserts green; results in `backend/eval/results.md`
  - T7 live-LLM verification complete (`f6c69d3`, `db4985d`): three field findings fixed —
    projections-informed widening, as-of date in prompts, action-space gating after the
    eval caught an empty-set accept. ~13s/run with streaming
  - LLM-on eval (`abd9547`): **MAPE 2.2%, 20/20 within ±10%, median 1.4%**, Bearspaw
    estimated where deterministic couldn't; all scenario asserts green
- **2026-06-11 (evening)** — UX addendum designed and approved via browser-mockup brainstorm
  (`docs/specs/2026-06-11-sessions-chat-ui-design.md`): per-home sessions with background runs,
  chat-hybrid transcript with pinned hero valuation card, address intake + community auto-fill
  + mismatch guards, `/api/ask` follow-up Q&A with what-if re-runs. Boxed 3.0h (F1–F4), 4-step
  cut ladder armed. Build pending
- **2026-06-11 (late evening)** — Time-log accounting audit: fixed a 0.1h overlap double-count,
  reworked totals to wall-clock union of intervals with a per-row Counted column. 5.3h of 12h
  cap used, 2.0h reserve intact
- **2026-06-11 (night)** — UX addendum F1–F4 built and live-verified (~1.0h vs 3.0h boxed,
  93 tests green, survived a 3h usage-limit gap mid-build via the plan's resume protocol):
  - F1 address intake: schema passthrough + deterministic community auto-fill + form
    mismatch warning + intake LLM cross-check (found live: address-only subjects skipped
    the LLM pass entirely — prompt restructured to two independent jobs, verified both
    directions)
  - F2 sessions + chat transcript + pinned hero valuation card (key-factors line,
    flags as sentences, evaluated-at/as-of/duration, built-year in every recap, Adjusted $
    column + similarity-breakdown chips in the comp table); background runs with done-●
    badge; localStorage persistence with clobber guard. Bonus: fixed latent narrative
    double-emit (streamed tokens + node-completion re-send — invisible until LLM-on UI use)
  - F3 `/api/ask` + per-session chat: grounded answers (live test cited the 3 conflicted
    comps and the demoted comp's 44.62 score from context); what-if "triple garage?" →
    diff chip `garage_stalls: 2 → 3` → linked session → **engine** moved the estimate
    +$10k ($629,679 → $639,679) — the guardrail story, demonstrated
  - F4 eval guard: 20/20 within ±10% held (MAPE 2.5% this run vs 2.2% recorded —
    run-to-run review-verdict variance, engine identical; official results.md kept);
    2 new screenshots in docs/images; README updated (sessions/chat section, production
    notes: geocoder seam, server-side run state, sign-off backstop)
- **2026-06-12 (after midnight)** — Stretch queue S1–S3 all landed (~0.4h vs 2.25h boxed,
  100 tests):
  - S1 comp challenge → re-review: live test "comp 2 backs onto a highway" → agent
    re-reviewed with the claim as evidence → exclude with reasoning → engine
    re-reconciled → hero card "⚖ challenge applied — revised from $639,679 (B)",
    original preserved, exchange in transcript. Video beat: human gives *evidence*,
    agent re-judges, engine recomputes — nobody edits a number
  - S2 `BASELINE_DIVERGENCE` risk rule: median-$/sqft yardstick × subject size vs the
    estimate; ±15% tolerance, silent under 5 sales (thin-market yardsticks are noise)
  - S3 calibration demo (`eval/calibration.md`): hedonic fit on 2,603 sales, **R² 0.976**,
    recovers bed $8,185 vs config $8,000 · garage $11,596 vs $10,000 · lot $2/sqft exact ·
    trend ≈1.1%/q vs 1.2% config; honest note on marginal-vs-full $/sqft. Roadmap item 2
    as running code
- **2026-06-12 (afternoon)** — Design block (#17/#18): similarity/recency question settled
  (keep weights, three-rung adjustability story) · S9 feedback capture + S10 feedback
  report designed and queued (spec §8) · final build order locked:
  S5 → S9+S10 → S7 → S8 → S6, Bo reviews after each item
- **2026-06-12 (afternoon)** — S5 chat grounding + prompt hardenings (`d232990`, TDD,
  114 tests): methodology block generated from `engine/config.py` + risk-rule registry
  (a test forces every registered rule to appear — new rule without a meaning fails CI);
  `/api/ask` now carries METHODOLOGY + MARKET STATS; what-ifs scoped to the latest
  message; challenge claims weighed as unverified. Live: "how do you adjust for an older
  sale?" → answer cites Evanston 1.2%/quarter, 20-pt recency, 365-day decay — every
  number config-true; Toronto investment question politely declined. Video beat: ask the
  agent *how its own math works* and it answers from the engine's constants, not vibes
- **Remaining**: build queue above (~3.25h boxed) · T11 video (Friday, protected 1.5h box)
  + GitHub repo push · final read-through
