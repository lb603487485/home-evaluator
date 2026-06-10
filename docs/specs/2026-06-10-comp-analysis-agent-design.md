# Spec — KV Comp-Analysis Agent (home-evaluator)

**Date:** 2026-06-10 · **Deadline:** Fri 2026-06-12, 11:59 PM MST (firm)
**Budget:** 11h planned + 1h user reserve · **Submission:** public GitHub repo + README + ≤3-min demo video

---

## 1. Problem & scope

KV Capital underwrites loans to Alberta home builders. The bottleneck is **comp analysis**:
finding comparable recent sales across multiple sources and reasoning to a value estimate.

**In scope (prototype):**
- Residential properties, Calgary communities (synthetic data, real community names)
- Input: listing-style form (community, type, beds, baths, sqft, year built, lot, garage) + free-text notes
- Output: ranked comps with similarity scores, per-comp review verdicts, adjustment math,
  valuation estimate + range + confidence grade + risk flags, appraiser-style narrative
- Multi-source ingestion with provenance (the actual pain point — demonstrated, not just claimed)

**Out of scope (named in README "what I cut", all reachable via extension points §8):**
- Borrower/owner legal status, title encumbrances, credit checks (different underwriting step, different data)
- Commercial properties
- Live data connectors (MLS/Pillar 9, SPIN2) — production story documented instead
- Fuzzy entity resolution (we control synthetic mess; normalized-exact address join suffices)
- Self-improving agent loops (future work: LangSmith datasets + LLM-as-judge)
- RAG/vector retrieval — wrong tool for structured numeric comps (exact predicates + auditable
  scoring beat cosine similarity); belongs later as semantic re-rank over unstructured listing
  remarks/appraisal docs, as an enrichment signal inside score/review

**Why synthetic data:** Alberta sold prices are locked behind Pillar 9/land titles (verified:
Calgary open data has no sales, no interior attributes). That lock-up *is* the business problem.
We synthesize a ground-truth world — which also gives us provable ranking quality (§6).

---

## 2. Architecture overview

```
                    ┌─ data layer (offline, §3) ─────────────────────┐
 ground-truth model │ mls_sales.csv  land_titles.csv  assessments.csv │
                    └───────┬────────────┬───────────────┬───────────┘
                       adapters → canonical PropertyRecord → merge+provenance (§4)
                                        │  (comps.parquet)
                                        ▼
 user form ──► FastAPI ──► LangGraph agent (§5)
                │            intake → search ⇄ widen → score → review ×N → valuate → narrate
                │            (Haiku)  (code+Sonnet)   (code)  (Haiku ∥)    (code)    (Sonnet)
                ▼
            SSE stream ──► React/Vite single page (§7): live timeline + comps + narrative
```

**Two clocks:** data is acquired at *ingestion time* (offline batch — prototype: startup build;
production: scheduled sync from licensed feeds, never query-time browsing/scraping), while the
agent at *query time* searches the local merged store in milliseconds. Live retrieval, if ever,
is a future enrichment adapter — freshness add-on, not foundation.

Principles:
- **LLM never produces a number that isn't traceable to the engine.** Math = pure code, tested.
  LLM = judgment (search strategy, comp review, notes interpretation) + language (narrative).
- **Graceful degradation:** any LLM failure → deterministic fallback; user still gets ranked comps.
- **Per-node models** via env config (Haiku where volume, Sonnet where judgment). LangSmith tracing on.

---

## 3. Data layer (1.0h)

`backend/data/generate.py` — seeded, deterministic (`--seed 42`).

**Communities (8, real Calgary names, distinct profiles):**

| Community | Profile | Types | Approx sales/24mo |
|---|---|---|---|
| Beltline | inner-city condo towers | apartment | ~500 |
| Bridgeland | mixed condo/infill | apartment, townhouse | ~300 |
| Killarney | infill semis/detached | semi, detached | ~350 |
| Tuscany | 2000s suburban | detached | ~450 |
| Evanston | new-build suburban | detached, townhouse | ~500 |
| Auburn Bay | lake community | detached, townhouse | ~400 |
| Aspen Woods | luxury (outlier variance) | detached | ~150 |
| Bearspaw | acreage, **thin data** | detached | **~5** |

~2,700 sales over 24 months. Each property: lat/lon (community centroid + jitter) so radius
search is real geometry.

**Ground-truth price model** (single source of truth, reused by eval):
```
price = base_ppsf[community][type] · sqft
        + bed/bath/garage premiums + finished-basement premium
        − age depreciation (capped) + lot premium
        × community quarterly trend factor × (1 + ε),  ε ~ N(0, 0.04)
```
Exact coefficients live in `backend/data/price_model.py` — plausible Calgary magnitudes
(e.g., Evanston detached ≈ $330/sqft; Beltline apartment ≈ $420/sqft incl. condo discount).

