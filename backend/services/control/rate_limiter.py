"""
Rate Limiter for Control API

인증 시도 및 API 요청에 대한 속도 제한을 구현합니다.

주요 기능:
- 인증 시도: 5회/5분, 초과 시 15분 잠금
- API 요청: 100회/분
- IP 기반 및 장치 기반 제한
"""

import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """제한 유형"""
    AUTH_ATTEMPT = "auth_attempt"  # 인증 시도
    API_REQUEST = "api_request"  # 일반 API 요청
    CREDENTIAL_ACCESS = "credential_access"  # 인증정보 접근
    DEVICE_CONTROL = "device_control"  # 장치 제어


@dataclass
class RateLimitConfig:
    """속도 제한 설정"""
    max_attempts: int  # 최대 시도 횟수
    window_seconds: int  # 시간 창 (초)
    lockout_seconds: int = 0  # 잠금 시간 (초), 0이면 잠금 없음


# 기본 속도 제한 설정
DEFAULT_LIMITS: Dict[RateLimitType, RateLimitConfig] = {
    RateLimitType.AUTH_ATTEMPT: RateLimitConfig(
        max_attempts=5,
        window_seconds=300,  # 5분
        lockout_seconds=900,  # 15분 잠금
    ),
    RateLimitType.API_REQUEST: RateLimitConfig(
        max_attempts=100,
        window_seconds=60,  # 1분
        lockout_seconds=0,  # 잠금 없음
    ),
    RateLimitType.CREDENTIAL_ACCESS: RateLimitConfig(
        max_attempts=10,
        window_seconds=60,  # 1분
        lockout_seconds=300,  # 5분 잠금
    ),
    RateLimitType.DEVICE_CONTROL: RateLimitConfig(
        max_attempts=30,
        window_seconds=60,  # 1분
        lockout_seconds=0,  # 잠금 없음
    ),
}


@dataclass
class RateLimitState:
    """속도 제한 상태"""
    attempts: list = field(default_factory=list)  # 시도 타임스탬프 목록
    lockout_until: Optional[datetime] = None  # 잠금 해제 시간
    total_blocked: int = 0  # 총 차단 횟수


