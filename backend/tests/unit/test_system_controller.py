"""
System Controller 단위 테스트

자연어 명령 처리 및 Function Calling 엔진을 테스트합니다.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

import sys
sys.path.insert(0, '/home/sphwang/dev/Total-LLM/backend')

from services.control.system_controller import (
    SystemController,
    SystemControllerSync
)
from services.control.function_schemas import (
    ACU_FUNCTIONS,
    CCTV_FUNCTIONS,
    SYSTEM_FUNCTIONS,
    ALL_FUNCTIONS,
    get_function_schema,
    get_functions_by_category
)


class TestSystemControllerInit:
    """System Controller 초기화 테스트"""

    def test_init_simulation_mode(self):
        """시뮬레이션 모드 초기화"""
        controller = SystemController(simulation_mode=True)
        assert controller.acu is not None
        assert controller.cctv is not None

    def test_init_with_ollama_config(self):
        """Ollama 설정으로 초기화"""
        controller = SystemController(
            simulation_mode=True,
            ollama_host="http://localhost:11434",
            model_name="qwen2.5:0.5b"
        )
        assert controller.ollama_host == "http://localhost:11434"
        assert controller.model_name == "qwen2.5:0.5b"

    def test_function_handlers_registered(self):
        """함수 핸들러 등록 확인"""
        controller = SystemController(simulation_mode=True)
        # ACU 함수들
        assert "unlock_door" in controller._function_handlers
        assert "lock_door" in controller._function_handlers
        # CCTV 함수들
        assert "start_recording" in controller._function_handlers
        assert "capture_snapshot" in controller._function_handlers
        # 시스템 함수들
        assert "get_system_status" in controller._function_handlers


class TestSystemControllerKeywordProcessing:
    """키워드 기반 명령 처리 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_process_door_open_command(self, controller):
        """문 열기 명령 처리"""
        result = await controller.process_command("1번 문 열어줘", use_llm=False)

        assert result["success"] is True
        assert len(result["executions"]) > 0

    @pytest.mark.asyncio
    async def test_process_door_lock_command(self, controller):
        """문 잠금 명령 처리"""
        result = await controller.process_command("정문 잠가줘", use_llm=False)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_door_status_command(self, controller):
        """문 상태 확인 명령"""
        result = await controller.process_command("출입문 상태 확인해줘", use_llm=False)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_recording_start_command(self, controller):
        """녹화 시작 명령"""
        result = await controller.process_command("1번 카메라 녹화 시작", use_llm=False)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_recording_stop_command(self, controller):
        """녹화 중지 명령"""
        # 먼저 녹화 시작
        await controller.process_command("1번 카메라 녹화 시작", use_llm=False)
        result = await controller.process_command("1번 카메라 녹화 중지", use_llm=False)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_snapshot_command(self, controller):
        """스냅샷 명령"""
        result = await controller.process_command("현재 화면 캡처해줘", use_llm=False)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_system_status_command(self, controller):
        """시스템 상태 조회 명령"""
        result = await controller.process_command("전체 시스템 상태 확인", use_llm=False)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_emergency_unlock_command(self, controller):
        """비상 개방 명령"""
        result = await controller.process_command("비상 개방", use_llm=False)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_process_unknown_command(self, controller):
        """알 수 없는 명령"""
        result = await controller.process_command("날씨 어때?", use_llm=False)

        assert result["success"] is False
        assert "이해하지 못했습니다" in result["message"]


