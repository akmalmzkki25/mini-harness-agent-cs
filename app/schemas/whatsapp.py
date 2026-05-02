from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    wa_id: str
    message_id: str
    text: str
    message_type: str = "text"
    files: list[str] = Field(default_factory=list)
    is_supported: bool = True
    display_name: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WebhookVerificationResponse(BaseModel):
    challenge: str


class CSHandoffRequest(BaseModel):
    wa_id: str
    assigned_to: str
    reason: str | None = None


class CSReplyRequest(BaseModel):
    wa_id: str
    assigned_to: str
    text: str
