"""
Image API 테스트

이미지 분석 REST API 엔드포인트의 모든 기능을 테스트합니다.
"""

import pytest
from fastapi.testclient import TestClient
import base64
import sys
from pathlib import Path

# 백엔드 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from total_llm.api.image_api import router, _analysis_store, get_detector
from fastapi import FastAPI

# 테스트용 FastAPI 앱 생성
app = FastAPI()
app.include_router(router)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_store():
    """각 테스트 전후로 저장소 초기화"""
    _analysis_store.clear()
    yield
    _analysis_store.clear()


@pytest.fixture
def sample_image_base64():
    """테스트용 샘플 이미지 (Base64)"""
    # 간단한 테스트 이미지 (1x1 픽셀 PNG)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    return base64.b64encode(png_data).decode('utf-8')


class TestImageAnalyzeEndpoint:
    """POST /image/analyze 테스트"""

    def test_analyze_image_success(self, sample_image_base64):
        """이미지 분석 성공"""
        response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64,
            "location": "로비",
            "mode": "standard"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "analysis_id" in data
        assert data["location"] == "로비"
        assert "incident_type" in data
        assert "incident_type_ko" in data
        assert "severity" in data
        assert "severity_ko" in data
        assert "confidence" in data
        assert "recommended_actions" in data

    def test_analyze_image_quick_mode(self, sample_image_base64):
        """빠른 분석 모드"""
        response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64,
            "mode": "quick"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_analyze_image_detailed_mode(self, sample_image_base64):
        """상세 분석 모드"""
        response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64,
            "mode": "detailed"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 상세 모드에서는 raw_analysis 포함
        assert "raw_analysis" in data

    def test_analyze_image_default_location(self, sample_image_base64):
        """기본 위치 사용"""
        response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64
        })

        assert response.status_code == 200
        data = response.json()
        assert data["location"] == "미지정"

    def test_analyze_image_stores_result(self, sample_image_base64):
        """분석 결과 저장소에 저장"""
        response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64
        })

        assert response.status_code == 200
        data = response.json()
        analysis_id = data["analysis_id"]

        # 저장소에 저장되었는지 확인
        assert analysis_id in _analysis_store


