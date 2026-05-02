from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.setting import setting
from app.models.conversation import ConversationMessage
from app.modules.redis_client import get_redis_client
from app.services.agent_service import CustomerServiceAgent
from app.services.conversation_service import ConversationService
from app.services.memory_service import MemoryService
from app.utils.logger import get_logger


logger = get_logger(__name__)


class TestChatController:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversation_service = ConversationService(session)

    async def get_messages(self, wa_id: str) -> dict[str, list[dict[str, Any]]]:
        conversation = await self.conversation_service.get_or_create_active_conversation(wa_id=wa_id)
        query = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at.asc())
        )
        messages = list((await self.session.execute(query)).scalars().all())
        return {
            "messages": [
                {
                    "id": str(message.id),
                    "role": message.role.value,
                    "content": message.content,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "files": message.files_ if isinstance(message.files_, list) else [],
                    "is_fallback_timeout": (
                        isinstance(message.metadata_, dict)
                        and message.metadata_.get("scheduler") == "handoff_timeout_fallback"
                    ),
                }
                for message in messages
            ]
        }

    async def send_message(
        self,
        *,
        wa_id: str,
        text: str,
        display_name: str,
        image: UploadFile | None,
        auth_token: str | None,
    ) -> dict[str, Any]:
        if auth_token != setting.WEBSITE_DUMMY_AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid dummy auth token")
        if not text.strip() and image is None:
            raise HTTPException(status_code=422, detail="Text atau image wajib diisi")

        redis = get_redis_client()
        memory = MemoryService(redis)
        agent = CustomerServiceAgent(session=self.session, memory=memory)
        files: list[str] = []

        try:
            if image is not None:
                mime_type = image.content_type or ""
                if not mime_type.startswith("image/"):
                    raise HTTPException(status_code=400, detail="Saat ini hanya file image yang didukung")
                ext = Path(image.filename or "image.bin").suffix or ".bin"
                downloads_dir = Path(setting.DOWNLOADS_DIR)
                downloads_dir.mkdir(parents=True, exist_ok=True)
                file_path = downloads_dir / f"web-{uuid.uuid4().hex[:12]}{ext}"
                file_path.write_bytes(await image.read())
                files.append(str(file_path.resolve()))

            conversation = await self.conversation_service.get_or_create_active_conversation(
                wa_id=wa_id,
                display_name=display_name,
            )
            result = await agent.handle_user_message(
                conversation=conversation,
                text=text.strip() or "User mengirim bukti gambar",
                wa_message_id=f"web-{wa_id}-{uuid.uuid4().hex[:8]}",
                files=files,
            )
            await self.session.commit()
            return {
                "status": "ok",
                "conversation_id": str(conversation.id),
                "reply": result.decision.response_text,
                "action": result.decision.action.value,
                "stage": result.decision.stage,
                "confidence": result.decision.confidence,
                "files": files,
            }
        except Exception:
            await self.session.rollback()
            logger.exception("Website test chat request failed for wa_id=%s", wa_id)
            raise
        finally:
            await redis.aclose()
