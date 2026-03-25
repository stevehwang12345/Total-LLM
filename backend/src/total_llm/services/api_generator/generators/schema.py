"""
SchemaGenerator - Pydantic 모델 코드 생성기

LLM 분석 결과를 기반으로 Pydantic 스키마 코드를 생성합니다.
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from .base import BaseGenerator, GeneratedArtifact, ArtifactType
from ..analyzer import DeviceAnalysis, DeviceType
from ..spec_extractor import ExtractedAPI

logger = logging.getLogger(__name__)


class SchemaGenerator(BaseGenerator):
    """
    Pydantic 모델 코드 생성기

    ExtractedAPI 스펙을 기반으로 요청/응답 Pydantic 모델을 생성합니다.
    """

    # JSON 타입 → Python/Pydantic 타입 매핑
    TYPE_MAPPING = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "List",
        "object": "Dict[str, Any]",
        "null": "None",
        # 특수 포맷
        "date": "date",
        "datetime": "datetime",
        "time": "time",
        "email": "EmailStr",
        "uri": "HttpUrl",
        "uuid": "UUID",
        "binary": "bytes",
    }

    # 공통 필드 패턴
    COMMON_FIELD_PATTERNS = {
        "id": {"type": "str", "description": "고유 식별자"},
        "name": {"type": "str", "description": "이름"},
        "status": {"type": "str", "description": "상태"},
        "timestamp": {"type": "datetime", "description": "타임스탬프"},
        "created_at": {"type": "datetime", "description": "생성 시간"},
        "updated_at": {"type": "datetime", "description": "수정 시간"},
        "enabled": {"type": "bool", "description": "활성화 여부"},
        "error": {"type": "Optional[str]", "description": "에러 메시지"},
        "message": {"type": "str", "description": "메시지"},
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
        Pydantic 스키마 코드 생성

        Args:
            device_analysis: 장치 분석 결과
            api_spec: 추출된 API 스펙
            analysis_id: 분석 ID

        Returns:
            생성된 스키마 코드 아티팩트
        """
        # 템플릿 데이터 준비
        template_data = self._prepare_template_data(device_analysis, api_spec)

        # 템플릿 렌더링
        try:
            template = self.get_template("schema.py.j2")
            code = template.render(**template_data)
        except Exception as e:
            logger.warning(f"Template rendering failed, using fallback: {e}")
            code = self._generate_fallback_code(device_analysis, api_spec)

        # 코드 검증
        if not self.validate_syntax(code):
            logger.warning("Generated schema code has syntax errors")

        # 파일명 생성
        file_name = f"{device_analysis.manufacturer}_schemas.py"

        return GeneratedArtifact(
            artifact_type=ArtifactType.SCHEMA,
            file_name=file_name,
            content=code,
            metadata={
                "device_type": device_analysis.device_type.value,
                "manufacturer": device_analysis.manufacturer,
                "model_count": len(template_data["models"]),
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
        models = []

        # 1. 공통 기본 모델 생성
        base_model = self._create_base_model(device_analysis)
        models.append(base_model)

        # 2. 엔드포인트별 Request/Response 모델 생성
        for endpoint in api_spec.endpoints:
            request_model = self._create_request_model(endpoint)
            if request_model:
                models.append(request_model)

            response_model = self._create_response_model(endpoint)
            if response_model:
                models.append(response_model)

        # 3. 에러 응답 모델
        error_model = self._create_error_model(api_spec)
        models.append(error_model)

        # 4. 상태 응답 모델
        status_model = self._create_status_model(device_analysis)
        models.append(status_model)

        # 중복 제거
        seen_names = set()
        unique_models = []
        for model in models:
            if model["name"] not in seen_names:
                seen_names.add(model["name"])
                unique_models.append(model)

        # imports 결정
        imports = self._determine_imports(unique_models)

        return {
            "manufacturer": device_analysis.manufacturer,
            "device_type": device_analysis.device_type.value,
            "models": unique_models,
            "imports": imports,
        }

    def _create_base_model(self, device_analysis: DeviceAnalysis) -> Dict[str, Any]:
        """기본 응답 모델 생성"""
        class_name = f"{device_analysis.manufacturer.title()}BaseResponse"

        fields = [
            {"name": "success", "type": "bool", "default": "True", "description": "요청 성공 여부"},
            {"name": "timestamp", "type": "datetime", "default": "Field(default_factory=datetime.now)", "description": "응답 시간"},
            {"name": "device_id", "type": "Optional[str]", "default": "None", "description": "장치 ID"},
        ]

        return {
            "name": class_name,
            "base_class": "BaseModel",
            "description": f"{device_analysis.manufacturer.title()} 기본 응답 모델",
            "fields": fields,
        }

    def _create_request_model(self, endpoint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """요청 모델 생성"""
        params = endpoint.get("parameters", [])
        request_body = endpoint.get("request_body")

        if not params and not request_body:
            return None

        # 모델명 생성
        path = endpoint.get("path", "")
        method = endpoint.get("method", "GET")
        model_name = self._generate_model_name(path, method, "Request")

        fields = []

        # 파라미터 → 필드
        for param in params:
            field = self._param_to_field(param)
            fields.append(field)

        # request_body → 필드
        if request_body:
            body_fields = self._body_to_fields(request_body)
            fields.extend(body_fields)

        if not fields:
            return None

        return {
            "name": model_name,
            "base_class": "BaseModel",
            "description": endpoint.get("description", f"{path} 요청 모델"),
            "fields": fields,
        }

    def _create_response_model(self, endpoint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """응답 모델 생성"""
        response_schema = endpoint.get("response_schema", {})

        if not response_schema:
            return None

        # 모델명 생성
        path = endpoint.get("path", "")
        method = endpoint.get("method", "GET")
        model_name = self._generate_model_name(path, method, "Response")

        fields = self._schema_to_fields(response_schema)

        if not fields:
            # 기본 필드 추가
            fields = [
                {"name": "data", "type": "Dict[str, Any]", "default": "Field(default_factory=dict)", "description": "응답 데이터"},
            ]

        return {
            "name": model_name,
            "base_class": "BaseModel",
            "description": endpoint.get("description", f"{path} 응답 모델"),
            "fields": fields,
        }

    def _create_error_model(self, api_spec: ExtractedAPI) -> Dict[str, Any]:
        """에러 응답 모델 생성"""
        fields = [
            {"name": "success", "type": "bool", "default": "False", "description": "항상 False"},
            {"name": "error_code", "type": "str", "default": None, "description": "에러 코드"},
            {"name": "error_message", "type": "str", "default": None, "description": "에러 메시지"},
            {"name": "details", "type": "Optional[Dict[str, Any]]", "default": "None", "description": "상세 정보"},
        ]

        return {
            "name": "ErrorResponse",
            "base_class": "BaseModel",
            "description": "에러 응답 모델",
            "fields": fields,
        }

    def _create_status_model(self, device_analysis: DeviceAnalysis) -> Dict[str, Any]:
        """장치 상태 모델 생성"""
        class_name = f"{device_analysis.manufacturer.title()}DeviceStatus"

        fields = [
            {"name": "connected", "type": "bool", "default": "False", "description": "연결 상태"},
            {"name": "device_id", "type": "str", "default": None, "description": "장치 ID"},
            {"name": "manufacturer", "type": "str", "default": f'"{device_analysis.manufacturer}"', "description": "제조사"},
            {"name": "model", "type": "Optional[str]", "default": "None", "description": "모델명"},
            {"name": "firmware_version", "type": "Optional[str]", "default": "None", "description": "펌웨어 버전"},
            {"name": "last_seen", "type": "Optional[datetime]", "default": "None", "description": "마지막 통신 시간"},
        ]

        # 장치 타입별 추가 필드
        if device_analysis.device_type == DeviceType.CCTV:
            fields.extend([
                {"name": "streaming", "type": "bool", "default": "False", "description": "스트리밍 상태"},
                {"name": "recording", "type": "bool", "default": "False", "description": "녹화 상태"},
                {"name": "ptz_available", "type": "bool", "default": "False", "description": "PTZ 지원 여부"},
            ])
        elif device_analysis.device_type == DeviceType.ACU:
            fields.extend([
                {"name": "door_count", "type": "int", "default": "0", "description": "관리 출입문 수"},
                {"name": "online_doors", "type": "int", "default": "0", "description": "온라인 출입문 수"},
            ])

        return {
            "name": class_name,
            "base_class": "BaseModel",
            "description": f"{device_analysis.manufacturer.title()} 장치 상태 모델",
            "fields": fields,
        }

    def _generate_model_name(self, path: str, method: str, suffix: str) -> str:
        """경로에서 모델명 생성"""
        # 경로 정리
        parts = path.strip("/").split("/")
        # 파라미터 제거
        parts = [p for p in parts if not p.startswith("{")]

        if not parts:
            return f"{method.title()}{suffix}"

        # 마지막 2개 부분 사용
        name_parts = parts[-2:] if len(parts) > 1 else parts
        name = "".join(p.title() for p in name_parts)

        # 특수문자 제거
        name = "".join(c for c in name if c.isalnum())

        return f"{name}{suffix}"

    def _param_to_field(self, param: Dict[str, Any]) -> Dict[str, Any]:
        """파라미터를 필드로 변환"""
        name = param.get("name", "param")
        param_type = param.get("type", "string")
        required = param.get("required", False)
        description = param.get("description", "")

        python_type = self.TYPE_MAPPING.get(param_type, "str")

        if not required:
            python_type = f"Optional[{python_type}]"
            default = "None"
        else:
            default = None

        return {
            "name": name,
            "type": python_type,
            "default": default,
            "description": description,
        }

    def _body_to_fields(self, request_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """request_body를 필드 목록으로 변환"""
        fields = []

        if isinstance(request_body, dict):
            for key, value in request_body.items():
                if isinstance(value, dict):
                    field_type = value.get("type", "string")
                    python_type = self.TYPE_MAPPING.get(field_type, "str")
                    required = value.get("required", False)

                    if not required:
                        python_type = f"Optional[{python_type}]"
                        default = "None"
                    else:
                        default = None

                    fields.append({
                        "name": key,
                        "type": python_type,
                        "default": default,
                        "description": value.get("description", ""),
                    })
                else:
                    fields.append({
                        "name": key,
                        "type": "Any",
                        "default": "None",
                        "description": "",
                    })

        return fields

    def _schema_to_fields(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """JSON 스키마를 필드 목록으로 변환"""
        fields = []

        if isinstance(schema, dict):
            properties = schema.get("properties", schema)
            required_fields = schema.get("required", [])

            for key, value in properties.items():
                if key in ["properties", "required", "type"]:
                    continue

                if isinstance(value, dict):
                    field_type = value.get("type", "string")
                    python_type = self.TYPE_MAPPING.get(field_type, "str")
                else:
                    python_type = "Any"

                is_required = key in required_fields

                if not is_required:
                    python_type = f"Optional[{python_type}]"
                    default = "None"
                else:
                    default = None

                fields.append({
                    "name": key,
                    "type": python_type,
                    "default": default,
                    "description": value.get("description", "") if isinstance(value, dict) else "",
                })

        return fields

    def _determine_imports(self, models: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """필요한 imports 결정"""
        imports = {
            "typing": ["Any", "Dict", "List", "Optional"],
            "datetime": [],
            "pydantic": ["BaseModel", "Field"],
            "uuid": [],
        }

        all_types = set()
        for model in models:
            for field in model.get("fields", []):
                field_type = field.get("type", "")
                all_types.add(field_type)

        # 타입별 import 추가
        for t in all_types:
            if "datetime" in t.lower():
                if "datetime" not in imports["datetime"]:
                    imports["datetime"].append("datetime")
            if "date" in t.lower() and "datetime" not in t.lower():
                if "date" not in imports["datetime"]:
                    imports["datetime"].append("date")
            if "UUID" in t:
                if "UUID" not in imports["uuid"]:
                    imports["uuid"].append("UUID")
            if "EmailStr" in t or "HttpUrl" in t:
                if "EmailStr" in t and "EmailStr" not in imports["pydantic"]:
                    imports["pydantic"].append("EmailStr")
                if "HttpUrl" in t and "HttpUrl" not in imports["pydantic"]:
                    imports["pydantic"].append("HttpUrl")

        # 빈 리스트 제거
        return {k: v for k, v in imports.items() if v}

    def _generate_fallback_code(
        self,
        device_analysis: DeviceAnalysis,
        api_spec: ExtractedAPI
    ) -> str:
        """템플릿 실패 시 폴백 코드 생성"""
        manufacturer = device_analysis.manufacturer.title()

        return f'''"""
{manufacturer} Device Schemas - Auto-generated Pydantic models

Device Type: {device_analysis.device_type.value}
Generated by: LLM-Powered API Generator
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class {manufacturer}BaseResponse(BaseModel):
    """기본 응답 모델"""
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.now)
    device_id: Optional[str] = None


class {manufacturer}DeviceStatus(BaseModel):
    """장치 상태 모델"""
    connected: bool = False
    device_id: str
    manufacturer: str = "{device_analysis.manufacturer}"
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    last_seen: Optional[datetime] = None


class ErrorResponse(BaseModel):
    """에러 응답 모델"""
    success: bool = False
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    """명령 요청 모델"""
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout: float = 10.0


class CommandResponse({manufacturer}BaseResponse):
    """명령 응답 모델"""
    action: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
'''
