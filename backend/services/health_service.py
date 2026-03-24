#!/usr/bin/env python3
"""
Health Check Service

확장된 시스템 헬스 체크
- 의존성 상태 체크 (Qdrant, Redis, PostgreSQL, vLLM)
- 리소스 사용량 모니터링
- 상세 진단 정보
"""

import logging
import asyncio
import time
import os
import psutil
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """헬스 상태"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthService:
    """
    시스템 헬스 체크 서비스

    체크 항목:
    1. 내부 서비스 (RAG, Device Control 등)
    2. 외부 의존성 (Qdrant, Redis, PostgreSQL)
    3. AI 모델 서버 (vLLM, VLM)
    4. 시스템 리소스 (CPU, Memory, Disk)
    """

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        vllm_url: str = "http://localhost:9000",
        vlm_url: str = "http://localhost:9001"
    ):
        self.qdrant_url = qdrant_url
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.vllm_url = vllm_url
        self.vlm_url = vlm_url

        self._start_time = datetime.utcnow()

    async def get_full_health(self, app_state) -> Dict[str, Any]:
        """
        전체 헬스 체크

        Args:
            app_state: FastAPI app.state

        Returns:
            상세 헬스 정보
        """
        start = time.perf_counter()

        # Parallel health checks
        checks = await asyncio.gather(
            self._check_qdrant(),
            self._check_redis(),
            self._check_vllm(),
            self._check_vlm(),
            return_exceptions=True
        )

        qdrant_health, redis_health, vllm_health, vlm_health = checks

        # Handle exceptions
        for i, check in enumerate(checks):
            if isinstance(check, Exception):
                checks[i] = {"status": HealthStatus.UNHEALTHY, "error": str(check)}

        qdrant_health, redis_health, vllm_health, vlm_health = checks

        # Internal services check
        internal_services = self._check_internal_services(app_state)

        # System resources
        system_resources = self._get_system_resources()

        # Determine overall status
        all_statuses = [
            qdrant_health.get("status"),
            internal_services.get("database", {}).get("status"),
            internal_services.get("rag", {}).get("status"),
        ]

        if all(s == HealthStatus.HEALTHY for s in all_statuses if s):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in all_statuses if s):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        duration_ms = (time.perf_counter() - start) * 1000

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "check_duration_ms": round(duration_ms, 2),
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "dependencies": {
                "qdrant": qdrant_health,
                "redis": redis_health,
                "vllm": vllm_health,
                "vlm": vlm_health,
            },
            "services": internal_services,
            "system": system_resources,
        }

    async def get_simple_health(self, app_state) -> Dict[str, Any]:
        """
        간단한 헬스 체크 (빠른 응답용)
        """
        services = {
            "database": app_state.db_pool is not None,
            "rag": app_state.rag_service is not None,
            "device_registry": app_state.device_registry is not None,
            "llm": app_state.llm_client is not None,
        }

        all_healthy = all(services.values())

        return {
            "status": HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED,
            "services": services,
        }

    async def _check_qdrant(self) -> Dict[str, Any]:
        """Qdrant 벡터 DB 체크"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.qdrant_url}/healthz")

                if response.status_code == 200:
                    # Get collection info
                    collections_response = await client.get(f"{self.qdrant_url}/collections")
                    collections_data = collections_response.json()
                    collection_count = len(collections_data.get("result", {}).get("collections", []))

                    return {
                        "status": HealthStatus.HEALTHY,
                        "url": self.qdrant_url,
                        "collections": collection_count,
                    }
                else:
                    return {
                        "status": HealthStatus.UNHEALTHY,
                        "url": self.qdrant_url,
                        "error": f"HTTP {response.status_code}",
                    }

        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "url": self.qdrant_url,
                "error": str(e),
            }

    async def _check_redis(self) -> Dict[str, Any]:
        """Redis 캐시 체크"""
        try:
            import redis.asyncio as redis

            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                socket_timeout=3.0
            )

            await client.ping()
            info = await client.info("memory")
            await client.close()

            return {
                "status": HealthStatus.HEALTHY,
                "host": f"{self.redis_host}:{self.redis_port}",
                "memory_used": info.get("used_memory_human", "N/A"),
            }

        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,  # Redis is optional
                "host": f"{self.redis_host}:{self.redis_port}",
                "error": str(e),
            }

    async def _check_vllm(self) -> Dict[str, Any]:
        """vLLM (Text LLM) 서버 체크"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.vllm_url}/v1/models")

                if response.status_code == 200:
                    data = response.json()
                    models = [m["id"] for m in data.get("data", [])]

                    return {
                        "status": HealthStatus.HEALTHY,
                        "url": self.vllm_url,
                        "models": models,
                    }
                else:
                    return {
                        "status": HealthStatus.UNHEALTHY,
                        "url": self.vllm_url,
                        "error": f"HTTP {response.status_code}",
                    }

        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "url": self.vllm_url,
                "error": str(e),
            }

    async def _check_vlm(self) -> Dict[str, Any]:
        """VLM (Vision LLM) 서버 체크"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.vlm_url}/v1/models")

                if response.status_code == 200:
                    data = response.json()
                    models = [m["id"] for m in data.get("data", [])]

                    return {
                        "status": HealthStatus.HEALTHY,
                        "url": self.vlm_url,
                        "models": models,
                    }
                else:
                    return {
                        "status": HealthStatus.DEGRADED,
                        "url": self.vlm_url,
                        "error": f"HTTP {response.status_code}",
                    }

        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,  # VLM is optional
                "url": self.vlm_url,
                "error": str(e),
            }

    def _check_internal_services(self, app_state) -> Dict[str, Any]:
        """내부 서비스 상태 체크"""
        return {
            "database": {
                "status": HealthStatus.HEALTHY if app_state.db_pool else HealthStatus.UNHEALTHY,
                "initialized": app_state.db_pool is not None,
            },
            "rag": {
                "status": HealthStatus.HEALTHY if app_state.rag_service else HealthStatus.UNHEALTHY,
                "initialized": app_state.rag_service is not None,
            },
            "device_registry": {
                "status": HealthStatus.HEALTHY if app_state.device_registry else HealthStatus.DEGRADED,
                "initialized": app_state.device_registry is not None,
            },
            "device_control": {
                "status": HealthStatus.HEALTHY if app_state.device_control else HealthStatus.DEGRADED,
                "initialized": app_state.device_control is not None,
            },
            "command_orchestrator": {
                "status": HealthStatus.HEALTHY if app_state.command_orchestrator else HealthStatus.DEGRADED,
                "initialized": app_state.command_orchestrator is not None,
            },
            "llm_client": {
                "status": HealthStatus.HEALTHY if app_state.llm_client else HealthStatus.UNHEALTHY,
                "initialized": app_state.llm_client is not None,
            },
            "websocket": {
                "status": HealthStatus.HEALTHY if getattr(app_state, 'ws_broadcaster', None) else HealthStatus.DEGRADED,
                "initialized": getattr(app_state, 'ws_broadcaster', None) is not None,
            },
            "cache": {
                "status": HealthStatus.HEALTHY if getattr(app_state, 'cache_service', None) else HealthStatus.DEGRADED,
                "initialized": getattr(app_state, 'cache_service', None) is not None,
            },
            "conversation": {
                "status": HealthStatus.HEALTHY if getattr(app_state, 'conversation_service', None) else HealthStatus.DEGRADED,
                "initialized": getattr(app_state, 'conversation_service', None) is not None,
            },
        }

    def _get_system_resources(self) -> Dict[str, Any]:
        """시스템 리소스 정보"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu": {
                    "percent": cpu_percent,
                    "cores": psutil.cpu_count(),
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "percent": round(disk.percent, 1),
                },
            }

        except Exception as e:
            logger.warning(f"Failed to get system resources: {e}")
            return {"error": str(e)}


# Singleton instance
_health_service: Optional[HealthService] = None


def get_health_service(
    qdrant_url: str = "http://localhost:6333",
    redis_host: str = "localhost",
    redis_port: int = 6379,
    vllm_url: str = "http://localhost:9000",
    vlm_url: str = "http://localhost:9001"
) -> HealthService:
    """HealthService 싱글톤 반환"""
    global _health_service
    if _health_service is None:
        _health_service = HealthService(
            qdrant_url=qdrant_url,
            redis_host=redis_host,
            redis_port=redis_port,
            vllm_url=vllm_url,
            vlm_url=vlm_url
        )
    return _health_service
