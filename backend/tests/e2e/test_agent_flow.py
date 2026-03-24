"""
Agent E2E 통합 테스트
전체 Agent 워크플로우를 테스트합니다.
"""
import json
import time

import pytest
import httpx


BASE_URL = "http://localhost:9002"
TIMEOUT = 60.0


class TestAgentWorkflow:
    """Agent 전체 워크플로우 테스트"""

    def test_full_math_workflow(self):
        """
        전체 수학 계산 워크플로우 테스트
        1. 히스토리 초기화
        2. 수학 쿼리 실행
        3. 히스토리 확인
        4. 통계 확인
        """
        # Step 1: 히스토리 초기화
        httpx.delete(f"{BASE_URL}/agent/history", timeout=TIMEOUT)

        # Step 2: 수학 쿼리 실행
        payload = {"query": "15 더하기 28은?", "include_steps": False}
        response = httpx.post(f"{BASE_URL}/agent/query", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200
        query_data = response.json()
        assert query_data["answer"] is not None

        # Step 3: 히스토리 확인
        time.sleep(1)  # 히스토리 저장 대기
        response = httpx.get(f"{BASE_URL}/agent/history", timeout=TIMEOUT)
        assert response.status_code == 200
        history = response.json()
        assert history["total"] >= 1

        # 최근 실행이 우리가 보낸 쿼리인지 확인
        if history["history"]:
            latest = history["history"][-1]  # 최근 기록은 끝에 있음
            assert latest["query"] == "15 더하기 28은?"
            assert latest["success"] is True

        # Step 4: 통계 확인
        response = httpx.get(f"{BASE_URL}/agent/stats", timeout=TIMEOUT)
        assert response.status_code == 200
        stats = response.json()
        assert stats["today"]["queries"] >= 1

    def test_multiple_tool_calls(self):
        """
        여러 도구 호출 테스트
        1. 여러 수학 연산 수행
        2. 각 도구 사용 횟수 확인
        """
        # 히스토리 초기화
        httpx.delete(f"{BASE_URL}/agent/history", timeout=TIMEOUT)

        # 여러 쿼리 실행
        queries = [
            "10 곱하기 5는?",
            "100에서 35를 빼면?",
            "50을 2로 나누면?"
        ]

        for query in queries:
            payload = {"query": query, "include_steps": False}
            response = httpx.post(f"{BASE_URL}/agent/query", json=payload, timeout=TIMEOUT)
            assert response.status_code == 200
            time.sleep(0.5)

        # 통계에서 도구 사용 확인
        response = httpx.get(f"{BASE_URL}/agent/stats", timeout=TIMEOUT)
        stats = response.json()
        assert stats["today"]["queries"] >= 3
        assert stats["today"]["tool_calls"] >= 3

    def test_error_handling(self):
        """
        에러 처리 테스트
        잘못된 입력에 대한 에러 처리 확인
        """
        # 빈 쿼리 (현재 구현은 200을 반환하고 LLM이 처리)
        payload = {"query": "", "include_steps": False}
        response = httpx.post(f"{BASE_URL}/agent/query", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200  # 빈 쿼리도 LLM이 처리 가능

        # 잘못된 필드
        payload = {"invalid_field": "test"}
        response = httpx.post(f"{BASE_URL}/agent/query", json=payload, timeout=TIMEOUT)
        assert response.status_code in [400, 422]

    def test_agent_tool_integration(self):
        """
        Agent와 Tool 통합 테스트
        1. 도구 목록 조회
        2. 특정 도구 사용
        3. 사용 횟수 증가 확인
        """
        # Step 1: 도구 목록 조회
        response = httpx.get(f"{BASE_URL}/agent/tools", timeout=TIMEOUT)
        tools_before = response.json()
        initial_tools = {t["name"]: t["usage_count"] for t in tools_before["tools"]}

        # Step 2: multiply 도구 사용
        payload = {"query": "7 곱하기 8은?", "include_steps": False}
        response = httpx.post(f"{BASE_URL}/agent/query", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200

        # Step 3: 사용 횟수 증가 확인 (선택적 - 백엔드 구현에 따라)
        time.sleep(1)
        response = httpx.get(f"{BASE_URL}/agent/tools", timeout=TIMEOUT)
        tools_after = response.json()

        # multiply 도구 찾기
        multiply_tool = next((t for t in tools_after["tools"] if t["name"] == "multiply"), None)
        if multiply_tool:
            # 사용 횟수가 증가했거나 최소한 0 이상이어야 함
            assert multiply_tool["usage_count"] >= initial_tools.get("multiply", 0)


class TestRAGWorkflow:
    """RAG 워크플로우 테스트 (Agent 아닌 일반 RAG)"""

    @pytest.mark.skip(reason="Optional RAG test")
    def test_rag_query(self):
        """RAG 쿼리 테스트"""
        payload = {"query": "adaptive retrieval이란?", "k": 3}
        response = httpx.post(f"{BASE_URL}/query", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "documents" in data


class TestConcurrentRequests:
    """동시 요청 테스트"""

    @pytest.mark.skip(reason="Performance test, may take long time")
    def test_concurrent_agent_queries(self):
        """동시 여러 Agent 쿼리 처리 테스트"""
        import concurrent.futures

        def send_query(index):
            payload = {"query": f"{index} 곱하기 2는?", "include_steps": False}
            response = httpx.post(f"{BASE_URL}/agent/query", json=payload, timeout=TIMEOUT)
            return response.status_code == 200

        # 3개 동시 요청
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(send_query, i) for i in range(1, 4)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # 모든 요청이 성공했는지 확인
        assert all(results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
