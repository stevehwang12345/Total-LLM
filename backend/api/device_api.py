#!/usr/bin/env python3
"""
Device Management API

장비 등록, 조회, 제어 API
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])


# ============================================
# Request/Response Models
# ============================================

class Device(BaseModel):
    """장비 모델"""
    device_id: str
    device_type: str
    manufacturer: str
    ip_address: str
    port: int
    protocol: str
    location: Optional[str] = None
    zone: Optional[str] = None
    status: str
    last_health_check: Optional[str] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    uptime_seconds: Optional[int] = None


class DeviceRegisterRequest(BaseModel):
    """장비 등록 요청"""
    device_type: str = Field(..., description="CCTV | ACU")
    manufacturer: str = Field(..., description="한화 | 슈프리마 | 제네틱 | 머큐리")
    ip_address: str = Field(..., description="IP 주소")
    port: int = Field(default=22, description="포트 번호")
    protocol: str = Field(..., description="SSH | REST | SNMP")
    location: Optional[str] = Field(None, description="설치 장소")
    zone: Optional[str] = Field(None, description="보안 구역")
    username: Optional[str] = Field(None, description="인증 사용자명")
    password: Optional[str] = Field(None, description="인증 비밀번호")
    api_key: Optional[str] = Field(None, description="API 키")


class DeviceControlRequest(BaseModel):
    """장비 제어 요청"""
    device_id: str = Field(..., description="장비 ID")
    command: str = Field(..., description="제어 명령")
    duration_seconds: int = Field(default=5, description="지속 시간 (초)")
    reason: str = Field(default="사용자 요청", description="제어 사유")


class DeviceControlResponse(BaseModel):
    """장비 제어 응답"""
    control_id: int
    device_id: str
    command: str
    status: str
    result: str
    rollback_executed: bool
    execution_time_ms: int


# ============================================
# Global Variables (main.py에서 주입)
# ============================================

device_registry = None
device_control = None


def set_device_registry(registry):
    """Device Registry 설정"""
    global device_registry
    device_registry = registry


def set_device_control(control):
    """Device Control 설정"""
    global device_control
    device_control = control


# ============================================
# API Endpoints
# ============================================

@router.get("", response_model=List[Device])
async def get_devices(
    device_type: str = Query(default="all", description="장비 유형 필터 (CCTV, ACU, all)"),
    status_filter: str = Query(default="all", description="상태 필터 (online, offline, all)")
):
    """
    장비 목록 조회

    Args:
        device_type: 장비 유형 필터
        status_filter: 상태 필터

    Returns:
        장비 리스트
    """
    if not device_registry:
        raise HTTPException(status_code=500, detail="Device registry not initialized")

    logger.info(f"📋 Fetching devices: type={device_type}, status={status_filter}")

    try:
        devices = await device_registry.list_devices(
            device_type=device_type,
            status_filter=status_filter
        )

        return devices

    except Exception as e:
        logger.error(f"❌ Failed to fetch devices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{device_id}", response_model=Device)
async def get_device(device_id: str):
    """
    특정 장비 조회

    Args:
        device_id: 장비 ID

    Returns:
        장비 상세 정보
    """
    if not device_registry:
        raise HTTPException(status_code=500, detail="Device registry not initialized")

    try:
        devices = await device_registry.list_devices()
        device = next((d for d in devices if d["device_id"] == device_id), None)

        if not device:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

        return device

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{device_id}/status", response_model=Device)
async def get_device_status(device_id: str):
    """
    장비 상태 조회

    Args:
        device_id: 장비 ID

    Returns:
        장비 상태 정보
    """
    if not device_registry:
        raise HTTPException(status_code=500, detail="Device registry not initialized")

    logger.info(f"📊 Getting device status: {device_id}")

    try:
        status = await device_registry.get_device_status(device_id)
        return status

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to get status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register", response_model=Device)
async def register_device(request: DeviceRegisterRequest):
    """
    장비 등록

    Args:
        request: 장비 등록 정보

    Returns:
        등록된 장비 정보
    """
    if not device_registry:
        raise HTTPException(status_code=500, detail="Device registry not initialized")

    logger.info(f"📝 Registering device: {request.device_type} ({request.manufacturer}) @ {request.ip_address}")

    try:
        device = await device_registry.register_device(
            device_type=request.device_type,
            manufacturer=request.manufacturer,
            ip_address=request.ip_address,
            port=request.port,
            protocol=request.protocol,
            location=request.location,
            zone=request.zone,
            credentials={
                "username": request.username,
                "password": request.password,
                "api_key": request.api_key
            },
            registered_by="web_user"
        )

        return device

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to register device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/control", response_model=DeviceControlResponse)
async def control_device_endpoint(request: DeviceControlRequest):
    """
    장비 제어

    Args:
        request: 제어 명령

    Returns:
        제어 결과
    """
    if not device_control:
        raise HTTPException(status_code=500, detail="Device control not initialized")

    logger.info(f"🎛️ Controlling device: {request.device_id} → {request.command}")

    try:
        result = await device_control.execute_command(
            device_id=request.device_id,
            command=request.command,
            duration_seconds=request.duration_seconds,
            reason=request.reason,
            executed_by="web_user"
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to control device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commands/available")
async def get_available_commands(device_type: Optional[str] = Query(default=None)):
    """
    사용 가능한 제어 명령 조회

    Args:
        device_type: 장비 유형 (CCTV, ACU)

    Returns:
        {
            "CCTV": ["start_recording", "stop_recording", "open_camera_popup"],
            "ACU": ["door_open", "door_close", "alarm_clear"]
        }
    """
    commands = {
        "CCTV": [
            {"command": "start_recording", "description": "녹화 시작"},
            {"command": "stop_recording", "description": "녹화 중지"},
            {"command": "open_camera_popup", "description": "카메라 단독창 팝업"}
        ],
        "ACU": [
            {"command": "door_open", "description": "도어 열기", "supports_rollback": True},
            {"command": "door_close", "description": "도어 닫기", "supports_rollback": True},
            {"command": "alarm_clear", "description": "알람 해제"}
        ]
    }

    if device_type:
        if device_type not in commands:
            raise HTTPException(status_code=400, detail=f"Invalid device type: {device_type}")
        return {device_type: commands[device_type]}

    return commands


@router.get("/health")
async def health_check():
    """
    헬스 체크

    Returns:
        {"status": "healthy", "registry": bool, "control": bool}
    """
    return {
        "status": "healthy" if (device_registry and device_control) else "not_initialized",
        "registry": device_registry is not None,
        "control": device_control is not None
    }
