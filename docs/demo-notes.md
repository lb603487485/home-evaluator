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
- **Remaining** (per spec §9): T7 LLM nodes + prompts (80m box; needs `ANTHROPIC_API_KEY` in
  `backend/.env` for live verify) · T9 Vite UI (90m) · T10 eval (30m) · T11 README + video (90m)
