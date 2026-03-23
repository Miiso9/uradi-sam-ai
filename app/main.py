import base64
import hashlib
import json
import redis
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
    """
    Izvlači token direktno iz headera za potrebe rate limitera.
    Ako nema tokena, stavlja ga u 'unauthenticated' bucket (koji će ionako biti
    blokiran sa 401 Unauthorized od strane verify_supabase_jwt u ruti).
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    return "unauthenticated"

limiter = Limiter(key_func=get_user_token_for_limit)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/health")
def root():
    return {"status": "ok", "version": "2.1 Production Phase 1"}

@app.post("/api/v1/analyze")
@limiter.limit("5/minute")
async def analyze(
        request: Request,
        image: UploadFile = File(...),
        question: str = Form(...),
        user_id: str = Depends(verify_supabase_jwt)
):
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Datoteka mora biti slika.")

    file_size = 0
    image_bytes = bytearray()
    while chunk := await image.read(1024 * 1024):
        file_size += len(chunk)
        if file_size > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Slika prelazi 5MB limit.")
        image_bytes.extend(chunk)

    optimized_bytes = optimize_image(bytes(image_bytes))
    cache_raw_data = question.encode('utf-8') + optimized_bytes
    cache_key = f"cache:exact_match:{hashlib.sha256(cache_raw_data).hexdigest()}"

    cached_result = redis_client.get(cache_key)
    if cached_result:
        return {
            "task_id": "cached",
            "status": "completed",
            "result": json.loads(cached_result),
            "cached": True
        }

    base64_string = base64.b64encode(optimized_bytes).decode('utf-8')
    task = analyze_task.delay(base64_string, question, cache_key)

    return {
        "task_id": task.id,
        "status": "processing",
        "cached": False
    }

@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    if task_id == "cached":
        return {"error": "Ovaj task je već završen i serviran iz cache-a."}

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