from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationStatus, MessageRole
from app.modules.gemini_chat import assess_payment_evidence, generate_structured
from app.schemas.agent import (
    AgentAction,
    AgentDecision,
    AgentTurnResult,
    ChatMessage,
    PaymentEvidenceAssessment,
)
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
        files: list[str] | None = None,
    ) -> AgentTurnResult:
        files = files or []
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
            files=files,
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

        prechecked_decision = await self._payment_proof_precheck(
            text=text,
            files=files,
            conversation=conversation,
        )
        if prechecked_decision is not None:
            return await self._finalize_decision(
                conversation=conversation,
                decision=prechecked_decision,
                knowledge={},
            )

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

        return await self._finalize_decision(
            conversation=conversation,
            decision=decision,
            knowledge=knowledge,
        )

    async def _finalize_decision(
        self,
        *,
        conversation: Conversation,
        decision: AgentDecision,
        knowledge: dict[str, Any],
    ) -> AgentTurnResult:
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

    async def _payment_proof_precheck(
        self,
        *,
        text: str,
        files: list[str],
        conversation: Conversation,
    ) -> AgentDecision | None:
        try:
            assessment: PaymentEvidenceAssessment = await assess_payment_evidence(
                user_text=text,
                file_paths=files,
                conversation_stage=conversation.stage,
            )
        except Exception:
            logger.exception("Payment evidence assessment failed; continuing without payment precheck")
            return None

        if not assessment.is_payment_confirmation:
            return None

        if not assessment.has_image or assessment.image_relevance == "missing":
            return AgentDecision(
                action=AgentAction.REPLY,
                response_text=self._build_missing_payment_proof_message(assessment),
                stage="payment",
                confidence=max(0.8, assessment.confidence),
                handoff_reason=None,
                metadata={
                    "payment_precheck": "missing_image_proof",
                    "assessment": assessment.model_dump(),
                },
            )

        if assessment.image_relevance in {"invalid", "unclear"}:
            return AgentDecision(
                action=AgentAction.REPLY,
                response_text=self._build_invalid_or_unclear_proof_message(assessment),
                stage="payment",
                confidence=max(0.75, assessment.confidence),
                handoff_reason=None,
                metadata={
                    "payment_precheck": "image_not_confirmed",
                    "assessment": assessment.model_dump(),
                },
            )

        return AgentDecision(
            action=AgentAction.HANDOFF,
            response_text=self._build_received_payment_proof_message(assessment),
            stage="handoff",
            confidence=max(0.9, assessment.confidence),
            handoff_reason=f"Verifikasi bukti pembayaran ({assessment.scheme})",
            metadata={
                "payment_precheck": "image_received",
                "assessment": assessment.model_dump(),
                "file_count": len(files),
            },
        )

    @staticmethod
    def _build_missing_payment_proof_message(assessment: PaymentEvidenceAssessment) -> str:
        scheme_text = {
            "pembelian_produk": "pembelian produk/obat",
            "booking_konsultasi": "booking konsultasi dokter",
            "umum": "transaksi Kakak",
        }.get(assessment.scheme, "transaksi Kakak")
        return (
            f"Untuk konfirmasi {scheme_text}, mohon upload bukti pembayaran berupa gambar ya Kak "
            "(jpg/jpeg/png/webp). Tanpa gambar bukti transfer, kami belum bisa lanjut verifikasi."
        )

    @staticmethod
    def _build_invalid_or_unclear_proof_message(assessment: PaymentEvidenceAssessment) -> str:
        scheme_text = {
            "pembelian_produk": "pembelian produk/obat",
            "booking_konsultasi": "booking konsultasi dokter",
            "umum": "transaksi Kakak",
        }.get(assessment.scheme, "transaksi Kakak")
        return (
            f"Terima kasih Kak, kami sudah menerima gambar untuk {scheme_text}. "
            "Namun bukti pembayaran belum terbaca jelas/valid. Mohon kirim ulang screenshot/foto transfer "
            "yang memuat nominal, tujuan transfer, dan waktu transaksi."
        )

    @staticmethod
    def _build_received_payment_proof_message(assessment: PaymentEvidenceAssessment) -> str:
        scheme_text = {
            "pembelian_produk": "pembelian produk/obat",
            "booking_konsultasi": "booking konsultasi dokter",
            "umum": "transaksi Kakak",
        }.get(assessment.scheme, "transaksi Kakak")
        checks = assessment.checks_required or [
            "nominal transfer",
            "tujuan transfer",
            "waktu transaksi",
            "kesesuaian detail pesanan/booking",
        ]
        checks_text = ", ".join(checks)
        return (
            f"Terima kasih Kak, bukti pembayaran untuk {scheme_text} sudah kami terima. "
            f"Tim CS akan cek kesesuaian data ({checks_text}) "
            "sebelum diproses lebih lanjut."
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
