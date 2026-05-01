from __future__ import annotations

from typing import Any

import httpx

from app.core.setting import setting


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_request_item(text: str, title: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "model": setting.GEMINI_EMBEDDING_MODEL,
        "content": {
            "parts": [{"text": text}],
        },
        "taskType": setting.GEMINI_EMBEDDING_TASK_TYPE,
        "outputDimensionality": setting.TYPESENSE_VECTOR_DIM,
    }
    if title:
        item["title"] = title
    return item


async def request_gemini_embeddings(batch: list[dict[str, Any]]) -> list[list[float]]:
    if not setting.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in settings")

    url = f"{setting.GEMINI_API_BASE_URL}/{setting.GEMINI_EMBEDDING_MODEL}:batchEmbedContents"
    payload = {"requests": batch}
    headers = {
        "x-goog-api-key": setting.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=setting.TYPESENSE_TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini embedding request failed ({response.status_code}): {response.text}"
        )

    response_data = response.json()
    embeddings = response_data.get("embeddings", [])
    return [embedding["values"] for embedding in embeddings]


async def embed_documents(items: list[dict[str, Any]]) -> list[list[float]]:
    if not items:
        return []

    results: list[list[float]] = []
    for batch in chunked(items, setting.GEMINI_EMBEDDING_BATCH_SIZE):
        request_items = [
            build_request_item(item["text"], item.get("title"))
            for item in batch
        ]
        results.extend(await request_gemini_embeddings(request_items))

    return results
