#!/usr/bin/env python3
"""
Security Monitoring System - Main Application

보안 관제 시스템 메인 FastAPI 애플리케이션
"""

import asyncio
import logging
import os
import re
from pathlib import Path
import yaml
import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# .env 파일 로드 (환경변수 설정)
load_dotenv()

# Services
from total_llm.services.command_orchestrator import CommandOrchestrator
from total_llm.services.rag_service import RAGService
from total_llm.services.device_registry import DeviceRegistry
from total_llm.services.device_control import DeviceControl
from total_llm.services.alarm_handler import AlarmHandler
from total_llm.services.kafka_consumer import SecurityAlarmConsumer
from total_llm.services.websocket_broadcaster import WebSocketBroadcaster
from total_llm.services.report_generator import ReportGenerator
from total_llm.services.log_indexer import LogIndexer
from total_llm.services.cache_service import CacheService
from total_llm.services.conversation_service import ConversationService
from total_llm.tools.rag_tool import RAGTool

# API Routers
from total_llm.api.security_chat_api import router as security_chat_router
from total_llm.api.security_chat_api import (
    set_command_orchestrator,
    set_llm_client,
    set_conversation_service,
    set_cache_service
)
from total_llm.api.alarm_api import router as alarm_router
from total_llm.api.alarm_api import set_alarm_handler
from total_llm.api.device_api import router as device_router
from total_llm.api.device_api import set_device_registry, set_device_control
from total_llm.api.report_api import router as report_router
from total_llm.api.report_api import set_report_generator
from total_llm.api.log_ingestion_api import router as log_router
from total_llm.api.log_ingestion_api import set_log_indexer
from total_llm.api.image_api import router as image_router
from total_llm.api.image_api import set_vlm_analyzer
from total_llm.api.document_api import router as document_router
from total_llm.api.document_api import set_rag_tool, set_llm_client as set_document_llm_client
from total_llm.api.control_api import router as control_router
from total_llm.api.system_api import router as system_router
from total_llm.api.auth_api import router as auth_router

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# Configuration
# ============================================

def _resolve_env_vars(value):
    """
    환경 변수 참조를 실제 값으로 치환

    지원 형식:
    - ${VAR_NAME} - 환경변수 값 (없으면 빈 문자열)
    - ${VAR_NAME:-default} - 기본값 포함
    """
    if not isinstance(value, str):
        return value

    # ${VAR:-default} 또는 ${VAR} 패턴 매칭
    pattern = r'\$\{([^}]+)\}'

    def replace_env(match):
        var_expr = match.group(1)
        if ':-' in var_expr:
            var_name, default = var_expr.split(':-', 1)
            return os.environ.get(var_name, default)
        else:
            return os.environ.get(var_expr, '')

    return re.sub(pattern, replace_env, value)


def _resolve_config_env_vars(config):
    """config dict 전체에서 환경 변수 치환"""
    if isinstance(config, dict):
        return {k: _resolve_config_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_resolve_config_env_vars(item) for item in config]
    elif isinstance(config, str):
        resolved = _resolve_env_vars(config)
        # 숫자 문자열을 int/float로 변환 시도
        if isinstance(resolved, str) and resolved.isdigit():
            return int(resolved)
        if isinstance(resolved, str) and resolved.lower() in ('true', 'false'):
            return resolved.lower() == 'true'
        return resolved
    else:
        return config


def load_config():
    """
    config.yaml 로드 및 환경 변수 치환

    YAML 파일의 ${VAR:-default} 형식을 환경 변수로 치환합니다.
    민감한 정보(비밀번호 등)는 반드시 환경 변수로 설정해야 합니다.
    """
    config_path = Path(__file__).parent / "config" / "config.yaml"
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    # 환경 변수 치환
    config = _resolve_config_env_vars(raw_config)

    # 필수 환경 변수 검증
    db_password = config.get('database', {}).get('password', '')
    if not db_password or db_password == '${POSTGRES_PASSWORD}':
        logger.warning("⚠️  POSTGRES_PASSWORD 환경변수가 설정되지 않았습니다!")
        logger.warning("   프로덕션 환경에서는 반드시 설정하세요.")
        # 개발 환경용 기본값 (프로덕션에서는 절대 사용 금지)
        if os.environ.get('ENVIRONMENT', 'development') == 'development':
            config['database']['password'] = 'total_llm_dev'
            logger.info("   개발 환경 기본값 사용: 'total_llm_dev'")

    return config


