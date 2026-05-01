from __future__ import annotations

from typing import Any, Optional

from app.modules.gemini_embeddings import embed_documents
from app.modules.typesense_common import ensure_ok, request_typesense
from app.utils.logger import get_logger


class DataProdukSearchTool:
    COLLECTION_NAME = "data_produk"
    DEFAULT_QUERY_BY = "nama_produk,function,description,objective,aturan_pakai,caution_side_effect,pricing,content,document_type,source_file"
    DEFAULT_QUERY_BY_WEIGHTS = "8,7,6,5,4,3,2,5,1,1"
    DEFAULT_EXCLUDE_FIELDS = "vector"
    DEFAULT_TEXT_MATCH_TYPE = "max_weight"
    logger = get_logger(__name__)

    async def keyword_search(
        self,
        query: str,
        *,
        query_by: Optional[str] = None,
        per_page: int = 1,
    ) -> dict[str, Any]:
        self.logger.debug("Product keyword search query=%s per_page=%s", query, per_page)
        response = await request_typesense(
            "GET",
            f"/collections/{self.COLLECTION_NAME}/documents/search",
            params=self._build_search_payload(
                query=query,
                per_page=per_page,
                query_by=query_by,
            ),
        )
        await ensure_ok(response, {200})
        self.logger.info("Product keyword search completed hits=%s", len((response.json_data or {}).get("hits", [])))
        return response.json_data or {}

    async def vector_search(
        self,
        query: str,
        *,
        per_page: int = 1,
    ) -> dict[str, Any]:
        self.logger.debug("Product vector search query=%s per_page=%s", query, per_page)
        query_vector = await embed_documents([{"text": query, "title": "produk_query"}])
        vector_query = self._build_vector_query(query_vector[0], per_page)

        response = await request_typesense(
            "POST",
            f"/collections/{self.COLLECTION_NAME}/documents/search",
            json_body=self._build_search_payload(
                query="*",
                per_page=per_page,
                vector_query=vector_query,
            ),
        )
        await ensure_ok(response, {200})
        self.logger.info("Product vector search completed hits=%s", len((response.json_data or {}).get("hits", [])))
        return response.json_data or {}

    async def hybrid_search(
        self,
        query: str,
        *,
        per_page: int = 1,
        alpha: float = 0.7,
    ) -> dict[str, Any]:
        self.logger.debug("Product hybrid search query=%s per_page=%s alpha=%s", query, per_page, alpha)
        query_vector = await embed_documents([{"text": query, "title": "produk_query"}])
        vector_query = self._build_vector_query(query_vector[0], per_page)

        response = await request_typesense(
            "POST",
            f"/collections/{self.COLLECTION_NAME}/documents/search",
            json_body=self._build_search_payload(
                query=query,
                per_page=per_page,
                vector_query=vector_query,
                alpha=alpha,
            ),
        )
        await ensure_ok(response, {200})
        self.logger.info("Product hybrid search completed hits=%s", len((response.json_data or {}).get("hits", [])))
        return response.json_data or {}

    def _build_search_payload(
        self,
        *,
        query: str,
        per_page: int,
        query_by: Optional[str] = None,
        vector_query: Optional[str] = None,
        alpha: Optional[float] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "q": query,
            "query_by": query_by or self.DEFAULT_QUERY_BY,
            "query_by_weights": self.DEFAULT_QUERY_BY_WEIGHTS,
            "text_match_type": self.DEFAULT_TEXT_MATCH_TYPE,
            "exclude_fields": self.DEFAULT_EXCLUDE_FIELDS,
            "per_page": per_page,
        }
        if vector_query is not None:
            payload["vector_query"] = vector_query
        if alpha is not None:
            payload["alpha"] = alpha
        return payload

    @staticmethod
    def _build_vector_query(vector: list[float], per_page: int) -> str:
        compact_vector = [round(value, 6) for value in vector]
        return f"vector:([{','.join(map(str, compact_vector))}], k:{per_page})"
