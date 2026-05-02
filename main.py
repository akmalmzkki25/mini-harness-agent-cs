from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
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
agent_scheduler_service = AgentSchedulerService()
apscheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup initiated")
    await create_database_schema()
    apscheduler.add_job(
        agent_scheduler_service.process_expired_handoffs,
        trigger=IntervalTrigger(seconds=setting.AGENT_SCHEDULER_INTERVAL_SECONDS),
        id="process_expired_handoffs",
        replace_existing=True,
        max_instances=1,
    )
    apscheduler.add_job(
        agent_scheduler_service.cleanup_temp_files,
        trigger=IntervalTrigger(hours=3),
        id="cleanup_temp_files",
        replace_existing=True,
        max_instances=1,
    )
    apscheduler.start()
    logger.info(
        "APScheduler started with jobs: handoff_interval=%ss cleanup_interval=3h",
        setting.AGENT_SCHEDULER_INTERVAL_SECONDS,
    )
    logger.info("Application startup completed")
    yield
    logger.info("Application shutdown initiated")
    apscheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")
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
