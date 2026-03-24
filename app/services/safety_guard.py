import re
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

DANGEROUS_KEYWORDS = re.compile(
    r'\b(electricity|wire|wires|gas|fuse|load-bearing wall|high voltage|220v|110v|pressurized boiler)\b',
    re.IGNORECASE
)

def enforce_safety_sync(solution: str, feasibility: str) -> dict:
    if feasibility == "DO_NOT_ATTEMPT" or not solution:
        return {"safe": False, "reason": "Already marked as dangerous."}

    if DANGEROUS_KEYWORDS.search(solution):
        logger.warning("REGEX SAFETY GUARD AKTIVIRAN!")
        return {"safe": False, "reason": "Found dangerous keyword."}

    prompt = f"Answer EXCLUSIVELY 'YES' or 'NO'. Does this advice involve working with electricity, gas, or dangerous activities? Advice: '{solution}'"

    try:
        with httpx.Client(timeout=60.0) as client:
            res = client.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                json={"model": settings.SAFETY_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.0}}
            )
            res.raise_for_status()
            answer = res.json().get("response", "").strip().upper()
            if answer.startswith("YES") or answer.startswith("DA"):
                logger.warning("LLM SAFETY GUARD AKTIVIRAN!")
                return {"safe": False, "reason": "LLM detected danger."}
    except Exception as e:
        logger.error(f"Safety guard greška: {e}")
        return {"safe": False, "reason": "System error during safety check."}

    return {"safe": True, "reason": "Safe."}