#!/usr/bin/env python3
import asyncio
import logging
from importlib import import_module
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from total_llm.api.alarm_api import router as alarm_router
from total_llm.api.auth_api import router as auth_router
from total_llm.api.control_api import router as control_router
from total_llm.api.device_api import router as device_router
from total_llm.api.document_api import router as document_router
from total_llm.api.generator_api import router as generator_router
from total_llm.api.image_api import router as image_router
from total_llm.api.log_ingestion_api import router as log_router
from total_llm.api.report_api import router as report_router
from total_llm.api.security_chat_api import router as security_chat_router
from total_llm.api.system_api import router as system_router
from total_llm.core.config import get_settings
from total_llm.core.exceptions import register_exception_handlers
from total_llm.services.alarm_handler import AlarmHandler
from total_llm.services.cache_service import CacheService
from total_llm.services.command_orchestrator import CommandOrchestrator
from total_llm.services.conversation_service import ConversationService
from total_llm.services.device_control import DeviceControl
from total_llm.services.device_registry import DeviceRegistry
from total_llm.services.kafka_consumer import SecurityAlarmConsumer
from total_llm.services.log_indexer import LogIndexer
from total_llm.services.rag_service import RAGService
from total_llm.services.report_generator import ReportGenerator
from total_llm.services.vlm_analyzer import VLMAnalyzer
from total_llm.services.websocket_broadcaster import WebSocketBroadcaster

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings(); app.state.settings = s; logger.info("🚀 Starting Security Monitoring System...")
    db = s.database
    app.state.db_pool = await asyncpg.create_pool(host=db.host, port=db.port, database=db.database, user=db.username, password=db.password, min_size=5, max_size=db.pool_size)
    app.state.rag_service = RAGService(); app.state.device_registry = DeviceRegistry(db_pool=app.state.db_pool)
    app.state.device_control = DeviceControl(db_pool=app.state.db_pool, device_registry=app.state.device_registry, rollback_timeout=s.security.device_control.rollback_timeout_seconds)
    app.state.command_orchestrator = CommandOrchestrator(rag_service=app.state.rag_service, device_registry=app.state.device_registry, device_control=app.state.device_control)
    app.state.llm_client = AsyncOpenAI(base_url=s.llm.base_url, api_key="dummy")

    app.state.cache_service = None
    try:
        app.state.cache_service = CacheService(); await app.state.cache_service.connect()
    except Exception as e:
        logger.warning(f"Cache Service init failed: {e}")

    app.state.conversation_service = None
    try:
        app.state.conversation_service = ConversationService(); await app.state.conversation_service.connect()
    except Exception as e:
        logger.warning(f"Conversation Service init failed: {e}")

    app.state.vlm_analyzer = None
    try:
        use_shared_client = s.vlm.base_url == s.llm.base_url and s.vlm.model_name == s.llm.model_name
        vlm_client = app.state.llm_client if use_shared_client else AsyncOpenAI(base_url=s.vlm.base_url, api_key="dummy")
        app.state.vlm_analyzer = VLMAnalyzer(
            base_url=s.vlm.base_url,
            model_name=s.vlm.model_name,
            max_tokens=s.vlm.max_tokens,
            temperature=s.vlm.temperature,
            client=vlm_client,
        )
    except Exception as e:
        logger.warning(f"VLM Analyzer init failed: {e}")

    app.state.ws_broadcaster = WebSocketBroadcaster(host="0.0.0.0", port=9003); app.state.ws_task = asyncio.create_task(app.state.ws_broadcaster.start())
    app.state.alarm_handler = AlarmHandler(db_pool=app.state.db_pool, storage_path=s.security.alarm_images.storage_path, retention_days=s.security.alarm_images.retention_days, websocket_broadcaster=app.state.ws_broadcaster, vlm_analyzer=app.state.vlm_analyzer)
    app.state.kafka_consumer = None; app.state.kafka_task = None
    try:
        k = s.security.kafka
        app.state.kafka_consumer = SecurityAlarmConsumer(bootstrap_servers=k.bootstrap_servers, topic=k.topic, group_id=k.group_id, alarm_handler=app.state.alarm_handler.handle_alarm)
        app.state.kafka_task = asyncio.create_task(app.state.kafka_consumer.start())
    except Exception as e:
        logger.warning(f"Kafka Consumer start failed (optional): {e}")

    app.state.report_generator = ReportGenerator(db_pool=app.state.db_pool, storage_path=s.security.reports.storage_path, vlm_analyzer=None)
    app.state.log_indexer = LogIndexer(db_pool=app.state.db_pool, rag_tool=app.state.rag_service.retriever.rag_tool)
    logger.info("✅ All services initialized successfully")
    yield

    logger.info("🛑 Shutting down...")
    if app.state.kafka_consumer is not None:
        await app.state.kafka_consumer.stop()
        if app.state.kafka_task: app.state.kafka_task.cancel()
    await app.state.ws_broadcaster.stop(); app.state.ws_task.cancel()
    if app.state.cache_service: await app.state.cache_service.disconnect()
    if app.state.conversation_service: await app.state.conversation_service.disconnect()
    await app.state.db_pool.close(); logger.info("✅ Shutdown complete")


app = FastAPI(title="Security Monitoring System API", description="보안 관제 시스템 백엔드 API", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)
settings = get_settings()
middleware_module = import_module("total_llm.core.middleware")
RequestIDMiddleware = middleware_module.RequestIDMiddleware
TimingMiddleware = middleware_module.TimingMiddleware
SecurityHeadersMiddleware = middleware_module.SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.api.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for r in (security_chat_router, alarm_router, device_router, report_router, log_router, image_router, document_router, control_router, system_router, auth_router, generator_router):
    app.include_router(r)
app.mount("/api/images", StaticFiles(directory=settings.security.alarm_images.storage_path), name="alarm_images")


@app.get("/")
async def root():
    return {"service": "Security Monitoring System", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "services": {"database": app.state.db_pool is not None, "rag": app.state.rag_service is not None, "device_registry": app.state.device_registry is not None, "device_control": app.state.device_control is not None, "command_orchestrator": app.state.command_orchestrator is not None, "llm": app.state.llm_client is not None, "websocket": app.state.ws_broadcaster is not None, "alarm_handler": app.state.alarm_handler is not None, "kafka": app.state.kafka_consumer is not None, "report_generator": app.state.report_generator is not None, "log_indexer": app.state.log_indexer is not None, "cache": app.state.cache_service is not None, "conversation": app.state.conversation_service is not None}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("total_llm.app:app", host=settings.api.host, port=settings.api.port, reload=False, log_level="info")
