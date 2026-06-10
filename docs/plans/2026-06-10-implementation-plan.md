# KV Comp-Analysis Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Spec (the contract): `docs/specs/2026-06-10-comp-analysis-agent-design.md`. TDD on all
> engine/ingestion code; LLM nodes get fallback-path tests, not LLM-output tests.

**Goal:** Working comp-analysis agent — form in, ranked comps + valuation + narrative out — per approved spec, within ~8.5 build hours.

**Architecture:** Offline synthetic 3-source data → ingestion/merge with provenance → deterministic engine (filter/score/adjust/value/flags) wrapped by a 6-node LangGraph agent (LLM = judgment + language only) → FastAPI SSE → single-page React UI.

**Tech Stack:** Python 3.12 + uv · pydantic v2 · pandas/pyarrow · LangGraph + langchain-anthropic · FastAPI/uvicorn · pytest || Vite + React + TS + Tailwind.

**Time boxes are hard:** if a task hits its box, ship the escape hatch named in the task and move on. Update `TIMELOG.md` at every task boundary. Commit after every green test run.

---

## File map (decomposition locked)

```
backend/
  pyproject.toml                  # uv project; deps pinned here
  app/main.py                     # FastAPI app, CORS, startup: build comps.parquet if missing
  app/api.py                      # GET /api/communities · POST /api/evaluate (SSE)
  app/events.py                   # SSE event dataclasses + serializer
  agent/state.py                  # AgentState TypedDict + node I/O models
  agent/graph.py                  # StateGraph wiring, conditional edges, Send fan-out
  agent/llm.py                    # model factory: per-node env override, Haiku/Sonnet defaults
  agent/nodes/intake.py           # LLM: validate + notes → signals; fallback: skip notes
  agent/nodes/search.py           # code search + LLM widening (≤2 rounds); det. fallback
  agent/nodes/review.py           # Send fan-out worker + pre-checks; fallback: keep+unreviewed
  agent/nodes/narrate.py          # streamed narrative; fallback: table-only
  agent/prompts/{intake,search,review,narrate}.md
  engine/config.py                # ALL tunables: weights, rates, filters, confidence cuts
  engine/filters.py               # hard filters + widening moves (pure)
  engine/scoring.py               # similarity 0-100 (pure)
  engine/valuation.py             # adjustments + weighted estimate + confidence (pure)
  engine/risk_rules.py            # RiskFlag + rule registry (pure)
  data/schema.py                  # PropertyRecord, SubjectProperty, normalize_address()
  data/price_model.py             # ground-truth coefficients + price() — reused by eval
  data/generate.py                # CLI: world → mls_sales/land_titles/assessments CSVs
  data/sources/{mls,land_titles,assessments}.py   # adapters → canonical frames
  data/merge.py                   # join + precedence + conflicts → comps.parquet
  data/store.py                   # CompSource protocol + SyntheticDataSource (async fetch)
  eval/eval.py                    # 20 held-out subjects → MAPE, recovery, scenario asserts
  tests/test_{schema,generate,merge,filters,scoring,valuation,risk_rules,graph,api}.py
frontend/
  src/App.tsx                     # layout: form left, timeline+results right
  src/api.ts                      # SSE client (fetch + ReadableStream parse)
  src/types.ts                    # mirrors backend event/response shapes
  src/components/{SubjectForm,AgentTimeline,ValuationBanner,CompTable,NarrativePanel,FlagChips}.tsx
```

---

## Shared contracts (later tasks MUST match these exactly)

