from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.setting import setting
from app.modules.gemini_chat import generate_structured
from app.schemas.agent import ChatMessage, SummaryOutput
from app.utils.logger import get_logger


logger = get_logger(__name__)


class MemoryService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def add_message(self, conversation_id: UUID, message: ChatMessage) -> None:
        key = self._messages_key(conversation_id)
        await self.redis.rpush(key, message.model_dump_json())
        await self.redis.expire(key, 60 * 60 * 24 * 14)
        logger.debug("Added memory message conversation_id=%s role=%s", conversation_id, message.role)
        await self._summarize_if_needed(conversation_id)

    async def get_context(self, conversation_id: UUID) -> tuple[str, list[ChatMessage]]:
        summary = await self.redis.get(self._summary_key(conversation_id)) or ""
        raw_items = await self.redis.lrange(self._messages_key(conversation_id), 0, -1)
        logger.debug("Loaded memory context conversation_id=%s message_count=%s", conversation_id, len(raw_items))
        return summary, [ChatMessage.model_validate_json(item) for item in raw_items]

    async def _summarize_if_needed(self, conversation_id: UUID) -> None:
        key = self._messages_key(conversation_id)
        count = await self.redis.llen(key)
        if count <= setting.AGENT_MAX_RAW_MESSAGES:
            return
        logger.info("Summarizing memory conversation_id=%s message_count=%s", conversation_id, count)

        overflow_count = count - setting.AGENT_MAX_RAW_MESSAGES
        overflow = await self.redis.lrange(key, 0, overflow_count - 1)
        existing_summary = await self.redis.get(self._summary_key(conversation_id)) or ""
        messages = [ChatMessage.model_validate_json(item) for item in overflow]
        transcript = "\n".join(f"{item.role}: {item.content}" for item in messages)
        prompt = (
            "Ringkas percakapan customer service Mahva Clinic berikut untuk memory agent. "
            "Pertahankan nama, kebutuhan pasien, keberatan, status pembayaran/booking, dan hal yang perlu follow-up.\n\n"
            f"Ringkasan sebelumnya:\n{existing_summary or '-'}\n\nPercakapan baru:\n{transcript}\n\n"
            'Kembalikan JSON dengan key "summary".'
        )
        try:
            result: SummaryOutput = await generate_structured(prompt, SummaryOutput)
            summary = result.summary
            logger.debug("Memory summarization succeeded conversation_id=%s", conversation_id)
        except Exception:
            logger.exception("Memory summarization failed conversation_id=%s; using fallback summary", conversation_id)
            summary = f"{existing_summary}\n{transcript}".strip()

        await self.redis.set(self._summary_key(conversation_id), summary, ex=60 * 60 * 24 * 30)
        await self.redis.ltrim(key, overflow_count, -1)
        logger.info("Memory summary updated conversation_id=%s trimmed_messages=%s", conversation_id, overflow_count)

    @staticmethod
    def _messages_key(conversation_id: UUID) -> str:
        return f"agent:conversation:{conversation_id}:messages"

    @staticmethod
    def _summary_key(conversation_id: UUID) -> str:
        return f"agent:conversation:{conversation_id}:summary"
