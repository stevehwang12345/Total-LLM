"""
연결 상태 관리 및 헬스체크 서비스

장치 연결 상태를 모니터링하고 자동 재연결/진단 기능을 제공합니다.
- 지수 백오프 재시도 로직
- 연결 진단 (네트워크, 포트, 인증, 프로토콜)
- 백그라운드 헬스체크
- 연결 이벤트 추적
"""

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
import httpx
from total_llm.core.config import get_settings

logger = logging.getLogger(__name__)


class DiagnosticResult(str, Enum):
    """진단 결과"""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    TIMEOUT = "timeout"


@dataclass
class ConnectionDiagnostics:
    """연결 진단 결과"""
    device_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 진단 항목별 결과
    network_reachable: DiagnosticResult = DiagnosticResult.SKIP
    port_open: DiagnosticResult = DiagnosticResult.SKIP
    http_accessible: DiagnosticResult = DiagnosticResult.SKIP
    auth_valid: DiagnosticResult = DiagnosticResult.SKIP
    onvif_available: DiagnosticResult = DiagnosticResult.SKIP

    # 상세 정보
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "results": {
                "network_reachable": self.network_reachable.value,
                "port_open": self.port_open.value,
                "http_accessible": self.http_accessible.value,
                "auth_valid": self.auth_valid.value,
                "onvif_available": self.onvif_available.value,
            },
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "recommendations": self.recommendations,
            "overall_status": self._overall_status(),
        }

    def _overall_status(self) -> str:
        results = [
            self.network_reachable,
            self.port_open,
            self.http_accessible,
            self.auth_valid,
        ]
        if all(r == DiagnosticResult.PASS for r in results):
            return "healthy"
        elif self.network_reachable == DiagnosticResult.FAIL:
            return "unreachable"
        elif self.auth_valid == DiagnosticResult.FAIL:
            return "auth_failed"
        else:
            return "degraded"


@dataclass
class ConnectionAttempt:
    """연결 시도 기록"""
    timestamp: str
    success: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ConnectionStats:
    """연결 통계"""
    device_id: str
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    last_error: Optional[str] = None
    avg_latency_ms: float = 0.0
    recent_attempts: List[ConnectionAttempt] = field(default_factory=list)

    def record_attempt(self, success: bool, latency_ms: Optional[float] = None, error: Optional[str] = None):
        """연결 시도 기록"""
        attempt = ConnectionAttempt(
            timestamp=datetime.now().isoformat(),
            success=success,
            latency_ms=latency_ms,
            error=error,
        )

        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
            self.last_success = attempt.timestamp
        else:
            self.failed_attempts += 1
            self.last_failure = attempt.timestamp
            self.last_error = error

        # 최근 시도 기록 (최대 20개)
        self.recent_attempts.append(attempt)
        if len(self.recent_attempts) > 20:
            self.recent_attempts.pop(0)

        # 평균 지연시간 업데이트
        latencies = [a.latency_ms for a in self.recent_attempts if a.latency_ms is not None]
        if latencies:
            self.avg_latency_ms = sum(latencies) / len(latencies)

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "success_rate": round(self.success_rate * 100, 1),
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "last_error": self.last_error,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "recent_attempts": [
                {"timestamp": a.timestamp, "success": a.success, "latency_ms": a.latency_ms}
                for a in self.recent_attempts[-5:]  # 최근 5개만
            ],
        }