**Planted edge cases (the test bed):**

| Case | Mechanism | What the agent must do |
|---|---|---|
| Non-arm's-length transfers (~2%) | land-titles only, price ×0.5–0.7, no MLS record | detect (price/assessed < 0.75) and exclude, with reason |
| Thin market | Bearspaw: ~5 sales/24mo | widen search, log reasoning, lower confidence |
| Luxury outlier | Aspen Woods: ε ~ N(0, 0.10) | wider range, HIGH_DISPERSION flag |
| Quick flip | 2 properties sold twice <6mo apart, 2nd +25% | review flags suspicious appreciation |
| Price conflicts (~5%) | MLS sold_price ≠ land-titles price by 1–3% | precedence: land titles; DATA_CONFLICT flag |
| Year-built conflicts (~5%) | MLS realtor-entered year off by 2–5 yrs | precedence: assessment |
| Stale-only comps | one Tuscany pocket: no sales <120d | STALE_COMPS flag, time adjustment does the work |

**Three emitted source files (different shapes, same world):**
- `mls_sales.csv` — beds (incl. "3+1" notation), baths, sqft, garage, sold price/date, realtor address format. Missing: private sales.
- `land_titles.csv` — EVERY transfer: legal address format, transfer price, date. No interior attributes.
- `assessments.csv` — every property: year built, lot size, assessed value, abbreviated address format. No sales.

---

## 4. Ingestion layer (1.0h)

`backend/data/sources/*.py` + `merge.py` → `comps.parquet` (built at startup or via CLI).

- **`CompSource` interface** (async `fetch(criteria) -> list[PropertyRecord]`): one implementation
  today (`SyntheticDataSource` over the merged table); production = N adapters queried with
  `asyncio.gather`. The interface is the multi-source story.
- **Canonical `PropertyRecord`** (pydantic): address_key, community, property_type, beds,
  beds_bsmt, baths, sqft, lot_sqft, year_built, garage_stalls, lat, lon, sold_price, sold_date,
  assessed_value, `sources: dict[field → origin]`, `conflicts: list[Conflict]`.
- **Address normalization** → join key (case, abbreviations, unit prefixes). Unit-tested.
- **Precedence:** land-titles price > MLS price; assessment year_built > MLS; MLS interior attrs
  (sole source). Conflicts beyond tolerance recorded, not silently resolved.
