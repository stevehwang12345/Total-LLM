"""
APISpecExtractor - LLM 기반 API 스펙 추출

문서와 장치 정보를 LLM으로 분석하여 상세 API 스펙을 추출합니다.
"""

import logging
import json
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .analyzer import DeviceAnalysis, Protocol
from .doc_parser import APIDocument, APISpecification, ParsedEndpoint

logger = logging.getLogger(__name__)


@dataclass
class ExtractedAPI:
    """추출된 API 정보"""
    base_url: str
    auth_type: str
    content_type: str
    endpoints: List[Dict[str, Any]]
    common_headers: Dict[str, str] = field(default_factory=dict)
    error_codes: Dict[str, str] = field(default_factory=dict)
    rate_limits: Optional[Dict[str, Any]] = None
    notes: List[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_llm_response: Optional[str] = None


@dataclass
class EndpointDetail:
    """상세 엔드포인트 정보"""
    path: str
    method: str
    description: str
    category: str  # ptz, streaming, door_control, etc.
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    auth_required: bool = True
    example_request: Optional[str] = None
    example_response: Optional[str] = None


class APISpecExtractor:
    """
    LLM 기반 API 스펙 추출기

    문서와 장치 분석 결과를 결합하여 상세 API 스펙을 추출합니다.
    """

    # 프로토콜별 기본 API 패턴
    PROTOCOL_PATTERNS = {
        Protocol.ISAPI: {
            "base_url": "/ISAPI",
            "auth_type": "digest",
            "content_type": "application/xml",
            "common_endpoints": [
                "/System/deviceInfo",
                "/PTZ/channels/{id}/continuous",
                "/Streaming/channels/{id}/picture",
                "/ContentMgmt/record",
            ]
        },
        Protocol.CGI: {
            "base_url": "/cgi-bin",
            "auth_type": "digest",
            "content_type": "application/json",
            "common_endpoints": [
                "/ptz.cgi?action=start",
                "/configManager.cgi?action=getConfig",
                "/eventManager.cgi?action=attach",
            ]
        },
        Protocol.ONVIF: {
            "base_url": "/onvif",
            "auth_type": "ws-security",
            "content_type": "application/soap+xml",
            "common_endpoints": [
                "/device_service",
                "/ptz_service",
                "/media_service",
            ]
        },
        Protocol.REST: {
            "base_url": "/api",
            "auth_type": "bearer",
            "content_type": "application/json",
            "common_endpoints": [
                "/v1/devices",
                "/v1/status",
                "/v1/control",
            ]
        },
    }

    # 카테고리별 엔드포인트 힌트
    CATEGORY_HINTS = {
        "ptz": ["ptz", "pan", "tilt", "zoom", "continuous", "absolute", "preset"],
        "streaming": ["stream", "rtsp", "picture", "snapshot", "video", "live"],
        "recording": ["record", "playback", "search", "download", "contentmgmt"],
        "system": ["device", "system", "info", "config", "time", "network"],
        "door_control": ["door", "lock", "unlock", "access", "entry"],
        "user_management": ["user", "credential", "card", "fingerprint"],
        "events": ["event", "alarm", "notification", "subscribe"],
    }

    def __init__(self, llm_client=None, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            llm_client: vLLM 클라이언트
            config: 설정 옵션
        """
        self.llm_client = llm_client
        self.config = config or {}
        self._prompts_dir = Path(__file__).parent / "prompts"

    async def extract(
        self,
        device_analysis: DeviceAnalysis,
        documents: Optional[List[APIDocument]] = None,
        parsed_specs: Optional[List[APISpecification]] = None
    ) -> ExtractedAPI:
        """
        API 스펙 추출

        Args:
            device_analysis: 장치 분석 결과
            documents: API 문서 목록
            parsed_specs: 파싱된 API 스펙 목록

        Returns:
            추출된 API 정보
        """
        # 1. 프로토콜 기반 기본 패턴 적용
        base_pattern = self._get_base_pattern(device_analysis)

        # 2. 문서가 있으면 문서 기반 추출
        if parsed_specs:
            doc_based = self._extract_from_specs(parsed_specs, device_analysis)
            base_pattern = self._merge_patterns(base_pattern, doc_based)

        # 3. LLM으로 상세 스펙 추출
        if self.llm_client:
            llm_extracted = await self._llm_extract(
                device_analysis,
                documents,
                base_pattern
            )
            return self._finalize_extraction(base_pattern, llm_extracted)

        # 4. LLM 없으면 기본 패턴 반환
        return ExtractedAPI(
            base_url=base_pattern.get("base_url", "/"),
            auth_type=base_pattern.get("auth_type", "basic"),
            content_type=base_pattern.get("content_type", "application/json"),
            endpoints=self._generate_default_endpoints(device_analysis, base_pattern),
            confidence=0.5,
            notes=["Generated from protocol patterns without LLM analysis"],
        )

    def _get_base_pattern(self, device_analysis: DeviceAnalysis) -> Dict[str, Any]:
        """프로토콜 기반 기본 패턴 반환"""
        pattern = {
            "base_url": "/",
            "auth_type": "basic",
            "content_type": "application/json",
            "common_endpoints": [],
        }

        # 주요 프로토콜 패턴 적용
        for protocol in device_analysis.protocols:
            if protocol in self.PROTOCOL_PATTERNS:
                proto_pattern = self.PROTOCOL_PATTERNS[protocol]
                pattern["base_url"] = proto_pattern["base_url"]
                pattern["auth_type"] = proto_pattern["auth_type"]
                pattern["content_type"] = proto_pattern["content_type"]
                pattern["common_endpoints"].extend(proto_pattern["common_endpoints"])
                break

        # 장치 분석의 api_hints 적용
        if device_analysis.api_hints:
            hints = device_analysis.api_hints
            if "base_path" in hints:
                pattern["base_url"] = hints["base_path"]
            if "auth_type" in hints:
                pattern["auth_type"] = hints["auth_type"]

        return pattern

    def _extract_from_specs(
        self,
        specs: List[APISpecification],
        device_analysis: DeviceAnalysis
    ) -> Dict[str, Any]:
        """파싱된 스펙에서 패턴 추출"""
        result = {
            "base_url": "/",
            "auth_type": None,
            "endpoints": [],
        }

        for spec in specs:
            if spec.base_url and spec.base_url != "/":
                result["base_url"] = spec.base_url

            if spec.auth_type:
                result["auth_type"] = spec.auth_type

            for endpoint in spec.endpoints:
                result["endpoints"].append({
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "description": endpoint.description,
                    "parameters": endpoint.parameters,
                    "request_body": endpoint.request_body,
                    "responses": endpoint.responses,
                    "category": self._categorize_endpoint(endpoint.path),
                })

        return result

    def _categorize_endpoint(self, path: str) -> str:
        """엔드포인트 카테고리 분류"""
        path_lower = path.lower()

        for category, hints in self.CATEGORY_HINTS.items():
            if any(hint in path_lower for hint in hints):
                return category

        return "general"

    def _merge_patterns(
        self,
        base: Dict[str, Any],
        additional: Dict[str, Any]
    ) -> Dict[str, Any]:
        """패턴 병합"""
        result = base.copy()

        if additional.get("base_url") and additional["base_url"] != "/":
            result["base_url"] = additional["base_url"]

        if additional.get("auth_type"):
            result["auth_type"] = additional["auth_type"]

        # 엔드포인트 병합
        existing_paths = set(result.get("common_endpoints", []))
        for ep in additional.get("endpoints", []):
            if ep["path"] not in existing_paths:
                if "endpoints" not in result:
                    result["endpoints"] = []
                result["endpoints"].append(ep)

        return result

    async def _llm_extract(
        self,
        device_analysis: DeviceAnalysis,
        documents: Optional[List[APIDocument]],
        base_pattern: Dict[str, Any]
    ) -> Dict[str, Any]:
        """LLM 기반 상세 추출"""
        prompt = self._build_extraction_prompt(device_analysis, documents, base_pattern)

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.config.get("model", "default"),
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2048,
            )

            content = response.choices[0].message.content
            return self._parse_llm_response(content)

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {}

    def _get_system_prompt(self) -> str:
        """시스템 프롬프트 반환"""
        prompt_file = self._prompts_dir / "api_extraction.txt"
        if prompt_file.exists():
            return prompt_file.read_text()

        return """You are an API documentation analyst. Extract structured API specifications."""

    def _build_extraction_prompt(
        self,
        device_analysis: DeviceAnalysis,
        documents: Optional[List[APIDocument]],
        base_pattern: Dict[str, Any]
    ) -> str:
        """추출 프롬프트 생성"""
        doc_content = ""
        if documents:
            for doc in documents[:3]:  # 최대 3개 문서
                doc_content += f"\n--- Document ({doc.doc_type.value}) ---\n"
                doc_content += doc.content[:5000]  # 5KB 제한

        return f"""Analyze this device and extract detailed API specification.

## Device Information
- Type: {device_analysis.device_type.value}
- Manufacturer: {device_analysis.manufacturer}
- Model: {device_analysis.model or 'Unknown'}
- Protocols: {[p.value for p in device_analysis.protocols]}
- Capabilities: {device_analysis.capabilities}

## Base Pattern (from protocol)
{json.dumps(base_pattern, indent=2)}

## Documentation
{doc_content if doc_content else "No documentation available"}

## Task
Extract complete API specification including:
1. All available endpoints with parameters
2. Request/response formats
3. Authentication requirements
4. Error codes
5. Rate limits if mentioned

Respond in JSON format with this structure:
{{
  "base_url": "/ISAPI",
  "auth_type": "digest",
  "content_type": "application/xml",
  "endpoints": [
    {{
      "path": "/PTZ/channels/{{channel}}/continuous",
      "method": "PUT",
      "category": "ptz",
      "description": "Continuous PTZ movement",
      "parameters": [...],
      "request_body": {{...}},
      "response_schema": {{...}}
    }}
  ],
  "common_headers": {{}},
  "error_codes": {{}},
  "confidence": 0.85
}}
"""

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """LLM 응답 파싱"""
        try:
            # JSON 블록 추출
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                data["raw_llm_response"] = content
                return data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        return {"raw_llm_response": content}

    def _generate_default_endpoints(
        self,
        device_analysis: DeviceAnalysis,
        base_pattern: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """기본 엔드포인트 생성"""
        endpoints = []
        base_url = base_pattern.get("base_url", "")

        # CCTV 기본 엔드포인트
        if device_analysis.device_type.value == "cctv":
            endpoints.extend([
                {
                    "path": f"{base_url}/System/deviceInfo",
                    "method": "GET",
                    "category": "system",
                    "description": "Get device information",
                },
                {
                    "path": f"{base_url}/PTZ/channels/1/continuous",
                    "method": "PUT",
                    "category": "ptz",
                    "description": "Continuous PTZ movement",
                    "parameters": [
                        {"name": "pan", "type": "integer", "in": "body"},
                        {"name": "tilt", "type": "integer", "in": "body"},
                        {"name": "zoom", "type": "integer", "in": "body"},
                    ]
                },
                {
                    "path": f"{base_url}/Streaming/channels/1/picture",
                    "method": "GET",
                    "category": "streaming",
                    "description": "Capture snapshot",
                },
            ])

        # ACU 기본 엔드포인트
        elif device_analysis.device_type.value == "acu":
            endpoints.extend([
                {
                    "path": f"{base_url}/door/1/unlock",
                    "method": "POST",
                    "category": "door_control",
                    "description": "Unlock door",
                    "parameters": [
                        {"name": "duration", "type": "integer", "in": "body"},
                    ]
                },
                {
                    "path": f"{base_url}/door/1/status",
                    "method": "GET",
                    "category": "door_control",
                    "description": "Get door status",
                },
                {
                    "path": f"{base_url}/accesslog",
                    "method": "GET",
                    "category": "events",
                    "description": "Get access logs",
                    "parameters": [
                        {"name": "start_time", "type": "string", "in": "query"},
                        {"name": "end_time", "type": "string", "in": "query"},
                        {"name": "limit", "type": "integer", "in": "query"},
                    ]
                },
            ])

        return endpoints

    def _finalize_extraction(
        self,
        base_pattern: Dict[str, Any],
        llm_extracted: Dict[str, Any]
    ) -> ExtractedAPI:
        """최종 추출 결과 생성"""
        return ExtractedAPI(
            base_url=llm_extracted.get("base_url", base_pattern.get("base_url", "/")),
            auth_type=llm_extracted.get("auth_type", base_pattern.get("auth_type", "basic")),
            content_type=llm_extracted.get("content_type", base_pattern.get("content_type", "application/json")),
            endpoints=llm_extracted.get("endpoints", []),
            common_headers=llm_extracted.get("common_headers", {}),
            error_codes=llm_extracted.get("error_codes", {}),
            rate_limits=llm_extracted.get("rate_limits"),
            confidence=llm_extracted.get("confidence", 0.6),
            raw_llm_response=llm_extracted.get("raw_llm_response"),
            notes=llm_extracted.get("notes", []),
        )

    async def reverse_engineer(
        self,
        device_analysis: DeviceAnalysis,
        http_samples: List[Dict[str, Any]]
    ) -> ExtractedAPI:
        """
        HTTP 샘플에서 API 리버스 엔지니어링

        Args:
            device_analysis: 장치 분석 결과
            http_samples: 캡처된 HTTP 요청/응답 샘플

        Returns:
            추론된 API 스펙
        """
        if not self.llm_client:
            return self._basic_reverse_engineer(http_samples)

        prompt = self._build_reverse_prompt(device_analysis, http_samples)

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.config.get("model", "default"),
                messages=[
                    {"role": "system", "content": self._get_reverse_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2048,
            )

            content = response.choices[0].message.content
            parsed = self._parse_llm_response(content)

            return ExtractedAPI(
                base_url=parsed.get("base_url", "/"),
                auth_type=parsed.get("auth_mechanism", {}).get("type", "unknown"),
                content_type=parsed.get("response_format", "application/json"),
                endpoints=parsed.get("inferred_endpoints", []),
                confidence=0.6,  # 리버스 엔지니어링은 낮은 신뢰도
                notes=["Inferred from HTTP traffic analysis"],
                raw_llm_response=content,
            )

        except Exception as e:
            logger.error(f"Reverse engineering failed: {e}")
            return self._basic_reverse_engineer(http_samples)

    def _get_reverse_system_prompt(self) -> str:
        """리버스 엔지니어링 시스템 프롬프트"""
        prompt_file = self._prompts_dir / "protocol_reverse.txt"
        if prompt_file.exists():
            return prompt_file.read_text()

        return """You are a protocol reverse engineering expert."""

    def _build_reverse_prompt(
        self,
        device_analysis: DeviceAnalysis,
        http_samples: List[Dict[str, Any]]
    ) -> str:
        """리버스 엔지니어링 프롬프트 생성"""
        samples_str = json.dumps(http_samples[:10], indent=2)  # 최대 10개 샘플

        return f"""Analyze these HTTP samples and infer the API structure.

## Device Information
- Type: {device_analysis.device_type.value}
- Manufacturer: {device_analysis.manufacturer}
- Protocols: {[p.value for p in device_analysis.protocols]}

## HTTP Samples
{samples_str}

Analyze patterns and provide inferred API specification in JSON format.
"""

    def _basic_reverse_engineer(
        self,
        http_samples: List[Dict[str, Any]]
    ) -> ExtractedAPI:
        """기본 리버스 엔지니어링 (LLM 없이)"""
        endpoints = []
        paths_seen = set()

        for sample in http_samples:
            path = sample.get("path", sample.get("url", ""))
            method = sample.get("method", "GET")

            if path and path not in paths_seen:
                paths_seen.add(path)
                endpoints.append({
                    "path": path,
                    "method": method,
                    "category": self._categorize_endpoint(path),
                    "inferred": True,
                })

        # 공통 base_url 추출
        base_url = "/"
        if paths_seen:
            common_prefix = self._find_common_prefix(list(paths_seen))
            if common_prefix:
                base_url = common_prefix

        return ExtractedAPI(
            base_url=base_url,
            auth_type="unknown",
            content_type="application/json",
            endpoints=endpoints,
            confidence=0.4,
            notes=["Basic pattern extraction without LLM analysis"],
        )

    def _find_common_prefix(self, paths: List[str]) -> str:
        """경로들의 공통 접두사 찾기"""
        if not paths:
            return "/"

        # 첫 번째 슬래시 이후 경로 분리
        split_paths = [p.split("/")[1:] for p in paths if p.startswith("/")]
        if not split_paths:
            return "/"

        common = []
        for parts in zip(*split_paths):
            if len(set(parts)) == 1:
                common.append(parts[0])
            else:
                break

        return "/" + "/".join(common) if common else "/"
