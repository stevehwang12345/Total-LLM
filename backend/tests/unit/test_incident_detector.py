"""
Incident Detector 단위 테스트

사고 감지 및 심각도 평가 로직을 테스트합니다.
"""

import pytest
import sys
sys.path.insert(0, '/home/sphwang/dev/Total-LLM/backend')

from services.vision.detection.incident_detector import (
    IncidentDetector,
    IncidentType,
    SeverityLevel
)


class TestIncidentTypeEnum:
    """IncidentType Enum 테스트"""

    def test_incident_types(self):
        """사고 유형 값 확인"""
        assert IncidentType.VIOLENCE.value == "폭력"
        assert IncidentType.FIGHTING.value == "싸움"
        assert IncidentType.FALLING.value == "넘어짐/낙상"
        assert IncidentType.INTRUSION.value == "침입"
        assert IncidentType.THREATENING.value == "위협행위"
        assert IncidentType.ABNORMAL_BEHAVIOR.value == "비정상행동"
        assert IncidentType.NORMAL.value == "정상"
        assert IncidentType.NO_PERSON.value == "분석불가-사람없음"
        assert IncidentType.UNCLEAR.value == "판단불가-불분명"


class TestSeverityLevelEnum:
    """SeverityLevel Enum 테스트"""

    def test_severity_levels(self):
        """심각도 수준 값 확인"""
        assert SeverityLevel.CRITICAL.value == "매우높음"
        assert SeverityLevel.HIGH.value == "높음"
        assert SeverityLevel.MEDIUM.value == "중간"
        assert SeverityLevel.LOW.value == "낮음"
        assert SeverityLevel.INFO.value == "정보"


class TestIncidentDetectorInit:
    """Incident Detector 초기화 테스트"""

    def test_init(self):
        """초기화 테스트"""
        detector = IncidentDetector()
        assert detector is not None
        assert len(detector.no_person_patterns) > 0
        assert len(detector.normal_patterns) > 0
        assert len(detector.incident_patterns) > 0
        assert len(detector.severity_keywords) > 0


class TestIncidentDetectorNoPerson:
    """사람 없음 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_no_person_korean(self, detector):
        """한글 사람 없음 패턴 감지"""
        analysis = "화면에 사람이 없습니다. 빈 복도입니다."
        result = detector.detect_incidents(analysis)

        assert len(result) == 1
        assert result[0][0] == IncidentType.NO_PERSON
        assert result[0][1] == 1.0

    def test_detect_no_person_english(self, detector):
        """영어 사람 없음 패턴 감지"""
        analysis = "Count: none. Empty hallway."
        result = detector.detect_incidents(analysis)

        assert len(result) == 1
        assert result[0][0] == IncidentType.NO_PERSON

    def test_detect_no_person_count_zero(self, detector):
        """Count: 0 패턴 감지"""
        analysis = "PEOPLE:\n- Count: 0\nNo persons detected in frame."
        result = detector.detect_incidents(analysis)

        assert result[0][0] == IncidentType.NO_PERSON


class TestIncidentDetectorUnclear:
    """판단 불가 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_unclear_korean(self, detector):
        """한글 판단 불가 패턴 감지"""
        analysis = "영상이 불분명하여 명확한 판단이 불가합니다."
        result = detector.detect_incidents(analysis)

        assert result[0][0] == IncidentType.UNCLEAR
        assert result[0][1] == 0.5

    def test_detect_unclear_english(self, detector):
        """영어 판단 불가 패턴 감지"""
        analysis = "Situation: unclear due to poor lighting."
        result = detector.detect_incidents(analysis)

        assert result[0][0] == IncidentType.UNCLEAR


class TestIncidentDetectorNormal:
    """정상 상황 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_normal_korean(self, detector):
        """한글 정상 상황 감지"""
        analysis = "정상 상황입니다. 특이사항 없음. 일상적인 보행 활동."
        result = detector.detect_incidents(analysis)

        assert result[0][0] == IncidentType.NORMAL
        assert result[0][1] == 1.0

    def test_detect_normal_english(self, detector):
        """영어 정상 상황 감지"""
        analysis = "Situation: normal. State: normal. Regular activity observed."
        result = detector.detect_incidents(analysis)

        assert result[0][0] == IncidentType.NORMAL


class TestIncidentDetectorViolence:
    """폭력 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_violence_korean(self, detector):
        """한글 폭력 감지"""
        analysis = "폭력 행위가 관찰됩니다. 한 사람이 다른 사람을 때리고 있습니다."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.VIOLENCE in incidents

    def test_detect_violence_english(self, detector):
        """영어 폭력 감지"""
        analysis = "Violence: yes. Action: punch. State: dangerous."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.VIOLENCE in incidents


class TestIncidentDetectorFighting:
    """싸움 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_fighting_korean(self, detector):
        """한글 싸움 감지"""
        analysis = "두 사람 사이에 몸싸움이 진행 중입니다. 격투 행위 관찰됨."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.FIGHTING in incidents

    def test_detect_fighting_english(self, detector):
        """영어 싸움 감지"""
        analysis = "Fighting: yes. Action: fight between two persons."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.FIGHTING in incidents


class TestIncidentDetectorFalling:
    """낙상 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_falling_korean(self, detector):
        """한글 낙상 감지"""
        analysis = "한 사람이 넘어짐 관찰됩니다. 바닥에 누워있는 상태입니다."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.FALLING in incidents

    def test_detect_falling_english(self, detector):
        """영어 낙상 감지"""
        analysis = "Falling: yes. Posture: lying on ground. State: injured."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.FALLING in incidents


