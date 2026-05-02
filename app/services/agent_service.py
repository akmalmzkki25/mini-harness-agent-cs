from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationStatus, MessageRole
from app.modules.gemini_chat import generate_structured
from app.schemas.agent import AgentAction, AgentDecision, AgentTurnResult, ChatMessage
from app.services.conversation_service import ConversationService
from app.services.memory_service import MemoryService
from app.tools import DataProdukSearchTool, FaqObatSearchTool
from app.utils.logger import get_logger


logger = get_logger(__name__)


class CustomerServiceAgent:
    def __init__(self, *, session: AsyncSession, memory: MemoryService) -> None:
        self.conversation_service = ConversationService(session)
        self.memory = memory
        self.faq_tool = FaqObatSearchTool()
        self.product_tool = DataProdukSearchTool()

    async def handle_user_message(
        self,
        *,
        conversation: Conversation,
        text: str,
        wa_message_id: str | None = None,
    ) -> AgentTurnResult:
        logger.info(
            "Handling user message conversation_id=%s status=%s",
            conversation.id,
            conversation.status.value,
        )
        await self.conversation_service.save_message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=text,
            wa_message_id=wa_message_id,
        )
        await self.memory.add_message(conversation.id, ChatMessage(role="user", content=text))

        if conversation.status == ConversationStatus.HUMAN_HANDOFF:
            logger.info("Conversation %s is in human handoff state", conversation.id)
            decision = AgentDecision(
                action=AgentAction.HANDOFF,
                response_text="Baik Kak, pesan Kakak akan dilanjutkan oleh tim CS kami ya.",
                stage=conversation.stage,
                confidence=1.0,
                handoff_reason="Conversation is currently assigned to human CS",
            )
            return AgentTurnResult(decision=decision)

        knowledge = await self._retrieve_knowledge(text)
        summary, recent_messages = await self.memory.get_context(conversation.id)
        logger.debug(
            "Conversation %s memory loaded summary_present=%s recent_messages=%s",
            conversation.id,
            bool(summary),
            len(recent_messages),
        )
        decision = await self._decide(
            user_text=text,
            conversation=conversation,
            summary=summary,
            recent_messages=recent_messages,
            knowledge=knowledge,
        )

        if decision.action in {AgentAction.HANDOFF, AgentAction.ESCALATE}:
            logger.info(
                "Conversation %s moving to handoff action=%s reason=%s",
                conversation.id,
                decision.action.value,
                decision.handoff_reason,
            )
            await self.conversation_service.mark_handoff_pending(
                conversation=conversation,
                reason=decision.handoff_reason or decision.action.value,
            )
        elif decision.action == AgentAction.REPLY:
            logger.info("Conversation %s remains active with reply action", conversation.id)
            await self.conversation_service.mark_active(conversation)

        await self.conversation_service.save_message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=decision.response_text,
            metadata={"agent_action": decision.action.value, "confidence": decision.confidence},
        )
        await self.conversation_service.record_event(
            conversation_id=conversation.id,
            event_type=f"agent_{decision.action.value}",
            payload={"decision": decision.model_dump(), "knowledge": knowledge},
        )
        await self.memory.add_message(
            conversation.id,
            ChatMessage(role="assistant", content=decision.response_text),
        )
        return AgentTurnResult(
            decision=decision,
            used_tools=["faq_obat.hybrid_search", "data_produk.hybrid_search"],
            knowledge_context=knowledge,
        )

    async def _retrieve_knowledge(self, query: str) -> dict[str, Any]:
        logger.debug("Retrieving knowledge for query=%s", query)
        faq_result, product_result = await asyncio.gather(
            self.faq_tool.hybrid_search(query, per_page=3),
            self.product_tool.hybrid_search(query, per_page=3),
        )
        knowledge = {
            "faq_obat": self._compact_hits(faq_result),
            "data_produk": self._compact_hits(product_result),
        }
        logger.info(
            "Knowledge retrieval completed faq_hits=%s product_hits=%s",
            len(knowledge["faq_obat"]),
            len(knowledge["data_produk"]),
        )
        return knowledge

    async def _decide(
        self,
        *,
        user_text: str,
        conversation: Conversation,
        summary: str,
        recent_messages: list[ChatMessage],
        knowledge: dict[str, Any],
    ) -> AgentDecision:
        prompt = self._build_prompt(
            user_text=user_text,
            conversation=conversation,
            summary=summary,
            recent_messages=recent_messages,
            knowledge=knowledge,
        )
        try:
            result: AgentDecision = await generate_structured(prompt, AgentDecision)
            logger.info(
                "Agent decision generated action=%s stage=%s confidence=%.2f",
                result.action.value,
                result.stage,
                result.confidence,
            )
            return result  # type: ignore[return-value]
        except Exception:
            logger.exception("Agent decision generation failed; falling back to handoff")
            return AgentDecision(
                action=AgentAction.HANDOFF,
                response_text=(
                    "Mohon tunggu sebentar ya Kak, saya bantu teruskan ke tim CS kami "
                    "agar jawabannya lebih tepat."
                ),
                stage=conversation.stage,
                confidence=0.3,
                handoff_reason="agent_decision_failed",
            )

    def _build_prompt(
        self,
        *,
        user_text: str,
        conversation: Conversation,
        summary: str,
        recent_messages: list[ChatMessage],
        knowledge: dict[str, Any],
    ) -> str:
        transcript = "\n".join(f"{item.role}: {item.content}" for item in recent_messages[-10:])
        return f"""
        Anda adalah agent CS Online Mahva Clinic untuk WhatsApp. Jawab ramah, singkat, dan profesional dalam Bahasa Indonesia dengan sapaan "Kak".

        Tujuan utama:
        - Bantu jawab pertanyaan umum berdasarkan knowledge base.
        - Arahkan pasien ke konsultasi dokter online Rp150.000 via chat sebagai default.
        - Video call hanya jika pasien meminta.
        - Jangan membuat diagnosis, resep, klaim medis baru, atau janji di luar knowledge base.

        Wajib handoff/eskalasi ke CS manusia jika:
        - pasien meminta refund/pembatalan setelah bayar
        - komplain keras, marah, mengancam, atau isu legal
        - bukti pembayaran perlu diverifikasi
        - pasien meminta konsultasi offline
        - dokter tidak tersedia, reschedule kompleks, atau pengiriman obat bermasalah
        - pertanyaan medis personal yang butuh dokter

        Status percakapan saat ini: {conversation.status.value}
        Stage saat ini: {conversation.stage}
        Ringkasan memory: {summary or "-"}
        Percakapan terbaru:
        {transcript or "-"}

        Knowledge hasil tools:
        {json.dumps(knowledge, ensure_ascii=False)}

        Pesan pasien terbaru:
        {user_text}

        Kembalikan JSON valid saja dengan bentuk:
        {{
            "action": "reply|handoff|escalate|close",
            "response_text": "teks yang dikirim ke pasien",
            "stage": "new_lead|education|booking|payment|questionnaire|consultation|medicine_invoice|shipping|follow_up|handoff",
            "confidence": 0.0,
            "handoff_reason": null,
            "metadata": {{}}
        }}
        """

    @staticmethod
    def _compact_hits(result: dict[str, Any]) -> list[dict[str, Any]]:
        hits = result.get("hits", []) if isinstance(result, dict) else []
        compacted: list[dict[str, Any]] = []
        for hit in hits[:3]:
            document = hit.get("document", {})
            compacted.append(
                {
                    "text_match": hit.get("text_match"),
                    "vector_distance": hit.get("vector_distance"),
                    "document": document,
                }
            )
        return compacted
