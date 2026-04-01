import jwt
import logging
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security = HTTPBearer()
logger = logging.getLogger(__name__)

async def verify_supabase_jwt(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verificira JWT token.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Nevažeći token payload.")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token je istekao.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Nevažeći autentifikacijski token.")