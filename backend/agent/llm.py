"""Model factory + prompt loading + LLM plumbing helpers.

Per-node model override via {NODE}_MODEL env; Haiku for volume nodes,
Sonnet for judgment/language nodes.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from langchain_anthropic import ChatAnthropic

DEFAULTS = {
    "intake": "claude-haiku-4-5",
    "search": "claude-sonnet-4-6",
    "review": "claude-haiku-4-5",
    "narrate": "claude-sonnet-4-6",
    "ask": "claude-sonnet-4-6",
}

PROMPTS_DIR = Path(__file__).parent / "prompts"


def llm_enabled() -> bool:
    return not os.environ.get("AGENT_NO_LLM") and bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_model(node: str, **kwargs) -> ChatAnthropic:
    return ChatAnthropic(model=os.environ.get(f"{node.upper()}_MODEL", DEFAULTS[node]),
                         max_tokens=kwargs.pop("max_tokens", 1024),
                         timeout=30, max_retries=1, **kwargs)


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def message_text(content) -> str:
    """AIMessage.content is a str or a list of content blocks."""
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") if isinstance(block, dict)
                   else getattr(block, "text", "") for block in content)


def parse_json_block(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)
