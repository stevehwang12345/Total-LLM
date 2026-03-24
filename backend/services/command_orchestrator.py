#!/usr/bin/env python3
"""
Command Orchestrator for Security Monitoring System

Qwen Function Calling 결과를 받아 적절한 서비스로 라우팅하는 중앙 오케스트레이터
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CommandOrchestrator:
    """
    Qwen Function Call을 받아 적절한 서비스로 라우팅

    역할:
    1. search_documents → RAG Service
    2. register_device → Device Registry Service
    3. control_device → Device Control Service
    4. get_device_status → Device Registry Service
    5. list_devices → Device Registry Service
    """

    def __init__(
        self,
        rag_service=None,
        device_registry=None,
        device_control=None
    ):
        """
        Args:
            rag_service: RAG 서비스 인스턴스 (문서 검색용)
            device_registry: 장비 등록/조회 서비스
            device_control: 장비 제어 서비스
        """
        self.rag_service = rag_service
        self.device_registry = device_registry
        self.device_control = device_control

        logger.info("✅ CommandOrchestrator initialized")

    async def execute_function(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Function 실행 메인 로직

        Args:
            function_name: 실행할 함수 이름
            arguments: 함수 파라미터
            user_id: 요청 사용자 ID (감사 로그용)

        Returns:
            {
                "status": "success" | "error",
                "data": {...},
                "message": "...",
                "execution_time_ms": 123
            }
        """
        start_time = time.time()

        try:
            logger.info(f"🔧 Executing function: {function_name}")
            logger.debug(f"   Arguments: {arguments}")
            logger.debug(f"   User: {user_id}")

            # 함수별 라우팅
            if function_name == "search_documents":
                result = await self._search_documents(arguments)

            elif function_name == "register_device":
                result = await self._register_device(arguments, user_id)

            elif function_name == "control_device":
                result = await self._control_device(arguments, user_id)

            elif function_name == "get_device_status":
                result = await self._get_device_status(arguments)

            elif function_name == "list_devices":
                result = await self._list_devices(arguments)

            else:
                raise ValueError(f"Unknown function: {function_name}")

            # 실행 시간 계산
            execution_time_ms = int((time.time() - start_time) * 1000)
            result["execution_time_ms"] = execution_time_ms

            logger.info(f"✅ Function executed in {execution_time_ms}ms")
            return result

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Function execution failed: {e}", exc_info=True)

            return {
                "status": "error",
                "message": str(e),
                "error_type": type(e).__name__,
                "execution_time_ms": execution_time_ms
            }

    # ============================================
    # 1. 문서 검색 (RAG)
    # ============================================

    async def _search_documents(
        self,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        내부 문서 검색 (보안 정책, 로그, 매뉴얼)

        Args:
            arguments: {
                "query": str,
                "top_k": int,
                "filter_type": "policy" | "log" | "manual" | "all"
            }

        Returns:
            {
                "status": "success",
                "data": {
                    "documents": [
                        {
                            "content": str,
                            "metadata": {...},
                            "score": float
                        }
                    ],
                    "total_results": int,
                    "query": str
                }
            }
        """
        if not self.rag_service:
            raise RuntimeError("RAG service not initialized")

        query = arguments["query"]
        top_k = arguments.get("top_k", 5)
        filter_type = arguments.get("filter_type", "all")

        logger.info(f"🔍 Searching documents: query='{query}', top_k={top_k}, filter={filter_type}")

        # RAG 서비스 호출
        search_results = await self.rag_service.search(
            query=query,
            top_k=top_k,
            filter_metadata={"type": filter_type} if filter_type != "all" else None
        )

        return {
            "status": "success",
            "data": {
                "documents": search_results,
                "total_results": len(search_results),
                "query": query,
                "filter_type": filter_type
            },
            "message": f"{len(search_results)}개 문서를 찾았습니다."
        }

    # ============================================
    # 2. 장비 등록
    # ============================================

    async def _register_device(
        self,
        arguments: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        CCTV/ACU 장비 등록

        Args:
            arguments: {
                "device_type": "CCTV" | "ACU",
                "manufacturer": "한화" | "슈프리마" | "제네틱" | "머큐리",
                "ip_address": str,
                "port": int,
                "protocol": "SSH" | "REST" | "SNMP",
                "location": str (optional),
                "zone": str (optional),
                "username": str (optional),
                "password": str (optional),
                "api_key": str (optional)
            }

        Returns:
            {
                "status": "success",
                "data": {
                    "device_id": str,
                    "device_type": str,
                    "manufacturer": str,
                    "ip_address": str,
                    "status": "offline"
                }
            }
        """
        if not self.device_registry:
            raise RuntimeError("Device registry service not initialized")

        device_type = arguments["device_type"]
        manufacturer = arguments["manufacturer"]
        ip_address = arguments["ip_address"]

        logger.info(f"📝 Registering device: {device_type} ({manufacturer}) @ {ip_address}")

        # Device Registry 서비스 호출
        device = await self.device_registry.register_device(
            device_type=device_type,
            manufacturer=manufacturer,
            ip_address=ip_address,
            port=arguments.get("port", 22),
            protocol=arguments["protocol"],
            location=arguments.get("location"),
            zone=arguments.get("zone"),
            credentials={
                "username": arguments.get("username"),
                "password": arguments.get("password"),
                "api_key": arguments.get("api_key")
            },
            registered_by=user_id
        )

        return {
            "status": "success",
            "data": device,
            "message": f"장비 {device['device_id']}가 성공적으로 등록되었습니다."
        }

    # ============================================
    # 3. 장비 제어
    # ============================================

    async def _control_device(
        self,
        arguments: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        CCTV/ACU 장비 제어 실행

        Args:
            arguments: {
                "device_id": str,
                "command": "start_recording" | "stop_recording" | "open_camera_popup" |
                          "door_open" | "door_close" | "alarm_clear",
                "duration_seconds": int (optional),
                "reason": str (optional)
            }

        Returns:
            {
                "status": "success",
                "data": {
                    "control_id": int,
                    "device_id": str,
                    "command": str,
                    "result": str,
                    "rollback_executed": bool (ACU only)
                }
            }
        """
        if not self.device_control:
            raise RuntimeError("Device control service not initialized")

        device_id = arguments["device_id"]
        command = arguments["command"]

        logger.info(f"🎛️ Controlling device: {device_id} → {command}")

        # Device Control 서비스 호출
        control_result = await self.device_control.execute_command(
            device_id=device_id,
            command=command,
            duration_seconds=arguments.get("duration_seconds", 5),
            reason=arguments.get("reason", "사용자 요청"),
            executed_by=user_id
        )

        return {
            "status": "success",
            "data": control_result,
            "message": f"명령 '{command}'이(가) 실행되었습니다."
        }

    # ============================================
    # 4. 장비 상태 조회
    # ============================================

    async def _get_device_status(
        self,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        장비 상태 조회

        Args:
            arguments: {"device_id": str}

        Returns:
            {
                "status": "success",
                "data": {
                    "device_id": str,
                    "status": "online" | "offline" | "error",
                    "cpu_usage": float,
                    "memory_usage": float,
                    "uptime_seconds": int,
                    "last_health_check": str
                }
            }
        """
        if not self.device_registry:
            raise RuntimeError("Device registry service not initialized")

        device_id = arguments["device_id"]

        logger.info(f"📊 Getting device status: {device_id}")

        # Device Registry 서비스 호출
        status = await self.device_registry.get_device_status(device_id)

        return {
            "status": "success",
            "data": status,
            "message": f"장비 상태: {status['status']}"
        }

    # ============================================
    # 5. 장비 목록 조회
    # ============================================

    async def _list_devices(
        self,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        등록된 장비 목록 조회

        Args:
            arguments: {
                "device_type": "CCTV" | "ACU" | "all",
                "status_filter": "online" | "offline" | "all"
            }

        Returns:
            {
                "status": "success",
                "data": {
                    "devices": [
                        {
                            "device_id": str,
                            "device_type": str,
                            "manufacturer": str,
                            "ip_address": str,
                            "status": str,
                            "location": str
                        }
                    ],
                    "total_count": int
                }
            }
        """
        if not self.device_registry:
            raise RuntimeError("Device registry service not initialized")

        device_type = arguments.get("device_type", "all")
        status_filter = arguments.get("status_filter", "all")

        logger.info(f"📋 Listing devices: type={device_type}, status={status_filter}")

        # Device Registry 서비스 호출
        devices = await self.device_registry.list_devices(
            device_type=device_type,
            status_filter=status_filter
        )

        return {
            "status": "success",
            "data": {
                "devices": devices,
                "total_count": len(devices)
            },
            "message": f"{len(devices)}개 장비를 찾았습니다."
        }


# ============================================
# 편의 함수
# ============================================

def format_function_result_for_llm(result: Dict[str, Any]) -> str:
    """
    Function 실행 결과를 LLM이 읽기 쉬운 텍스트로 변환

    Args:
        result: execute_function 반환값

    Returns:
        포맷팅된 문자열
    """
    if result["status"] == "error":
        return f"❌ 오류 발생: {result['message']}"

    # 성공 케이스
    message = result.get("message", "")
    data = result.get("data", {})

    # 간단한 JSON 포맷팅
    import json
    formatted_data = json.dumps(data, ensure_ascii=False, indent=2)

    return f"{message}\n\n```json\n{formatted_data}\n```"
