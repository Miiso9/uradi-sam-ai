import time
import httpx
import logging
from app.core.config import settings
from app.services.rag_service import retrieve_context_with_timeout
from app.services.prompts import SYSTEM_PROMPT
from app.services.safety_guard import enforce_safety_sync
from app.schemas.ai_models import AIAnalysisResult

logger = logging.getLogger(__name__)

def analyze_sync(image_base64: str, question: str) -> dict:
    """Obrada slike i teksta unutar Celery workera."""

    context = retrieve_context_with_timeout(question)
    prompt = f"{SYSTEM_PROMPT}\nPitanje: {question}\nKontekst priručnika:\n{context}"

    payload = {
        "model": settings.AI_MODEL,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "format": AIAnalysisResult.model_json_schema()
    }

    start = time.time()
    try:
        with httpx.Client(timeout=120) as client:
            res = client.post(f"{settings.OLLAMA_HOST}/api/generate", json=payload)
            res.raise_for_status()
            raw_response = res.json().get("response", "{}")
    except Exception as e:
        logger.error(f"Ollama nedostupna ili je bacila timeout: {e}")
        return {"error": "AI sustav je trenutno preopterećen."}

    latency = round(time.time() - start, 2)

    try:
        analysis_data = AIAnalysisResult.model_validate_json(raw_response)
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
        analysis_data.solution = "SISTEMSKA BLOKADA: Otkriven opasan zahvat. Ne pokušavajte sami. Pozovite ovlaštenog stručnjaka."
        analysis_data.dangers = "OPASNOST PO ŽIVOT I IMOVINU. Rad zahtijeva certifikat."

    if analysis_data.confidence < 0.6 and analysis_data.diy_feasibility != "DO_NOT_ATTEMPT":
        analysis_data.solution = "Model nije potpuno siguran u dijagnozu. Preporučujemo konzultacije sa stručnjakom prije ikakvih zahvata."
        analysis_data.diy_feasibility = "UNKNOWN"

    return {
        "data": analysis_data.model_dump(),
        "latency": latency
    }