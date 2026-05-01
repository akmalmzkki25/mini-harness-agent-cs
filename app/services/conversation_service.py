from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.setting import setting
from app.models.conversation import (
    AgentEvent,
    Contact,
    Conversation,
    ConversationMessage,
    ConversationStatus,
    MessageRole,
)
from app.utils.logger import get_logger


logger = get_logger(__name__)


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_active_conversation(
        self,
        *,
        wa_id: str,
        display_name: str | None = None,
    ) -> Conversation:
        contact = await self._get_or_create_contact(wa_id=wa_id, display_name=display_name)
        query = (
            select(Conversation)
            .where(Conversation.contact_id == contact.id)
            .where(Conversation.status != ConversationStatus.CLOSED)
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        conversation = (await self.session.execute(query)).scalar_one_or_none()
        if conversation:
            logger.debug("Found existing conversation %s for wa_id=%s", conversation.id, wa_id)
            return conversation

        conversation = Conversation(contact_id=contact.id)
        self.session.add(conversation)
        await self.session.flush()
        logger.info("Created new conversation %s for wa_id=%s", conversation.id, wa_id)
        return conversation

    async def save_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        wa_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            wa_message_id=wa_message_id,
            metadata_=metadata or {},
        )
        self.session.add(message)
        await self.session.flush()
        logger.debug("Saved message %s role=%s conversation_id=%s", message.id, role.value, conversation_id)
        return message

    async def record_event(
        self,
        *,
        conversation_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> AgentEvent:
        event = AgentEvent(conversation_id=conversation_id, event_type=event_type, payload=payload)
        self.session.add(event)
        await self.session.flush()
        logger.debug("Recorded event %s type=%s conversation_id=%s", event.id, event_type, conversation_id)
        return event

    async def mark_handoff_pending(
        self,
        *,
        conversation: Conversation,
        reason: str,
        assigned_to: str | None = None,
    ) -> Conversation:
        conversation.status = ConversationStatus.HANDOFF_PENDING
        conversation.assigned_to = assigned_to
        conversation.handoff_reason = reason
        conversation.handoff_deadline_at = datetime.now(timezone.utc) + timedelta(
            seconds=setting.AGENT_HANDOFF_TIMEOUT_SECONDS
        )
        logger.info("Conversation %s marked handoff_pending reason=%s", conversation.id, reason)
        return conversation

    async def mark_human_handoff(
        self,
        *,
        conversation: Conversation,
        assigned_to: str | None = None,
        reason: str | None = None,
    ) -> Conversation:
        conversation.status = ConversationStatus.HUMAN_HANDOFF
        conversation.assigned_to = assigned_to
        conversation.handoff_reason = reason or conversation.handoff_reason
        conversation.handoff_deadline_at = datetime.now(timezone.utc) + timedelta(
            seconds=setting.AGENT_HANDOFF_TIMEOUT_SECONDS
        )
        logger.info(
            "Conversation %s marked human_handoff assigned_to=%s",
            conversation.id,
            assigned_to,
        )
        return conversation

    async def mark_active(self, conversation: Conversation) -> Conversation:
        conversation.status = ConversationStatus.ACTIVE
        conversation.handoff_reason = None
        conversation.handoff_deadline_at = None
        logger.info("Conversation %s marked active", conversation.id)
        return conversation

    async def get_expired_handoffs(self) -> list[Conversation]:
        now = datetime.now(timezone.utc)
        query = (
            select(Conversation)
            .options(selectinload(Conversation.contact))
            .where(
                Conversation.status.in_(
                    [ConversationStatus.HANDOFF_PENDING, ConversationStatus.HUMAN_HANDOFF]
                )
            )
            .where(Conversation.handoff_deadline_at <= now)
        )
        conversations = list((await self.session.execute(query)).scalars().all())
        logger.debug("Found %s expired handoff conversations", len(conversations))
        return conversations

    async def get_last_user_message(self, conversation_id: UUID) -> ConversationMessage | None:
        query = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .where(ConversationMessage.role == MessageRole.USER)
            .order_by(ConversationMessage.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(query)).scalar_one_or_none()

    async def _get_or_create_contact(self, *, wa_id: str, display_name: str | None) -> Contact:
        query = select(Contact).where(Contact.wa_id == wa_id)
        contact = (await self.session.execute(query)).scalar_one_or_none()
        if contact:
            if display_name and contact.display_name != display_name:
                contact.display_name = display_name
                logger.debug("Updated contact display_name for wa_id=%s", wa_id)
            return contact

        contact = Contact(wa_id=wa_id, display_name=display_name)
        self.session.add(contact)
        await self.session.flush()
        logger.info("Created contact %s for wa_id=%s", contact.id, wa_id)
        return contact
