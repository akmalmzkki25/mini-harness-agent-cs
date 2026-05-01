from __future__ import annotations

from typing import Any

import httpx

from app.core.setting import setting
from app.schemas.whatsapp import WhatsAppTextMessage
from app.utils.logger import get_logger


logger = get_logger(__name__)


class WhatsAppService:
    async def send_text(self, *, to: str, text: str) -> dict[str, Any]:
        url = (
            f"{setting.WHATSAPP_GRAPH_API_BASE_URL}/"
            f"{setting.WHATSAPP_GRAPH_API_VERSION}/{setting.WHATSAPP_PHONE_NUMBER_ID}/messages"
        )
        headers = {
            "Authorization": f"Bearer {setting.WHATSAPP_ACCESS_TOKEN}",
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

    def extract_text_messages(self, payload: dict[str, Any]) -> list[WhatsAppTextMessage]:
        messages: list[WhatsAppTextMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts = {
                    contact.get("wa_id"): contact.get("profile", {}).get("name")
                    for contact in value.get("contacts", [])
                }
                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue
                    wa_id = message.get("from")
                    messages.append(
                        WhatsAppTextMessage(
                            wa_id=wa_id,
                            message_id=message.get("id", ""),
                            text=message.get("text", {}).get("body", ""),
                            display_name=contacts.get(wa_id),
                            raw_payload=message,
                        )
                    )
        logger.debug("Extracted %s text messages from WhatsApp payload", len(messages))
        return messages
