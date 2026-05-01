from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.modules.typesense_common import ensure_ok, get_typesense_config, request_typesense


FAQ_COLLECTION = "faq_obat"
PRODUCT_COLLECTION = "data_produk"


def build_faq_schema(vector_dim: int) -> dict[str, Any]:
    return {
        "name": FAQ_COLLECTION,
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "pertanyaan", "type": "string"},
            {"name": "jawaban", "type": "string"},
            {"name": "document_type", "type": "string", "facet": True},
            {"name": "source_file", "type": "string", "facet": True},
            {"name": "content", "type": "string"},
            {"name": "vector", "type": "float[]", "num_dim": vector_dim},
        ],
    }


def build_product_schema(vector_dim: int) -> dict[str, Any]:
    return {
        "name": PRODUCT_COLLECTION,
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "nama_produk", "type": "string"},
            {"name": "function", "type": "string"},
            {"name": "description", "type": "string"},
            {"name": "caution_side_effect", "type": "string"},
            {"name": "aturan_pakai", "type": "string"},
            {"name": "objective", "type": "string"},
            {"name": "pricing", "type": "string"},
            {"name": "document_type", "type": "string", "facet": True},
            {"name": "source_file", "type": "string", "facet": True},
            {"name": "content", "type": "string"},
            {"name": "vector", "type": "float[]", "num_dim": vector_dim},
        ],
    }


async def collection_exists(name: str) -> bool:
    response = await request_typesense("GET", f"/collections/{name}")
    if response.status_code == 404:
        return False
    await ensure_ok(response, {200})
    return True


async def recreate_collection(schema: dict[str, Any]) -> None:
    name = schema["name"]
    if await collection_exists(name):
        await ensure_ok(await request_typesense("DELETE", f"/collections/{name}"), {200})

    await ensure_ok(
        await request_typesense("POST", "/collections", json_body=schema),
        {201},
    )


async def init_typesense_collections() -> None:
    config = get_typesense_config()
    await recreate_collection(build_faq_schema(config["vector_dim"]))
    await recreate_collection(build_product_schema(config["vector_dim"]))


if __name__ == "__main__":
    asyncio.run(init_typesense_collections())
    print("Typesense collections initialized successfully.")
