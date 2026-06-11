"""Narrate: appraiser-style explanation of the valuation.

Task 6: deterministic fallback only — empty narrative, the tables speak.
Task 7 adds the streamed LLM narrative.
"""


async def narrate_node(state: dict) -> dict:
    return {"narrative": ""}
