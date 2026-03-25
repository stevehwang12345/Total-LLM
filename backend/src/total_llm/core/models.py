from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class IncidentType(str, Enum):
    NORMAL = "정상"
    VIOLENCE = "폭력"
    FALL = "넘어짐/낙상"
    INTRUSION = "침입"
    THREAT = "위협행위"
    ABNORMAL = "비정상행동"
    VANDALISM = "기물파손"
    FIRE = "화재"
    LOITERING = "배회"


class SeverityLevel(str, Enum):
    INFO = "정보"
    LOW = "낮음"
    MEDIUM = "중간"
    HIGH = "높음"
    CRITICAL = "매우높음"


class QAResult(BaseModel):
    q1_detection: str = Field(default="N/A", description="폭력/범죄 감지 여부")
    q2_classification: str = Field(default="N/A", description="사고 유형 분류")
    q3_subject: str = Field(default="N/A", description="관련 인물/객체 설명")
    q4_description: str = Field(default="N/A", description="상황 설명")


class IncidentAnalysis(BaseModel):
    qa_results: QAResult
    incident_type: IncidentType = IncidentType.NORMAL
    severity: SeverityLevel = SeverityLevel.INFO
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SecurityAlarmResult(BaseModel):
    threat_detected: bool = False
    threat_level: str = "FALSE_POSITIVE"
    description: str = ""
    recommended_actions: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class SecurityReport(BaseModel):
    report_id: str
    qa_results: QAResult
    incident_type: str
    severity: str
    raw_report: str = ""
    markdown_report: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGSearchResult(BaseModel):
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    strategy: str = "unknown"
    cached: bool = False
    query: str = ""
