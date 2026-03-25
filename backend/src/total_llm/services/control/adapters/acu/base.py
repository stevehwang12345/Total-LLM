"""
Base ACU Adapter Module
ACU(Access Control Unit) 장치 어댑터의 기본 클래스

이 모듈은 모든 ACU 어댑터가 구현해야 하는 인터페이스를 정의합니다.
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from ..base import (
    BaseDeviceAdapter,
    DeviceCommand,
    DeviceResponse,
    DeviceType,
    CommandStatus
)


class DoorStatus(str, Enum):
    """출입문 상태"""
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    OPEN = "open"
    CLOSED = "closed"
    HELD_OPEN = "held_open"      # 문이 열린 채로 유지됨
    FORCED_OPEN = "forced_open"  # 강제로 열림 (알람)
    UNKNOWN = "unknown"


class AccessType(str, Enum):
    """출입 유형"""
    CARD = "card"
    FINGERPRINT = "fingerprint"
    FACE = "face"
    PIN = "pin"
    QR = "qr"
    REMOTE = "remote"           # 원격 제어
    MANUAL = "manual"           # 수동
    EMERGENCY = "emergency"     # 비상


class AccessResult(str, Enum):
    """출입 결과"""
    GRANTED = "granted"
    DENIED = "denied"
    TIMEOUT = "timeout"
    ERROR = "error"


class AlarmType(str, Enum):
    """알람 유형"""
    DOOR_FORCED = "door_forced"
    DOOR_HELD = "door_held"
    TAMPER = "tamper"
    INVALID_ACCESS = "invalid_access"
    SYSTEM_ERROR = "system_error"


@dataclass
class DoorInfo:
    """출입문 정보"""
    door_id: str
    name: str
    status: DoorStatus = DoorStatus.UNKNOWN
    location: str = ""
    zone: str = ""
    is_emergency_exit: bool = False
    last_access_time: Optional[datetime] = None
    last_access_user: Optional[str] = None


@dataclass
class AccessLog:
    """출입 이력"""
    log_id: str
    door_id: str
    user_id: Optional[str]
    user_name: Optional[str]
    access_type: AccessType
    result: AccessResult
    timestamp: datetime
    card_number: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlarmEvent:
    """알람 이벤트"""
    alarm_id: str
    door_id: str
    alarm_type: AlarmType
    timestamp: datetime
    acknowledged: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class BaseACUAdapter(BaseDeviceAdapter):
    """
    ACU 장치 어댑터 기본 클래스

    모든 ACU 어댑터(ZKTeco, Suprema, HID 등)는 이 클래스를 상속합니다.
    """

    def __init__(self, device_info: Dict[str, Any]):
        # ACU 타입으로 강제 설정
        device_info["device_type"] = DeviceType.ACU.value
        super().__init__(device_info)

        # ACU 전용 속성
        self._doors: Dict[str, DoorInfo] = {}
        self._supported_access_types: List[AccessType] = [AccessType.CARD, AccessType.REMOTE]

    @property
    def doors(self) -> Dict[str, DoorInfo]:
        """등록된 출입문 목록"""
        return self._doors

    @property
    def supported_access_types(self) -> List[AccessType]:
        """지원하는 인증 방식"""
        return self._supported_access_types

    # ==================== Door Control ====================

    @abstractmethod
    async def unlock_door(
        self,
        door_id: str,
        duration: int = 5
    ) -> DeviceResponse:
        """
        출입문 잠금 해제

        Args:
            door_id: 출입문 ID
            duration: 해제 유지 시간 (초)

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def lock_door(self, door_id: str) -> DeviceResponse:
        """
        출입문 잠금

        Args:
            door_id: 출입문 ID

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def hold_open(self, door_id: str) -> DeviceResponse:
        """
        출입문 열림 유지 (상시 개방)

        Args:
            door_id: 출입문 ID

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def release_hold(self, door_id: str) -> DeviceResponse:
        """
        출입문 열림 유지 해제

        Args:
            door_id: 출입문 ID

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    # ==================== Status & Info ====================

    @abstractmethod
    async def get_door_status(self, door_id: str) -> DoorInfo:
        """
        출입문 상태 조회

        Args:
            door_id: 출입문 ID

        Returns:
            DoorInfo: 출입문 정보
        """
        pass

    @abstractmethod
    async def get_all_doors(self) -> List[DoorInfo]:
        """
        모든 출입문 상태 조회

        Returns:
            List[DoorInfo]: 출입문 목록
        """
        pass

    # ==================== Access Log ====================

    @abstractmethod
    async def get_access_log(
        self,
        door_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AccessLog]:
        """
        출입 이력 조회

        Args:
            door_id: 출입문 ID (None이면 전체)
            start_time: 조회 시작 시간
            end_time: 조회 종료 시간
            limit: 최대 조회 수

        Returns:
            List[AccessLog]: 출입 이력 목록
        """
        pass

    # ==================== Alarm Management ====================

    @abstractmethod
    async def get_active_alarms(self) -> List[AlarmEvent]:
        """
        활성 알람 목록 조회

        Returns:
            List[AlarmEvent]: 알람 이벤트 목록
        """
        pass

    @abstractmethod
    async def acknowledge_alarm(self, alarm_id: str) -> DeviceResponse:
        """
        알람 확인 처리

        Args:
            alarm_id: 알람 ID

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    # ==================== Emergency ====================

    @abstractmethod
    async def emergency_unlock_all(self) -> DeviceResponse:
        """
        비상 전체 해제

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def emergency_lock_all(self) -> DeviceResponse:
        """
        비상 전체 잠금 (락다운)

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    # ==================== Command Execution ====================

    async def execute(self, command: DeviceCommand) -> DeviceResponse:
        """
        ACU 명령 실행 디스패처

        지원 액션:
        - unlock_door: 출입문 해제
        - lock_door: 출입문 잠금
        - hold_open: 상시 개방
        - release_hold: 상시 개방 해제
        - get_door_status: 출입문 상태
        - get_access_log: 출입 이력
        - emergency_unlock_all: 비상 전체 해제
        - emergency_lock_all: 비상 전체 잠금
        """
        action = command.action.lower()
        params = command.parameters

        try:
            if action == "unlock_door":
                return await self.unlock_door(
                    door_id=params.get("door_id", "1"),
                    duration=params.get("duration", 5)
                )
            elif action == "lock_door":
                return await self.lock_door(
                    door_id=params.get("door_id", "1")
                )
            elif action == "hold_open":
                return await self.hold_open(
                    door_id=params.get("door_id", "1")
                )
            elif action == "release_hold":
                return await self.release_hold(
                    door_id=params.get("door_id", "1")
                )
            elif action == "get_door_status":
                door_info = await self.get_door_status(
                    door_id=params.get("door_id", "1")
                )
                return DeviceResponse(
                    success=True,
                    device_id=self.device_id,
                    action=action,
                    result={
                        "door_id": door_info.door_id,
                        "name": door_info.name,
                        "status": door_info.status.value,
                        "location": door_info.location
                    }
                )
            elif action == "get_access_log":
                logs = await self.get_access_log(
                    door_id=params.get("door_id"),
                    limit=params.get("limit", 100)
                )
                return DeviceResponse(
                    success=True,
                    device_id=self.device_id,
                    action=action,
                    result={
                        "logs": [
                            {
                                "log_id": log.log_id,
                                "door_id": log.door_id,
                                "user_name": log.user_name,
                                "access_type": log.access_type.value,
                                "result": log.result.value,
                                "timestamp": log.timestamp.isoformat()
                            }
                            for log in logs
                        ]
                    }
                )
            elif action == "emergency_unlock_all":
                return await self.emergency_unlock_all()
            elif action == "emergency_lock_all":
                return await self.emergency_lock_all()
            else:
                return DeviceResponse(
                    success=False,
                    device_id=self.device_id,
                    action=action,
                    status=CommandStatus.NOT_SUPPORTED,
                    error=f"Unsupported action: {action}"
                )
        except Exception as e:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action=action,
                status=CommandStatus.FAILED,
                error=str(e)
            )