```python
# data/schema.py
class PropertyRecord(BaseModel):
    address_key: str            # normalized join key
    address: str                # display form
    community: str
    property_type: Literal["detached", "semi", "townhouse", "apartment"]
    beds: int | None            # above grade
    beds_bsmt: int = 0
    baths: float | None
    sqft: int | None
    lot_sqft: int | None
    year_built: int | None
    garage_stalls: int = 0
    lat: float
    lon: float
    sold_price: int | None      # None for assessment-only rows
    sold_date: date | None
    assessed_value: int | None
    sources: dict[str, str] = {}     # field -> "mls" | "land_titles" | "assessment"
    conflicts: list[Conflict] = []

class Conflict(BaseModel):
    field: str; values: dict[str, float | int | str]; resolved_with: str

class SubjectProperty(BaseModel):
    community: str; property_type: str; beds: int; baths: float
    sqft: int; year_built: int
    lot_sqft: int | None = None; garage_stalls: int = 0; notes: str = ""

# engine/risk_rules.py
class RiskFlag(BaseModel):
    code: str; severity: Literal["info", "caution", "warning"]
    message: str; evidence: dict = {}
RISK_RULES: list[Callable[[ValuationContext], RiskFlag | None]]   # the registry

# agent/state.py
class AgentState(TypedDict, total=False):
    subject: SubjectProperty
    notes_signals: list[str]
    criteria: SearchCriteria          # radius_km, days, sqft_pct, beds_delta
    search_log: list[dict]            # {round, criteria, found, reason}
    candidates: list[PropertyRecord]
    scored: list[ScoredComp]          # comp + score + score_parts
    reviews: list[ReviewVerdict]      # {address_key, verdict: keep|demote|exclude, reason, unreviewed: bool}
    valuation: Valuation              # estimate, low, high, confidence, per-comp adjustments
    risk_flags: list[RiskFlag]
    narrative: str
    errors: list[str]
```

```python
# engine/config.py — single home for every tunable (values final unless eval disproves)
WEIGHTS = {"distance": 25, "recency": 20, "sqft": 20, "beds_baths": 10,
           "year_built": 10, "lot": 5, "garage": 5, "same_community": 5}
FILTER_DEFAULTS = dict(radius_km=2.0, days=180, sqft_pct=0.25, beds_delta=1)
WIDENING_MOVES = {"extend_days": (+90, 365), "widen_radius": (1.5, 5.0),
                  "relax_sqft": (0.35,), "relax_beds": (2,)}   # (step, cap)
MIN_COMPS, TOP_N_REVIEW, MAX_WIDEN_ROUNDS = 5, 8, 2
ADJ = dict(ppsf_marginal=0.5, bed=8_000, bath=6_000, garage=10_000,
           age_per_year=800, age_cap=20_000, lot_per_sqft=2.0, lot_deadband=2_000)
CONFIDENCE = dict(A=dict(min_comps=6, max_iqr=0.06, min_sim=75),
                  C=dict(max_comps=3, min_iqr=0.12))           # B = else
NON_ARMS_LENGTH_RATIO = 0.75    # price/assessed below this ⇒ suspect
PRICE_CONFLICT_TOL = 0.005      # >0.5% MLS vs land-titles delta ⇒ Conflict
```

```python
# data/price_model.py — ground truth (generator + eval share this)
BASE_PPSF = {  # (community, type) -> $/sqft; types absent = not generated
  "Beltline": {"apartment": 420}, "Bridgeland": {"apartment": 440, "townhouse": 390},
  "Killarney": {"semi": 460, "detached": 510}, "Tuscany": {"detached": 350},
  "Evanston": {"detached": 330, "townhouse": 310},
  "Auburn Bay": {"detached": 360, "townhouse": 330},
  "Aspen Woods": {"detached": 520}, "Bearspaw": {"detached": 480}}
PREMIUMS = dict(bed=9_000, bath=7_000, garage=11_000, bsmt_finished=25_000)
AGE_DEP_PER_YEAR, AGE_DEP_CAP = 850, 22_000
LOT_PER_SQFT = 2.2                     # beyond community-typical lot
TREND_QoQ = {c: 0.012 for c in BASE_PPSF} | {"Beltline": 0.018, "Bearspaw": 0.006}
NOISE_SD = 0.04                        # Aspen Woods: 0.10
def true_price(attrs, sold_date) -> int: ...   # the formula in spec §3
```

SSE events (`app/events.py`, mirrored in `frontend/src/types.ts`):
`node {node, status: started|done|fallback, detail?}` · `search_update {round, criteria, found, reason}` ·
`comps {items: ScoredComp[]}` · `reviews {items: ReviewVerdict[]}` ·
`valuation {estimate, low, high, confidence, flags: RiskFlag[], adjustments: per-comp rows}` ·
`narrative_delta {text}` · `done {run_id, timings}` · `error {message, recoverable}`

