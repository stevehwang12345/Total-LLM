#!/usr/bin/env python3
"""
Device Control Service

CCTV/ACU 장비 제어 및 롤백 로직을 담당하는 서비스
"""

import asyncpg
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class DeviceControl:
    """
    장비 제어 서비스

    역할:
    1. CCTV 제어 (녹화 시작/중지, 카메라 팝업)
    2. ACU 제어 (도어 개폐, 알람 해제)
    3. ACU 롤백 로직 (10초 타임아웃)
    4. 제어 이력 저장
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        device_registry,
        rollback_timeout: int = 10,
        max_retry: int = 3
    ):
        """
        Args:
            db_pool: asyncpg 연결 풀
            device_registry: DeviceRegistry 인스턴스
            rollback_timeout: ACU 롤백 타임아웃 (초)
            max_retry: 최대 재시도 횟수
        """
        self.db_pool = db_pool
        self.device_registry = device_registry
        self.rollback_timeout = rollback_timeout
        self.max_retry = max_retry

        # 제조사별 어댑터 초기화
        self.adapters = {
            "한화": HanwhaAdapter(),
            "슈프리마": SupremaAdapter(),
            "제네틱": GeneticAdapter(),
            "머큐리": MercuryAdapter()
        }

        logger.info(f"✅ DeviceControl initialized (rollback_timeout={rollback_timeout}s)")

    # ============================================
    # 메인 제어 로직
    # ============================================

    async def execute_command(
        self,
        device_id: str,
        command: str,
        duration_seconds: int = 5,
        reason: str = "사용자 요청",
        executed_by: str = "system"
    ) -> Dict[str, Any]:
        """
        장비 제어 명령 실행

        Args:
            device_id: 장비 ID
            command: 실행할 명령
            duration_seconds: 명령 지속 시간 (ACU door_open 등)
            reason: 제어 사유 (감사 로그)
            executed_by: 실행자 ID

        Returns:
            {
                "control_id": int,
                "device_id": str,
                "command": str,
                "status": "success" | "failed" | "rollback",
                "result": str,
                "rollback_executed": bool,
                "execution_time_ms": int
            }
        """
        start_time = time.time()

        # 장비 정보 조회
        device_info = await self.device_registry.get_device_info(device_id)

        # Control 이력 생성 (pending)
        control_id = await self._create_control_record(
            device_id=device_id,
            command=command,
            parameters={"duration_seconds": duration_seconds, "reason": reason},
            executed_by=executed_by
        )

        try:
            # 제조사 어댑터 선택
            manufacturer = device_info["manufacturer"]
            adapter = self.adapters.get(manufacturer)

            if not adapter:
                raise ValueError(f"지원하지 않는 제조사: {manufacturer}")

            logger.info(f"🎛️ Executing command: {device_id} → {command} (adapter={manufacturer})")

            # 명령 실행
            await self._update_control_status(control_id, "executing")

            result = await adapter.execute_command(
                device_info=device_info,
                command=command,
                duration_seconds=duration_seconds
            )

            # ACU 제어 + 롤백 필요 여부 확인
            rollback_executed = False
            if device_info["device_type"] == "ACU" and command in ["door_open", "door_close"]:
                # 롤백 대기
                logger.info(f"⏳ Waiting {self.rollback_timeout}s for rollback check...")
                await asyncio.sleep(self.rollback_timeout)

                # 롤백 명령 실행
                rollback_command = "door_close" if command == "door_open" else "door_open"
                logger.info(f"🔄 Executing rollback: {rollback_command}")

                try:
                    await adapter.execute_command(
                        device_info=device_info,
                        command=rollback_command,
                        duration_seconds=5
                    )

                    rollback_executed = True
                    await self._update_control_rollback(
                        control_id=control_id,
                        rollback_command=rollback_command,
                        rollback_status="success"
                    )

                except Exception as rollback_error:
                    logger.error(f"❌ Rollback failed: {rollback_error}")
                    await self._update_control_rollback(
                        control_id=control_id,
                        rollback_command=rollback_command,
                        rollback_status="failed"
                    )

            # 성공 처리
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._update_control_result(
                control_id=control_id,
                status="success",
                result=result,
                execution_time_ms=execution_time_ms
            )

            logger.info(f"✅ Command executed successfully in {execution_time_ms}ms")

            return {
                "control_id": control_id,
                "device_id": device_id,
                "command": command,
                "status": "success",
                "result": result,
                "rollback_executed": rollback_executed,
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Command execution failed: {e}", exc_info=True)

            await self._update_control_result(
                control_id=control_id,
                status="failed",
                error_message=str(e),
                execution_time_ms=execution_time_ms
            )

            raise

    # ============================================
    # DB 이력 관리
    # ============================================

    async def _create_control_record(
        self,
        device_id: str,
        command: str,
        parameters: Dict[str, Any],
        executed_by: str
    ) -> int:
        """제어 이력 생성 (pending)"""
        import json

        async with self.db_pool.acquire() as conn:
            control_id = await conn.fetchval(
                """
                INSERT INTO device_controls (
                    device_id, command, parameters, status, executed_by, executed_at
                )
                VALUES ($1, $2, $3, 'pending', $4, $5)
                RETURNING control_id
                """,
                device_id, command, json.dumps(parameters), executed_by, datetime.now()
            )

        return control_id

    async def _update_control_status(self, control_id: int, status: str) -> None:
        """제어 상태 업데이트"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE device_controls SET status = $2 WHERE control_id = $1",
                control_id, status
            )

    async def _update_control_result(
        self,
        control_id: int,
        status: str,
        result: str = None,
        error_message: str = None,
        execution_time_ms: int = 0
    ) -> None:
        """제어 결과 업데이트"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE device_controls
                SET status = $2, result = $3, error_message = $4,
                    completed_at = $5, execution_time_ms = $6
                WHERE control_id = $1
                """,
                control_id, status, result, error_message,
                datetime.now(), execution_time_ms
            )

    async def _update_control_rollback(
        self,
        control_id: int,
        rollback_command: str,
        rollback_status: str
    ) -> None:
        """롤백 정보 업데이트"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE device_controls
                SET rollback_required = TRUE,
                    rollback_command = $2,
                    rollback_status = $3,
                    rollback_executed_at = $4
                WHERE control_id = $1
                """,
                control_id, rollback_command, rollback_status, datetime.now()
            )


# ============================================
# 제조사별 어댑터 (Adapter Pattern)
# ============================================

class DeviceAdapter:
    """장비 제어 어댑터 기본 클래스"""

    async def execute_command(
        self,
        device_info: Dict[str, Any],
        command: str,
        duration_seconds: int
    ) -> str:
        """
        장비 제어 명령 실행

        Args:
            device_info: {device_id, device_type, manufacturer, ip_address, port, protocol, credentials}
            command: 실행할 명령
            duration_seconds: 지속 시간

        Returns:
            실행 결과 메시지
        """
        raise NotImplementedError


class HanwhaAdapter(DeviceAdapter):
    """한화 장비 어댑터 (SSH/REST)"""

    async def execute_command(
        self,
        device_info: Dict[str, Any],
        command: str,
        duration_seconds: int
    ) -> str:
        protocol = device_info["protocol"]

        if protocol == "SSH":
            return await self._execute_ssh(device_info, command, duration_seconds)
        elif protocol == "REST":
            return await self._execute_rest(device_info, command, duration_seconds)
        else:
            raise ValueError(f"지원하지 않는 프로토콜: {protocol}")

    async def _execute_ssh(self, device_info, command, duration_seconds):
        """SSH를 통한 제어 (Paramiko 사용)"""
        import paramiko

        ip = device_info["ip_address"]
        port = device_info["port"]
        username = device_info["credentials"].get("username")
        password = device_info["credentials"].get("password")

        # SSH 연결
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(ip, port=port, username=username, password=password, timeout=5)

            # 명령 매핑 (제조사 특화)
            cmd_map = {
                "start_recording": "wisenet-ctl recording start",
                "stop_recording": "wisenet-ctl recording stop",
                "open_camera_popup": "wisenet-ctl popup open",
                "door_open": f"wisenet-ctl door open --duration {duration_seconds}",
                "door_close": "wisenet-ctl door close",
                "alarm_clear": "wisenet-ctl alarm clear"
            }

            ssh_command = cmd_map.get(command)
            if not ssh_command:
                raise ValueError(f"알 수 없는 명령: {command}")

            stdin, stdout, stderr = ssh.exec_command(ssh_command)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                error = stderr.read().decode()
                raise RuntimeError(f"SSH 명령 실패: {error}")

            output = stdout.read().decode()
            logger.debug(f"SSH output: {output}")

            return f"한화 장비 제어 성공 (SSH): {command}"

        finally:
            ssh.close()

    async def _execute_rest(self, device_info, command, duration_seconds):
        """REST API를 통한 제어 (aiohttp 사용)"""
        import aiohttp

        ip = device_info["ip_address"]
        port = device_info["port"]
        api_key = device_info["credentials"].get("api_key")

        # REST API 엔드포인트 매핑
        endpoint_map = {
            "start_recording": "/api/v1/recording/start",
            "stop_recording": "/api/v1/recording/stop",
            "open_camera_popup": "/api/v1/camera/popup",
            "door_open": "/api/v1/access/door/open",
            "door_close": "/api/v1/access/door/close",
            "alarm_clear": "/api/v1/alarm/clear"
        }

        endpoint = endpoint_map.get(command)
        if not endpoint:
            raise ValueError(f"알 수 없는 명령: {command}")

        url = f"http://{ip}:{port}{endpoint}"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {"duration": duration_seconds}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=5) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"REST API 실패 ({resp.status}): {error_text}")

                return f"한화 장비 제어 성공 (REST): {command}"


