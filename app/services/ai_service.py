import time
import httpx
import logging
from deep_translator import GoogleTranslator  # <-- Dodan prevoditelj

from app.core.config import settings
from app.services.b2b_service import match_b2b_opportunities
from app.services.rag_service import retrieve_context_with_timeout
from app.services.prompts import SYSTEM_PROMPT
from app.services.safety_guard import enforce_safety_sync
from app.schemas.ai_models import AIAnalysisResult
from app.utils.json_utils import extract_json_string

logger = logging.getLogger(__name__)

def analyze_sync(image_base64: str, question: str) -> dict:
    """Obrada slike i teksta unutar Celery workera s uključenim prijevodom."""

    logger.info(f"▶️ Započinjem AI analizu za upit: '{question}'")

    context = retrieve_context_with_timeout(question)

    try:
        logger.info("Prevodim pitanje na engleski za AI...")
        en_question = GoogleTranslator(source='hr', target='en').translate(question)
        logger.info(f"Pitanje na engleskom: '{en_question}'")
    except Exception as e:
        logger.error(f"Greška pri prijevodu pitanja, koristim original: {e}")
        en_question = question

    if context:
        prompt = f"{SYSTEM_PROMPT}\nQuestion: {en_question}\nManual Context:\n{context}"
    else:
        prompt = f"{SYSTEM_PROMPT}\nQuestion: {en_question}\nNo manual available. Rely exclusively on visual analysis."

    payload = {
        "model": settings.AI_MODEL,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "format": AIAnalysisResult.model_json_schema(),
        "options": {
            "temperature": 0.2
        }
    }

    start = time.time()
    try:
        logger.info("Šaljem podatke u LLaVA model... (ovo može potrajati na CPU)")
        with httpx.Client(timeout=180.0) as client:
            res = client.post(f"{settings.OLLAMA_HOST}/api/generate", json=payload)
            res.raise_for_status()
            raw_response = res.json().get("response", "{}")
            logger.info(f"RAW LLaVA ODGOVOR (na engleskom): {raw_response}")
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
            rejection_reason="Error parsing model response.",
            confidence=0.0
        )

    safety_check = enforce_safety_sync(analysis_data.solution, analysis_data.diy_feasibility)
    if not safety_check["safe"]:
        analysis_data.diy_feasibility = "DO_NOT_ATTEMPT"

        reason = safety_check.get("reason", "Unknown safety reason.")
        logger.warning(f"SAFETY GUARD BLOKIRAO RJEŠENJE! Razlog: {reason}")

        analysis_data.solution = "CRITICAL DANGER: Do not touch the device or try to fix it yourself. Immediately turn off the main power supply at the fuse box. If there is an active fire, evacuate the area and call emergency services (fire department). Contact a certified electrician."
        analysis_data.dangers = "EXTREME RISK OF ELECTROCUTION AND FIRE. Requires immediate professional intervention."

    if analysis_data.confidence < 0.6 and analysis_data.diy_feasibility != "DO_NOT_ATTEMPT":
        analysis_data.solution = "The model is not entirely sure. We recommend consulting a professional."
        analysis_data.diy_feasibility = "UNKNOWN"

    # 5. Prevodimo finalne rezultate nazad na HRVATSKI
    try:
        logger.info("🔤 Prevodim JSON vrijednosti nazad na hrvatski...")
        translator = GoogleTranslator(source='en', target='hr')

        if analysis_data.rejection_reason:
            analysis_data.rejection_reason = translator.translate(analysis_data.rejection_reason)
        if analysis_data.identification:
            analysis_data.identification = translator.translate(analysis_data.identification)
        if analysis_data.solution:
            analysis_data.solution = translator.translate(analysis_data.solution)
        if analysis_data.dangers:
            analysis_data.dangers = translator.translate(analysis_data.dangers)

        # NOVO: Prevodimo i B2B polja
        if analysis_data.recommended_expert:
            analysis_data.recommended_expert = translator.translate(analysis_data.recommended_expert)

        translated_tools = []
        for tool in analysis_data.required_tools:
            translated_tools.append(translator.translate(tool))
        analysis_data.required_tools = translated_tools

    except Exception as e:
        logger.error(f"❌ Greška pri prijevodu na hrvatski: {e}")

    # 6. B2B Matchmaking (Tražimo linkove ili majstore na osnovu prevedenih podataka)
    b2b_info = match_b2b_opportunities(
        tools=analysis_data.required_tools,
        expert=analysis_data.recommended_expert,
        feasibility=analysis_data.diy_feasibility
    )

    return {
        "data": analysis_data.model_dump(),
        "b2b": b2b_info,
        "latency": latency
    }