---

### Task 0: Scaffold (box: 15 min)

- [ ] `cd backend && uv init --python 3.12`; add deps: `pydantic pandas pyarrow langgraph langchain-anthropic langchain-core fastapi uvicorn[standard] sse-starlette python-dotenv pytest pytest-asyncio httpx`
- [ ] Create the file-map directory tree with empty `__init__.py`s; copy contracts above into `data/schema.py`, `engine/config.py`, `agent/state.py` (stubs for not-yet-defined types commented)
- [ ] `.env.example`: `ANTHROPIC_API_KEY=`, `LANGSMITH_TRACING=`, `LANGSMITH_API_KEY=`, `LANGSMITH_PROJECT=home-evaluator`, `INTAKE_MODEL=claude-haiku-4-5`, `SEARCH_MODEL=claude-sonnet-4-6`, `REVIEW_MODEL=claude-haiku-4-5`, `NARRATE_MODEL=claude-sonnet-4-6`
- [ ] `uv run pytest` → "no tests ran" (sanity) · Commit: `chore: backend scaffold`

### Task 1: Schema + address normalization (box: 30 min)

- [ ] Failing tests `tests/test_schema.py`:
  - `normalize_address("123 Evanston Way NW, Calgary") == normalize_address("123 EVANSTON WAY NW")`
  - `normalize_address("#301, 880 12 Ave SW") == normalize_address("UNIT 301 880 12 AVENUE SW")`
  - suffix/dir abbreviations (`Avenue→AVE`, `Northwest→NW`), unit prefixes (`#|UNIT|APT`), punctuation/case stripped, city dropped
  - `PropertyRecord` round-trips with empty `sources`/`conflicts` defaults
- [ ] Implement `normalize_address` (regex table, ~30 lines) + models → green · Commit: `feat: canonical schema + address normalization`

### Task 2: Ground-truth world + 3-source generator (box: 45 min)

