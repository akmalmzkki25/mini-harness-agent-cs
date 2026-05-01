from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.commands.init_typesense import FAQ_COLLECTION, PRODUCT_COLLECTION

from app.modules.gemini_embeddings import embed_documents
from app.modules.typesense_common import (
    ensure_ok,
    load_json_file,
    request_typesense,
)
from app.utils.logger import get_logger


logger = get_logger(__name__)


async def build_faq_documents() -> list[dict[str, Any]]:
    raw_documents = await load_json_file("faq_obat.json")
    logger.info("Building FAQ documents count=%s", len(raw_documents))
    documents: list[dict[str, Any]] = []
    embedding_inputs: list[dict[str, Any]] = []

    for index, item in enumerate(raw_documents, start=1):
        content = f"Pertanyaan: {item['pertanyaan']}\nJawaban: {item['jawaban']}"
        documents.append(
            {
                "id": f"faq-{index}",
                "pertanyaan": item["pertanyaan"],
                "jawaban": item["jawaban"],
                "document_type": "faq_obat",
                "source_file": "faq_obat.json",
                "content": content,
            }
        )
        embedding_inputs.append({"text": content, "title": item["pertanyaan"]})

    vectors = await embed_documents(embedding_inputs)
    for document, vector in zip(documents, vectors):
        document["vector"] = vector

    return documents


async def build_product_documents() -> list[dict[str, Any]]:
    raw_documents = await load_json_file("data_produk.json")
    logger.info("Building product documents count=%s", len(raw_documents))
    documents: list[dict[str, Any]] = []
    embedding_inputs: list[dict[str, Any]] = []

    for index, item in enumerate(raw_documents, start=1):
        content = "\n".join(
            [
                f"Nama produk: {item['nama_produk']}",
                f"Fungsi: {item['function']}",
                f"Deskripsi: {item['description']}",
                f"Efek samping dan perhatian: {item['caution_side_effect']}",
                f"Aturan pakai: {item['aturan_pakai']}",
                f"Objektif: {item['objective']}",
                f"Harga: {item['pricing']}",
            ]
        )
        documents.append(
            {
                "id": f"product-{index}",
                "nama_produk": item["nama_produk"],
                "function": item["function"],
                "description": item["description"],
                "caution_side_effect": item["caution_side_effect"],
                "aturan_pakai": item["aturan_pakai"],
                "objective": item["objective"],
                "pricing": item["pricing"],
                "document_type": "data_produk",
                "source_file": "data_produk.json",
                "content": content,
            }
        )
        embedding_inputs.append({"text": content, "title": item["nama_produk"]})

    vectors = await embed_documents(embedding_inputs)
    for document, vector in zip(documents, vectors):
        document["vector"] = vector

    return documents


async def import_documents(collection_name: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    logger.info("Importing documents into Typesense collection=%s count=%s", collection_name, len(documents))
    payload = "\n".join(json.dumps(document, ensure_ascii=False) for document in documents)
    response = await request_typesense(
        "POST",
        f"/collections/{collection_name}/documents/import",
        params={"action": "upsert"},
        data=payload,
    )
    await ensure_ok(response, {200})
    logger.info("Typesense import completed collection=%s", collection_name)
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


async def index_all_typesense_data() -> dict[str, list[dict[str, Any]]]:
    logger.info("Starting full Typesense data indexing")
    faq_documents = await build_faq_documents()
    product_documents = await build_product_documents()
    faq_result = await import_documents(FAQ_COLLECTION, faq_documents)
    product_result = await import_documents(PRODUCT_COLLECTION, product_documents)
    result = {
        FAQ_COLLECTION: faq_result,
        PRODUCT_COLLECTION: product_result,
    }
    logger.info("Completed full Typesense data indexing")
    return result


if __name__ == "__main__":
    result = asyncio.run(index_all_typesense_data())
    faq_count = len(result[FAQ_COLLECTION])
    product_count = len(result[PRODUCT_COLLECTION])
    print(f"Indexed {faq_count} FAQ documents and {product_count} product documents.")
