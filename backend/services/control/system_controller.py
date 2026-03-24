"""
System Controller - Function Calling 기반 외부 시스템 제어 엔진

vLLM OpenAI 호환 API (Qwen2.5-14B-Instruct-AWQ)를 사용하여
자연어 명령을 분석하고 ACU/CCTV 시스템을 제어합니다.
"""

from typing import Dict, Any, Optional, List, Callable
import json
import logging
import asyncio

from .function_schemas import ALL_FUNCTIONS, ACU_FUNCTIONS, CCTV_FUNCTIONS, FUNCTION_MAP
from .acu_controller import ACUController
from .cctv_controller import CCTVController

logger = logging.getLogger(__name__)


class SystemController:
    """
    Function Calling 기반 외부 시스템 제어 엔진

    사용자의 자연어 명령을 분석하여 적절한 함수를 호출합니다.
    vLLM OpenAI 호환 API 또는 Ollama를 지원합니다.
    """

    def __init__(
        self,
        model_name: str = "/model",
        vllm_base_url: str = "http://localhost:9000/v1",
        ollama_host: str = "http://localhost:11434",
        simulation_mode: bool = True,
        prefer_vllm: bool = True,
    ):
        """
        Args:
            model_name: 모델 이름 (vLLM: "/model", Ollama: "qwen2.5:0.5b-instruct")
            vllm_base_url: vLLM OpenAI 호환 API 주소
            ollama_host: Ollama 서버 주소 (fallback)
            simulation_mode: ACU/CCTV 시뮬레이션 모드
            prefer_vllm: vLLM 우선 사용 여부
        """
        self.model_name = model_name
        self.vllm_base_url = vllm_base_url
        self.ollama_host = ollama_host
        self.prefer_vllm = prefer_vllm

        # 하위 컨트롤러
        self.acu = ACUController(simulation_mode=simulation_mode)
        self.cctv = CCTVController(simulation_mode=simulation_mode)

        # 함수 핸들러 매핑
        self._function_handlers: Dict[str, Callable] = {
            # ACU 함수들
            "unlock_door": self.acu.unlock_door,
            "lock_door": self.acu.lock_door,
            "get_door_status": self.acu.get_door_status,
            "get_access_log": self.acu.get_access_log,
            "grant_access": self.acu.grant_access,
            "revoke_access": self.acu.revoke_access,
            "emergency_unlock_all": self.acu.emergency_unlock_all,
            "emergency_lock_all": self.acu.emergency_lock_all,
            # CCTV 함수들
            "move_camera": self.cctv.move_camera,
            "go_to_preset": self.cctv.go_to_preset,
            "save_preset": self.cctv.save_preset,
            "start_recording": self.cctv.start_recording,
            "stop_recording": self.cctv.stop_recording,
            "capture_snapshot": self.cctv.capture_snapshot,
            "get_camera_status": self.cctv.get_camera_status,
            "get_recording_list": self.cctv.get_recording_list,
            "set_motion_detection": self.cctv.set_motion_detection,
            # 시스템 함수들
            "get_system_status": self._get_system_status,
            "get_alerts": self._get_alerts,
        }

        self._vllm_available = False
        self._ollama_available = False
        logger.info(f"SystemController initialized with model: {model_name}, vLLM: {vllm_base_url}")

    async def _check_vllm(self) -> bool:
        """vLLM 서버 가용성 확인"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.vllm_base_url}/models", timeout=5.0)
                self._vllm_available = response.status_code == 200
                if self._vllm_available:
                    logger.info("vLLM server is available")
                return self._vllm_available
        except Exception as e:
            logger.warning(f"vLLM not available: {e}")
            self._vllm_available = False
            return False

    async def _check_ollama(self) -> bool:
        """Ollama 서버 가용성 확인 (fallback)"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.ollama_host}/api/tags", timeout=5.0)
                self._ollama_available = response.status_code == 200
                return self._ollama_available
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._ollama_available = False
            return False

    async def process_command(
        self,
        user_input: str,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        사용자 자연어 명령 처리

        Args:
            user_input: 자연어 명령 (예: "1번 출입문 열어줘", "카메라 녹화 시작")
            use_llm: LLM을 사용하여 명령 파싱 (False면 키워드 기반)

        Returns:
            실행 결과
        """
        logger.info(f"Processing command: {user_input}")

        # LLM 사용 여부 결정 - vLLM 우선, Ollama fallback
        if use_llm:
            if self.prefer_vllm and await self._check_vllm():
                return await self._process_with_vllm(user_input)
            elif await self._check_ollama():
                return await self._process_with_ollama(user_input)

        return await self._process_with_keywords(user_input)

    async def _process_with_vllm(self, user_input: str) -> Dict[str, Any]:
        """vLLM OpenAI 호환 API를 사용한 명령 처리"""
        try:
            import httpx

            system_prompt = self._build_system_prompt()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            # OpenAI 호환 Function Calling 형식으로 변환
            tools = self._convert_to_openai_tools()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.vllm_base_url}/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto",
                        "temperature": 0.7,
                        "max_tokens": 512,
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(f"vLLM error: {response.text}")
                    return await self._process_with_keywords(user_input)

                result = response.json()
                choice = result.get("choices", [{}])[0]
                message = choice.get("message", {})

                # Function Call 처리 (OpenAI 형식)
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    return await self._execute_openai_tool_calls(user_input, tool_calls)
                else:
                    # 일반 응답
                    return {
                        "success": True,
                        "command": user_input,
                        "executions": [],
                        "message": message.get("content", "명령을 처리했습니다."),
                        "llm_backend": "vllm",
                    }

        except Exception as e:
            logger.error(f"vLLM processing error: {e}")
            return await self._process_with_keywords(user_input)

    async def _process_with_ollama(self, user_input: str) -> Dict[str, Any]:
        """Ollama를 사용한 명령 처리 (fallback)"""
        try:
            import httpx

            system_prompt = self._build_system_prompt()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_host}/api/chat",
                    json={
                        "model": "qwen2.5:0.5b-instruct",  # Ollama용 모델명
                        "messages": messages,
                        "tools": ALL_FUNCTIONS,
                        "stream": False,
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(f"Ollama error: {response.text}")
                    return await self._process_with_keywords(user_input)

                result = response.json()
                message = result.get("message", {})

                # Function Call 처리
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    return await self._execute_tool_calls(user_input, tool_calls)
                else:
                    # 일반 응답
                    return {
                        "success": True,
                        "command": user_input,
                        "executions": [],
                        "message": message.get("content", "명령을 처리했습니다."),
                        "llm_backend": "ollama",
                    }

        except Exception as e:
            logger.error(f"Ollama processing error: {e}")
            return await self._process_with_keywords(user_input)

    def _convert_to_openai_tools(self) -> List[Dict[str, Any]]:
        """Ollama 형식 함수 스키마를 OpenAI 형식으로 변환"""
        openai_tools = []
        for func in ALL_FUNCTIONS:
            openai_tool = {
                "type": "function",
                "function": func.get("function", func)
            }
            openai_tools.append(openai_tool)
        return openai_tools

    async def _execute_openai_tool_calls(
        self,
        user_input: str,
        tool_calls: List[Dict],
    ) -> Dict[str, Any]:
        """OpenAI 형식 Function Call 실행"""
        executions = []

        for tool_call in tool_calls:
            func_name = tool_call.get("function", {}).get("name")
            func_args_str = tool_call.get("function", {}).get("arguments", "{}")

            # 문자열인 경우 JSON 파싱
            if isinstance(func_args_str, str):
                try:
                    func_args = json.loads(func_args_str)
                except json.JSONDecodeError:
                    func_args = {}
            else:
                func_args = func_args_str

            if func_name in self._function_handlers:
                handler = self._function_handlers[func_name]
                try:
                    result = await handler(**func_args)
                    executions.append({
                        "function": func_name,
                        "arguments": func_args,
                        "result": result,
                    })
                except Exception as e:
                    logger.error(f"Function execution error: {func_name} - {e}")
                    executions.append({
                        "function": func_name,
                        "arguments": func_args,
                        "result": {"success": False, "error": str(e)},
                    })
            else:
                logger.warning(f"Unknown function: {func_name}")

        return {
            "success": len(executions) > 0,
            "command": user_input,
            "executions": executions,
            "message": self._format_response(executions),
            "llm_backend": "vllm",
        }

    async def _process_with_keywords(self, user_input: str) -> Dict[str, Any]:
        """키워드 기반 명령 처리 (LLM 없이)"""
        input_lower = user_input.lower()
        executions = []

        # ACU 키워드 매칭
        if any(kw in input_lower for kw in ["열어", "개방", "unlock", "오픈"]):
            door_id = self._extract_door_id(user_input)
            if door_id:
                result = await self.acu.unlock_door(door_id)
                executions.append({"function": "unlock_door", "arguments": {"door_id": door_id}, "result": result})

        elif any(kw in input_lower for kw in ["잠가", "잠금", "lock", "닫아"]):
            door_id = self._extract_door_id(user_input)
            if door_id:
                result = await self.acu.lock_door(door_id)
                executions.append({"function": "lock_door", "arguments": {"door_id": door_id}, "result": result})

        elif any(kw in input_lower for kw in ["문 상태", "출입문 상태", "door status"]):
            door_id = self._extract_door_id(user_input)
            result = await self.acu.get_door_status(door_id)
            executions.append({"function": "get_door_status", "arguments": {"door_id": door_id}, "result": result})

        elif any(kw in input_lower for kw in ["비상 개방", "전체 열어", "emergency unlock"]):
            result = await self.acu.emergency_unlock_all(reason="user_command", description=user_input)
            executions.append({"function": "emergency_unlock_all", "arguments": {"reason": "user_command"}, "result": result})

        # CCTV 키워드 매칭
        elif any(kw in input_lower for kw in ["녹화 시작", "recording start", "녹화해"]):
            camera_id = self._extract_camera_id(user_input)
            if camera_id:
                result = await self.cctv.start_recording(camera_id)
                executions.append({"function": "start_recording", "arguments": {"camera_id": camera_id}, "result": result})

        elif any(kw in input_lower for kw in ["녹화 중지", "녹화 멈춰", "recording stop"]):
            camera_id = self._extract_camera_id(user_input)
            if camera_id:
                result = await self.cctv.stop_recording(camera_id)
                executions.append({"function": "stop_recording", "arguments": {"camera_id": camera_id}, "result": result})

        elif any(kw in input_lower for kw in ["스냅샷", "사진", "캡처", "snapshot"]):
            camera_id = self._extract_camera_id(user_input)
            if camera_id:
                result = await self.cctv.capture_snapshot(camera_id)
                executions.append({"function": "capture_snapshot", "arguments": {"camera_id": camera_id}, "result": result})

        elif any(kw in input_lower for kw in ["카메라 상태", "cctv 상태", "camera status"]):
            camera_id = self._extract_camera_id(user_input)
            result = await self.cctv.get_camera_status(camera_id)
            executions.append({"function": "get_camera_status", "arguments": {"camera_id": camera_id}, "result": result})

        elif any(kw in input_lower for kw in ["프리셋", "preset"]):
            camera_id = self._extract_camera_id(user_input)
            preset_id = self._extract_preset_id(user_input)
            if camera_id and preset_id:
                result = await self.cctv.go_to_preset(camera_id, preset_id)
                executions.append({"function": "go_to_preset", "arguments": {"camera_id": camera_id, "preset_id": preset_id}, "result": result})

        # 시스템 상태
        elif any(kw in input_lower for kw in ["시스템 상태", "전체 상태", "system status"]):
            result = await self._get_system_status()
            executions.append({"function": "get_system_status", "arguments": {}, "result": result})

        # 결과 생성
        if executions:
            return {
                "success": True,
                "command": user_input,
                "executions": executions,
                "message": self._format_response(executions),
            }
        else:
            return {
                "success": False,
                "command": user_input,
                "executions": [],
                "message": f"❓ 명령을 이해하지 못했습니다: '{user_input}'\n\n지원하는 명령 예시:\n- '1번 출입문 열어줘'\n- '로비 카메라 녹화 시작'\n- '시스템 상태 확인'",
            }

    async def _execute_tool_calls(
        self,
        user_input: str,
        tool_calls: List[Dict],
    ) -> Dict[str, Any]:
        """Function Call 실행"""
        executions = []

        for tool_call in tool_calls:
            func_name = tool_call.get("function", {}).get("name")
            func_args = tool_call.get("function", {}).get("arguments", {})

            # 문자열인 경우 JSON 파싱
            if isinstance(func_args, str):
                try:
                    func_args = json.loads(func_args)
                except json.JSONDecodeError:
                    func_args = {}

            if func_name in self._function_handlers:
                handler = self._function_handlers[func_name]
                try:
                    result = await handler(**func_args)
                    executions.append({
                        "function": func_name,
                        "arguments": func_args,
                        "result": result,
                    })
                except Exception as e:
                    logger.error(f"Function execution error: {func_name} - {e}")
                    executions.append({
                        "function": func_name,
                        "arguments": func_args,
                        "result": {"success": False, "error": str(e)},
                    })
            else:
                logger.warning(f"Unknown function: {func_name}")

        return {
            "success": len(executions) > 0,
            "command": user_input,
            "executions": executions,
            "message": self._format_response(executions),
        }

    def _build_system_prompt(self) -> str:
        """Function Calling 시스템 프롬프트 생성 - 등록된 실제 장치 정보 포함"""
        # 실제 등록된 카메라 목록 생성
        camera_list = []
        for cam_id, cam in self.cctv._cameras.items():
            camera_list.append(f"- {cam_id}: {cam.name} ({cam.location})")
        cameras_str = "\n".join(camera_list) if camera_list else "- (등록된 카메라 없음)"

        # 실제 등록된 출입문 목록 생성
        door_list = []
        for door_id, door in self.acu._doors.items():
            door_list.append(f"- {door_id}: {door.name} ({door.location})")
        doors_str = "\n".join(door_list) if door_list else "- (등록된 출입문 없음)"

        return f"""당신은 보안 시스템 제어 AI입니다.
사용자의 자연어 명령을 분석하여 적절한 함수를 호출해야 합니다.

지원하는 시스템:
1. ACU (출입통제): 출입문 개폐, 잠금, 출입 이력 조회, 권한 관리
2. CCTV (영상감시): PTZ 제어, 녹화, 스냅샷, 프리셋 이동

현재 등록된 카메라 목록:
{cameras_str}

현재 등록된 출입문 목록:
{doors_str}

중요:
- 사용자가 장치 이름이나 위치를 말하면 위 목록에서 정확한 ID를 찾아 사용하세요.
- 예: "로비 카메라" → cam_01 또는 cam_121_01 (목록에서 확인)
- 한국어와 영어 명령 모두 처리할 수 있습니다."""

    def _extract_door_id(self, text: str) -> Optional[str]:
        """텍스트에서 문 ID 추출"""
        patterns = {
            "1번": "door_01", "1번문": "door_01", "정문": "door_01",
            "2번": "door_02", "2번문": "door_02", "후문": "door_02",
            "3번": "door_03", "3번문": "door_03", "주차장": "door_03",
            "4번": "door_04", "4번문": "door_04", "서버실": "door_04",
            "5번": "door_05", "5번문": "door_05", "회의실": "door_05",
        }
        for pattern, door_id in patterns.items():
            if pattern in text:
                return door_id
        return "door_01"  # 기본값

    def _extract_camera_id(self, text: str) -> Optional[str]:
        """텍스트에서 카메라 ID 추출"""
        patterns = {
            "1번": "cam_01", "1번 카메라": "cam_01", "로비": "cam_01",
            "2번": "cam_02", "2번 카메라": "cam_02", "주차장": "cam_02",
            "3번": "cam_03", "3번 카메라": "cam_03", "후문": "cam_03",
            "4번": "cam_04", "4번 카메라": "cam_04", "옥상": "cam_04",
            "5번": "cam_05", "5번 카메라": "cam_05", "서버실": "cam_05",
        }
        for pattern, cam_id in patterns.items():
            if pattern in text:
                return cam_id
        return "cam_01"  # 기본값

    def _extract_preset_id(self, text: str) -> Optional[str]:
        """텍스트에서 프리셋 ID 추출"""
        patterns = {
            "입구": "entrance", "entrance": "entrance",
            "주차장": "parking", "parking": "parking",
            "전체": "wide", "wide": "wide",
            "확대": "zoom_center", "zoom": "zoom_center",
        }
        for pattern, preset_id in patterns.items():
            if pattern in text.lower():
                return preset_id
        return None

    def _format_response(self, executions: List[Dict]) -> str:
        """실행 결과를 사용자 친화적 메시지로 변환"""
        if not executions:
            return "명령을 처리했습니다."

        messages = []
        for exec_info in executions:
            result = exec_info.get("result", {})
            if isinstance(result, dict):
                msg = result.get("message")
                if msg:
                    messages.append(msg)
                elif result.get("success") is False:
                    error = result.get("error", "알 수 없는 오류")
                    messages.append(f"❌ 오류: {error}")
                else:
                    func = exec_info.get("function", "명령")
                    messages.append(f"✅ {func} 실행 완료")

        return "\n".join(messages) if messages else "명령을 처리했습니다."

    async def _get_system_status(
        self,
        include_details: bool = False,
    ) -> Dict[str, Any]:
        """전체 시스템 상태 조회"""
        acu_status = await self.acu.get_door_status()
        cctv_status = await self.cctv.get_camera_status()

        return {
            "success": True,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "acu": acu_status,
            "cctv": cctv_status,
            "message": f"📊 시스템 상태\n- ACU: {acu_status.get('total', 0)}개 출입문\n- CCTV: {cctv_status.get('total', 0)}개 카메라 (녹화 중: {cctv_status.get('recording', 0)}개)",
        }

    async def _get_alerts(
        self,
        severity: str = "all",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """활성 알림 조회 (시뮬레이션)"""
        # 시뮬레이션용 알림 데이터
        alerts = [
            {"severity": "info", "message": "시스템 정상 운영 중", "timestamp": "2025-01-12T10:00:00"},
            {"severity": "warning", "message": "cam_05 오프라인", "timestamp": "2025-01-12T09:30:00"},
        ]

        if severity != "all":
            alerts = [a for a in alerts if a["severity"] == severity]

        return {
            "success": True,
            "total": len(alerts),
            "alerts": alerts[:limit],
        }

    async def execute_function(
        self,
        function_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """특정 함수 직접 실행"""
        if function_name not in self._function_handlers:
            return {
                "success": False,
                "error": f"Unknown function: {function_name}",
            }

        handler = self._function_handlers[function_name]
        try:
            result = await handler(**arguments)
            return result
        except Exception as e:
            logger.error(f"Function execution error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_available_functions(self) -> List[str]:
        """사용 가능한 함수 목록 반환"""
        return list(self._function_handlers.keys())

    def get_function_schema(self, function_name: str) -> Optional[Dict[str, Any]]:
        """함수 스키마 조회"""
        return FUNCTION_MAP.get(function_name)


# 동기 버전 래퍼
class SystemControllerSync:
    """동기식 System Controller 래퍼"""

    def __init__(self, *args, **kwargs):
        self._async_controller = SystemController(*args, **kwargs)

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def process_command(self, *args, **kwargs):
        return self._run(self._async_controller.process_command(*args, **kwargs))

    def execute_function(self, *args, **kwargs):
        return self._run(self._async_controller.execute_function(*args, **kwargs))

    @property
    def acu(self):
        return self._async_controller.acu

    @property
    def cctv(self):
        return self._async_controller.cctv