- [ ] `data/price_model.py` per contract. Test: `true_price` of a known fixture (Evanston detached, 1850 sqft, 3bd/2.5ba, 2021, garage 2, ~Q1-2026) lands in $580k–$660k; newer-sold > older-sold for identical attrs (trend works)
- [ ] `data/generate.py --seed 42 --out data/raw/`: per spec §3 — communities/volumes table, lat/lon = centroid + jitter, attrs drawn per community/type ranges, price = `true_price`×(1+ε). Plant edge cases per spec table (non-arm's-length: land-titles only + price×0.5–0.7; Bearspaw ~5 sales; flips ×2; price conflicts ~5% at 1–3%; year_built conflicts ~5% at 2–5y; one stale Tuscany pocket). Emit:
  - `mls_sales.csv` — realtor address ("123 Evanston Way NW, Calgary"), `beds` like `"3+1"`, baths, sqft, garage, list/sold price, sold date. EXCLUDES private sales
  - `land_titles.csv` — legal-ish address ("PLAN 123 BLK 4 LOT 56; 123 EVANSTON WAY NW"), transfer price/date for EVERY sale
  - `assessments.csv` — abbreviated address ("123 EVANSTON WY NW"), year built, lot sqft, assessed value, EVERY property
- [ ] Test `tests/test_generate.py`: row counts per community ±20% of spec; ≥1 of each edge case present (query the frames); determinism (two runs, same seed ⇒ identical hashes)
- [ ] Commit: `feat: synthetic 3-source Calgary dataset with planted edge cases`

### Task 3: Adapters + merge with provenance (box: 45 min)

- [ ] Failing tests `tests/test_merge.py` (build tiny hand-written 3-source fixture, NOT generated data):
  - join hits across all 3 address formats
  - price precedence: land_titles wins; >0.5% delta ⇒ `Conflict(field="sold_price")` recorded
  - year_built precedence: assessment wins over MLS
  - `"3+1"` → `beds=3, beds_bsmt=1`
  - private sale (land-titles only, no MLS) → record with `sold_price` set, `sqft=None` ⇒ `complete_for_comps == False`
  - `sources` maps every populated field to its origin
- [ ] Implement `data/sources/*.py` (each: read CSV → canonical frame) + `data/merge.py` (outer join on `address_key` + precedence + conflicts; writes `comps.parquet`) → green
- [ ] Run on generated data: `uv run python -m data.merge` → log row count, % merged from 3/2/1 sources · Commit: `feat: multi-source ingestion with field provenance`

### Task 4: Filters + similarity scoring (box: 40 min)

- [ ] Failing tests `tests/test_filters.py`, `tests/test_scoring.py`:
  - filters: type must match; haversine radius; days window; sqft band; beds delta; incomplete records excluded
  - widening: each move respects its cap; `apply_move` is pure (returns new criteria)
  - scoring monotonicity: same comp moved farther/staler/more-different-sqft ⇒ strictly lower score; identical twin scores 100±ε; weights sum check
  - `score_parts` returned per dimension (UI + narrative need the breakdown)
- [ ] Implement (pure pandas/numpy; haversine inline ~6 lines) → green · Commit: `feat: deterministic comp filtering and similarity scoring`

### Task 5: Adjustments + valuation + risk rules (box: 50 min)

- [ ] Failing tests `tests/test_valuation.py` (hand-computed fixture of 6 comps — assert exact numbers), `tests/test_risk_rules.py`:
  - time adjustment uses community trend index between sold_date and today
  - direction tests: bigger comp adjusts DOWN toward subject, etc., for every ADJ term
  - estimate = similarity-weighted median of adjusted prices; range = weighted P25–P75
  - confidence: fixture hits A; drop to 3 comps ⇒ C; inflate dispersion ⇒ not A
  - each initial rule fires on a crafted context and stays silent otherwise: THIN_COMPS, HIGH_DISPERSION, NON_ARMS_LENGTH_EXCLUDED, DATA_CONFLICT, EXTRAPOLATION, STALE_COMPS, WIDENED_SEARCH
  - registry: appending a lambda rule gets evaluated (expandability proof)
- [ ] Implement `engine/valuation.py`, `engine/risk_rules.py` → green · Commit: `feat: adjustment-based valuation, confidence grading, risk-rule registry`

### Task 6: Graph skeleton — deterministic end-to-end (box: 40 min)

- [ ] `data/store.py`: `class CompSource(Protocol): async def fetch(criteria) -> list[PropertyRecord]` + `SyntheticDataSource(parquet_path)`
- [ ] `agent/graph.py`: full StateGraph with ALL SIX nodes wired (conditional search→widen edge, Send fan-out for review) but LLM nodes running their **deterministic fallbacks only** (env `AGENT_NO_LLM=1`): intake passes subject through; search widens in fixed order; review keeps all with `unreviewed=True`; narrate emits "" 
- [ ] Test `tests/test_graph.py` (asyncio, no API key needed): Evanston subject ⇒ valuation present, ≥5 comps, search_log has 0 rounds; Bearspaw subject ⇒ search_log shows widening rounds with caps respected, WIDENED_SEARCH + THIN_COMPS flags present; non-arm's-length comp absent from scored set
- [ ] Commit: `feat: agent graph runs end-to-end deterministically (LLM-off mode)`

### Task 7: LLM nodes + prompts (box: 80 min) — *hatch: batched review (one call), 1-round widening*

- [ ] `agent/llm.py`: `get_model(node)` → `ChatAnthropic` from `{NODE}_MODEL` env; defaults per contract
- [ ] Prompts (`agent/prompts/*.md`): per spec §5 — each ends with explicit JSON-only output schema. `narrate.md` includes the methodology section + hard rule "use ONLY numbers provided in the data block"
- [ ] `intake`: structured output `{normalized_subject, signals: list[str], concerns: list[str]}`; on exception → fallback + `node fallback` event
- [ ] `search`: when thin, LLM picks ONE move from WIDENING_MOVES with reason (JSON); cap rounds; on exception → deterministic order
- [ ] `review`: worker prompt gets comp + score_parts + deterministic pre-check results (price/assessed ratio, conflicts, flip flag); JSON verdict; per-worker exception → keep+unreviewed
- [ ] `narrate`: streamed via `astream`; receives subject, scored+reviewed comps, valuation, flags
- [ ] Manual verify (needs key): `uv run python -m agent.run_demo` (tiny CLI runner printing events) on 3 subjects: normal Evanston / Bearspaw widening / notes-rich ("backs onto golf course, unfinished basement"). Check: latency ≤~10s, narrative cites only real numbers, review excludes planted non-arm's-length when present
- [ ] Commit: `feat: LLM judgment nodes with deterministic fallbacks`

### Task 8: FastAPI + SSE (box: 40 min)

- [ ] Failing test `tests/test_api.py` (httpx, `AGENT_NO_LLM=1`): `GET /api/communities` ⇒ 8 communities with stats; `POST /api/evaluate` ⇒ event stream containing `node`, `comps`, `valuation`, `done` in order; invalid subject ⇒ 422
- [ ] Implement `app/main.py` (startup: ensure parquet; CORS for :5173), `app/api.py` (graph `astream_events` → SSE via sse-starlette), `app/events.py` → green · Commit: `feat: SSE evaluate endpoint`

### Task 9: Frontend (box: 90 min) — *hatch: Streamlit page hitting same API*

- [ ] Scaffold: `npm create vite@latest frontend -- --template react-ts`; Tailwind v4; `vite.config` proxy `/api`→`:8000`
- [ ] `src/types.ts` mirroring event shapes; `src/api.ts` SSE reader (`fetch` + ReadableStream line parser, `onEvent` callback)
- [ ] Components per spec §7: SubjectForm (communities from API; sensible defaults so demo is 2 clicks) · AgentTimeline (event feed: node status lines, search rounds with reasons, fallback badges) · ValuationBanner (estimate, range bar, confidence A/B/C badge, FlagChips with severity colors) · CompTable (rank, address, sold price/date, attrs, similarity with parts on hover, review verdict chip; expandable row → adjustment ladder + provenance badges per field) · NarrativePanel (streaming markdown via `react-markdown`)
- [ ] Manual verify: full run against live backend, normal + Bearspaw subjects; check stream renders progressively · Commit: `feat: single-page UI with live agent timeline`

### Task 10: Eval + results (box: 30 min) — *hatch: drop table, keep scenario asserts in pytest*

- [ ] `eval/eval.py`: 20 seeded subjects (NOT in sales data) priced by `true_price` → run graph (LLM on) → report: MAPE, median |error|, % within ±10%, comp-recovery@8 vs model-nearest-10, scenario asserts (Bearspaw widened ∧ flagged; non-arm's-length excluded; conflict flagged) → markdown table to stdout + `eval/results.md`
- [ ] Run; paste table into README draft; if MAPE >8% on normal cases, single tuning pass on `WEIGHTS`/`ADJ` only · Commit: `feat: eval harness + results`

### Task 11: README + demo video (box: 90 min, Friday, protected)

- [ ] README per spec §9 sections — includes architecture diagram (mermaid), eval table, "what I cut and why", production data plan (Pillar 9/SPIN2), extension points, time log summary
- [ ] `git remote add origin` (user creates public GitHub repo) + push
- [ ] User records ≤3-min video per spec outline; link in README · Final commit + push

---

## Self-review (done)

- **Spec coverage:** §3→T2, §4→T1+T3, §5→T6+T7, §6→T5+T10, §7→T8+T9, §8→T5 registry test + prompts-as-files + CompSource protocol, §9→boxes/hatches mirrored. Sam call: dropped by user decision.
- **Type consistency:** contracts block is single source; tasks reference, never redefine.
- **Placeholders:** prompts' full prose and React markup intentionally authored at execution (creative content, contracts pinned here) — bounded by explicit acceptance checks in T7/T9.
- **Budget:** T0–T10 ≈ 6.9h + T11 1.5h = 8.4h ≤ 9.5h remaining (incl. 1h user reserve untouched).
