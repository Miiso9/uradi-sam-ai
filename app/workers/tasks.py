import json
import logging
from typing import Optional
from app.workers.celery_app import celery_app
from app.services.ai_service import analyze_sync, generate_chat_title, send_expo_push_notification
from app.services.b2b_service import match_b2b_opportunities
from app.services.db_service import db_service
from app.core.config import settings
import redis

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
logger = logging.getLogger(__name__)

@celery_app.task(name="app.workers.tasks.analyze_task", bind=True)
def analyze_task(self, image_64: Optional[str], question: str, cache_key: Optional[str], chat_id: str, user_id: str, token: str):
    try:
        self.update_state(state='STARTED')

        chat_history = []
        if chat_id:
            full_chat = db_service.get_chat_with_messages(chat_id, user_id, token)
            if full_chat and "messages" in full_chat:
                for msg in full_chat["messages"]:
                    role = "user" if msg["role"] == "user" else "assistant"
                    content = msg["content"]

                    if role == "assistant" and msg.get("ai_data"):
                        ai_data = msg["ai_data"].get("data", {})
                        if ai_data:
                            ident = ai_data.get("identification", "")
                            tools = ", ".join(ai_data.get("required_tools", []))
                            content = f"[PREVIOUS IDENTIFICATION: {ident}]\n[PREVIOUS TOOLS: {tools}]\n{content}"

                    chat_history.append({
                        "role": role,
                        "content": content
                    })

        raw_ai_response = analyze_sync(
            image_base64=image_64,
            question=question,
            history=chat_history
        )

        analysis_data = raw_ai_response.get("data", {})
        tools = analysis_data.get("required_tools", [])
        expert = analysis_data.get("recommended_expert", "")
        feasibility = analysis_data.get("diy_feasibility", "")

        b2b_data = match_b2b_opportunities(
            tools=tools,
            expert=expert,
            feasibility=feasibility
        )

        final_result = {
            "data": analysis_data,
            "b2b": b2b_data
        }

        db_service.add_message(
            chat_id=chat_id,
            user_id=user_id,
            token=token,
            role="ai",
            content=analysis_data.get("solution", "Analiza završena."),
            ai_data=final_result
        )

        try:
            push_token = db_service.get_user_push_token(user_id)
            if push_token:
                problem_id = analysis_data.get("identification", "Popravak je spreman")
                send_expo_push_notification(
                    token=push_token,
                    title="AI Majstor je završio!",
                    body=f"Rešenje: {problem_id[:50]}...",
                    data={"chat_id": chat_id}
                )
        except Exception as e:
            logger.error(f"Greška pri slanju notifikacije: {e}")

        if not chat_history:
            try:
                new_title = generate_chat_title(question, analysis_data.get("solution", ""))
                db_service.update_chat_title(chat_id, token, new_title)
            except Exception as e:
                logger.error(f"Greška pri naslovu: {e}")

        if cache_key and not chat_history:
            redis_client.setex(cache_key, settings.CACHE_EXPIRE_SECONDS, json.dumps(final_result))

        return final_result

    except Exception as e:
        logger.error(f"Greška u workeru: {str(e)}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise e