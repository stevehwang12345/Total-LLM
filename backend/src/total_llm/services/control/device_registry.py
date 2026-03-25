"""
장치 등록 및 관리 서비스

발견된 네트워크 장치를 등록하고 LLM 제어 시스템과 연동합니다.
- 장치 등록/수정/삭제
- 인증 정보 관리
- 실시간 연결 상태 관리
- SystemController와 자동 연동
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from enum import Enum
import json
from pathlib import Path
import httpx

from .network_discovery import (
    DiscoveredDevice,
    DeviceType,
    DeviceStatus,
    NetworkDiscoveryService,
    get_discovery_service
)
from .credential_manager import get_credential_manager, CredentialManager

logger = logging.getLogger(__name__)


class ConnectionStatus(str, Enum):
    """연결 상태"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTH_FAILED = "auth_failed"
    ERROR = "error"


@dataclass
class RegisteredDevice:
    """등록된 장치"""
    id: str
    ip: str
    name: str
    device_type: DeviceType
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    zone_id: Optional[str] = None  # 보안 존 ID

    # 인증 정보 (암호화 저장)
    username: Optional[str] = None
    password: Optional[str] = None
    _encrypted_credentials: Optional[str] = None  # 암호화된 인증정보

    # 연결 정보
    connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    rtsp_url: Optional[str] = None
    web_interface: Optional[str] = None
    onvif_url: Optional[str] = None

    # 기능 정보
    ptz_capable: bool = False
    recording_capable: bool = False
    audio_capable: bool = False

    # 메타데이터
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['device_type'] = self.device_type.value
        result['connection_status'] = self.connection_status.value
        return result

    @classmethod
    def from_discovered(
        cls,
        device: DiscoveredDevice,
        device_id: str,
        name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        location: Optional[str] = None,
    ) -> "RegisteredDevice":
        """발견된 장치에서 등록 장치 생성"""
        return cls(
            id=device_id,
            ip=device.ip,
            name=name,
            device_type=device.device_type,
            manufacturer=device.manufacturer,
            model=device.model,
            location=location,
            username=username,
            password=password,
            rtsp_url=device.rtsp_url,
            web_interface=device.web_interface,
            onvif_url=f"http://{device.ip}/onvif/device_service" if device.onvif_supported else None,
            additional_info=device.additional_info or {},
        )


