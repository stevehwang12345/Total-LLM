"""
Multi-Agent System 단위 테스트

Multi-Agent 협업 시스템의 기능을 테스트합니다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.multi_agent import MultiAgentSystem, AgentState


class TestMultiAgentSystemInit:
    """Multi-Agent System 초기화 테스트"""

    def test_init_default_config(self, tmp_path):
        """기본 설정으로 초기화"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        system = MultiAgentSystem(config_path=str(config_file))
        assert system is not None
        assert system.workflow is None
        assert system.llm is None
        assert system.tools == []

    def test_init_with_custom_config(self, tmp_path):
        """커스텀 설정 파일로 초기화"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        system = MultiAgentSystem(config_path=str(config_file))
        assert system.llm_config["model_name"] == "test-model"


class TestMultiAgentSystemInitialize:
    """시스템 초기화 테스트"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """테스트용 설정 파일"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.mark.asyncio
    async def test_initialize_creates_workflow(self, mock_config):
        """초기화 시 워크플로우 생성"""
        system = MultiAgentSystem(config_path=mock_config)

        with patch('agents.multi_agent.get_mcp_tools', new_callable=AsyncMock) as mock_get_tools:
            mock_get_tools.return_value = []

            with patch('agents.multi_agent.ChatOpenAI'):
                await system.initialize()

                assert system.workflow is not None
                assert system.llm is not None

    @pytest.mark.asyncio
    async def test_initialize_with_additional_tools(self, mock_config):
        """추가 도구와 함께 초기화"""
        system = MultiAgentSystem(config_path=mock_config)

        with patch('agents.multi_agent.get_mcp_tools', new_callable=AsyncMock) as mock_get_tools:
            mock_tool = MagicMock()
            mock_tool.name = "mcp_tool"
            mock_get_tools.return_value = [mock_tool]

            additional_tool = MagicMock()
            additional_tool.name = "additional_tool"

            with patch('agents.multi_agent.ChatOpenAI'):
                await system.initialize(additional_tools=[additional_tool])

                assert len(system.tools) == 2


class TestAgentState:
    """AgentState TypedDict 테스트"""

    def test_agent_state_creation(self):
        """상태 생성"""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="테스트")],
            "current_agent": "planner",
            "task_type": "research",
            "context": {"key": "value"},
            "final_answer": None,
            "tool_calls": []
        }

        assert state["current_agent"] == "planner"
        assert state["task_type"] == "research"
        assert len(state["messages"]) == 1


class TestPlannerNode:
    """Planner 노드 테스트"""

    @pytest.fixture
    def system(self, tmp_path):
        """테스트용 시스템"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return MultiAgentSystem(config_path=str(config_file))

    def test_planner_research_task(self, system):
        """검색 작업 판별"""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="Python에 대해 검색해줘")],
            "current_agent": "",
            "task_type": "",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        result = system._planner_node(state)

        assert result["task_type"] == "research"
        assert result["current_agent"] == "planner"

    def test_planner_analysis_task(self, system):
        """분석 작업 판별"""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="이 데이터를 분석해줘")],
            "current_agent": "",
            "task_type": "",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        result = system._planner_node(state)

        assert result["task_type"] == "analysis"

    def test_planner_execution_task(self, system):
        """실행 작업 판별"""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="보고서 만들어줘")],
            "current_agent": "",
            "task_type": "",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        result = system._planner_node(state)

        assert result["task_type"] == "execution"

    def test_planner_stores_original_query(self, system):
        """원본 쿼리 저장"""
        from langchain_core.messages import HumanMessage

        original_query = "Python에 대해 알려줘"
        state: AgentState = {
            "messages": [HumanMessage(content=original_query)],
            "current_agent": "",
            "task_type": "",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        result = system._planner_node(state)

        assert result["context"]["original_query"] == original_query


class TestRouteTask:
    """작업 라우팅 테스트"""

    @pytest.fixture
    def system(self, tmp_path):
        """테스트용 시스템"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return MultiAgentSystem(config_path=str(config_file))

    def test_route_to_research(self, system):
        """검색으로 라우팅"""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="Python에 대해 검색해줘")],
            "current_agent": "planner",
            "task_type": "research",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        result = system._route_task(state)

        assert result == "research"

    def test_route_to_analysis(self, system):
        """분석으로 라우팅"""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="이 데이터를 분석해줘")],
            "current_agent": "planner",
            "task_type": "analysis",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        result = system._route_task(state)

        assert result == "analysis"

    def test_route_short_query_to_execution(self, system):
        """짧은 쿼리는 실행으로"""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="안녕")],  # 10자 미만
            "current_agent": "planner",
            "task_type": "research",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        result = system._route_task(state)

        assert result == "execution"


