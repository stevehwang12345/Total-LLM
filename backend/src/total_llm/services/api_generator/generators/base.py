"""
BaseGenerator - 코드 생성기 기본 클래스

모든 코드 생성기의 기본이 되는 추상 클래스입니다.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

from jinja2 import Environment, FileSystemLoader, Template

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """생성 아티팩트 유형"""
    ADAPTER = "adapter"
    SCHEMA = "schema"
    ENDPOINT = "endpoint"
    TEST = "test"


class ArtifactStatus(Enum):
    """아티팩트 상태"""
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    REJECTED = "rejected"


@dataclass
class GeneratedArtifact:
    """생성된 코드 아티팩트"""
    artifact_type: ArtifactType
    file_name: str
    content: str
    version: int = 1
    status: ArtifactStatus = ArtifactStatus.DRAFT
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    analysis_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "artifact_type": self.artifact_type.value,
            "file_name": self.file_name,
            "content": self.content,
            "version": self.version,
            "status": self.status.value,
            "metadata": self.metadata,
            "generated_at": self.generated_at,
            "analysis_id": self.analysis_id,
        }


class BaseGenerator(ABC):
    """
    코드 생성기 기본 클래스

    Jinja2 템플릿을 사용하여 코드를 생성합니다.
    """

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
        llm_client=None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            templates_dir: Jinja2 템플릿 디렉토리
            llm_client: vLLM 클라이언트 (선택적)
            config: 설정 옵션
        """
        self.templates_dir = templates_dir or Path(__file__).parent.parent / "templates"
        self.llm_client = llm_client
        self.config = config or {}

        # Jinja2 환경 설정
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 커스텀 필터 등록
        self._register_filters()

    def _register_filters(self):
        """Jinja2 커스텀 필터 등록"""
        self.jinja_env.filters["snake_case"] = self._to_snake_case
        self.jinja_env.filters["camel_case"] = self._to_camel_case
        self.jinja_env.filters["pascal_case"] = self._to_pascal_case
        self.jinja_env.filters["python_type"] = self._to_python_type

    @staticmethod
    def _to_snake_case(text: str) -> str:
        """스네이크 케이스 변환"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @staticmethod
    def _to_camel_case(text: str) -> str:
        """카멜 케이스 변환"""
        components = text.replace("-", "_").split("_")
        return components[0].lower() + "".join(x.title() for x in components[1:])

    @staticmethod
    def _to_pascal_case(text: str) -> str:
        """파스칼 케이스 변환"""
        components = text.replace("-", "_").split("_")
        return "".join(x.title() for x in components)

    @staticmethod
    def _to_python_type(api_type: str) -> str:
        """API 타입을 Python 타입으로 변환"""
        type_mapping = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "List",
            "object": "Dict[str, Any]",
        }
        return type_mapping.get(api_type.lower(), "Any")

    def get_template(self, template_name: str) -> Template:
        """템플릿 로드"""
        try:
            return self.jinja_env.get_template(template_name)
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {e}")
            raise

    @abstractmethod
    def generate(self, *args, **kwargs) -> GeneratedArtifact:
        """코드 생성 (하위 클래스에서 구현)"""
        pass

    def validate_syntax(self, code: str, language: str = "python") -> bool:
        """생성된 코드 문법 검증"""
        if language == "python":
            try:
                compile(code, "<string>", "exec")
                return True
            except SyntaxError as e:
                logger.warning(f"Syntax error in generated code: {e}")
                return False
        return True

    def format_code(self, code: str, language: str = "python") -> str:
        """코드 포맷팅"""
        if language == "python":
            try:
                import black
                return black.format_str(code, mode=black.Mode())
            except ImportError:
                logger.warning("black not installed, skipping formatting")
            except Exception as e:
                logger.warning(f"Failed to format code: {e}")
        return code
