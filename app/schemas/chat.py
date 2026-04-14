from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID

class MessageResponse(BaseModel):
    id: UUID
    chat_id: UUID
    role: str
    content: str
    image_url: Optional[str] = None
    ai_data: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[MessageResponse]] = []

class Config:
    from_attributes = True

class ChatCreate(BaseModel):
    title: Optional[str] = "Novi popravak"