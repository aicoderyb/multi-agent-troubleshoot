"""Supervisor: choose which specialist agents to run."""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from mulat.logging_config import get_logger
from mulat.orchestration.prompts_loader import load_prompt
from mulat.orchestration.state import GraphState

logger = get_logger(__name__)

ALL_AGENTS = ("node_health", "right_sizing", "pod_security")
_VALID_TARGETS = set(ALL_AGENTS)


def supervisor_node(state: GraphState) -> GraphState:
    """Keyword routing (no LLM)."""
    request = (state.get("request") or "").lower()
    if "notready" in request or "node" in request:
        targets = ["node_health"]
    elif "security" in request or "pss" in request or "privileged" in request:
        targets = ["pod_security"]
    elif "right-size" in request or "prometheus" in request or "cpu" in request:
        targets = ["right_sizing"]
    else:
        targets = list(ALL_AGENTS)
    logger.debug("Keyword supervisor targets=%s", targets)
    return {"targets": targets}


def _parse_targets_json(text: str) -> list[str]:
    """Extract {"targets": [...]} from model output (may include markdown fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    raw = data.get("targets")
    if not isinstance(raw, list):
        raise ValueError("LLM response missing 'targets' list")
    targets = [t for t in raw if isinstance(t, str) and t in _VALID_TARGETS]
    if not targets:
        raise ValueError("No valid agent names in targets")
    logger.debug("LLM supervisor parsed targets=%s", targets)
    return targets


def supervisor_node_llm(state: GraphState, llm) -> GraphState:
    """LLM routing using prompts/supervisor.md. Falls back to keyword supervisor on errors."""
    try:
        system = load_prompt("supervisor")
        user = state.get("request") or ""
        msg = llm.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(
                    content=(
                        f"{user}\n\n"
                        'Reply with JSON only, e.g. {"targets": ["node_health", "right_sizing"]}. '
                        f"Valid names: {list(ALL_AGENTS)}."
                    )
                ),
            ]
        )
        content = msg.content if hasattr(msg, "content") else str(msg)
        targets = _parse_targets_json(content)
        logger.info("LLM supervisor targets=%s", targets)
        return {"targets": targets}
    except (json.JSONDecodeError, ValueError, FileNotFoundError, TypeError) as exc:
        logger.warning("LLM supervisor parse error, using keywords: %s", exc)
        return supervisor_node(state)
    except Exception:
        logger.exception("LLM supervisor failed, using keyword fallback")
        return supervisor_node(state)
