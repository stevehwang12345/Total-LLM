"""
DeviceAnalyzer - LLM 기반 장치 분석기

네트워크 탐색 결과를 LLM으로 분석하여 장치 타입, 제조사, 프로토콜을 식별합니다.
"""

import logging
import json
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """장치 유형"""
    CCTV = "cctv"
    ACU = "acu"
    NVR = "nvr"
    DVR = "dvr"
    SENSOR = "sensor"
    UNKNOWN = "unknown"


class Protocol(Enum):
    """지원 프로토콜"""
    ONVIF = "onvif"
    RTSP = "rtsp"
    ISAPI = "isapi"  # Hikvision
    CGI = "cgi"  # Dahua
    WISENET = "wisenet"  # Hanwha
    REST = "rest"
    UNKNOWN = "unknown"


@dataclass
class DeviceFingerprint:
    """장치 핑거프린트 (네트워크 탐색 결과)"""
    ip: str
    ports: List[int]
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    http_headers: Dict[str, str] = field(default_factory=dict)
    http_response: Optional[str] = None
    onvif_info: Optional[Dict[str, Any]] = None
    banner: Optional[str] = None
    services: List[str] = field(default_factory=list)


@dataclass
class DeviceAnalysis:
    """장치 분석 결과"""
    device_type: DeviceType
    manufacturer: str
    model: Optional[str]
    protocols: List[Protocol]
    confidence: float
    firmware_version: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    api_hints: Dict[str, Any] = field(default_factory=dict)
    raw_llm_response: Optional[str] = None
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DeviceAnalyzer:
    """
    LLM 기반 장치 분석기

    네트워크 핑거프린트를 분석하여 장치 정보를 추출합니다.
    """

    # 알려진 제조사 패턴
    MANUFACTURER_PATTERNS = {
        "hikvision": ["hikvision", "hik", "ds-", "isapi"],
        "dahua": ["dahua", "dh-", "amcrest"],
        "hanwha": ["hanwha", "samsung", "wisenet", "snp-", "snv-", "snd-"],
        "axis": ["axis", "accc"],
        "bosch": ["bosch", "dinion", "autodome"],
        "uniview": ["uniview", "unv", "ipc-"],
        "zkteco": ["zkteco", "zk", "inbio", "c3-"],
        "suprema": ["suprema", "biostar", "bioentry"],
        "hid": ["hid", "iclass", "vertx"],
    }

    # 포트 기반 서비스 매핑
    PORT_SERVICES = {
        80: "http",
        443: "https",
        554: "rtsp",
        8000: "http_alt",
        8080: "http_proxy",
        8899: "onvif_events",
        37777: "dahua_rpc",
        4370: "zkteco_sdk",
    }

    def __init__(self, llm_client=None, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            llm_client: vLLM 클라이언트 (OpenAI 호환 API)
            config: 설정 옵션
        """
        self.llm_client = llm_client
        self.config = config or {}
        self._prompts_dir = Path(__file__).parent / "prompts"

    async def analyze(self, fingerprint: DeviceFingerprint) -> DeviceAnalysis:
        """
        장치 핑거프린트를 분석합니다.

        Args:
            fingerprint: 네트워크 탐색 결과

        Returns:
            DeviceAnalysis: 분석 결과
        """
        # 1. 룰 기반 사전 분석
        pre_analysis = self._pre_analyze(fingerprint)

        # 2. LLM 분석 (필요한 경우)
        if self.llm_client and pre_analysis["confidence"] < 0.8:
            llm_analysis = await self._llm_analyze(fingerprint, pre_analysis)
            return self._merge_analysis(pre_analysis, llm_analysis)

        # 3. 룰 기반 결과 반환
        return DeviceAnalysis(
            device_type=pre_analysis["device_type"],
            manufacturer=pre_analysis["manufacturer"],
            model=pre_analysis.get("model"),
            protocols=pre_analysis["protocols"],
            confidence=pre_analysis["confidence"],
            firmware_version=pre_analysis.get("firmware_version"),
            capabilities=pre_analysis.get("capabilities", []),
            api_hints=pre_analysis.get("api_hints", {}),
        )

    def _pre_analyze(self, fingerprint: DeviceFingerprint) -> Dict[str, Any]:
        """룰 기반 사전 분석"""
        result = {
            "device_type": DeviceType.UNKNOWN,
            "manufacturer": "unknown",
            "model": None,
            "protocols": [],
            "confidence": 0.0,
            "capabilities": [],
            "api_hints": {},
        }

        # 포트 기반 서비스 탐지
        services = []
        for port in fingerprint.ports:
            if port in self.PORT_SERVICES:
                services.append(self.PORT_SERVICES[port])

        # ONVIF 정보가 있으면 CCTV
        if fingerprint.onvif_info:
            result["device_type"] = DeviceType.CCTV
            result["protocols"].append(Protocol.ONVIF)
            result["confidence"] = 0.9

            # ONVIF에서 제조사/모델 추출
            if "manufacturer" in fingerprint.onvif_info:
                mfr = fingerprint.onvif_info["manufacturer"].lower()
                result["manufacturer"] = self._identify_manufacturer(mfr)

            if "model" in fingerprint.onvif_info:
                result["model"] = fingerprint.onvif_info["model"]

        # HTTP 헤더/응답에서 제조사 식별
        if fingerprint.http_headers:
            server = fingerprint.http_headers.get("Server", "").lower()
            result["manufacturer"] = self._identify_manufacturer(server) or result["manufacturer"]

        if fingerprint.http_response:
            response_lower = fingerprint.http_response.lower()

            # 제조사 식별
            for mfr, patterns in self.MANUFACTURER_PATTERNS.items():
                if any(p in response_lower for p in patterns):
                    result["manufacturer"] = mfr
                    break

            # 프로토콜 힌트
            if "isapi" in response_lower:
                result["protocols"].append(Protocol.ISAPI)
                result["api_hints"]["base_path"] = "/ISAPI"

            if "/cgi-bin" in response_lower:
                result["protocols"].append(Protocol.CGI)
                result["api_hints"]["base_path"] = "/cgi-bin"

        # 포트 기반 장치 유형 추정
        if 554 in fingerprint.ports:
            result["protocols"].append(Protocol.RTSP)
            if result["device_type"] == DeviceType.UNKNOWN:
                result["device_type"] = DeviceType.CCTV
                result["confidence"] = 0.7

        if 4370 in fingerprint.ports:
            result["device_type"] = DeviceType.ACU
            result["manufacturer"] = "zkteco"
            result["confidence"] = 0.85

        if 37777 in fingerprint.ports:
            result["device_type"] = DeviceType.CCTV
            result["manufacturer"] = "dahua"
            result["protocols"].append(Protocol.CGI)
            result["confidence"] = 0.85

        # 중복 제거
        result["protocols"] = list(set(result["protocols"]))

        return result

    def _identify_manufacturer(self, text: str) -> Optional[str]:
        """텍스트에서 제조사 식별"""
        text_lower = text.lower()
        for mfr, patterns in self.MANUFACTURER_PATTERNS.items():
            if any(p in text_lower for p in patterns):
                return mfr
        return None

    async def _llm_analyze(
        self,
        fingerprint: DeviceFingerprint,
        pre_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """LLM 기반 상세 분석"""
        prompt = self._build_analysis_prompt(fingerprint, pre_analysis)

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.config.get("model", "default"),
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1024,
            )

            content = response.choices[0].message.content
            return self._parse_llm_response(content)

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {}

    def _get_system_prompt(self) -> str:
        """시스템 프롬프트 반환"""
        prompt_file = self._prompts_dir / "device_classification.txt"
        if prompt_file.exists():
            return prompt_file.read_text()

        return """You are an expert in security device identification.
Analyze the provided device fingerprint and identify:
1. Device type (cctv, acu, nvr, dvr, sensor)
2. Manufacturer
3. Model (if identifiable)
4. Supported protocols
5. API capabilities

Respond in JSON format only."""

    def _build_analysis_prompt(
        self,
        fingerprint: DeviceFingerprint,
        pre_analysis: Dict[str, Any]
    ) -> str:
        """분석 프롬프트 생성"""
        data = {
            "ip": fingerprint.ip,
            "ports": fingerprint.ports,
            "hostname": fingerprint.hostname,
            "http_headers": fingerprint.http_headers,
            "http_response_snippet": (
                fingerprint.http_response[:500]
                if fingerprint.http_response
                else None
            ),
            "onvif_info": fingerprint.onvif_info,
            "banner": fingerprint.banner,
            "pre_analysis": {
                "device_type": pre_analysis["device_type"].value
                if isinstance(pre_analysis["device_type"], DeviceType)
                else pre_analysis["device_type"],
                "manufacturer": pre_analysis["manufacturer"],
                "confidence": pre_analysis["confidence"],
            }
        }

        return f"""Analyze this device fingerprint and provide detailed identification:

{json.dumps(data, indent=2, ensure_ascii=False)}

Provide your analysis in JSON format with these fields:
- device_type: string
- manufacturer: string
- model: string or null
- protocols: list of strings
- confidence: float (0-1)
- capabilities: list of strings
- api_hints: object with base_path, auth_type, etc.
"""

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """LLM 응답 파싱"""
        try:
            # JSON 블록 추출
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())

                # 타입 변환
                if "device_type" in data:
                    try:
                        data["device_type"] = DeviceType(data["device_type"])
                    except ValueError:
                        data["device_type"] = DeviceType.UNKNOWN

                if "protocols" in data:
                    protocols = []
                    for p in data["protocols"]:
                        try:
                            protocols.append(Protocol(p.lower()))
                        except ValueError:
                            protocols.append(Protocol.UNKNOWN)
                    data["protocols"] = protocols

                data["raw_llm_response"] = content
                return data

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")

        return {"raw_llm_response": content}

    def _merge_analysis(
        self,
        pre_analysis: Dict[str, Any],
        llm_analysis: Dict[str, Any]
    ) -> DeviceAnalysis:
        """룰 기반과 LLM 분석 결과 병합"""
        # LLM 결과 우선, 없으면 룰 기반 결과 사용
        device_type = llm_analysis.get("device_type", pre_analysis["device_type"])
        if isinstance(device_type, str):
            try:
                device_type = DeviceType(device_type)
            except ValueError:
                device_type = DeviceType.UNKNOWN

        protocols = llm_analysis.get("protocols", []) or pre_analysis["protocols"]
        if not protocols:
            protocols = [Protocol.UNKNOWN]

        # 신뢰도는 LLM 결과가 있으면 더 높게
        confidence = llm_analysis.get("confidence", pre_analysis["confidence"])
        if llm_analysis.get("raw_llm_response"):
            confidence = max(confidence, 0.7)

        return DeviceAnalysis(
            device_type=device_type,
            manufacturer=llm_analysis.get("manufacturer", pre_analysis["manufacturer"]),
            model=llm_analysis.get("model", pre_analysis.get("model")),
            protocols=protocols,
            confidence=confidence,
            firmware_version=llm_analysis.get("firmware_version"),
            capabilities=llm_analysis.get("capabilities", pre_analysis.get("capabilities", [])),
            api_hints={
                **pre_analysis.get("api_hints", {}),
                **llm_analysis.get("api_hints", {})
            },
            raw_llm_response=llm_analysis.get("raw_llm_response"),
        )

    async def analyze_batch(
        self,
        fingerprints: List[DeviceFingerprint]
    ) -> List[DeviceAnalysis]:
        """여러 장치 일괄 분석"""
        results = []
        for fp in fingerprints:
            try:
                analysis = await self.analyze(fp)
                results.append(analysis)
            except Exception as e:
                logger.error(f"Failed to analyze device {fp.ip}: {e}")
                results.append(DeviceAnalysis(
                    device_type=DeviceType.UNKNOWN,
                    manufacturer="unknown",
                    model=None,
                    protocols=[Protocol.UNKNOWN],
                    confidence=0.0,
                ))
        return results