class TestIncidentDetectorIntrusion:
    """침입 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_intrusion_korean(self, detector):
        """한글 침입 감지"""
        analysis = "허가 없이 제한구역에 침입하는 인물이 발견되었습니다."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.INTRUSION in incidents

    def test_detect_intrusion_english(self, detector):
        """영어 침입 감지"""
        analysis = "Intrusion: yes. Action: trespass into restricted area."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.INTRUSION in incidents


class TestIncidentDetectorThreatening:
    """위협 행위 감지 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_detect_threatening_korean(self, detector):
        """한글 위협 행위 감지"""
        analysis = "한 사람이 위협적인 행동을 보이며 공격적인 자세를 취하고 있습니다."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.THREATENING in incidents

    def test_detect_threatening_english(self, detector):
        """영어 위협 행위 감지"""
        analysis = "Threatening: yes. Action: threaten another person."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.THREATENING in incidents


class TestIncidentDetectorSeverity:
    """심각도 평가 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_severity_critical_keywords(self, detector):
        """심각 키워드 기반 심각도"""
        analysis = "심각한 상황입니다. 생명에 위험이 있습니다. 즉시 조치 필요."
        incidents = [IncidentType.VIOLENCE]

        severity = detector.assess_severity(analysis, incidents)
        assert severity == SeverityLevel.CRITICAL

    def test_severity_high_by_type(self, detector):
        """사고 유형 기반 심각도"""
        analysis = "싸움이 발생했습니다."
        incidents = [IncidentType.FIGHTING]

        severity = detector.assess_severity(analysis, incidents)
        assert severity == SeverityLevel.HIGH

    def test_severity_medium_by_type(self, detector):
        """중간 심각도"""
        analysis = "수상한 행동이 관찰됩니다."
        incidents = [IncidentType.ABNORMAL_BEHAVIOR]

        severity = detector.assess_severity(analysis, incidents)
        assert severity == SeverityLevel.MEDIUM

    def test_severity_info_normal(self, detector):
        """정상 상황 심각도"""
        analysis = "정상적인 상황입니다."
        incidents = [IncidentType.NORMAL]

        severity = detector.assess_severity(analysis, incidents)
        assert severity == SeverityLevel.INFO


class TestIncidentDetectorAnalyzeIncident:
    """전체 사고 분석 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_analyze_incident_violence(self, detector):
        """폭력 사고 전체 분석"""
        analysis = "Violence: yes. 심각한 폭행이 관찰됩니다. Action: punch."
        result = detector.analyze_incident(analysis)

        assert "primary_incident" in result
        assert "all_incidents" in result
        assert "severity" in result
        assert "summary" in result

        primary_type, confidence = result["primary_incident"]
        assert primary_type == IncidentType.VIOLENCE
        assert confidence > 0

    def test_analyze_incident_normal(self, detector):
        """정상 상황 전체 분석"""
        analysis = "Situation: normal. 특이사항 없습니다."
        result = detector.analyze_incident(analysis)

        primary_type, _ = result["primary_incident"]
        assert primary_type == IncidentType.NORMAL
        assert result["severity"] == SeverityLevel.INFO

    def test_analyze_incident_no_person(self, detector):
        """사람 없음 전체 분석"""
        analysis = "Count: none. 화면에 사람이 없습니다."
        result = detector.analyze_incident(analysis)

        primary_type, _ = result["primary_incident"]
        assert primary_type == IncidentType.NO_PERSON
        assert result["severity"] == SeverityLevel.INFO

    def test_analyze_incident_multiple(self, detector):
        """다중 사고 감지"""
        analysis = """
        폭력 행위가 관찰됩니다. 두 사람이 싸움 중입니다.
        Violence: yes. Fighting: yes.
        Action: punch, fight.
        """
        result = detector.analyze_incident(analysis)

        # 다중 사고 감지 확인
        assert len(result["all_incidents"]) >= 1

        # 심각도가 높아야 함
        assert result["severity"] in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]


class TestIncidentDetectorSeverityComparison:
    """심각도 비교 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_compare_severity_greater(self, detector):
        """심각도 비교: 더 높음"""
        result = detector._compare_severity(SeverityLevel.CRITICAL, SeverityLevel.HIGH)
        assert result == 1

    def test_compare_severity_less(self, detector):
        """심각도 비교: 더 낮음"""
        result = detector._compare_severity(SeverityLevel.LOW, SeverityLevel.HIGH)
        assert result == -1

    def test_compare_severity_equal(self, detector):
        """심각도 비교: 같음"""
        result = detector._compare_severity(SeverityLevel.MEDIUM, SeverityLevel.MEDIUM)
        assert result == 0


class TestIncidentDetectorEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def detector(self):
        return IncidentDetector()

    def test_empty_analysis(self, detector):
        """빈 분석 결과"""
        result = detector.detect_incidents("")

        # 아무것도 감지 안 되면 정상으로 간주
        assert result[0][0] == IncidentType.NORMAL

    def test_mixed_language(self, detector):
        """혼합 언어 분석"""
        analysis = "Violence: yes. 폭력 행위가 관찰됩니다. State: dangerous."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.VIOLENCE in incidents

    def test_case_insensitive(self, detector):
        """대소문자 구분 없음"""
        analysis = "VIOLENCE: YES. ACTION: PUNCH."
        result = detector.detect_incidents(analysis)

        incidents = [inc[0] for inc in result]
        assert IncidentType.VIOLENCE in incidents


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
