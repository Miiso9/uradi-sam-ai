import time
import httpx
import logging
from typing import Optional, List, Dict
from deep_translator import GoogleTranslator

from app.core.config import settings
from app.services.rag_service import retrieve_context_with_timeout
from app.services.prompts import SYSTEM_PROMPT
from app.services.safety_guard import enforce_safety_sync
from app.schemas.ai_models import AIAnalysisResult
from app.utils.json_utils import extract_json_string

logger = logging.getLogger(__name__)

def analyze_sync(image_base64: Optional[str], question: str, history: List[Dict] = []) -> dict:
    logger.info(f"Započinjem AI analizu za upit: '{question}'")
    context = retrieve_context_with_timeout(question)

    try:
        en_question = GoogleTranslator(source='hr', target='en').translate(question)
    except Exception as e:
        logger.error(f"Greška pri prijevodu pitanja: {e}")
        en_question = question

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    final_user_prompt = ""

    if context:
        final_user_prompt += (
            f"--- POTENTIAL MANUAL CONTEXT ---\n{context}\n"
            f"(IMPORTANT: Ignore this context completely if it does not match the image. "
            f"Do not set is_relevant to false just because this manual text is wrong.)\n\n"
        )

    if history:
        final_user_prompt += "--- PREVIOUS CONVERSATION HISTORY ---\n"
        for msg in history:
            role_name = "User" if msg["role"] == "user" else "AI"
            final_user_prompt += f"{role_name}: {msg['content']}\n"

        final_user_prompt += (
            "\n(CRITICAL: The above was the past conversation. Now answer the CURRENT QUESTION below. "
            "You MUST still return ONLY the requested JSON format. DO NOT use placeholder words like 'tool1'.)\n\n"
        )

    final_user_prompt += f"--- CURRENT QUESTION ---\n{en_question}"

    current_message = {
        "role": "user",
        "content": final_user_prompt
    }
    if image_base64:
        current_message["images"] = [image_base64]

    messages.append(current_message)

    payload = {
        "model": settings.AI_MODEL,
        "messages": messages,
        "stream": False,
        "format": AIAnalysisResult.model_json_schema(),
        "options": {"temperature": 0.2, "num_ctx": 4096}
    }

    start = time.time()
    try:
        with httpx.Client(timeout=180.0) as client:
            res = client.post(f"{settings.OLLAMA_HOST}/api/chat", json=payload)
            res.raise_for_status()
            response_json = res.json()
            raw_response = response_json.get("message", {}).get("content", "{}")
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise RuntimeError(f"AI obrada neuspješna: {e}")

    latency = round(time.time() - start, 2)

    try:
        clean_json = extract_json_string(raw_response)
        analysis_data = AIAnalysisResult.model_validate_json(clean_json)
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        analysis_data = AIAnalysisResult(is_relevant=False, rejection_reason="Error parsing model response.", confidence=0.0)

    safety_check = enforce_safety_sync(analysis_data.solution, analysis_data.diy_feasibility)
    if safety_check.get("override"):
        analysis_data.diy_feasibility = "DO_NOT_ATTEMPT"
        analysis_data.solution = "CRITICAL DANGER: Hazardous elements detected. Do not attempt yourself. Contact a professional."
        analysis_data.dangers = "EXTREME RISK OF INJURY OR PROPERTY DAMAGE."

    try:
        translator = GoogleTranslator(source='en', target='hr')
        if analysis_data.rejection_reason: analysis_data.rejection_reason = translator.translate(analysis_data.rejection_reason)
        if analysis_data.identification: analysis_data.identification = translator.translate(analysis_data.identification)
        if analysis_data.solution: analysis_data.solution = translator.translate(analysis_data.solution)
        if analysis_data.dangers: analysis_data.dangers = translator.translate(analysis_data.dangers)
        if analysis_data.recommended_expert: analysis_data.recommended_expert = translator.translate(analysis_data.recommended_expert)
        analysis_data.required_tools = [translator.translate(t) for t in analysis_data.required_tools]
    except Exception as e:
        logger.error(f"Greška pri prijevodu na HR: {e}")

    from app.services.b2b_service import match_b2b_opportunities
    b2b_info = match_b2b_opportunities(
        tools=analysis_data.required_tools,
        expert=analysis_data.recommended_expert,
        feasibility=analysis_data.diy_feasibility
    )

    return {"data": analysis_data.model_dump(), "b2b": b2b_info, "latency": latency}

def generate_chat_title(question: str, solution: str) -> str:
    """Generira kratki naslov za chat."""
    try:
        prompt = f"Na temelju pitanja '{question}' i rješenja '{solution}', vrati naslov od 3-4 riječi na hrvatskom. Vrati samo tekst bez navodnika."
        payload = {"model": settings.AI_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.3}}
        with httpx.Client(timeout=30.0) as client:
            res = client.post(f"{settings.OLLAMA_HOST}/api/generate", json=payload)
            res.raise_for_status()
            return res.json().get("response", "Novi popravak").strip()
    except:
        return question[:30]