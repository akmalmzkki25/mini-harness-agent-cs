from __future__ import annotations

import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.setting import setting
from app.schemas.agent import PaymentEvidenceAssessment
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    return json.loads(cleaned)


def _normalize_model_name(model_name: str) -> str:
    return model_name.removeprefix("models/")


def _get_client() -> genai.Client:
    return genai.Client(api_key=setting.GEMINI_API_KEY)


async def _generate_text_sync(prompt: str) -> str:
    logger.info("Requesting Gemini text generation with model=%s", setting.GEMINI_CHAT_MODEL)
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=_normalize_model_name(setting.GEMINI_CHAT_MODEL),
        contents=prompt,
        config={
            "temperature": 0.6,
        },
    )

    text = getattr(response, "text", None)
    if not text:
        logger.error("Gemini text generation returned empty response text")
        raise RuntimeError("Gemini chat request failed: empty response text")
    logger.debug("Gemini text generation completed successfully")
    return text


async def generate_text(prompt: str) -> str:
    if not setting.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in settings")
    return await _generate_text_sync(prompt)


async def _generate_structured_sync(prompt: str, output_model: type[BaseModel]) -> BaseModel:
    logger.info(
        "Requesting Gemini structured generation with model=%s schema=%s",
        setting.GEMINI_CHAT_MODEL,
        output_model.__name__,
    )
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=_normalize_model_name(setting.GEMINI_CHAT_MODEL),
        contents=prompt,
        config={
            "temperature": 0.6,
            "response_mime_type": "application/json",
            "response_json_schema": output_model.model_json_schema(),
        },
    )
    text = getattr(response, "text", None)
    if not text:
        logger.error("Gemini structured generation returned empty response text")
        raise RuntimeError("Gemini structured request failed: empty response text")
    logger.debug("Gemini structured generation completed successfully")
    return output_model.model_validate(_extract_json(text))


async def generate_structured(prompt: str, output_model: type[BaseModel]) -> BaseModel:
    if not setting.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in settings")
    return await _generate_structured_sync(prompt, output_model)


def _build_inline_image_parts(file_paths: list[str]) -> list[types.Part]:
    parts: list[types.Part] = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            logger.warning("Skipping non-existent image path: %s", file_path)
            continue
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type or not mime_type.startswith("image/"):
            logger.warning("Skipping non-image file path for Gemini inline input: %s", file_path)
            continue
        parts.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type))
    return parts


async def assess_payment_evidence(
    *,
    user_text: str,
    file_paths: list[str],
    conversation_stage: str,
) -> PaymentEvidenceAssessment:
    if not setting.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in settings")

    prompt = (
        "Anda adalah pemeriksa konfirmasi pembayaran untuk customer service klinik.\n"
        "Tugas Anda:\n"
        "1) Tentukan apakah pesan user adalah konfirmasi pembayaran atau bukan.\n"
        "2) Jika iya, tentukan skema transaksi: pembelian_produk, booking_konsultasi, atau umum.\n"
        "3) Jika ada gambar, nilai apakah gambar relevan sebagai bukti pembayaran: valid, unclear, invalid.\n"
        "4) Jika tidak ada gambar tetapi ini konfirmasi pembayaran, image_relevance harus missing.\n"
        "5) Berikan checks_required berisi poin cek manual CS, misalnya nominal, tujuan transfer, waktu, nama produk/jadwal.\n"
        "Jawab hanya JSON sesuai schema yang diberikan.\n\n"
        f"Stage percakapan saat ini: {conversation_stage}\n"
        f"Pesan user: {user_text}\n"
    )
    content_parts: list[Any] = [prompt]
    content_parts.extend(_build_inline_image_parts(file_paths))
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=_normalize_model_name(setting.GEMINI_CHAT_MODEL),
        contents=content_parts,
        config={
            "temperature": 0.6,
            "response_mime_type": "application/json",
            "response_json_schema": PaymentEvidenceAssessment.model_json_schema(),
        },
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Payment evidence assessment failed: empty response text")
    return PaymentEvidenceAssessment.model_validate(_extract_json(text))