class RateLimiter:
    """
    속도 제한 관리자

    메모리 기반으로 요청 속도를 제한합니다.
    프로덕션에서는 Redis 기반으로 교체 권장.
    """

    def __init__(self, limits: Optional[Dict[RateLimitType, RateLimitConfig]] = None):
        self.limits = limits or DEFAULT_LIMITS.copy()
        # 키: (limit_type, identifier), 값: RateLimitState
        self._states: Dict[Tuple[RateLimitType, str], RateLimitState] = defaultdict(RateLimitState)
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        limit_type: RateLimitType,
        identifier: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        속도 제한 검사

        Args:
            limit_type: 제한 유형
            identifier: 식별자 (IP, device_id, user_id 등)

        Returns:
            (allowed, message): 허용 여부 및 메시지
        """
        async with self._lock:
            key = (limit_type, identifier)
            state = self._states[key]
            config = self.limits.get(limit_type)

            if not config:
                return True, None

            now = datetime.now()

            # 잠금 상태 확인
            if state.lockout_until:
                if now < state.lockout_until:
                    remaining = (state.lockout_until - now).total_seconds()
                    return False, f"잠금 상태입니다. {int(remaining)}초 후에 다시 시도하세요."
                else:
                    # 잠금 해제
                    state.lockout_until = None
                    state.attempts.clear()

            # 시간 창 내의 시도만 유지
            window_start = now - timedelta(seconds=config.window_seconds)
            state.attempts = [t for t in state.attempts if t > window_start]

            # 제한 확인
            if len(state.attempts) >= config.max_attempts:
                state.total_blocked += 1

                # 잠금 설정
                if config.lockout_seconds > 0:
                    state.lockout_until = now + timedelta(seconds=config.lockout_seconds)
                    logger.warning(
                        f"Rate limit exceeded - locked: type={limit_type.value}, "
                        f"id={identifier}, lockout={config.lockout_seconds}s"
                    )
                    return False, f"요청 한도 초과. {config.lockout_seconds}초 동안 잠금됩니다."

                logger.warning(
                    f"Rate limit exceeded: type={limit_type.value}, id={identifier}"
                )
                return False, f"요청 한도 초과. {config.window_seconds}초 후에 다시 시도하세요."

            # 시도 기록
            state.attempts.append(now)
            return True, None

    async def record_success(
        self,
        limit_type: RateLimitType,
        identifier: str,
    ):
        """
        성공적인 인증 후 상태 초기화 (AUTH_ATTEMPT 용)

        인증 성공 시 실패 카운트를 리셋합니다.
        """
        if limit_type != RateLimitType.AUTH_ATTEMPT:
            return

        async with self._lock:
            key = (limit_type, identifier)
            if key in self._states:
                self._states[key].attempts.clear()
                self._states[key].lockout_until = None

    async def get_remaining(
        self,
        limit_type: RateLimitType,
        identifier: str,
    ) -> Dict:
        """
        남은 요청 수 조회

        Returns:
            {
                "remaining": 남은 요청 수,
                "reset_after": 리셋까지 남은 초,
                "locked": 잠금 여부,
                "lockout_remaining": 잠금 해제까지 남은 초
            }
        """
        async with self._lock:
            key = (limit_type, identifier)
            state = self._states[key]
            config = self.limits.get(limit_type)

            if not config:
                return {"remaining": -1, "reset_after": 0, "locked": False}

            now = datetime.now()

            # 잠금 상태
            if state.lockout_until and now < state.lockout_until:
                remaining_lockout = (state.lockout_until - now).total_seconds()
                return {
                    "remaining": 0,
                    "reset_after": int(remaining_lockout),
                    "locked": True,
                    "lockout_remaining": int(remaining_lockout),
                }

            # 현재 시도 수 계산
            window_start = now - timedelta(seconds=config.window_seconds)
            current_attempts = len([t for t in state.attempts if t > window_start])
            remaining = max(0, config.max_attempts - current_attempts)

            # 리셋 시간 계산
            reset_after = 0
            if state.attempts:
                oldest = min(t for t in state.attempts if t > window_start)
                reset_after = int((oldest + timedelta(seconds=config.window_seconds) - now).total_seconds())
                reset_after = max(0, reset_after)

            return {
                "remaining": remaining,
                "reset_after": reset_after,
                "locked": False,
                "lockout_remaining": 0,
            }

    async def reset(
        self,
        limit_type: RateLimitType,
        identifier: str,
    ):
        """특정 식별자의 제한 상태 초기화"""
        async with self._lock:
            key = (limit_type, identifier)
            if key in self._states:
                del self._states[key]

    async def get_stats(self) -> Dict:
        """전체 속도 제한 통계"""
        async with self._lock:
            stats = {
                "total_identifiers": len(self._states),
                "by_type": defaultdict(lambda: {"active": 0, "locked": 0, "total_blocked": 0}),
            }

            now = datetime.now()
            for (limit_type, _), state in self._states.items():
                type_stats = stats["by_type"][limit_type.value]
                type_stats["active"] += 1
                if state.lockout_until and now < state.lockout_until:
                    type_stats["locked"] += 1
                type_stats["total_blocked"] += state.total_blocked

            stats["by_type"] = dict(stats["by_type"])
            return stats

    async def cleanup_expired(self):
        """만료된 상태 정리"""
        async with self._lock:
            now = datetime.now()
            expired_keys = []

            for key, state in self._states.items():
                limit_type, _ = key
                config = self.limits.get(limit_type)

                if not config:
                    continue

                # 잠금 해제 시간이 지난 경우
                if state.lockout_until and now >= state.lockout_until:
                    state.lockout_until = None
                    state.attempts.clear()

                # 시간 창이 지난 시도 제거
                window_start = now - timedelta(seconds=config.window_seconds)
                state.attempts = [t for t in state.attempts if t > window_start]

                # 비어있는 상태 제거
                if not state.attempts and not state.lockout_until:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._states[key]

            return len(expired_keys)


# 싱글톤 인스턴스
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Rate Limiter 싱글톤 인스턴스 반환"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# FastAPI 의존성용 함수들
async def check_auth_rate_limit(identifier: str) -> Tuple[bool, Optional[str]]:
    """인증 속도 제한 검사 (편의 함수)"""
    limiter = get_rate_limiter()
    return await limiter.check_rate_limit(RateLimitType.AUTH_ATTEMPT, identifier)


async def check_api_rate_limit(identifier: str) -> Tuple[bool, Optional[str]]:
    """API 속도 제한 검사 (편의 함수)"""
    limiter = get_rate_limiter()
    return await limiter.check_rate_limit(RateLimitType.API_REQUEST, identifier)


async def check_credential_rate_limit(identifier: str) -> Tuple[bool, Optional[str]]:
    """인증정보 접근 속도 제한 검사 (편의 함수)"""
    limiter = get_rate_limiter()
    return await limiter.check_rate_limit(RateLimitType.CREDENTIAL_ACCESS, identifier)


async def check_device_control_rate_limit(identifier: str) -> Tuple[bool, Optional[str]]:
    """장치 제어 속도 제한 검사 (편의 함수)"""
    limiter = get_rate_limiter()
    return await limiter.check_rate_limit(RateLimitType.DEVICE_CONTROL, identifier)