class ConnectionHealthService:
    """
    장치 연결 상태 모니터링 서비스

    기능:
    - 지수 백오프 재시도
    - 연결 진단 (네트워크, 포트, 인증, 프로토콜)
    - 백그라운드 헬스체크
    - 연결 이벤트 추적
    """

    def __init__(
        self,
        max_retry_attempts: Optional[int] = None,
        initial_retry_delay: Optional[float] = None,
        max_retry_delay: Optional[float] = None,
        backoff_multiplier: float = 2.0,
        health_check_interval: int = 60,
    ):
        """
        Args:
            max_retry_attempts: 최대 재시도 횟수
            initial_retry_delay: 초기 재시도 대기 시간 (초)
            max_retry_delay: 최대 재시도 대기 시간 (초)
            backoff_multiplier: 백오프 배수
            health_check_interval: 헬스체크 간격 (초)
        """
        settings = get_settings()
        real_settings = settings.device_control.real
        security_settings = settings.security.device_control

        self.max_retry_attempts = max_retry_attempts or security_settings.max_retry_attempts
        self.initial_retry_delay = initial_retry_delay if initial_retry_delay is not None else float(real_settings.retry_delay)
        self.max_retry_delay = max_retry_delay if max_retry_delay is not None else float(real_settings.command_timeout * 2)
        self.backoff_multiplier = backoff_multiplier
        self.health_check_interval = health_check_interval
        self._connection_timeout = float(real_settings.connection_timeout)

        self._connection_stats: Dict[str, ConnectionStats] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

        # 이벤트 콜백
        self._on_connect_callbacks: List[Callable] = []
        self._on_disconnect_callbacks: List[Callable] = []

    def get_stats(self, device_id: str) -> ConnectionStats:
        """장치의 연결 통계 조회"""
        if device_id not in self._connection_stats:
            self._connection_stats[device_id] = ConnectionStats(device_id=device_id)
        return self._connection_stats[device_id]

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """모든 장치의 연결 통계 조회"""
        return {
            device_id: stats.to_dict()
            for device_id, stats in self._connection_stats.items()
        }

    async def connect_with_retry(
        self,
        device_id: str,
        connect_func: Callable,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        지수 백오프 재시도로 연결 시도

        Args:
            device_id: 장치 ID
            connect_func: 연결 함수 (async callable)
            *args, **kwargs: 연결 함수 인자

        Returns:
            {
                "success": bool,
                "attempts": int,
                "total_time": float,
                "last_error": Optional[str]
            }
        """
        stats = self.get_stats(device_id)
        delay = self.initial_retry_delay
        last_error = None
        start_time = time.time()

        for attempt in range(1, self.max_retry_attempts + 1):
            try:
                logger.info(f"[{device_id}] 연결 시도 {attempt}/{self.max_retry_attempts}")

                attempt_start = time.time()
                result = await connect_func(*args, **kwargs)
                latency = (time.time() - attempt_start) * 1000

                if result:
                    stats.record_attempt(success=True, latency_ms=latency)
                    logger.info(f"[{device_id}] 연결 성공 (시도 {attempt}, 지연 {latency:.0f}ms)")

                    # 연결 성공 콜백
                    for callback in self._on_connect_callbacks:
                        try:
                            await callback(device_id)
                        except Exception as e:
                            logger.error(f"연결 콜백 오류: {e}")

                    return {
                        "success": True,
                        "attempts": attempt,
                        "total_time": time.time() - start_time,
                        "latency_ms": latency,
                    }
                else:
                    raise ConnectionError("Connection returned False")

            except Exception as e:
                last_error = str(e)
                stats.record_attempt(success=False, error=last_error)
                logger.warning(f"[{device_id}] 연결 실패 (시도 {attempt}): {last_error}")

                if attempt < self.max_retry_attempts:
                    logger.info(f"[{device_id}] {delay:.1f}초 후 재시도...")
                    await asyncio.sleep(delay)
                    delay = min(delay * self.backoff_multiplier, self.max_retry_delay)

        # 모든 시도 실패
        logger.error(f"[{device_id}] 연결 실패 (최대 시도 횟수 초과)")

        # 연결 실패 콜백
        for callback in self._on_disconnect_callbacks:
            try:
                await callback(device_id, last_error)
            except Exception as e:
                logger.error(f"연결 해제 콜백 오류: {e}")

        return {
            "success": False,
            "attempts": self.max_retry_attempts,
            "total_time": time.time() - start_time,
            "last_error": last_error,
        }

    async def diagnose_connection(
        self,
        device_id: str,
        ip: str,
        port: int = 80,
        username: Optional[str] = None,
        password: Optional[str] = None,
        check_onvif: bool = True,
    ) -> ConnectionDiagnostics:
        """
        장치 연결 진단

        순차적으로 다음 항목을 검사합니다:
        1. 네트워크 도달 가능성 (ping/socket)
        2. 포트 열림 여부
        3. HTTP 접근 가능성
        4. 인증 유효성
        5. ONVIF 지원 여부 (선택)

        Args:
            device_id: 장치 ID
            ip: 장치 IP 주소
            port: HTTP 포트 (기본 80)
            username: 인증 사용자명
            password: 인증 비밀번호
            check_onvif: ONVIF 검사 여부

        Returns:
            ConnectionDiagnostics 객체
        """
        diag = ConnectionDiagnostics(device_id=device_id)
        start_time = time.time()

        # 1. 네트워크 도달 가능성
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._connection_timeout)
            result = sock.connect_ex((ip, port))
            sock.close()

            if result == 0:
                diag.network_reachable = DiagnosticResult.PASS
                diag.port_open = DiagnosticResult.PASS
            else:
                diag.network_reachable = DiagnosticResult.FAIL
                diag.port_open = DiagnosticResult.FAIL
                diag.error_message = f"포트 {port}에 연결할 수 없습니다"
                diag.recommendations.append(f"장치가 네트워크에 연결되어 있는지 확인하세요")
                diag.recommendations.append(f"방화벽 설정을 확인하세요")
                return diag

        except socket.timeout:
            diag.network_reachable = DiagnosticResult.TIMEOUT
            diag.error_message = "네트워크 연결 시간 초과"
            diag.recommendations.append("네트워크 연결 상태를 확인하세요")
            return diag
        except Exception as e:
            diag.network_reachable = DiagnosticResult.FAIL
            diag.error_message = str(e)
            return diag

        # 2. HTTP 접근 가능성
        try:
            async with httpx.AsyncClient(timeout=self._connection_timeout) as client:
                response = await client.get(f"http://{ip}:{port}/")
                if response.status_code in (200, 301, 302, 401, 403):
                    diag.http_accessible = DiagnosticResult.PASS
                else:
                    diag.http_accessible = DiagnosticResult.FAIL
                    diag.recommendations.append(f"HTTP 응답 코드: {response.status_code}")
        except httpx.TimeoutException:
            diag.http_accessible = DiagnosticResult.TIMEOUT
            diag.recommendations.append("HTTP 응답 시간이 너무 깁니다")
        except Exception as e:
            diag.http_accessible = DiagnosticResult.FAIL
            diag.error_message = str(e)

        # 3. 인증 유효성
        if username and password:
            try:
                async with httpx.AsyncClient(timeout=self._connection_timeout) as client:
                    # Digest Auth 시도
                    auth = httpx.DigestAuth(username, password)
                    response = await client.get(f"http://{ip}:{port}/", auth=auth)

                    if response.status_code == 200:
                        diag.auth_valid = DiagnosticResult.PASS
                    elif response.status_code == 401:
                        diag.auth_valid = DiagnosticResult.FAIL
                        diag.error_message = "인증 실패"
                        diag.recommendations.append("사용자명/비밀번호를 확인하세요")
                    else:
                        diag.auth_valid = DiagnosticResult.PASS  # 다른 응답도 인증 성공으로 간주

            except Exception as e:
                diag.auth_valid = DiagnosticResult.FAIL
                diag.recommendations.append(f"인증 테스트 실패: {str(e)}")
        else:
            diag.auth_valid = DiagnosticResult.SKIP
            diag.recommendations.append("인증 정보가 설정되지 않았습니다")

        # 4. ONVIF 지원 여부
        if check_onvif:
            try:
                async with httpx.AsyncClient(timeout=self._connection_timeout) as client:
                    # ONVIF 서비스 URL 확인
                    response = await client.get(
                        f"http://{ip}:{port}/onvif/device_service",
                        follow_redirects=True,
                    )
                    if response.status_code in (200, 400, 401, 500):
                        # 400/500도 ONVIF가 있다는 의미
                        diag.onvif_available = DiagnosticResult.PASS
                    else:
                        diag.onvif_available = DiagnosticResult.FAIL
            except Exception:
                diag.onvif_available = DiagnosticResult.FAIL

        # 지연 시간 계산
        diag.latency_ms = (time.time() - start_time) * 1000

        return diag

    async def start_health_monitor(
        self,
        devices: List[Dict[str, Any]],
        check_func: Callable,
    ):
        """
        백그라운드 헬스체크 시작

        Args:
            devices: 모니터링할 장치 목록 [{"id": "...", "ip": "...", ...}, ...]
            check_func: 상태 확인 함수 async (device_id) -> bool
        """
        if self._running:
            logger.warning("헬스 모니터가 이미 실행 중입니다")
            return

        self._running = True
        logger.info(f"헬스 모니터 시작 (간격: {self.health_check_interval}초, 장치: {len(devices)}개)")

        async def monitor_loop():
            while self._running:
                try:
                    for device in devices:
                        device_id = device.get("id")
                        if not device_id:
                            continue

                        try:
                            success = await check_func(device_id)
                            stats = self.get_stats(device_id)
                            stats.record_attempt(success=success)

                            if not success:
                                logger.warning(f"[{device_id}] 헬스체크 실패")

                        except Exception as e:
                            logger.error(f"[{device_id}] 헬스체크 오류: {e}")
                            self.get_stats(device_id).record_attempt(success=False, error=str(e))

                    await asyncio.sleep(self.health_check_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"헬스 모니터 오류: {e}")
                    await asyncio.sleep(5)

        self._health_check_task = asyncio.create_task(monitor_loop())

    async def stop_health_monitor(self):
        """백그라운드 헬스체크 중지"""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        logger.info("헬스 모니터 중지됨")

    def on_connect(self, callback: Callable):
        """연결 성공 이벤트 콜백 등록"""
        self._on_connect_callbacks.append(callback)

    def on_disconnect(self, callback: Callable):
        """연결 해제 이벤트 콜백 등록"""
        self._on_disconnect_callbacks.append(callback)


# 싱글톤 인스턴스
_health_service: Optional[ConnectionHealthService] = None


def get_health_service() -> ConnectionHealthService:
    """연결 헬스 서비스 인스턴스 반환"""
    global _health_service
    if _health_service is None:
        _health_service = ConnectionHealthService()
    return _health_service
