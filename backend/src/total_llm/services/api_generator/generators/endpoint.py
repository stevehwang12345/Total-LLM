"""
EndpointGenerator - FastAPI 라우터 코드 생성기

LLM 분석 결과를 기반으로 FastAPI 라우터 코드를 생성합니다.
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from .base import BaseGenerator, GeneratedArtifact, ArtifactType
from ..analyzer import DeviceAnalysis, DeviceType
from ..spec_extractor import ExtractedAPI

logger = logging.getLogger(__name__)


class EndpointGenerator(BaseGenerator):
    """
    FastAPI 라우터 코드 생성기

    ExtractedAPI 스펙을 기반으로 FastAPI 라우터를 생성합니다.
    """

    # HTTP 메서드 → FastAPI 데코레이터 매핑
    METHOD_DECORATORS = {
        "GET": "get",
        "POST": "post",
        "PUT": "put",
        "DELETE": "delete",
        "PATCH": "patch",
    }

    # 카테고리별 태그
    CATEGORY_TAGS = {
        "ptz": "PTZ Control",
        "streaming": "Streaming",
        "recording": "Recording",
        "system": "System",
        "event": "Events",
        "door_control": "Door Control",
        "access": "Access Management",
        "user": "User Management",
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
        FastAPI 라우터 코드 생성

        Args:
            device_analysis: 장치 분석 결과
            api_spec: 추출된 API 스펙
            analysis_id: 분석 ID

        Returns:
            생성된 라우터 코드 아티팩트
        """
        # 템플릿 데이터 준비
        template_data = self._prepare_template_data(device_analysis, api_spec)

        # 템플릿 렌더링
        try:
            template = self.get_template("router.py.j2")
            code = template.render(**template_data)
        except Exception as e:
            logger.warning(f"Template rendering failed, using fallback: {e}")
            code = self._generate_fallback_code(device_analysis, api_spec)

        # 코드 검증
        if not self.validate_syntax(code):
            logger.warning("Generated router code has syntax errors")

        # 파일명 생성
        file_name = f"{device_analysis.manufacturer}_router.py"

        return GeneratedArtifact(
            artifact_type=ArtifactType.ENDPOINT,
            file_name=file_name,
            content=code,
            metadata={
                "device_type": device_analysis.device_type.value,
                "manufacturer": device_analysis.manufacturer,
                "route_count": len(template_data["routes"]),
                "tags": template_data["tags"],
            },
            analysis_id=analysis_id,
        )

    def _prepare_template_data(
        self,
        device_analysis: DeviceAnalysis,
        api_spec: ExtractedAPI
    ) -> Dict[str, Any]:
        """템플릿 데이터 준비"""
        # 라우트 생성
        routes = []
        tags = set()

        for endpoint in api_spec.endpoints:
            route = self._create_route(endpoint, device_analysis)
            routes.append(route)
            if route.get("tag"):
                tags.add(route["tag"])

        # 어댑터 클래스명
        adapter_class = f"{device_analysis.manufacturer.title()}Adapter"

        # 스키마 모듈명
        schema_module = f"{device_analysis.manufacturer}_schemas"

        # 라우터 prefix
        prefix = f"/{device_analysis.manufacturer}"

        return {
            "manufacturer": device_analysis.manufacturer,
            "device_type": device_analysis.device_type.value,
            "adapter_class": adapter_class,
            "schema_module": schema_module,
            "prefix": prefix,
            "routes": routes,
            "tags": list(tags),
        }

    def _create_route(
        self,
        endpoint: Dict[str, Any],
        device_analysis: DeviceAnalysis
    ) -> Dict[str, Any]:
        """엔드포인트에서 라우트 생성"""
        path = endpoint.get("path", "/")
        method = endpoint.get("method", "GET").upper()
        category = endpoint.get("category", "general")
        description = endpoint.get("description", "")

        # 함수명 생성
        func_name = self._generate_function_name(path, method)

        # FastAPI 경로로 변환 (ISAPI 스타일 → FastAPI 스타일)
        fastapi_path = self._convert_to_fastapi_path(path)

        # 파라미터 처리
        path_params = self._extract_path_params(path)
        query_params = self._extract_query_params(endpoint.get("parameters", []))
        body_params = endpoint.get("request_body")

        # 태그 결정
        tag = self.CATEGORY_TAGS.get(category, "General")

        # 응답 모델명
        response_model = self._generate_response_model_name(path, method)

        return {
            "path": fastapi_path,
            "method": self.METHOD_DECORATORS.get(method, "get"),
            "func_name": func_name,
            "description": description or f"{method} {path}",
            "tag": tag,
            "path_params": path_params,
            "query_params": query_params,
            "body_params": body_params,
            "response_model": response_model,
            "original_path": path,
            "category": category,
        }

    def _generate_function_name(self, path: str, method: str) -> str:
        """경로에서 함수명 생성"""
        # 경로 정리
        parts = path.strip("/").split("/")
        # 파라미터 제거
        parts = [p for p in parts if not p.startswith("{")]

        if not parts:
            return f"{method.lower()}_root"

        # 마지막 2개 부분 사용
        name_parts = parts[-2:] if len(parts) > 1 else parts
        name = "_".join(name_parts).lower()

        # 특수문자 제거
        name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

        return f"{method.lower()}_{name}"

    def _convert_to_fastapi_path(self, path: str) -> str:
        """ISAPI/CGI 경로를 FastAPI 경로로 변환"""
        # {id} → {item_id} 형태로 유지
        import re

        # 기존 파라미터 형식 유지
        fastapi_path = path

        # /ISAPI/ 또는 /cgi-bin/ 제거
        fastapi_path = re.sub(r'^/ISAPI', '', fastapi_path)
        fastapi_path = re.sub(r'^/cgi-bin', '', fastapi_path)

        # 빈 경로 방지
        if not fastapi_path or fastapi_path == "/":
            fastapi_path = "/"

        return fastapi_path

    def _extract_path_params(self, path: str) -> List[Dict[str, Any]]:
        """경로에서 path 파라미터 추출"""
        import re

        params = []
        matches = re.findall(r'\{(\w+)\}', path)

        for match in matches:
            params.append({
                "name": match,
                "type": "str",
                "description": f"Path parameter: {match}",
            })

        return params

    def _extract_query_params(self, parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """쿼리 파라미터 추출"""
        query_params = []

        for param in parameters:
            if param.get("in", "query") == "query":
                query_params.append({
                    "name": param.get("name", "param"),
                    "type": self._map_type(param.get("type", "string")),
                    "required": param.get("required", False),
                    "default": param.get("default"),
                    "description": param.get("description", ""),
                })

        return query_params

    def _map_type(self, json_type: str) -> str:
        """JSON 타입을 Python 타입으로 매핑"""
        type_map = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "List[Any]",
            "object": "Dict[str, Any]",
        }
        return type_map.get(json_type, "str")

    def _generate_response_model_name(self, path: str, method: str) -> str:
        """응답 모델명 생성"""
        parts = path.strip("/").split("/")
        parts = [p for p in parts if not p.startswith("{")]

        if not parts:
            return "Dict[str, Any]"

        name_parts = parts[-2:] if len(parts) > 1 else parts
        name = "".join(p.title() for p in name_parts)
        name = "".join(c for c in name if c.isalnum())

        return f"{name}Response"

    def _generate_fallback_code(
        self,
        device_analysis: DeviceAnalysis,
        api_spec: ExtractedAPI
    ) -> str:
        """템플릿 실패 시 폴백 코드 생성"""
        manufacturer = device_analysis.manufacturer
        class_name = f"{manufacturer.title()}Adapter"

        # 라우트 코드 생성
        routes_code = self._generate_route_code(api_spec.endpoints, device_analysis)

        return f'''"""
{manufacturer.title()} Device Router - Auto-generated FastAPI endpoints

Device Type: {device_analysis.device_type.value}
Generated by: LLM-Powered API Generator
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel

from total_llm.services.control.adapters.factory import DeviceAdapterFactory
from total_llm.services.control.adapters.base import DeviceCommand, DeviceResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/{manufacturer}",
    tags=["{manufacturer.title()} Device Control"],
)


# Response Models
class BaseResponse(BaseModel):
    success: bool = True
    timestamp: datetime = datetime.now()
    device_id: Optional[str] = None


class CommandResponse(BaseResponse):
    action: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StatusResponse(BaseResponse):
    connected: bool = False
    manufacturer: str = "{manufacturer}"
    capabilities: Dict[str, Any] = {{}}


# Dependency
async def get_adapter(device_id: str):
    """장치 어댑터 획득"""
    factory = DeviceAdapterFactory()
    adapter = factory.get_adapter(device_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Device not found: {{device_id}}")
    return adapter


# Routes
@router.get("/status/{{device_id}}", response_model=StatusResponse)
async def get_device_status(
    device_id: str = Path(..., description="장치 ID"),
    adapter=Depends(get_adapter)
):
    """장치 상태 조회"""
    try:
        status = await adapter.get_status()
        return StatusResponse(
            success=True,
            device_id=device_id,
            connected=adapter.is_connected,
            capabilities=await adapter.get_capabilities(),
        )
    except Exception as e:
        logger.error(f"Failed to get status: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect/{{device_id}}", response_model=BaseResponse)
async def connect_device(
    device_id: str = Path(..., description="장치 ID"),
    adapter=Depends(get_adapter)
):
    """장치 연결"""
    try:
        success = await adapter.connect()
        return BaseResponse(
            success=success,
            device_id=device_id,
        )
    except Exception as e:
        logger.error(f"Failed to connect: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect/{{device_id}}", response_model=BaseResponse)
async def disconnect_device(
    device_id: str = Path(..., description="장치 ID"),
    adapter=Depends(get_adapter)
):
    """장치 연결 해제"""
    try:
        success = await adapter.disconnect()
        return BaseResponse(
            success=success,
            device_id=device_id,
        )
    except Exception as e:
        logger.error(f"Failed to disconnect: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/command/{{device_id}}", response_model=CommandResponse)
async def execute_command(
    device_id: str = Path(..., description="장치 ID"),
    action: str = Body(..., description="명령 액션"),
    parameters: Dict[str, Any] = Body(default={{}}, description="명령 파라미터"),
    adapter=Depends(get_adapter)
):
    """명령 실행"""
    try:
        command = DeviceCommand(
            action=action,
            device_id=device_id,
            parameters=parameters,
        )
        response = await adapter.execute(command)
        return CommandResponse(
            success=response.success,
            device_id=device_id,
            action=action,
            result=response.result,
            error=response.error,
        )
    except Exception as e:
        logger.error(f"Failed to execute command: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))

{routes_code}
'''

    def _generate_route_code(
        self,
        endpoints: List[Dict[str, Any]],
        device_analysis: DeviceAnalysis
    ) -> str:
        """엔드포인트별 라우트 코드 생성"""
        routes = []

        for endpoint in endpoints[:10]:  # 최대 10개로 제한
            path = endpoint.get("path", "/")
            method = endpoint.get("method", "GET").lower()
            description = endpoint.get("description", f"{method.upper()} {path}")
            category = endpoint.get("category", "general")

            func_name = self._generate_function_name(path, method)
            fastapi_path = self._convert_to_fastapi_path(path)

            # 간단한 라우트 코드
            route_code = f'''
@router.{method}("{fastapi_path}", tags=["{self.CATEGORY_TAGS.get(category, 'General')}"])
async def {func_name}(
    device_id: str = Query(..., description="장치 ID"),
    adapter=Depends(get_adapter)
):
    """{description}"""
    try:
        command = DeviceCommand(
            action="{func_name}",
            device_id=device_id,
            parameters={{}},
        )
        response = await adapter.execute(command)
        return CommandResponse(
            success=response.success,
            device_id=device_id,
            action="{func_name}",
            result=response.result,
            error=response.error,
        )
    except Exception as e:
        logger.error(f"{{func_name}} failed: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))
'''
            routes.append(route_code)

        return "\n".join(routes)