class TestMultiAgentQuery:
    """쿼리 처리 테스트"""

    @pytest.fixture
    def mock_system(self, tmp_path):
        """테스트용 시스템"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return MultiAgentSystem(config_path=str(config_file))

    @pytest.mark.asyncio
    async def test_query_returns_expected_format(self, mock_system):
        """쿼리 결과 형식 확인"""
        from langchain_core.messages import AIMessage

        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "messages": [
                AIMessage(content="[Planner] 작업 유형: research"),
                AIMessage(content="[Researcher] 검색 결과"),
                AIMessage(content="[Executor] 최종 답변입니다.")
            ],
            "final_answer": "최종 답변입니다.",
            "tool_calls": []
        })

        mock_system.workflow = mock_workflow

        result = await mock_system.query("테스트 쿼리", thread_id="test")

        assert "answer" in result
        assert "steps" in result
        assert "agents_used" in result
        assert "tool_calls" in result
        assert "thread_id" in result

    @pytest.mark.asyncio
    async def test_query_extracts_agents_used(self, mock_system):
        """사용된 에이전트 추출"""
        from langchain_core.messages import AIMessage

        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "messages": [
                AIMessage(content="[Planner] 작업 분석"),
                AIMessage(content="[Researcher] 검색 완료"),
                AIMessage(content="[Analyzer] 분석 완료"),
                AIMessage(content="[Executor] 최종 답변")
            ],
            "final_answer": "최종 답변",
            "tool_calls": []
        })

        mock_system.workflow = mock_workflow

        result = await mock_system.query("복잡한 쿼리")

        assert "Planner" in result["agents_used"]
        assert "Researcher" in result["agents_used"]
        assert "Analyzer" in result["agents_used"]
        assert "Executor" in result["agents_used"]

    @pytest.mark.asyncio
    async def test_query_auto_initialize(self, mock_system):
        """초기화 안 된 상태에서 쿼리 시 자동 초기화"""
        assert mock_system.workflow is None

        with patch.object(mock_system, 'initialize', new_callable=AsyncMock) as mock_init:
            # initialize 후 workflow 설정
            async def set_workflow():
                mock_system.workflow = AsyncMock()
                mock_system.workflow.ainvoke = AsyncMock(return_value={
                    "messages": [],
                    "final_answer": "답변",
                    "tool_calls": []
                })

            mock_init.side_effect = set_workflow

            result = await mock_system.query("테스트")

            mock_init.assert_called_once()


class TestMultiAgentSingleton:
    """싱글톤 인스턴스 테스트"""

    @pytest.mark.asyncio
    async def test_get_multi_agent(self):
        """get_multi_agent 함수 테스트"""
        import agents.multi_agent as agent_module

        # 싱글톤 초기화
        agent_module._multi_agent = None

        with patch.object(MultiAgentSystem, '__init__', return_value=None):
            with patch.object(MultiAgentSystem, 'initialize', new_callable=AsyncMock):
                mock_agent_instance = MagicMock()
                mock_agent_instance.initialize = AsyncMock()

                with patch('agents.multi_agent.MultiAgentSystem', return_value=mock_agent_instance):
                    from agents.multi_agent import get_multi_agent

                    agent1 = await get_multi_agent()
                    agent2 = await get_multi_agent()

                    # 같은 인스턴스 반환
                    assert agent1 is agent2


class TestAgentNodes:
    """개별 에이전트 노드 테스트"""

    @pytest.fixture
    def system(self, tmp_path):
        """테스트용 시스템"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return MultiAgentSystem(config_path=str(config_file))

    @pytest.mark.asyncio
    async def test_researcher_node_uses_research_tools(self, system):
        """Researcher가 검색 도구 사용"""
        from langchain_core.messages import AIMessage, HumanMessage

        # 도구 설정
        search_tool = MagicMock()
        search_tool.name = "web_search"
        other_tool = MagicMock()
        other_tool.name = "calculator"
        system.tools = [search_tool, other_tool]

        # LLM 설정
        system.llm = MagicMock()

        state: AgentState = {
            "messages": [HumanMessage(content="테스트")],
            "current_agent": "planner",
            "task_type": "research",
            "context": {"original_query": "Python 검색"},
            "final_answer": None,
            "tool_calls": []
        }

        with patch('agents.multi_agent.create_react_agent') as mock_create:
            mock_agent = AsyncMock()
            mock_agent.ainvoke = AsyncMock(return_value={
                "messages": [AIMessage(content="검색 결과")]
            })
            mock_create.return_value = mock_agent

            result = await system._researcher_node(state)

            assert result["current_agent"] == "researcher"
            assert "research_result" in result["context"]

    @pytest.mark.asyncio
    async def test_executor_node_generates_final_answer(self, system):
        """Executor가 최종 답변 생성"""
        from langchain_core.messages import HumanMessage, AIMessage

        system.llm = AsyncMock()
        system.llm.ainvoke = AsyncMock(return_value=AIMessage(content="최종 종합 답변입니다."))

        state: AgentState = {
            "messages": [HumanMessage(content="테스트")],
            "current_agent": "analyzer",
            "task_type": "research",
            "context": {
                "original_query": "Python 검색",
                "research_result": "검색 결과",
                "analysis_result": "분석 결과"
            },
            "final_answer": None,
            "tool_calls": []
        }

        result = await system._executor_node(state)

        assert result["current_agent"] == "executor"
        assert result["final_answer"] == "최종 종합 답변입니다."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
