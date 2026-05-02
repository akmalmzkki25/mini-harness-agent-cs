from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import MessageRole
from app.modules.redis_client import get_redis_client
from app.schemas.agent import ChatMessage
from app.schemas.whatsapp import CSHandoffRequest, CSReplyRequest
from app.services.agent_service import CustomerServiceAgent
from app.services.conversation_service import ConversationService
from app.services.memory_service import MemoryService
from app.services.whatsapp_service import WhatsAppService
from app.utils.logger import get_logger


logger = get_logger(__name__)


class WhatsAppController:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversation_service = ConversationService(session)
        self.whatsapp = WhatsAppService()

    async def receive_webhook(self, payload: dict) -> dict[str, str]:
        messages = await self.whatsapp.extract_messages(payload)
        logger.info("Received WhatsApp webhook payload with %s supported messages", len(messages))
        redis = get_redis_client()
        memory = MemoryService(redis)
        agent = CustomerServiceAgent(session=self.session, memory=memory)

        try:
            for message in messages:
                logger.info("Processing WhatsApp message %s from %s", message.message_id, message.wa_id)
                conversation = await self.conversation_service.get_or_create_active_conversation(
                    wa_id=message.wa_id,
                    display_name=message.display_name,
                )
                if not message.is_supported:
                    await self.conversation_service.save_message(
                        conversation_id=conversation.id,
                        role=MessageRole.USER,
                        content=message.text,
                        wa_message_id=message.message_id,
                        metadata={"message_type": message.message_type, "supported": False},
                    )
                    unsupported_text = (
                        "Untuk saat ini kami belum mendukung file selain gambar ya Kak. "
                        "Silakan kirim bukti pembayaran dalam format image (jpg/jpeg/png/webp)."
                    )
                    await self.conversation_service.save_message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=unsupported_text,
                        metadata={"system_rule": "image_only_upload"},
                    )
                    await self.whatsapp.send_text(to=message.wa_id, text=unsupported_text)
                    continue

                result = await agent.handle_user_message(
                    conversation=conversation,
                    text=message.text,
                    wa_message_id=message.message_id,
                    files=message.files,
                )
                await self.whatsapp.send_text(to=message.wa_id, text=result.decision.response_text)

            await self.session.commit()
            logger.info("WhatsApp webhook processing committed successfully")
        except Exception:
            await self.session.rollback()
            logger.exception("WhatsApp webhook processing failed and transaction rolled back")
            raise
        finally:
            await redis.aclose()
            logger.debug("Redis connection closed after webhook processing")

        return {"status": "ok"}

    async def cs_takeover(self, payload: CSHandoffRequest) -> dict[str, str]:
        conversation = await self.conversation_service.get_or_create_active_conversation(wa_id=payload.wa_id)
        await self.conversation_service.mark_human_handoff(
            conversation=conversation,
            assigned_to=payload.assigned_to,
            reason=payload.reason or "cs_takeover",
        )
        await self.conversation_service.record_event(
            conversation_id=conversation.id,
            event_type="cs_takeover",
            payload=payload.model_dump(),
        )
        await self.session.commit()
        logger.info("CS takeover set for conversation_id=%s assigned_to=%s", conversation.id, payload.assigned_to)
        return {"status": "ok"}

    async def cs_reply(self, payload: CSReplyRequest) -> dict[str, str]:
        redis = get_redis_client()
        memory = MemoryService(redis)

        try:
            conversation = await self.conversation_service.get_or_create_active_conversation(wa_id=payload.wa_id)
            await self.conversation_service.mark_human_handoff(
                conversation=conversation,
                assigned_to=payload.assigned_to,
                reason="cs_reply",
            )
            await self.conversation_service.save_message(
                conversation_id=conversation.id,
                role=MessageRole.HUMAN,
                content=payload.text,
                metadata={"assigned_to": payload.assigned_to},
            )
            await memory.add_message(conversation.id, ChatMessage(role="human", content=payload.text))
            await self.whatsapp.send_text(to=payload.wa_id, text=payload.text)
            await self.conversation_service.record_event(
                conversation_id=conversation.id,
                event_type="cs_reply",
                payload={"assigned_to": payload.assigned_to},
            )
            await self.session.commit()
            logger.info("CS reply sent conversation_id=%s assigned_to=%s", conversation.id, payload.assigned_to)
        except Exception:
            await self.session.rollback()
            logger.exception("CS reply failed for wa_id=%s", payload.wa_id)
            raise
        finally:
            await redis.aclose()

        return {"status": "ok"}
