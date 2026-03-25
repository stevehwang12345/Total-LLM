"""
Simulation Adapters Module
시뮬레이션 어댑터

실제 장치 없이 시스템을 테스트할 수 있는 시뮬레이션 어댑터입니다.
"""

import asyncio
import base64
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import (
    BaseDeviceAdapter,
    DeviceCommand,
    DeviceResponse,
    DeviceType,
    ConnectionStatus,
    CommandStatus
)
from .cctv.base import (
    BaseCCTVAdapter,
    PTZPosition,
    PTZDirection,
    Preset,
    RecordingStatus,
    StreamInfo,
    StreamProtocol
)
from .acu.base import (
    BaseACUAdapter,
    DoorInfo,
    DoorStatus,
    AccessLog,
    AccessType,
    AccessResult,
    AlarmEvent,
    AlarmType
)

logger = logging.getLogger(__name__)


class SimulationCCTVAdapter(BaseCCTVAdapter):
    """
    CCTV 시뮬레이션 어댑터

    실제 카메라 없이 CCTV 제어를 시뮬레이션합니다.
    """

    def __init__(self, device_info: Dict[str, Any]):
        super().__init__(device_info)

        # 시뮬레이션 상태
        self._current_position = PTZPosition(pan=0.0, tilt=0.0, zoom=1.0)
        self._recording_status = RecordingStatus.STOPPED
        self._presets = {
            "1": Preset(preset_id="1", name="홈 포지션", position=PTZPosition(0, 0, 1)),
            "2": Preset(preset_id="2", name="정문", position=PTZPosition(-45, -10, 2)),
            "3": Preset(preset_id="3", name="주차장", position=PTZPosition(90, -20, 3)),
        }

        # 시뮬레이션 설정
        self._response_delay_ms = device_info.get("simulation_delay_ms", 100)

        logger.info(f"SimulationCCTVAdapter created for {self.device_id}")

    async def _simulate_delay(self):
        """응답 지연 시뮬레이션"""
        if self._response_delay_ms > 0:
            await asyncio.sleep(self._response_delay_ms / 1000)

    async def connect(self) -> bool:
        """연결 시뮬레이션"""
        await self._simulate_delay()
        self._connection_status = ConnectionStatus.CONNECTED
        self._update_communication_time()
        logger.info(f"[SIMULATION] {self.device_id} connected")
        return True

    async def disconnect(self) -> bool:
        """연결 해제 시뮬레이션"""
        await self._simulate_delay()
        self._connection_status = ConnectionStatus.DISCONNECTED
        logger.info(f"[SIMULATION] {self.device_id} disconnected")
        return True

    async def get_status(self) -> Dict[str, Any]:
        """장치 상태 조회"""
        await self._simulate_delay()
        return {
            "device_id": self.device_id,
            "connection_status": self._connection_status.value,
            "recording_status": self._recording_status.value,
            "position": {
                "pan": self._current_position.pan,
                "tilt": self._current_position.tilt,
                "zoom": self._current_position.zoom
            },
            "has_ptz": self._has_ptz,
            "has_audio": self._has_audio,
            "simulation": True
        }

    async def get_capabilities(self) -> List[str]:
        """기능 목록 조회"""
        capabilities = [
            "ptz_move",
            "ptz_continuous",
            "preset",
            "recording",
            "snapshot",
            "streaming"
        ]
        if self._has_audio:
            capabilities.append("audio")
        if self._has_ir:
            capabilities.append("ir_control")
        return capabilities

    async def move_ptz(
        self,
        pan: Optional[float] = None,
        tilt: Optional[float] = None,
        zoom: Optional[float] = None,
        speed: float = 0.5
    ) -> DeviceResponse:
        """PTZ 이동"""
        await self._simulate_delay()

        if pan is not None:
            self._current_position.pan = max(-180, min(180, pan))
        if tilt is not None:
            self._current_position.tilt = max(-90, min(90, tilt))
        if zoom is not None:
            self._current_position.zoom = max(1.0, min(20.0, zoom))

        logger.info(
            f"[SIMULATION] {self.device_id} PTZ moved to "
            f"pan={self._current_position.pan}, "
            f"tilt={self._current_position.tilt}, "
            f"zoom={self._current_position.zoom}"
        )

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

    async def move_continuous(
        self,
        direction: PTZDirection,
        speed: float = 0.5
    ) -> DeviceResponse:
        """연속 이동"""
        await self._simulate_delay()

        # 방향에 따른 이동 시뮬레이션
        delta = speed * 10
        if direction == PTZDirection.UP:
            self._current_position.tilt = min(90, self._current_position.tilt + delta)
        elif direction == PTZDirection.DOWN:
            self._current_position.tilt = max(-90, self._current_position.tilt - delta)
        elif direction == PTZDirection.LEFT:
            self._current_position.pan = max(-180, self._current_position.pan - delta)
        elif direction == PTZDirection.RIGHT:
            self._current_position.pan = min(180, self._current_position.pan + delta)
        elif direction == PTZDirection.ZOOM_IN:
            self._current_position.zoom = min(20, self._current_position.zoom + 0.5)
        elif direction == PTZDirection.ZOOM_OUT:
            self._current_position.zoom = max(1, self._current_position.zoom - 0.5)

        logger.info(f"[SIMULATION] {self.device_id} continuous move: {direction.value}")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="move_continuous",
            result={"direction": direction.value, "speed": speed}
        )

    async def stop_ptz(self) -> DeviceResponse:
        """PTZ 정지"""
        await self._simulate_delay()
        logger.info(f"[SIMULATION] {self.device_id} PTZ stopped")
        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="stop_ptz",
            result={"message": "PTZ movement stopped"}
        )

    async def go_to_preset(self, preset_id: str) -> DeviceResponse:
        """프리셋 이동"""
        await self._simulate_delay()

        if preset_id not in self._presets:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="go_to_preset",
                status=CommandStatus.FAILED,
                error=f"Preset {preset_id} not found"
            )

        preset = self._presets[preset_id]
        if preset.position:
            self._current_position = PTZPosition(
                pan=preset.position.pan,
                tilt=preset.position.tilt,
                zoom=preset.position.zoom
            )

        logger.info(f"[SIMULATION] {self.device_id} moved to preset '{preset.name}'")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="go_to_preset",
            result={
                "preset_id": preset_id,
                "preset_name": preset.name,
                "position": {
                    "pan": self._current_position.pan,
                    "tilt": self._current_position.tilt,
                    "zoom": self._current_position.zoom
                }
            }
        )

    async def set_preset(self, preset_id: str, name: str) -> DeviceResponse:
        """프리셋 저장"""
        await self._simulate_delay()

        self._presets[preset_id] = Preset(
            preset_id=preset_id,
            name=name,
            position=PTZPosition(
                pan=self._current_position.pan,
                tilt=self._current_position.tilt,
                zoom=self._current_position.zoom
            )
        )

        logger.info(f"[SIMULATION] {self.device_id} preset '{name}' saved at {preset_id}")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="set_preset",
            result={"preset_id": preset_id, "name": name}
        )

    async def get_presets(self) -> List[Preset]:
        """프리셋 목록 조회"""
        await self._simulate_delay()
        return list(self._presets.values())

    async def get_ptz_position(self) -> PTZPosition:
        """현재 PTZ 위치 조회"""
        await self._simulate_delay()
        return self._current_position

    async def start_recording(self) -> DeviceResponse:
        """녹화 시작"""
        await self._simulate_delay()
        self._recording_status = RecordingStatus.RECORDING
        logger.info(f"[SIMULATION] {self.device_id} recording started")
        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="start_recording",
            result={"status": "recording"}
        )

    async def stop_recording(self) -> DeviceResponse:
        """녹화 중지"""
        await self._simulate_delay()
        self._recording_status = RecordingStatus.STOPPED
        logger.info(f"[SIMULATION] {self.device_id} recording stopped")
        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="stop_recording",
            result={"status": "stopped"}
        )

    async def get_recording_status(self) -> RecordingStatus:
        """녹화 상태 조회"""
        await self._simulate_delay()
        return self._recording_status

    async def capture_snapshot(
        self,
        resolution: str = "1920x1080"
    ) -> DeviceResponse:
        """스냅샷 캡처 시뮬레이션"""
        await self._simulate_delay()

        # 1x1 빨간색 픽셀 (시뮬레이션용)
        dummy_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        logger.info(f"[SIMULATION] {self.device_id} snapshot captured ({resolution})")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="capture_snapshot",
            result={
                "image_base64": dummy_image,
                "resolution": resolution,
                "timestamp": datetime.now().isoformat(),
                "simulation": True
            }
        )

    async def get_stream_url(
        self,
        protocol: StreamProtocol = StreamProtocol.RTSP,
        stream_type: str = "main"
    ) -> StreamInfo:
        """스트림 URL 조회"""
        await self._simulate_delay()

        if protocol == StreamProtocol.RTSP:
            url = f"rtsp://{self.ip}:{554}/stream/{stream_type}"
        elif protocol == StreamProtocol.HTTP:
            url = f"http://{self.ip}:{self.port}/video/{stream_type}"
        else:
            url = f"http://{self.ip}:{self.port}/hls/{stream_type}.m3u8"

        return StreamInfo(
            url=url,
            protocol=protocol,
            resolution="1920x1080" if stream_type == "main" else "640x480",
            fps=30 if stream_type == "main" else 15,
            is_main_stream=(stream_type == "main")
        )


