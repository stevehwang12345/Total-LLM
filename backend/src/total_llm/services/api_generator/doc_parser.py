"""
DocumentationParser - API 문서 수집 및 파싱

제조사 API 문서를 수집하고 파싱하여 구조화된 정보를 추출합니다.
"""

import logging
import re
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DocType(Enum):
    """문서 유형"""
    OPENAPI = "openapi"
    SWAGGER = "swagger"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"
    UNKNOWN = "unknown"


@dataclass
class APIDocument:
    """API 문서"""
    doc_type: DocType
    source_url: Optional[str]
    content: str
    parsed_spec: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ParsedEndpoint:
    """파싱된 엔드포인트"""
    path: str
    method: str
    description: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class APISpecification:
    """API 스펙"""
    title: str
    version: str
    base_url: str
    auth_type: Optional[str] = None
    endpoints: List[ParsedEndpoint] = field(default_factory=list)
    schemas: Dict[str, Any] = field(default_factory=dict)
    raw_spec: Optional[Dict[str, Any]] = None


class DocumentationParser:
    """
    API 문서 파서

    다양한 형식의 API 문서를 파싱하여 구조화된 스펙을 추출합니다.
    """

    # 알려진 제조사 문서 URL
    MANUFACTURER_DOCS = {
        "hikvision": {
            "isapi": "https://www.hikvision.com/content/dam/hikvision/en/support/regional-materials/Brazil/ISAPI_EN.pdf",
            "sdk": "https://www.hikvision.com/en/support/download/sdk/",
        },
        "dahua": {
            "api": "https://www.dahuasecurity.com/support/downloadCenter",
        },
        "axis": {
            "vapix": "https://www.axis.com/vapix-library/",
        },
        "onvif": {
            "core": "https://www.onvif.org/profiles/",
            "spec": "https://www.onvif.org/ver20/ptz/wsdl/ptz.wsdl",
        },
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Args:
            cache_dir: 문서 캐시 디렉토리
        """
        self.cache_dir = cache_dir or Path("/tmp/api_docs_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_documentation(
        self,
        manufacturer: str,
        model: Optional[str] = None,
        protocol: Optional[str] = None
    ) -> List[APIDocument]:
        """
        제조사 API 문서를 수집합니다.

        Args:
            manufacturer: 제조사명
            model: 모델명 (선택)
            protocol: 프로토콜 (선택)

        Returns:
            수집된 문서 목록
        """
        documents = []

        # 1. 캐시 확인
        cached = self._check_cache(manufacturer, model, protocol)
        if cached:
            logger.info(f"Using cached documentation for {manufacturer}")
            return cached

        # 2. 알려진 문서 URL에서 수집
        if manufacturer.lower() in self.MANUFACTURER_DOCS:
            urls = self.MANUFACTURER_DOCS[manufacturer.lower()]
            for doc_name, url in urls.items():
                try:
                    doc = await self._fetch_url(url)
                    if doc:
                        doc.metadata["doc_name"] = doc_name
                        doc.metadata["manufacturer"] = manufacturer
                        documents.append(doc)
                except Exception as e:
                    logger.warning(f"Failed to fetch {url}: {e}")

        # 3. 웹 검색으로 추가 문서 수집 (선택적)
        if not documents:
            search_docs = await self._search_documentation(manufacturer, model, protocol)
            documents.extend(search_docs)

        # 4. 캐시 저장
        if documents:
            self._save_cache(manufacturer, model, protocol, documents)

        return documents

    async def _fetch_url(self, url: str) -> Optional[APIDocument]:
        """URL에서 문서 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return None

                    content_type = response.headers.get("Content-Type", "")
                    content = await response.text()

                    # 문서 유형 판단
                    doc_type = self._detect_doc_type(content_type, content, url)

                    return APIDocument(
                        doc_type=doc_type,
                        source_url=url,
                        content=content,
                        metadata={"content_type": content_type}
                    )

        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def _detect_doc_type(
        self,
        content_type: str,
        content: str,
        url: str
    ) -> DocType:
        """문서 유형 감지"""
        # Content-Type 기반
        if "json" in content_type:
            if '"openapi"' in content or '"swagger"' in content:
                return DocType.OPENAPI
            return DocType.SWAGGER

        if "pdf" in content_type:
            return DocType.PDF

        if "html" in content_type:
            return DocType.HTML

        # 확장자 기반
        if url.endswith(".json"):
            return DocType.OPENAPI
        if url.endswith(".yaml") or url.endswith(".yml"):
            return DocType.OPENAPI
        if url.endswith(".pdf"):
            return DocType.PDF

        # 내용 기반
        if content.strip().startswith("{") or content.strip().startswith("openapi:"):
            return DocType.OPENAPI

        if "<html" in content.lower() or "<!doctype" in content.lower():
            return DocType.HTML

        return DocType.UNKNOWN

    async def _search_documentation(
        self,
        manufacturer: str,
        model: Optional[str],
        protocol: Optional[str]
    ) -> List[APIDocument]:
        """웹 검색으로 문서 찾기 (향후 구현)"""
        # 현재는 빈 리스트 반환
        # 추후 웹 검색 API 연동 가능
        return []

    def parse_document(self, document: APIDocument) -> Optional[APISpecification]:
        """
        문서를 파싱하여 API 스펙 추출

        Args:
            document: API 문서

        Returns:
            파싱된 API 스펙
        """
        if document.doc_type == DocType.OPENAPI:
            return self._parse_openapi(document)
        elif document.doc_type == DocType.HTML:
            return self._parse_html(document)
        elif document.doc_type == DocType.TEXT:
            return self._parse_text(document)
        else:
            logger.warning(f"Unsupported document type: {document.doc_type}")
            return None

    def _parse_openapi(self, document: APIDocument) -> Optional[APISpecification]:
        """OpenAPI/Swagger 스펙 파싱"""
        try:
            spec = json.loads(document.content)
        except json.JSONDecodeError:
            try:
                import yaml
                spec = yaml.safe_load(document.content)
            except Exception:
                logger.error("Failed to parse OpenAPI spec")
                return None

        # OpenAPI 3.x 또는 Swagger 2.x
        version = spec.get("openapi") or spec.get("swagger") or "unknown"
        info = spec.get("info", {})

        # 기본 URL 추출
        if "servers" in spec:  # OpenAPI 3.x
            base_url = spec["servers"][0].get("url", "/")
        else:  # Swagger 2.x
            base_url = spec.get("basePath", "/")

        # 엔드포인트 추출
        endpoints = []
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    endpoint = ParsedEndpoint(
                        path=path,
                        method=method.upper(),
                        description=details.get("summary") or details.get("description"),
                        parameters=details.get("parameters", []),
                        request_body=details.get("requestBody"),
                        responses=details.get("responses", {}),
                        tags=details.get("tags", []),
                    )
                    endpoints.append(endpoint)

        # 인증 타입 추출
        auth_type = None
        security_schemes = spec.get("components", {}).get("securitySchemes", {})
        if not security_schemes:
            security_schemes = spec.get("securityDefinitions", {})
        if security_schemes:
            for scheme_name, scheme in security_schemes.items():
                if scheme.get("type") == "http":
                    auth_type = scheme.get("scheme", "basic")
                elif scheme.get("type") == "apiKey":
                    auth_type = "apikey"
                elif scheme.get("type") == "oauth2":
                    auth_type = "oauth2"
                break

        return APISpecification(
            title=info.get("title", "Unknown API"),
            version=info.get("version", version),
            base_url=base_url,
            auth_type=auth_type,
            endpoints=endpoints,
            schemas=spec.get("components", {}).get("schemas", {})
                    or spec.get("definitions", {}),
            raw_spec=spec,
        )

    def _parse_html(self, document: APIDocument) -> Optional[APISpecification]:
        """HTML 문서에서 API 정보 추출"""
        soup = BeautifulSoup(document.content, "html.parser")

        # 제목 추출
        title_tag = soup.find("title")
        title = title_tag.text if title_tag else "Unknown API"

        # API 엔드포인트 패턴 찾기
        endpoints = []

        # 코드 블록에서 API 패턴 추출
        code_blocks = soup.find_all(["code", "pre"])
        for block in code_blocks:
            text = block.get_text()

            # HTTP 메서드 + 경로 패턴
            api_patterns = re.findall(
                r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s<>"]+)',
                text,
                re.IGNORECASE
            )

            for method, path in api_patterns:
                endpoint = ParsedEndpoint(
                    path=path,
                    method=method.upper(),
                )
                endpoints.append(endpoint)

        # URL 패턴에서 API 경로 추출
        all_text = soup.get_text()
        url_patterns = re.findall(r'/api/[^\s<>"]+', all_text)
        for path in set(url_patterns):
            if not any(e.path == path for e in endpoints):
                endpoint = ParsedEndpoint(
                    path=path,
                    method="GET",  # 기본값
                )
                endpoints.append(endpoint)

        if not endpoints:
            return None

        return APISpecification(
            title=title,
            version="unknown",
            base_url="/",
            endpoints=endpoints,
        )

    def _parse_text(self, document: APIDocument) -> Optional[APISpecification]:
        """텍스트 문서에서 API 정보 추출"""
        content = document.content

        # HTTP 메서드 + 경로 패턴 찾기
        endpoints = []
        api_patterns = re.findall(
            r'(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)',
            content,
            re.IGNORECASE
        )

        for method, path in api_patterns:
            endpoint = ParsedEndpoint(
                path=path.rstrip(",.;:"),
                method=method.upper(),
            )
            endpoints.append(endpoint)

        if not endpoints:
            return None

        return APISpecification(
            title="Extracted API",
            version="unknown",
            base_url="/",
            endpoints=endpoints,
        )

    def _check_cache(
        self,
        manufacturer: str,
        model: Optional[str],
        protocol: Optional[str]
    ) -> Optional[List[APIDocument]]:
        """캐시 확인"""
        cache_key = f"{manufacturer}_{model or 'all'}_{protocol or 'all'}"
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)

                # 캐시 유효기간 확인 (7일)
                cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
                if (datetime.now() - cached_at).days < 7:
                    documents = []
                    for doc_data in data.get("documents", []):
                        documents.append(APIDocument(
                            doc_type=DocType(doc_data["doc_type"]),
                            source_url=doc_data.get("source_url"),
                            content=doc_data["content"],
                            metadata=doc_data.get("metadata", {}),
                            fetched_at=doc_data.get("fetched_at"),
                        ))
                    return documents
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        return None

    def _save_cache(
        self,
        manufacturer: str,
        model: Optional[str],
        protocol: Optional[str],
        documents: List[APIDocument]
    ):
        """캐시 저장"""
        cache_key = f"{manufacturer}_{model or 'all'}_{protocol or 'all'}"
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            data = {
                "cached_at": datetime.now().isoformat(),
                "documents": [
                    {
                        "doc_type": doc.doc_type.value,
                        "source_url": doc.source_url,
                        "content": doc.content[:100000],  # 100KB 제한
                        "metadata": doc.metadata,
                        "fetched_at": doc.fetched_at,
                    }
                    for doc in documents
                ]
            }

            with open(cache_file, "w") as f:
                json.dump(data, f)

        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def parse_from_http_response(self, response_data: Dict[str, Any]) -> APISpecification:
        """
        HTTP 응답에서 API 스펙 추론

        Args:
            response_data: HTTP 응답 데이터 (headers, body, status_code 등)

        Returns:
            추론된 API 스펙
        """
        endpoints = []

        # 응답 패턴에서 가능한 엔드포인트 추론
        if "request_path" in response_data:
            path = response_data["request_path"]
            method = response_data.get("request_method", "GET")

            # 응답 구조 분석
            body = response_data.get("body", {})
            params = []

            # 경로 파라미터 추출
            path_params = re.findall(r'\{(\w+)\}', path)
            for param in path_params:
                params.append({
                    "name": param,
                    "in": "path",
                    "type": "string",
                    "required": True,
                })

            endpoint = ParsedEndpoint(
                path=path,
                method=method,
                parameters=params,
                responses={"200": {"schema": body}} if body else {},
            )
            endpoints.append(endpoint)

        return APISpecification(
            title="Inferred API",
            version="inferred",
            base_url=response_data.get("base_url", "/"),
            endpoints=endpoints,
        )
