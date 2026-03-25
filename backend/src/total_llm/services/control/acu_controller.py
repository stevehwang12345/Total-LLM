"""
ACU (출입통제장치) 제어기

출입문 개폐, 잠금/해제, 출입 이력 관리, 권한 관리 기능을 제공합니다.
실제 ACU 시스템 연동 또는 시뮬레이션 모드로 동작합니다.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)


class DoorState(Enum):
    """출입문 상태"""
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    OPEN = "open"
    ERROR = "error"


class AccessAction(Enum):
    """출입 이벤트 유형"""
    UNLOCK = "unlock"
    LOCK = "lock"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    EMERGENCY_UNLOCK = "emergency_unlock"
    EMERGENCY_LOCK = "emergency_lock"


@dataclass
class DoorInfo:
    """출입문 정보"""
    door_id: str
    name: str
    location: str
    state: DoorState = DoorState.LOCKED
    is_open: bool = False
    last_access_time: Optional[datetime] = None
    last_access_user: Optional[str] = None


@dataclass
class AccessLog:
    """출입 이력"""
    door_id: str
    action: AccessAction
    timestamp: datetime
    user_id: Optional[str] = None
    success: bool = True
    details: Optional[str] = None


@dataclass
class AccessPermission:
    """출입 권한"""
    user_id: str
    door_id: str
    granted_at: datetime
    valid_until: Optional[datetime] = None
    granted_by: str = "system"


class ACUController:
    """
    ACU 출입통제 제어기

    실제 ACU 시스템 API와 연동하거나 시뮬레이션 모드로 동작합니다.
    """

    def __init__(
        self,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        simulation_mode: bool = True,
    ):
        """
        Args:
            api_endpoint: 실제 ACU 시스템 API 엔드포인트
            api_key: API 인증 키
            simulation_mode: True이면 시뮬레이션 모드로 동작
        """
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self._simulation_mode = simulation_mode or api_endpoint is None

        # 시뮬레이션용 데이터
        self._doors: Dict[str, DoorInfo] = {}
        self._access_logs: List[AccessLog] = []
        self._permissions: List[AccessPermission] = []
        self._lock = asyncio.Lock()

        if self._simulation_mode:
            self._init_simulation_data()
            logger.info("ACUController initialized in SIMULATION mode")
        else:
            logger.info(f"ACUController initialized with endpoint: {api_endpoint}")

    def _init_simulation_data(self):
        """시뮬레이션용 초기 데이터 설정"""
        self._doors = {
            "door_01": DoorInfo(
                door_id="door_01",
                name="정문",
                location="1층 로비",
                state=DoorState.LOCKED,
            ),
            "door_02": DoorInfo(
                door_id="door_02",
                name="후문",
                location="1층 후면",
                state=DoorState.LOCKED,
            ),
            "door_03": DoorInfo(
                door_id="door_03",
                name="주차장 입구",
                location="지하 1층",
                state=DoorState.LOCKED,
            ),
            "door_04": DoorInfo(
                door_id="door_04",
                name="서버실",
                location="3층",
                state=DoorState.LOCKED,
            ),
            "door_05": DoorInfo(
                door_id="door_05",
                name="회의실 A",
                location="2층",
                state=DoorState.UNLOCKED,
            ),
        }

    def _normalize_door_id(self, door_id: str) -> str:
        """문 ID 정규화 (한글 이름 → ID 변환)"""
        name_to_id = {
            "정문": "door_01",
            "후문": "door_02",
            "주차장": "door_03",
            "주차장 입구": "door_03",
            "서버실": "door_04",
            "회의실": "door_05",
            "회의실 A": "door_05",
            "1번문": "door_01",
            "2번문": "door_02",
            "3번문": "door_03",
            "4번문": "door_04",
            "5번문": "door_05",
            "1번": "door_01",
            "2번": "door_02",
            "3번": "door_03",
        }
        return name_to_id.get(door_id, door_id)

    def _log_access(
        self,
        door_id: str,
        action: AccessAction,
        user_id: Optional[str] = None,
        success: bool = True,
        details: Optional[str] = None,
    ):
        """출입 이력 기록"""
        log = AccessLog(
            door_id=door_id,
            action=action,
            timestamp=datetime.now(),
            user_id=user_id,
            success=success,
            details=details,
        )
        self._access_logs.append(log)
        logger.info(f"ACU Log: {action.value} on {door_id} - {'Success' if success else 'Failed'}")

    async def unlock_door(
        self,
        door_id: str,
        duration: int = 5,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        출입문 열기 (잠금 해제)

        Args:
            door_id: 출입문 ID
            duration: 개방 유지 시간(초)
            user_id: 요청 사용자 ID

        Returns:
            실행 결과
        """
        door_id = self._normalize_door_id(door_id)
        logger.info(f"ACU: Unlocking door {door_id} for {duration}s")

        if self._simulation_mode:
            async with self._lock:
                if door_id not in self._doors:
                    self._log_access(door_id, AccessAction.UNLOCK, user_id, False, "Door not found")
                    return {
                        "success": False,
                        "error": f"출입문 '{door_id}'을(를) 찾을 수 없습니다",
                        "door_id": door_id,
                    }

                door = self._doors[door_id]
                door.state = DoorState.UNLOCKED
                door.is_open = True
                door.last_access_time = datetime.now()
                door.last_access_user = user_id

                self._log_access(door_id, AccessAction.UNLOCK, user_id, True, f"Duration: {duration}s")

                return {
                    "success": True,
                    "door_id": door_id,
                    "door_name": door.name,
                    "action": "unlocked",
                    "duration": duration,
                    "message": f"✅ {door.name}({door_id})이(가) {duration}초 동안 열립니다",
                }
        else:
            return await self._call_api("unlock", door_id=door_id, duration=duration)

    async def lock_door(
        self,
        door_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        출입문 잠금

        Args:
            door_id: 출입문 ID
            user_id: 요청 사용자 ID

        Returns:
            실행 결과
        """
        door_id = self._normalize_door_id(door_id)
        logger.info(f"ACU: Locking door {door_id}")

        if self._simulation_mode:
            async with self._lock:
                if door_id not in self._doors:
                    self._log_access(door_id, AccessAction.LOCK, user_id, False, "Door not found")
                    return {
                        "success": False,
                        "error": f"출입문 '{door_id}'을(를) 찾을 수 없습니다",
                        "door_id": door_id,
                    }

                door = self._doors[door_id]
                door.state = DoorState.LOCKED
                door.is_open = False

                self._log_access(door_id, AccessAction.LOCK, user_id, True)

                return {
                    "success": True,
                    "door_id": door_id,
                    "door_name": door.name,
                    "action": "locked",
                    "message": f"🔒 {door.name}({door_id})이(가) 잠겼습니다",
                }
        else:
            return await self._call_api("lock", door_id=door_id)

    async def get_door_status(
        self,
        door_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        출입문 상태 조회

        Args:
            door_id: 출입문 ID (없으면 전체 조회)

        Returns:
            상태 정보
        """
        if self._simulation_mode:
            if door_id:
                door_id = self._normalize_door_id(door_id)
                if door_id not in self._doors:
                    return {"error": f"출입문 '{door_id}'을(를) 찾을 수 없습니다"}

                door = self._doors[door_id]
                return {
                    "door_id": door.door_id,
                    "name": door.name,
                    "location": door.location,
                    "state": door.state.value,
                    "is_open": door.is_open,
                    "last_access_time": door.last_access_time.isoformat() if door.last_access_time else None,
                    "last_access_user": door.last_access_user,
                }
            else:
                return {
                    "total": len(self._doors),
                    "doors": [
                        {
                            "door_id": d.door_id,
                            "name": d.name,
                            "location": d.location,
                            "state": d.state.value,
                            "is_open": d.is_open,
                        }
                        for d in self._doors.values()
                    ]
                }
        else:
            return await self._call_api("status", door_id=door_id)

    async def get_access_log(
        self,
        door_id: Optional[str] = None,
        limit: int = 10,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        출입 이력 조회

        Args:
            door_id: 출입문 ID (없으면 전체)
            limit: 최대 조회 개수
            start_time: 시작 시간
            end_time: 종료 시간

        Returns:
            출입 이력 목록
        """
        if self._simulation_mode:
            logs = self._access_logs.copy()

            # 필터링
            if door_id:
                door_id = self._normalize_door_id(door_id)
                logs = [l for l in logs if l.door_id == door_id]

            # 최근 순 정렬 및 제한
            logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)[:limit]

            return {
                "total": len(logs),
                "logs": [
                    {
                        "door_id": l.door_id,
                        "action": l.action.value,
                        "timestamp": l.timestamp.isoformat(),
                        "user_id": l.user_id,
                        "success": l.success,
                        "details": l.details,
                    }
                    for l in logs
                ]
            }
        else:
            return await self._call_api("logs", door_id=door_id, limit=limit)

    async def grant_access(
        self,
        door_id: str,
        user_id: str,
        valid_until: Optional[str] = None,
        granted_by: str = "system",
    ) -> Dict[str, Any]:
        """출입 권한 부여"""
        door_id = self._normalize_door_id(door_id)
        logger.info(f"ACU: Granting access to {user_id} for {door_id}")

        if self._simulation_mode:
            if door_id not in self._doors:
                return {"success": False, "error": f"출입문 '{door_id}'을(를) 찾을 수 없습니다"}

            permission = AccessPermission(
                user_id=user_id,
                door_id=door_id,
                granted_at=datetime.now(),
                valid_until=datetime.fromisoformat(valid_until) if valid_until else None,
                granted_by=granted_by,
            )
            self._permissions.append(permission)

            door = self._doors[door_id]
            return {
                "success": True,
                "door_id": door_id,
                "door_name": door.name,
                "user_id": user_id,
                "action": "access_granted",
                "valid_until": valid_until,
                "message": f"✅ {user_id}에게 {door.name} 출입 권한이 부여되었습니다",
            }
        else:
            return await self._call_api("grant_access", door_id=door_id, user_id=user_id)

    async def revoke_access(
        self,
        user_id: str,
        door_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """출입 권한 취소"""
        if door_id:
            door_id = self._normalize_door_id(door_id)
        logger.info(f"ACU: Revoking access for {user_id} on {door_id or 'all doors'}")

        if self._simulation_mode:
            original_count = len(self._permissions)
            if door_id:
                self._permissions = [
                    p for p in self._permissions
                    if not (p.user_id == user_id and p.door_id == door_id)
                ]
            else:
                self._permissions = [
                    p for p in self._permissions if p.user_id != user_id
                ]

            revoked_count = original_count - len(self._permissions)
            return {
                "success": True,
                "user_id": user_id,
                "door_id": door_id,
                "revoked_count": revoked_count,
                "message": f"✅ {user_id}의 출입 권한 {revoked_count}개가 취소되었습니다",
            }
        else:
            return await self._call_api("revoke_access", user_id=user_id, door_id=door_id)

    async def emergency_unlock_all(
        self,
        reason: str,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        비상 전체 개방

        Args:
            reason: 비상 개방 사유
            description: 상세 설명
            user_id: 요청자

        Returns:
            실행 결과
        """
        logger.warning(f"ACU: EMERGENCY UNLOCK ALL - Reason: {reason}")

        if self._simulation_mode:
            async with self._lock:
                unlocked_doors = []
                for door in self._doors.values():
                    door.state = DoorState.UNLOCKED
                    door.is_open = True
                    unlocked_doors.append(door.door_id)
                    self._log_access(
                        door.door_id,
                        AccessAction.EMERGENCY_UNLOCK,
                        user_id,
                        True,
                        f"Emergency: {reason} - {description or ''}"
                    )

                return {
                    "success": True,
                    "action": "emergency_unlock_all",
                    "reason": reason,
                    "description": description,
                    "doors_unlocked": unlocked_doors,
                    "count": len(unlocked_doors),
                    "message": f"🚨 비상 개방: 전체 {len(unlocked_doors)}개 출입문이 열렸습니다 (사유: {reason})",
                }
        else:
            return await self._call_api("emergency_unlock", reason=reason, description=description)

    async def emergency_lock_all(
        self,
        reason: str,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        비상 전체 잠금 (봉쇄)

        Args:
            reason: 비상 잠금 사유
            description: 상세 설명
            user_id: 요청자

        Returns:
            실행 결과
        """
        logger.warning(f"ACU: EMERGENCY LOCK ALL - Reason: {reason}")

        if self._simulation_mode:
            async with self._lock:
                locked_doors = []
                for door in self._doors.values():
                    door.state = DoorState.LOCKED
                    door.is_open = False
                    locked_doors.append(door.door_id)
                    self._log_access(
                        door.door_id,
                        AccessAction.EMERGENCY_LOCK,
                        user_id,
                        True,
                        f"Emergency: {reason} - {description or ''}"
                    )

                return {
                    "success": True,
                    "action": "emergency_lock_all",
                    "reason": reason,
                    "description": description,
                    "doors_locked": locked_doors,
                    "count": len(locked_doors),
                    "message": f"🔒 비상 봉쇄: 전체 {len(locked_doors)}개 출입문이 잠겼습니다 (사유: {reason})",
                }
        else:
            return await self._call_api("emergency_lock", reason=reason, description=description)

    async def _call_api(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        실제 ACU API 호출

        REST API 기반 ACU 시스템과 통신합니다.
        연결 실패 시 시뮬레이션 모드로 자동 폴백합니다.

        Args:
            action: API 액션 (unlock, lock, status, etc.)
            **kwargs: 액션별 파라미터

        Returns:
            API 응답 데이터

        Raises:
            ConnectionError: API 서버 연결 실패
            ValueError: 잘못된 응답 형식
        """
        if not self.api_endpoint:
            logger.warning(f"No API endpoint configured for action: {action}")
            raise ConnectionError("ACU API endpoint not configured")

        # API 경로 매핑
        action_paths = {
            "unlock": "/doors/{door_id}/unlock",
            "lock": "/doors/{door_id}/lock",
            "status": "/doors/{door_id}/status",
            "access_log": "/doors/{door_id}/access-log",
            "grant_access": "/access/grant",
            "revoke_access": "/access/revoke",
            "emergency_unlock": "/emergency/unlock-all",
            "emergency_lock": "/emergency/lock-all",
        }

        path_template = action_paths.get(action)
        if not path_template:
            raise ValueError(f"Unknown ACU action: {action}")

        # 경로에서 변수 치환
        door_id = kwargs.pop("door_id", None)
        if "{door_id}" in path_template:
            if not door_id:
                raise ValueError(f"door_id required for action: {action}")
            path = path_template.format(door_id=door_id)
        else:
            path = path_template

        url = f"{self.api_endpoint.rstrip('/')}{path}"
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # HTTP 메서드 결정
        method = "POST" if action in ["unlock", "lock", "grant_access", "revoke_access",
                                       "emergency_unlock", "emergency_lock"] else "GET"

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if method == "POST":
                    async with session.post(url, json=kwargs, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"ACU API {action} success: {url}")
                            return data
                        else:
                            error_text = await response.text()
                            logger.error(f"ACU API {action} failed: {response.status} - {error_text}")
                            raise ConnectionError(f"ACU API error: {response.status}")
                else:
                    async with session.get(url, params=kwargs, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"ACU API {action} success: {url}")
                            return data
                        else:
                            error_text = await response.text()
                            logger.error(f"ACU API {action} failed: {response.status} - {error_text}")
                            raise ConnectionError(f"ACU API error: {response.status}")

        except aiohttp.ClientError as e:
            logger.error(f"ACU API connection error for {action}: {e}")
            raise ConnectionError(f"Failed to connect to ACU API: {e}")
        except asyncio.TimeoutError:
            logger.error(f"ACU API timeout for {action}")
            raise ConnectionError("ACU API request timeout")


# 동기 버전 래퍼 (필요 시 사용)
class ACUControllerSync:
    """동기식 ACU Controller 래퍼"""

    def __init__(self, *args, **kwargs):
        self._async_controller = ACUController(*args, **kwargs)

    def _run(self, coro):
        """코루틴 실행"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    def unlock_door(self, *args, **kwargs):
        return self._run(self._async_controller.unlock_door(*args, **kwargs))

    def lock_door(self, *args, **kwargs):
        return self._run(self._async_controller.lock_door(*args, **kwargs))

    def get_door_status(self, *args, **kwargs):
        return self._run(self._async_controller.get_door_status(*args, **kwargs))

    def get_access_log(self, *args, **kwargs):
        return self._run(self._async_controller.get_access_log(*args, **kwargs))

    def grant_access(self, *args, **kwargs):
        return self._run(self._async_controller.grant_access(*args, **kwargs))

    def revoke_access(self, *args, **kwargs):
        return self._run(self._async_controller.revoke_access(*args, **kwargs))

    def emergency_unlock_all(self, *args, **kwargs):
        return self._run(self._async_controller.emergency_unlock_all(*args, **kwargs))

    def emergency_lock_all(self, *args, **kwargs):
        return self._run(self._async_controller.emergency_lock_all(*args, **kwargs))
