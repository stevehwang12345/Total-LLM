"""
Device Adapter Factory Module
장치 어댑터 팩토리

제조사, 프로토콜, 장치 유형에 따라 적절한 어댑터를 생성합니다.
"""

import importlib
import logging
from typing import Any, Dict, Optional, Type

from .base import BaseDeviceAdapter, DeviceType

logger = logging.getLogger(__name__)


class DeviceAdapterFactory:
    """
    장치 어댑터 팩토리

    장치 정보를 기반으로 적절한 어댑터 인스턴스를 생성합니다.
    시뮬레이션 모드, Hybrid 모드를 지원합니다.
    """

    # 제조사별 어댑터 매핑
    _cctv_adapters: Dict[str, Type[BaseDeviceAdapter]] = {}
    _acu_adapters: Dict[str, Type[BaseDeviceAdapter]] = {}

    # 기본 프로토콜 어댑터
    _default_cctv_adapter: Optional[Type[BaseDeviceAdapter]] = None
    _default_acu_adapter: Optional[Type[BaseDeviceAdapter]] = None

    # 시뮬레이션 어댑터
    _simulation_adapter: Optional[Type[BaseDeviceAdapter]] = None

    def __init__(
        self,
        mode: str = "simulation",
        fallback_to_simulation: bool = True
    ):
        """
        팩토리 초기화

        Args:
            mode: 제어 모드
                - "simulation": 시뮬레이션만 사용
                - "real": 실제 장치만 사용
                - "hybrid": 실제 장치 우선, 실패 시 시뮬레이션
            fallback_to_simulation: 연결 실패 시 시뮬레이션 폴백 여부 (hybrid 모드)
        """
        self.mode = mode
        self.fallback_to_simulation = fallback_to_simulation

        # 어댑터 등록
        self._register_adapters()

        logger.info(f"DeviceAdapterFactory initialized in '{mode}' mode")

    def _register_adapters(self):
        """
        어댑터 등록

        사용 가능한 어댑터들을 등록합니다.
        """
        # 시뮬레이션 어댑터 등록
        try:
            from .simulation import SimulationCCTVAdapter, SimulationACUAdapter
            self._simulation_adapter = True  # 시뮬레이션 모듈 로드됨
            logger.info("Simulation adapters registered")
        except ImportError:
            logger.warning("Simulation adapters not available")

        # ONVIF 어댑터 등록 (기본 CCTV)
        try:
            from .cctv.onvif import ONVIFAdapter
            self._cctv_adapters["onvif"] = ONVIFAdapter
            self._default_cctv_adapter = ONVIFAdapter
            logger.info("ONVIF adapter registered as default CCTV adapter")
        except ImportError:
            logger.warning("ONVIF adapter not available")

        # 제조사별 CCTV 어댑터 등록
        cctv_adapters = [
            ("hanwha", "HanwhaAdapter"),
            ("hikvision", "HikvisionAdapter"),
            ("dahua", "DahuaAdapter"),
            ("axis", "AxisAdapter"),
        ]
        for manufacturer, adapter_name in cctv_adapters:
            try:
                module = importlib.import_module(
                    f".cctv.{manufacturer}",
                    package=__package__
                )
                adapter_class = getattr(module, adapter_name)
                self._cctv_adapters[manufacturer] = adapter_class
                logger.info(f"{adapter_name} registered for manufacturer '{manufacturer}'")
            except (ImportError, AttributeError, ModuleNotFoundError):
                logger.debug(f"CCTV adapter '{adapter_name}' not implemented - will use ONVIF fallback for '{manufacturer}'")

        # 제조사별 ACU 어댑터 등록
        acu_adapters = [
            ("zkteco", "ZKTecoAdapter"),
            ("suprema", "SupremaAdapter"),
            ("hid", "HIDAdapter"),
        ]
        for manufacturer, adapter_name in acu_adapters:
            try:
                module = importlib.import_module(
                    f".acu.{manufacturer}",
                    package=__package__
                )
                adapter_class = getattr(module, adapter_name)
                self._acu_adapters[manufacturer] = adapter_class
                logger.info(f"{adapter_name} registered for manufacturer '{manufacturer}'")
            except (ImportError, AttributeError, ModuleNotFoundError):
                logger.debug(f"ACU adapter '{adapter_name}' not implemented - simulation mode will be used for '{manufacturer}'")

    def create_adapter(self, device_info: Dict[str, Any]) -> BaseDeviceAdapter:
        """
        장치 정보를 기반으로 적절한 어댑터 생성

        Args:
            device_info: 장치 정보
                - device_type: "cctv" | "acu"
                - manufacturer: 제조사 (예: "hanwha", "zkteco")
                - protocol: 프로토콜 (예: "onvif")
                - id/device_id: 장치 ID
                - ip: IP 주소
                - port: 포트
                - username: 사용자명
                - password: 비밀번호

        Returns:
            BaseDeviceAdapter: 생성된 어댑터 인스턴스
        """
        device_type = device_info.get("device_type", "").lower()
        manufacturer = device_info.get("manufacturer", "").lower()
        protocol = device_info.get("protocol", "").lower()
        is_real_device = device_info.get("is_real_device", False)

        # 모드별 어댑터 선택
        if self.mode == "simulation":
            return self._create_simulation_adapter(device_info)

        elif self.mode == "real":
            adapter = self._create_real_adapter(device_info)
            if adapter is None:
                raise ValueError(
                    f"No adapter available for {device_type}/{manufacturer}"
                )
            return adapter

        elif self.mode == "hybrid":
            # Hybrid 모드: 실제 장치이면 실제 어댑터 시도
            if is_real_device:
                adapter = self._create_real_adapter(device_info)
                if adapter is not None:
                    return adapter

                # 폴백 옵션
                if self.fallback_to_simulation:
                    logger.warning(
                        f"Falling back to simulation for {device_info.get('id')}"
                    )
                    return self._create_simulation_adapter(device_info)
                else:
                    raise ValueError(
                        f"No adapter available for {device_type}/{manufacturer}"
                    )
            else:
                # 실제 장치가 아니면 시뮬레이션
                return self._create_simulation_adapter(device_info)

        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def _create_simulation_adapter(
        self,
        device_info: Dict[str, Any]
    ) -> BaseDeviceAdapter:
        """
        시뮬레이션 어댑터 생성
        """
        from .simulation import SimulationCCTVAdapter, SimulationACUAdapter

        device_type = device_info.get("device_type", "").lower()

        if device_type == "cctv":
            return SimulationCCTVAdapter(device_info)
        elif device_type == "acu":
            return SimulationACUAdapter(device_info)
        else:
            # 기본값: CCTV 시뮬레이션
            logger.warning(f"Unknown device type '{device_type}', using CCTV simulation")
            device_info["device_type"] = "cctv"
            return SimulationCCTVAdapter(device_info)

    def _create_real_adapter(
        self,
        device_info: Dict[str, Any]
    ) -> Optional[BaseDeviceAdapter]:
        """
        실제 장치 어댑터 생성
        """
        device_type = device_info.get("device_type", "").lower()
        manufacturer = device_info.get("manufacturer", "").lower()
        protocol = device_info.get("protocol", "").lower()

        if device_type == "cctv":
            # 제조사별 어댑터 우선
            if manufacturer in self._cctv_adapters:
                adapter_class = self._cctv_adapters[manufacturer]
                return adapter_class(device_info)

            # 프로토콜별 어댑터
            if protocol in self._cctv_adapters:
                adapter_class = self._cctv_adapters[protocol]
                return adapter_class(device_info)

            # 기본 CCTV 어댑터 (ONVIF)
            if self._default_cctv_adapter:
                return self._default_cctv_adapter(device_info)

        elif device_type == "acu":
            # 제조사별 어댑터 우선
            if manufacturer in self._acu_adapters:
                adapter_class = self._acu_adapters[manufacturer]
                return adapter_class(device_info)

            # 기본 ACU 어댑터
            if self._default_acu_adapter:
                return self._default_acu_adapter(device_info)

        return None

    def get_available_adapters(self) -> Dict[str, Dict[str, str]]:
        """
        사용 가능한 어댑터 목록 반환
        """
        return {
            "cctv": {
                name: adapter.__name__
                for name, adapter in self._cctv_adapters.items()
            },
            "acu": {
                name: adapter.__name__
                for name, adapter in self._acu_adapters.items()
            },
            "simulation": "available" if self._simulation_adapter else "not available"
        }

    def set_mode(self, mode: str):
        """
        제어 모드 변경

        Args:
            mode: "simulation", "real", "hybrid"
        """
        if mode not in ["simulation", "real", "hybrid"]:
            raise ValueError(f"Invalid mode: {mode}")
        self.mode = mode
        logger.info(f"Control mode changed to '{mode}'")


# 싱글톤 인스턴스
_factory_instance: Optional[DeviceAdapterFactory] = None


def get_adapter_factory(
    mode: str = "hybrid",
    fallback_to_simulation: bool = True
) -> DeviceAdapterFactory:
    """
    어댑터 팩토리 싱글톤 인스턴스 반환

    Args:
        mode: 제어 모드
        fallback_to_simulation: 시뮬레이션 폴백 여부

    Returns:
        DeviceAdapterFactory: 팩토리 인스턴스
    """
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = DeviceAdapterFactory(
            mode=mode,
            fallback_to_simulation=fallback_to_simulation
        )
    return _factory_instance
