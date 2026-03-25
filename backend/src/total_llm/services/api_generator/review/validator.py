"""
CodeValidator - 생성된 코드 자동 검증

생성된 코드의 문법, 보안, 품질을 자동으로 검증합니다.
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """검증 레벨"""
    ERROR = "error"      # 반드시 수정 필요
    WARNING = "warning"  # 수정 권장
    INFO = "info"        # 참고 사항


class ValidationCategory(Enum):
    """검증 카테고리"""
    SYNTAX = "syntax"
    SECURITY = "security"
    QUALITY = "quality"
    COMPATIBILITY = "compatibility"
    PERFORMANCE = "performance"


@dataclass
class ValidationIssue:
    """검증 이슈"""
    level: ValidationLevel
    category: ValidationCategory
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """검증 결과"""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    score: float = 100.0  # 0-100 점수
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ValidationLevel.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ValidationLevel.WARNING)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "score": self.score,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "level": i.level.value,
                    "category": i.category.value,
                    "message": i.message,
                    "line_number": i.line_number,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "metadata": self.metadata,
        }


class CodeValidator:
    """
    코드 검증기

    생성된 코드의 문법, 보안, 품질을 검증합니다.
    """

    # 보안 위험 패턴
    SECURITY_PATTERNS = [
        (r'eval\s*\(', "eval() 사용은 보안 위험", ValidationLevel.ERROR),
        (r'exec\s*\(', "exec() 사용은 보안 위험", ValidationLevel.ERROR),
        (r'__import__\s*\(', "동적 import는 주의 필요", ValidationLevel.WARNING),
        (r'subprocess\..*shell\s*=\s*True', "shell=True는 보안 위험", ValidationLevel.ERROR),
        (r'os\.system\s*\(', "os.system() 대신 subprocess 사용 권장", ValidationLevel.WARNING),
        (r'pickle\.load', "pickle은 신뢰할 수 없는 데이터에 위험", ValidationLevel.WARNING),
        (r'yaml\.load\s*\([^,]+\)', "yaml.load()는 yaml.safe_load() 사용 권장", ValidationLevel.WARNING),
        (r'password\s*=\s*["\'][^"\']+["\']', "하드코딩된 비밀번호 감지", ValidationLevel.ERROR),
        (r'api_key\s*=\s*["\'][^"\']+["\']', "하드코딩된 API 키 감지", ValidationLevel.ERROR),
        (r'secret\s*=\s*["\'][^"\']+["\']', "하드코딩된 시크릿 감지", ValidationLevel.ERROR),
    ]

    # 품질 패턴
    QUALITY_PATTERNS = [
        (r'except\s*:', "bare except 사용은 권장하지 않음", ValidationLevel.WARNING),
        (r'# TODO', "TODO 코멘트 발견", ValidationLevel.INFO),
        (r'# FIXME', "FIXME 코멘트 발견", ValidationLevel.WARNING),
        (r'# HACK', "HACK 코멘트 발견", ValidationLevel.WARNING),
        (r'print\s*\(', "print() 대신 logging 사용 권장", ValidationLevel.INFO),
        (r'\.format\s*\(', "f-string 사용 권장 (Python 3.6+)", ValidationLevel.INFO),
        (r'type\s*\(\s*\w+\s*\)\s*==', "type() 대신 isinstance() 사용 권장", ValidationLevel.WARNING),
    ]

    # 필수 import 패턴 (파일 유형별)
    REQUIRED_IMPORTS = {
        "adapter": ["logging", "typing", "aiohttp", "DeviceCommand", "DeviceResponse"],
        "schema": ["typing", "pydantic", "BaseModel"],
        "router": ["fastapi", "APIRouter", "HTTPException"],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.strict_mode = self.config.get("strict_mode", False)

    def validate(self, code: str, artifact_type: str = "adapter") -> ValidationResult:
        """
        코드 전체 검증

        Args:
            code: 검증할 코드
            artifact_type: 아티팩트 타입 (adapter, schema, router, test)

        Returns:
            검증 결과
        """
        issues = []

        # 1. 구문 검증
        syntax_issues = self._validate_syntax(code)
        issues.extend(syntax_issues)

        # 구문 에러가 있으면 추가 검증 스킵
        if any(i.level == ValidationLevel.ERROR and i.category == ValidationCategory.SYNTAX
               for i in syntax_issues):
            return ValidationResult(
                valid=False,
                issues=issues,
                score=0.0,
                metadata={"artifact_type": artifact_type, "validation_complete": False},
            )

        # 2. 보안 검증
        security_issues = self._validate_security(code)
        issues.extend(security_issues)

        # 3. 품질 검증
        quality_issues = self._validate_quality(code)
        issues.extend(quality_issues)

        # 4. 호환성 검증
        compatibility_issues = self._validate_compatibility(code, artifact_type)
        issues.extend(compatibility_issues)

        # 5. 성능 검증
        performance_issues = self._validate_performance(code)
        issues.extend(performance_issues)

        # 점수 계산
        score = self._calculate_score(issues)

        # 유효성 판단
        has_errors = any(i.level == ValidationLevel.ERROR for i in issues)

        return ValidationResult(
            valid=not has_errors,
            issues=issues,
            score=score,
            metadata={
                "artifact_type": artifact_type,
                "validation_complete": True,
                "lines_of_code": len(code.splitlines()),
            },
        )

    def _validate_syntax(self, code: str) -> List[ValidationIssue]:
        """구문 검증"""
        issues = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                category=ValidationCategory.SYNTAX,
                message=f"구문 오류: {e.msg}",
                line_number=e.lineno,
                column=e.offset,
                suggestion="Python 문법을 확인하세요",
            ))

        return issues

    def _validate_security(self, code: str) -> List[ValidationIssue]:
        """보안 검증"""
        issues = []

        for pattern, message, level in self.SECURITY_PATTERNS:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                line_number = code[:match.start()].count('\n') + 1
                issues.append(ValidationIssue(
                    level=level,
                    category=ValidationCategory.SECURITY,
                    message=message,
                    line_number=line_number,
                    suggestion="보안 가이드라인을 참고하세요",
                ))

        return issues

    def _validate_quality(self, code: str) -> List[ValidationIssue]:
        """품질 검증"""
        issues = []

        for pattern, message, level in self.QUALITY_PATTERNS:
            for match in re.finditer(pattern, code):
                line_number = code[:match.start()].count('\n') + 1
                issues.append(ValidationIssue(
                    level=level,
                    category=ValidationCategory.QUALITY,
                    message=message,
                    line_number=line_number,
                ))

        # 함수 길이 검사
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    if func_lines > 50:
                        issues.append(ValidationIssue(
                            level=ValidationLevel.WARNING,
                            category=ValidationCategory.QUALITY,
                            message=f"함수 '{node.name}'가 너무 깁니다 ({func_lines}줄)",
                            line_number=node.lineno,
                            suggestion="함수를 작은 단위로 분리하세요",
                        ))
        except Exception:
            pass

        return issues

    def _validate_compatibility(self, code: str, artifact_type: str) -> List[ValidationIssue]:
        """호환성 검증"""
        issues = []

        # 필수 import 확인
        required = self.REQUIRED_IMPORTS.get(artifact_type, [])
        for req in required:
            if req not in code:
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"'{req}' import가 누락되었을 수 있습니다",
                    suggestion=f"import {req}를 추가하세요",
                ))

        # async/await 일관성 확인
        has_async_def = "async def" in code
        has_await = "await" in code

        if has_async_def and not has_await:
            issues.append(ValidationIssue(
                level=ValidationLevel.INFO,
                category=ValidationCategory.COMPATIBILITY,
                message="async 함수에서 await를 사용하지 않습니다",
                suggestion="비동기 작업이 필요 없다면 일반 함수로 변경하세요",
            ))

        return issues

    def _validate_performance(self, code: str) -> List[ValidationIssue]:
        """성능 검증"""
        issues = []

        # 비효율적인 패턴 감지
        inefficient_patterns = [
            (r'for\s+\w+\s+in\s+range\s*\(\s*len\s*\(', "range(len()) 대신 enumerate() 사용 권장"),
            (r'\+\s*=\s*["\']', "문자열 연결에 += 대신 join() 또는 f-string 사용 권장"),
            (r'time\.sleep\s*\(', "동기 sleep은 비동기 코드에서 asyncio.sleep() 사용 권장"),
        ]

        for pattern, message in inefficient_patterns:
            for match in re.finditer(pattern, code):
                line_number = code[:match.start()].count('\n') + 1
                issues.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    category=ValidationCategory.PERFORMANCE,
                    message=message,
                    line_number=line_number,
                ))

        return issues

    def _calculate_score(self, issues: List[ValidationIssue]) -> float:
        """점수 계산"""
        score = 100.0

        for issue in issues:
            if issue.level == ValidationLevel.ERROR:
                score -= 20.0
            elif issue.level == ValidationLevel.WARNING:
                score -= 5.0
            elif issue.level == ValidationLevel.INFO:
                score -= 1.0

        return max(0.0, score)

    def validate_adapter(self, code: str) -> ValidationResult:
        """어댑터 코드 검증"""
        result = self.validate(code, "adapter")

        # 어댑터 특화 검증
        additional_issues = []

        # BaseDeviceAdapter 상속 확인
        if "BaseDeviceAdapter" not in code and "BaseCCTVAdapter" not in code and "BaseACUAdapter" not in code:
            additional_issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                category=ValidationCategory.COMPATIBILITY,
                message="표준 어댑터 클래스를 상속하지 않습니다",
                suggestion="BaseCCTVAdapter 또는 BaseACUAdapter를 상속하세요",
            ))

        # 필수 메서드 확인
        required_methods = ["connect", "disconnect", "execute", "get_status"]
        for method in required_methods:
            if f"def {method}" not in code and f"async def {method}" not in code:
                additional_issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category=ValidationCategory.COMPATIBILITY,
                    message=f"필수 메서드 '{method}'가 누락되었습니다",
                    suggestion=f"{method} 메서드를 구현하세요",
                ))

        result.issues.extend(additional_issues)
        result.score = self._calculate_score(result.issues)
        result.valid = result.error_count == 0

        return result

    def validate_schema(self, code: str) -> ValidationResult:
        """스키마 코드 검증"""
        result = self.validate(code, "schema")

        additional_issues = []

        # BaseModel 상속 확인
        if "BaseModel" not in code:
            additional_issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                category=ValidationCategory.COMPATIBILITY,
                message="Pydantic BaseModel을 사용하지 않습니다",
                suggestion="from pydantic import BaseModel을 추가하세요",
            ))

        result.issues.extend(additional_issues)
        result.score = self._calculate_score(result.issues)
        result.valid = result.error_count == 0

        return result

    def validate_router(self, code: str) -> ValidationResult:
        """라우터 코드 검증"""
        result = self.validate(code, "router")

        additional_issues = []

        # APIRouter 사용 확인
        if "APIRouter" not in code:
            additional_issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                category=ValidationCategory.COMPATIBILITY,
                message="FastAPI APIRouter를 사용하지 않습니다",
                suggestion="from fastapi import APIRouter를 추가하세요",
            ))

        # 에러 핸들링 확인
        if "HTTPException" not in code:
            additional_issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                category=ValidationCategory.QUALITY,
                message="HTTPException을 사용한 에러 처리가 없습니다",
                suggestion="적절한 에러 핸들링을 추가하세요",
            ))

        result.issues.extend(additional_issues)
        result.score = self._calculate_score(result.issues)
        result.valid = result.error_count == 0

        return result
