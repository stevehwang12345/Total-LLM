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
    from total_llm.services.control.system_controller import SystemController
    from total_llm.services.control.network_discovery import NetworkDiscoveryService
    from total_llm.services.control.device_registry import DeviceRegistry as ControlDeviceRegistry
    from total_llm.services.control.connection_health import ConnectionHealthService
    from total_llm.services.control.zone_manager import ZoneManager
    from total_llm.services.control.audit_logger import AuditLogger
    from total_llm.services.control.rate_limiter import RateLimiter
    from total_llm.services.control.credential_manager import CredentialManager
    from total_llm.services.api_generator import DeviceAnalyzer
    from total_llm.services.api_generator.review import ReviewWorkflow, AdapterDeployer


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


def get_control_system_controller(request: Request) -> "SystemController":
    from total_llm.services.control.system_controller import SystemController

    controller = getattr(request.app.state, "control_system_controller", None)
    if controller is None:
        settings = get_settings()
        controller = SystemController(
            model_name=settings.llm.model_name,
            vllm_base_url=settings.llm.base_url,
            simulation_mode=settings.device_control.default_mode == "simulation",
        )
        request.app.state.control_system_controller = controller
    return controller


def get_control_network_discovery(request: Request) -> "NetworkDiscoveryService":
    from total_llm.services.control.network_discovery import NetworkDiscoveryService

    discovery = getattr(request.app.state, "control_network_discovery", None)
    if discovery is None:
        discovery = NetworkDiscoveryService()
        request.app.state.control_network_discovery = discovery
    return discovery


def get_control_device_registry(request: Request) -> "ControlDeviceRegistry":
    from total_llm.services.control.device_registry import DeviceRegistry

    registry = getattr(request.app.state, "control_device_registry", None)
    if registry is None:
        registry = DeviceRegistry()
        request.app.state.control_device_registry = registry
    return registry


def get_control_health_service(request: Request) -> "ConnectionHealthService":
    from total_llm.services.control.connection_health import ConnectionHealthService

    service = getattr(request.app.state, "control_health_service", None)
    if service is None:
        service = ConnectionHealthService()
        request.app.state.control_health_service = service
    return service


def get_control_zone_manager(request: Request) -> "ZoneManager":
    from total_llm.services.control.zone_manager import ZoneManager

    manager = getattr(request.app.state, "control_zone_manager", None)
    if manager is None:
        manager = ZoneManager()
        request.app.state.control_zone_manager = manager
    return manager


def get_control_audit_logger(request: Request) -> "AuditLogger":
    from total_llm.services.control.audit_logger import AuditLogger

    logger_service = getattr(request.app.state, "control_audit_logger", None)
    if logger_service is None:
        logger_service = AuditLogger()
        request.app.state.control_audit_logger = logger_service
    return logger_service


def get_control_rate_limiter(request: Request) -> "RateLimiter":
    from total_llm.services.control.rate_limiter import RateLimiter

    limiter = getattr(request.app.state, "control_rate_limiter", None)
    if limiter is None:
        limiter = RateLimiter()
        request.app.state.control_rate_limiter = limiter
    return limiter


def get_control_credential_manager(request: Request) -> "CredentialManager":
    from total_llm.services.control.credential_manager import CredentialManager

    manager = getattr(request.app.state, "control_credential_manager", None)
    if manager is None:
        manager = CredentialManager(key=get_settings().device_credential_key or None)
        request.app.state.control_credential_manager = manager
    return manager


def get_generator_device_analyzer(request: Request) -> "DeviceAnalyzer":
    from total_llm.services.api_generator import DeviceAnalyzer

    analyzer = getattr(request.app.state, "generator_device_analyzer", None)
    if analyzer is None:
        analyzer = DeviceAnalyzer()
        request.app.state.generator_device_analyzer = analyzer
    return analyzer


def get_generator_review_workflow(request: Request) -> "ReviewWorkflow":
    from total_llm.services.api_generator.review import ReviewWorkflow

    workflow = getattr(request.app.state, "generator_review_workflow", None)
    if workflow is None:
        workflow = ReviewWorkflow()
        request.app.state.generator_review_workflow = workflow
    return workflow


def get_generator_deployer(request: Request) -> "AdapterDeployer":
    from total_llm.services.api_generator.review import AdapterDeployer

    deployer = getattr(request.app.state, "generator_deployer", None)
    if deployer is None:
        deployer = AdapterDeployer()
        request.app.state.generator_deployer = deployer
    return deployer


def get_generator_analyses(request: Request) -> dict[str, Any]:
    analyses = getattr(request.app.state, "generator_analyses", None)
    if analyses is None:
        analyses = {}
        request.app.state.generator_analyses = analyses
    return analyses


def get_generator_specs(request: Request) -> dict[str, Any]:
    specs = getattr(request.app.state, "generator_specs", None)
    if specs is None:
        specs = {}
        request.app.state.generator_specs = specs
    return specs


def get_generator_artifacts(request: Request) -> dict[str, Any]:
    artifacts = getattr(request.app.state, "generator_artifacts", None)
    if artifacts is None:
        artifacts = {}
        request.app.state.generator_artifacts = artifacts
    return artifacts


def get_system_server_processes(request: Request) -> dict[str, Any]:
    processes = getattr(request.app.state, "system_server_processes", None)
    if processes is None:
        processes = {"llm": None, "vlm": None}
        request.app.state.system_server_processes = processes
    return processes


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
ControlSystemControllerDep = Annotated[Any, Depends(get_control_system_controller)]
ControlNetworkDiscoveryDep = Annotated[Any, Depends(get_control_network_discovery)]
ControlDeviceRegistryDep = Annotated[Any, Depends(get_control_device_registry)]
ControlHealthServiceDep = Annotated[Any, Depends(get_control_health_service)]
ControlZoneManagerDep = Annotated[Any, Depends(get_control_zone_manager)]
ControlAuditLoggerDep = Annotated[Any, Depends(get_control_audit_logger)]
ControlRateLimiterDep = Annotated[Any, Depends(get_control_rate_limiter)]
ControlCredentialManagerDep = Annotated[Any, Depends(get_control_credential_manager)]
GeneratorDeviceAnalyzerDep = Annotated[Any, Depends(get_generator_device_analyzer)]
GeneratorReviewWorkflowDep = Annotated[Any, Depends(get_generator_review_workflow)]
GeneratorDeployerDep = Annotated[Any, Depends(get_generator_deployer)]
GeneratorAnalysesDep = Annotated[Any, Depends(get_generator_analyses)]
GeneratorSpecsDep = Annotated[Any, Depends(get_generator_specs)]
GeneratorArtifactsDep = Annotated[Any, Depends(get_generator_artifacts)]
SystemServerProcessesDep = Annotated[Any, Depends(get_system_server_processes)]
