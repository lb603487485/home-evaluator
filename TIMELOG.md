# Time Log — home-evaluator (KV Capital comp-analysis challenge)

**What counts as time:** wall-clock human-involved time — discussion, my (Bo's) thinking and
reading, reviewing Claude's output, and Claude's working time inside a session. Not just
keyboard/agent activity. Offline thinking (away from the session) gets logged when reported.
Duration shows each row's real working time; Counted shows what the row actually adds to the
total (overlapping time counts on the earliest row covering it, so the total is the wall-clock
union of intervals). Total = sum of Counted; overlapping rows carry a note naming their pair.

| Date | Start | End | Duration | Counted | What we did |
|------|-------|-----|----------|---------|-------------|
| 2026-06-10 | 14:06 | 16:18 | 1.4h | 1.4h | Session 1: scoping + design (§1): data-source research, architecture choice (hybrid LangGraph), multi-source ingestion design, risk/scope decisions, spec + CLAUDE.md + implementation plan written, design Q&A (nodes, skills, batch-vs-live, RAG), spec locked. (off-project time excluded, per Bo) |
| 2026-06-10 | 16:18 | 16:29 | 0.2h | 0.2h | Session 1 addendum: design Q&A (tool use → bind_tools plan tweak, memory/statelessness note, frontend form walkthrough), reserve raised to 2h |
| 2026-06-11 | 10:25 | 10:57 | 0.5h | 0.5h | Session 2 block 1: T0 scaffold (uv, 3.12, contracts) · T1 schema+normalize (8 tests) · T2 price model+generator, edge cases planted (11 tests) · T3 adapters+merge with provenance (9 tests) → comps.parquet (6,290 rec, 2,603 scorable). 28 tests green, 4 commits. Mid-block verification re-check of T0/T1 at Bo's request |
| 2026-06-11 | 10:57 | 11:20 | 0.4h | 0.4h | Session 2 block 2: T4 filters+scoring (17 tests) · T5 valuation+risk registry, hand-computed fixture exact (22 tests) · T6 six-node graph deterministic e2e, Bearspaw calibration fix (3 tests) · T8 FastAPI SSE (3 tests, reordered before T7 — no API key on machine). 73 tests green, 4 commits. Demo-notes §2/§3 updated |
| 2026-06-11 | 11:14 | 11:25 | 0.2h | 0.1h | Session 2 block 3: T7 LLM nodes — llm.py factory, 4 prompt files, tool-calling widen (bind_tools, accept_results), review prechecks+verdicts, streamed narrate, run_demo CLI; 8 fake-model wiring tests. 81 tests green. **Live-LLM verify pending: needs ANTHROPIC_API_KEY in backend/.env.** Overlaps block 2 by 0.1h (11:14–11:20) — counted once in total |
| 2026-06-11 | 11:25 | 11:35 | 0.2h | 0.2h | Session 2 block 4: T9 Vite UI (6 components, SSE reader, verified live in browser — screenshots sent) · T10 eval harness: **MAPE 2.1%, 19/19 within ±10%, scenario asserts pass** (LLM-off baseline). 81 tests, 4 commits. Dev servers left running (:8000/:5173) |
| 2026-06-11 | 11:40 | 12:00 | 0.3h | 0.3h | Session 2 block 5: graph diagram Q&A · Bo added API key → **T7 live-LLM verify run**. Found+fixed: blind widening (now engine-projects per-move counts for the LLM), missing as-of date ("future sale" artifact), verbose reviews (token caps; ~30s→~13s). All planted cases handled correctly live; narrative numbers all trace to data block. LLM-on eval rerun kicked off |
| 2026-06-11 | 12:00 | 12:10 | 0.2h | 0.2h | Session 2 block 6: LLM-on eval caught agent accepting an empty comp set (scenario assert failed) → root-caused (projections showed relax_beds=1) → action-space guardrail + accept logged to audit trail (4 new tests, 84 green) → eval rerun: **MAPE 2.2%, 20/20 within ±10%, median 1.4%, Bearspaw estimated** |
| 2026-06-11 | 12:00 | 12:10 | 0.2h | 0h | Session 3 (parallel tab, fully concurrent with block 6 — adds nothing to total): ML roadmap vetting Q&A — graded 4 calibration upgrades (HPI subscription for MARKET_TREND_QOQ, hedonic fit of ADJ, AVM-divergence risk rule, learned WEIGHTS from KV's appraisal archive) against engine seams + verified data paths; what we won't claim (synthetic-trained ML, black-box AVM). Decision + video bullet → demo-notes §1/§2 |
| 2026-06-11 | 18:05 | 18:20 | 0.3h | 0.3h | Session 2 block 7 (after ~6h away): README drafted per spec §9 — problem, architecture + self-drawn graph, run instructions, planted-cases table, eval table (LLM-on vs baseline), decisions, cuts, production plan, extension points. Screenshots checked into docs/images. 84 tests re-verified |
| 2026-06-11 | 18:25 | 18:45 | 0.3h | 0.3h | Session 2 block 8: LangGraph Studio support — langgraph.json + make_graph factory + JSON-input coercion at intake (85 tests). Dependency fight: cli 0.1.54 had silently resolved (no `dev` command); fixed via requires-python <3.13, prerelease allow for langgraph-api, sse-starlette <3.4 (dev-server cap). Verified live run through dev API on :2025 (:2024 owned by another project) |
| 2026-06-11 | 18:26 | 19:15 | 0.8h | 0.5h | Session 4: UX design brainstorm with browser mockups (Bo's 4 asks → 6 decisions): chat-hybrid (form in, transcript out), per-home sessions w/ background runs + localStorage, pinned hero valuation card w/ key-factors line + timestamps, address intake + deterministic community auto-fill + mismatch guards, `/api/ask` Q&A + what-if re-runs (visible diff → linked session). Design v3 approved; spec addendum written. Overlaps block 8 by 0.3h (18:26–18:45) — counted once in total |
| 2026-06-11 | 19:15 | 19:50 | 0.6h | 0.6h | Session 4 cont.: design Q&A (Bo's Q5–7 + follow-ups) → 3 stretch items specced + 3 no-builds settled. Bo redesigned S1: challenge→re-review replaces click-override (human contributes evidence, agent re-judges, both logged). AVM stand-in = transparent $/sqft norm divergence flag, trained-fake rejected. ML calibration demo queued last. Spec §8 stretch queue added; green light to build |

**Total so far (wall-clock):** ~5.0h of 12h cap = sum of Counted column (Duration sums to
5.6h; 0.6h of overlap counted once: 0.1h blocks 2/3 + 0.2h session 3 + 0.3h block 8/session 4).
(5.0h build blocks + 2.0h reserve remaining.)
**State: T0–T10 built and verified; README drafted; UX addendum approved (spec: `docs/specs/2026-06-11-sessions-chat-ui-design.md`, boxed 3.0h F1–F4).** Remaining: F1–F4 UX build · (Bo) record ≤3-min video + link it in README · create public GitHub repo + push · final read-through of README/demo-notes.
Time boxes are strict: a block hitting its box takes its escape hatch immediately — overruns bill the reserve.

## Plan vs actual (from spec §9)

| Block | Est | Actual | Status |
|---|---|---|---|
| §1 Scope + design (incl. impl. plan) | 1.0h | ~1.5h | done — overran 0.5h: thorough spec + impl. plan + design Q&A. Build blocks must hold their lines; recovery if needed: §5 hatches (batched review, 1-round widening), then user reserve |
| §3 Data generator | 1.0h | ~0.25h | done — T2 (incl. T0 scaffold overhead) |
| §4 Ingestion | 1.0h | ~0.25h | done — T1 schema/normalize + T3 adapters/merge |
| §5 Agent graph | 3.0h | ~0.4h | done — T6+T7 (live-LLM verify pending key) |
| §7 API + Vite UI | 2.0h | ~0.4h | done — T8+T9, UI verified live |
| §6 Tests + eval | 1.5h | ~0.1h | done — tests were in-line (TDD); T10 eval harness |
| README + video | 1.5h | — | |
| UX addendum (sessions/chat/address, spec 2026-06-11) | 0.5h design + 3.0h boxed build | 0.5h design | design done; F1–F4 boxes set at observed velocity, 4-step cut ladder armed |
| Reserve (user's) | 2.0h | — | untouched (raised from 1h, 2026-06-10, to guarantee ≤12h total) |
