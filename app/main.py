import base64
import hashlib
import json
import redis
import logging
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from celery.result import AsyncResult

from app.core.config import settings
from app.core.security import verify_supabase_jwt
from app.workers.tasks import analyze_task
from app.workers.celery_app import celery_app
from app.utils.image import optimize_image
from app.schemas.chat import ChatResponse
from app.services.db_service import db_service

logger = logging.getLogger(__name__)

app = FastAPI(title="UradiSam API Production")
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_user_token_for_limit(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    return "unauthenticated"

limiter = Limiter(key_func=get_user_token_for_limit)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/health")
def root():
    return {"status": "ok", "version": "2.1 Strict RLS"}

@app.post("/api/v1/analyze")
@limiter.limit("5/minute")
async def analyze(
        request: Request,
        image: Optional[UploadFile] = File(None),
        question: str = Form(...),
        chat_id: Optional[str] = Form(None),
        auth_data: dict = Depends(verify_supabase_jwt)
):
    user_id = auth_data["user_id"]
    token = auth_data["token"]

    if not chat_id:
        new_chat = db_service.create_chat(user_id, token, title=question[:30] + "...")
        chat_id = str(new_chat["id"])

    image_url = None
    base64_string = None
    cache_key = None

    if image and image.filename:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Datoteka mora biti slika.")

        file_size = 0
        image_bytes = bytearray()
        while chunk := await image.read(1024 * 1024):
            file_size += len(chunk)
            if file_size > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Slika prelazi limit.")
            image_bytes.extend(chunk)

        optimized_image_payload = optimize_image(bytes(image_bytes))

        try:
            image_url = db_service.upload_image(user_id, chat_id, token, optimized_image_payload)
        except Exception as e:
            logger.error(f"Storage upload failed: {e}")

        base64_string = base64.b64encode(optimized_image_payload).decode('utf-8')
        cache_raw_data = question.encode('utf-8') + optimized_image_payload
        cache_key = f"cache:exact_match:{hashlib.sha256(cache_raw_data).hexdigest()}"

        cached_result = redis_client.get(cache_key)
        if cached_result and chat_id is None:
            return {
                "task_id": "cached",
                "status": "completed",
                "result": json.loads(cached_result),
                "cached": True
            }

    db_service.add_message(
        chat_id=chat_id,
        user_id=user_id,
        token=token,
        role="user",
        content=question,
        image_url=image_url
    )

    task = analyze_task.delay(base64_string, question, cache_key, chat_id, user_id, token)

    return {
        "task_id": task.id,
        "chat_id": chat_id,
        "status": "processing",
        "cached": False
    }

@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    if task_id == "cached":
        return {"error": "Ovaj task je već završen."}

    task_result = AsyncResult(task_id, app=celery_app)

    if task_result.state == 'PENDING':
        return {"task_id": task_id, "status": "U redu čekanja..."}
    elif task_result.state == 'STARTED':
        return {"task_id": task_id, "status": "AI analizira..."}
    elif task_result.state == 'SUCCESS':
        return {"task_id": task_id, "status": "completed", "result": task_result.result}
    elif task_result.state == 'FAILURE':
        return {"task_id": task_id, "status": "failed", "error": str(task_result.info)}

    return {"task_id": task_id, "status": task_result.state}

@app.get("/api/v1/chats", response_model=List[ChatResponse])
async def get_user_chats(auth_data: dict = Depends(verify_supabase_jwt)):
    return db_service.get_user_chats(auth_data["user_id"], auth_data["token"])

@app.get("/api/v1/chats/{chat_id}", response_model=ChatResponse)
async def get_chat_history(chat_id: str, auth_data: dict = Depends(verify_supabase_jwt)):
    chat = db_service.get_chat_with_messages(chat_id, auth_data["user_id"], auth_data["token"])
    if not chat:
        raise HTTPException(status_code=404, detail="Chat nije pronađen.")
    return chat