class TestImageAnalyzeUploadEndpoint:
    """POST /image/analyze/upload 테스트"""

    def test_upload_image_success(self):
        """이미지 업로드 분석 성공"""
        # 테스트용 PNG 이미지
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'

        response = client.post(
            "/image/analyze/upload",
            files={"file": ("test.png", png_data, "image/png")},
            data={"location": "주차장", "mode": "standard"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["location"] == "주차장"

    def test_upload_unsupported_file_type(self):
        """지원하지 않는 파일 형식"""
        response = client.post(
            "/image/analyze/upload",
            files={"file": ("test.txt", b"text content", "text/plain")},
            data={"location": "테스트"}
        )

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


class TestBatchAnalyzeEndpoint:
    """POST /image/batch 테스트"""

    def test_batch_analyze_success(self, sample_image_base64):
        """배치 분석 성공"""
        response = client.post("/image/batch", json={
            "images": [
                {"image_base64": sample_image_base64, "location": "카메라1"},
                {"image_base64": sample_image_base64, "location": "카메라2"},
                {"image_base64": sample_image_base64, "location": "카메라3"}
            ],
            "mode": "standard"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["total"] == 3
        assert data["completed"] == 3
        assert data["failed"] == 0
        assert len(data["results"]) == 3

    def test_batch_analyze_max_limit(self, sample_image_base64):
        """배치 최대 개수 초과"""
        images = [
            {"image_base64": sample_image_base64, "location": f"카메라{i}"}
            for i in range(11)  # 11개 (최대 10개 초과)
        ]

        response = client.post("/image/batch", json={
            "images": images
        })

        assert response.status_code == 400
        assert "Maximum 10 images" in response.json()["detail"]

    def test_batch_analyze_empty(self):
        """빈 배치"""
        response = client.post("/image/batch", json={
            "images": []
        })

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


class TestGetAnalysisEndpoint:
    """GET /image/{analysis_id} 테스트"""

    def test_get_analysis_success(self, sample_image_base64):
        """분석 결과 조회 성공"""
        # 먼저 분석 실행
        analyze_response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64
        })
        analysis_id = analyze_response.json()["analysis_id"]

        # 결과 조회
        response = client.get(f"/image/{analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["analysis"]["analysis_id"] == analysis_id

    def test_get_analysis_not_found(self):
        """존재하지 않는 분석 결과"""
        response = client.get("/image/nonexistent_id")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"]


class TestListAnalysisEndpoint:
    """GET /image/ 테스트"""

    def test_list_analysis_empty(self):
        """빈 목록 조회"""
        response = client.get("/image/")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 0
        assert data["results"] == []

    def test_list_analysis_with_results(self, sample_image_base64):
        """결과 목록 조회"""
        # 여러 분석 실행
        for i in range(3):
            client.post("/image/analyze", json={
                "image_base64": sample_image_base64 + str(i),  # 다른 결과 유도
                "location": f"위치_{i}"
            })

        response = client.get("/image/")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 3

    def test_list_analysis_with_limit(self, sample_image_base64):
        """결과 개수 제한"""
        # 5개 분석 실행
        for i in range(5):
            client.post("/image/analyze", json={
                "image_base64": sample_image_base64 + str(i),
                "location": f"위치_{i}"
            })

        response = client.get("/image/?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3


class TestReportEndpoint:
    """POST /image/report 테스트"""

    def test_generate_report_markdown(self, sample_image_base64):
        """Markdown 보고서 생성"""
        # 분석 실행
        analyze_response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64,
            "location": "로비"
        })
        analysis_id = analyze_response.json()["analysis_id"]

        # 보고서 생성
        response = client.post("/image/report", json={
            "analysis_ids": [analysis_id],
            "title": "테스트 보고서",
            "output_format": "markdown"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["title"] == "테스트 보고서"
        assert data["format"] == "markdown"
        assert "# 테스트 보고서" in data["content"]
        assert "로비" in data["content"]

    def test_generate_report_json(self, sample_image_base64):
        """JSON 보고서 생성"""
        # 분석 실행
        analyze_response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64
        })
        analysis_id = analyze_response.json()["analysis_id"]

        # 보고서 생성
        response = client.post("/image/report", json={
            "analysis_ids": [analysis_id],
            "output_format": "json"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"

    def test_generate_report_multiple_analyses(self, sample_image_base64):
        """여러 분석 결과로 보고서 생성"""
        # 여러 분석 실행
        analysis_ids = []
        for i in range(3):
            analyze_response = client.post("/image/analyze", json={
                "image_base64": sample_image_base64 + str(i),
                "location": f"카메라_{i}"
            })
            analysis_ids.append(analyze_response.json()["analysis_id"])

        # 보고서 생성
        response = client.post("/image/report", json={
            "analysis_ids": analysis_ids,
            "title": "종합 보고서"
        })

        assert response.status_code == 200
        data = response.json()
        assert "3건" in data["content"]

    def test_generate_report_no_valid_analysis(self):
        """유효한 분석 결과 없음"""
        response = client.post("/image/report", json={
            "analysis_ids": ["invalid_id_1", "invalid_id_2"]
        })

        assert response.status_code == 404
        assert "No valid analysis" in response.json()["detail"]


class TestHealthCheckEndpoint:
    """GET /image/health 테스트"""

    def test_health_check(self):
        """헬스 체크"""
        response = client.get("/image/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ok"
        assert data["service"] == "Image Analysis API"
        assert "incident_types" in data
        assert "severity_levels" in data
        assert "stored_analyses" in data
        assert "detector_patterns" in data


class TestIncidentDetectorIntegration:
    """IncidentDetector 통합 테스트"""

    def test_detector_initialized(self):
        """Detector 초기화 확인"""
        detector = get_detector()
        assert detector is not None
        assert len(detector.incident_patterns) > 0

    def test_different_scenarios(self, sample_image_base64):
        """다양한 시나리오 테스트 (시뮬레이션)"""
        # 여러 다른 이미지로 다양한 시나리오 테스트
        scenarios_found = set()

        for i in range(10):
            response = client.post("/image/analyze", json={
                "image_base64": sample_image_base64 + f"_scenario_{i}",
                "location": f"테스트_{i}"
            })

            assert response.status_code == 200
            data = response.json()
            scenarios_found.add(data["incident_type"])

        # 최소 1개 이상의 다른 시나리오가 나와야 함
        assert len(scenarios_found) >= 1


class TestRecommendedActions:
    """권장 조치 테스트"""

    def test_actions_present(self, sample_image_base64):
        """권장 조치가 포함되어 있는지"""
        response = client.post("/image/analyze", json={
            "image_base64": sample_image_base64
        })

        assert response.status_code == 200
        data = response.json()

        assert "recommended_actions" in data
        assert isinstance(data["recommended_actions"], list)
        # 최소 1개 이상의 권장 조치
        assert len(data["recommended_actions"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
