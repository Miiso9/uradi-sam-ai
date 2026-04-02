import json
import urllib.request

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import logging
from app.core.config import settings

security = HTTPBearer()
logger = logging.getLogger(__name__)

def verify_supabase_jwt(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verificira JWT token tako da direktno pita Supabase je li validan.
    Ovo rješava sve probleme s novim ECC / HS256 algoritmima.
    """
    token = credentials.credentials

    url = f"{settings.SUPABASE_URL}/auth/v1/user"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": settings.SUPABASE_ANON_KEY
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                user_id = data.get("id")

                if not user_id:
                    raise HTTPException(status_code=401, detail="Nevažeći token payload.")

                return user_id

    except urllib.error.HTTPError as e:
        logger.error(f"Supabase odbio token: {e.code}")
        raise HTTPException(status_code=401, detail="Token je istekao ili je nevažeći.")
    except Exception as e:
        logger.error(f"Greška pri spajanju na Supabase: {str(e)}")
        raise HTTPException(status_code=401, detail="Greška pri provjeri autentifikacije.")
