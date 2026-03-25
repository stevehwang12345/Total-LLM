"""
ACU Controller 단위 테스트

출입통제장치(ACU) 컨트롤러의 모든 기능을 테스트합니다.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '/home/sphwang/dev/Total-LLM/backend')

from total_llm.services.control.acu_controller import (
    ACUController,
    ACUControllerSync,
    DoorState,
    AccessAction,
    DoorInfo,
    AccessLog,
    AccessPermission
)


class TestACUControllerInit:
    """ACU Controller 초기화 테스트"""

    def test_init_simulation_mode(self):
        """시뮬레이션 모드 초기화 테스트"""
        controller = ACUController(simulation_mode=True)
        assert controller._simulation_mode is True
        assert len(controller._doors) == 5
        assert len(controller._access_logs) == 0
        assert len(controller._permissions) == 0

    def test_init_without_endpoint(self):
        """API 엔드포인트 없이 초기화 (시뮬레이션 모드)"""
        controller = ACUController()
        assert controller._simulation_mode is True

    def test_simulated_doors_structure(self):
        """시뮬레이션 도어 구조 확인"""
        controller = ACUController(simulation_mode=True)

        expected_doors = ["door_01", "door_02", "door_03", "door_04", "door_05"]
        for door_id in expected_doors:
            assert door_id in controller._doors
            door = controller._doors[door_id]
            assert isinstance(door, DoorInfo)
            assert door.door_id == door_id


class TestACUControllerDoorOperations:
    """도어 잠금/해제 테스트"""

    @pytest.fixture
    def controller(self):
        return ACUController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_unlock_door_success(self, controller):
        """도어 잠금 해제 성공 테스트"""
        result = await controller.unlock_door("door_01", duration=10)

        assert result["success"] is True
        assert result["door_id"] == "door_01"
        assert result["action"] == "unlocked"  # 실제 구현은 "unlocked" 반환
        assert result["duration"] == 10
        assert controller._doors["door_01"].state == DoorState.UNLOCKED

    @pytest.mark.asyncio
    async def test_unlock_door_invalid_id(self, controller):
        """존재하지 않는 도어 ID 테스트"""
        result = await controller.unlock_door("invalid_door")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unlock_door_creates_access_log(self, controller):
        """도어 해제 시 로그 생성 확인"""
        initial_log_count = len(controller._access_logs)
        await controller.unlock_door("door_01")

        assert len(controller._access_logs) == initial_log_count + 1
        log = controller._access_logs[-1]
        assert log.door_id == "door_01"
        assert log.action == AccessAction.UNLOCK

    @pytest.mark.asyncio
    async def test_lock_door_success(self, controller):
        """도어 잠금 성공 테스트"""
        # 먼저 열기
        await controller.unlock_door("door_01")

        # 잠금
        result = await controller.lock_door("door_01")

        assert result["success"] is True
        assert result["action"] == "locked"  # 실제 구현은 "locked" 반환
        assert controller._doors["door_01"].state == DoorState.LOCKED

    @pytest.mark.asyncio
    async def test_lock_door_invalid_id(self, controller):
        """존재하지 않는 도어 잠금 테스트"""
        result = await controller.lock_door("invalid_door")

        assert result["success"] is False


class TestACUControllerStatusQueries:
    """상태 조회 테스트"""

    @pytest.fixture
    def controller(self):
        return ACUController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_get_door_status_single(self, controller):
        """단일 도어 상태 조회"""
        result = await controller.get_door_status("door_01")

        # 단일 도어 조회는 doors 배열 없이 직접 반환
        assert "door_id" in result
        assert result["door_id"] == "door_01"

    @pytest.mark.asyncio
    async def test_get_door_status_all(self, controller):
        """전체 도어 상태 조회"""
        result = await controller.get_door_status()

        assert "doors" in result
        assert "total" in result
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_get_access_log_empty(self, controller):
        """빈 접근 로그 조회"""
        result = await controller.get_access_log()

        assert "logs" in result
        assert result["logs"] == []

    @pytest.mark.asyncio
    async def test_get_access_log_with_entries(self, controller):
        """접근 로그 조회"""
        # 로그 생성
        await controller.unlock_door("door_01")
        await controller.lock_door("door_01")

        result = await controller.get_access_log()

        assert "logs" in result
        assert len(result["logs"]) == 2

    @pytest.mark.asyncio
    async def test_get_access_log_filtered_by_door(self, controller):
        """도어별 로그 필터링"""
        await controller.unlock_door("door_01")
        await controller.unlock_door("door_02")

        result = await controller.get_access_log(door_id="door_01")

        assert "logs" in result
        assert all(log["door_id"] == "door_01" for log in result["logs"])

    @pytest.mark.asyncio
    async def test_get_access_log_with_limit(self, controller):
        """로그 개수 제한"""
        for _ in range(5):
            await controller.unlock_door("door_01")

        result = await controller.get_access_log(limit=3)

        assert len(result["logs"]) == 3


class TestACUControllerPermissions:
    """접근 권한 관리 테스트"""

    @pytest.fixture
    def controller(self):
        return ACUController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_grant_access_success(self, controller):
        """접근 권한 부여 성공"""
        result = await controller.grant_access("door_01", "user_001")

        assert result["success"] is True
        assert result["door_id"] == "door_01"
        assert result["user_id"] == "user_001"

    @pytest.mark.asyncio
    async def test_grant_access_with_expiry(self, controller):
        """만료 시간이 있는 권한 부여"""
        valid_until = (datetime.now() + timedelta(days=7)).isoformat()
        result = await controller.grant_access("door_01", "user_001", valid_until=valid_until)

        assert result["success"] is True
        assert "valid_until" in result

    @pytest.mark.asyncio
    async def test_grant_access_invalid_door(self, controller):
        """존재하지 않는 도어에 권한 부여"""
        result = await controller.grant_access("invalid_door", "user_001")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_revoke_access_success(self, controller):
        """접근 권한 취소"""
        # 먼저 권한 부여
        await controller.grant_access("door_01", "user_001")

        # 권한 취소
        result = await controller.revoke_access("user_001", "door_01")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_revoke_access_all_doors(self, controller):
        """모든 도어 권한 취소"""
        await controller.grant_access("door_01", "user_001")
        await controller.grant_access("door_02", "user_001")

        result = await controller.revoke_access("user_001")

        assert result["success"] is True
        assert result["revoked_count"] >= 2


class TestACUControllerEmergency:
    """비상 제어 테스트"""

    @pytest.fixture
    def controller(self):
        return ACUController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_emergency_unlock_all(self, controller):
        """비상 전체 잠금 해제"""
        result = await controller.emergency_unlock_all(reason="fire")

        assert result["success"] is True
        assert result["action"] == "emergency_unlock_all"
        assert result["count"] == 5  # doors_affected -> count

        # 모든 도어가 열렸는지 확인
        for door in controller._doors.values():
            assert door.state == DoorState.UNLOCKED

    @pytest.mark.asyncio
    async def test_emergency_unlock_all_with_description(self, controller):
        """사유 설명이 있는 비상 해제"""
        result = await controller.emergency_unlock_all(
            reason="fire",
            description="1층 화재 발생"
        )

        assert result["success"] is True
        assert "message" in result  # timestamp 대신 message

    @pytest.mark.asyncio
    async def test_emergency_lock_all(self, controller):
        """비상 전체 잠금"""
        result = await controller.emergency_lock_all(reason="security_threat")

        assert result["success"] is True
        assert result["action"] == "emergency_lock_all"

        # 모든 도어가 잠겼는지 확인
        for door in controller._doors.values():
            assert door.state == DoorState.LOCKED


class TestACUControllerSync:
    """동기 래퍼 테스트"""

    def test_sync_unlock_door(self):
        """동기 도어 해제"""
        controller = ACUControllerSync(simulation_mode=True)
        result = controller.unlock_door("door_01")

        assert result["success"] is True

    def test_sync_lock_door(self):
        """동기 도어 잠금"""
        controller = ACUControllerSync(simulation_mode=True)
        controller.unlock_door("door_01")
        result = controller.lock_door("door_01")

        assert result["success"] is True

    def test_sync_get_door_status(self):
        """동기 상태 조회"""
        controller = ACUControllerSync(simulation_mode=True)
        result = controller.get_door_status()

        assert "doors" in result
        assert result["total"] == 5


class TestDoorStateEnum:
    """DoorState Enum 테스트"""

    def test_door_states(self):
        """도어 상태 값 확인"""
        assert DoorState.LOCKED.value == "locked"
        assert DoorState.UNLOCKED.value == "unlocked"
        assert DoorState.OPEN.value == "open"
        assert DoorState.ERROR.value == "error"


class TestAccessActionEnum:
    """AccessAction Enum 테스트"""

    def test_access_actions(self):
        """접근 액션 값 확인"""
        assert AccessAction.UNLOCK.value == "unlock"
        assert AccessAction.LOCK.value == "lock"
        # 실제 구현: GRANT -> ACCESS_GRANTED, REVOKE -> ACCESS_DENIED
        assert AccessAction.ACCESS_GRANTED.value == "access_granted"
        assert AccessAction.ACCESS_DENIED.value == "access_denied"
        assert AccessAction.EMERGENCY_UNLOCK.value == "emergency_unlock"
        assert AccessAction.EMERGENCY_LOCK.value == "emergency_lock"


class TestDoorIdNormalization:
    """도어 ID 정규화 테스트"""

    @pytest.fixture
    def controller(self):
        return ACUController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_normalize_korean_name(self, controller):
        """한글 이름 정규화"""
        result = await controller.unlock_door("정문")
        assert result["success"] is True
        assert result["door_id"] == "door_01"

    @pytest.mark.asyncio
    async def test_normalize_number_name(self, controller):
        """번호 이름 정규화"""
        result = await controller.unlock_door("1번문")
        assert result["success"] is True
        assert result["door_id"] == "door_01"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
