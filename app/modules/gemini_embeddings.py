from __future__ import annotations

import asyncio
from typing import Any

from google import genai
from google.genai import types

from app.core.setting import setting
from app.utils.logger import get_logger


logger = get_logger(__name__)


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_request_item(text: str, title: str | None = None) -> dict[str, Any]:
    return {"content": text, "title": title}


def _normalize_model_name(model_name: str) -> str:
    return model_name.removeprefix("models/")


def _get_client() -> genai.Client:
    return genai.Client(api_key=setting.GEMINI_API_KEY)


async def _request_gemini_embeddings_sync(batch: list[dict[str, Any]]) -> list[list[float]]:
    client = _get_client()
    model_name = _normalize_model_name(setting.GEMINI_EMBEDDING_MODEL)
    contents = [item["content"] for item in batch]
    logger.info("Requesting Gemini embeddings with model=%s batch_size=%s", model_name, len(contents))

    response = await client.aio.models.embed_content(
        model=model_name,
        contents=contents,
        config=types.EmbedContentConfig(
            task_type=setting.GEMINI_EMBEDDING_TASK_TYPE,
            output_dimensionality=setting.TYPESENSE_VECTOR_DIM,
        ),
    )

    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        vectors = [list(getattr(embedding, "values", []) or []) for embedding in embeddings]
        if all(vectors):
            logger.debug("Gemini embeddings request completed successfully")
            return vectors

    single_embedding = getattr(response, "embedding", None)
    single_values = list(getattr(single_embedding, "values", []) or [])
    if single_values and len(batch) == 1:
        logger.debug("Gemini embeddings request completed with single embedding fallback")
        return [single_values]

    logger.error("Gemini embeddings request returned empty values")
    raise RuntimeError("Gemini embedding request failed: empty embedding values")


async def request_gemini_embeddings(batch: list[dict[str, Any]]) -> list[list[float]]:
    if not setting.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in settings")
    return await _request_gemini_embeddings_sync(batch)


async def embed_documents(items: list[dict[str, Any]]) -> list[list[float]]:
    if not items:
        logger.debug("embed_documents called with empty items")
        return []

    results: list[list[float]] = []
    for batch in chunked(items, setting.GEMINI_EMBEDDING_BATCH_SIZE):
        request_items = [
            build_request_item(item["text"], item.get("title"))
            for item in batch
        ]
        results.extend(await request_gemini_embeddings(request_items))

    logger.info("Embedded %s documents successfully", len(items))
    return results
