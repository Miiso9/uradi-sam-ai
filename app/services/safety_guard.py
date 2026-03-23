import re
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

DANGEROUS_KEYWORDS = re.compile(
    r'\b(struja|žica|žice|plin|osigurač|nosivi zid|visoki napon|220v|bojler pod pritiskom)\b',
    re.IGNORECASE
)

def enforce_safety_sync(solution: str, feasibility: str) -> dict:
    if feasibility == "DO_NOT_ATTEMPT" or not solution:
        return {"safe": False, "reason": "Već označeno kao opasno."}

    if DANGEROUS_KEYWORDS.search(solution):
        logger.warning("🚨 REGEX SAFETY GUARD AKTIVIRAN!")
        return {"safe": False, "reason": "Pronađena opasna ključna riječ."}

    prompt = f"Odgovori ISKLJUČIVO 'DA' ili 'NE'. Da li ovaj savjet uključuje rad sa strujom, plinom ili opasne radnje? Savjet: '{solution}'"

    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                json={"model": settings.SAFETY_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.0}}
            )
            res.raise_for_status()
            answer = res.json().get("response", "").strip().upper()
            if answer.startswith("DA"):
                logger.warning("🚨 LLM SAFETY GUARD AKTIVIRAN!")
                return {"safe": False, "reason": "LLM detektirao opasnost."}
    except Exception as e:
        logger.error(f"Safety guard greška: {e}")
        return {"safe": False, "reason": "Sistemska greška sigurnosne provjere."}

    return {"safe": True, "reason": "Sigurno."}