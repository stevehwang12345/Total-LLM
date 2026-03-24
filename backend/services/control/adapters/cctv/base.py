"""
Base CCTV Adapter Module
CCTV 장치 어댑터의 기본 클래스

이 모듈은 모든 CCTV 어댑터가 구현해야 하는 인터페이스를 정의합니다.
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from ..base import (
    BaseDeviceAdapter,
    DeviceCommand,
    DeviceResponse,
    DeviceType,
    CommandStatus
)


class PTZDirection(str, Enum):
    """PTZ 이동 방향"""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UP_LEFT = "up_left"
    UP_RIGHT = "up_right"
    DOWN_LEFT = "down_left"
    DOWN_RIGHT = "down_right"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    STOP = "stop"


class RecordingStatus(str, Enum):
    """녹화 상태"""
    RECORDING = "recording"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"


class StreamProtocol(str, Enum):
    """스트리밍 프로토콜"""
    RTSP = "rtsp"
    HTTP = "http"
    HLS = "hls"
    WEBRTC = "webrtc"


@dataclass
class PTZPosition:
    """PTZ 위치 정보"""
    pan: float = 0.0       # -180 ~ 180
    tilt: float = 0.0      # -90 ~ 90
    zoom: float = 1.0      # 1.0 ~ max_zoom
    is_normalized: bool = True  # 정규화된 값인지 여부


@dataclass
class PTZLimits:
    """PTZ 제한 범위"""
    pan_min: float = -180.0
    pan_max: float = 180.0
    tilt_min: float = -90.0
    tilt_max: float = 90.0
    zoom_min: float = 1.0
    zoom_max: float = 20.0


@dataclass
class Preset:
    """프리셋 정보"""
    preset_id: str
    name: str
    position: Optional[PTZPosition] = None
    thumbnail: Optional[str] = None  # Base64 또는 URL


@dataclass
class StreamInfo:
    """스트림 정보"""
    url: str
    protocol: StreamProtocol
    resolution: str = "1920x1080"
    fps: int = 30
    codec: str = "H.264"
    is_main_stream: bool = True


class BaseCCTVAdapter(BaseDeviceAdapter):
    """
    CCTV 장치 어댑터 기본 클래스

    모든 CCTV 어댑터(ONVIF, Hanwha, Hikvision 등)는 이 클래스를 상속합니다.
    """

    def __init__(self, device_info: Dict[str, Any]):
        # CCTV 타입으로 강제 설정
        device_info["device_type"] = DeviceType.CCTV.value
        super().__init__(device_info)

        # CCTV 전용 속성
        self._ptz_limits = PTZLimits()
        self._current_position = PTZPosition()
        self._presets: Dict[str, Preset] = {}
        self._recording_status = RecordingStatus.STOPPED
        self._has_ptz = device_info.get("has_ptz", True)
        self._has_audio = device_info.get("has_audio", False)
        self._has_ir = device_info.get("has_ir", False)

    @property
    def has_ptz(self) -> bool:
        """PTZ 지원 여부"""
        return self._has_ptz

    @property
    def recording_status(self) -> RecordingStatus:
        """현재 녹화 상태"""
        return self._recording_status

    @property
    def current_position(self) -> PTZPosition:
        """현재 PTZ 위치"""
        return self._current_position

    # ==================== PTZ Control ====================

    @abstractmethod
    async def move_ptz(
        self,
        pan: Optional[float] = None,
        tilt: Optional[float] = None,
        zoom: Optional[float] = None,
        speed: float = 0.5
    ) -> DeviceResponse:
        """
        PTZ 이동 (절대 위치)

        Args:
            pan: 팬 각도 (-180 ~ 180)
            tilt: 틸트 각도 (-90 ~ 90)
            zoom: 줌 배율 (1.0 ~ max)
            speed: 이동 속도 (0.0 ~ 1.0)

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def move_continuous(
        self,
        direction: PTZDirection,
        speed: float = 0.5
    ) -> DeviceResponse:
        """
        PTZ 연속 이동

        Args:
            direction: 이동 방향
            speed: 이동 속도 (0.0 ~ 1.0)

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def stop_ptz(self) -> DeviceResponse:
        """
        PTZ 이동 정지

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def go_to_preset(self, preset_id: str) -> DeviceResponse:
        """
        프리셋 위치로 이동

        Args:
            preset_id: 프리셋 ID

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def set_preset(self, preset_id: str, name: str) -> DeviceResponse:
        """
        현재 위치를 프리셋으로 저장

        Args:
            preset_id: 프리셋 ID
            name: 프리셋 이름

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def get_presets(self) -> List[Preset]:
        """
        프리셋 목록 조회

        Returns:
            List[Preset]: 프리셋 목록
        """
        pass

    @abstractmethod
    async def get_ptz_position(self) -> PTZPosition:
        """
        현재 PTZ 위치 조회

        Returns:
            PTZPosition: 현재 위치
        """
        pass

    # ==================== Recording Control ====================

    @abstractmethod
    async def start_recording(self) -> DeviceResponse:
        """
        녹화 시작

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def stop_recording(self) -> DeviceResponse:
        """
        녹화 중지

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        pass

    @abstractmethod
    async def get_recording_status(self) -> RecordingStatus:
        """
        녹화 상태 조회

        Returns:
            RecordingStatus: 현재 녹화 상태
        """
        pass

    # ==================== Snapshot & Streaming ====================

    @abstractmethod
    async def capture_snapshot(
        self,
        resolution: str = "1920x1080"
    ) -> DeviceResponse:
        """
        스냅샷 캡처

        Args:
            resolution: 해상도

        Returns:
            DeviceResponse: result에 {"image_base64": "..."} 포함
        """
        pass

    @abstractmethod
    async def get_stream_url(
        self,
        protocol: StreamProtocol = StreamProtocol.RTSP,
        stream_type: str = "main"
    ) -> StreamInfo:
        """
        스트림 URL 조회

        Args:
            protocol: 스트리밍 프로토콜
            stream_type: 스트림 타입 ("main", "sub")

        Returns:
            StreamInfo: 스트림 정보
        """
        pass

    # ==================== Command Execution ====================

    async def execute(self, command: DeviceCommand) -> DeviceResponse:
        """
        CCTV 명령 실행 디스패처

        지원 액션:
        - move_ptz: PTZ 이동
        - move_continuous: 연속 이동
        - stop_ptz: PTZ 정지
        - go_to_preset: 프리셋 이동
        - set_preset: 프리셋 저장
        - start_recording: 녹화 시작
        - stop_recording: 녹화 중지
        - capture_snapshot: 스냅샷
        - get_stream_url: 스트림 URL
        """
        action = command.action.lower()
        params = command.parameters

        try:
            if action == "move_ptz":
                return await self.move_ptz(
                    pan=params.get("pan"),
                    tilt=params.get("tilt"),
                    zoom=params.get("zoom"),
                    speed=params.get("speed", 0.5)
                )
            elif action == "move_continuous":
                direction = PTZDirection(params.get("direction", "stop"))
                return await self.move_continuous(
                    direction=direction,
                    speed=params.get("speed", 0.5)
                )
            elif action == "stop_ptz":
                return await self.stop_ptz()
            elif action == "go_to_preset":
                return await self.go_to_preset(params.get("preset_id", "1"))
            elif action == "set_preset":
                return await self.set_preset(
                    preset_id=params.get("preset_id", "1"),
                    name=params.get("name", "Preset")
                )
            elif action == "start_recording":
                return await self.start_recording()
            elif action == "stop_recording":
                return await self.stop_recording()
            elif action == "capture_snapshot":
                return await self.capture_snapshot(
                    resolution=params.get("resolution", "1920x1080")
                )
            elif action == "get_stream_url":
                protocol = StreamProtocol(params.get("protocol", "rtsp"))
                stream_info = await self.get_stream_url(
                    protocol=protocol,
                    stream_type=params.get("stream_type", "main")
                )
                return DeviceResponse(
                    success=True,
                    device_id=self.device_id,
                    action=action,
                    result={"stream_url": stream_info.url, "protocol": stream_info.protocol.value}
                )
            else:
                return DeviceResponse(
                    success=False,
                    device_id=self.device_id,
                    action=action,
                    status=CommandStatus.NOT_SUPPORTED,
                    error=f"Unsupported action: {action}"
                )
        except Exception as e:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action=action,
                status=CommandStatus.FAILED,
                error=str(e)
            )
