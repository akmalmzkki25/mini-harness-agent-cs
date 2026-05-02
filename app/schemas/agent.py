from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentAction(str, Enum):
    REPLY = "reply"
    HANDOFF = "handoff"
    ESCALATE = "escalate"
    CLOSE = "close"


class AgentDecision(BaseModel):
    action: AgentAction = Field(description="Next operational action")
    response_text: str = Field(description="Message to send to the patient if action is reply or handoff")
    stage: str = Field(default="active")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    handoff_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "human", "system"]
    content: str


class AgentTurnResult(BaseModel):
    decision: AgentDecision
    used_tools: list[str] = Field(default_factory=list)
    knowledge_context: dict[str, Any] = Field(default_factory=dict)

class SummaryOutput(BaseModel):
    summary: str