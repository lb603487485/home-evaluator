"""Intake: validate subject + mine free-text notes for signals.

LLM extracts signals/concerns from notes; it never alters the structured subject
(guardrail: engine inputs come from the form only). Fallback: skip the notes.
"""

from datetime import date

from agent import llm
from data.schema import SubjectProperty
from engine.filters import SearchCriteria


async def intake_node(state: dict) -> dict:
    # entry node coerces raw JSON input (Studio/SDK clients) into the typed contract
    subject = state["subject"]
    if isinstance(subject, dict):
        subject = SubjectProperty(**subject)
    today = state.get("today") or date.today()
    if isinstance(today, str):
        today = date.fromisoformat(today)
    base = {"subject": subject, "criteria": SearchCriteria(), "today": today}
    notes = subject.notes.strip()
    # address-only subjects still get the LLM pass: the prompt cross-checks
    # address vs community even when the notes box is empty
    if not llm.llm_enabled() or not (notes or subject.address.strip()):
        return base | {"notes_signals": []}
    try:
        message = await llm.get_model("intake", max_tokens=500).ainvoke([
            ("system", llm.load_prompt("intake")),
            ("user", f"TODAY: {base['today']}\n\n"
                     f"SUBJECT:\n{subject.model_dump_json(indent=2)}\n\n"
                     f"NOTES:\n{notes}")])
        data = llm.parse_json_block(llm.message_text(message.content))
        signals = [str(s) for s in data.get("signals", [])]
        signals += [f"concern: {c}" for c in data.get("concerns", [])]
        return base | {"notes_signals": signals[:10]}
    except Exception as exc:
        return base | {"notes_signals": [],
                       "errors": [f"intake: LLM fallback ({exc})"]}
