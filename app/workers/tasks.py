import json
import redis
from app.workers.celery_app import celery_app
from app.services.ai_service import analyze_sync
from app.core.config import settings

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

@celery_app.task(bind=True, max_retries=3)
def analyze_task(self, image_base64: str, question: str, cache_key: str = None):
    """
    Izvršava pozadinsku obradu koristeći sinkrone funkcije.
    Ako obrada prođe uspješno, sprema rezultat u Redis cache.
    """
    try:
        result = analyze_sync(image_base64, question)

        if cache_key and "error" not in result:
            try:
                redis_client.set(cache_key, json.dumps(result), ex=86400)
            except Exception as redis_err:
                print(f"Greška pri spremanju u cache: {redis_err}")

        return result

    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)