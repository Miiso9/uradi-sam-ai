import time
import httpx
import logging
from app.core.config import settings
from app.services.rag_service import retrieve_context_with_timeout
from app.services.prompts import SYSTEM_PROMPT
from app.services.safety_guard import enforce_safety_sync
from app.schemas.ai_models import AIAnalysisResult
from app.utils.json_utils import extract_json_string

logger = logging.getLogger(__name__)

def analyze_sync(image_base64: str, question: str) -> dict:
    """Obrada slike i teksta unutar Celery workera."""

    logger.info(f"Započinjem AI analizu za upit: '{question}'")

    context = retrieve_context_with_timeout(question)

    if context:
        prompt = f"{SYSTEM_PROMPT}\nPitanje: {question}\nKontekst priručnika:\n{context}"
    else:
        prompt = f"{SYSTEM_PROMPT}\nPitanje: {question}\nNema dostupnog priručnika za ovaj problem. Osloni se isključivo na vizualnu analizu i vlastito znanje."

    payload = {
        "model": settings.AI_MODEL,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "format": AIAnalysisResult.model_json_schema()
    }

    start = time.time()
    try:
        logger.info("Šaljem podatke u LLaVA model... (ovo može potrajati na CPU)")
        with httpx.Client(timeout=180.0) as client:
            res = client.post(f"{settings.OLLAMA_HOST}/api/generate", json=payload)
            res.raise_for_status()
            raw_response = res.json().get("response", "{}")
            logger.info(f"RAW LLaVA ODGOVOR: {raw_response}")
    except Exception as e:
        logger.error(f"Ollama nedostupna ili je bacila timeout: {e}")
        raise RuntimeError(f"AI obrada nije uspjela unutar zadanog vremena: {e}")

    latency = round(time.time() - start, 2)

    try:
        clean_json = extract_json_string(raw_response)
        analysis_data = AIAnalysisResult.model_validate_json(clean_json)
    except Exception as e:
        logger.error(f"Pydantic parsing greška: {e} na raw: {raw_response}")
        analysis_data = AIAnalysisResult(
            is_relevant=False,
            rejection_reason="Greška pri parsiranju odgovora modela.",
            confidence=0.0
        )

    safety_check = enforce_safety_sync(analysis_data.solution, analysis_data.diy_feasibility)
    if not safety_check["safe"]:
        analysis_data.diy_feasibility = "DO_NOT_ATTEMPT"
        razlog = safety_check.get("reason", "SISTEMSKA BLOKADA: Otkriven opasan zahvat. Ne pokušavajte sami. Pozovite ovlaštenog stručnjaka.")
        analysis_data.solution = razlog
        analysis_data.dangers = "OPASNOST PO ŽIVOT I IMOVINU. Rad zahtijeva certifikat."

    if analysis_data.confidence < 0.6 and analysis_data.diy_feasibility != "DO_NOT_ATTEMPT":
        analysis_data.solution = "Model nije potpuno siguran u dijagnozu. Preporučujemo konzultacije sa stručnjakom prije ikakvih zahvata."
        analysis_data.diy_feasibility = "UNKNOWN"

    return {
        "data": analysis_data.model_dump(),
        "latency": latency
    }