# ============================================
# Lifespan Management
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행"""
    logger.info("🚀 Starting Security Monitoring System...")

    # Configuration
    config = load_config()

    # ============================================
    # 1. Database Connection Pool
    # ============================================
    logger.info("📊 Connecting to PostgreSQL...")
    db_config = config['database']
    db_pool = await asyncpg.create_pool(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['username'],
        password=db_config['password'],
        min_size=5,
        max_size=db_config['pool_size']
    )
    app.state.db_pool = db_pool
    logger.info("✅ Database connected")

    # ============================================
    # 2. RAG Service (Qdrant + Embedding)
    # ============================================
    logger.info("🔍 Initializing RAG Service...")
    rag_service = RAGService()
    app.state.rag_service = rag_service
    logger.info("✅ RAG Service initialized")

    # ============================================
    # 3. Device Registry & Control
    # ============================================
    logger.info("🔧 Initializing Device Services...")
    device_registry = DeviceRegistry(db_pool=db_pool)
    device_control = DeviceControl(
        db_pool=db_pool,
        device_registry=device_registry,
        rollback_timeout=config['security']['device_control']['rollback_timeout_seconds']
    )
    app.state.device_registry = device_registry
    app.state.device_control = device_control
    set_device_registry(device_registry)
    set_device_control(device_control)
    logger.info("✅ Device Services initialized")

    # ============================================
    # 4. Command Orchestrator
    # ============================================
    logger.info("🎛️ Initializing Command Orchestrator...")
    command_orchestrator = CommandOrchestrator(
        rag_service=rag_service,
        device_registry=device_registry,
        device_control=device_control
    )
    app.state.command_orchestrator = command_orchestrator
    set_command_orchestrator(command_orchestrator)
    logger.info("✅ Command Orchestrator initialized")

    # ============================================
    # 5. LLM Client (Qwen - OpenAI Compatible)
    # ============================================
    logger.info("🤖 Initializing LLM Client...")
    from openai import AsyncOpenAI
    llm_client = AsyncOpenAI(
        base_url=config['llm']['base_url'],
        api_key="dummy"  # vLLM doesn't require API key
    )
    app.state.llm_client = llm_client
    set_llm_client(llm_client)
    logger.info("✅ LLM Client initialized")

    # ============================================
    # 5.1 Cache Service (Redis) - Phase 2
    # ============================================
    logger.info("💾 Initializing Cache Service...")
    try:
        cache_service = CacheService()
        await cache_service.connect()
        app.state.cache_service = cache_service
        set_cache_service(cache_service)
        logger.info("✅ Cache Service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Cache Service initialization failed: {e}")
        logger.warning("   RAG caching will be disabled")
        app.state.cache_service = None

    # ============================================
    # 5.2 Conversation Service (PostgreSQL) - Phase 2
    # ============================================
    logger.info("💬 Initializing Conversation Service...")
    try:
        conversation_service = ConversationService()
        await conversation_service.connect()
        app.state.conversation_service = conversation_service
        set_conversation_service(conversation_service)
        logger.info("✅ Conversation Service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Conversation Service initialization failed: {e}")
        logger.warning("   Conversation persistence will be disabled")
        app.state.conversation_service = None

    # ============================================
    # 6. VLM Analyzer (QwenVLM)
    # ============================================
    logger.info("👁️ Initializing VLM Analyzer...")
    from total_llm.services.vlm_analyzer import VLMAnalyzer

    # VLM 설정 (config에서 읽거나 기본값 사용)
    vlm_config = config.get('vlm', {})
    vlm_base_url = vlm_config.get('base_url', 'http://localhost:9001/v1')
    vlm_model_name = vlm_config.get('model_name', '/model')

    try:
        vlm_analyzer = VLMAnalyzer(
            base_url=vlm_base_url,
            model_name=vlm_model_name,
            max_tokens=vlm_config.get('max_tokens', 2048),
            temperature=vlm_config.get('temperature', 0.7)
        )
        app.state.vlm_analyzer = vlm_analyzer
        set_vlm_analyzer(vlm_analyzer)  # image_api에 VLM Analyzer 주입
        logger.info(f"✅ VLM Analyzer initialized (base_url={vlm_base_url})")
    except Exception as e:
        logger.warning(f"⚠️ VLM Analyzer initialization failed: {e}")
        logger.warning("   Image analysis will use fallback simulation mode")
        app.state.vlm_analyzer = None

    # ============================================
    # 7. WebSocket Broadcaster
    # ============================================
    logger.info("📡 Initializing WebSocket Broadcaster...")
    ws_broadcaster = WebSocketBroadcaster(host="0.0.0.0", port=9003)
    app.state.ws_broadcaster = ws_broadcaster

    # WebSocket 서버를 백그라운드에서 실행
    ws_task = asyncio.create_task(ws_broadcaster.start())
    app.state.ws_task = ws_task
    logger.info("✅ WebSocket Broadcaster started")

    # ============================================
    # 8. Alarm Handler
    # ============================================
    logger.info("🔔 Initializing Alarm Handler...")
    alarm_handler = AlarmHandler(
        db_pool=db_pool,
        storage_path=config['security']['alarm_images']['storage_path'],
        retention_days=config['security']['alarm_images']['retention_days'],
        websocket_broadcaster=ws_broadcaster,
        vlm_analyzer=vlm_analyzer  # VLM 통합
    )
    app.state.alarm_handler = alarm_handler
    set_alarm_handler(alarm_handler)
    logger.info("✅ Alarm Handler initialized")

    # ============================================
    # 8. Kafka Consumer (Optional)
    # ============================================
    logger.info("📨 Initializing Kafka Consumer...")
    try:
        kafka_config = config['security']['kafka']
        kafka_consumer = SecurityAlarmConsumer(
            bootstrap_servers=kafka_config['bootstrap_servers'],
            topic=kafka_config['topic'],
            group_id=kafka_config['group_id'],
            alarm_handler=alarm_handler.handle_alarm
        )
        app.state.kafka_consumer = kafka_consumer

        # Kafka Consumer를 백그라운드에서 실행
        kafka_task = asyncio.create_task(kafka_consumer.start())
        app.state.kafka_task = kafka_task
        logger.info("✅ Kafka Consumer started")
    except Exception as e:
        logger.warning(f"⚠️ Kafka Consumer failed to start (optional): {e}")
        app.state.kafka_consumer = None
        app.state.kafka_task = None

    # ============================================
    # 9. Report Generator
    # ============================================
    logger.info("📄 Initializing Report Generator...")
    report_generator = ReportGenerator(
        db_pool=db_pool,
        storage_path=config['security']['reports']['storage_path'],
        vlm_analyzer=None  # TODO: QwenVLM 통합
    )
    app.state.report_generator = report_generator
    set_report_generator(report_generator)
    logger.info("✅ Report Generator initialized")

    # ============================================
    # 10. Log Indexer
    # ============================================
    logger.info("📝 Initializing Log Indexer...")
    rag_tool = rag_service.retriever.rag_tool
    log_indexer = LogIndexer(
        db_pool=db_pool,
        rag_tool=rag_tool
    )
    app.state.log_indexer = log_indexer
    set_log_indexer(log_indexer)
    logger.info("✅ Log Indexer initialized")

    # ============================================
    # 11. Document API (RAG Tool + LLM 주입)
    # ============================================
    set_rag_tool(rag_tool)
    set_document_llm_client(llm_client)
    logger.info("✅ Document API initialized with RAG Tool and LLM")

    # ============================================
    # Startup Complete
    # ============================================
    logger.info("✅ All services initialized successfully!")
    logger.info("=" * 60)
    logger.info("🛡️  Security Monitoring System is ready!")
    logger.info("=" * 60)

    yield

    # ============================================
    # Shutdown
    # ============================================
    logger.info("🛑 Shutting down...")

    # Kafka Consumer 종료 (Optional)
    if hasattr(app.state, 'kafka_consumer') and app.state.kafka_consumer is not None:
        await app.state.kafka_consumer.stop()
        if app.state.kafka_task:
            app.state.kafka_task.cancel()

    # WebSocket Broadcaster 종료
    if hasattr(app.state, 'ws_broadcaster'):
        await app.state.ws_broadcaster.stop()
        app.state.ws_task.cancel()

    # Cache Service 종료
    if hasattr(app.state, 'cache_service') and app.state.cache_service:
        await app.state.cache_service.disconnect()

    # Conversation Service 종료
    if hasattr(app.state, 'conversation_service') and app.state.conversation_service:
        await app.state.conversation_service.disconnect()

    # Database 종료
    if hasattr(app.state, 'db_pool'):
        await app.state.db_pool.close()

    logger.info("✅ Shutdown complete")


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="Security Monitoring System API",
    description="보안 관제 시스템 백엔드 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(security_chat_router)
app.include_router(alarm_router)
app.include_router(device_router)
app.include_router(report_router)
app.include_router(log_router)
app.include_router(image_router)
app.include_router(document_router)
app.include_router(control_router)
app.include_router(system_router)
app.include_router(auth_router)

# Static Files (이미지 서빙)
app.mount(
    "/api/images",
    StaticFiles(directory="/home/sphwang/dev/vLLM/data/alarms"),
    name="alarm_images"
)

# ============================================
# Root Endpoints
# ============================================

@app.get("/")
async def root():
    """API 루트"""
    return {
        "service": "Security Monitoring System",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """전체 시스템 헬스 체크"""
    kafka_status = getattr(app.state, 'kafka_consumer', None) is not None
    cache_status = getattr(app.state, 'cache_service', None) is not None
    conversation_status = getattr(app.state, 'conversation_service', None) is not None

    return {
        "status": "healthy",
        "services": {
            "database": app.state.db_pool is not None,
            "rag": app.state.rag_service is not None,
            "device_registry": app.state.device_registry is not None,
            "device_control": app.state.device_control is not None,
            "command_orchestrator": app.state.command_orchestrator is not None,
            "llm": app.state.llm_client is not None,
            "websocket": app.state.ws_broadcaster is not None,
            "alarm_handler": app.state.alarm_handler is not None,
            "kafka": kafka_status,  # Optional service
            "report_generator": app.state.report_generator is not None,
            "log_indexer": app.state.log_indexer is not None,
            "cache": cache_status,  # Phase 2: Redis cache
            "conversation": conversation_status,  # Phase 2: Conversation persistence
        }
    }


# ============================================
# Main Entry Point
# ============================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9002,
        reload=False,  # 프로덕션에서는 False
        log_level="info"
    )
