"""
AdapterGenerator - 장치 어댑터 코드 생성기

LLM 분석 결과를 기반으로 장치 어댑터 Python 코드를 생성합니다.
"""

import logging
from typing import Any, Dict, Optional
from pathlib import Path

from .base import BaseGenerator, GeneratedArtifact, ArtifactType
from ..analyzer import DeviceAnalysis, DeviceType, Protocol
from ..spec_extractor import ExtractedAPI

logger = logging.getLogger(__name__)


class AdapterGenerator(BaseGenerator):
    """
    장치 어댑터 코드 생성기

    ExtractedAPI 스펙을 기반으로 BaseCCTVAdapter 또는 BaseACUAdapter를
    상속하는 어댑터 클래스를 생성합니다.
    """

    # 프로토콜별 기본 설정
    PROTOCOL_CONFIG = {
        Protocol.ISAPI: {
            "http_library": "aiohttp",
            "auth_class": "DigestAuth",
            "content_type": "application/xml",
            "response_parser": "xml.etree.ElementTree",
        },
        Protocol.CGI: {
            "http_library": "aiohttp",
            "auth_class": "DigestAuth",
            "content_type": "application/json",
            "response_parser": "json",
        },
        Protocol.ONVIF: {
            "http_library": "zeep",
            "auth_class": "WS-Security",
            "content_type": "application/soap+xml",
            "response_parser": "zeep",
        },
        Protocol.REST: {
            "http_library": "aiohttp",
            "auth_class": "BasicAuth",
            "content_type": "application/json",
            "response_parser": "json",
        },
    }

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
        llm_client=None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(templates_dir, llm_client, config)

    def generate(
        self,
        device_analysis: DeviceAnalysis,
        api_spec: ExtractedAPI,
        analysis_id: Optional[str] = None
    ) -> GeneratedArtifact:
        """
        어댑터 코드 생성

        Args:
            device_analysis: 장치 분석 결과
            api_spec: 추출된 API 스펙
            analysis_id: 분석 ID

        Returns:
            생성된 어댑터 코드 아티팩트
        """
        # 템플릿 데이터 준비
        template_data = self._prepare_template_data(device_analysis, api_spec)

        # 템플릿 렌더링
        try:
            template = self.get_template("adapter.py.j2")
            code = template.render(**template_data)
        except Exception as e:
            logger.warning(f"Template rendering failed, using fallback: {e}")
            code = self._generate_fallback_code(device_analysis, api_spec)

        # 코드 검증
        if not self.validate_syntax(code):
            logger.warning("Generated code has syntax errors")

        # 파일명 생성
        file_name = f"{device_analysis.manufacturer}_adapter.py"

        return GeneratedArtifact(
            artifact_type=ArtifactType.ADAPTER,
            file_name=file_name,
            content=code,
            metadata={
                "device_type": device_analysis.device_type.value,
                "manufacturer": device_analysis.manufacturer,
                "model": device_analysis.model,
                "protocols": [p.value for p in device_analysis.protocols],
                "base_url": api_spec.base_url,
                "auth_type": api_spec.auth_type,
                "endpoint_count": len(api_spec.endpoints),
            },
            analysis_id=analysis_id,
        )

    def _prepare_template_data(
        self,
        device_analysis: DeviceAnalysis,
        api_spec: ExtractedAPI
    ) -> Dict[str, Any]:
        """템플릿 데이터 준비"""
        # 기본 클래스 결정
        if device_analysis.device_type == DeviceType.CCTV:
            base_class = "BaseCCTVAdapter"
            base_import = "from services.control.adapters.cctv.base import BaseCCTVAdapter"
        elif device_analysis.device_type == DeviceType.ACU:
            base_class = "BaseACUAdapter"
            base_import = "from services.control.adapters.acu.base import BaseACUAdapter"
        else:
            base_class = "BaseDeviceAdapter"
            base_import = "from services.control.adapters.base import BaseDeviceAdapter"

        # 프로토콜 설정
        primary_protocol = device_analysis.protocols[0] if device_analysis.protocols else Protocol.REST
        proto_config = self.PROTOCOL_CONFIG.get(primary_protocol, self.PROTOCOL_CONFIG[Protocol.REST])

        # 메서드 생성
        methods = self._generate_methods(device_analysis, api_spec)

        # 클래스명 생성
        class_name = f"{device_analysis.manufacturer.title()}Adapter"

        return {
            "class_name": class_name,
            "base_class": base_class,
            "base_import": base_import,
            "manufacturer": device_analysis.manufacturer,
            "model": device_analysis.model,
            "device_type": device_analysis.device_type.value,
            "protocols": [p.value for p in device_analysis.protocols],
            "base_url": api_spec.base_url,
            "auth_type": api_spec.auth_type,
            "content_type": api_spec.content_type,
            "http_library": proto_config["http_library"],
            "auth_class": proto_config["auth_class"],
            "response_parser": proto_config["response_parser"],
            "methods": methods,
            "endpoints": api_spec.endpoints,
            "common_headers": api_spec.common_headers,
            "error_codes": api_spec.error_codes,
        }

    def _generate_methods(
        self,
        device_analysis: DeviceAnalysis,
        api_spec: ExtractedAPI
    ) -> list:
        """엔드포인트별 메서드 생성"""
        methods = []

        for endpoint in api_spec.endpoints:
            method_name = self._endpoint_to_method_name(endpoint)
            method_data = {
                "name": method_name,
                "path": endpoint.get("path", "/"),
                "http_method": endpoint.get("method", "GET"),
                "description": endpoint.get("description", ""),
                "category": endpoint.get("category", "general"),
                "parameters": endpoint.get("parameters", []),
                "request_body": endpoint.get("request_body"),
                "returns": endpoint.get("response_schema", {}),
            }
            methods.append(method_data)

        return methods

    def _endpoint_to_method_name(self, endpoint: Dict[str, Any]) -> str:
        """엔드포인트 경로를 메서드명으로 변환"""
        path = endpoint.get("path", "")
        method = endpoint.get("method", "GET").lower()

        # 경로에서 메서드명 추출
        parts = path.strip("/").split("/")
        # 파라미터 제거
        parts = [p for p in parts if not p.startswith("{")]

        if not parts:
            return f"{method}_endpoint"

        # 마지막 2개 부분 사용
        name_parts = parts[-2:] if len(parts) > 1 else parts
        name = "_".join(name_parts).lower()

        # 특수문자 제거
        name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

        return f"{method}_{name}"

    def _generate_fallback_code(
        self,
        device_analysis: DeviceAnalysis,
        api_spec: ExtractedAPI
    ) -> str:
        """템플릿 실패 시 폴백 코드 생성"""
        class_name = f"{device_analysis.manufacturer.title()}Adapter"

        if device_analysis.device_type == DeviceType.CCTV:
            base_class = "BaseCCTVAdapter"
            base_import = "from services.control.adapters.cctv.base import BaseCCTVAdapter"
        elif device_analysis.device_type == DeviceType.ACU:
            base_class = "BaseACUAdapter"
            base_import = "from services.control.adapters.acu.base import BaseACUAdapter"
        else:
            base_class = "BaseDeviceAdapter"
            base_import = "from services.control.adapters.base import BaseDeviceAdapter"

        return f'''"""
{class_name} - Auto-generated adapter for {device_analysis.manufacturer} devices

Device Type: {device_analysis.device_type.value}
Protocols: {[p.value for p in device_analysis.protocols]}
Generated by: LLM-Powered API Generator
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

import aiohttp
from aiohttp import BasicAuth, DigestAuth

{base_import}
from total_llm.services.control.adapters.base import DeviceCommand, DeviceResponse

logger = logging.getLogger(__name__)


class {class_name}({base_class}):
    """
    {device_analysis.manufacturer.title()} Device Adapter

    Base URL: {api_spec.base_url}
    Auth Type: {api_spec.auth_type}
    """

    def __init__(self, device_info: Dict[str, Any]):
        super().__init__(device_info)
        self.base_url = f"http://{{self.ip}}:{{self.port}}{api_spec.base_url}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> bool:
        """Establish connection to device"""
        try:
            auth = DigestAuth(self.username, self.password)
            self.session = aiohttp.ClientSession(auth=auth)

            # Test connection
            async with self.session.get(f"{{self.base_url}}/System/deviceInfo") as resp:
                self._connected = resp.status == 200
                return self._connected
        except Exception as e:
            logger.error(f"Connection failed: {{e}}")
            return False

    async def disconnect(self) -> bool:
        """Close connection"""
        if self.session:
            await self.session.close()
            self.session = None
        self._connected = False
        return True

    async def execute(self, command: DeviceCommand) -> DeviceResponse:
        """Execute device command"""
        action = command.action

        # Route to specific method
        handler = getattr(self, f"_handle_{{action}}", None)
        if handler:
            return await handler(command)

        return DeviceResponse(
            success=False,
            device_id=self.device_id,
            action=action,
            error=f"Unknown action: {{action}}",
            timestamp=datetime.now().isoformat(),
        )

    async def get_status(self) -> Dict[str, Any]:
        """Get device status"""
        return {{
            "connected": self._connected,
            "device_id": self.device_id,
            "manufacturer": "{device_analysis.manufacturer}",
        }}

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get device capabilities"""
        return {{
            "device_type": "{device_analysis.device_type.value}",
            "protocols": {[p.value for p in device_analysis.protocols]},
            "capabilities": {device_analysis.capabilities},
        }}
'''
