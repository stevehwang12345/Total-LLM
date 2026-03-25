"""
CCTV (영상감시) 제어기

PTZ 제어, 녹화, 스냅샷, 프리셋 관리 등 CCTV 카메라 제어 기능을 제공합니다.
Device Adapter Pattern을 사용하여 실제 장치(ONVIF) 또는 시뮬레이션 모드로 동작합니다.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import asyncio
from pathlib import Path

import yaml

from .adapters import DeviceAdapterFactory, DeviceCommand, DeviceResponse
from .adapters.cctv.base import (
    BaseCCTVAdapter,
    PTZDirection,
    StreamProtocol
)
from .adapters.simulation import SimulationCCTVAdapter

logger = logging.getLogger(__name__)


class CameraState(Enum):
    """카메라 상태"""
    ONLINE = "online"
    OFFLINE = "offline"
    RECORDING = "recording"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class RecordingQuality(Enum):
    """녹화 품질"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


@dataclass
class PTZPosition:
    """PTZ 위치"""
    pan: float = 0.0  # -180 ~ 180
    tilt: float = 0.0  # -90 ~ 90
    zoom: float = 1.0  # 1x ~ 20x


@dataclass
class Preset:
    """프리셋 정보"""
    preset_id: str
    name: str
    position: PTZPosition
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CameraInfo:
    """카메라 정보"""
    camera_id: str
    name: str
    location: str
    state: CameraState = CameraState.ONLINE
    is_recording: bool = False
    position: PTZPosition = field(default_factory=PTZPosition)
    presets: Dict[str, Preset] = field(default_factory=dict)
    motion_detection: bool = False
    motion_sensitivity: str = "medium"
    # Adapter 관련 정보
    adapter: Optional[BaseCCTVAdapter] = None
    is_real_device: bool = False
    ip: str = ""
    port: int = 80
    manufacturer: str = "simulation"


@dataclass
class Recording:
    """녹화 정보"""
    recording_id: str
    camera_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    quality: RecordingQuality = RecordingQuality.HIGH
    file_path: Optional[str] = None


def _load_device_control_config() -> Dict[str, Any]:
    """config.yaml에서 device_control 설정 로드"""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            return config.get("device_control", {})
    except Exception as e:
        logger.warning(f"Failed to load device_control config: {e}")
        return {}


