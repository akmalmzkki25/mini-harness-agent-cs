from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

import httpx

from app.core.setting import setting
from app.schemas.whatsapp import IncomingMessage
from app.utils.logger import get_logger


logger = get_logger(__name__)


class WhatsAppService:
    @staticmethod
    def _auth_headers() -> dict[str, str]:
        return {
            "Authorization": f"Bearer {setting.WHATSAPP_ACCESS_TOKEN}",
        }

    async def send_text(self, *, to: str, text: str) -> dict[str, Any]:
        url = (
            f"{setting.WHATSAPP_GRAPH_API_BASE_URL}/"
            f"{setting.WHATSAPP_GRAPH_API_VERSION}/{setting.WHATSAPP_PHONE_NUMBER_ID}/messages"
        )
        headers = {
            **self._auth_headers(),
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        logger.info("Sending WhatsApp text message to=%s", to)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            logger.error("WhatsApp send failed to=%s status=%s", to, response.status_code)
            raise RuntimeError(f"WhatsApp send failed ({response.status_code}): {response.text}")
        logger.debug("WhatsApp send succeeded to=%s", to)
        return response.json()

    async def _download_media_to_downloads(self, media_id: str) -> str:
        media_meta_url = (
            f"{setting.WHATSAPP_GRAPH_API_BASE_URL}/"
            f"{setting.WHATSAPP_GRAPH_API_VERSION}/{media_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            meta_response = await client.get(media_meta_url, headers=self._auth_headers())
            if meta_response.status_code >= 400:
                raise RuntimeError(
                    f"Failed to fetch WhatsApp media metadata ({meta_response.status_code}): {meta_response.text}"
                )
            meta = meta_response.json()
            media_url = meta.get("url")
            mime_type = meta.get("mime_type", "")
            if not media_url:
                raise RuntimeError("WhatsApp media metadata does not include a URL")
            if not str(mime_type).startswith("image/"):
                raise RuntimeError(f"Unsupported WhatsApp media mime type: {mime_type}")

            binary_response = await client.get(media_url, headers=self._auth_headers())
            if binary_response.status_code >= 400:
                raise RuntimeError(
                    f"Failed to download WhatsApp media ({binary_response.status_code}): {binary_response.text}"
                )
            content_type = binary_response.headers.get("content-type", mime_type)
            if not str(content_type).startswith("image/"):
                raise RuntimeError(f"Downloaded media is not image content-type: {content_type}")

            extension = content_type.split("/", 1)[1].split(";")[0].strip() or "bin"
            downloads_dir = Path(setting.DOWNLOADS_DIR)
            downloads_dir.mkdir(parents=True, exist_ok=True)
            filename = f"wa-{media_id}-{uuid.uuid4().hex[:8]}.{extension}"
            filepath = downloads_dir / filename
            filepath.write_bytes(binary_response.content)
            logger.info("Downloaded WhatsApp image media_id=%s to %s", media_id, filepath)
            return str(filepath.resolve())

    async def extract_messages(self, payload: dict[str, Any]) -> list[IncomingMessage]:
        messages: list[IncomingMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts = {
                    contact.get("wa_id"): contact.get("profile", {}).get("name")
                    for contact in value.get("contacts", [])
                }
                for message in value.get("messages", []):
                    wa_id = message.get("from")
                    message_type = message.get("type", "")
                    message_id = message.get("id", "")
                    if message_type == "text":
                        messages.append(
                            IncomingMessage(
                                wa_id=wa_id,
                                message_id=message_id,
                                text=message.get("text", {}).get("body", ""),
                                message_type="text",
                                files=[],
                                is_supported=True,
                                display_name=contacts.get(wa_id),
                                raw_payload=message,
                            )
                        )
                        continue

                    if message_type == "image":
                        image_payload = message.get("image", {})
                        media_id = image_payload.get("id", "")
                        caption = image_payload.get("caption", "")
                        if not media_id:
                            continue
                        image_path = await self._download_media_to_downloads(media_id)
                        messages.append(
                            IncomingMessage(
                                wa_id=wa_id,
                                message_id=message_id,
                                text=caption or "User mengirim bukti gambar",
                                message_type="image",
                                files=[image_path],
                                is_supported=True,
                                display_name=contacts.get(wa_id),
                                raw_payload=message,
                            )
                        )
                        continue
                    if message_type:
                        messages.append(
                            IncomingMessage(
                                wa_id=wa_id,
                                message_id=message_id,
                                text=f"User mengirim file tipe {message_type}",
                                message_type=message_type,
                                files=[],
                                is_supported=False,
                                display_name=contacts.get(wa_id),
                                raw_payload=message,
                            )
                        )
        logger.debug("Extracted %s supported WhatsApp messages", len(messages))
        return messages