class TestSystemControllerDoorIdExtraction:
    """도어 ID 추출 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    def test_extract_door_id_number(self, controller):
        """숫자로 된 문 ID 추출"""
        door_id = controller._extract_door_id("1번 문 열어줘")
        assert door_id == "door_01"

    def test_extract_door_id_name(self, controller):
        """이름으로 된 문 ID 추출"""
        door_id = controller._extract_door_id("정문 열어줘")
        assert door_id == "door_01"

    def test_extract_door_id_back_door(self, controller):
        """후문 ID 추출"""
        door_id = controller._extract_door_id("후문 잠가줘")
        assert door_id == "door_02"

    def test_extract_door_id_server_room(self, controller):
        """서버실 ID 추출"""
        door_id = controller._extract_door_id("서버실 문 열어줘")
        assert door_id == "door_04"

    def test_extract_door_id_default(self, controller):
        """ID를 찾을 수 없을 때 기본값"""
        door_id = controller._extract_door_id("문 열어줘")
        assert door_id == "door_01"


class TestSystemControllerCameraIdExtraction:
    """카메라 ID 추출 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    def test_extract_camera_id_number(self, controller):
        """숫자로 된 카메라 ID 추출"""
        cam_id = controller._extract_camera_id("1번 카메라 이동")
        assert cam_id == "cam_01"

    def test_extract_camera_id_name(self, controller):
        """이름으로 된 카메라 ID 추출"""
        cam_id = controller._extract_camera_id("로비 카메라 줌")
        assert cam_id == "cam_01"

    def test_extract_camera_id_parking(self, controller):
        """주차장 카메라 ID 추출"""
        cam_id = controller._extract_camera_id("주차장 카메라")
        assert cam_id == "cam_02"

    def test_extract_camera_id_default(self, controller):
        """ID를 찾을 수 없을 때 기본값"""
        cam_id = controller._extract_camera_id("카메라 이동")
        assert cam_id == "cam_01"


class TestSystemControllerPresetIdExtraction:
    """프리셋 ID 추출 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    def test_extract_preset_id_entrance(self, controller):
        """입구 프리셋 ID 추출"""
        preset_id = controller._extract_preset_id("입구 프리셋으로")
        assert preset_id == "entrance"

    def test_extract_preset_id_parking(self, controller):
        """주차장 프리셋 ID 추출"""
        preset_id = controller._extract_preset_id("주차장 프리셋")
        assert preset_id == "parking"

    def test_extract_preset_id_wide(self, controller):
        """와이드 프리셋 ID 추출"""
        preset_id = controller._extract_preset_id("전체 화면으로")
        assert preset_id == "wide"


class TestFunctionSchemas:
    """Function Schema 테스트"""

    def test_acu_functions_count(self):
        """ACU 함수 개수 확인"""
        assert len(ACU_FUNCTIONS) == 8

    def test_cctv_functions_count(self):
        """CCTV 함수 개수 확인"""
        assert len(CCTV_FUNCTIONS) == 9

    def test_system_functions_count(self):
        """시스템 함수 개수 확인"""
        assert len(SYSTEM_FUNCTIONS) == 2

    def test_all_functions_count(self):
        """전체 함수 개수 확인"""
        assert len(ALL_FUNCTIONS) == 19

    def test_get_function_schema_valid(self):
        """유효한 함수 스키마 조회"""
        schema = get_function_schema("unlock_door")
        assert schema is not None
        assert schema["name"] == "unlock_door"
        assert "parameters" in schema

    def test_get_function_schema_invalid(self):
        """존재하지 않는 함수 스키마 조회"""
        schema = get_function_schema("invalid_function")
        assert schema is None

    def test_get_functions_by_category_acu(self):
        """ACU 카테고리 함수 조회"""
        functions = get_functions_by_category("acu")
        assert len(functions) == 8

    def test_get_functions_by_category_cctv(self):
        """CCTV 카테고리 함수 조회"""
        functions = get_functions_by_category("cctv")
        assert len(functions) == 9

    def test_get_functions_by_category_system(self):
        """시스템 카테고리 함수 조회"""
        functions = get_functions_by_category("system")
        assert len(functions) == 2

    def test_function_schema_structure(self):
        """함수 스키마 구조 검증"""
        for func in ALL_FUNCTIONS:
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert "type" in func["parameters"]
            assert func["parameters"]["type"] == "object"
            assert "properties" in func["parameters"]
            assert "required" in func["parameters"]


class TestSystemControllerSync:
    """동기 래퍼 테스트"""

    def test_sync_process_command(self):
        """동기 명령 처리"""
        controller = SystemControllerSync(simulation_mode=True)
        result = controller.process_command("1번 문 열어줘", use_llm=False)

        assert result["success"] is True

    def test_sync_execute_function(self):
        """동기 함수 실행"""
        controller = SystemControllerSync(simulation_mode=True)
        result = controller.execute_function("unlock_door", {"door_id": "door_01"})

        assert result["success"] is True


class TestSystemControllerSystemStatus:
    """시스템 상태 조회 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_get_system_status(self, controller):
        """시스템 상태 조회"""
        result = await controller._get_system_status()

        assert result["success"] is True
        assert "acu" in result
        assert "cctv" in result

    @pytest.mark.asyncio
    async def test_get_alerts(self, controller):
        """알림 조회"""
        result = await controller._get_alerts()

        assert result["success"] is True
        assert "alerts" in result

    @pytest.mark.asyncio
    async def test_get_alerts_by_severity(self, controller):
        """심각도별 알림 조회"""
        result = await controller._get_alerts(severity="warning")

        assert result["success"] is True


