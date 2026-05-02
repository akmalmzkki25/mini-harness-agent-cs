from __future__ import annotations

from pathlib import Path

from app.core.setting import setting
from app.models.conversation import Conversation, ConversationStatus, MessageRole
from app.modules.database import AsyncSessionLocal
from app.modules.redis_client import get_redis_client
from app.schemas.agent import ChatMessage
from app.services.conversation_service import ConversationService
from app.services.memory_service import MemoryService
from app.services.whatsapp_service import WhatsAppService
from app.utils.logger import get_logger


logger = get_logger(__name__)


class AgentSchedulerService:
    async def process_expired_handoffs(self) -> None:
        async with AsyncSessionLocal() as session:
            conversation_service = ConversationService(session)
            whatsapp_service = WhatsAppService()
            redis = get_redis_client()
            memory = MemoryService(redis)
            expired = await conversation_service.get_expired_handoffs()
            logger.info("Processing %s expired handoff conversations", len(expired))
            for conversation in expired:
                contact = conversation.contact
                logger.info(
                    "Applying fallback for conversation_id=%s previous_status=%s",
                    conversation.id,
                    conversation.status.value,
                )
                text = await self._build_fallback_message(conversation_service, conversation)
                await conversation_service.mark_active(conversation)
                await conversation_service.save_message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=text,
                    metadata={"scheduler": "handoff_timeout_fallback"},
                )
                await memory.add_message(conversation.id, ChatMessage(role="assistant", content=text))
                if setting.USE_WEBSITE and not setting.USE_WHATSAPP_WEBHOOK:
                    logger.info(
                        "Fallback reply stored for website test mode conversation_id=%s",
                        conversation.id,
                    )
                else:
                    await whatsapp_service.send_text(to=contact.wa_id, text=text)
                    logger.info("Fallback reply sent for expired handoff conversation_id=%s", conversation.id)
            await session.commit()
            await redis.aclose()

    def cleanup_temp_files(self) -> None:
        targets = [setting.DOWNLOADS_DIR, setting.UPLOADS_DIR]
        deleted_files = 0
        for target in targets:
            target_path = Path(target)
            if not target_path.exists():
                continue
            for file_path in target_path.rglob("*"):
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        deleted_files += 1
                    except OSError:
                        logger.exception("Failed to delete temp file path=%s", file_path)
        logger.info(
            "Temporary file cleanup completed targets=%s deleted_files=%s",
            ",".join(targets),
            deleted_files,
        )

    async def _build_fallback_message(
        self,
        conversation_service: ConversationService,
        conversation: Conversation,
    ) -> str:
        if conversation.status == ConversationStatus.HUMAN_HANDOFF:
            last_user_message = await conversation_service.get_last_user_message(conversation.id)
            suggestion = (
                f'"{last_user_message.content}"'
                if last_user_message and last_user_message.content
                else "pertanyaan terakhir Kakak"
            )
            return (
                "Sesi dengan tim CS untuk saat ini sudah kami akhiri dulu ya, Kak. "
                "Saya sebagai asisten otomatis akan lanjut membantu. "
                f"Kalau mau, kita bisa lanjut dari {suggestion}. "
                "Silakan kirim pertanyaan terbaru Kakak."
            )

        return (
            "Mohon maaf Kak, tim CS kami belum sempat mengambil alih percakapan ini. "
            "Saya bantu lanjutkan dulu ya. Ada yang ingin Kakak tanyakan lagi?"
        )
