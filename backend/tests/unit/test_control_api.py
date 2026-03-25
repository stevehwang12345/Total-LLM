"""
Control API 단위 테스트

외부 시스템 제어 REST API의 기능을 테스트합니다.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '/home/sphwang/dev/Total-LLM/backend')

from total_llm.api.control_api import router, get_controller
from fastapi import FastAPI


# 테스트용 앱 생성
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestControlAPIHealth:
    """Control API 헬스체크 테스트"""

    def test_health_check(self):
        """헬스체크 엔드포인트 테스트"""
        response = client.get("/control/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "simulation_mode" in data
        assert "functions_available" in data


class TestControlAPIFunctions:
    """함수 관련 API 테스트"""

    def test_list_functions(self):
        """함수 목록 조회 테스트"""
        response = client.get("/control/functions")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert data["total"] == 19
        assert "categories" in data
        assert "acu" in data["categories"]
        assert "cctv" in data["categories"]


class TestControlAPICommand:
    """자연어 명령 API 테스트"""

    def test_process_command_door_open(self):
        """문 열기 명령 테스트"""
        response = client.post(
            "/control/command",
            json={"command": "1번 문 열어줘", "use_llm": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["executions"]) > 0

    def test_process_command_system_status(self):
        """시스템 상태 명령 테스트"""
        response = client.post(
            "/control/command",
            json={"command": "시스템 상태 확인", "use_llm": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_process_command_unknown(self):
        """알 수 없는 명령 테스트"""
        response = client.post(
            "/control/command",
            json={"command": "오늘 날씨 어때?", "use_llm": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestControlAPIFunctionCall:
    """직접 함수 호출 API 테스트"""

    def test_function_call_valid(self):
        """유효한 함수 호출 테스트"""
        response = client.post(
            "/control/function",
            json={
                "function_name": "unlock_door",
                "arguments": {"door_id": "door_01"}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_function_call_invalid(self):
        """존재하지 않는 함수 호출 테스트"""
        response = client.post(
            "/control/function",
            json={
                "function_name": "invalid_function",
                "arguments": {}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestControlAPIACU:
    """ACU API 테스트"""

    def test_unlock_door(self):
        """문 열기 API 테스트"""
        response = client.post(
            "/control/acu/door/unlock",
            json={"door_id": "door_01", "duration": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_lock_door(self):
        """문 잠금 API 테스트"""
        # 먼저 열기
        client.post("/control/acu/door/unlock", json={"door_id": "door_01", "duration": 5})
        # 잠금
        response = client.post(
            "/control/acu/door/lock",
            json={"door_id": "door_01"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_door_status_all(self):
        """전체 문 상태 조회 테스트"""
        response = client.get("/control/acu/door/status")
        assert response.status_code == 200
        data = response.json()
        assert "doors" in data or "door_id" in data

    def test_get_door_status_single(self):
        """단일 문 상태 조회 테스트"""
        response = client.get("/control/acu/door/status?door_id=door_01")
        assert response.status_code == 200
        data = response.json()
        assert "door_id" in data

    def test_get_access_log(self):
        """출입 이력 조회 테스트"""
        response = client.get("/control/acu/log")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_grant_access(self):
        """권한 부여 테스트"""
        response = client.post(
            "/control/acu/permission/grant",
            json={"door_id": "door_01", "user_id": "user_001"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_emergency_unlock(self):
        """비상 개방 테스트"""
        response = client.post(
            "/control/acu/emergency/unlock",
            json={"reason": "fire", "description": "테스트용 비상 개방"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestControlAPICCTV:
    """CCTV API 테스트"""

    def test_move_camera(self):
        """카메라 이동 테스트"""
        response = client.post(
            "/control/cctv/camera/move",
            json={"camera_id": "cam_01", "pan": 45, "tilt": 30, "zoom": 2.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_go_to_preset(self):
        """프리셋 이동 테스트"""
        response = client.post(
            "/control/cctv/camera/preset",
            json={"camera_id": "cam_01", "preset_id": "entrance"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_start_recording(self):
        """녹화 시작 테스트"""
        response = client.post(
            "/control/cctv/recording/start",
            json={"camera_id": "cam_01", "duration": 0, "quality": "high"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_stop_recording(self):
        """녹화 중지 테스트"""
        # 먼저 녹화 시작
        client.post("/control/cctv/recording/start", json={"camera_id": "cam_01", "duration": 0, "quality": "high"})
        # 녹화 중지
        response = client.post(
            "/control/cctv/recording/stop",
            json={"camera_id": "cam_01"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_capture_snapshot(self):
        """스냅샷 캡처 테스트"""
        response = client.post(
            "/control/cctv/snapshot",
            json={"camera_id": "cam_01", "resolution": "1080p"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_camera_status_all(self):
        """전체 카메라 상태 조회 테스트"""
        response = client.get("/control/cctv/camera/status")
        assert response.status_code == 200
        data = response.json()
        assert "cameras" in data or "camera_id" in data

    def test_get_recordings(self):
        """녹화 목록 조회 테스트"""
        response = client.get("/control/cctv/recordings")
        assert response.status_code == 200
        data = response.json()
        assert "recordings" in data

    def test_set_motion_detection(self):
        """모션 감지 설정 테스트"""
        response = client.post(
            "/control/cctv/motion",
            json={"camera_id": "cam_01", "enabled": True, "sensitivity": "high"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestControlAPISystem:
    """시스템 API 테스트"""

    def test_get_system_status(self):
        """시스템 상태 조회 테스트"""
        response = client.get("/control/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "acu" in data
        assert "cctv" in data

    def test_get_alerts(self):
        """알림 조회 테스트"""
        response = client.get("/control/system/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "alerts" in data

    def test_get_alerts_filtered(self):
        """필터링된 알림 조회 테스트"""
        response = client.get("/control/system/alerts?severity=warning&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
