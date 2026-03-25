"""
외부 시스템 제어 서비스 모듈

Function Calling 기반으로 ACU(출입통제) 및 CCTV(영상감시) 시스템을 제어합니다.

주요 기능:
- ACU/CCTV 장치 제어 (Function Calling)
- 네트워크 장치 탐색
- 장치 등록 및 인증 관리 (암호화)
- 연결 상태 모니터링 및 헬스체크
"""

from .function_schemas import ACU_FUNCTIONS, CCTV_FUNCTIONS, ALL_FUNCTIONS
from .acu_controller import ACUController
from .cctv_controller import CCTVController
from .system_controller import SystemController
from .network_discovery import NetworkDiscoveryService, get_discovery_service
from .device_registry import DeviceRegistry, get_device_registry, RegisteredDevice
from .credential_manager import CredentialManager, get_credential_manager
from .connection_health import ConnectionHealthService, get_health_service
from .zone_manager import ZoneManager, Zone, SecurityLevel, get_zone_manager
from .audit_logger import AuditLogger, AuditEventType, AuditSeverity, get_audit_logger
from .rate_limiter import (
    RateLimiter, RateLimitType, RateLimitConfig, get_rate_limiter,
    check_auth_rate_limit, check_api_rate_limit,
    check_credential_rate_limit, check_device_control_rate_limit,
)

__all__ = [
    # Function schemas
    "ACU_FUNCTIONS",
    "CCTV_FUNCTIONS",
    "ALL_FUNCTIONS",
    # Controllers
    "ACUController",
    "CCTVController",
    "SystemController",
    # Network discovery
    "NetworkDiscoveryService",
    "get_discovery_service",
    # Device registry
    "DeviceRegistry",
    "get_device_registry",
    "RegisteredDevice",
    # Credential management (Phase 1)
    "CredentialManager",
    "get_credential_manager",
    # Connection health (Phase 2)
    "ConnectionHealthService",
    "get_health_service",
    # Zone management (Phase 4)
    "ZoneManager",
    "Zone",
    "SecurityLevel",
    "get_zone_manager",
    # Audit logging (Phase 4)
    "AuditLogger",
    "AuditEventType",
    "AuditSeverity",
    "get_audit_logger",
    # Rate limiting (Phase 4)
    "RateLimiter",
    "RateLimitType",
    "RateLimitConfig",
    "get_rate_limiter",
    "check_auth_rate_limit",
    "check_api_rate_limit",
    "check_credential_rate_limit",
    "check_device_control_rate_limit",
]
