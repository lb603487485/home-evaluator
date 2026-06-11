"""Tiny CLI runner printing the agent's event stream — manual verification for Task 7.

    uv run python -m agent.run_demo                 # all three demo subjects
    uv run python -m agent.run_demo --subject bearspaw

Needs ANTHROPIC_API_KEY in backend/.env for LLM mode; falls back deterministically without.
"""

import argparse
import asyncio
import time

from dotenv import load_dotenv

from agent.graph import build_graph
from agent.llm import llm_enabled
from data.schema import SubjectProperty
from data.store import SyntheticDataSource, ensure_comps

SUBJECTS = {
    "evanston": SubjectProperty(community="Evanston", property_type="detached", beds=3,
                                baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                                garage_stalls=2),
    "bearspaw": SubjectProperty(community="Bearspaw", property_type="detached", beds=4,
                                baths=3.5, sqft=3000, year_built=2005, lot_sqft=150_000,
                                garage_stalls=3),
    "notes": SubjectProperty(community="Evanston", property_type="detached", beds=3,
                             baths=2.5, sqft=1850, year_built=2020, lot_sqft=4000,
                             garage_stalls=2,
                             notes="backs onto golf course, unfinished basement, "
                                   "original windows"),
}


async def run(name: str, subject: SubjectProperty) -> None:
    graph = build_graph(SyntheticDataSource(ensure_comps()))
    print(f"\n{'=' * 60}\n{name}  (LLM {'ON' if llm_enabled() else 'OFF'})\n{'=' * 60}")
    started = time.perf_counter()
    async for mode, chunk in graph.astream({"subject": subject},
                                           stream_mode=["updates", "custom"]):
        if mode == "custom":
            print(chunk, end="", flush=True)
            continue
        for node, delta in chunk.items():
            delta = delta or {}
            for err in delta.get("errors") or []:
                print(f"  [fallback] {err}")
            if node == "intake":
                print(f"[intake] signals: {delta.get('notes_signals') or '—'}")
            elif node == "search":
                e = delta["search_log"][0]
                print(f"[search] round {e['round']}: found {e['found']} — {e['reason']}")
            elif node == "widen":
                print(f"[widen] {delta.get('widen_reason')}")
            elif node == "score":
                top = delta["scored"][:3]
                print(f"[score] {len(delta['scored'])} scored; top: "
                      + ", ".join(f"{s.comp.address} ({s.score})" for s in top))
            elif node == "review_comp":
                [v] = delta["reviews"]
                mark = " (unreviewed)" if v.unreviewed else ""
                print(f"[review] {v.address_key}: {v.verdict}{mark} — {v.reason}")
            elif node == "valuate":
                v = delta["valuation"]
                if v:
                    print(f"[valuate] ${v.estimate:,} (${v.low:,}–${v.high:,}) "
                          f"confidence {v.confidence}")
                print(f"[flags] {[f.code for f in delta['risk_flags']] or '—'}")
            elif node == "narrate":
                print(f"\n[narrate] {len(delta.get('narrative') or '')} chars")
    print(f"[done] {time.perf_counter() - started:.1f}s")


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subject", choices=[*SUBJECTS, "all"], default="all")
    args = ap.parse_args()
    names = list(SUBJECTS) if args.subject == "all" else [args.subject]
    for name in names:
        asyncio.run(run(name, SUBJECTS[name]))


if __name__ == "__main__":
    main()
