"""
Base Device Adapter Module
표준화된 장치 제어 인터페이스 정의

이 모듈은 모든 장치 어댑터의 기본 클래스와 공통 데이터 구조를 정의합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """장치 유형"""
    CCTV = "cctv"
    ACU = "acu"
    SENSOR = "sensor"
    ALARM = "alarm"
    UNKNOWN = "unknown"


class ConnectionStatus(str, Enum):
    """연결 상태"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    TIMEOUT = "timeout"


class CommandStatus(str, Enum):
    """명령 실행 상태"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    NOT_SUPPORTED = "not_supported"


@dataclass
class DeviceCommand:
    """장치 명령 표준 형식"""
    action: str                          # "unlock", "move", "snapshot" 등
    device_id: str                       # 장치 ID
    parameters: Dict[str, Any] = field(default_factory=dict)  # 명령별 파라미터
    timeout: float = 10.0                # 타임아웃 (초)
    priority: int = 0                    # 우선순위 (높을수록 우선)
    request_id: Optional[str] = None     # 요청 추적 ID

    def __post_init__(self):
        if self.request_id is None:
            self.request_id = f"{self.device_id}_{self.action}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


@dataclass
class DeviceResponse:
    """장치 응답 표준 형식"""
    success: bool
    device_id: str
    action: str
    status: CommandStatus = CommandStatus.SUCCESS
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: str = ""
    execution_time_ms: float = 0.0
    request_id: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.success and self.status == CommandStatus.SUCCESS:
            self.status = CommandStatus.FAILED

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "success": self.success,
            "device_id": self.device_id,
            "action": self.action,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "error_code": self.error_code,
            "timestamp": self.timestamp,
            "execution_time_ms": self.execution_time_ms,
            "request_id": self.request_id
        }


@dataclass
class DeviceInfo:
    """장치 정보"""
    device_id: str
    device_type: DeviceType
    name: str
    manufacturer: str
    model: str
    ip: str
    port: int = 80
    location: str = ""
    firmware_version: str = ""
    serial_number: str = ""
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseDeviceAdapter(ABC):
    """
    모든 장치 어댑터의 기본 클래스

    이 클래스는 장치와의 통신을 위한 표준 인터페이스를 정의합니다.
    각 제조사/프로토콜별 어댑터는 이 클래스를 상속하여 구현합니다.
    """

    def __init__(self, device_info: Dict[str, Any]):
        """
        어댑터 초기화

        Args:
            device_info: 장치 정보 딕셔너리
                - id: 장치 ID
                - ip: IP 주소
                - port: 포트 번호 (기본 80)
                - username: 인증 사용자명
                - password: 인증 비밀번호
                - manufacturer: 제조사
                - model: 모델명
                - device_type: 장치 유형
        """
        self.device_id = device_info.get("id", device_info.get("device_id", ""))
        self.ip = device_info.get("ip", "")
        self.port = device_info.get("port", 80)
        self.username = device_info.get("username", "admin")
        self.password = device_info.get("password", "")
        self.manufacturer = device_info.get("manufacturer", "unknown")
        self.model = device_info.get("model", "")
        self.device_type = DeviceType(device_info.get("device_type", "unknown"))
        self.name = device_info.get("name", f"{self.manufacturer}_{self.device_id}")
        self.location = device_info.get("location", "")

        self._connection_status = ConnectionStatus.DISCONNECTED
        self._last_communication: Optional[datetime] = None
        self._error_count = 0
        self._max_retries = 3
        self._retry_delay = 1.0

        self._device_info = device_info

        logger.info(f"Adapter initialized for device {self.device_id} ({self.manufacturer})")

    @property
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._connection_status == ConnectionStatus.CONNECTED

    @property
    def connection_status(self) -> ConnectionStatus:
        """현재 연결 상태"""
        return self._connection_status

    @property
    def last_communication(self) -> Optional[datetime]:
        """마지막 통신 시간"""
        return self._last_communication

    def _update_communication_time(self):
        """통신 시간 업데이트"""
        self._last_communication = datetime.now()

    def _record_error(self, error: str):
        """에러 기록"""
        self._error_count += 1
        logger.error(f"Device {self.device_id} error ({self._error_count}): {error}")

    def _reset_error_count(self):
        """에러 카운트 리셋"""
        self._error_count = 0

    # ==================== Abstract Methods ====================

    @abstractmethod
    async def connect(self) -> bool:
        """
        장치 연결

        Returns:
            bool: 연결 성공 여부
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """
        장치 연결 해제

        Returns:
            bool: 연결 해제 성공 여부
        """
        pass

    @abstractmethod
    async def execute(self, command: DeviceCommand) -> DeviceResponse:
        """
        명령 실행

        Args:
            command: 실행할 명령

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """
        장치 상태 조회

        Returns:
            Dict: 장치 상태 정보
        """
        pass

    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """
        장치 기능 목록 조회

        Returns:
            List[str]: 지원 기능 목록
        """
        pass

    # ==================== Common Methods ====================

    async def ping(self) -> bool:
        """
        장치 연결 확인 (간단한 연결 테스트)

        Returns:
            bool: 연결 가능 여부
        """
        try:
            status = await self.get_status()
            return status is not None
        except Exception as e:
            logger.warning(f"Ping failed for {self.device_id}: {e}")
            return False

    async def reconnect(self) -> bool:
        """
        장치 재연결

        Returns:
            bool: 재연결 성공 여부
        """
        logger.info(f"Attempting reconnection for {self.device_id}")
        await self.disconnect()
        return await self.connect()

    def get_device_info(self) -> DeviceInfo:
        """
        장치 정보 반환

        Returns:
            DeviceInfo: 장치 정보 객체
        """
        return DeviceInfo(
            device_id=self.device_id,
            device_type=self.device_type,
            name=self.name,
            manufacturer=self.manufacturer,
            model=self.model,
            ip=self.ip,
            port=self.port,
            location=self.location,
            metadata=self._device_info
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(device_id={self.device_id}, ip={self.ip}, connected={self.is_connected})"
