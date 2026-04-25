from typing import List, Optional, Any
from supabase import create_client, Client, ClientOptions
import uuid
from app.core.config import settings

class DBService:
    def _get_client(self, token: str) -> Client:
        options = ClientOptions(headers={"Authorization": f"Bearer {token}"})
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY, options=options)

    def create_chat(self, user_id: str, token: str, title: str = "Novi popravak") -> dict:
        client = self._get_client(token)
        res = client.table("chats").insert({"user_id": user_id, "title": title}).execute()
        return res.data[0]

    def update_chat_title(self, chat_id: str, token: str, title: str):
        client = self._get_client(token)
        client.table("chats").update({"title": title}).eq("id", chat_id).execute()

    def get_user_chats(self, user_id: str, token: str) -> List[dict]:
        client = self._get_client(token)
        res = client.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
        return res.data

    def get_chat_with_messages(self, chat_id: str, user_id: str, token: str) -> Optional[dict]:
        client = self._get_client(token)
        c_res = client.table("chats").select("*").eq("id", chat_id).eq("user_id", user_id).single().execute()
        if not c_res.data:
            return None
        m_res = client.table("messages").select("*").eq("chat_id", chat_id).order("created_at", desc=False).execute()
        data = c_res.data
        data["messages"] = m_res.data
        return data

    def add_message(self, chat_id: str, user_id: str, token: str, role: str, content: str, image_url: Optional[str] = None, ai_data: Optional[Any] = None) -> dict:
        client = self._get_client(token)
        res = client.table("messages").insert({
            "chat_id": chat_id, "user_id": user_id, "role": role,
            "content": content, "image_url": image_url, "ai_data": ai_data
        }).execute()
        client.table("chats").update({"updated_at": "now()"}).eq("id", chat_id).execute()
        return res.data[0]

    def upload_image(self, user_id: str, chat_id: str, token: str, image_bytes: bytes) -> str:
        client = self._get_client(token)
        path = f"{user_id}/{chat_id}/{uuid.uuid4()}.jpg"
        client.storage.from_("repair-images").upload(path=path, file=image_bytes, file_options={"content-type": "image/jpeg"})
        return client.storage.from_("repair-images").get_public_url(path)

    def get_user_push_token(self, user_id: str) -> Optional[str]:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        try:
            res = client.table("profiles").select("push_token, notifications_enabled").eq("id", user_id).single().execute()
            if res.data and res.data.get("notifications_enabled"):
                return res.data.get("push_token")
            return None
        except Exception:
            return None

db_service = DBService()