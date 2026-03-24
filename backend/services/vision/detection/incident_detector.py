"""
보안 사고 감지 시스템

Vision 모델의 분석 결과에서 사고 유형과 심각도를 판단합니다.

Detection Strategy:
    - 키워드 기반 패턴 매칭
    - 심각도 자동 평가
    - 사고 유형 분류
"""

import re
from typing import Dict, List, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IncidentType(Enum):
    """사고 유형"""
    VIOLENCE = "폭력"
    FIGHTING = "싸움"
    FALLING = "넘어짐/낙상"
    INTRUSION = "침입"
    THREATENING = "위협행위"
    ABNORMAL_BEHAVIOR = "비정상행동"
    NORMAL = "정상"
    NO_PERSON = "분석불가-사람없음"
    UNCLEAR = "판단불가-불분명"


class SeverityLevel(Enum):
    """심각도 수준"""
    CRITICAL = "매우높음"
    HIGH = "높음"
    MEDIUM = "중간"
    LOW = "낮음"
    INFO = "정보"


class IncidentDetector:
    """
    사고 감지 및 분류 시스템

    Features:
        - 키워드 기반 사고 유형 감지
        - 심각도 자동 평가
        - 다중 사고 유형 지원
        - 신뢰도 점수 계산
    """

    def __init__(self):
        """키워드 패턴 초기화 - 구조화된 영어 출력 형식에 맞게 설정"""

        # 1순위: 사람 없음 패턴 (한글 + 영어)
        self.no_person_patterns = [
            # 한글 (기존 호환성)
            r"사람.*없",
            r"인물.*없",
            r"사람 없음",
            r"분석 대상 없음",
            r"사람.*미감지",
            # 영어 (새 구조화된 형식)
            r"Count:\s*none",
            r"Count:\s*0",
            r"no\s+people",
        ]

        # 2순위: 판단 불가 패턴 (한글 + 영어)
        self.unclear_patterns = [
            # 한글
            r"판단.*불가",
            r"불분명",
            r"확실하지 않",
            r"추가 검토 필요",
            r"명확하지 않",
            # 영어 (새 구조화된 형식)
            r"Situation:\s*unclear",
            r"uncertain",
        ]

        # 3순위: 정상 상황 패턴 (한글 + 영어)
        self.normal_patterns = [
            # 한글
            r"정상 상황",
            r"보안 사고.*없",
            r"이상.*없",
            r"특이사항.*없",
            r"안전",
            r"일상적",
            # 영어 (새 구조화된 형식)
            r"Situation:\s*normal",
            r"State:\s*normal",
        ]

        # 4순위: 사고 유형별 키워드 패턴 (한글 + 영어)
        self.incident_patterns = {
            IncidentType.VIOLENCE: [
                # 한글
                r"폭력.*관찰",
                r"공격.*행위",
                r"구타",
                r"가격",
                r"때리",
                r"주먹",
                r"폭행",
                # 영어 (새 구조화된 형식)
                r"Violence:\s*yes",
                r"Action:.*attack",
                r"Action:.*punch",
                r"Action:.*hit",
                r"Action:.*strike",
                r"State:\s*dangerous",
            ],
            IncidentType.FIGHTING: [
                # 한글
                r"싸움.*진행",
                r"충돌.*관찰",
                r"몸싸움",
                r"격투",
                r"밀치",
                r"언쟁",
                # 영어 (새 구조화된 형식)
                r"Fighting:\s*yes",
                r"Action:.*fight",
                r"Action:.*struggle",
                r"Action:.*grapple",
            ],
            IncidentType.FALLING: [
                # 한글
                r"넘어짐.*관찰",
                r"쓰러짐",
                r"낙상",
                r"바닥.*누워",
                r"자세.*쓰러",
                # 영어 (새 구조화된 형식)
                r"Falling:\s*yes",
                r"Posture:\s*fallen",
                r"Posture:\s*lying",
                r"Action:.*fell",
                r"State:\s*injured",
            ],
            IncidentType.INTRUSION: [
                # 한글
                r"침입",
                r"무단.*출입",
                r"허가.*없",
                r"불법.*진입",
                # 영어 (새 구조화된 형식)
                r"Intrusion:\s*yes",
                r"Action:.*intrude",
                r"Action:.*trespass",
            ],
            IncidentType.THREATENING: [
                # 한글
                r"위협.*행동",
                r"공격적.*자세",
                r"위협",
                # 영어 (새 구조화된 형식)
                r"Threatening:\s*yes",
                r"Action:.*threaten",
                r"State:\s*suspicious",
            ],
            IncidentType.ABNORMAL_BEHAVIOR: [
                # 한글
                r"비정상.*행동",
                r"이상.*행동",
                r"수상",
                # 영어
                r"State:\s*suspicious",
                r"Action:.*unusual",
            ],
        }

        # 심각도 판단 키워드
        self.severity_keywords = {
            SeverityLevel.CRITICAL: [
                r"심각",
                r"매우",
                r"극심",
                r"중대",
                r"생명",
                r"사망",
                r"치명",
                r"즉시",
                r"긴급",
            ],
            SeverityLevel.HIGH: [
                r"높은",
                r"큰",
                r"상당한",
                r"심한",
                r"위험한",
                r"출혈",
                r"골절",
            ],
            SeverityLevel.MEDIUM: [
                r"중간",
                r"보통",
                r"일부",
                r"가벼운",
                r"경미한",
            ],
            SeverityLevel.LOW: [
                r"낮은",
                r"작은",
                r"미미한",
                r"미세한",
            ],
        }

    def detect_incidents(self, vision_analysis: str) -> List[Tuple[IncidentType, float]]:
        """
        Vision 분석 결과에서 사고 유형 감지 - 우선순위 기반

        Args:
            vision_analysis: Vision 모델의 분석 결과 텍스트

        Returns:
            List[Tuple[IncidentType, float]]: [(사고유형, 신뢰도), ...]
        """

        # 1순위: 사람 없음 체크
        for pattern in self.no_person_patterns:
            if re.search(pattern, vision_analysis, re.IGNORECASE):
                return [(IncidentType.NO_PERSON, 1.0)]

        # 2순위: 판단 불가 체크
        for pattern in self.unclear_patterns:
            if re.search(pattern, vision_analysis, re.IGNORECASE):
                return [(IncidentType.UNCLEAR, 0.5)]

        # 3순위: 정상 상황 체크
        normal_matches = sum(1 for p in self.normal_patterns
                            if re.search(p, vision_analysis, re.IGNORECASE))

        if normal_matches >= 1:  # 1개 이상 정상 키워드
            return [(IncidentType.NORMAL, 1.0)]

        # 4순위: 사고 패턴 체크
        detected = []
        for incident_type, patterns in self.incident_patterns.items():
            matches = sum(1 for p in patterns
                         if re.search(p, vision_analysis, re.IGNORECASE))

            if matches > 0:
                confidence = min(matches / len(patterns), 1.0)
                detected.append((incident_type, confidence))

        # 사고가 감지되면 신뢰도 순으로 정렬
        if detected:
            detected.sort(key=lambda x: x[1], reverse=True)
            return detected

        # 아무것도 감지 안 되면 정상으로 간주
        return [(IncidentType.NORMAL, 1.0)]

    def assess_severity(self, vision_analysis: str, incident_types: List[IncidentType]) -> SeverityLevel:
        """
        심각도 평가

        Args:
            vision_analysis: Vision 모델의 분석 결과 텍스트
            incident_types: 감지된 사고 유형 리스트

        Returns:
            SeverityLevel: 심각도 수준
        """
        # 키워드 기반 심각도 점수 계산
        severity_scores = {level: 0 for level in SeverityLevel}

        for level, keywords in self.severity_keywords.items():
            for keyword in keywords:
                if re.search(keyword, vision_analysis, re.IGNORECASE):
                    severity_scores[level] += 1

        # 사고 유형에 따른 기본 심각도
        type_severity_map = {
            IncidentType.VIOLENCE: SeverityLevel.CRITICAL,
            IncidentType.FIGHTING: SeverityLevel.HIGH,
            IncidentType.FALLING: SeverityLevel.HIGH,
            IncidentType.THREATENING: SeverityLevel.MEDIUM,
            IncidentType.INTRUSION: SeverityLevel.MEDIUM,
            IncidentType.ABNORMAL_BEHAVIOR: SeverityLevel.MEDIUM,
            IncidentType.NORMAL: SeverityLevel.INFO,
            IncidentType.NO_PERSON: SeverityLevel.INFO,
            IncidentType.UNCLEAR: SeverityLevel.INFO,
        }

        # 가장 높은 심각도 사고 유형 선택
        max_severity = SeverityLevel.INFO
        for incident_type in incident_types:
            type_severity = type_severity_map.get(incident_type, SeverityLevel.MEDIUM)
            if self._compare_severity(type_severity, max_severity) > 0:
                max_severity = type_severity

        # 키워드 점수로 심각도 조정
        if severity_scores[SeverityLevel.CRITICAL] > 0:
            return SeverityLevel.CRITICAL
        elif severity_scores[SeverityLevel.HIGH] > 1:
            # HIGH 키워드가 2개 이상이면 심각도 상향
            if max_severity == SeverityLevel.MEDIUM:
                return SeverityLevel.HIGH
            return max_severity

        return max_severity

    def _compare_severity(self, level1: SeverityLevel, level2: SeverityLevel) -> int:
        """
        심각도 비교

        Returns:
            int: level1 > level2 이면 1, 같으면 0, level1 < level2 이면 -1
        """
        order = [
            SeverityLevel.INFO,
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL,
        ]

        idx1 = order.index(level1)
        idx2 = order.index(level2)

        if idx1 > idx2:
            return 1
        elif idx1 < idx2:
            return -1
        else:
            return 0

    def analyze_incident(self, vision_analysis: str) -> Dict:
        """
        전체 사고 분석

        Args:
            vision_analysis: Vision 모델의 분석 결과 텍스트

        Returns:
            Dict: {
                "primary_incident": (IncidentType, confidence),
                "all_incidents": [(IncidentType, confidence), ...],
                "severity": SeverityLevel,
                "summary": str
            }
        """
        # 사고 감지
        detected_incidents = self.detect_incidents(vision_analysis)

        # 심각도 평가
        incident_types = [inc[0] for inc in detected_incidents]
        severity = self.assess_severity(vision_analysis, incident_types)

        # 주요 사고
        primary_incident = detected_incidents[0] if detected_incidents else (IncidentType.NORMAL, 1.0)

        # 요약 생성
        incident_type, confidence = primary_incident
        summary = f"{incident_type.value} (신뢰도: {confidence:.1%}), 심각도: {severity.value}"

        logger.debug(f"🔍 Incident Detection Result: {summary}")
        logger.debug(f"   All detected: {[(inc[0].value, f'{inc[1]:.1%}') for inc in detected_incidents]}")

        return {
            "primary_incident": primary_incident,
            "all_incidents": detected_incidents,
            "severity": severity,
            "summary": summary,
        }
