from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.core.setting import setting
from app.utils.logger import get_logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "app" / "data"
logger = get_logger(__name__)


class SimpleResponse:
    def __init__(self, status_code: int, text: str, json_data: Any | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.json_data = json_data


def get_typesense_config() -> dict[str, Any]:
    uri = setting.TYPESENSE_URI.rstrip("/")
    api_key = setting.TYPESENSE_API_KEY
    vector_dim = setting.TYPESENSE_VECTOR_DIM
    timeout = setting.TYPESENSE_TIMEOUT_SECONDS

    if not uri:
        raise ValueError("TYPESENSE_URI is not set in settings")
    if not api_key:
        raise ValueError("TYPESENSE_API_KEY is not set in settings")

    return {
        "uri": uri,
        "api_key": api_key,
        "vector_dim": vector_dim,
        "timeout": timeout,
    }


def _json_response(payload: Any, status_code: int = 200) -> SimpleResponse:
    return SimpleResponse(
        status_code=status_code,
        text=json.dumps(payload, ensure_ascii=False),
        json_data=payload,
    )


async def request_typesense(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: str | None = None,
) -> SimpleResponse:
    config = get_typesense_config()
    headers = {
        "X-TYPESENSE-API-KEY": config["api_key"],
        "Content-Type": "application/json",
    }
    url = f"{config['uri']}{path}"

    try:
        logger.debug("Typesense request started method=%s path=%s", method.upper(), path)
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            if path.endswith("/documents/search"):
                search_params = params or json_body or {}
                vector_query = str(search_params.get("vector_query", ""))
                force_body = method.upper() == "POST" or len(vector_query) > 1000

                if force_body:
                    collection_name = path.strip("/").split("/")[1]
                    logger.info("Using Typesense multi_search fallback for collection=%s", collection_name)
                    payload = {
                        "searches": [
                            {
                                "collection": collection_name,
                                **search_params,
                            }
                        ]
                    }
                    response = await client.post(
                        f"{config['uri']}/multi_search",
                        headers=headers,
                        json=payload,
                    )
                    if response.is_success:
                        multi_data = response.json()
                        if isinstance(multi_data, dict) and multi_data.get("results"):
                            logger.debug("Typesense multi_search succeeded for collection=%s", collection_name)
                            return _json_response(multi_data["results"][0], response.status_code)
                    return SimpleResponse(response.status_code, response.text)

            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                content=data,
            )
            if "application/json" in response.headers.get("content-type", ""):
                logger.debug("Typesense request completed with JSON response status=%s", response.status_code)
                return _json_response(response.json(), response.status_code)
            logger.debug("Typesense request completed with text response status=%s", response.status_code)
            return SimpleResponse(response.status_code, response.text)
    except httpx.HTTPError as error:
        logger.exception("Typesense request failed method=%s path=%s", method.upper(), path)
        return SimpleResponse(status_code=500, text=json.dumps({"message": str(error)}))


async def ensure_ok(response: SimpleResponse, expected_statuses: set[int]) -> SimpleResponse:
    if response.status_code not in expected_statuses:
        raise RuntimeError(
            f"Typesense request failed ({response.status_code}): {response.text}"
        )
    return response


async def load_json_file(filename: str) -> list[dict[str, Any]]:
    path = DATA_DIR / filename
    logger.debug("Loading JSON file from %s", path)
    return json.loads(path.read_text(encoding="utf-8"))