- Records missing core comp attributes (sqft, beds) — e.g., private sales with no MLS row —
  are excluded from scoring with a logged reason (they still feed non-arm's-length detection).

---

## 5. Agent graph (3.0h)

LangGraph `StateGraph`; state: subject, criteria, search_log[], candidates[], scored[],
reviews[], valuation, risk_flags[], narrative, errors[], timings.

| Node | Type / model | Behavior | On failure |
|---|---|---|---|
| **intake** | LLM · Haiku | validate form; parse notes → structured signals (e.g., "backs onto golf course" → qualitative premium note; "unfinished basement" → feature) | proceed without notes signals |
| **search** | code + LLM · Sonnet | filter via CompSource. If `< 5` comps: LLM picks ONE widening move/round from menu {extend window +90d (max 365), radius ×1.5 (max 5km), sqft ±35%, beds ±2} with stated reason; **max 2 rounds**; all logged | deterministic widening order (window → radius → sqft) |
| **score** | pure code | similarity 0–100, weights in `engine/config.py`: distance 25, recency 20, sqft 20, beds/baths 10, year 10, lot 5, garage 5, same-community 5. Top 8 → review | n/a (tested) |
| **review** | LLM · Haiku, **parallel Send fan-out** | per comp: deterministic pre-checks attached (price/assessed ratio, conflicts, flip history) → verdict `{keep, demote, exclude, reason}` | default keep + "unreviewed" tag |
| **valuate** | pure code | per-comp adjustments → time (trend index), sqft Δ·marginal ppsf, beds/baths/garage/age/lot; similarity-weighted median of adjusted prices; range = weighted P25–P75 widened by flag penalties; confidence A/B/C; risk-flag registry (§6) | n/a (tested) |
| **narrate** | LLM · Sonnet, streamed | sections: subject → market context → comp rationale (cite scores/adjustments) → estimate + confidence → risk flags → methodology. Prompt hard rule: only cite provided numbers | emit table-only result |

Latency target: **≤ ~10s end-to-end** (intake ~1.5s + search ≤1 LLM call/round + review ∥ ~2.5s
+ narrate ~4s streamed). LangSmith tracing via env (`LANGSMITH_TRACING=true`).

**Confidence grading:** A = ≥6 comps ∧ IQR/median <6% ∧ avg similarity >75 · C = <4 comps ∨
IQR/median >12% ∨ widened twice · B = otherwise.

---

## 6. Risk-flag registry & eval

**Registry pattern (the expandability requirement):** each rule is
`(state) -> RiskFlag | None` with `code, severity ∈ {info, caution, warning}, message, evidence`;
rules registered in a list in `engine/risk_rules.py`. UI renders whatever arrives.

Initial rules: `THIN_COMPS`, `HIGH_DISPERSION`, `NON_ARMS_LENGTH_EXCLUDED`, `DATA_CONFLICT`,
`EXTRAPOLATION` (subject outside comp attribute range), `STALE_COMPS`, `WIDENED_SEARCH`.
Future rules (stretch/never): `TITLE_ENCUMBRANCE`, `OWNER_LEGAL_STATUS`, `FORCED_SALE_DISCOUNT` —
each = new rule fn + (if needed) new CompSource adapter. Zero engine changes.

**Eval (`backend/eval/eval.py`, 0.5h of §6's 1.5h):** 20 held-out subjects priced by the
ground-truth model (not present in sales data):
- valuation MAPE vs ground truth (target: <8% on normal cases)
- comp recovery: % of model-nearest-10 comps appearing in agent's top-8
- scenario asserts: Bearspaw widens ∧ flags; non-arm's-length excluded; conflict flagged
Output: markdown table → README.

**Tests (pytest, ~1h):** address normalization; merge precedence + conflict detection;
filter bounds + widening caps; scoring monotonicity (closer/more similar ⇒ ≥ score);
adjustment directions; non-arm's-length rule; flag triggers; valuation on a hand-computed fixture.

---

## 7. API & frontend (2.0h)

**FastAPI** (`backend/app/`):
- `GET /api/communities` → names + basic stats (form dropdown)
- `POST /api/evaluate` → **SSE stream**: `node` (status), `search_update` (round, criteria,
  found, reason), `comps` (scored list), `reviews` (verdicts), `valuation` (estimate, range,
  confidence, flags), `narrative_delta` (tokens), `done` (run_id, timings), `error`

**React + Vite + TS + Tailwind, single page**, thin client (frontend swap = rendering swap):
- `SubjectForm` (left) — dropdowns + numbers + notes textarea
- `AgentTimeline` — live node/search events as they stream (**the demo moment**)
- `ValuationBanner` — estimate · range · confidence badge · flag chips
- `CompTable` — rank, address, sold price/date, attrs, similarity, adjusted value, review
  verdict; expandable row = adjustment breakdown + per-field provenance badges
- `NarrativePanel` — streaming markdown

---

## 8. Extension points (0h — interface shape, not extra code)

1. **New data source** → implement `CompSource` adapter; merge/provenance unchanged
2. **New risk factor** → register rule fn in `risk_rules.py`
3. **Model swaps** → per-node env vars (`INTAKE_MODEL`, `REVIEW_MODEL`, …) — market-pilot pattern
4. **Frontend swap** → stable API contract; Next.js later = rendering swap
5. **New pipeline stage** → new LangGraph node (e.g., future title-check between review and valuate)
6. **Expert-editable instructions** → node prompts are files (`agent/prompts/`); the appraisal
   methodology guiding `narrate` can be revised by lending staff without code changes. If the
   product later grows into a multi-procedure underwriting copilot, these become true on-demand
   skills (one per procedure) with this pipeline as the comp-analysis skill's tool.

---

## 9. Time plan & escape hatches

| Block | Est | When | Overrun hatch |
|---|---|---|---|
| §3 Data generator | 1.0h | tonight | 6 communities, fewer edge-case types |
| §4 Ingestion | 1.0h | tonight | fixed precedence order, simpler conflicts |
| §5 Agent graph | 3.0h | Thu | review fan-out → single batched call; widening → 1 round |
| §7 API + Vite UI | 2.0h | Thu | Streamlit fallback (~30min, API unchanged) — fallback only, not the plan |
| §6 Tests + eval | 1.5h | Fri | keep ingestion+scoring tests; drop eval table |
| README + video | 1.5h | Fri | **sacred — never cut** |
| Reserve (user's) | 1.0h | — | spent only by user decision |

Checkpoint rule: Thu midday — if the graph isn't demo-able end-to-end, invoke §5/§7 hatches
immediately rather than Friday night.

**Stack:** Python 3.12 + uv · LangGraph + langchain-anthropic · FastAPI/uvicorn · pandas/pyarrow
· pydantic · pytest || Vite + React + TS + Tailwind. Models: Sonnet (`claude-sonnet-4-6`) for
search/narrate, Haiku (`claude-haiku-4-5`) for intake/review — all env-overridable.

**README sections:** problem understanding · approach + architecture diagram · demo gif ·
how to run · design decisions & tradeoffs · **what I cut and why** · eval results · what's next ·
time log. **Video (≤3min):** problem 15s → architecture 45s → normal demo 50s → edge-case demo
(widening + exclusion) 40s → eval table + next 20s.
