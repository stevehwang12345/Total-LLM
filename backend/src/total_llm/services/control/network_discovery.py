"""
네트워크 장치 탐색 서비스

네트워크 내 CCTV, NVR, ACU 장치를 자동으로 탐색하고 식별합니다.
- 포트 스캔 (HTTP, RTSP, ONVIF, ACU 포트)
- 장치 유형 식별 (제조사, 모델)
- ONVIF 프로토콜 지원 확인
"""

import asyncio
import socket
import struct
import re
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """장치 유형"""
    NVR = "nvr"
    IP_CAMERA = "ip_camera"
    ACU = "acu"
    UNKNOWN = "unknown"
    NETWORK_DEVICE = "network_device"


class DeviceStatus(str, Enum):
    """장치 상태"""
    ONLINE = "online"
    OFFLINE = "offline"
    AUTH_REQUIRED = "auth_required"
    ERROR = "error"


@dataclass
class DiscoveredDevice:
    """발견된 장치 정보"""
    ip: str
    device_type: DeviceType
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    mac_address: Optional[str] = None
    status: DeviceStatus = DeviceStatus.ONLINE
    ports: Dict[str, bool] = field(default_factory=dict)  # port_name: is_open
    protocols: List[str] = field(default_factory=list)  # supported protocols
    web_interface: Optional[str] = None
    rtsp_url: Optional[str] = None
    onvif_supported: bool = False
    auth_required: bool = False
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['device_type'] = self.device_type.value
        result['status'] = self.status.value
        return result


