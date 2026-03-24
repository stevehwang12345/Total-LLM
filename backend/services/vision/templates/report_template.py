"""
보안 보고서 템플릿

Markdown 형식의 표준화된 보안 사고 보고서 템플릿
"""

from typing import Dict, Optional
from datetime import datetime


class ReportTemplate:
    """
    보안 보고서 템플릿 생성기

    Features:
        - 표준화된 Markdown 형식
        - 메타데이터 자동 포함
        - 섹션별 구조화
        - 내보내기 호환성
    """

    @staticmethod
    def create_header(
        location: str,
        timestamp: str,
        incident_type: str,
        severity: str,
    ) -> str:
        """보고서 헤더 생성"""
        return f"""# 🚨 HDS LLM 보안 사고 보고서

---

## 📋 사고 개요

| 항목 | 내용 |
|------|------|
| **발생일시** | {timestamp} |
| **발생장소** | {location} |
| **사고유형** | {incident_type} |
| **심각도** | {severity} |
| **보고서 작성** | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |

---
"""

    @staticmethod
    def create_analysis_section(vision_analysis: str) -> str:
        """상황 분석 섹션 생성"""
        return f"""## 📸 상황 분석

### CCTV 영상 분석 결과

{vision_analysis}

---
"""

    @staticmethod
    def create_footer(report_id: Optional[str] = None) -> str:
        """보고서 푸터 생성"""
        footer = "\n---\n\n"
        footer += "## 📌 참고사항\n\n"
        footer += "- 본 보고서는 AI 분석 시스템에 의해 자동 생성되었습니다.\n"
        footer += "- 최종 판단은 보안 담당자의 검토를 거쳐야 합니다.\n"
        footer += "- CCTV 원본 영상은 별도로 보관 및 관리됩니다.\n\n"

        if report_id:
            footer += f"**보고서 ID**: `{report_id}`\n\n"

        footer += f"**생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        footer += "---\n\n"
        footer += "*이 문서의 내용은 보안 등급에 따라 처리되어야 합니다.*\n"

        return footer

    @staticmethod
    def format_complete_report(
        location: str,
        timestamp: str,
        incident_type: str,
        severity: str,
        vision_analysis: str,
        generated_report: str,
        report_id: Optional[str] = None,
    ) -> str:
        """
        완전한 보고서 생성

        Args:
            location: 발생 장소
            timestamp: 발생 시간
            incident_type: 사고 유형
            severity: 심각도
            vision_analysis: Vision 모델 분석 결과
            generated_report: Language 모델 생성 보고서
            report_id: 보고서 ID (선택)

        Returns:
            str: 완전한 Markdown 보고서
        """
        # 헤더
        report = ReportTemplate.create_header(
            location=location,
            timestamp=timestamp,
            incident_type=incident_type,
            severity=severity,
        )

        # Vision 분석 섹션 (선택적)
        # report += ReportTemplate.create_analysis_section(vision_analysis)

        # Language 모델 생성 보고서 본문
        report += generated_report

        # 푸터
        report += ReportTemplate.create_footer(report_id=report_id)

        return report

    @staticmethod
    def generate_report_id(timestamp: str, location: str) -> str:
        """
        보고서 ID 생성

        Format: SEC-YYYYMMDD-HHMMSS-LOCATION_HASH

        Args:
            timestamp: 발생 시간
            location: 발생 장소

        Returns:
            str: 보고서 ID
        """
        try:
            # 타임스탬프 파싱
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            date_part = dt.strftime("%Y%m%d-%H%M%S")
        except:
            # 파싱 실패 시 현재 시간 사용
            date_part = datetime.now().strftime("%Y%m%d-%H%M%S")

        # 장소 해시 (간단한 체크섬)
        location_hash = abs(hash(location)) % 10000

        return f"SEC-{date_part}-{location_hash:04d}"


class ReportMetadata:
    """보고서 메타데이터 관리"""

    def __init__(
        self,
        report_id: str,
        location: str,
        timestamp: str,
        incident_type: str,
        severity: str,
        confidence: float,
    ):
        self.report_id = report_id
        self.location = location
        self.timestamp = timestamp
        self.incident_type = incident_type
        self.severity = severity
        self.confidence = confidence
        self.created_at = datetime.now()

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "report_id": self.report_id,
            "location": self.location,
            "timestamp": self.timestamp,
            "incident_type": self.incident_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """Markdown 형식으로 변환"""
        return f"""## 📊 보고서 메타데이터

```json
{self.to_dict()}
```
"""
