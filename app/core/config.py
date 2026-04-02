import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "UradiSam API Production"
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    AI_MODEL: str = os.getenv("AI_MODEL", "llava")
    SAFETY_MODEL: str = os.getenv("SAFETY_MODEL", "llama3")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    MAX_IMAGE_SIZE_MB: int = 5
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")

settings = Settings()