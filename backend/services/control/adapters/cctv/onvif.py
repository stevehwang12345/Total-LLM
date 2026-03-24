"""
ONVIF Adapter Module
ONVIF 프로토콜 기반 CCTV 어댑터

ONVIF 표준을 지원하는 모든 IP 카메라와 호환됩니다.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..base import (
    DeviceResponse,
    ConnectionStatus,
    CommandStatus
)
from .base import (
    BaseCCTVAdapter,
    PTZPosition,
    PTZDirection,
    Preset,
    RecordingStatus,
    StreamInfo,
    StreamProtocol
)

logger = logging.getLogger(__name__)

# ONVIF 라이브러리 가용성 확인
try:
    from onvif import ONVIFCamera
    from zeep.exceptions import Fault
    ONVIF_AVAILABLE = True
except ImportError:
    ONVIF_AVAILABLE = False
    logger.warning(
        "ONVIF libraries not available. Install with: "
        "pip install onvif-zeep zeep"
    )


class ONVIFAdapter(BaseCCTVAdapter):
    """
    ONVIF 프로토콜 어댑터

    ONVIF 표준을 지원하는 IP 카메라를 제어합니다.
    주요 지원 기능:
    - PTZ 제어 (절대/상대/연속 이동)
    - 프리셋 관리
    - 스냅샷 캡처
    - 스트림 URL 조회
    """

    def __init__(self, device_info: Dict[str, Any]):
        super().__init__(device_info)

        # ONVIF 전용 속성
        self._onvif_camera: Optional[Any] = None
        self._ptz_service: Optional[Any] = None
        self._media_service: Optional[Any] = None
        self._imaging_service: Optional[Any] = None
        self._device_service: Optional[Any] = None

        # 프로파일 정보
        self._media_profile: Optional[Any] = None
        self._ptz_configuration: Optional[Any] = None

        # WSDL 캐시 설정
        self._wsdl_dir = device_info.get("wsdl_dir", None)

        if not ONVIF_AVAILABLE:
            logger.error(
                f"ONVIF adapter created for {self.device_id} but ONVIF library not available"
            )

    async def connect(self) -> bool:
        """
        ONVIF 카메라 연결

        Returns:
            bool: 연결 성공 여부
        """
        if not ONVIF_AVAILABLE:
            self._connection_status = ConnectionStatus.ERROR
            logger.error("ONVIF library not available")
            return False

        try:
            self._connection_status = ConnectionStatus.CONNECTING

            # 비동기 실행을 위해 executor 사용
            loop = asyncio.get_event_loop()
            self._onvif_camera = await loop.run_in_executor(
                None,
                lambda: ONVIFCamera(
                    self.ip,
                    self.port,
                    self.username,
                    self.password,
                    self._wsdl_dir
                )
            )

            # 서비스 초기화
            self._device_service = self._onvif_camera.create_devicemgmt_service()
            self._media_service = self._onvif_camera.create_media_service()

            # 미디어 프로파일 가져오기
            profiles = await loop.run_in_executor(
                None,
                self._media_service.GetProfiles
            )
            if profiles:
                self._media_profile = profiles[0]

            # PTZ 서비스 시도
            try:
                self._ptz_service = self._onvif_camera.create_ptz_service()
                self._has_ptz = True

                # PTZ 설정 가져오기
                if self._media_profile:
                    ptz_configs = await loop.run_in_executor(
                        None,
                        lambda: self._ptz_service.GetConfigurations()
                    )
                    if ptz_configs:
                        self._ptz_configuration = ptz_configs[0]

            except Exception as e:
                logger.info(f"PTZ service not available for {self.device_id}: {e}")
                self._has_ptz = False

            self._connection_status = ConnectionStatus.CONNECTED
            self._update_communication_time()
            self._reset_error_count()

            logger.info(f"ONVIF camera {self.device_id} connected successfully")
            return True

        except Exception as e:
            self._connection_status = ConnectionStatus.ERROR
            self._record_error(str(e))
            logger.error(f"Failed to connect ONVIF camera {self.device_id}: {e}")
            return False

    async def disconnect(self) -> bool:
        """
        ONVIF 카메라 연결 해제

        Returns:
            bool: 연결 해제 성공 여부
        """
        self._onvif_camera = None
        self._ptz_service = None
        self._media_service = None
        self._device_service = None
        self._media_profile = None
        self._connection_status = ConnectionStatus.DISCONNECTED

        logger.info(f"ONVIF camera {self.device_id} disconnected")
        return True

    async def get_status(self) -> Dict[str, Any]:
        """
        장치 상태 조회

        Returns:
            Dict: 장치 상태 정보
        """
        if not self.is_connected:
            return {
                "device_id": self.device_id,
                "connection_status": self._connection_status.value,
                "error": "Not connected"
            }

        try:
            loop = asyncio.get_event_loop()

            # 장치 정보 조회
            device_info = await loop.run_in_executor(
                None,
                self._device_service.GetDeviceInformation
            )

            status = {
                "device_id": self.device_id,
                "connection_status": self._connection_status.value,
                "manufacturer": device_info.Manufacturer if device_info else self.manufacturer,
                "model": device_info.Model if device_info else self.model,
                "firmware_version": device_info.FirmwareVersion if device_info else "",
                "serial_number": device_info.SerialNumber if device_info else "",
                "has_ptz": self._has_ptz,
                "protocol": "onvif"
            }

            # PTZ 위치 조회 (가능한 경우)
            if self._has_ptz and self._ptz_service:
                try:
                    position = await self.get_ptz_position()
                    status["position"] = {
                        "pan": position.pan,
                        "tilt": position.tilt,
                        "zoom": position.zoom
                    }
                except Exception:
                    pass

            self._update_communication_time()
            return status

        except Exception as e:
            self._record_error(str(e))
            return {
                "device_id": self.device_id,
                "connection_status": self._connection_status.value,
                "error": str(e)
            }

    async def get_capabilities(self) -> List[str]:
        """
        장치 기능 목록 조회

        Returns:
            List[str]: 지원 기능 목록
        """
        capabilities = ["streaming", "snapshot"]

        if self._has_ptz:
            capabilities.extend([
                "ptz_move",
                "ptz_continuous",
                "ptz_stop",
                "preset"
            ])

        if self._media_service:
            capabilities.append("media_profiles")

        return capabilities

    async def move_ptz(
        self,
        pan: Optional[float] = None,
        tilt: Optional[float] = None,
        zoom: Optional[float] = None,
        speed: float = 0.5
    ) -> DeviceResponse:
        """
        PTZ 절대 위치 이동

        Args:
            pan: 팬 각도 (-1.0 ~ 1.0, ONVIF 정규화)
            tilt: 틸트 각도 (-1.0 ~ 1.0, ONVIF 정규화)
            zoom: 줌 레벨 (0.0 ~ 1.0, ONVIF 정규화)
            speed: 이동 속도 (0.0 ~ 1.0)

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        if not self._has_ptz or not self._ptz_service:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="move_ptz",
                status=CommandStatus.NOT_SUPPORTED,
                error="PTZ not supported"
            )

        if not self.is_connected:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="move_ptz",
                status=CommandStatus.FAILED,
                error="Not connected"
            )

        try:
            loop = asyncio.get_event_loop()

            # ONVIF PTZ 요청 생성
            request = self._ptz_service.create_type('AbsoluteMove')
            request.ProfileToken = self._media_profile.token

            # 위치 설정
            request.Position = {
                'PanTilt': {
                    'x': pan if pan is not None else 0,
                    'y': tilt if tilt is not None else 0
                },
                'Zoom': {
                    'x': zoom if zoom is not None else 0
                }
            }

            # 속도 설정
            request.Speed = {
                'PanTilt': {'x': speed, 'y': speed},
                'Zoom': {'x': speed}
            }

            await loop.run_in_executor(
                None,
                lambda: self._ptz_service.AbsoluteMove(request)
            )

            # 현재 위치 업데이트
            if pan is not None:
                self._current_position.pan = pan
            if tilt is not None:
                self._current_position.tilt = tilt
            if zoom is not None:
                self._current_position.zoom = zoom

            self._update_communication_time()

            return DeviceResponse(
                success=True,
                device_id=self.device_id,
                action="move_ptz",
                result={
                    "pan": self._current_position.pan,
                    "tilt": self._current_position.tilt,
                    "zoom": self._current_position.zoom
                }
            )

        except Exception as e:
            self._record_error(str(e))
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="move_ptz",
                status=CommandStatus.FAILED,
                error=str(e)
            )

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
        if not self._has_ptz or not self._ptz_service:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="move_continuous",
                status=CommandStatus.NOT_SUPPORTED,
                error="PTZ not supported"
            )

        if not self.is_connected:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="move_continuous",
                status=CommandStatus.FAILED,
                error="Not connected"
            )

        try:
            loop = asyncio.get_event_loop()

            # 방향에 따른 속도 벡터 계산
            pan_speed = 0.0
            tilt_speed = 0.0
            zoom_speed = 0.0

            if direction == PTZDirection.UP:
                tilt_speed = speed
            elif direction == PTZDirection.DOWN:
                tilt_speed = -speed
            elif direction == PTZDirection.LEFT:
                pan_speed = -speed
            elif direction == PTZDirection.RIGHT:
                pan_speed = speed
            elif direction == PTZDirection.UP_LEFT:
                pan_speed = -speed
                tilt_speed = speed
            elif direction == PTZDirection.UP_RIGHT:
                pan_speed = speed
                tilt_speed = speed
            elif direction == PTZDirection.DOWN_LEFT:
                pan_speed = -speed
                tilt_speed = -speed
            elif direction == PTZDirection.DOWN_RIGHT:
                pan_speed = speed
                tilt_speed = -speed
            elif direction == PTZDirection.ZOOM_IN:
                zoom_speed = speed
            elif direction == PTZDirection.ZOOM_OUT:
                zoom_speed = -speed
            elif direction == PTZDirection.STOP:
                return await self.stop_ptz()

            # ONVIF ContinuousMove 요청
            request = self._ptz_service.create_type('ContinuousMove')
            request.ProfileToken = self._media_profile.token
            request.Velocity = {
                'PanTilt': {'x': pan_speed, 'y': tilt_speed},
                'Zoom': {'x': zoom_speed}
            }

            await loop.run_in_executor(
                None,
                lambda: self._ptz_service.ContinuousMove(request)
            )

            self._update_communication_time()

            return DeviceResponse(
                success=True,
                device_id=self.device_id,
                action="move_continuous",
                result={
                    "direction": direction.value,
                    "speed": speed
                }
            )

        except Exception as e:
            self._record_error(str(e))
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="move_continuous",
                status=CommandStatus.FAILED,
                error=str(e)
            )

    async def stop_ptz(self) -> DeviceResponse:
        """
        PTZ 이동 정지

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        if not self._has_ptz or not self._ptz_service:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="stop_ptz",
                status=CommandStatus.NOT_SUPPORTED,
                error="PTZ not supported"
            )

        if not self.is_connected:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="stop_ptz",
                status=CommandStatus.FAILED,
                error="Not connected"
            )

        try:
            loop = asyncio.get_event_loop()

            request = self._ptz_service.create_type('Stop')
            request.ProfileToken = self._media_profile.token
            request.PanTilt = True
            request.Zoom = True

            await loop.run_in_executor(
                None,
                lambda: self._ptz_service.Stop(request)
            )

            self._update_communication_time()

            return DeviceResponse(
                success=True,
                device_id=self.device_id,
                action="stop_ptz",
                result={"message": "PTZ movement stopped"}
            )

        except Exception as e:
            self._record_error(str(e))
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="stop_ptz",
                status=CommandStatus.FAILED,
                error=str(e)
            )

    async def go_to_preset(self, preset_id: str) -> DeviceResponse:
        """
        프리셋 위치로 이동

        Args:
            preset_id: 프리셋 ID 또는 토큰

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        if not self._has_ptz or not self._ptz_service:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="go_to_preset",
                status=CommandStatus.NOT_SUPPORTED,
                error="PTZ not supported"
            )

        if not self.is_connected:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="go_to_preset",
                status=CommandStatus.FAILED,
                error="Not connected"
            )

        try:
            loop = asyncio.get_event_loop()

            request = self._ptz_service.create_type('GotoPreset')
            request.ProfileToken = self._media_profile.token
            request.PresetToken = preset_id

            await loop.run_in_executor(
                None,
                lambda: self._ptz_service.GotoPreset(request)
            )

            self._update_communication_time()

            return DeviceResponse(
                success=True,
                device_id=self.device_id,
                action="go_to_preset",
                result={"preset_id": preset_id}
            )

        except Exception as e:
            self._record_error(str(e))
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="go_to_preset",
                status=CommandStatus.FAILED,
                error=str(e)
            )

    async def set_preset(self, preset_id: str, name: str) -> DeviceResponse:
        """
        현재 위치를 프리셋으로 저장

        Args:
            preset_id: 프리셋 ID (토큰)
            name: 프리셋 이름

        Returns:
            DeviceResponse: 명령 실행 결과
        """
        if not self._has_ptz or not self._ptz_service:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="set_preset",
                status=CommandStatus.NOT_SUPPORTED,
                error="PTZ not supported"
            )

        if not self.is_connected:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="set_preset",
                status=CommandStatus.FAILED,
                error="Not connected"
            )

        try:
            loop = asyncio.get_event_loop()

            request = self._ptz_service.create_type('SetPreset')
            request.ProfileToken = self._media_profile.token
            request.PresetName = name

            result = await loop.run_in_executor(
                None,
                lambda: self._ptz_service.SetPreset(request)
            )

            preset_token = result if isinstance(result, str) else preset_id

            # 내부 프리셋 목록 업데이트
            self._presets[preset_token] = Preset(
                preset_id=preset_token,
                name=name,
                position=PTZPosition(
                    pan=self._current_position.pan,
                    tilt=self._current_position.tilt,
                    zoom=self._current_position.zoom
                )
            )

            self._update_communication_time()

            return DeviceResponse(
                success=True,
                device_id=self.device_id,
                action="set_preset",
                result={"preset_id": preset_token, "name": name}
            )

        except Exception as e:
            self._record_error(str(e))
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="set_preset",
                status=CommandStatus.FAILED,
                error=str(e)
            )

    async def get_presets(self) -> List[Preset]:
        """
        프리셋 목록 조회

        Returns:
            List[Preset]: 프리셋 목록
        """
        if not self._has_ptz or not self._ptz_service:
            return []

        if not self.is_connected:
            return list(self._presets.values())

        try:
            loop = asyncio.get_event_loop()

            presets_response = await loop.run_in_executor(
                None,
                lambda: self._ptz_service.GetPresets(self._media_profile.token)
            )

            presets = []
            for p in presets_response:
                preset = Preset(
                    preset_id=p.token,
                    name=p.Name if hasattr(p, 'Name') else p.token
                )
                if hasattr(p, 'PTZPosition'):
                    preset.position = PTZPosition(
                        pan=p.PTZPosition.PanTilt.x if hasattr(p.PTZPosition, 'PanTilt') else 0,
                        tilt=p.PTZPosition.PanTilt.y if hasattr(p.PTZPosition, 'PanTilt') else 0,
                        zoom=p.PTZPosition.Zoom.x if hasattr(p.PTZPosition, 'Zoom') else 1
                    )
                presets.append(preset)
                self._presets[preset.preset_id] = preset

            self._update_communication_time()
            return presets

        except Exception as e:
            self._record_error(str(e))
            return list(self._presets.values())

    async def get_ptz_position(self) -> PTZPosition:
        """
        현재 PTZ 위치 조회

        Returns:
            PTZPosition: 현재 위치
        """
        if not self._has_ptz or not self._ptz_service:
            return self._current_position

        if not self.is_connected:
            return self._current_position

        try:
            loop = asyncio.get_event_loop()

            status = await loop.run_in_executor(
                None,
                lambda: self._ptz_service.GetStatus(self._media_profile.token)
            )

            if hasattr(status, 'Position'):
                pos = status.Position
                self._current_position = PTZPosition(
                    pan=pos.PanTilt.x if hasattr(pos, 'PanTilt') else 0,
                    tilt=pos.PanTilt.y if hasattr(pos, 'PanTilt') else 0,
                    zoom=pos.Zoom.x if hasattr(pos, 'Zoom') else 1,
                    is_normalized=True
                )

            self._update_communication_time()
            return self._current_position

        except Exception as e:
            self._record_error(str(e))
            return self._current_position

    async def start_recording(self) -> DeviceResponse:
        """
        녹화 시작 (ONVIF Recording 서비스 필요)

        Note: 대부분의 카메라는 별도 NVR이 필요합니다.
        """
        return DeviceResponse(
            success=False,
            device_id=self.device_id,
            action="start_recording",
            status=CommandStatus.NOT_SUPPORTED,
            error="Recording requires NVR integration"
        )

    async def stop_recording(self) -> DeviceResponse:
        """녹화 중지"""
        return DeviceResponse(
            success=False,
            device_id=self.device_id,
            action="stop_recording",
            status=CommandStatus.NOT_SUPPORTED,
            error="Recording requires NVR integration"
        )

    async def get_recording_status(self) -> RecordingStatus:
        """녹화 상태 조회"""
        return RecordingStatus.STOPPED

    async def capture_snapshot(
        self,
        resolution: str = "1920x1080"
    ) -> DeviceResponse:
        """
        스냅샷 캡처

        Args:
            resolution: 해상도 (무시됨 - 프로파일 기본 해상도 사용)

        Returns:
            DeviceResponse: result에 {"image_base64": "..."} 포함
        """
        if not self.is_connected or not self._media_service:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="capture_snapshot",
                status=CommandStatus.FAILED,
                error="Not connected"
            )

        try:
            loop = asyncio.get_event_loop()

            # 스냅샷 URI 가져오기
            snapshot_uri = await loop.run_in_executor(
                None,
                lambda: self._media_service.GetSnapshotUri(self._media_profile.token)
            )

            # 실제 스냅샷 다운로드는 HTTP 요청 필요
            # 여기서는 URI만 반환
            self._update_communication_time()

            return DeviceResponse(
                success=True,
                device_id=self.device_id,
                action="capture_snapshot",
                result={
                    "snapshot_uri": snapshot_uri.Uri,
                    "resolution": resolution,
                    "timestamp": datetime.now().isoformat()
                }
            )

        except Exception as e:
            self._record_error(str(e))
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="capture_snapshot",
                status=CommandStatus.FAILED,
                error=str(e)
            )

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
        if not self.is_connected or not self._media_service:
            # 기본 RTSP URL 반환
            return StreamInfo(
                url=f"rtsp://{self.username}:{self.password}@{self.ip}:{554}/stream1",
                protocol=protocol,
                resolution="unknown",
                is_main_stream=(stream_type == "main")
            )

        try:
            loop = asyncio.get_event_loop()

            # 미디어 프로파일 선택 (main/sub)
            profiles = await loop.run_in_executor(
                None,
                self._media_service.GetProfiles
            )

            profile = profiles[0]  # 기본값
            if stream_type == "sub" and len(profiles) > 1:
                profile = profiles[1]

            # 스트림 URI 가져오기
            stream_setup = {
                'Stream': 'RTP-Unicast',
                'Transport': {'Protocol': protocol.value.upper()}
            }

            stream_uri = await loop.run_in_executor(
                None,
                lambda: self._media_service.GetStreamUri(stream_setup, profile.token)
            )

            # 해상도 정보 추출
            resolution = "1920x1080"
            if hasattr(profile, 'VideoEncoderConfiguration'):
                vec = profile.VideoEncoderConfiguration
                if hasattr(vec, 'Resolution'):
                    resolution = f"{vec.Resolution.Width}x{vec.Resolution.Height}"

            self._update_communication_time()

            return StreamInfo(
                url=stream_uri.Uri,
                protocol=protocol,
                resolution=resolution,
                is_main_stream=(stream_type == "main")
            )

        except Exception as e:
            self._record_error(str(e))
            # 폴백: 기본 RTSP URL
            return StreamInfo(
                url=f"rtsp://{self.username}:{self.password}@{self.ip}:{554}/stream1",
                protocol=protocol,
                resolution="unknown",
                is_main_stream=(stream_type == "main")
            )
