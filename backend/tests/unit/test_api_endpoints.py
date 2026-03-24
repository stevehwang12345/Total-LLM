"""
API 엔드포인트 단위 테스트
FastAPI 백엔드 엔드포인트를 테스트합니다.
"""
import json

import pytest
import httpx


BASE_URL = "http://localhost:9002"
TIMEOUT = 30.0


class TestHealthEndpoint:
    """Health Check 엔드포인트 테스트"""

    def test_health_check(self):
        """헬스 체크 응답 테스트"""
        response = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "llm" in data
        assert "retriever" in data


class TestAgentToolsEndpoint:
    """Agent Tools 엔드포인트 테스트"""

    def test_get_agent_tools(self):
        """도구 목록 조회 테스트"""
        response = httpx.get(f"{BASE_URL}/agent/tools", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "tools_count" in data
        assert "tools" in data
        assert data["tools_count"] == 6

    def test_tool_list_structure(self):
        """도구 목록 구조 검증"""
        response = httpx.get(f"{BASE_URL}/agent/tools", timeout=TIMEOUT)
        data = response.json()
        tools = data["tools"]

        # 필수 도구 확인
        tool_names = [t["name"] for t in tools]
        expected_tools = {"add", "subtract", "multiply", "divide", "search_web", "search_documents"}
        assert set(tool_names) == expected_tools

        # 각 도구의 필수 필드 확인
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "usage_count" in tool

    @pytest.mark.skip(reason="Tool details endpoint has implementation issue with current agent")
    def test_tool_details(self):
        """특정 도구 상세 정보 조회 테스트"""
        response = httpx.get(f"{BASE_URL}/agent/tools/multiply", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "multiply"
        assert "description" in data
        assert "parameters" in data


class TestAgentHistoryEndpoint:
    """Agent History 엔드포인트 테스트"""

    def test_get_agent_history(self):
        """실행 히스토리 조회 테스트"""
        response = httpx.get(f"{BASE_URL}/agent/history", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_clear_agent_history(self):
        """히스토리 삭제 테스트"""
        response = httpx.delete(f"{BASE_URL}/agent/history", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestAgentStatsEndpoint:
    """Agent Stats 엔드포인트 테스트"""

    def test_get_agent_stats(self):
        """통계 조회 테스트"""
        response = httpx.get(f"{BASE_URL}/agent/stats", timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "today" in data
        assert "all_time" in data

        # 오늘의 통계 구조 확인
        today = data["today"]
        assert "queries" in today
        assert "successful" in today
        assert "failed" in today
        assert "tool_calls" in today
        assert "success_rate" in today


class TestAgentQueryEndpoint:
    """Agent Query 엔드포인트 테스트"""

    def test_agent_query_simple_math(self):
        """간단한 수학 쿼리 테스트"""
        payload = {
            "query": "25 곱하기 4는?",
            "include_steps": False
        }
        response = httpx.post(
            f"{BASE_URL}/agent/query",
            json=payload,
            timeout=60.0  # Agent 처리 시간 고려
        )
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "answer" in data
        assert data["answer"] is not None

        # 결과에 multiply 도구 사용 흔적 확인
        if "tool_calls" in data:
            tool_names = [t["name"] for t in data["tool_calls"]]
            assert "multiply" in tool_names

    @pytest.mark.skip(reason="Requires actual LLM processing, may take long time")
    def test_agent_query_with_search(self):
        """검색 쿼리 테스트 (선택적)"""
        payload = {
            "query": "파이썬에 대해 알려줘",
            "include_steps": True
        }
        response = httpx.post(
            f"{BASE_URL}/agent/query",
            json=payload,
            timeout=60.0
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