class SupremaAdapter(DeviceAdapter):
    """슈프리마 장비 어댑터 (주로 ACU, REST API)"""

    async def execute_command(self, device_info, command, duration_seconds):
        import aiohttp

        ip = device_info["ip_address"]
        port = device_info["port"]
        api_key = device_info["credentials"].get("api_key")

        # 슈프리마 BioStar API
        endpoint_map = {
            "door_open": "/api/doors/open",
            "door_close": "/api/doors/close",
            "alarm_clear": "/api/events/clear"
        }

        endpoint = endpoint_map.get(command)
        if not endpoint:
            raise ValueError(f"슈프리마 ACU는 {command} 명령을 지원하지 않습니다.")

        url = f"https://{ip}:{port}{endpoint}"
        headers = {"X-API-Key": api_key}
        payload = {"duration": duration_seconds}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, ssl=False, timeout=5) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"슈프리마 API 실패: {error_text}")

                return f"슈프리마 ACU 제어 성공: {command}"


class GeneticAdapter(DeviceAdapter):
    """제네틱 장비 어댑터 (CCTV 전용)"""

    async def execute_command(self, device_info, command, duration_seconds):
        # 간단한 예시 (실제로는 ONVIF 프로토콜 사용)
        logger.info(f"[MOCK] 제네틱 {command} 실행")
        await asyncio.sleep(0.1)  # 네트워크 시뮬레이션
        return f"제네틱 CCTV 제어 성공: {command}"


class MercuryAdapter(DeviceAdapter):
    """머큐리 장비 어댑터 (ACU 전용)"""

    async def execute_command(self, device_info, command, duration_seconds):
        # 간단한 예시
        logger.info(f"[MOCK] 머큐리 {command} 실행")
        await asyncio.sleep(0.1)
        return f"머큐리 ACU 제어 성공: {command}"
