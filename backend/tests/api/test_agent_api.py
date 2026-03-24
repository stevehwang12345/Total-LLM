"""
Agent API 테스트

MCP Agent 및 Multi-Agent API 엔드포인트 테스트입니다.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_mcp_agent():
    """MCP Agent 목"""
    agent = MagicMock()
    agent.tools = [
        MagicMock(name="add", description="두 수를 더합니다"),
        MagicMock(name="search", description="웹 검색을 수행합니다"),
    ]
    agent.tools[0].name = "add"
    agent.tools[0].description = "두 수를 더합니다"
    agent.tools[0].args_schema = None
    agent.tools[1].name = "search"
    agent.tools[1].description = "웹 검색을 수행합니다"
    agent.tools[1].args_schema = None

    agent.tool_dict = {"add": agent.tools[0], "search": agent.tools[1]}

    async def mock_query(query, thread_id="default"):
        return {
            "answer": f"질문 '{query}'에 대한 답변입니다.",
            "tool_calls": [{"name": "add", "args": {"a": 1, "b": 2}, "id": "tc1"}],
            "iterations": 1
        }

    agent.query = AsyncMock(side_effect=mock_query)
    return agent


@pytest.fixture
def mock_multi_agent():
    """Multi-Agent System 목"""
    agent = MagicMock()
    agent.tools = []

    async def mock_query(query, thread_id="default"):
        return {
            "answer": f"'{query}'에 대한 종합적인 답변입니다.",
            "agents_used": ["Planner", "Researcher", "Analyzer", "Executor"],
            "steps": [
                {"agent": "Planner", "message": "작업 분석 완료"},
                {"agent": "Researcher", "message": "정보 수집 완료"},
                {"agent": "Executor", "message": "최종 답변 생성"}
            ],
            "tool_calls": []
        }

    agent.query = AsyncMock(side_effect=mock_query)
    return agent


@pytest.fixture
def app_with_mocks(mock_mcp_agent, mock_multi_agent):
    """Mock Agent가 주입된 FastAPI 앱"""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import Optional, List, Dict
    from datetime import datetime
    from collections import defaultdict

    app = FastAPI()

    # 글로벌 상태
    agent_execution_history = []
    tool_usage_stats = defaultdict(int)

    # Pydantic 모델
    class AgentQueryRequest(BaseModel):
        query: str
        include_steps: bool = False

    class AgentQueryResponse(BaseModel):
        query: str
        answer: str
        tool_calls: List[Dict]
        steps: Optional[List[Dict]] = None
        metadata: Dict

    class MultiAgentQueryRequest(BaseModel):
        query: str
        thread_id: Optional[str] = "default"
        include_steps: bool = True

    class MultiAgentQueryResponse(BaseModel):
        query: str
        answer: str
        agents_used: List[str]
        steps: Optional[List[Dict]]
        tool_calls: List[Dict]
        metadata: Dict

    # MCP Agent 엔드포인트
    @app.post("/agent/query", response_model=AgentQueryResponse)
    async def agent_query(request: AgentQueryRequest):
        try:
            start_time = datetime.now()
            result = await mock_mcp_agent.query(request.query)
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            execution_record = {
                'id': f"exec_{len(agent_execution_history)}",
                'query': request.query,
                'answer': result['answer'],
                'tool_calls': result['tool_calls'],
                'execution_time': execution_time,
                'timestamp': end_time.isoformat(),
                'success': True,
                'iterations': result.get('iterations', 0)
            }
            agent_execution_history.append(execution_record)

            for tool_call in result['tool_calls']:
                tool_usage_stats[tool_call['name']] += 1

            return AgentQueryResponse(
                query=request.query,
                answer=result['answer'],
                tool_calls=result['tool_calls'],
                steps=None,
                metadata={
                    'iterations': result.get('iterations', 0),
                    'tools_used': len(result['tool_calls']),
                    'execution_time': execution_time
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent/tools")
    async def get_agent_tools():
        tools_info = []
        for tool in mock_mcp_agent.tools:
            tools_info.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": {},
                "usage_count": tool_usage_stats.get(tool.name, 0)
            })
        return {
            "tools_count": len(mock_mcp_agent.tools),
            "tools": tools_info
        }

    @app.get("/agent/tools/{tool_name}")
    async def get_tool_details(tool_name: str):
        tool = mock_mcp_agent.tool_dict.get(tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": {},
            "usage_count": tool_usage_stats.get(tool_name, 0),
            "last_used": None
        }

    @app.get("/agent/history")
    async def get_agent_history(limit: int = 50):
        history = list(reversed(agent_execution_history[-limit:]))
        return {
            "total": len(agent_execution_history),
            "history": history
        }

    @app.delete("/agent/history")
    async def clear_agent_history():
        agent_execution_history.clear()
        tool_usage_stats.clear()
        return {"status": "ok", "message": "History cleared"}

    @app.get("/agent/stats")
    async def get_agent_stats():
        total = len(agent_execution_history)
        successful = len([r for r in agent_execution_history if r.get('success', False)])
        failed = total - successful
        total_tool_calls = sum(len(r.get('tool_calls', [])) for r in agent_execution_history)
        success_rate = (successful / total * 100) if total > 0 else 0

        return {
            "today": {
                "queries": total,
                "successful": successful,
                "failed": failed,
                "tool_calls": total_tool_calls,
                "success_rate": round(success_rate, 1)
            },
            "all_time": {
                "queries": len(agent_execution_history),
                "tool_usage": dict(tool_usage_stats)
            }
        }

    # Multi-Agent 엔드포인트
    @app.post("/agent/multi/query", response_model=MultiAgentQueryResponse)
    async def multi_agent_query(request: MultiAgentQueryRequest):
        try:
            start_time = datetime.now()
            result = await mock_multi_agent.query(request.query, thread_id=request.thread_id)
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            execution_record = {
                'id': f"multi_{len(agent_execution_history)}",
                'query': request.query,
                'answer': result['answer'],
                'agents_used': result['agents_used'],
                'tool_calls': result['tool_calls'],
                'execution_time': execution_time,
                'timestamp': end_time.isoformat(),
                'success': True,
                'thread_id': request.thread_id
            }
            agent_execution_history.append(execution_record)

            return MultiAgentQueryResponse(
                query=request.query,
                answer=result['answer'],
                agents_used=result['agents_used'],
                steps=result['steps'] if request.include_steps else None,
                tool_calls=result['tool_calls'],
                metadata={
                    'agents_count': len(result['agents_used']),
                    'tools_used': len(result['tool_calls']),
                    'execution_time': execution_time,
                    'thread_id': request.thread_id
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/agent/multi/info")
    async def multi_agent_info():
        return {
            "status": "active",
            "system": "Multi-Agent Collaborative System",
            "agents": [
                {"name": "Planner", "role": "작업 분석 및 라우팅"},
                {"name": "Researcher", "role": "정보 수집 및 검색"},
                {"name": "Analyzer", "role": "데이터 분석 및 해석"},
                {"name": "Executor", "role": "최종 답변 생성"}
            ],
            "tools_count": 0
        }

    return app


@pytest.fixture
def client(app_with_mocks):
    """테스트 클라이언트"""
    return TestClient(app_with_mocks)


class TestAgentQueryEndpoint:
    """POST /agent/query 테스트"""

    def test_agent_query_success(self, client):
        """에이전트 쿼리 성공"""
        response = client.post("/agent/query", json={
            "query": "1 더하기 2는?"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["query"] == "1 더하기 2는?"
        assert "answer" in data
        assert "tool_calls" in data
        assert "metadata" in data

    def test_agent_query_with_steps(self, client):
        """실행 단계 포함 쿼리"""
        response = client.post("/agent/query", json={
            "query": "테스트 질문",
            "include_steps": True
        })

        assert response.status_code == 200
        data = response.json()
        assert "steps" in data

    def test_agent_query_metadata(self, client):
        """메타데이터 확인"""
        response = client.post("/agent/query", json={
            "query": "테스트"
        })

        assert response.status_code == 200
        data = response.json()

        assert "iterations" in data["metadata"]
        assert "tools_used" in data["metadata"]
        assert "execution_time" in data["metadata"]


class TestAgentToolsEndpoint:
    """GET /agent/tools 테스트"""

    def test_get_tools_list(self, client):
        """도구 목록 조회"""
        response = client.get("/agent/tools")

        assert response.status_code == 200
        data = response.json()

        assert "tools_count" in data
        assert "tools" in data
        assert data["tools_count"] == 2

    def test_get_tool_details(self, client):
        """특정 도구 상세 조회"""
        response = client.get("/agent/tools/add")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "add"
        assert "description" in data
        assert "usage_count" in data

    def test_get_tool_not_found(self, client):
        """존재하지 않는 도구"""
        response = client.get("/agent/tools/nonexistent")

        assert response.status_code == 404


class TestAgentHistoryEndpoint:
    """GET/DELETE /agent/history 테스트"""

    def test_get_history_empty(self, client):
        """빈 히스토리 조회"""
        response = client.get("/agent/history")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["history"] == []

    def test_get_history_with_entries(self, client):
        """히스토리 조회"""
        # 쿼리 실행
        client.post("/agent/query", json={"query": "테스트 1"})
        client.post("/agent/query", json={"query": "테스트 2"})

        response = client.get("/agent/history")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert len(data["history"]) == 2

    def test_get_history_with_limit(self, client):
        """히스토리 제한"""
        for i in range(5):
            client.post("/agent/query", json={"query": f"테스트 {i}"})

        response = client.get("/agent/history?limit=3")

        assert response.status_code == 200
        data = response.json()

        assert len(data["history"]) == 3

    def test_clear_history(self, client):
        """히스토리 삭제"""
        client.post("/agent/query", json={"query": "테스트"})

        response = client.delete("/agent/history")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # 삭제 확인
        history_response = client.get("/agent/history")
        assert history_response.json()["total"] == 0


class TestAgentStatsEndpoint:
    """GET /agent/stats 테스트"""

    def test_get_stats_empty(self, client):
        """빈 통계"""
        response = client.get("/agent/stats")

        assert response.status_code == 200
        data = response.json()

        assert "today" in data
        assert "all_time" in data
        assert data["today"]["queries"] == 0

    def test_get_stats_with_queries(self, client):
        """쿼리 후 통계"""
        client.post("/agent/query", json={"query": "테스트 1"})
        client.post("/agent/query", json={"query": "테스트 2"})

        response = client.get("/agent/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["today"]["queries"] == 2
        assert data["today"]["successful"] == 2
        assert data["today"]["success_rate"] == 100.0


class TestMultiAgentQueryEndpoint:
    """POST /agent/multi/query 테스트"""

    def test_multi_agent_query_success(self, client):
        """Multi-Agent 쿼리 성공"""
        response = client.post("/agent/multi/query", json={
            "query": "Python에 대해 검색해줘"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["query"] == "Python에 대해 검색해줘"
        assert "answer" in data
        assert "agents_used" in data
        assert len(data["agents_used"]) == 4

    def test_multi_agent_query_with_thread_id(self, client):
        """스레드 ID 지정"""
        response = client.post("/agent/multi/query", json={
            "query": "테스트",
            "thread_id": "custom_thread"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["metadata"]["thread_id"] == "custom_thread"

    def test_multi_agent_query_with_steps(self, client):
        """실행 단계 포함"""
        response = client.post("/agent/multi/query", json={
            "query": "분석해줘",
            "include_steps": True
        })

        assert response.status_code == 200
        data = response.json()

        assert data["steps"] is not None
        assert len(data["steps"]) >= 1

    def test_multi_agent_query_without_steps(self, client):
        """실행 단계 제외"""
        response = client.post("/agent/multi/query", json={
            "query": "테스트",
            "include_steps": False
        })

        assert response.status_code == 200
        data = response.json()

        assert data["steps"] is None


class TestMultiAgentInfoEndpoint:
    """GET /agent/multi/info 테스트"""

    def test_get_multi_agent_info(self, client):
        """Multi-Agent 정보 조회"""
        response = client.get("/agent/multi/info")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "active"
        assert data["system"] == "Multi-Agent Collaborative System"
        assert "agents" in data
        assert len(data["agents"]) == 4

        # 각 에이전트 확인
        agent_names = [a["name"] for a in data["agents"]]
        assert "Planner" in agent_names
        assert "Researcher" in agent_names
        assert "Analyzer" in agent_names
        assert "Executor" in agent_names


class TestAgentQueryToolTracking:
    """도구 사용 추적 테스트"""

    def test_tool_usage_tracked(self, client):
        """도구 사용 추적"""
        # 쿼리 실행
        client.post("/agent/query", json={"query": "1 + 2"})

        # 통계 확인
        stats_response = client.get("/agent/stats")
        data = stats_response.json()

        # 도구 사용 통계에 add가 있어야 함
        assert "add" in data["all_time"]["tool_usage"]
        assert data["all_time"]["tool_usage"]["add"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
