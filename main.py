from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

from routers import webhook
from services.scheduler_jobs import enviar_recordatorios_diarios, solicitar_comprobantes_vencidos

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Recordatorio diario a las 9am hora Ciudad de Mexico
    scheduler.add_job(
        enviar_recordatorios_diarios,
        CronTrigger(hour=15, minute=0, timezone="UTC"),  # 9am CST = 15:00 UTC
        id="recordatorios_diarios",
        replace_existing=True,
    )
    # Solicitar comprobante el dia del vencimiento a las 10am
    scheduler.add_job(
        solicitar_comprobantes_vencidos,
        CronTrigger(hour=16, minute=0, timezone="UTC"),  # 10am CST
        id="solicitar_comprobantes",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado con jobs de cobranza")
    yield
    scheduler.shutdown()
    logger.info("Scheduler detenido")


app = FastAPI(
    title="CobranzaAI Backend",
    description="Backend para recordatorios de cobranza via WhatsApp con validacion de comprobantes por IA",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router, prefix="/webhook", tags=["WhatsApp Webhook"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "CobranzaAI Backend", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
