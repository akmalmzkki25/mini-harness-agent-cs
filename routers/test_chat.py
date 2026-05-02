from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.setting import setting
from app.models.conversation import ConversationMessage
from app.modules.database import get_db_session
from app.modules.redis_client import get_redis_client
from app.services.agent_service import CustomerServiceAgent
from app.services.conversation_service import ConversationService
from app.services.memory_service import MemoryService
from app.utils.logger import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/test-chat", tags=["test-chat"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("", response_class=HTMLResponse)
async def test_chat_page(request: Request) -> Any:
    if not setting.USE_WEBSITE:
        raise HTTPException(status_code=404, detail="Website test chat is disabled")
    return templates.TemplateResponse(
        "test_chat.html",
        {"request": request, "dummy_token": setting.WEBSITE_DUMMY_AUTH_TOKEN},
    )


@router.get("/messages")
async def get_test_chat_messages(
    wa_id: str = Query(..., min_length=5, max_length=32),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, list[dict[str, Any]]]:
    conversation_service = ConversationService(session)
    conversation = await conversation_service.get_or_create_active_conversation(wa_id=wa_id)
    query = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.asc())
    )
    messages = list((await session.execute(query)).scalars().all())
    return {
        "messages": [
            {
                "id": str(message.id),
                "role": message.role.value,
                "content": message.content,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "files": message.files_ if isinstance(message.files_, list) else [],
                "is_fallback_timeout": (
                    isinstance(message.metadata_, dict)
                    and message.metadata_.get("scheduler") == "handoff_timeout_fallback"
                ),
            }
            for message in messages
        ]
    }


@router.post("/send")
async def send_test_chat_message(
    wa_id: str = Form(..., min_length=5, max_length=32),
    text: str = Form("", max_length=3000),
    display_name: str = Form("Website User", max_length=255),
    image: UploadFile | None = File(default=None),
    x_dummy_auth: str | None = Header(default=None, alias="X-Dummy-Auth"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if not setting.USE_WEBSITE:
        raise HTTPException(status_code=404, detail="Website test chat is disabled")
    if x_dummy_auth != setting.WEBSITE_DUMMY_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid dummy auth token")
    if not text.strip() and image is None:
        raise HTTPException(status_code=422, detail="Text atau image wajib diisi")

    redis = get_redis_client()
    memory = MemoryService(redis)
    conversation_service = ConversationService(session)
    agent = CustomerServiceAgent(session=session, memory=memory)
    files: list[str] = []

    try:
        if image is not None:
            mime_type = image.content_type or ""
            if not mime_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Saat ini hanya file image yang didukung")
            ext = Path(image.filename or "image.bin").suffix or ".bin"
            downloads_dir = Path(setting.DOWNLOADS_DIR)
            downloads_dir.mkdir(parents=True, exist_ok=True)
            file_path = downloads_dir / f"web-{uuid.uuid4().hex[:12]}{ext}"
            file_path.write_bytes(await image.read())
            files.append(str(file_path.resolve()))

        conversation = await conversation_service.get_or_create_active_conversation(
            wa_id=wa_id,
            display_name=display_name,
        )
        result = await agent.handle_user_message(
            conversation=conversation,
            text=text.strip() or "User mengirim bukti gambar",
            wa_message_id=f"web-{wa_id}-{uuid.uuid4().hex[:8]}",
            files=files,
        )
        await session.commit()
        return {
            "status": "ok",
            "conversation_id": str(conversation.id),
            "reply": result.decision.response_text,
            "action": result.decision.action.value,
            "stage": result.decision.stage,
            "confidence": result.decision.confidence,
            "files": files,
        }
    except Exception:
        await session.rollback()
        logger.exception("Website test chat request failed for wa_id=%s", wa_id)
        raise
    finally:
        await redis.aclose()
