"""Eval vs ground truth: 20 held-out subjects priced by the true price model →
MAPE, median error, ±10% hit rate, comp-recovery@8 vs model-nearest-10, plus
scenario asserts. Writes eval/results.md.

    uv run python -m eval.eval
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from agent.graph import build_graph
from agent.llm import llm_enabled
from data.generate import COMMUNITIES
from data.price_model import TREND_ANCHOR, true_price
from data.schema import SubjectProperty
from data.store import SyntheticDataSource, ensure_comps

TODAY = TREND_ANCHOR
SEED = 7  # held-out: subjects are form inputs, never rows in the sales data
NEAREST_N = 10

# (community, type, how many subjects)
MIX = [("Evanston", "detached", 3), ("Evanston", "townhouse", 1),
       ("Tuscany", "detached", 3), ("Auburn Bay", "detached", 2),
       ("Auburn Bay", "townhouse", 1), ("Killarney", "semi", 2),
       ("Killarney", "detached", 1), ("Beltline", "apartment", 3),
       ("Bridgeland", "apartment", 1), ("Bridgeland", "townhouse", 1),
       ("Aspen Woods", "detached", 1), ("Bearspaw", "detached", 1)]


def make_subjects() -> list[SubjectProperty]:
    rng = np.random.default_rng(SEED)
    subjects = []
    for community, ptype, n in MIX:
        spec = COMMUNITIES[community]["types"][ptype]
        for _ in range(n):
            subjects.append(SubjectProperty(
                community=community, property_type=ptype,
                beds=int(rng.integers(spec["beds"][0], spec["beds"][1] + 1)),
                baths=float(rng.integers(int(spec["baths"][0] * 2),
                                         int(spec["baths"][1] * 2) + 1)) / 2,
                sqft=int(rng.integers(spec["sqft"][0], spec["sqft"][1] + 1)),
                year_built=int(rng.integers(spec["year"][0], spec["year"][1] + 1)),
                lot_sqft=(int(rng.integers(spec["lot"][0], spec["lot"][1] + 1))
                          if spec["lot"] else None),
                garage_stalls=int(rng.integers(spec["garage"][0],
                                               spec["garage"][1] + 1)),
            ))
    return subjects


def model_nearest(source: SyntheticDataSource, subject: SubjectProperty,
                  truth: int) -> set[str]:
    """The NEAREST_N scorable same-segment sales whose ground-truth value (priced
    fresh today from their true attributes) is closest to the subject's truth."""
    df = source._frame()
    pool = df[(df["community"] == subject.community)
              & (df["property_type"] == subject.property_type)
              & df["sqft"].notna() & df["beds"].notna()
              & df["sold_price"].notna() & df["sold_date"].notna()]
    distances = []
    for row in pool.to_dict("records"):
        value = true_price(row, TODAY)
        distances.append((abs(value - truth), row["address_key"]))
    return {key for _, key in sorted(distances)[:NEAREST_N]}


async def main() -> None:
    load_dotenv()
    source = SyntheticDataSource(ensure_comps())
    graph = build_graph(source)
    rows, all_flags, any_non_arms = [], set(), False

    for i, subject in enumerate(make_subjects(), 1):
        truth = true_price(subject.model_dump(), TODAY)
        out = await graph.ainvoke({"subject": subject, "today": TODAY})
        valuation, flags = out["valuation"], {f.code for f in out["risk_flags"]}
        all_flags |= flags
        any_non_arms |= any(e["reason"] == "non_arms_length"
                            for e in out.get("exclusions") or [])
        estimate = valuation.estimate if valuation else None
        kept = {a.address_key for a in valuation.adjustments} if valuation else set()
        recovery = (len(kept & model_nearest(source, subject, truth)) / len(kept)
                    if kept else 0.0)
        rows.append(dict(
            n=i, segment=f"{subject.community} {subject.property_type}",
            truth=truth, estimate=estimate,
            error=(estimate - truth) / truth if estimate else None,
            confidence=valuation.confidence if valuation else "—",
            recovery=recovery, widened=len(out["search_log"]) > 1, flags=flags))

    # scenario asserts — the planted edge cases must drive agent behavior
    bearspaw = next(r for r in rows if r["segment"].startswith("Bearspaw"))
    assert bearspaw["widened"] and "WIDENED_SEARCH" in bearspaw["flags"], \
        "Bearspaw must widen and flag it"
    assert "THIN_COMPS" in bearspaw["flags"], "Bearspaw must flag thin comps"
    assert any_non_arms, "non-arm's-length transfers must be excluded somewhere"
    assert "DATA_CONFLICT" in all_flags, "source conflicts must surface as flags"

    scored = [r for r in rows if r["error"] is not None]
    normal = [r for r in scored if not r["segment"].startswith(("Bearspaw", "Aspen"))]

    def mape(rs):
        return float(np.mean([abs(r["error"]) for r in rs]))

    lines = [
        f"# Eval results — LLM {'ON' if llm_enabled() else 'OFF (deterministic)'}",
        "",
        "| # | segment | truth | estimate | error | conf | recovery@8 |",
        "|---|---------|-------|----------|-------|------|------------|",
    ]
    for r in rows:
        est = f"${r['estimate']:,}" if r["estimate"] else "—"
        err = f"{r['error']:+.1%}" if r["error"] is not None else "—"
        lines.append(f"| {r['n']} | {r['segment']}{' ◆' if r['widened'] else ''} "
                     f"| ${r['truth']:,} | {est} | {err} | {r['confidence']} "
                     f"| {r['recovery']:.0%} |")
    lines += [
        "",
        f"- **MAPE (all {len(scored)}):** {mape(scored):.1%} · "
        f"**MAPE (normal, n={len(normal)}):** {mape(normal):.1%}",
        f"- **Median |error|:** {float(np.median([abs(r['error']) for r in scored])):.1%}",
        f"- **Within ±10%:** {sum(abs(r['error']) <= 0.10 for r in scored)}/{len(scored)}",
        f"- **Mean comp-recovery@8 vs model-nearest-10:** "
        f"{float(np.mean([r['recovery'] for r in scored])):.0%}",
        "- Scenario asserts passed: Bearspaw widened+flagged · non-arm's-length "
        "excluded · DATA_CONFLICT surfaced",
        "- ◆ = search was widened",
        "",
        "Recovery@8 note: similarity ranking optimizes adjusted-price reliability "
        "(distance, recency, attribute closeness), not raw value proximity, so low "
        "overlap with the value-nearest-10 is expected (chance ≈ 3%); estimate "
        "accuracy above is the outcome metric.",
    ]
    report = "\n".join(lines)
    print(report)
    (Path(__file__).parent / "results.md").write_text(report + "\n")


if __name__ == "__main__":
    asyncio.run(main())
