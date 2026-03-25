"""
보안 감사 로깅 서비스

장치 제어 및 인증정보 관련 모든 활동을 로깅합니다.
- 인증정보 접근/변경 로깅
- 연결 이벤트 로깅
- 제어 명령 로깅
- 보안 이벤트 로깅
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """감사 이벤트 유형"""
    # 인증정보 관련
    CREDENTIAL_VIEW = "credential_view"
    CREDENTIAL_UPDATE = "credential_update"
    CREDENTIAL_TEST = "credential_test"
    CREDENTIAL_DECRYPT = "credential_decrypt"

    # 연결 관련
    CONNECTION_SUCCESS = "connection_success"
    CONNECTION_FAILURE = "connection_failure"
    CONNECTION_TIMEOUT = "connection_timeout"
    AUTH_FAILURE = "auth_failure"
    RECONNECT_ATTEMPT = "reconnect_attempt"

    # 장치 제어 관련
    DEVICE_REGISTER = "device_register"
    DEVICE_UPDATE = "device_update"
    DEVICE_DELETE = "device_delete"
    DEVICE_CONTROL = "device_control"

    # PTZ/녹화 제어
    PTZ_MOVE = "ptz_move"
    PTZ_PRESET = "ptz_preset"
    RECORDING_START = "recording_start"
    RECORDING_STOP = "recording_stop"

    # ACU 제어
    DOOR_UNLOCK = "door_unlock"
    DOOR_LOCK = "door_lock"

    # 보안 이벤트
    SECURITY_ALERT = "security_alert"
    ACCESS_DENIED = "access_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class AuditSeverity(str, Enum):
    """감사 이벤트 심각도"""
    DEBUG = "debug"      # 디버깅용 상세 정보
    INFO = "info"        # 일반 정보
    WARNING = "warning"  # 주의 필요
    ERROR = "error"      # 오류 발생
    CRITICAL = "critical"  # 심각한 보안 이벤트


@dataclass
class AuditEvent:
    """감사 이벤트 데이터"""
    id: str
    timestamp: str
    event_type: AuditEventType
    severity: AuditSeverity
    device_id: Optional[str]
    user_id: Optional[str]
    ip_address: Optional[str]
    action: str
    details: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "action": self.action,
            "details": self.details,
            "success": self.success,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=AuditEventType(data["event_type"]),
            severity=AuditSeverity(data["severity"]),
            device_id=data.get("device_id"),
            user_id=data.get("user_id"),
            ip_address=data.get("ip_address"),
            action=data["action"],
            details=data.get("details", {}),
            success=data.get("success", True),
            error_message=data.get("error_message"),
        )


class AuditLogger:
    """
    보안 감사 로거

    사용법:
        audit = AuditLogger()

        # 인증정보 접근 로깅
        await audit.log_credential_access(
            device_id="cam_001",
            action="update",
            user_id="admin",
            success=True
        )

        # 연결 이벤트 로깅
        await audit.log_connection_event(
            device_id="cam_001",
            event_type=AuditEventType.CONNECTION_SUCCESS,
            details={"latency_ms": 150}
        )

        # 감사 로그 조회
        logs = audit.get_logs(device_id="cam_001", limit=100)
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        max_logs_per_file: int = 10000,
        retention_days: int = 90,
    ):
        """
        감사 로거 초기화

        Args:
            storage_path: 로그 저장 경로
            max_logs_per_file: 파일당 최대 로그 수
            retention_days: 로그 보관 기간 (일)
        """
        if storage_path is None:
            storage_path = Path(__file__).parent.parent.parent.parent / "data" / "audit_logs"

        self._storage_path = storage_path
        self._max_logs_per_file = max_logs_per_file
        self._retention_days = retention_days

        # 메모리 캐시 (최근 로그 빠른 접근용)
        self._recent_logs: List[AuditEvent] = []
        self._max_cache_size = 1000

        # 현재 로그 파일
        self._current_log_count = 0

        self._ensure_storage()
        self._load_recent_logs()

    def _ensure_storage(self):
        """저장소 디렉토리 확보"""
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def _get_current_log_file(self) -> Path:
        """현재 날짜의 로그 파일 경로"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self._storage_path / f"audit_{date_str}.jsonl"

    def _load_recent_logs(self):
        """최근 로그 로드 (캐시용)"""
        log_file = self._get_current_log_file()
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # 마지막 N개만 로드
                    for line in lines[-self._max_cache_size:]:
                        try:
                            data = json.loads(line.strip())
                            event = AuditEvent.from_dict(data)
                            self._recent_logs.append(event)
                        except Exception:
                            pass
                logger.info(f"감사 로그 캐시 로드: {len(self._recent_logs)}개")
            except Exception as e:
                logger.error(f"감사 로그 로드 실패: {e}")

    def _write_log(self, event: AuditEvent):
        """로그 파일에 기록"""
        log_file = self._get_current_log_file()
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

            # 캐시 업데이트
            self._recent_logs.append(event)
            if len(self._recent_logs) > self._max_cache_size:
                self._recent_logs = self._recent_logs[-self._max_cache_size:]

        except Exception as e:
            logger.error(f"감사 로그 기록 실패: {e}")

    def _create_event(
        self,
        event_type: AuditEventType,
        action: str,
        device_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
    ) -> AuditEvent:
        """감사 이벤트 생성"""
        # 기본 심각도 결정
        if severity is None:
            if not success:
                severity = AuditSeverity.ERROR
            elif event_type in [
                AuditEventType.AUTH_FAILURE,
                AuditEventType.RATE_LIMIT_EXCEEDED,
                AuditEventType.ACCESS_DENIED,
            ]:
                severity = AuditSeverity.WARNING
            elif event_type in [AuditEventType.SECURITY_ALERT]:
                severity = AuditSeverity.CRITICAL
            else:
                severity = AuditSeverity.INFO

        return AuditEvent(
            id=str(uuid.uuid4())[:12],
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            severity=severity,
            device_id=device_id,
            user_id=user_id,
            ip_address=ip_address,
            action=action,
            details=details or {},
            success=success,
            error_message=error_message,
        )

    async def log_credential_access(
        self,
        device_id: str,
        action: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """
        인증정보 접근 로깅

        Args:
            device_id: 장치 ID
            action: "view", "update", "test", "decrypt"
            user_id: 사용자 ID
            ip_address: 접근 IP
            success: 성공 여부
            details: 추가 상세 정보
        """
        event_type_map = {
            "view": AuditEventType.CREDENTIAL_VIEW,
            "update": AuditEventType.CREDENTIAL_UPDATE,
            "test": AuditEventType.CREDENTIAL_TEST,
            "decrypt": AuditEventType.CREDENTIAL_DECRYPT,
        }

        event_type = event_type_map.get(action, AuditEventType.CREDENTIAL_VIEW)

        event = self._create_event(
            event_type=event_type,
            action=f"credential_{action}",
            device_id=device_id,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            success=success,
            error_message=error_message,
        )

        self._write_log(event)

        # 파이썬 로깅에도 기록
        log_msg = f"[AUDIT] Credential {action} - device={device_id}, user={user_id}, success={success}"
        if success:
            logger.info(log_msg)
        else:
            logger.warning(f"{log_msg}, error={error_message}")

    async def log_connection_event(
        self,
        device_id: str,
        event_type: AuditEventType,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """
        연결 이벤트 로깅

        Args:
            device_id: 장치 ID
            event_type: CONNECTION_SUCCESS, CONNECTION_FAILURE, AUTH_FAILURE 등
            details: 상세 정보 (latency_ms, attempts 등)
        """
        success = event_type in [
            AuditEventType.CONNECTION_SUCCESS,
            AuditEventType.RECONNECT_ATTEMPT,
        ]

        event = self._create_event(
            event_type=event_type,
            action=event_type.value,
            device_id=device_id,
            details=details,
            success=success,
            error_message=error_message,
        )

        self._write_log(event)

    async def log_device_control(
        self,
        device_id: str,
        action: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """
        장치 제어 명령 로깅

        Args:
            device_id: 장치 ID
            action: "ptz_move", "ptz_preset", "recording_start", "door_unlock" 등
            user_id: 사용자 ID
            details: 명령 상세 정보
        """
        event_type_map = {
            "ptz_move": AuditEventType.PTZ_MOVE,
            "ptz_preset": AuditEventType.PTZ_PRESET,
            "recording_start": AuditEventType.RECORDING_START,
            "recording_stop": AuditEventType.RECORDING_STOP,
            "door_unlock": AuditEventType.DOOR_UNLOCK,
            "door_lock": AuditEventType.DOOR_LOCK,
        }

        event_type = event_type_map.get(action, AuditEventType.DEVICE_CONTROL)

        event = self._create_event(
            event_type=event_type,
            action=action,
            device_id=device_id,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            success=success,
            error_message=error_message,
        )

        self._write_log(event)

        log_msg = f"[AUDIT] Device control - action={action}, device={device_id}, user={user_id}"
        logger.info(log_msg)

    async def log_security_event(
        self,
        event_type: AuditEventType,
        action: str,
        device_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """
        보안 이벤트 로깅 (접근 거부, 속도 제한 등)
        """
        event = self._create_event(
            event_type=event_type,
            action=action,
            device_id=device_id,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            success=False,
            error_message=error_message,
            severity=AuditSeverity.WARNING,
        )

        self._write_log(event)

        logger.warning(
            f"[AUDIT] Security event - type={event_type.value}, "
            f"device={device_id}, ip={ip_address}, error={error_message}"
        )

    def get_logs(
        self,
        device_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """
        감사 로그 조회

        Args:
            device_id: 특정 장치 필터
            event_type: 이벤트 유형 필터
            severity: 심각도 필터
            start_time: 시작 시간
            end_time: 종료 시간
            limit: 최대 결과 수
            offset: 건너뛸 결과 수

        Returns:
            필터링된 감사 이벤트 목록 (최신순)
        """
        # 캐시에서 필터링
        filtered = self._recent_logs.copy()

        if device_id:
            filtered = [e for e in filtered if e.device_id == device_id]

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if severity:
            filtered = [e for e in filtered if e.severity == severity]

        if start_time:
            start_str = start_time.isoformat()
            filtered = [e for e in filtered if e.timestamp >= start_str]

        if end_time:
            end_str = end_time.isoformat()
            filtered = [e for e in filtered if e.timestamp <= end_str]

        # 최신순 정렬
        filtered.sort(key=lambda e: e.timestamp, reverse=True)

        # 페이징
        return filtered[offset:offset + limit]

    def get_device_audit_summary(self, device_id: str) -> Dict[str, Any]:
        """
        장치별 감사 요약

        Returns:
            {
                "device_id": "cam_001",
                "total_events": 150,
                "by_type": {"connection_success": 100, ...},
                "by_severity": {"info": 140, ...},
                "last_event": {...},
                "security_events": 2
            }
        """
        logs = self.get_logs(device_id=device_id, limit=1000)

        by_type = {}
        by_severity = {}
        security_count = 0

        for log in logs:
            # 이벤트 유형별 집계
            type_name = log.event_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

            # 심각도별 집계
            sev_name = log.severity.value
            by_severity[sev_name] = by_severity.get(sev_name, 0) + 1

            # 보안 이벤트 카운트
            if log.severity in [AuditSeverity.WARNING, AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
                security_count += 1

        return {
            "device_id": device_id,
            "total_events": len(logs),
            "by_type": by_type,
            "by_severity": by_severity,
            "last_event": logs[0].to_dict() if logs else None,
            "security_events": security_count,
        }

    def cleanup_old_logs(self, days: Optional[int] = None):
        """오래된 로그 파일 정리"""
        if days is None:
            days = self._retention_days

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        removed = 0
        for log_file in self._storage_path.glob("audit_*.jsonl"):
            # 파일명에서 날짜 추출
            try:
                file_date = log_file.stem.split("_")[1]
                if file_date < cutoff_str:
                    log_file.unlink()
                    removed += 1
            except Exception:
                pass

        if removed:
            logger.info(f"오래된 감사 로그 {removed}개 삭제됨")


# 싱글톤 인스턴스
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """감사 로거 인스턴스 반환"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
