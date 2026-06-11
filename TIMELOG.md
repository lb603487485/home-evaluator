# Time Log — home-evaluator (KV Capital comp-analysis challenge)

**What counts as time:** wall-clock human-involved time — discussion, my (Bo's) thinking and
reading, reviewing Claude's output, and Claude's working time inside a session. Not just
keyboard/agent activity. Offline thinking (away from the session) gets logged when reported.

| Date | Start | End | Duration | What we did |
|------|-------|-----|----------|-------------|
| 2026-06-10 | 14:06 | 16:18 | 1.4h | Session 1: scoping + design (§1): data-source research, architecture choice (hybrid LangGraph), multi-source ingestion design, risk/scope decisions, spec + CLAUDE.md + implementation plan written, design Q&A (nodes, skills, batch-vs-live, RAG), spec locked. (off-project time excluded, per Bo) |
| 2026-06-10 | 16:18 | 16:29 | 0.2h | Session 1 addendum: design Q&A (tool use → bind_tools plan tweak, memory/statelessness note, frontend form walkthrough), reserve raised to 2h |
| 2026-06-11 | 10:25 | 10:57 | 0.5h | Session 2 block 1: T0 scaffold (uv, 3.12, contracts) · T1 schema+normalize (8 tests) · T2 price model+generator, edge cases planted (11 tests) · T3 adapters+merge with provenance (9 tests) → comps.parquet (6,290 rec, 2,603 scorable). 28 tests green, 4 commits. Mid-block verification re-check of T0/T1 at Bo's request |

| 2026-06-11 | 10:57 | 11:20 | 0.4h | Session 2 block 2: T4 filters+scoring (17 tests) · T5 valuation+risk registry, hand-computed fixture exact (22 tests) · T6 six-node graph deterministic e2e, Bearspaw calibration fix (3 tests) · T8 FastAPI SSE (3 tests, reordered before T7 — no API key on machine). 73 tests green, 4 commits. Demo-notes §2/§3 updated |

**Total so far:** ~2.5h of 12h cap (7.5h build blocks + 2.0h reserve remaining).
Time boxes are strict: a block hitting its box takes its escape hatch immediately — overruns bill the reserve.

## Plan vs actual (from spec §9)

| Block | Est | Actual | Status |
|---|---|---|---|
| §1 Scope + design (incl. impl. plan) | 1.0h | ~1.5h | done — overran 0.5h: thorough spec + impl. plan + design Q&A. Build blocks must hold their lines; recovery if needed: §5 hatches (batched review, 1-round widening), then user reserve |
| §3 Data generator | 1.0h | ~0.25h | done — T2 (incl. T0 scaffold overhead) |
| §4 Ingestion | 1.0h | ~0.25h | done — T1 schema/normalize + T3 adapters/merge |
| §5 Agent graph | 3.0h | — | |
| §7 API + Vite UI | 2.0h | — | |
| §6 Tests + eval | 1.5h | — | |
| README + video | 1.5h | — | |
| Reserve (user's) | 2.0h | — | untouched (raised from 1h, 2026-06-10, to guarantee ≤12h total) |
