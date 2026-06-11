"""Intake: validate subject + mine free-text notes for signals.

Task 6: deterministic fallback only — subject passes through, default criteria.
Task 7 adds the LLM path; on any LLM failure this fallback is the behavior.
"""

from datetime import date

from engine.filters import SearchCriteria


async def intake_node(state: dict) -> dict:
    return {
        "notes_signals": [],
        "criteria": SearchCriteria(),
        "today": state.get("today") or date.today(),
    }