class CCTVController:
    """
    CCTV 영상감시 제어기

    Device Adapter Pattern을 사용하여 실제 장치 또는 시뮬레이션으로 동작합니다.
    Hybrid 모드: 실제 장치 우선, 연결 실패 시 시뮬레이션 폴백
    """

    def __init__(
        self,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        simulation_mode: bool = True,
        mode: Optional[str] = None,  # "simulation", "real", "hybrid"
    ):
        """
        Args:
            api_endpoint: (deprecated) ONVIF 또는 CCTV 시스템 API 엔드포인트
            api_key: (deprecated) API 인증 키
            simulation_mode: True이면 시뮬레이션 모드로 동작
            mode: 제어 모드 ("simulation", "real", "hybrid")
        """
        # 설정 로드
        config = _load_device_control_config()

        # 모드 결정 (우선순위: 명시적 mode > simulation_mode > config)
        if mode:
            self._mode = mode
        elif simulation_mode:
            self._mode = "simulation"
        else:
            self._mode = config.get("default_mode", "hybrid")

        # Adapter Factory 초기화
        fallback = config.get("hybrid", {}).get("fallback_to_simulation", True)
        self._adapter_factory = DeviceAdapterFactory(
            mode=self._mode,
            fallback_to_simulation=fallback
        )

        # 카메라 저장소
        self._cameras: Dict[str, CameraInfo] = {}
        self._recordings: List[Recording] = []
        self._active_recordings: Dict[str, Recording] = {}
        self._lock = asyncio.Lock()

        # 시뮬레이션 데이터 초기화 (hybrid/simulation 모드)
        if self._mode in ["simulation", "hybrid"]:
            self._init_simulation_data()

        logger.info(f"CCTVController initialized in '{self._mode}' mode")

    def _init_simulation_data(self):
        """시뮬레이션용 초기 데이터 설정"""
        # 기본 프리셋 정의
        default_presets = {
            "entrance": Preset("entrance", "입구", PTZPosition(0, 0, 1.0)),
            "parking": Preset("parking", "주차장", PTZPosition(45, -15, 2.0)),
            "wide": Preset("wide", "전체 보기", PTZPosition(0, 0, 1.0)),
            "zoom_center": Preset("zoom_center", "중앙 확대", PTZPosition(0, 0, 5.0)),
        }

        self._cameras = {
            "cam_01": CameraInfo(
                camera_id="cam_01",
                name="로비 카메라",
                location="1층 로비",
                state=CameraState.ONLINE,
                position=PTZPosition(0, 0, 1.0),
                presets=default_presets.copy(),
            ),
            "cam_02": CameraInfo(
                camera_id="cam_02",
                name="주차장 카메라",
                location="지하 1층 주차장",
                state=CameraState.ONLINE,
                position=PTZPosition(45, -15, 2.0),
                presets=default_presets.copy(),
            ),
            "cam_03": CameraInfo(
                camera_id="cam_03",
                name="후문 카메라",
                location="1층 후문",
                state=CameraState.RECORDING,
                is_recording=True,
                position=PTZPosition(0, 0, 1.0),
                presets=default_presets.copy(),
            ),
            "cam_04": CameraInfo(
                camera_id="cam_04",
                name="옥상 카메라",
                location="옥상",
                state=CameraState.ONLINE,
                position=PTZPosition(90, -30, 3.0),
                presets=default_presets.copy(),
            ),
            "cam_05": CameraInfo(
                camera_id="cam_05",
                name="서버실 카메라",
                location="3층 서버실",
                state=CameraState.OFFLINE,
                position=PTZPosition(0, 0, 1.0),
                presets=default_presets.copy(),
            ),
        }

    def register_camera(
        self,
        camera_id: str,
        name: str,
        location: str,
        ip: str,
        port: int = 80,
        username: str = "admin",
        password: str = "",
        manufacturer: str = "onvif",
        is_real_device: bool = True,
    ) -> Dict[str, Any]:
        """
        실제 카메라 등록

        네트워크 탐색으로 발견된 카메라를 컨트롤러에 등록합니다.
        """
        device_info = {
            "id": camera_id,
            "device_id": camera_id,
            "device_type": "cctv",
            "name": name,
            "location": location,
            "ip": ip,
            "port": port,
            "username": username,
            "password": password,
            "manufacturer": manufacturer,
            "is_real_device": is_real_device,
        }

        # 어댑터 생성
        try:
            adapter = self._adapter_factory.create_adapter(device_info)
        except Exception as e:
            logger.error(f"Failed to create adapter for {camera_id}: {e}")
            adapter = None

        # 카메라 정보 저장
        camera = CameraInfo(
            camera_id=camera_id,
            name=name,
            location=location,
            state=CameraState.ONLINE,
            adapter=adapter,
            is_real_device=is_real_device,
            ip=ip,
            port=port,
            manufacturer=manufacturer,
        )
        self._cameras[camera_id] = camera

        logger.info(f"Camera registered: {camera_id} ({name}) - real_device={is_real_device}")

        return {
            "success": True,
            "camera_id": camera_id,
            "name": name,
            "message": f"카메라 '{name}'이(가) 등록되었습니다",
        }

    def _normalize_camera_id(self, camera_id: str) -> str:
        """카메라 ID 정규화 (한글 이름 → ID 변환)"""
        name_to_id = {
            "로비": "cam_01",
            "로비 카메라": "cam_01",
            "주차장": "cam_02",
            "주차장 카메라": "cam_02",
            "후문": "cam_03",
            "후문 카메라": "cam_03",
            "옥상": "cam_04",
            "옥상 카메라": "cam_04",
            "서버실": "cam_05",
            "서버실 카메라": "cam_05",
            "1번": "cam_01",
            "2번": "cam_02",
            "3번": "cam_03",
            "4번": "cam_04",
            "5번": "cam_05",
            "1번 카메라": "cam_01",
            "2번 카메라": "cam_02",
            "3번 카메라": "cam_03",
        }
        return name_to_id.get(camera_id, camera_id)

    def _get_adapter_for_camera(self, camera: CameraInfo) -> BaseCCTVAdapter:
        """카메라에 대한 어댑터 반환 (없으면 생성)"""
        if camera.adapter:
            return camera.adapter

        # 시뮬레이션 어댑터 생성
        device_info = {
            "id": camera.camera_id,
            "device_type": "cctv",
            "name": camera.name,
            "location": camera.location,
            "ip": camera.ip or "127.0.0.1",
            "port": camera.port,
            "manufacturer": camera.manufacturer,
            "is_real_device": camera.is_real_device,
        }
        adapter = self._adapter_factory.create_adapter(device_info)
        camera.adapter = adapter
        return adapter

    async def move_camera(
        self,
        camera_id: str,
        pan: Optional[float] = None,
        tilt: Optional[float] = None,
        zoom: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        카메라 PTZ 제어

        Args:
            camera_id: 카메라 ID
            pan: 수평 이동각도 (-180 ~ 180)
            tilt: 수직 이동각도 (-90 ~ 90)
            zoom: 줌 레벨 (1x ~ 20x)

        Returns:
            실행 결과
        """
        camera_id = self._normalize_camera_id(camera_id)
        logger.info(f"CCTV: Moving camera {camera_id} - pan={pan}, tilt={tilt}, zoom={zoom}")

        async with self._lock:
            if camera_id not in self._cameras:
                return {
                    "success": False,
                    "error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다",
                    "camera_id": camera_id,
                }

            camera = self._cameras[camera_id]
            if camera.state == CameraState.OFFLINE:
                return {
                    "success": False,
                    "error": f"카메라 '{camera.name}'이(가) 오프라인 상태입니다",
                    "camera_id": camera_id,
                }

            # 어댑터를 통한 PTZ 제어
            adapter = self._get_adapter_for_camera(camera)

            # 연결 확인
            if not adapter.is_connected:
                await adapter.connect()

            # PTZ 이동
            response = await adapter.move_ptz(pan=pan, tilt=tilt, zoom=zoom)

            if response.success:
                # 로컬 상태 업데이트
                if pan is not None:
                    camera.position.pan = max(-180, min(180, pan))
                if tilt is not None:
                    camera.position.tilt = max(-90, min(90, tilt))
                if zoom is not None:
                    camera.position.zoom = max(1.0, min(20.0, zoom))

                return {
                    "success": True,
                    "camera_id": camera_id,
                    "camera_name": camera.name,
                    "action": "moved",
                    "position": {
                        "pan": camera.position.pan,
                        "tilt": camera.position.tilt,
                        "zoom": camera.position.zoom,
                    },
                    "message": f"🎥 {camera.name}이(가) 이동했습니다 (Pan:{camera.position.pan:.1f}°, Tilt:{camera.position.tilt:.1f}°, Zoom:{camera.position.zoom:.1f}x)",
                }
            else:
                return {
                    "success": False,
                    "error": response.error or "PTZ 이동 실패",
                    "camera_id": camera_id,
                }

    async def go_to_preset(
        self,
        camera_id: str,
        preset_id: str,
    ) -> Dict[str, Any]:
        """
        프리셋 위치로 이동

        Args:
            camera_id: 카메라 ID
            preset_id: 프리셋 ID

        Returns:
            실행 결과
        """
        camera_id = self._normalize_camera_id(camera_id)
        logger.info(f"CCTV: Moving camera {camera_id} to preset {preset_id}")

        async with self._lock:
            if camera_id not in self._cameras:
                return {
                    "success": False,
                    "error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다",
                }

            camera = self._cameras[camera_id]

            # 어댑터를 통한 프리셋 이동
            adapter = self._get_adapter_for_camera(camera)

            if not adapter.is_connected:
                await adapter.connect()

            response = await adapter.go_to_preset(preset_id)

            if response.success:
                # 로컬 프리셋 정보로 위치 업데이트
                if preset_id in camera.presets:
                    preset = camera.presets[preset_id]
                    camera.position = PTZPosition(
                        pan=preset.position.pan,
                        tilt=preset.position.tilt,
                        zoom=preset.position.zoom,
                    )
                    preset_name = preset.name
                else:
                    preset_name = preset_id

                return {
                    "success": True,
                    "camera_id": camera_id,
                    "camera_name": camera.name,
                    "preset_id": preset_id,
                    "preset_name": preset_name,
                    "action": "preset_moved",
                    "position": {
                        "pan": camera.position.pan,
                        "tilt": camera.position.tilt,
                        "zoom": camera.position.zoom,
                    },
                    "message": f"🎥 {camera.name}이(가) '{preset_name}' 프리셋으로 이동했습니다",
                }
            else:
                available = ", ".join(camera.presets.keys())
                return {
                    "success": False,
                    "error": response.error or f"프리셋 '{preset_id}'을(를) 찾을 수 없습니다. 사용 가능: {available}",
                }

    async def save_preset(
        self,
        camera_id: str,
        preset_id: str,
        preset_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """현재 위치를 프리셋으로 저장"""
        camera_id = self._normalize_camera_id(camera_id)
        logger.info(f"CCTV: Saving preset {preset_id} for camera {camera_id}")

        async with self._lock:
            if camera_id not in self._cameras:
                return {"success": False, "error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다"}

            camera = self._cameras[camera_id]

            # 어댑터를 통한 프리셋 저장
            adapter = self._get_adapter_for_camera(camera)

            if not adapter.is_connected:
                await adapter.connect()

            name = preset_name or preset_id
            response = await adapter.set_preset(preset_id, name)

            if response.success:
                # 로컬 프리셋 저장
                preset = Preset(
                    preset_id=preset_id,
                    name=name,
                    position=PTZPosition(
                        pan=camera.position.pan,
                        tilt=camera.position.tilt,
                        zoom=camera.position.zoom,
                    ),
                )
                camera.presets[preset_id] = preset

                return {
                    "success": True,
                    "camera_id": camera_id,
                    "preset_id": preset_id,
                    "preset_name": name,
                    "message": f"✅ 프리셋 '{name}'이(가) 저장되었습니다",
                }
            else:
                return {
                    "success": False,
                    "error": response.error or "프리셋 저장 실패",
                }

    async def start_recording(
        self,
        camera_id: str,
        duration: int = 0,
        quality: str = "high",
    ) -> Dict[str, Any]:
        """
        녹화 시작

        Args:
            camera_id: 카메라 ID
            duration: 녹화 시간(분). 0이면 수동 중지까지
            quality: 녹화 품질

        Returns:
            실행 결과
        """
        camera_id = self._normalize_camera_id(camera_id)
        logger.info(f"CCTV: Starting recording on {camera_id}")

        async with self._lock:
            if camera_id not in self._cameras:
                return {
                    "success": False,
                    "error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다",
                }

            camera = self._cameras[camera_id]
            if camera.state == CameraState.OFFLINE:
                return {
                    "success": False,
                    "error": f"카메라 '{camera.name}'이(가) 오프라인 상태입니다",
                }

            if camera.is_recording:
                return {
                    "success": False,
                    "error": f"카메라 '{camera.name}'은(는) 이미 녹화 중입니다",
                }

            # 어댑터를 통한 녹화 시작
            adapter = self._get_adapter_for_camera(camera)

            if not adapter.is_connected:
                await adapter.connect()

            response = await adapter.start_recording()

            # 로컬 상태 업데이트 (실제 장치 성공/실패 무관)
            camera.is_recording = True
            camera.state = CameraState.RECORDING

            recording = Recording(
                recording_id=f"rec_{camera_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                camera_id=camera_id,
                start_time=datetime.now(),
                quality=RecordingQuality(quality),
            )
            self._active_recordings[camera_id] = recording
            self._recordings.append(recording)

            duration_text = f"{duration}분" if duration > 0 else "수동 중지까지"
            return {
                "success": True,
                "camera_id": camera_id,
                "camera_name": camera.name,
                "recording_id": recording.recording_id,
                "action": "recording_started",
                "duration": duration,
                "quality": quality,
                "message": f"🔴 {camera.name} 녹화를 시작했습니다 (품질: {quality}, 시간: {duration_text})",
            }

    async def stop_recording(
        self,
        camera_id: str,
    ) -> Dict[str, Any]:
        """
        녹화 중지

        Args:
            camera_id: 카메라 ID

        Returns:
            실행 결과
        """
        camera_id = self._normalize_camera_id(camera_id)
        logger.info(f"CCTV: Stopping recording on {camera_id}")

        async with self._lock:
            if camera_id not in self._cameras:
                return {
                    "success": False,
                    "error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다",
                }

            camera = self._cameras[camera_id]
            if not camera.is_recording:
                return {
                    "success": False,
                    "error": f"카메라 '{camera.name}'은(는) 녹화 중이 아닙니다",
                }

            # 어댑터를 통한 녹화 중지
            adapter = self._get_adapter_for_camera(camera)

            if not adapter.is_connected:
                await adapter.connect()

            await adapter.stop_recording()

            # 로컬 상태 업데이트
            camera.is_recording = False
            camera.state = CameraState.ONLINE

            recording = self._active_recordings.pop(camera_id, None)
            duration = 0
            if recording:
                recording.end_time = datetime.now()
                duration = (recording.end_time - recording.start_time).total_seconds()

            return {
                "success": True,
                "camera_id": camera_id,
                "camera_name": camera.name,
                "recording_id": recording.recording_id if recording else None,
                "action": "recording_stopped",
                "duration_seconds": duration,
                "message": f"⏹️ {camera.name} 녹화가 중지되었습니다",
            }

    async def capture_snapshot(
        self,
        camera_id: str,
        resolution: str = "1080p",
    ) -> Dict[str, Any]:
        """
        스냅샷 캡처

        Args:
            camera_id: 카메라 ID
            resolution: 해상도

        Returns:
            실행 결과
        """
        camera_id = self._normalize_camera_id(camera_id)
        logger.info(f"CCTV: Capturing snapshot from {camera_id}")

        async with self._lock:
            if camera_id not in self._cameras:
                return {
                    "success": False,
                    "error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다",
                }

            camera = self._cameras[camera_id]
            if camera.state == CameraState.OFFLINE:
                return {
                    "success": False,
                    "error": f"카메라 '{camera.name}'이(가) 오프라인 상태입니다",
                }

            # 어댑터를 통한 스냅샷 캡처
            adapter = self._get_adapter_for_camera(camera)

            if not adapter.is_connected:
                await adapter.connect()

            response = await adapter.capture_snapshot(resolution=resolution)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{camera_id}_{timestamp}.jpg"

            result = {
                "success": response.success,
                "camera_id": camera_id,
                "camera_name": camera.name,
                "filename": filename,
                "resolution": resolution,
                "timestamp": timestamp,
                "action": "snapshot_captured",
                "message": f"📸 {camera.name} 스냅샷이 캡처되었습니다 ({filename})",
            }

            # 실제 이미지 데이터가 있으면 포함
            if response.result and "image_base64" in response.result:
                result["image_base64"] = response.result["image_base64"]
            elif response.result and "snapshot_uri" in response.result:
                result["snapshot_uri"] = response.result["snapshot_uri"]

            return result

    async def get_camera_status(
        self,
        camera_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        카메라 상태 조회

        Args:
            camera_id: 카메라 ID (없으면 전체 조회)

        Returns:
            상태 정보
        """
        if camera_id:
            camera_id = self._normalize_camera_id(camera_id)
            if camera_id not in self._cameras:
                return {"error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다"}

            camera = self._cameras[camera_id]
            return {
                "camera_id": camera.camera_id,
                "name": camera.name,
                "location": camera.location,
                "state": camera.state.value,
                "is_recording": camera.is_recording,
                "motion_detection": camera.motion_detection,
                "position": {
                    "pan": camera.position.pan,
                    "tilt": camera.position.tilt,
                    "zoom": camera.position.zoom,
                },
                "presets": list(camera.presets.keys()),
                "is_real_device": camera.is_real_device,
                "manufacturer": camera.manufacturer,
            }
        else:
            online_count = sum(1 for c in self._cameras.values() if c.state != CameraState.OFFLINE)
            recording_count = sum(1 for c in self._cameras.values() if c.is_recording)
            real_device_count = sum(1 for c in self._cameras.values() if c.is_real_device)

            return {
                "total": len(self._cameras),
                "online": online_count,
                "recording": recording_count,
                "real_devices": real_device_count,
                "mode": self._mode,
                "cameras": [
                    {
                        "camera_id": c.camera_id,
                        "name": c.name,
                        "location": c.location,
                        "state": c.state.value,
                        "is_recording": c.is_recording,
                        "is_real_device": c.is_real_device,
                    }
                    for c in self._cameras.values()
                ]
            }

    async def get_recording_list(
        self,
        camera_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """녹화 영상 목록 조회"""
        recordings = self._recordings.copy()

        if camera_id:
            camera_id = self._normalize_camera_id(camera_id)
            recordings = [r for r in recordings if r.camera_id == camera_id]

        recordings = sorted(recordings, key=lambda x: x.start_time, reverse=True)[:limit]

        return {
            "total": len(recordings),
            "recordings": [
                {
                    "recording_id": r.recording_id,
                    "camera_id": r.camera_id,
                    "start_time": r.start_time.isoformat(),
                    "end_time": r.end_time.isoformat() if r.end_time else None,
                    "quality": r.quality.value,
                    "status": "completed" if r.end_time else "recording",
                }
                for r in recordings
            ]
        }

    async def set_motion_detection(
        self,
        camera_id: str,
        enabled: bool,
        sensitivity: str = "medium",
    ) -> Dict[str, Any]:
        """모션 감지 설정"""
        camera_id = self._normalize_camera_id(camera_id)
        logger.info(f"CCTV: Setting motion detection on {camera_id} to {enabled}")

        async with self._lock:
            if camera_id not in self._cameras:
                return {"success": False, "error": f"카메라 '{camera_id}'을(를) 찾을 수 없습니다"}

            camera = self._cameras[camera_id]
            camera.motion_detection = enabled
            camera.motion_sensitivity = sensitivity

            status = "활성화" if enabled else "비활성화"
            return {
                "success": True,
                "camera_id": camera_id,
                "camera_name": camera.name,
                "motion_detection": enabled,
                "sensitivity": sensitivity,
                "message": f"✅ {camera.name} 모션 감지가 {status}되었습니다 (민감도: {sensitivity})",
            }

    def set_mode(self, mode: str):
        """
        제어 모드 변경

        Args:
            mode: "simulation", "real", "hybrid"
        """
        self._mode = mode
        self._adapter_factory.set_mode(mode)
        logger.info(f"CCTV Controller mode changed to '{mode}'")


# 동기 버전 래퍼
class CCTVControllerSync:
    """동기식 CCTV Controller 래퍼"""

    def __init__(self, *args, **kwargs):
        self._async_controller = CCTVController(*args, **kwargs)

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def move_camera(self, *args, **kwargs):
        return self._run(self._async_controller.move_camera(*args, **kwargs))

    def go_to_preset(self, *args, **kwargs):
        return self._run(self._async_controller.go_to_preset(*args, **kwargs))

    def save_preset(self, *args, **kwargs):
        return self._run(self._async_controller.save_preset(*args, **kwargs))

    def start_recording(self, *args, **kwargs):
        return self._run(self._async_controller.start_recording(*args, **kwargs))

    def stop_recording(self, *args, **kwargs):
        return self._run(self._async_controller.stop_recording(*args, **kwargs))

    def capture_snapshot(self, *args, **kwargs):
        return self._run(self._async_controller.capture_snapshot(*args, **kwargs))

    def get_camera_status(self, *args, **kwargs):
        return self._run(self._async_controller.get_camera_status(*args, **kwargs))

    def get_recording_list(self, *args, **kwargs):
        return self._run(self._async_controller.get_recording_list(*args, **kwargs))

    def set_motion_detection(self, *args, **kwargs):
        return self._run(self._async_controller.set_motion_detection(*args, **kwargs))
