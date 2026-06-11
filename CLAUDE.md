# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**home-evaluator** — AI comp-analysis agent for the KV Capital AI Engineer hackathon.
Given a subject property (form + free-text notes), it retrieves and ranks comparable sales
from multi-source synthetic Alberta data, produces a valuation estimate with confidence and
risk flags, and explains its reasoning appraiser-style.

- **Deadline: Fri 2026-06-12, 11:59 PM MST (firm).** Budget 11h + 1h reserve — see `TIMELOG.md`.
- **Spec (the working contract): `docs/specs/2026-06-10-comp-analysis-agent-design.md`.**
  Scope changes cost visible hours; check the spec's escape hatches before adding anything.
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
- `backend/app/` — FastAPI: `GET /api/communities`, `POST /api/evaluate` (SSE stream)
- `frontend/` — Vite + React + TS + Tailwind, single page, thin client over the API

## Commands

```bash
# backend (from backend/)
uv sync                          # install deps
uv run python -m data.generate --seed 42   # regenerate dataset
uv run uvicorn app.main:app --reload       # API on :8000
uv run pytest                    # all tests
uv run pytest tests/test_scoring.py -k monotonic   # single test
uv run python -m eval.eval       # eval vs ground truth → markdown table

# frontend (from frontend/)
npm install
npm run dev                      # UI on :5173 (proxies /api → :8000)
```

## Conventions

- Models per node via env (`INTAKE_MODEL`, `SEARCH_MODEL`, `REVIEW_MODEL`, `NARRATE_MODEL`);
  defaults: Sonnet for search/narrate, Haiku for intake/review. `ANTHROPIC_API_KEY` required;
  `LANGSMITH_TRACING=true` optional.
- Prompts live in `backend/agent/prompts/` as files, not inline strings.
- Every LLM node has a deterministic fallback — a failed LLM call degrades the result,
  never 500s the request.
- Tunable engine constants (weights, adjustment rates, filter defaults) live in
  `backend/engine/config.py` — never scattered as magic numbers.
- **Time logging:** update `TIMELOG.md` at every work-block boundary (start/end/what).
  Time = wall-clock human-involved time (discussion, Bo's thinking/reading/review, Claude's
  work in session) — not just agent activity. Compare actual vs spec estimates; if a block
  overruns, invoke its escape hatch early.
- **Demo notes:** at the same boundaries, update `docs/demo-notes.md` — new decisions/trade-offs
  into §2, completed work into §3, video-worthy lines into §1. It accumulates; never rewrite it
  from scratch.
- Follow the workspace Karpathy guidelines (`../CLAUDE.md`): surgical changes, no speculative
  features, state assumptions, verify before claiming done.