class TestSystemControllerExecuteFunction:
    """함수 직접 실행 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_execute_function_valid(self, controller):
        """유효한 함수 실행"""
        result = await controller.execute_function("unlock_door", {"door_id": "door_01"})

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_function_invalid(self, controller):
        """존재하지 않는 함수 실행"""
        result = await controller.execute_function("invalid_function", {})

        assert result["success"] is False
        assert "Unknown function" in result["error"]

    @pytest.mark.asyncio
    async def test_get_available_functions(self, controller):
        """사용 가능한 함수 목록"""
        functions = controller.get_available_functions()

        assert "unlock_door" in functions
        assert "start_recording" in functions
        assert "get_system_status" in functions


class TestSystemControllerIntegration:
    """통합 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_complex_workflow(self, controller):
        """복잡한 워크플로우 테스트"""
        # 1. 문 열기
        result1 = await controller.process_command("1번 문 열어줘", use_llm=False)
        assert result1["success"] is True

        # 2. 카메라 녹화 시작
        result2 = await controller.process_command("1번 카메라 녹화 시작", use_llm=False)
        assert result2["success"] is True

        # 3. 시스템 상태 확인
        result3 = await controller.process_command("시스템 상태 확인", use_llm=False)
        assert result3["success"] is True

        # 4. 문 잠금
        result4 = await controller.process_command("1번 문 잠가줘", use_llm=False)
        assert result4["success"] is True

        # 5. 녹화 중지
        result5 = await controller.process_command("1번 카메라 녹화 중지", use_llm=False)
        assert result5["success"] is True

    @pytest.mark.asyncio
    async def test_concurrent_commands(self, controller):
        """동시 명령 처리 테스트"""
        commands = [
            ("1번 문 열어줘", False),
            ("2번 문 열어줘", False),
            ("시스템 상태 확인", False)
        ]

        # 동시에 명령 실행
        results = await asyncio.gather(
            *[controller.process_command(cmd, use_llm=use_llm) for cmd, use_llm in commands]
        )

        # 모든 명령이 성공해야 함
        for result in results:
            assert result["success"] is True


class TestSystemControllerResponseFormatting:
    """응답 포맷팅 테스트"""

    @pytest.fixture
    def controller(self):
        return SystemController(simulation_mode=True)

    @pytest.mark.asyncio
    async def test_response_includes_message(self, controller):
        """응답에 메시지 포함"""
        result = await controller.process_command("1번 문 열어줘", use_llm=False)

        assert "message" in result

    @pytest.mark.asyncio
    async def test_response_includes_command(self, controller):
        """응답에 원본 명령 포함"""
        command = "1번 문 열어줘"
        result = await controller.process_command(command, use_llm=False)

        assert result["command"] == command

    @pytest.mark.asyncio
    async def test_response_includes_executions(self, controller):
        """응답에 실행 정보 포함"""
        result = await controller.process_command("1번 문 열어줘", use_llm=False)

        assert "executions" in result
        assert len(result["executions"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
