# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project

**home-evaluator** — AI comp-analysis agent for the KV Capital AI Engineer hackathon.
Given a subject property (form, paste-box extraction, or free-text notes), it retrieves and
ranks comparable sales from multi-source synthetic Alberta data, produces a valuation
estimate with confidence and risk flags, and explains its reasoning appraiser-style — in a
per-home session UI with follow-up Q&A, what-if re-runs, and comp challenges.

- **Deadline: Fri 2026-06-12, 11:59 PM MST (firm).** Budget 12h hard cap — see `TIMELOG.md`
  (Duration/Counted convention documented in its header).
- **Specs (the working contract):** `docs/specs/2026-06-10-comp-analysis-agent-design.md`
  (core) + `docs/specs/2026-06-11-sessions-chat-ui-design.md` (sessions/chat UX addendum;
  §8 holds the stretch queue + checkpoint protocol).
  Scope changes cost visible hours; check the specs' escape hatches before adding anything.
- Submission: public GitHub repo, README, ≤3-min demo video.

## Architecture (read the spec for detail)

- `backend/data/` — synthetic generator (seeded, ground-truth price model) emitting 3
  differently-shaped sources (MLS / land titles / assessments) + adapters + merge with
  field-level provenance → `comps.parquet`
- `backend/engine/` — **pure code, no LLM imports**: filters, similarity scoring, adjustments,
  valuation, risk-rule registry. Everything here is deterministic and unit-tested.
- `backend/agent/` — LangGraph graph: intake → search (agentic widening, ≤2 rounds) → score →
  review (parallel Send fan-out) → valuate → narrate (streamed). LLM = judgment + language only;
  **the LLM never produces a number the engine didn't compute.**
- `backend/app/` — FastAPI: `GET /api/communities` · `POST /api/evaluate` (SSE stream) ·
  `POST /api/ask` (grounded Q&A; what-if returns a code-computed subject diff; comp
  challenge re-runs the review + engine recompute) · `POST /api/extract` (paste-box →
  form prefill, community constrained to known list). Backend is stateless across runs.
- `frontend/` — Vite + React + TS + Tailwind: per-home **sessions** (multi-session store in
  `src/sessions.ts`, runs continue in background, completed sessions persist to
  localStorage), chat transcript + pinned hero valuation card, follow-up chat. The session
  object is the future DB schema; persistence is isolated in `loadSessions`/`persistSessions`.

## Commands

```bash
# backend (from backend/)
uv sync                          # install deps
uv run python -m data.generate --seed 42   # regenerate dataset
uv run uvicorn app.main:app --reload       # API on :8000
uv run pytest                    # all tests
uv run pytest tests/test_scoring.py -k monotonic   # single test
uv run python -m eval.eval       # eval vs ground truth → markdown table
uv run python -m eval.calibrate  # hedonic fit vs engine rates → eval/calibration.md
uv run langgraph dev --port 2025 # LangGraph Studio dev server (2024 is taken by another project)

# frontend (from frontend/)
npm install
npm run dev                      # UI on :5173 (proxies /api → :8000)
```

## Conventions

- Models per node via env (`INTAKE_MODEL`, `SEARCH_MODEL`, `REVIEW_MODEL`, `NARRATE_MODEL`,
  `ASK_MODEL`, `EXTRACT_MODEL`); defaults: Sonnet for search/narrate/ask/extract, Haiku for
  intake/review. `ANTHROPIC_API_KEY` required; `LANGSMITH_TRACING=true` optional.
- Prompts live in `backend/agent/prompts/` as files, not inline strings.
- Every LLM node has a deterministic fallback — a failed LLM call degrades the result,
  never 500s the request.
- Tunable engine constants (weights, adjustment rates, filter defaults) live in
  `backend/engine/config.py` — never scattered as magic numbers.
- **Time logging:** update `TIMELOG.md` at every work-block boundary (start/end/what).
  Time = wall-clock human-involved time (discussion, Bo's thinking/reading/review, Codex's
  work in session) — not just agent activity. Compare actual vs spec estimates; if a block
  overruns, invoke its escape hatch early.
- **Demo notes:** at the same boundaries, update `docs/demo-notes.md` — new decisions/trade-offs
  into §2, completed work into §3, video-worthy lines into §1. It accumulates; never rewrite it
  from scratch.
- Follow the workspace Karpathy guidelines (`../AGENTS.md`): surgical changes, no speculative
  features, state assumptions, verify before claiming done.
