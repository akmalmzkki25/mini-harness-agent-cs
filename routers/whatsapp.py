from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.whatsapp_controller import WhatsAppController
from app.core.setting import setting
from app.modules.database import get_db_session
from app.schemas.whatsapp import CSHandoffRequest, CSReplyRequest
from app.utils.logger import get_logger


router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
logger = get_logger(__name__)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    if hub_mode == "subscribe" and hub_verify_token == setting.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verification succeeded")
        return PlainTextResponse(hub_challenge)
    logger.warning("WhatsApp webhook verification failed")
    raise HTTPException(status_code=403, detail="Invalid WhatsApp verify token")


@router.post("")
async def receive_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    payload = await request.json()
    controller = WhatsAppController(session)
    return await controller.receive_webhook(payload)


@router.post("/cs/takeover")
async def cs_takeover(
    payload: CSHandoffRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    controller = WhatsAppController(session)
    return await controller.cs_takeover(payload)


@router.post("/cs/reply")
async def cs_reply(
    payload: CSReplyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    controller = WhatsAppController(session)
    return await controller.cs_reply(payload)
