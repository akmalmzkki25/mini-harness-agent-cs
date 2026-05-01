from __future__ import annotations

import asyncio
import json
from typing import Any

from google import genai
from pydantic import BaseModel

from app.core.setting import setting
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