class SimulationACUAdapter(BaseACUAdapter):
    """
    ACU 시뮬레이션 어댑터

    실제 출입통제 장치 없이 ACU 제어를 시뮬레이션합니다.
    """

    def __init__(self, device_info: Dict[str, Any]):
        super().__init__(device_info)

        # 시뮬레이션 출입문 초기화
        self._doors = {
            "1": DoorInfo(door_id="1", name="정문", status=DoorStatus.LOCKED, location="1층"),
            "2": DoorInfo(door_id="2", name="후문", status=DoorStatus.LOCKED, location="1층"),
            "3": DoorInfo(door_id="3", name="서버실", status=DoorStatus.LOCKED, location="지하1층"),
        }

        # 시뮬레이션 출입 이력
        self._access_logs: List[AccessLog] = []
        self._generate_sample_logs()

        # 활성 알람
        self._active_alarms: List[AlarmEvent] = []

        # 시뮬레이션 설정
        self._response_delay_ms = device_info.get("simulation_delay_ms", 100)

        logger.info(f"SimulationACUAdapter created for {self.device_id}")

    def _generate_sample_logs(self):
        """샘플 출입 이력 생성"""
        sample_users = [
            ("user001", "김철수"),
            ("user002", "이영희"),
            ("user003", "박지민"),
            ("user004", "최수영"),
        ]

        for i in range(10):
            user_id, user_name = random.choice(sample_users)
            door_id = random.choice(list(self._doors.keys()))
            self._access_logs.append(
                AccessLog(
                    log_id=f"log_{i:04d}",
                    door_id=door_id,
                    user_id=user_id,
                    user_name=user_name,
                    access_type=AccessType.CARD,
                    result=AccessResult.GRANTED,
                    timestamp=datetime.now() - timedelta(hours=random.randint(1, 48)),
                    card_number=f"1234567890{i:02d}"
                )
            )

    async def _simulate_delay(self):
        """응답 지연 시뮬레이션"""
        if self._response_delay_ms > 0:
            await asyncio.sleep(self._response_delay_ms / 1000)

    async def connect(self) -> bool:
        """연결 시뮬레이션"""
        await self._simulate_delay()
        self._connection_status = ConnectionStatus.CONNECTED
        self._update_communication_time()
        logger.info(f"[SIMULATION] {self.device_id} connected")
        return True

    async def disconnect(self) -> bool:
        """연결 해제 시뮬레이션"""
        await self._simulate_delay()
        self._connection_status = ConnectionStatus.DISCONNECTED
        logger.info(f"[SIMULATION] {self.device_id} disconnected")
        return True

    async def get_status(self) -> Dict[str, Any]:
        """장치 상태 조회"""
        await self._simulate_delay()
        return {
            "device_id": self.device_id,
            "connection_status": self._connection_status.value,
            "doors": {
                door_id: {
                    "name": door.name,
                    "status": door.status.value,
                    "location": door.location
                }
                for door_id, door in self._doors.items()
            },
            "active_alarms": len(self._active_alarms),
            "simulation": True
        }

    async def get_capabilities(self) -> List[str]:
        """기능 목록 조회"""
        return [
            "door_control",
            "access_log",
            "alarm_management",
            "emergency_control",
            "user_management"
        ]

    async def unlock_door(
        self,
        door_id: str,
        duration: int = 5
    ) -> DeviceResponse:
        """출입문 해제"""
        await self._simulate_delay()

        if door_id not in self._doors:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="unlock_door",
                status=CommandStatus.FAILED,
                error=f"Door {door_id} not found"
            )

        self._doors[door_id].status = DoorStatus.UNLOCKED
        self._doors[door_id].last_access_time = datetime.now()
        self._doors[door_id].last_access_user = "system"

        # 출입 이력 추가
        self._access_logs.insert(0, AccessLog(
            log_id=f"log_{len(self._access_logs):04d}",
            door_id=door_id,
            user_id="system",
            user_name="시스템",
            access_type=AccessType.REMOTE,
            result=AccessResult.GRANTED,
            timestamp=datetime.now()
        ))

        logger.info(f"[SIMULATION] {self.device_id} door {door_id} unlocked for {duration}s")

        # 자동 잠금 타이머 (실제로는 구현하지 않음)

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="unlock_door",
            result={
                "door_id": door_id,
                "door_name": self._doors[door_id].name,
                "status": "unlocked",
                "duration": duration
            }
        )

    async def lock_door(self, door_id: str) -> DeviceResponse:
        """출입문 잠금"""
        await self._simulate_delay()

        if door_id not in self._doors:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="lock_door",
                status=CommandStatus.FAILED,
                error=f"Door {door_id} not found"
            )

        self._doors[door_id].status = DoorStatus.LOCKED

        logger.info(f"[SIMULATION] {self.device_id} door {door_id} locked")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="lock_door",
            result={
                "door_id": door_id,
                "door_name": self._doors[door_id].name,
                "status": "locked"
            }
        )

    async def hold_open(self, door_id: str) -> DeviceResponse:
        """상시 개방"""
        await self._simulate_delay()

        if door_id not in self._doors:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="hold_open",
                status=CommandStatus.FAILED,
                error=f"Door {door_id} not found"
            )

        self._doors[door_id].status = DoorStatus.HELD_OPEN

        logger.info(f"[SIMULATION] {self.device_id} door {door_id} held open")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="hold_open",
            result={
                "door_id": door_id,
                "door_name": self._doors[door_id].name,
                "status": "held_open"
            }
        )

    async def release_hold(self, door_id: str) -> DeviceResponse:
        """상시 개방 해제"""
        await self._simulate_delay()

        if door_id not in self._doors:
            return DeviceResponse(
                success=False,
                device_id=self.device_id,
                action="release_hold",
                status=CommandStatus.FAILED,
                error=f"Door {door_id} not found"
            )

        self._doors[door_id].status = DoorStatus.LOCKED

        logger.info(f"[SIMULATION] {self.device_id} door {door_id} hold released")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="release_hold",
            result={
                "door_id": door_id,
                "door_name": self._doors[door_id].name,
                "status": "locked"
            }
        )

    async def get_door_status(self, door_id: str) -> DoorInfo:
        """출입문 상태 조회"""
        await self._simulate_delay()

        if door_id not in self._doors:
            raise ValueError(f"Door {door_id} not found")

        return self._doors[door_id]

    async def get_all_doors(self) -> List[DoorInfo]:
        """모든 출입문 상태 조회"""
        await self._simulate_delay()
        return list(self._doors.values())

    async def get_access_log(
        self,
        door_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AccessLog]:
        """출입 이력 조회"""
        await self._simulate_delay()

        logs = self._access_logs

        if door_id:
            logs = [log for log in logs if log.door_id == door_id]

        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]

        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]

        return logs[:limit]

    async def get_active_alarms(self) -> List[AlarmEvent]:
        """활성 알람 조회"""
        await self._simulate_delay()
        return self._active_alarms

    async def acknowledge_alarm(self, alarm_id: str) -> DeviceResponse:
        """알람 확인"""
        await self._simulate_delay()

        for alarm in self._active_alarms:
            if alarm.alarm_id == alarm_id:
                alarm.acknowledged = True
                logger.info(f"[SIMULATION] Alarm {alarm_id} acknowledged")
                return DeviceResponse(
                    success=True,
                    device_id=self.device_id,
                    action="acknowledge_alarm",
                    result={"alarm_id": alarm_id, "acknowledged": True}
                )

        return DeviceResponse(
            success=False,
            device_id=self.device_id,
            action="acknowledge_alarm",
            status=CommandStatus.FAILED,
            error=f"Alarm {alarm_id} not found"
        )

    async def emergency_unlock_all(self) -> DeviceResponse:
        """비상 전체 해제"""
        await self._simulate_delay()

        for door in self._doors.values():
            door.status = DoorStatus.UNLOCKED

        logger.info(f"[SIMULATION] {self.device_id} emergency unlock all")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="emergency_unlock_all",
            result={
                "message": "All doors unlocked",
                "doors_affected": len(self._doors)
            }
        )

    async def emergency_lock_all(self) -> DeviceResponse:
        """비상 전체 잠금"""
        await self._simulate_delay()

        for door in self._doors.values():
            door.status = DoorStatus.LOCKED

        logger.info(f"[SIMULATION] {self.device_id} emergency lock all (lockdown)")

        return DeviceResponse(
            success=True,
            device_id=self.device_id,
            action="emergency_lock_all",
            result={
                "message": "All doors locked (lockdown)",
                "doors_affected": len(self._doors)
            }
        )