class NetworkDiscoveryService:
    """네트워크 장치 탐색 서비스"""

    # 스캔할 포트 정의
    CCTV_PORTS = {
        80: "http",
        443: "https",
        554: "rtsp",
        8000: "http_alt",
        8080: "http_proxy",
        8081: "http_alt2",
        8899: "onvif_alt",
        37777: "dahua_tcp",
        37778: "dahua_udp",
        34567: "xiongmai",
    }

    ACU_PORTS = {
        4370: "zkteco",
        5005: "suprema",
        4050: "hid",
        4096: "honeywell",
        8090: "acu_web",
        4000: "acu_generic",
        9922: "genetec",
    }

    # 제조사 식별 패턴
    MANUFACTURER_PATTERNS = {
        "hanwha": ["Hanwha", "Samsung Techwin", "iPolis", "Wisenet", "hanwha", "HANWHA", "Hanwha Vision"],
        "hikvision": ["Hikvision", "HIKVISION", "HikVision", "DS-", "hikvision"],
        "dahua": ["Dahua", "DAHUA", "DH-", "dahua"],
        "axis": ["AXIS", "Axis Communications", "axis"],
        "bosch": ["Bosch", "BOSCH", "bosch"],
        "honeywell": ["Honeywell", "HONEYWELL", "honeywell"],
        "zkteco": ["ZKTeco", "ZKTECO", "ZK", "zkteco"],
        "suprema": ["Suprema", "SUPREMA", "BioStar", "suprema"],
    }

    def __init__(
        self,
        subnet: str = "192.168.1.0/24",
        timeout: float = 1.0,
        max_concurrent: int = 50,
    ):
        self.subnet = subnet
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self._scan_results: List[DiscoveredDevice] = []

    def _parse_subnet(self, subnet: str) -> List[str]:
        """서브넷을 IP 목록으로 변환"""
        if "/" in subnet:
            base_ip, mask = subnet.split("/")
            mask = int(mask)
        else:
            base_ip = subnet
            mask = 24

        parts = [int(p) for p in base_ip.split(".")]
        base_int = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
        host_bits = 32 - mask
        num_hosts = (1 << host_bits) - 2  # 네트워크/브로드캐스트 제외

        ips = []
        for i in range(1, num_hosts + 1):
            ip_int = (base_int & (0xFFFFFFFF << host_bits)) + i
            ip = f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"
            ips.append(ip)

        return ips

    async def _check_port(self, ip: str, port: int) -> bool:
        """포트 오픈 여부 확인"""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=self.timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False

    async def _scan_ports(self, ip: str, ports: Dict[int, str]) -> Dict[str, bool]:
        """여러 포트 동시 스캔"""
        tasks = {
            name: self._check_port(ip, port)
            for port, name in ports.items()
        }
        results = {}
        for name, task in tasks.items():
            results[name] = await task
        return results

    async def _get_http_info(self, ip: str, port: int = 80) -> Dict[str, Any]:
        """HTTP 헤더 및 응답 분석"""
        info = {
            "server": None,
            "title": None,
            "manufacturer": None,
            "redirect": None,
            "auth_required": False,
            "content": None,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout * 2) as client:
                response = await client.get(
                    f"http://{ip}:{port}/",
                    follow_redirects=False
                )

                # 서버 헤더
                info["server"] = response.headers.get("Server", "")

                # 인증 필요 여부
                if response.status_code == 401:
                    info["auth_required"] = True
                    www_auth = response.headers.get("WWW-Authenticate", "")
                    # MAC 주소 추출 (realm에서)
                    mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", www_auth)
                    if mac_match:
                        info["mac_address"] = mac_match.group(0)

                # 리다이렉트 확인
                if response.status_code in (301, 302, 303, 307, 308):
                    info["redirect"] = response.headers.get("Location", "")

                # HTML 콘텐츠 분석
                content = response.text
                info["content"] = content[:500] if content else None

                # 리다이렉트 페이지 follow (Hanwha Vision 등)
                if "./wmf/index.html" in content or "location.href" in content:
                    try:
                        redirect_response = await client.get(
                            f"http://{ip}:{port}/wmf/index.html",
                            follow_redirects=False
                        )
                        if redirect_response.status_code == 200:
                            content = redirect_response.text
                            info["content"] = content[:500]
                    except Exception:
                        pass

                # 타이틀 추출
                title_match = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
                if title_match:
                    info["title"] = title_match.group(1).strip()

                # 제조사 식별 (콘텐츠 + 타이틀 + 서버 헤더)
                search_text = f"{content} {info.get('title', '')} {info.get('server', '')}".lower()
                for mfr, patterns in self.MANUFACTURER_PATTERNS.items():
                    for pattern in patterns:
                        if pattern.lower() in search_text:
                            info["manufacturer"] = mfr
                            break
                    if info["manufacturer"]:
                        break

        except Exception as e:
            logger.debug(f"HTTP check failed for {ip}:{port}: {e}")

        return info

    async def _check_onvif(self, ip: str) -> bool:
        """ONVIF 지원 여부 확인"""
        onvif_paths = [
            "/onvif/device_service",
            "/onvif-http/snapshot",
        ]

        try:
            async with httpx.AsyncClient(timeout=self.timeout * 2) as client:
                for path in onvif_paths:
                    try:
                        response = await client.get(f"http://{ip}{path}")
                        # 401도 ONVIF 지원으로 간주 (인증 필요)
                        if response.status_code in (200, 401, 405):
                            return True
                    except Exception:
                        pass
        except Exception:
            pass

        return False

    async def _identify_device(self, ip: str) -> Optional[DiscoveredDevice]:
        """장치 식별 및 정보 수집"""
        # 포트 스캔
        all_ports = {**self.CCTV_PORTS, **self.ACU_PORTS}
        port_results = await self._scan_ports(ip, all_ports)

        # 열린 포트가 없으면 스킵
        open_ports = {k: v for k, v in port_results.items() if v}
        if not open_ports:
            return None

        device = DiscoveredDevice(
            ip=ip,
            device_type=DeviceType.UNKNOWN,
            ports=port_results,
        )

        # HTTP 정보 수집
        if port_results.get("http") or port_results.get("http_alt") or port_results.get("http_proxy"):
            http_port = 80 if port_results.get("http") else (8000 if port_results.get("http_alt") else 8080)
            http_info = await self._get_http_info(ip, http_port)

            device.manufacturer = http_info.get("manufacturer")
            device.auth_required = http_info.get("auth_required", False)
            device.web_interface = f"http://{ip}:{http_port}/"

            if http_info.get("mac_address"):
                device.mac_address = http_info["mac_address"]

            if http_info.get("auth_required"):
                device.status = DeviceStatus.AUTH_REQUIRED

            # 제조사별 추가 정보
            if device.manufacturer:
                device.additional_info["title"] = http_info.get("title")
                device.additional_info["server"] = http_info.get("server")

        # 장치 유형 결정
        has_rtsp = port_results.get("rtsp", False)
        has_dahua = port_results.get("dahua_tcp", False) or port_results.get("dahua_udp", False)
        has_acu_port = any(port_results.get(name) for name in ["zkteco", "suprema", "hid", "honeywell", "acu_web"])

        if has_acu_port:
            device.device_type = DeviceType.ACU
            device.protocols.append("acu")
        elif has_rtsp or has_dahua:
            # RTSP가 있으면 카메라/NVR
            if device.manufacturer in ["hanwha", "hikvision", "dahua", "axis"]:
                device.device_type = DeviceType.IP_CAMERA
            else:
                device.device_type = DeviceType.NVR
            device.protocols.append("rtsp")
            device.rtsp_url = f"rtsp://{ip}:554/"
        elif port_results.get("http"):
            device.device_type = DeviceType.NETWORK_DEVICE

        # ONVIF 지원 확인
        if port_results.get("http") or port_results.get("http_alt"):
            device.onvif_supported = await self._check_onvif(ip)
            if device.onvif_supported:
                device.protocols.append("onvif")

        return device

    async def scan_network(
        self,
        subnet: Optional[str] = None,
        target_ips: Optional[List[str]] = None,
        device_types: Optional[List[DeviceType]] = None,
    ) -> List[DiscoveredDevice]:
        """
        네트워크 스캔 실행

        Args:
            subnet: 스캔할 서브넷 (예: "192.168.1.0/24")
            target_ips: 특정 IP 목록만 스캔
            device_types: 필터링할 장치 유형

        Returns:
            발견된 장치 목록
        """
        if target_ips:
            ips_to_scan = target_ips
        else:
            ips_to_scan = self._parse_subnet(subnet or self.subnet)

        logger.info(f"Starting network scan for {len(ips_to_scan)} IPs")

        # 동시 스캔 제한
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def scan_with_limit(ip: str):
            async with semaphore:
                return await self._identify_device(ip)

        # 병렬 스캔
        tasks = [scan_with_limit(ip) for ip in ips_to_scan]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 필터링
        devices = []
        for result in results:
            if isinstance(result, DiscoveredDevice):
                if device_types is None or result.device_type in device_types:
                    devices.append(result)

        # 결과 저장
        self._scan_results = devices
        logger.info(f"Scan complete. Found {len(devices)} devices")

        return devices

    async def scan_single_ip(self, ip: str) -> Optional[DiscoveredDevice]:
        """단일 IP 스캔"""
        return await self._identify_device(ip)

    async def quick_scan(self, subnet: Optional[str] = None) -> Dict[str, Any]:
        """
        빠른 스캔 (CCTV/NVR/ACU만 탐색)

        Returns:
            요약 정보와 장치 목록
        """
        devices = await self.scan_network(
            subnet=subnet,
            device_types=[DeviceType.IP_CAMERA, DeviceType.NVR, DeviceType.ACU]
        )

        # 요약 생성
        summary = {
            "total": len(devices),
            "by_type": {
                "ip_camera": len([d for d in devices if d.device_type == DeviceType.IP_CAMERA]),
                "nvr": len([d for d in devices if d.device_type == DeviceType.NVR]),
                "acu": len([d for d in devices if d.device_type == DeviceType.ACU]),
            },
            "by_manufacturer": {},
            "onvif_supported": len([d for d in devices if d.onvif_supported]),
            "auth_required": len([d for d in devices if d.auth_required]),
        }

        for device in devices:
            if device.manufacturer:
                summary["by_manufacturer"][device.manufacturer] = \
                    summary["by_manufacturer"].get(device.manufacturer, 0) + 1

        return {
            "summary": summary,
            "devices": [d.to_dict() for d in devices],
        }

    def get_last_results(self) -> List[DiscoveredDevice]:
        """마지막 스캔 결과 반환"""
        return self._scan_results


# 싱글톤 인스턴스
_discovery_service: Optional[NetworkDiscoveryService] = None


def get_discovery_service() -> NetworkDiscoveryService:
    """네트워크 탐색 서비스 인스턴스 반환"""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = NetworkDiscoveryService()
    return _discovery_service
