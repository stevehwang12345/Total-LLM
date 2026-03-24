"""
CCTV Controller 단위 테스트

영상감시장치(CCTV) 컨트롤러의 모든 기능을 테스트합니다.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '/home/sphwang/dev/Total-LLM/backend')

from services.control.cctv_controller import (
    CCTVController,
    CCTVControllerSync,
    CameraState,
    RecordingQuality,
    PTZPosition,
    Preset,
    CameraInfo,
    Recording
)


class TestCCTVControllerInit:
    """CCTV Controller 초기화 테스트"""

    def test_init_simulation_mode(self):
        """시뮬레이션 모드 초기화 테스트"""
        controller = CCTVController(simulation_mode=True)
        assert controller._simulation_mode is True
        assert len(controller._cameras) == 5
        assert len(controller._recordings) == 0

    def test_init_without_endpoint(self):
        """API 엔드포인트 없이 초기화 (시뮬레이션 모드)"""
        controller = CCTVController()
        assert controller._simulation_mode is True

    def test_simulated_cameras_structure(self):
        """시뮬레이션 카메라 구조 확인"""
        controller = CCTVController(simulation_mode=True)

        expected_cameras = ["cam_01", "cam_02", "cam_03", "cam_04", "cam_05"]
        for cam_id in expected_cameras:
            assert cam_id in controller._cameras
            camera = controller._cameras[cam_id]
            assert isinstance(camera, CameraInfo)
            assert camera.camera_id == cam_id

    def test_default_presets_exist(self):
        """기본 프리셋 존재 확인"""
        controller = CCTVController(simulation_mode=True)

        for camera in controller._cameras.values():
            assert len(camera.presets) >= 4
            preset_ids = list(camera.presets.keys())
            assert "entrance" in preset_ids
            assert "parking" in preset_ids


class TestCCTVControllerPTZOperations:
    """PTZ 제어 테스트"""

    @pytest.fixture
    def controller(self):
        return CCTVController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_move_camera_pan(self, controller):
        """Pan 이동 테스트"""
        result = await controller.move_camera("cam_01", pan=45)

        assert result["success"] is True
        assert result["camera_id"] == "cam_01"
        assert result["position"]["pan"] == 45  # new_position -> position

    @pytest.mark.asyncio
    async def test_move_camera_tilt(self, controller):
        """Tilt 이동 테스트"""
        result = await controller.move_camera("cam_01", tilt=30)

        assert result["success"] is True
        assert result["position"]["tilt"] == 30

    @pytest.mark.asyncio
    async def test_move_camera_zoom(self, controller):
        """Zoom 제어 테스트"""
        result = await controller.move_camera("cam_01", zoom=5.0)

        assert result["success"] is True
        assert result["position"]["zoom"] == 5.0

    @pytest.mark.asyncio
    async def test_move_camera_combined(self, controller):
        """복합 PTZ 제어 테스트"""
        result = await controller.move_camera("cam_01", pan=90, tilt=-45, zoom=10.0)

        assert result["success"] is True
        pos = result["position"]
        assert pos["pan"] == 90
        assert pos["tilt"] == -45
        assert pos["zoom"] == 10.0

    @pytest.mark.asyncio
    async def test_move_camera_invalid_id(self, controller):
        """존재하지 않는 카메라 제어"""
        result = await controller.move_camera("invalid_cam", pan=45)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_move_camera_pan_limits(self, controller):
        """Pan 범위 제한 테스트"""
        # -180 ~ 180 범위
        result = await controller.move_camera("cam_01", pan=200)
        assert result["success"] is True
        assert -180 <= result["position"]["pan"] <= 180

    @pytest.mark.asyncio
    async def test_move_camera_zoom_limits(self, controller):
        """Zoom 범위 제한 테스트"""
        # 1x ~ 20x 범위
        result = await controller.move_camera("cam_01", zoom=25)
        assert result["success"] is True
        assert 1 <= result["position"]["zoom"] <= 20

    @pytest.mark.asyncio
    async def test_move_camera_offline(self, controller):
        """오프라인 카메라 제어"""
        # cam_05는 기본적으로 offline
        result = await controller.move_camera("cam_05", pan=45)

        assert result["success"] is False
        assert "오프라인" in result["error"]


class TestCCTVControllerPresets:
    """프리셋 관리 테스트"""

    @pytest.fixture
    def controller(self):
        return CCTVController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_go_to_preset_success(self, controller):
        """프리셋 이동 성공"""
        result = await controller.go_to_preset("cam_01", "entrance")

        assert result["success"] is True
        assert result["preset_id"] == "entrance"

    @pytest.mark.asyncio
    async def test_go_to_preset_invalid_camera(self, controller):
        """존재하지 않는 카메라"""
        result = await controller.go_to_preset("invalid_cam", "entrance")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_go_to_preset_invalid_preset(self, controller):
        """존재하지 않는 프리셋"""
        result = await controller.go_to_preset("cam_01", "invalid_preset")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_save_preset_success(self, controller):
        """프리셋 저장 성공"""
        # 먼저 카메라 이동
        await controller.move_camera("cam_01", pan=120, tilt=30, zoom=5.0)

        # 프리셋 저장
        result = await controller.save_preset("cam_01", "new_preset", "새로운 위치")

        assert result["success"] is True
        assert result["preset_id"] == "new_preset"

    @pytest.mark.asyncio
    async def test_save_preset_overwrite(self, controller):
        """기존 프리셋 덮어쓰기"""
        result = await controller.save_preset("cam_01", "entrance", "입구 새 위치")

        assert result["success"] is True


class TestCCTVControllerRecording:
    """녹화 제어 테스트"""

    @pytest.fixture
    def controller(self):
        return CCTVController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_start_recording_success(self, controller):
        """녹화 시작 성공"""
        result = await controller.start_recording("cam_01")

        assert result["success"] is True
        assert result["camera_id"] == "cam_01"
        assert controller._cameras["cam_01"].is_recording is True

    @pytest.mark.asyncio
    async def test_start_recording_with_duration(self, controller):
        """지정 시간 녹화"""
        result = await controller.start_recording("cam_01", duration=30)

        assert result["success"] is True
        assert result["duration"] == 30

    @pytest.mark.asyncio
    async def test_start_recording_with_quality(self, controller):
        """품질 지정 녹화"""
        result = await controller.start_recording("cam_01", quality="max")

        assert result["success"] is True
        assert result["quality"] == "max"

    @pytest.mark.asyncio
    async def test_start_recording_already_recording(self, controller):
        """이미 녹화 중인 경우"""
        await controller.start_recording("cam_01")
        result = await controller.start_recording("cam_01")

        # 이미 녹화 중이면 실패
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_stop_recording_success(self, controller):
        """녹화 중지 성공"""
        await controller.start_recording("cam_01")
        result = await controller.stop_recording("cam_01")

        assert result["success"] is True
        assert controller._cameras["cam_01"].is_recording is False

    @pytest.mark.asyncio
    async def test_stop_recording_not_recording(self, controller):
        """녹화하지 않는 카메라 중지"""
        result = await controller.stop_recording("cam_01")

        # 녹화 중이 아니면 실패
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_recording_list_empty(self, controller):
        """빈 녹화 목록 조회"""
        result = await controller.get_recording_list()

        assert "recordings" in result
        assert result["recordings"] == []

    @pytest.mark.asyncio
    async def test_get_recording_list_with_entries(self, controller):
        """녹화 목록 조회"""
        # 녹화 시작 및 중지
        await controller.start_recording("cam_01")
        await controller.stop_recording("cam_01")

        result = await controller.get_recording_list()

        assert "recordings" in result
        assert len(result["recordings"]) >= 1


class TestCCTVControllerSnapshot:
    """스냅샷 캡처 테스트"""

    @pytest.fixture
    def controller(self):
        return CCTVController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_capture_snapshot_success(self, controller):
        """스냅샷 캡처 성공"""
        result = await controller.capture_snapshot("cam_01")

        assert result["success"] is True
        assert result["camera_id"] == "cam_01"
        assert "filename" in result

    @pytest.mark.asyncio
    async def test_capture_snapshot_with_resolution(self, controller):
        """해상도 지정 스냅샷"""
        result = await controller.capture_snapshot("cam_01", resolution="4k")

        assert result["success"] is True
        assert result["resolution"] == "4k"

    @pytest.mark.asyncio
    async def test_capture_snapshot_invalid_camera(self, controller):
        """존재하지 않는 카메라 스냅샷"""
        result = await controller.capture_snapshot("invalid_cam")

        assert result["success"] is False


class TestCCTVControllerStatus:
    """상태 조회 테스트"""

    @pytest.fixture
    def controller(self):
        return CCTVController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_get_camera_status_single(self, controller):
        """단일 카메라 상태 조회"""
        result = await controller.get_camera_status("cam_01")

        # 단일 카메라 조회는 직접 반환
        assert "camera_id" in result
        assert result["camera_id"] == "cam_01"

    @pytest.mark.asyncio
    async def test_get_camera_status_all(self, controller):
        """전체 카메라 상태 조회"""
        result = await controller.get_camera_status()

        assert "cameras" in result
        assert "total" in result
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_get_camera_status_includes_position(self, controller):
        """상태에 PTZ 위치 포함"""
        result = await controller.get_camera_status("cam_01")

        assert "position" in result
        assert "pan" in result["position"]
        assert "tilt" in result["position"]
        assert "zoom" in result["position"]


class TestCCTVControllerMotionDetection:
    """모션 감지 설정 테스트"""

    @pytest.fixture
    def controller(self):
        return CCTVController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_set_motion_detection_enable(self, controller):
        """모션 감지 활성화"""
        result = await controller.set_motion_detection("cam_01", enabled=True)

        assert result["success"] is True
        assert result["motion_detection"] is True  # enabled -> motion_detection

    @pytest.mark.asyncio
    async def test_set_motion_detection_disable(self, controller):
        """모션 감지 비활성화"""
        result = await controller.set_motion_detection("cam_01", enabled=False)

        assert result["success"] is True
        assert result["motion_detection"] is False

    @pytest.mark.asyncio
    async def test_set_motion_detection_sensitivity(self, controller):
        """모션 감지 민감도 설정"""
        result = await controller.set_motion_detection(
            "cam_01",
            enabled=True,
            sensitivity="high"
        )

        assert result["success"] is True
        assert result["sensitivity"] == "high"


class TestCCTVControllerSync:
    """동기 래퍼 테스트"""

    def test_sync_move_camera(self):
        """동기 카메라 이동"""
        controller = CCTVControllerSync(simulation_mode=True)
        result = controller.move_camera("cam_01", pan=45)

        assert result["success"] is True

    def test_sync_get_camera_status(self):
        """동기 상태 조회"""
        controller = CCTVControllerSync(simulation_mode=True)
        result = controller.get_camera_status()

        assert "cameras" in result
        assert result["total"] == 5

    def test_sync_start_recording(self):
        """동기 녹화 시작"""
        controller = CCTVControllerSync(simulation_mode=True)
        result = controller.start_recording("cam_01")

        assert result["success"] is True

    def test_sync_capture_snapshot(self):
        """동기 스냅샷 캡처"""
        controller = CCTVControllerSync(simulation_mode=True)
        result = controller.capture_snapshot("cam_01")

        assert result["success"] is True


class TestCameraStateEnum:
    """CameraState Enum 테스트"""

    def test_camera_states(self):
        """카메라 상태 값 확인"""
        assert CameraState.ONLINE.value == "online"
        assert CameraState.OFFLINE.value == "offline"
        assert CameraState.RECORDING.value == "recording"
        assert CameraState.ERROR.value == "error"
        assert CameraState.MAINTENANCE.value == "maintenance"


class TestRecordingQualityEnum:
    """RecordingQuality Enum 테스트"""

    def test_recording_quality(self):
        """녹화 품질 값 확인"""
        assert RecordingQuality.LOW.value == "low"
        assert RecordingQuality.MEDIUM.value == "medium"
        assert RecordingQuality.HIGH.value == "high"
        assert RecordingQuality.MAX.value == "max"


class TestCameraIdNormalization:
    """카메라 ID 정규화 테스트"""

    @pytest.fixture
    def controller(self):
        return CCTVController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_normalize_korean_name(self, controller):
        """한글 이름 정규화"""
        result = await controller.move_camera("로비", pan=45)
        assert result["success"] is True
        assert result["camera_id"] == "cam_01"

    @pytest.mark.asyncio
    async def test_normalize_number_name(self, controller):
        """번호 이름 정규화"""
        result = await controller.move_camera("1번 카메라", pan=45)
        assert result["success"] is True
        assert result["camera_id"] == "cam_01"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
