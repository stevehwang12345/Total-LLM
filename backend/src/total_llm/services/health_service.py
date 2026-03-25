#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
import psutil

from total_llm.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthService:
    def __init__(self, settings: Optional[Settings] = None, timeout_seconds: float = 5.0):
        self.settings = settings or get_settings()
        self.timeout_seconds = timeout_seconds
        self._start_time = datetime.utcnow()

        self.qdrant_url = f"http://{self.settings.qdrant.host}:{self.settings.qdrant.port}"
        self.redis_host = self.settings.redis.host
        self.redis_port = self.settings.redis.port
        self.llm_url = self.settings.llm.base_url.rstrip("/")
        self.vlm_url = self.settings.vlm.base_url.rstrip("/")

    async def get_full_health(self, app_state) -> dict[str, Any]:
        start = time.perf_counter()

        checks = await asyncio.gather(
            self._check_database(app_state),
            self._check_qdrant(),
            self._check_redis(),
            self._check_llm(),
            self._check_vlm(),
            return_exceptions=True,
        )

        names = ["database", "qdrant", "redis", "llm", "vlm"]
        dependencies: dict[str, dict[str, Any]] = {}
        for name, result in zip(names, checks):
            if isinstance(result, BaseException):
                dependencies[name] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": str(result),
                }
            else:
                dependencies[name] = result

        internal_services = self._check_internal_services(app_state)
        system_resources = self._get_system_resources()
        overall_status = self._determine_overall_status(dependencies)
        duration_ms = (time.perf_counter() - start) * 1000

        healthy_count = sum(1 for dep in dependencies.values() if dep.get("status") == HealthStatus.HEALTHY)

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "check_duration_ms": round(duration_ms, 2),
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": self.settings.environment,
            "summary": {
                "healthy_dependencies": healthy_count,
                "total_dependencies": len(dependencies),
            },
            "dependencies": dependencies,
            "services": internal_services,
            "system": system_resources,
        }

    async def get_simple_health(self, app_state) -> dict[str, Any]:
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

    def _determine_overall_status(self, dependencies: dict[str, dict[str, Any]]) -> HealthStatus:
        required = ["database", "qdrant", "llm"]
        optional = ["redis", "vlm"]

        if any(dependencies[name].get("status") == HealthStatus.UNHEALTHY for name in required):
            return HealthStatus.UNHEALTHY

        if any(dependencies[name].get("status") != HealthStatus.HEALTHY for name in required + optional):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    async def _check_database(self, app_state) -> dict[str, Any]:
        if not getattr(app_state, "db_pool", None):
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "Database pool is not initialized",
            }

        started = time.perf_counter()
        try:
            await asyncio.wait_for(self._probe_database(app_state), timeout=self.timeout_seconds)
            return {
                "status": HealthStatus.HEALTHY,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "host": f"{self.settings.database.host}:{self.settings.database.port}",
                "database": self.settings.database.database,
            }
        except asyncio.TimeoutError:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"Timeout after {self.timeout_seconds:.1f}s",
                "host": f"{self.settings.database.host}:{self.settings.database.port}",
                "database": self.settings.database.database,
            }
        except Exception as exc:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": str(exc),
                "host": f"{self.settings.database.host}:{self.settings.database.port}",
                "database": self.settings.database.database,
            }

    async def _probe_database(self, app_state) -> None:
        async with app_state.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

    async def _check_qdrant(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.qdrant_url}/healthz")
                if response.status_code != 200:
                    return {
                        "status": HealthStatus.UNHEALTHY,
                        "url": self.qdrant_url,
                        "error": f"HTTP {response.status_code}",
                    }

                collections_response = await client.get(f"{self.qdrant_url}/collections")
                collection_count = 0
                if collections_response.status_code == 200:
                    payload = collections_response.json()
                    collection_count = len(payload.get("result", {}).get("collections", []))

                return {
                    "status": HealthStatus.HEALTHY,
                    "url": self.qdrant_url,
                    "collections": collection_count,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                }
        except Exception as exc:
            return {
                "status": HealthStatus.UNHEALTHY,
                "url": self.qdrant_url,
                "error": str(exc),
            }

    async def _check_redis(self) -> dict[str, Any]:
        import redis.asyncio as redis

        started = time.perf_counter()
        client: Optional[redis.Redis] = None
        try:
            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                socket_timeout=self.timeout_seconds,
                socket_connect_timeout=self.timeout_seconds,
            )
            await asyncio.wait_for(client.ping(), timeout=self.timeout_seconds)
            info = await asyncio.wait_for(client.info("memory"), timeout=self.timeout_seconds)
            return {
                "status": HealthStatus.HEALTHY,
                "host": f"{self.redis_host}:{self.redis_port}",
                "memory_used": info.get("used_memory_human", "N/A"),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            return {
                "status": HealthStatus.DEGRADED,
                "host": f"{self.redis_host}:{self.redis_port}",
                "error": str(exc),
            }
        finally:
            if client is not None:
                await client.close()

    async def _check_llm(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.llm_url}/models")
                if response.status_code != 200:
                    return {
                        "status": HealthStatus.UNHEALTHY,
                        "url": self.llm_url,
                        "error": f"HTTP {response.status_code}",
                    }

                data = response.json()
                return {
                    "status": HealthStatus.HEALTHY,
                    "url": self.llm_url,
                    "models": [m.get("id") for m in data.get("data", [])],
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                }
        except Exception as exc:
            return {
                "status": HealthStatus.UNHEALTHY,
                "url": self.llm_url,
                "error": str(exc),
            }

    async def _check_vlm(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.vlm_url}/models")
                if response.status_code != 200:
                    return {
                        "status": HealthStatus.DEGRADED,
                        "url": self.vlm_url,
                        "error": f"HTTP {response.status_code}",
                    }

                data = response.json()
                return {
                    "status": HealthStatus.HEALTHY,
                    "url": self.vlm_url,
                    "models": [m.get("id") for m in data.get("data", [])],
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                }
        except Exception as exc:
            return {
                "status": HealthStatus.DEGRADED,
                "url": self.vlm_url,
                "error": str(exc),
            }

    def _check_internal_services(self, app_state) -> dict[str, Any]:
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
                "status": HealthStatus.HEALTHY if getattr(app_state, "ws_broadcaster", None) else HealthStatus.DEGRADED,
                "initialized": getattr(app_state, "ws_broadcaster", None) is not None,
            },
            "cache": {
                "status": HealthStatus.HEALTHY if getattr(app_state, "cache_service", None) else HealthStatus.DEGRADED,
                "initialized": getattr(app_state, "cache_service", None) is not None,
            },
            "conversation": {
                "status": HealthStatus.HEALTHY if getattr(app_state, "conversation_service", None) else HealthStatus.DEGRADED,
                "initialized": getattr(app_state, "conversation_service", None) is not None,
            },
        }

    def _get_system_resources(self) -> dict[str, Any]:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
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
        except Exception as exc:
            logger.warning("Failed to get system resources: %s", exc)
            return {"error": str(exc)}


_health_service: Optional[HealthService] = None


def get_health_service(
    settings: Optional[Settings] = None,
    timeout_seconds: float = 5.0,
) -> HealthService:
    global _health_service
    if _health_service is None:
        _health_service = HealthService(settings=settings, timeout_seconds=timeout_seconds)
    return _health_service
