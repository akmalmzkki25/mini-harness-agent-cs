from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.modules.database import create_database_schema
from app.services.scheduler_service import AgentSchedulerService
from app.utils.logger import configure_logging, get_logger
from app.core.setting import setting
from routers.test_chat import router as test_chat_router
from routers.whatsapp import router as whatsapp_router


configure_logging()
logger = get_logger(__name__)
scheduler = AgentSchedulerService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup initiated")
    await create_database_schema()
    scheduler.start()
    logger.info("Application startup completed")
    yield
    logger.info("Application shutdown initiated")
    await scheduler.stop()
    logger.info("Application shutdown completed")


app = FastAPI(title="Qlip CS WhatsApp Agent", version="0.1.0", lifespan=lifespan)
if setting.USE_WHATSAPP_WEBHOOK:
    app.include_router(whatsapp_router)

if setting.USE_WEBSITE:
    app.include_router(test_chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    logger.debug("Health check requested")
    return {"status": "ok"}


@app.get("/")
async def index():
    if setting.USE_WEBSITE:
        return RedirectResponse(url="/test-chat")
    return {"status": "ok", "message": "Service is running. Use /health."}
