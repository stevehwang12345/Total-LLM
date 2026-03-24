"""
외부 시스템 제어 API

ACU(출입통제) 및 CCTV(영상감시) 시스템 제어를 위한 REST API 엔드포인트입니다.
자연어 명령 처리 및 직접 함수 호출을 지원합니다.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import yaml

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from services.control.system_controller import SystemController
from services.control.function_schemas import ALL_FUNCTIONS, ACU_FUNCTIONS, CCTV_FUNCTIONS
from config.model_config import get_llm_model_name, get_llm_base_url
from services.control.network_discovery import (
    NetworkDiscoveryService,
    DeviceType,
    DeviceStatus,
    get_discovery_service,
)
from services.control.device_registry import (
    DeviceRegistry,
    RegisteredDevice,
    ConnectionStatus,
    get_device_registry,
)

logger = logging.getLogger(__name__)

# Router 생성
router = APIRouter(prefix="/control", tags=["Control"])

# System Controller 인스턴스 (글로벌)
_controller: Optional[SystemController] = None


def _load_llm_config() -> Dict[str, Any]:
    """config.yaml에서 LLM 설정 로드"""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            return config.get("llm", {})
    except Exception as e:
        logger.warning(f"Failed to load config.yaml: {e}, using defaults")
        return {}


def get_controller() -> SystemController:
    """System Controller 인스턴스 반환 (중앙 설정 모듈 사용)"""
    global _controller
    if _controller is None:
        # 중앙 설정 모듈에서 모델명과 URL 가져오기
        model_name = get_llm_model_name()
        base_url = get_llm_base_url()

        _controller = SystemController(
            model_name=model_name,
            vllm_base_url=base_url,
            simulation_mode=True
        )
        logger.info(f"SystemController initialized with model: {model_name}")
    return _controller


# =============================================================================
# Request/Response Models
# =============================================================================

class CommandRequest(BaseModel):
    """자연어 명령 요청"""
    command: str = Field(..., description="자연어 명령 (예: '1번 문 열어줘', '로비 카메라 녹화 시작')")
    use_llm: bool = Field(default=True, description="LLM을 사용한 명령 파싱 (False면 키워드 기반)")


class CommandResponse(BaseModel):
    """명령 실행 응답"""
    success: bool
    command: str
    executions: List[Dict[str, Any]]
    message: str


class FunctionCallRequest(BaseModel):
    """직접 함수 호출 요청"""
    function_name: str = Field(..., description="호출할 함수 이름 (예: unlock_door)")
    arguments: Dict[str, Any] = Field(default={}, description="함수 인자")


class FunctionCallResponse(BaseModel):
    """함수 호출 응답"""
    success: bool
    function_name: str
    result: Dict[str, Any]


class DoorActionRequest(BaseModel):
    """문 제어 요청"""
    door_id: str = Field(..., description="출입문 ID (예: door_01, 정문, 1번문)")
    duration: int = Field(default=5, ge=1, le=60, description="개방 유지 시간(초)")


class CameraActionRequest(BaseModel):
    """카메라 제어 요청"""
    camera_id: str = Field(..., description="카메라 ID (예: cam_01, 로비 카메라)")


class PTZRequest(BaseModel):
    """PTZ 제어 요청"""
    camera_id: str = Field(..., description="카메라 ID")
    pan: Optional[float] = Field(None, ge=-180, le=180, description="수평 이동각도")
    tilt: Optional[float] = Field(None, ge=-90, le=90, description="수직 이동각도")
    zoom: Optional[float] = Field(None, ge=1, le=20, description="줌 레벨")


class RecordingRequest(BaseModel):
    """녹화 요청"""
    camera_id: str = Field(..., description="카메라 ID")
    duration: int = Field(default=0, ge=0, le=1440, description="녹화 시간(분). 0이면 수동 중지까지")
    quality: str = Field(default="high", description="녹화 품질 (low, medium, high, max)")


class PresetRequest(BaseModel):
    """프리셋 요청"""
    camera_id: str = Field(..., description="카메라 ID")
    preset_id: str = Field(..., description="프리셋 ID")
    preset_name: Optional[str] = Field(None, description="프리셋 이름 (저장 시)")


class PermissionRequest(BaseModel):
    """권한 요청"""
    door_id: str = Field(..., description="출입문 ID")
    user_id: str = Field(..., description="사용자 ID")
    valid_until: Optional[str] = Field(None, description="권한 만료 시간 (ISO 8601)")


class EmergencyRequest(BaseModel):
    """비상 제어 요청"""
    reason: str = Field(..., description="비상 사유")
    description: Optional[str] = Field(None, description="상세 설명")


class NetworkScanRequest(BaseModel):
    """네트워크 스캔 요청"""
    subnet: str = Field(default="192.168.1.0/24", description="스캔할 서브넷")
    target_ips: Optional[List[str]] = Field(None, description="특정 IP만 스캔")
    device_types: Optional[List[str]] = Field(None, description="장치 유형 필터 (ip_camera, nvr, acu)")


class DeviceRegisterRequest(BaseModel):
    """장치 등록 요청"""
    ip: str = Field(..., description="장치 IP 주소")
    name: str = Field(..., description="장치 이름 (예: 로비 카메라)")
    username: Optional[str] = Field(None, description="인증 사용자명")
    password: Optional[str] = Field(None, description="인증 비밀번호")
    location: Optional[str] = Field(None, description="설치 위치")
    device_type: Optional[str] = Field(None, description="장치 유형 (ip_camera, nvr, acu)")
    auto_connect: bool = Field(default=True, description="등록 후 자동 연결")


class DeviceUpdateRequest(BaseModel):
    """장치 수정 요청"""
    name: Optional[str] = Field(None, description="장치 이름")
    username: Optional[str] = Field(None, description="인증 사용자명")
    password: Optional[str] = Field(None, description="인증 비밀번호")
    location: Optional[str] = Field(None, description="설치 위치")


# =============================================================================
# Natural Language Command API
# =============================================================================

@router.post("/command", response_model=CommandResponse, summary="자연어 명령 처리")
async def process_command(request: CommandRequest):
    """
    자연어 명령을 처리하여 시스템을 제어합니다.

    예시 명령:
    - "1번 출입문 열어줘"
    - "로비 카메라 녹화 시작"
    - "전체 시스템 상태 확인"
    - "비상 개방"
    """
    controller = get_controller()
    result = await controller.process_command(request.command, use_llm=request.use_llm)
    return CommandResponse(**result)


# =============================================================================
# Direct Function Call API
# =============================================================================

@router.post("/function", response_model=FunctionCallResponse, summary="함수 직접 호출")
async def call_function(request: FunctionCallRequest):
    """
    특정 함수를 직접 호출합니다.

    사용 가능한 함수:
    - ACU: unlock_door, lock_door, get_door_status, get_access_log, grant_access, revoke_access
    - CCTV: move_camera, go_to_preset, start_recording, stop_recording, capture_snapshot
    - System: get_system_status, get_alerts
    """
    controller = get_controller()
    result = await controller.execute_function(request.function_name, request.arguments)
    return FunctionCallResponse(
        success=result.get("success", False),
        function_name=request.function_name,
        result=result
    )


@router.get("/functions", summary="사용 가능한 함수 목록")
async def list_functions():
    """모든 사용 가능한 함수 목록과 스키마를 반환합니다."""
    return {
        "total": len(ALL_FUNCTIONS),
        "categories": {
            "acu": {"count": len(ACU_FUNCTIONS), "functions": [f["name"] for f in ACU_FUNCTIONS]},
            "cctv": {"count": len(CCTV_FUNCTIONS), "functions": [f["name"] for f in CCTV_FUNCTIONS]},
        },
        "schemas": ALL_FUNCTIONS
    }


# =============================================================================
# ACU (출입통제) API
# =============================================================================

@router.post("/acu/door/unlock", summary="출입문 열기")
async def unlock_door(request: DoorActionRequest):
    """지정된 출입문을 엽니다 (잠금 해제)."""
    controller = get_controller()
    result = await controller.acu.unlock_door(request.door_id, request.duration)
    return result


@router.post("/acu/door/lock", summary="출입문 잠금")
async def lock_door(door_id: str = Body(..., embed=True)):
    """지정된 출입문을 잠급니다."""
    controller = get_controller()
    result = await controller.acu.lock_door(door_id)
    return result


@router.get("/acu/door/status", summary="출입문 상태 조회")
async def get_door_status(door_id: Optional[str] = Query(None, description="출입문 ID (없으면 전체)")):
    """출입문 상태를 조회합니다."""
    controller = get_controller()
    result = await controller.acu.get_door_status(door_id)
    return result


@router.get("/acu/log", summary="출입 이력 조회")
async def get_access_log(
    door_id: Optional[str] = Query(None, description="출입문 ID"),
    limit: int = Query(10, ge=1, le=100, description="최대 조회 개수")
):
    """출입 이력을 조회합니다."""
    controller = get_controller()
    result = await controller.acu.get_access_log(door_id=door_id, limit=limit)
    return result


@router.post("/acu/permission/grant", summary="출입 권한 부여")
async def grant_access(request: PermissionRequest):
    """특정 사용자에게 출입 권한을 부여합니다."""
    controller = get_controller()
    result = await controller.acu.grant_access(
        request.door_id,
        request.user_id,
        request.valid_until
    )
    return result


@router.post("/acu/permission/revoke", summary="출입 권한 취소")
async def revoke_access(
    user_id: str = Body(..., description="사용자 ID"),
    door_id: Optional[str] = Body(None, description="출입문 ID (없으면 전체)")
):
    """사용자의 출입 권한을 취소합니다."""
    controller = get_controller()
    result = await controller.acu.revoke_access(user_id, door_id)
    return result


@router.post("/acu/emergency/unlock", summary="비상 전체 개방")
async def emergency_unlock(request: EmergencyRequest):
    """비상 시 모든 출입문을 엽니다."""
    controller = get_controller()
    result = await controller.acu.emergency_unlock_all(
        request.reason,
        request.description
    )
    return result


@router.post("/acu/emergency/lock", summary="비상 전체 잠금")
async def emergency_lock(request: EmergencyRequest):
    """비상 시 모든 출입문을 잠급니다 (봉쇄)."""
    controller = get_controller()
    result = await controller.acu.emergency_lock_all(
        request.reason,
        request.description
    )
    return result


# =============================================================================
# CCTV (영상감시) API
# =============================================================================

@router.post("/cctv/camera/move", summary="카메라 PTZ 제어")
async def move_camera(request: PTZRequest):
    """카메라를 이동합니다 (Pan/Tilt/Zoom)."""
    controller = get_controller()
    result = await controller.cctv.move_camera(
        request.camera_id,
        pan=request.pan,
        tilt=request.tilt,
        zoom=request.zoom
    )
    return result


@router.post("/cctv/camera/preset", summary="프리셋으로 이동")
async def go_to_preset(request: PresetRequest):
    """카메라를 프리셋 위치로 이동합니다."""
    controller = get_controller()
    result = await controller.cctv.go_to_preset(request.camera_id, request.preset_id)
    return result


@router.post("/cctv/camera/preset/save", summary="프리셋 저장")
async def save_preset(request: PresetRequest):
    """현재 카메라 위치를 프리셋으로 저장합니다."""
    controller = get_controller()
    result = await controller.cctv.save_preset(
        request.camera_id,
        request.preset_id,
        request.preset_name
    )
    return result


@router.post("/cctv/recording/start", summary="녹화 시작")
async def start_recording(request: RecordingRequest):
    """카메라 녹화를 시작합니다."""
    controller = get_controller()
    result = await controller.cctv.start_recording(
        request.camera_id,
        duration=request.duration,
        quality=request.quality
    )
    return result


@router.post("/cctv/recording/stop", summary="녹화 중지")
async def stop_recording(camera_id: str = Body(..., embed=True)):
    """카메라 녹화를 중지합니다."""
    controller = get_controller()
    result = await controller.cctv.stop_recording(camera_id)
    return result


@router.post("/cctv/snapshot", summary="스냅샷 캡처")
async def capture_snapshot(
    camera_id: str = Body(..., description="카메라 ID"),
    resolution: str = Body("1080p", description="해상도")
):
    """현재 화면을 스냅샷으로 캡처합니다."""
    controller = get_controller()
    result = await controller.cctv.capture_snapshot(camera_id, resolution)
    return result


@router.get("/cctv/camera/status", summary="카메라 상태 조회")
async def get_camera_status(camera_id: Optional[str] = Query(None, description="카메라 ID (없으면 전체)")):
    """카메라 상태를 조회합니다."""
    controller = get_controller()
    result = await controller.cctv.get_camera_status(camera_id)
    return result


@router.get("/cctv/recordings", summary="녹화 영상 목록")
async def get_recording_list(
    camera_id: Optional[str] = Query(None, description="카메라 ID"),
    limit: int = Query(20, ge=1, le=100, description="최대 조회 개수")
):
    """녹화 영상 목록을 조회합니다."""
    controller = get_controller()
    result = await controller.cctv.get_recording_list(camera_id=camera_id, limit=limit)
    return result


@router.post("/cctv/motion", summary="모션 감지 설정")
async def set_motion_detection(
    camera_id: str = Body(..., description="카메라 ID"),
    enabled: bool = Body(..., description="활성화 여부"),
    sensitivity: str = Body("medium", description="민감도 (low, medium, high)")
):
    """카메라 모션 감지를 설정합니다."""
    controller = get_controller()
    result = await controller.cctv.set_motion_detection(
        camera_id,
        enabled=enabled,
        sensitivity=sensitivity
    )
    return result


# =============================================================================
# System Status API
# =============================================================================

@router.get("/system/status", summary="시스템 전체 상태")
async def get_system_status():
    """ACU 및 CCTV 전체 시스템 상태를 조회합니다."""
    controller = get_controller()
    result = await controller._get_system_status()
    return result


@router.get("/system/alerts", summary="활성 알림 조회")
async def get_alerts(
    severity: str = Query("all", description="심각도 필터 (info, warning, critical, all)"),
    limit: int = Query(10, ge=1, le=100, description="최대 조회 개수")
):
    """활성화된 알림/경고를 조회합니다."""
    controller = get_controller()
    result = await controller._get_alerts(severity=severity, limit=limit)
    return result


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health", summary="컨트롤러 상태 확인")
async def health_check():
    """Control API 상태를 확인합니다."""
    controller = get_controller()
    registry = get_device_registry()
    return {
        "status": "ok",
        "simulation_mode": controller.acu._simulation_mode,
        "functions_available": len(controller.get_available_functions()),
        "acu_doors": len(controller.acu._doors),
        "cctv_cameras": len(controller.cctv._cameras),
        "registered_devices": len(registry.get_all_devices()),
        "connected_devices": len(registry.get_connected_devices()),
    }


# =============================================================================
# Network Discovery API (네트워크 장치 탐색)
# =============================================================================

@router.post("/network/scan", summary="네트워크 장치 스캔")
async def scan_network(request: NetworkScanRequest):
    """
    네트워크를 스캔하여 CCTV, NVR, ACU 장치를 탐색합니다.

    스캔 가능한 장치:
    - IP 카메라 (Hanwha, Hikvision, Dahua 등)
    - NVR (네트워크 비디오 레코더)
    - ACU (출입통제 장치)

    스캔 포트:
    - CCTV: 80, 443, 554(RTSP), 8000, 8080, 37777(Dahua)
    - ACU: 4370(ZKTeco), 5005(Suprema), 4050(HID)
    """
    discovery = get_discovery_service()

    # 장치 유형 필터
    device_types = None
    if request.device_types:
        device_types = [DeviceType(dt) for dt in request.device_types]

    result = await discovery.quick_scan(subnet=request.subnet)

    return {
        "success": True,
        "subnet": request.subnet,
        **result
    }


@router.post("/network/scan/ip", summary="특정 IP 스캔")
async def scan_single_ip(ip: str = Body(..., embed=True)):
    """단일 IP 주소를 스캔하여 장치 정보를 확인합니다."""
    discovery = get_discovery_service()
    device = await discovery.scan_single_ip(ip)

    if device:
        return {
            "success": True,
            "device": device.to_dict()
        }
    else:
        return {
            "success": False,
            "message": f"No device found at {ip}"
        }


# =============================================================================
# Device Registry API (장치 등록 관리)
# =============================================================================

@router.get("/devices", summary="등록된 장치 목록")
async def list_devices(
    device_type: Optional[str] = Query(None, description="장치 유형 필터"),
    connected_only: bool = Query(False, description="연결된 장치만")
):
    """등록된 모든 장치 목록을 조회합니다."""
    registry = get_device_registry()

    if connected_only:
        devices = registry.get_connected_devices()
    elif device_type:
        devices = registry.get_devices_by_type(DeviceType(device_type))
    else:
        devices = registry.get_all_devices()

    return {
        "success": True,
        "total": len(devices),
        "devices": [d.to_dict() for d in devices]
    }


@router.get("/devices/controller-status", summary="LLM 제어 연동 상태")
async def get_controller_sync_status():
    """LLM 제어 시스템과의 연동 상태를 확인합니다."""
    registry = get_device_registry()
    controller = get_controller()

    # 등록된 장치 ID 목록
    registered_camera_ids = {d.id for d in registry.get_all_devices() if d.device_type.value == "ip_camera"}
    registered_door_ids = {d.id for d in registry.get_all_devices() if d.device_type.value == "acu"}

    # 카메라 분류
    cameras_info = []
    real_camera_count = 0
    sim_camera_count = 0
    for cam_id, cam in controller.cctv._cameras.items():
        is_real = cam_id in registered_camera_ids
        cameras_info.append({
            "id": cam_id,
            "name": cam.name,
            "real": is_real
        })
        if is_real:
            real_camera_count += 1
        else:
            sim_camera_count += 1

    # 출입문 분류
    doors_info = []
    real_door_count = 0
    sim_door_count = 0
    for door_id, door in controller.acu._doors.items():
        is_real = door_id in registered_door_ids
        doors_info.append({
            "id": door_id,
            "name": door.name,
            "real": is_real
        })
        if is_real:
            real_door_count += 1
        else:
            sim_door_count += 1

    return {
        "success": True,
        "registered_devices": len(registry.get_all_devices()),
        "connected_devices": len(registry.get_connected_devices()),
        "controller": {
            "real_cameras": real_camera_count,
            "real_doors": real_door_count,
            "simulated_cameras": sim_camera_count,
            "simulated_doors": sim_door_count,
        },
        "devices": {
            "cameras": cameras_info,
            "doors": doors_info,
        }
    }


@router.get("/devices/{device_id}", summary="장치 상세 조회")
async def get_device(device_id: str):
    """특정 장치의 상세 정보를 조회합니다."""
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    return {
        "success": True,
        "device": device.to_dict()
    }


@router.post("/devices/register", summary="장치 등록")
async def register_device(request: DeviceRegisterRequest):
    """
    새 장치를 등록합니다.

    장치 등록 후:
    1. 자동으로 장치 정보 스캔
    2. 인증 정보가 있으면 연결 시도
    3. LLM 제어 시스템에 자동 연동
    """
    registry = get_device_registry()
    discovery = get_discovery_service()

    try:
        # 장치 타입 변환
        device_type = DeviceType(request.device_type) if request.device_type else None

        # IP 스캔하여 장치 정보 수집
        discovered = await discovery.scan_single_ip(request.ip)

        if discovered:
            # 발견된 장치 정보로 등록
            device = await registry.register_device(
                device=discovered,
                name=request.name,
                username=request.username,
                password=request.password,
                location=request.location,
                auto_connect=request.auto_connect,
            )
        else:
            # 스캔 실패 시 직접 등록
            device = await registry.register_from_ip(
                ip=request.ip,
                name=request.name,
                username=request.username,
                password=request.password,
                location=request.location,
                device_type=device_type,
            )

        # LLM 제어 시스템 갱신
        await _sync_devices_to_controller()

        return {
            "success": True,
            "message": f"Device registered: {device.id}",
            "device": device.to_dict()
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/devices/{device_id}", summary="장치 정보 수정")
async def update_device(device_id: str, request: DeviceUpdateRequest):
    """장치 정보를 수정합니다."""
    registry = get_device_registry()

    try:
        device = await registry.update_device(
            device_id=device_id,
            name=request.name,
            username=request.username,
            password=request.password,
            location=request.location,
        )

        # LLM 제어 시스템 갱신
        await _sync_devices_to_controller()

        return {
            "success": True,
            "device": device.to_dict()
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/devices/{device_id}", summary="장치 삭제")
async def delete_device(device_id: str):
    """장치를 삭제합니다."""
    registry = get_device_registry()

    if registry.delete_device(device_id):
        # LLM 제어 시스템 갱신
        await _sync_devices_to_controller()

        return {"success": True, "message": f"Device deleted: {device_id}"}
    else:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")


@router.post("/devices/{device_id}/connect", summary="장치 연결")
async def connect_device(device_id: str):
    """등록된 장치에 연결을 시도합니다."""
    registry = get_device_registry()

    device = registry.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    success = await registry.connect_device(device_id)

    if success:
        # LLM 제어 시스템 갱신
        await _sync_devices_to_controller()

    return {
        "success": success,
        "device_id": device_id,
        "connection_status": device.connection_status.value,
        "message": "Connected successfully" if success else "Connection failed"
    }


@router.post("/devices/{device_id}/disconnect", summary="장치 연결 해제")
async def disconnect_device(device_id: str):
    """장치 연결을 해제합니다."""
    registry = get_device_registry()

    device = registry.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    device.connection_status = ConnectionStatus.DISCONNECTED
    registry._save_devices()

    return {
        "success": True,
        "device_id": device_id,
        "message": "Disconnected"
    }


# =============================================================================
# LLM Controller Sync (LLM 제어 연동)
# =============================================================================

async def _sync_devices_to_controller():
    """
    등록된 장치를 SystemController에 동기화합니다.

    등록된 실제 장치를 LLM이 제어할 수 있도록 연동합니다.
    """
    from services.control.cctv_controller import CameraInfo, CameraState, PTZPosition
    from services.control.acu_controller import DoorInfo, DoorState

    registry = get_device_registry()
    controller = get_controller()

    # 장치 정보 내보내기
    device_data = registry.export_for_controller()

    # 카메라 동기화
    for cam_data in device_data["cameras"]:
        cam_id = cam_data["id"]
        if cam_id not in controller.cctv._cameras:
            # 새 카메라 추가 (CameraInfo 객체 생성)
            camera = CameraInfo(
                camera_id=cam_id,
                name=cam_data["name"],
                location=cam_data["location"],
                state=CameraState.ONLINE if cam_data["status"] == "online" else CameraState.OFFLINE,
            )
            controller.cctv._cameras[cam_id] = camera
            logger.info(f"Added real camera: {cam_id} ({cam_data['name']})")
        else:
            # 기존 카메라 정보 업데이트
            camera = controller.cctv._cameras[cam_id]
            camera.name = cam_data["name"]
            camera.location = cam_data["location"]
            camera.state = CameraState.ONLINE if cam_data["status"] == "online" else CameraState.OFFLINE

    # ACU 동기화
    for door_data in device_data["doors"]:
        door_id = door_data["id"]
        if door_id not in controller.acu._doors:
            # 새 출입문 추가 (DoorInfo 객체 생성)
            door = DoorInfo(
                door_id=door_id,
                name=door_data["name"],
                location=door_data["location"],
                state=DoorState.LOCKED if door_data["status"] == "locked" else DoorState.UNLOCKED,
            )
            controller.acu._doors[door_id] = door
            logger.info(f"Added real door: {door_id} ({door_data['name']})")
        else:
            # 기존 출입문 정보 업데이트
            door = controller.acu._doors[door_id]
            door.name = door_data["name"]
            door.location = door_data["location"]

    logger.info(f"Synced {len(device_data['cameras'])} cameras and {len(device_data['doors'])} doors to controller")


@router.post("/devices/sync", summary="LLM 제어 시스템 동기화")
async def sync_to_controller():
    """등록된 장치를 LLM 제어 시스템에 동기화합니다."""
    await _sync_devices_to_controller()

    registry = get_device_registry()
    controller = get_controller()

    # 등록된 장치 ID로 실제 장치 수 계산
    registered_camera_ids = {d.id for d in registry.get_all_devices() if d.device_type.value == "ip_camera"}
    registered_door_ids = {d.id for d in registry.get_all_devices() if d.device_type.value == "acu"}

    synced_cameras = len([cam_id for cam_id in controller.cctv._cameras.keys() if cam_id in registered_camera_ids])
    synced_doors = len([door_id for door_id in controller.acu._doors.keys() if door_id in registered_door_ids])

    return {
        "success": True,
        "message": "Devices synced to LLM controller",
        "synced": {
            "cameras": synced_cameras,
            "doors": synced_doors,
        },
        "total_registered": len(registry.get_all_devices()),
    }


# =============================================================================
# Credential Management API (인증정보 관리) - Phase 1 보안 강화
# =============================================================================

class CredentialUpdateRequest(BaseModel):
    """인증정보 업데이트 요청"""
    username: str = Field(..., description="사용자명")
    password: str = Field(..., description="비밀번호")
    test_connection: bool = Field(default=True, description="저장 전 연결 테스트 수행")


class CredentialTestRequest(BaseModel):
    """인증정보 테스트 요청"""
    username: Optional[str] = Field(None, description="테스트할 사용자명 (미입력 시 기존 값)")
    password: Optional[str] = Field(None, description="테스트할 비밀번호 (미입력 시 기존 값)")


@router.post("/devices/{device_id}/credentials", summary="장치 인증정보 업데이트")
async def update_device_credentials(device_id: str, request: CredentialUpdateRequest):
    """
    장치의 인증정보를 업데이트합니다.

    - 비밀번호는 암호화되어 저장됩니다 (Fernet AES-128-CBC)
    - test_connection=True면 저장 전에 연결 테스트를 수행합니다
    - 연결 테스트 실패 시 인증정보는 저장되지 않습니다
    """
    registry = get_device_registry()

    result = await registry.update_credentials(
        device_id=device_id,
        username=request.username,
        password=request.password,
        test_connection=request.test_connection,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    # 성공 시 LLM 제어 시스템 동기화
    if result["success"]:
        await _sync_devices_to_controller()

    return result


@router.post("/devices/{device_id}/credentials/test", summary="인증정보 테스트")
async def test_device_credentials(device_id: str, request: CredentialTestRequest):
    """
    인증정보를 테스트합니다 (저장하지 않음).

    - 새 인증정보를 저장 전에 유효성을 확인하는 용도
    - username/password 미입력 시 기존 저장된 값으로 테스트
    """
    registry = get_device_registry()

    result = await registry.test_credentials(
        device_id=device_id,
        username=request.username,
        password=request.password,
    )

    return result


@router.get("/devices/{device_id}/credentials/status", summary="인증정보 상태 확인")
async def get_credential_status(device_id: str):
    """
    장치의 인증정보 상태를 확인합니다.

    - 인증정보 유무, 마지막 연결 성공 시간 등
    - 보안상 실제 username/password는 반환하지 않습니다
    """
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    return {
        "device_id": device_id,
        "has_credentials": bool(device.username and device.password),
        "username_set": bool(device.username),
        "password_set": bool(device.password),
        "connection_status": device.connection_status.value,
        "last_seen": device.last_seen,
        "last_error": device.additional_info.get("last_error"),
    }


@router.get("/devices/export", summary="장치 정보 내보내기 (API용)")
async def export_devices_for_api():
    """
    등록된 장치 정보를 내보냅니다 (API 응답용).

    - 인증정보는 포함되지 않습니다 (보안)
    - RTSP URL의 비밀번호는 마스킹됩니다
    """
    registry = get_device_registry()
    return registry.export_for_api()


@router.get("/security/encryption-status", summary="암호화 상태 확인")
async def get_encryption_status():
    """
    인증정보 암호화 시스템 상태를 확인합니다.

    - 암호화 키 출처 (환경변수, 파일, 자동생성)
    - 암호화 방식 정보
    """
    from services.control.credential_manager import get_credential_manager

    manager = get_credential_manager()
    key_info = manager.get_key_info()

    # 보안상 민감한 정보는 제외
    return {
        "encryption_enabled": True,
        "encryption_method": "Fernet (AES-128-CBC + HMAC-SHA256)",
        "key_source": key_info["key_source"],
        "key_configured": key_info["key_present"],
        "recommendation": (
            "프로덕션 환경에서는 DEVICE_CREDENTIAL_KEY 환경변수를 설정하세요."
            if key_info["key_source"] == "auto_generated"
            else "OK"
        ),
    }


# =============================================================================
# Connection Health API (연결 상태 관리) - Phase 2
# =============================================================================

from services.control.connection_health import (
    ConnectionHealthService,
    get_health_service,
    ConnectionDiagnostics,
)


class DiagnoseRequest(BaseModel):
    """연결 진단 요청"""
    check_onvif: bool = Field(default=True, description="ONVIF 지원 여부 검사")


class ReconnectRequest(BaseModel):
    """재연결 요청"""
    max_attempts: int = Field(default=5, ge=1, le=10, description="최대 재시도 횟수")


@router.get("/devices/{device_id}/health", summary="장치 연결 상태 조회")
async def get_device_health(device_id: str):
    """
    장치의 연결 상태 및 통계를 조회합니다.

    - 총 연결 시도 횟수
    - 성공률
    - 평균 지연시간
    - 최근 연결 이력
    """
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    health_service = get_health_service()
    stats = health_service.get_stats(device_id)

    return {
        "device_id": device_id,
        "device_name": device.name,
        "connection_status": device.connection_status.value,
        "last_seen": device.last_seen,
        "stats": stats.to_dict(),
    }


@router.post("/devices/{device_id}/diagnose", summary="연결 진단 실행")
async def diagnose_device_connection(device_id: str, request: DiagnoseRequest = None):
    """
    장치 연결을 진단합니다.

    진단 항목:
    - 네트워크 도달 가능성
    - 포트 열림 여부
    - HTTP 접근 가능성
    - 인증 유효성
    - ONVIF 지원 여부 (선택)

    Returns:
        진단 결과 및 권장 조치 사항
    """
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    health_service = get_health_service()

    # 포트 추출 (web_interface URL에서)
    port = 80
    if device.web_interface:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(device.web_interface)
            port = parsed.port or 80
        except Exception:
            pass

    check_onvif = request.check_onvif if request else True

    diagnostics = await health_service.diagnose_connection(
        device_id=device_id,
        ip=device.ip,
        port=port,
        username=device.username,
        password=device.password,
        check_onvif=check_onvif,
    )

    return diagnostics.to_dict()


@router.post("/devices/{device_id}/reconnect", summary="장치 재연결")
async def reconnect_device(device_id: str, request: ReconnectRequest = None):
    """
    장치에 재연결을 시도합니다.

    - 지수 백오프 재시도 로직 사용
    - 최대 재시도 횟수 설정 가능
    """
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    if not device.username or not device.password:
        raise HTTPException(
            status_code=400,
            detail="인증 정보가 설정되지 않았습니다. 먼저 인증정보를 설정하세요."
        )

    health_service = get_health_service()
    max_attempts = request.max_attempts if request else 5

    # 임시로 max_attempts 설정
    original_max = health_service.max_retry_attempts
    health_service.max_retry_attempts = max_attempts

    try:
        # 람다로 device_id를 바인딩
        async def do_connect():
            return await registry.connect_device(device_id)

        result = await health_service.connect_with_retry(
            device_id=device_id,
            connect_func=do_connect,
        )

        # 연결 상태 업데이트
        if result["success"]:
            await _sync_devices_to_controller()

        return {
            "device_id": device_id,
            "success": result["success"],
            "attempts": result["attempts"],
            "total_time_seconds": round(result["total_time"], 2),
            "latency_ms": result.get("latency_ms"),
            "error": result.get("last_error"),
            "connection_status": device.connection_status.value,
        }

    finally:
        health_service.max_retry_attempts = original_max


@router.get("/health/devices", summary="전체 장치 연결 상태 요약")
async def get_all_devices_health():
    """
    등록된 모든 장치의 연결 상태를 요약합니다.

    Returns:
        - 전체 장치 수
        - 연결된 장치 수
        - 인증 실패 장치 수
        - 오프라인 장치 수
        - 장치별 상태 목록
    """
    registry = get_device_registry()
    health_service = get_health_service()
    devices = registry.get_all_devices()

    summary = {
        "total": len(devices),
        "connected": 0,
        "disconnected": 0,
        "auth_failed": 0,
        "error": 0,
    }

    device_status = []
    for device in devices:
        status = device.connection_status.value
        summary[status] = summary.get(status, 0) + 1

        stats = health_service.get_stats(device.id)
        device_status.append({
            "id": device.id,
            "name": device.name,
            "ip": device.ip,
            "type": device.device_type.value,
            "connection_status": status,
            "last_seen": device.last_seen,
            "success_rate": round(stats.success_rate * 100, 1),
            "avg_latency_ms": round(stats.avg_latency_ms, 1),
        })

    return {
        "summary": summary,
        "devices": device_status,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health/stats", summary="연결 통계 조회")
async def get_connection_stats():
    """
    모든 장치의 연결 통계를 조회합니다.

    - 장치별 연결 시도 횟수
    - 성공률
    - 평균 지연시간
    - 최근 시도 기록
    """
    health_service = get_health_service()
    return {
        "stats": health_service.get_all_stats(),
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# Zone Management API (존 관리) - Phase 4.1
# =============================================================================

from services.control.zone_manager import (
    ZoneManager,
    Zone,
    SecurityLevel,
    get_zone_manager,
)


class ZoneCreateRequest(BaseModel):
    """존 생성 요청"""
    zone_id: str = Field(..., description="존 ID (예: zone_lobby)")
    name: str = Field(..., description="존 이름 (예: 로비)")
    description: Optional[str] = Field(None, description="존 설명")
    security_level: int = Field(default=1, ge=1, le=5, description="보안 레벨 (1-5)")
    parent_zone_id: Optional[str] = Field(None, description="상위 존 ID")


class ZoneUpdateRequest(BaseModel):
    """존 수정 요청"""
    name: Optional[str] = Field(None, description="존 이름")
    description: Optional[str] = Field(None, description="존 설명")
    security_level: Optional[int] = Field(None, ge=1, le=5, description="보안 레벨 (1-5)")
    parent_zone_id: Optional[str] = Field(None, description="상위 존 ID")


class DeviceZoneAssignRequest(BaseModel):
    """장치 존 배정 요청"""
    zone_id: str = Field(..., description="배정할 존 ID")


@router.get("/zones", summary="존 목록 조회")
async def list_zones():
    """
    등록된 모든 존 목록을 조회합니다.

    Returns:
        존 목록 및 각 존에 배정된 장치 수
    """
    zone_manager = get_zone_manager()
    zones = zone_manager.get_all_zones()

    return {
        "success": True,
        "total": len(zones),
        "zones": [zone.to_dict() for zone in zones],
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/zones/hierarchy", summary="존 계층 구조 조회")
async def get_zone_hierarchy():
    """
    존의 계층 구조를 트리 형태로 조회합니다.

    Returns:
        루트 존부터 시작하는 계층적 구조
    """
    zone_manager = get_zone_manager()
    hierarchy = zone_manager.get_zone_hierarchy()

    return {
        "success": True,
        "hierarchy": hierarchy,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/zones/{zone_id}", summary="존 상세 조회")
async def get_zone(zone_id: str):
    """특정 존의 상세 정보를 조회합니다."""
    zone_manager = get_zone_manager()
    zone = zone_manager.get_zone(zone_id)

    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    # 존 경로 (상위 존 포함)
    path = zone_manager.get_zone_path(zone_id)

    # 해당 존에 배정된 장치 목록
    devices = zone_manager.get_devices_in_zone(zone_id)

    return {
        "success": True,
        "zone": zone.to_dict(),
        "path": path,
        "devices": [d.to_dict() for d in devices],
        "device_count": len(devices),
    }


@router.post("/zones", summary="존 생성")
async def create_zone(request: ZoneCreateRequest):
    """
    새로운 존을 생성합니다.

    보안 레벨:
    - 1: PUBLIC (공개 구역)
    - 2: INTERNAL (내부 구역)
    - 3: RESTRICTED (제한 구역)
    - 4: SECURE (보안 구역)
    - 5: CRITICAL (핵심 보안 구역)
    """
    zone_manager = get_zone_manager()

    try:
        security_level = SecurityLevel(request.security_level)
    except ValueError:
        security_level = SecurityLevel.PUBLIC

    try:
        zone = zone_manager.create_zone(
            zone_id=request.zone_id,
            name=request.name,
            description=request.description,
            security_level=security_level,
            parent_zone_id=request.parent_zone_id,
        )

        return {
            "success": True,
            "message": f"Zone created: {zone.zone_id}",
            "zone": zone.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/zones/{zone_id}", summary="존 수정")
async def update_zone(zone_id: str, request: ZoneUpdateRequest):
    """존 정보를 수정합니다."""
    zone_manager = get_zone_manager()

    security_level = None
    if request.security_level is not None:
        try:
            security_level = SecurityLevel(request.security_level)
        except ValueError:
            pass

    try:
        zone = zone_manager.update_zone(
            zone_id=zone_id,
            name=request.name,
            description=request.description,
            security_level=security_level,
            parent_zone_id=request.parent_zone_id,
        )

        return {
            "success": True,
            "zone": zone.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/zones/{zone_id}", summary="존 삭제")
async def delete_zone(zone_id: str, force: bool = Query(False, description="강제 삭제 (하위 존/장치 포함)")):
    """
    존을 삭제합니다.

    - force=False: 하위 존이나 배정된 장치가 있으면 삭제 불가
    - force=True: 하위 존/장치를 상위 존으로 이동 후 삭제
    """
    zone_manager = get_zone_manager()

    try:
        zone_manager.delete_zone(zone_id, force=force)
        return {
            "success": True,
            "message": f"Zone deleted: {zone_id}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/devices/{device_id}/zone", summary="장치 존 배정")
async def assign_device_to_zone(device_id: str, request: DeviceZoneAssignRequest):
    """
    장치를 특정 존에 배정합니다.

    - 기존 존 배정이 있으면 변경됩니다
    - 존 배정은 감사 로그에 기록됩니다
    """
    zone_manager = get_zone_manager()
    registry = get_device_registry()

    # 장치 확인
    device = registry.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    try:
        zone_manager.assign_device_to_zone(device_id, request.zone_id)

        # 감사 로깅
        from services.control.audit_logger import get_audit_logger
        audit = get_audit_logger()
        await audit.log_device_control(
            device_id=device_id,
            action="zone_assign",
            user_id="api",
            details={"zone_id": request.zone_id},
        )

        return {
            "success": True,
            "device_id": device_id,
            "zone_id": request.zone_id,
            "message": f"Device assigned to zone: {request.zone_id}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/devices/{device_id}/zone", summary="장치 존 배정 해제")
async def remove_device_from_zone(device_id: str):
    """장치의 존 배정을 해제합니다 (미분류로 이동)."""
    zone_manager = get_zone_manager()
    registry = get_device_registry()

    # 장치 확인
    device = registry.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    zone_manager.remove_device_from_zone(device_id)

    return {
        "success": True,
        "device_id": device_id,
        "message": "Device removed from zone (moved to unassigned)",
    }


@router.get("/zones/{zone_id}/devices", summary="존 내 장치 목록")
async def list_devices_in_zone(
    zone_id: str,
    include_subzones: bool = Query(False, description="하위 존 장치 포함")
):
    """
    특정 존에 배정된 장치 목록을 조회합니다.

    - include_subzones=True: 하위 존의 장치도 포함
    """
    zone_manager = get_zone_manager()

    zone = zone_manager.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    devices = zone_manager.get_devices_in_zone(zone_id, include_subzones=include_subzones)

    return {
        "success": True,
        "zone_id": zone_id,
        "zone_name": zone.name,
        "include_subzones": include_subzones,
        "total": len(devices),
        "devices": [d.to_dict() for d in devices],
    }


# =============================================================================
# Audit Log API (감사 로깅) - Phase 4.2
# =============================================================================

from services.control.audit_logger import (
    AuditLogger,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
)


class AuditLogQuery(BaseModel):
    """감사 로그 조회 필터"""
    event_types: Optional[List[str]] = Field(None, description="이벤트 유형 필터")
    severities: Optional[List[str]] = Field(None, description="심각도 필터")
    device_id: Optional[str] = Field(None, description="장치 ID 필터")
    user_id: Optional[str] = Field(None, description="사용자 ID 필터")
    start_time: Optional[str] = Field(None, description="시작 시간 (ISO 8601)")
    end_time: Optional[str] = Field(None, description="종료 시간 (ISO 8601)")
    limit: int = Field(default=100, ge=1, le=1000, description="최대 결과 수")


@router.get("/audit/logs", summary="감사 로그 조회")
async def get_audit_logs(
    event_type: Optional[str] = Query(None, description="이벤트 유형"),
    severity: Optional[str] = Query(None, description="심각도"),
    device_id: Optional[str] = Query(None, description="장치 ID"),
    user_id: Optional[str] = Query(None, description="사용자 ID"),
    limit: int = Query(100, ge=1, le=1000, description="최대 결과 수"),
):
    """
    감사 로그를 조회합니다.

    이벤트 유형:
    - credential_view: 인증정보 조회
    - credential_update: 인증정보 수정
    - credential_test: 인증정보 테스트
    - credential_export: 인증정보 내보내기
    - connection_attempt: 연결 시도
    - connection_success: 연결 성공
    - connection_failure: 연결 실패
    - connection_timeout: 연결 타임아웃
    - device_unlock: 출입문 해제
    - device_lock: 출입문 잠금
    - camera_ptz: 카메라 PTZ 제어
    - camera_recording: 녹화 제어
    - auth_failure: 인증 실패
    - access_denied: 접근 거부
    - config_change: 설정 변경
    """
    audit = get_audit_logger()

    # 필터 파싱
    event_types = [AuditEventType(event_type)] if event_type else None
    severities = [AuditSeverity[severity.upper()]] if severity else None

    logs = await audit.get_logs(
        event_types=event_types,
        severities=severities,
        device_id=device_id,
        user_id=user_id,
        limit=limit,
    )

    return {
        "success": True,
        "total": len(logs),
        "logs": logs,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/audit/logs/recent", summary="최근 감사 로그")
async def get_recent_audit_logs(
    minutes: int = Query(60, ge=1, le=1440, description="최근 N분 내 로그"),
    limit: int = Query(50, ge=1, le=500, description="최대 결과 수"),
):
    """
    최근 N분 내의 감사 로그를 조회합니다.

    실시간 모니터링 및 대시보드용 API입니다.
    """
    audit = get_audit_logger()
    logs = await audit.get_recent_logs(minutes=minutes, limit=limit)

    return {
        "success": True,
        "minutes": minutes,
        "total": len(logs),
        "logs": logs,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/audit/logs/security", summary="보안 이벤트 로그")
async def get_security_logs(
    limit: int = Query(100, ge=1, le=1000, description="최대 결과 수"),
):
    """
    보안 관련 이벤트 로그만 조회합니다.

    포함되는 이벤트:
    - 인증 실패
    - 접근 거부
    - 인증정보 관련 모든 이벤트
    """
    audit = get_audit_logger()

    security_events = [
        AuditEventType.AUTH_FAILURE,
        AuditEventType.ACCESS_DENIED,
        AuditEventType.CREDENTIAL_VIEW,
        AuditEventType.CREDENTIAL_UPDATE,
        AuditEventType.CREDENTIAL_TEST,
        AuditEventType.CREDENTIAL_EXPORT,
    ]

    logs = await audit.get_logs(
        event_types=security_events,
        limit=limit,
    )

    return {
        "success": True,
        "total": len(logs),
        "logs": logs,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/audit/logs/device/{device_id}", summary="장치별 감사 로그")
async def get_device_audit_logs(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000, description="최대 결과 수"),
):
    """특정 장치에 대한 모든 감사 로그를 조회합니다."""
    audit = get_audit_logger()

    logs = await audit.get_logs(
        device_id=device_id,
        limit=limit,
    )

    return {
        "success": True,
        "device_id": device_id,
        "total": len(logs),
        "logs": logs,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/audit/summary", summary="감사 로그 요약")
async def get_audit_summary(
    hours: int = Query(24, ge=1, le=168, description="집계 기간 (시간)"),
):
    """
    감사 로그 통계 요약을 조회합니다.

    - 이벤트 유형별 건수
    - 심각도별 건수
    - 시간대별 추이
    """
    audit = get_audit_logger()
    summary = await audit.get_summary(hours=hours)

    return {
        "success": True,
        "period_hours": hours,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
    }


@router.delete("/audit/logs", summary="감사 로그 정리")
async def cleanup_audit_logs(
    days: int = Query(90, ge=30, le=365, description="보관 기간 (일)"),
):
    """
    오래된 감사 로그를 정리합니다.

    - 지정된 일수보다 오래된 로그 파일 삭제
    - 기본 90일 보관
    """
    audit = get_audit_logger()
    deleted_count = await audit.cleanup_old_logs(days=days)

    return {
        "success": True,
        "retention_days": days,
        "deleted_files": deleted_count,
        "message": f"Cleaned up logs older than {days} days",
    }


# =============================================================================
# Rate Limiting API (속도 제한) - Phase 4.3
# =============================================================================

from services.control.rate_limiter import (
    RateLimiter,
    RateLimitType,
    get_rate_limiter,
    check_auth_rate_limit,
)


@router.get("/rate-limit/status", summary="속도 제한 상태 조회")
async def get_rate_limit_status(
    identifier: str = Query(..., description="식별자 (IP, device_id 등)"),
    limit_type: str = Query("api_request", description="제한 유형"),
):
    """
    특정 식별자의 속도 제한 상태를 조회합니다.

    제한 유형:
    - auth_attempt: 인증 시도 (5회/5분, 15분 잠금)
    - api_request: API 요청 (100회/분)
    - credential_access: 인증정보 접근 (10회/분, 5분 잠금)
    - device_control: 장치 제어 (30회/분)
    """
    limiter = get_rate_limiter()

    try:
        rate_type = RateLimitType(limit_type)
    except ValueError:
        rate_type = RateLimitType.API_REQUEST

    status = await limiter.get_remaining(rate_type, identifier)

    return {
        "identifier": identifier,
        "limit_type": limit_type,
        **status,
    }


@router.get("/rate-limit/stats", summary="속도 제한 통계")
async def get_rate_limit_stats():
    """전체 속도 제한 통계를 조회합니다."""
    limiter = get_rate_limiter()
    stats = await limiter.get_stats()

    return {
        "success": True,
        "stats": stats,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/rate-limit/reset", summary="속도 제한 초기화")
async def reset_rate_limit(
    identifier: str = Body(..., description="식별자"),
    limit_type: str = Body("auth_attempt", description="제한 유형"),
):
    """
    특정 식별자의 속도 제한을 초기화합니다.

    관리자 전용 - 잘못된 잠금 해제에 사용
    """
    limiter = get_rate_limiter()

    try:
        rate_type = RateLimitType(limit_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid limit type: {limit_type}")

    await limiter.reset(rate_type, identifier)

    # 감사 로깅
    audit = get_audit_logger()
    await audit.log_security_event(
        event_type=AuditEventType.CONFIG_CHANGE,
        severity=AuditSeverity.WARNING,
        details={
            "action": "rate_limit_reset",
            "identifier": identifier,
            "limit_type": limit_type,
        },
    )

    return {
        "success": True,
        "identifier": identifier,
        "limit_type": limit_type,
        "message": "Rate limit reset successfully",
    }


@router.post("/rate-limit/cleanup", summary="만료된 제한 정리")
async def cleanup_rate_limits():
    """만료된 속도 제한 상태를 정리합니다."""
    limiter = get_rate_limiter()
    cleaned = await limiter.cleanup_expired()

    return {
        "success": True,
        "cleaned_entries": cleaned,
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# Detailed Health Check API (상세 헬스체크) - Phase 4.4
# =============================================================================

@router.get("/health/detailed", summary="상세 시스템 헬스체크")
async def detailed_health_check():
    """
    전체 시스템의 상세 헬스체크를 수행합니다.

    확인 항목:
    - 백엔드 서비스 상태
    - 데이터베이스 연결
    - Redis 연결 (선택적)
    - Qdrant 연결 (선택적)
    - vLLM 서버 연결
    - 장치 연결 상태 요약
    """
    from pathlib import Path
    import aiohttp

    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {},
        "devices": {},
    }

    # 1. 백엔드 상태
    health_status["services"]["backend"] = {
        "status": "healthy",
        "uptime": "running",
    }

    # 2. 데이터베이스 연결 확인
    try:
        # PostgreSQL 연결 확인은 선택적
        health_status["services"]["database"] = {
            "status": "unknown",
            "message": "Not configured for health check",
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # 3. Redis 연결 확인 (선택적)
    try:
        health_status["services"]["redis"] = {
            "status": "unknown",
            "message": "Not configured for health check",
        }
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # 4. Qdrant 연결 확인
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:6333/collections", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    health_status["services"]["qdrant"] = {
                        "status": "healthy",
                        "port": 6333,
                    }
                else:
                    health_status["services"]["qdrant"] = {
                        "status": "unhealthy",
                        "error": f"HTTP {resp.status}",
                    }
    except Exception as e:
        health_status["services"]["qdrant"] = {
            "status": "unavailable",
            "error": str(e),
        }

    # 5. vLLM 서버 연결 확인
    llm_config = _load_llm_config()
    vllm_url = llm_config.get("base_url", "http://localhost:9000/v1")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{vllm_url}/models", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = data.get("data", [])
                    health_status["services"]["vllm"] = {
                        "status": "healthy",
                        "url": vllm_url,
                        "models_loaded": len(models),
                    }
                else:
                    health_status["services"]["vllm"] = {
                        "status": "unhealthy",
                        "url": vllm_url,
                        "error": f"HTTP {resp.status}",
                    }
    except Exception as e:
        health_status["services"]["vllm"] = {
            "status": "unavailable",
            "url": vllm_url,
            "error": str(e),
        }

    # 6. 장치 상태 요약
    registry = get_device_registry()
    devices = registry.get_all_devices()

    device_summary = {
        "total": len(devices),
        "connected": 0,
        "disconnected": 0,
        "auth_failed": 0,
        "error": 0,
    }

    for device in devices:
        status = device.connection_status.value
        if status in device_summary:
            device_summary[status] += 1
        else:
            device_summary["error"] += 1

    health_status["devices"] = device_summary

    # 7. 제어 시스템 상태
    controller = get_controller()
    health_status["control"] = {
        "simulation_mode": controller.acu._simulation_mode,
        "acu_doors": len(controller.acu._doors),
        "cctv_cameras": len(controller.cctv._cameras),
        "functions_available": len(controller.get_available_functions()),
    }

    # 8. 존 시스템 상태
    zone_manager = get_zone_manager()
    health_status["zones"] = {
        "total_zones": len(zone_manager.get_all_zones()),
    }

    # 9. 전체 상태 결정
    unhealthy_services = [
        name for name, info in health_status["services"].items()
        if info.get("status") == "unhealthy"
    ]

    if unhealthy_services:
        health_status["status"] = "degraded"
        health_status["unhealthy_services"] = unhealthy_services

    # 장치 연결 문제가 많으면 경고
    if device_summary["total"] > 0:
        connected_ratio = device_summary["connected"] / device_summary["total"]
        if connected_ratio < 0.5:
            health_status["warnings"] = health_status.get("warnings", [])
            health_status["warnings"].append(
                f"장치 연결률이 낮습니다: {connected_ratio*100:.0f}%"
            )

    return health_status


@router.get("/health/services", summary="서비스 연결 상태")
async def check_service_connections():
    """
    외부 서비스들의 연결 상태를 확인합니다.

    확인 서비스:
    - vLLM (텍스트 LLM)
    - Qdrant (벡터 DB)
    - PostgreSQL (선택적)
    - Redis (선택적)
    """
    import aiohttp

    services = {}

    # vLLM 확인
    llm_config = _load_llm_config()
    vllm_url = llm_config.get("base_url", "http://localhost:9000/v1")

    try:
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now()
            async with session.get(f"{vllm_url}/models", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                services["vllm"] = {
                    "status": "connected" if resp.status == 200 else "error",
                    "url": vllm_url,
                    "latency_ms": round(latency, 2),
                }
    except Exception as e:
        services["vllm"] = {
            "status": "disconnected",
            "url": vllm_url,
            "error": str(e),
        }

    # Qdrant 확인
    try:
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now()
            async with session.get("http://localhost:6333/collections", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                if resp.status == 200:
                    data = await resp.json()
                    services["qdrant"] = {
                        "status": "connected",
                        "url": "http://localhost:6333",
                        "latency_ms": round(latency, 2),
                        "collections": len(data.get("result", {}).get("collections", [])),
                    }
                else:
                    services["qdrant"] = {
                        "status": "error",
                        "url": "http://localhost:6333",
                        "error": f"HTTP {resp.status}",
                    }
    except Exception as e:
        services["qdrant"] = {
            "status": "disconnected",
            "url": "http://localhost:6333",
            "error": str(e),
        }

    return {
        "success": True,
        "services": services,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health/devices/summary", summary="장치 헬스 요약")
async def get_device_health_summary():
    """
    모든 장치의 연결 상태를 유형별로 요약합니다.
    """
    registry = get_device_registry()
    health_service = get_health_service()
    zone_manager = get_zone_manager()

    devices = registry.get_all_devices()

    summary = {
        "total_devices": len(devices),
        "by_status": {
            "connected": 0,
            "disconnected": 0,
            "auth_failed": 0,
            "error": 0,
            "connecting": 0,
        },
        "by_type": {},
        "by_zone": {},
        "connection_quality": {
            "excellent": 0,  # <100ms
            "good": 0,  # 100-500ms
            "fair": 0,  # 500-1000ms
            "poor": 0,  # >1000ms
            "unknown": 0,
        },
    }

    for device in devices:
        # 상태별 집계
        status = device.connection_status.value
        if status in summary["by_status"]:
            summary["by_status"][status] += 1

        # 유형별 집계
        device_type = device.device_type.value
        if device_type not in summary["by_type"]:
            summary["by_type"][device_type] = {"total": 0, "connected": 0}
        summary["by_type"][device_type]["total"] += 1
        if status == "connected":
            summary["by_type"][device_type]["connected"] += 1

        # 존별 집계
        zone_id = zone_manager.get_device_zone(device.id)
        zone = zone_manager.get_zone(zone_id) if zone_id else None
        zone_name = zone.name if zone else "미분류"

        if zone_name not in summary["by_zone"]:
            summary["by_zone"][zone_name] = {"total": 0, "connected": 0}
        summary["by_zone"][zone_name]["total"] += 1
        if status == "connected":
            summary["by_zone"][zone_name]["connected"] += 1

        # 연결 품질 집계
        stats = health_service.get_stats(device.id)
        if stats.avg_latency_ms > 0:
            if stats.avg_latency_ms < 100:
                summary["connection_quality"]["excellent"] += 1
            elif stats.avg_latency_ms < 500:
                summary["connection_quality"]["good"] += 1
            elif stats.avg_latency_ms < 1000:
                summary["connection_quality"]["fair"] += 1
            else:
                summary["connection_quality"]["poor"] += 1
        else:
            summary["connection_quality"]["unknown"] += 1

    # 전체 연결률
    if summary["total_devices"] > 0:
        summary["connection_rate"] = round(
            summary["by_status"]["connected"] / summary["total_devices"] * 100, 1
        )
    else:
        summary["connection_rate"] = 0

    return {
        "success": True,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
    }