class DeviceRegistry:
    """장치 등록소 (암호화된 인증정보 저장)"""

    # 기본 저장 경로 (보안 강화: /tmp → data 디렉토리)
    DEFAULT_STORAGE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "device_registry"

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = self.DEFAULT_STORAGE_DIR / "devices.json.enc"

        self._devices: Dict[str, RegisteredDevice] = {}
        self._discovery_service = get_discovery_service()
        self._connection_tasks: Dict[str, asyncio.Task] = {}
        self._credential_manager: CredentialManager = get_credential_manager()
        self._ensure_storage_directory()
        self._load_devices()

    def _ensure_storage_directory(self):
        """저장 디렉토리 생성 및 권한 설정"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            # 디렉토리 권한 설정 (소유자만 접근)
            os.chmod(self.storage_path.parent, 0o700)
        except Exception as e:
            logger.warning(f"저장 디렉토리 권한 설정 실패: {e}")

    def _load_devices(self):
        """저장된 장치 정보 로드 (암호화된 인증정보 복호화)"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for device_data in data.get("devices", []):
                        device_data["device_type"] = DeviceType(device_data["device_type"])
                        device_data["connection_status"] = ConnectionStatus(device_data["connection_status"])

                        # 암호화된 인증정보 복호화
                        encrypted_creds = device_data.pop("_encrypted_credentials", None)
                        if encrypted_creds:
                            decrypted = self._credential_manager.decrypt_credentials(encrypted_creds)
                            if decrypted:
                                device_data["username"] = decrypted.get("username")
                                device_data["password"] = decrypted.get("password")
                            else:
                                logger.warning(f"장치 {device_data.get('id')} 인증정보 복호화 실패")
                        else:
                            # 기존 평문 데이터 마이그레이션 (레거시 지원)
                            if device_data.get("username") or device_data.get("password"):
                                logger.info(f"장치 {device_data.get('id')} 평문 인증정보 발견 - 마이그레이션 필요")

                        device = RegisteredDevice(**device_data)
                        self._devices[device.id] = device

                logger.info(f"Loaded {len(self._devices)} devices from storage")
            except Exception as e:
                logger.error(f"Failed to load devices: {e}")

    def _save_devices(self):
        """장치 정보 저장 (인증정보 암호화)"""
        try:
            devices_data = []
            for device in self._devices.values():
                device_dict = device.to_dict()

                # 인증정보 암호화 (username, password를 암호화하여 저장)
                username = device_dict.pop("username", None)
                password = device_dict.pop("password", None)

                if username or password:
                    encrypted = self._credential_manager.encrypt_credentials({
                        "username": username,
                        "password": password,
                    })
                    device_dict["_encrypted_credentials"] = encrypted
                else:
                    device_dict["_encrypted_credentials"] = None

                devices_data.append(device_dict)

            data = {
                "devices": devices_data,
                "updated_at": datetime.now().isoformat(),
                "encryption": "fernet",  # 암호화 방식 표시
            }

            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # 파일 권한 설정 (소유자만 읽기/쓰기)
            os.chmod(self.storage_path, 0o600)

        except Exception as e:
            logger.error(f"Failed to save devices: {e}")

    def _generate_device_id(self, device_type: DeviceType, ip: str) -> str:
        """장치 ID 생성"""
        type_prefix = {
            DeviceType.IP_CAMERA: "cam",
            DeviceType.NVR: "nvr",
            DeviceType.ACU: "acu",
            DeviceType.NETWORK_DEVICE: "net",
            DeviceType.UNKNOWN: "dev",
        }
        prefix = type_prefix.get(device_type, "dev")
        # IP 마지막 옥텟 사용
        last_octet = ip.split(".")[-1].zfill(3)
        existing_count = len([d for d in self._devices.values() if d.device_type == device_type])
        return f"{prefix}_{last_octet}_{existing_count + 1:02d}"

    async def register_device(
        self,
        device: DiscoveredDevice,
        name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        location: Optional[str] = None,
        auto_connect: bool = True,
    ) -> RegisteredDevice:
        """
        장치 등록

        Args:
            device: 발견된 장치 정보
            name: 장치 이름 (예: "로비 카메라", "정문")
            username: 인증 사용자명
            password: 인증 비밀번호
            location: 설치 위치
            auto_connect: 등록 후 자동 연결 시도

        Returns:
            등록된 장치
        """
        # 중복 IP 체크
        for existing in self._devices.values():
            if existing.ip == device.ip:
                raise ValueError(f"Device with IP {device.ip} already registered as {existing.id}")

        device_id = self._generate_device_id(device.device_type, device.ip)

        registered = RegisteredDevice.from_discovered(
            device=device,
            device_id=device_id,
            name=name,
            username=username,
            password=password,
            location=location,
        )

        self._devices[device_id] = registered
        self._save_devices()

        logger.info(f"Registered device: {device_id} ({name}) at {device.ip}")

        # 자동 연결
        if auto_connect and username and password:
            await self.connect_device(device_id)

        return registered

    async def register_from_ip(
        self,
        ip: str,
        name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        location: Optional[str] = None,
        device_type: Optional[DeviceType] = None,
    ) -> RegisteredDevice:
        """
        IP 주소로 직접 장치 등록

        먼저 장치를 스캔하여 정보를 수집한 후 등록합니다.
        """
        # 장치 스캔
        device = await self._discovery_service.scan_single_ip(ip)

        if device is None:
            # 스캔 실패 시 기본 정보로 등록
            device = DiscoveredDevice(
                ip=ip,
                device_type=device_type or DeviceType.UNKNOWN,
            )

        return await self.register_device(
            device=device,
            name=name,
            username=username,
            password=password,
            location=location,
        )

    async def connect_device(self, device_id: str) -> bool:
        """장치 연결 시도"""
        device = self._devices.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        device.connection_status = ConnectionStatus.CONNECTING

        try:
            # HTTP 인증 테스트
            if device.web_interface and device.username and device.password:
                success = await self._test_http_auth(device)
                if success:
                    device.connection_status = ConnectionStatus.CONNECTED
                    device.last_seen = datetime.now().isoformat()

                    # 기능 탐색
                    await self._discover_capabilities(device)

                    self._save_devices()
                    logger.info(f"Connected to device: {device_id}")
                    return True
                else:
                    device.connection_status = ConnectionStatus.AUTH_FAILED
                    self._save_devices()
                    return False

            # 인증 정보 없으면 연결만 테스트
            if device.web_interface:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(device.web_interface)
                    if response.status_code in (200, 401):
                        device.connection_status = ConnectionStatus.CONNECTED
                        device.last_seen = datetime.now().isoformat()
                        self._save_devices()
                        return True

        except Exception as e:
            logger.error(f"Failed to connect to device {device_id}: {e}")
            device.connection_status = ConnectionStatus.ERROR
            device.additional_info["last_error"] = str(e)
            self._save_devices()

        return False

    async def _test_http_auth(self, device: RegisteredDevice) -> bool:
        """HTTP Digest 인증 테스트"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                auth = httpx.DigestAuth(device.username, device.password)

                # Hanwha Vision API 테스트
                if device.manufacturer == "hanwha":
                    response = await client.get(
                        f"http://{device.ip}/stw-cgi/system.cgi?msubmenu=deviceinfo&action=view",
                        auth=auth
                    )
                else:
                    # 일반 HTTP 테스트
                    response = await client.get(device.web_interface, auth=auth)

                return response.status_code == 200

        except Exception as e:
            logger.debug(f"Auth test failed: {e}")
            return False

    async def _discover_capabilities(self, device: RegisteredDevice):
        """장치 기능 탐색"""
        if device.device_type not in (DeviceType.IP_CAMERA, DeviceType.NVR):
            return

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                auth = None
                if device.username and device.password:
                    auth = httpx.DigestAuth(device.username, device.password)

                # PTZ 기능 확인
                if device.manufacturer == "hanwha":
                    try:
                        response = await client.get(
                            f"http://{device.ip}/stw-cgi/ptzcontrol.cgi?msubmenu=query&action=view",
                            auth=auth
                        )
                        device.ptz_capable = response.status_code == 200
                    except:
                        pass

                    # 녹화 기능 확인
                    try:
                        response = await client.get(
                            f"http://{device.ip}/stw-cgi/recording.cgi?msubmenu=status&action=view",
                            auth=auth
                        )
                        device.recording_capable = response.status_code == 200
                    except:
                        pass

        except Exception as e:
            logger.debug(f"Capability discovery failed: {e}")

    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        """장치 조회"""
        return self._devices.get(device_id)

    def get_all_devices(self) -> List[RegisteredDevice]:
        """모든 장치 조회"""
        return list(self._devices.values())

    def get_devices_by_type(self, device_type: DeviceType) -> List[RegisteredDevice]:
        """유형별 장치 조회"""
        return [d for d in self._devices.values() if d.device_type == device_type]

    def get_connected_devices(self) -> List[RegisteredDevice]:
        """연결된 장치만 조회"""
        return [d for d in self._devices.values() if d.connection_status == ConnectionStatus.CONNECTED]

    async def update_device(
        self,
        device_id: str,
        name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        location: Optional[str] = None,
    ) -> RegisteredDevice:
        """장치 정보 수정"""
        device = self._devices.get(device_id)
        if not device:
            raise ValueError(f"Device not found: {device_id}")

        if name is not None:
            device.name = name
        if username is not None:
            device.username = username
        if password is not None:
            device.password = password
        if location is not None:
            device.location = location

        self._save_devices()
        return device

    def delete_device(self, device_id: str) -> bool:
        """장치 삭제"""
        if device_id in self._devices:
            del self._devices[device_id]
            self._save_devices()
            logger.info(f"Deleted device: {device_id}")
            return True
        return False

    def export_for_controller(self, include_credentials: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """
        SystemController용 장치 정보 내보내기

        ACU와 CCTV 컨트롤러에서 사용할 수 있는 형식으로 변환

        Args:
            include_credentials: True면 인증정보 포함 (내부 시스템용)
                                False면 마스킹된 정보 (API 응답용)
        """
        cameras = []
        doors = []

        for device in self._devices.values():
            if device.device_type in (DeviceType.IP_CAMERA, DeviceType.NVR):
                camera_info = {
                    "id": device.id,
                    "name": device.name,
                    "ip": device.ip,
                    "location": device.location or "미지정",
                    "zone_id": device.zone_id,
                    "manufacturer": device.manufacturer,
                    "rtsp_url": self._mask_rtsp_url(device.rtsp_url) if not include_credentials else device.rtsp_url,
                    "ptz_capable": device.ptz_capable,
                    "recording_capable": device.recording_capable,
                    "status": "online" if device.connection_status == ConnectionStatus.CONNECTED else "offline",
                }

                if include_credentials and device.username:
                    camera_info["credentials"] = {
                        "username": device.username,
                        "password": device.password,
                    }
                else:
                    camera_info["has_credentials"] = bool(device.username)

                cameras.append(camera_info)

            elif device.device_type == DeviceType.ACU:
                door_info = {
                    "id": device.id,
                    "name": device.name,
                    "ip": device.ip,
                    "location": device.location or "미지정",
                    "zone_id": device.zone_id,
                    "manufacturer": device.manufacturer,
                    "status": "locked" if device.connection_status == ConnectionStatus.CONNECTED else "error",
                }

                if include_credentials and device.username:
                    door_info["credentials"] = {
                        "username": device.username,
                        "password": device.password,
                    }
                else:
                    door_info["has_credentials"] = bool(device.username)

                doors.append(door_info)

        return {
            "cameras": cameras,
            "doors": doors,
        }

    def _mask_rtsp_url(self, rtsp_url: Optional[str]) -> Optional[str]:
        """RTSP URL에서 비밀번호 마스킹"""
        if not rtsp_url:
            return None

        # rtsp://username:password@host:port/path 형식에서 비밀번호 마스킹
        import re
        pattern = r'(rtsp://[^:]+:)[^@]+(@.+)'
        masked = re.sub(pattern, r'\1****\2', rtsp_url)
        return masked

    def export_for_api(self) -> Dict[str, List[Dict[str, Any]]]:
        """API 응답용 장치 정보 (인증정보 미포함)"""
        return self.export_for_controller(include_credentials=False)

    def get_device_credentials(self, device_id: str) -> Optional[Dict[str, str]]:
        """
        특정 장치의 인증정보 조회 (내부 시스템용)

        Returns:
            {"username": "...", "password": "..."} 또는 None
        """
        device = self._devices.get(device_id)
        if not device or not device.username:
            return None
        return {
            "username": device.username,
            "password": device.password,
        }

    async def update_credentials(
        self,
        device_id: str,
        username: str,
        password: str,
        test_connection: bool = True,
    ) -> Dict[str, Any]:
        """
        장치 인증정보 업데이트

        Args:
            device_id: 장치 ID
            username: 새 사용자명
            password: 새 비밀번호
            test_connection: True면 연결 테스트 후 저장

        Returns:
            {"success": bool, "message": str, "connection_status": str}
        """
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "message": f"장치를 찾을 수 없습니다: {device_id}"}

        # 인증정보 임시 저장
        old_username = device.username
        old_password = device.password
        device.username = username
        device.password = password

        if test_connection:
            # 연결 테스트
            success = await self.connect_device(device_id)
            if not success:
                # 실패 시 롤백
                device.username = old_username
                device.password = old_password
                return {
                    "success": False,
                    "message": "인증 테스트 실패 - 사용자명/비밀번호를 확인하세요",
                    "connection_status": device.connection_status.value,
                }

        self._save_devices()
        return {
            "success": True,
            "message": "인증정보가 업데이트되었습니다",
            "connection_status": device.connection_status.value,
        }

    async def test_credentials(
        self,
        device_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        인증정보 테스트 (저장하지 않음)

        Args:
            device_id: 장치 ID
            username: 테스트할 사용자명 (None이면 기존 값 사용)
            password: 테스트할 비밀번호 (None이면 기존 값 사용)

        Returns:
            {"success": bool, "message": str}
        """
        device = self._devices.get(device_id)
        if not device:
            return {"success": False, "message": f"장치를 찾을 수 없습니다: {device_id}"}

        test_username = username or device.username
        test_password = password or device.password

        if not test_username or not test_password:
            return {"success": False, "message": "인증정보가 필요합니다"}

        # 임시 장치 객체로 테스트
        test_device = RegisteredDevice(
            id=device.id,
            ip=device.ip,
            name=device.name,
            device_type=device.device_type,
            manufacturer=device.manufacturer,
            web_interface=device.web_interface,
            username=test_username,
            password=test_password,
        )

        success = await self._test_http_auth(test_device)
        return {
            "success": success,
            "message": "인증 성공" if success else "인증 실패",
        }


# 싱글톤 인스턴스
_device_registry: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    """장치 등록소 인스턴스 반환"""
    global _device_registry
    if _device_registry is None:
        _device_registry = DeviceRegistry()
    return _device_registry
