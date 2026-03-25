"""FastAPI dependency injection accessors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Annotated

from fastapi import Depends, Request
from openai import AsyncOpenAI

from total_llm.core.config import Settings, get_settings as _get_settings

if TYPE_CHECKING:
    from asyncpg import Pool
    from total_llm.services.alarm_handler import AlarmHandler
    from total_llm.services.cache_service import CacheService
    from total_llm.services.command_orchestrator import CommandOrchestrator
    from total_llm.services.conversation_service import ConversationService
    from total_llm.services.device_control import DeviceControl
    from total_llm.services.device_registry import DeviceRegistry
    from total_llm.services.log_indexer import LogIndexer
    from total_llm.services.rag_service import RAGService
    from total_llm.services.report_generator import ReportGenerator
    from total_llm.services.vlm_analyzer import VLMAnalyzer
    from total_llm.tools.rag_tool import RAGTool


def get_db_pool(request: Request) -> "Pool":
    return request.app.state.db_pool


def get_rag_service(request: Request) -> "RAGService":
    from total_llm.services.rag_service import RAGService

    service: RAGService = request.app.state.rag_service
    return service


def get_llm_client(request: Request) -> AsyncOpenAI:
    return request.app.state.llm_client


def get_vlm_analyzer(request: Request) -> "VLMAnalyzer | None":
    from total_llm.services.vlm_analyzer import VLMAnalyzer

    analyzer: VLMAnalyzer | None = request.app.state.vlm_analyzer
    return analyzer


def get_command_orchestrator(request: Request) -> "CommandOrchestrator":
    from total_llm.services.command_orchestrator import CommandOrchestrator

    orchestrator: CommandOrchestrator = request.app.state.command_orchestrator
    return orchestrator


def get_device_registry(request: Request) -> "DeviceRegistry":
    return request.app.state.device_registry


def get_device_control(request: Request) -> "DeviceControl":
    return request.app.state.device_control


def get_alarm_handler(request: Request) -> "AlarmHandler":
    return request.app.state.alarm_handler


def get_report_generator(request: Request) -> "ReportGenerator":
    return request.app.state.report_generator


def get_log_indexer(request: Request) -> "LogIndexer":
    return request.app.state.log_indexer


def get_cache_service(request: Request) -> "CacheService | None":
    return request.app.state.cache_service


def get_conversation_service(request: Request) -> "ConversationService | None":
    return request.app.state.conversation_service


def get_rag_tool(request: Request) -> "RAGTool":
    return request.app.state.rag_service.retriever.rag_tool


def get_settings() -> Settings:
    return _get_settings()


DbPoolDep = Annotated[Any, Depends(get_db_pool)]
RAGServiceDep = Annotated[Any, Depends(get_rag_service)]
LLMClientDep = Annotated[Any, Depends(get_llm_client)]
VLMAnalyzerDep = Annotated[Any, Depends(get_vlm_analyzer)]
CommandOrchestratorDep = Annotated[Any, Depends(get_command_orchestrator)]
DeviceRegistryDep = Annotated[Any, Depends(get_device_registry)]
DeviceControlDep = Annotated[Any, Depends(get_device_control)]
AlarmHandlerDep = Annotated[Any, Depends(get_alarm_handler)]
ReportGeneratorDep = Annotated[Any, Depends(get_report_generator)]
LogIndexerDep = Annotated[Any, Depends(get_log_indexer)]
CacheServiceDep = Annotated[Any, Depends(get_cache_service)]
ConversationServiceDep = Annotated[Any, Depends(get_conversation_service)]
RAGToolDep = Annotated[Any, Depends(get_rag_tool)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
