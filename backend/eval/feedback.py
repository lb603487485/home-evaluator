"""Feedback report: user-vs-engine deltas and ratings, sliced by confidence /
community / risk flag, with callouts naming the engine/config.py knob to
investigate. Deterministic — no LLM. The loop: S9 captures → this report
diagnoses → eval.calibrate proposes → eval.eval validates. Feedback proposes,
eval disposes; nothing here moves a weight.

Run: uv run python -m eval.feedback  →  eval/feedback_report.md
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median

FEEDBACK_PATH = Path(__file__).resolve().parent.parent / "data" / "feedback.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "feedback_report.md"

CALLOUT_PCT = 0.05   # |median user-vs-engine| beyond this on a slice (n≥2) → callout
KNOBS = {
    "confidence": "similarity WEIGHTS / FILTER_DEFAULTS / WIDENING_MOVES (engine/config.py)",
    "community": "that community's MARKET_TREND_QOQ rate (engine/config.py)",
    "flag": "the flagged rule's threshold or the rates it leans on (engine/config.py)",
}


def _delta(rec: dict) -> float | None:
    estimate, user = rec["snapshot"].get("estimate"), rec.get("user_estimate")
    if estimate and user:
        return (user - estimate) / estimate
    return None


def _slices(records: list[dict]):
    """Yield (kind, name, group) — overall, then by confidence/community/flag."""
    yield "all", "all feedback", records
    for kind, key in (("confidence",
                       lambda r: f"confidence {r['snapshot'].get('confidence')}"),
                      ("community",
                       lambda r: str(r["snapshot"].get("subject", {}).get("community")))):
        groups: dict[str, list[dict]] = {}
        for r in records:
            groups.setdefault(key(r), []).append(r)
        yield from ((kind, name, group) for name, group in sorted(groups.items()))
    flags: dict[str, list[dict]] = {}
    for r in records:
        for code in r["snapshot"].get("flags") or []:
            flags.setdefault(f"flag {code}", []).append(r)
    yield from (("flag", name, group) for name, group in sorted(flags.items()))


def build_report(records: list[dict]) -> str:
    if not records:
        return ("# Feedback report\n\nNo feedback captured yet — rate a "
                "completed session in the UI first.\n")
    with_estimate = sum(1 for r in records if _delta(r) is not None)
    out = ["# Feedback report — user signal vs engine",
           "",
           f"n={len(records)} feedback records, {with_estimate} with a user estimate.",
           ""]
    if len(records) < 10:
        out += ["**n < 10: directional only — do not retune on this sample.**", ""]
    out += ["Loop: this report localizes → `eval.calibrate` proposes → a human edits "
            "`engine/config.py` → `eval.eval` validates against ground truth. "
            "Feedback never moves a weight directly.",
            "",
            "| slice | n | mean rating | median user-vs-engine |",
            "|---|---|---|---|"]
    callouts: list[str] = []
    for kind, name, group in _slices(records):
        deltas = [d for d in map(_delta, group) if d is not None]
        spread = f"{median(deltas):+.1%}" if deltas else "—"
        out.append(f"| {name} | n={len(group)} | "
                   f"{mean(r['rating'] for r in group):.1f} | {spread} |")
        if kind != "all" and len(deltas) >= 2 and abs(median(deltas)) > CALLOUT_PCT:
            callouts.append(f"- **{name}**: users estimate {median(deltas):+.1%} vs "
                            f"the engine (n={len(deltas)}) → investigate {KNOBS[kind]}")
    out += ["", "## Callouts", ""]
    out += callouts or [f"- none — no slice beyond ±{CALLOUT_PCT:.0%} with n≥2"]
    return "\n".join(out) + "\n"


def main() -> None:
    records = []
    if FEEDBACK_PATH.exists():
        records = [json.loads(line)
                   for line in FEEDBACK_PATH.read_text().splitlines() if line.strip()]
    report = build_report(records)
    REPORT_PATH.write_text(report)
    print(report)
    print(f"→ {REPORT_PATH}")


if __name__ == "__main__":
    main()
