from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.test_chat_controller import TestChatController
from app.core.setting import setting
from app.modules.database import get_db_session


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
    controller = TestChatController(session)
    return await controller.get_messages(wa_id)


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
    controller = TestChatController(session)
    return await controller.send_message(
        wa_id=wa_id,
        text=text,
        display_name=display_name,
        image=image,
        auth_token=x_dummy_auth,
    )
