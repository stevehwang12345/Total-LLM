"""
MCP Agent 단위 테스트

Simple MCP Agent의 기능을 테스트합니다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.mcp_agent import MCPAgent


class TestMCPAgentInit:
    """MCP Agent 초기화 테스트"""

    def test_init_default_config(self, tmp_path):
        """기본 설정으로 초기화"""
        # 테스트용 설정 파일 생성
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        agent = MCPAgent(config_path=str(config_file))
        assert agent is not None
        assert agent._initialized is False
        assert agent.tools == []
        assert agent.tool_dict == {}
        assert agent.agent is None

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

        agent = MCPAgent(config_path=str(config_file))
        assert agent.llm_config["model_name"] == "test-model"


class TestMCPAgentInitialize:
    """MCP Agent 초기화 메서드 테스트"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """테스트용 설정 파일"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
mcp:
  enabled: true
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.mark.asyncio
    async def test_initialize_with_fallback_tools(self, mock_config):
        """Fallback 도구로 초기화"""
        agent = MCPAgent(config_path=mock_config)

        with patch('agents.mcp_agent.get_mcp_tools', new_callable=AsyncMock) as mock_get_tools:
            mock_get_tools.side_effect = Exception("MCP unavailable")

            with patch('agents.mcp_agent.get_fallback_tools') as mock_fallback:
                mock_tool = MagicMock()
                mock_tool.name = "fallback_tool"
                mock_fallback.return_value = [mock_tool]

                with patch('agents.mcp_agent.ChatOpenAI'):
                    with patch('agents.mcp_agent.create_react_agent') as mock_create_agent:
                        mock_create_agent.return_value = MagicMock()
                        await agent.initialize()

                        assert agent._initialized is True
                        assert len(agent.tools) == 1
                        assert "fallback_tool" in agent.tool_dict

    @pytest.mark.asyncio
    async def test_initialize_with_additional_tools(self, mock_config):
        """추가 도구와 함께 초기화"""
        agent = MCPAgent(config_path=mock_config)

        with patch('agents.mcp_agent.get_mcp_tools', new_callable=AsyncMock) as mock_get_tools:
            mock_tool = MagicMock()
            mock_tool.name = "mcp_tool"
            mock_get_tools.return_value = [mock_tool]

            additional_tool = MagicMock()
            additional_tool.name = "additional_tool"

            with patch('agents.mcp_agent.ChatOpenAI'):
                with patch('agents.mcp_agent.create_react_agent') as mock_create_agent:
                    mock_create_agent.return_value = MagicMock()
                    await agent.initialize(additional_tools=[additional_tool])

                    assert len(agent.tools) == 2
                    assert "mcp_tool" in agent.tool_dict
                    assert "additional_tool" in agent.tool_dict

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mock_config):
        """초기화는 한 번만 실행"""
        agent = MCPAgent(config_path=mock_config)

        with patch('agents.mcp_agent.get_mcp_tools', new_callable=AsyncMock) as mock_get_tools:
            mock_get_tools.return_value = []

            with patch('agents.mcp_agent.ChatOpenAI'):
                with patch('agents.mcp_agent.create_react_agent') as mock_create_agent:
                    mock_create_agent.return_value = MagicMock()

                    await agent.initialize()
                    await agent.initialize()  # 두 번째 호출

                    # 한 번만 호출됨
                    assert mock_get_tools.call_count == 1


class TestMCPAgentQuery:
    """MCP Agent 쿼리 테스트"""

    @pytest.fixture
    def mock_agent(self, tmp_path):
        """테스트용 에이전트"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return MCPAgent(config_path=str(config_file))

    @pytest.mark.asyncio
    async def test_query_basic(self, mock_agent):
        """기본 쿼리 테스트"""
        from langchain_core.messages import AIMessage

        mock_agent._initialized = True
        mock_agent.agent = AsyncMock()

        # 응답 설정
        mock_result = {
            "messages": [
                AIMessage(content="테스트 답변입니다.")
            ]
        }
        mock_agent.agent.ainvoke = AsyncMock(return_value=mock_result)

        result = await mock_agent.query("테스트 질문")

        assert "answer" in result
        assert result["answer"] == "테스트 답변입니다."
        assert "tool_calls" in result
        assert "thread_id" in result

    @pytest.mark.asyncio
    async def test_query_with_tool_calls(self, mock_agent):
        """도구 호출이 있는 쿼리"""
        from langchain_core.messages import AIMessage

        mock_agent._initialized = True
        mock_agent.agent = AsyncMock()

        # 도구 호출이 있는 응답
        ai_msg_with_tools = AIMessage(content="")
        ai_msg_with_tools.tool_calls = [
            {"name": "calculator", "args": {"a": 1, "b": 2}, "id": "tc1"}
        ]

        final_msg = AIMessage(content="결과는 3입니다.")

        mock_result = {
            "messages": [ai_msg_with_tools, final_msg]
        }
        mock_agent.agent.ainvoke = AsyncMock(return_value=mock_result)

        result = await mock_agent.query("1 + 2는?")

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "calculator"

    @pytest.mark.asyncio
    async def test_query_auto_initialize(self, mock_agent):
        """초기화 안 된 상태에서 쿼리 시 자동 초기화"""
        assert mock_agent._initialized is False

        with patch.object(mock_agent, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_agent._initialized = True
            mock_agent.agent = AsyncMock()

            from langchain_core.messages import AIMessage
            mock_agent.agent.ainvoke = AsyncMock(return_value={
                "messages": [AIMessage(content="자동 초기화 후 응답")]
            })

            # 처음에는 초기화 안 됨
            mock_agent._initialized = False

            result = await mock_agent.query("테스트")

            # initialize가 호출됨
            mock_init.assert_called_once()


class TestMCPAgentToolsInfo:
    """도구 정보 조회 테스트"""

    def test_get_tools_info_empty(self, tmp_path):
        """도구 없음"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        agent = MCPAgent(config_path=str(config_file))
        tools_info = agent.get_tools_info()

        assert tools_info == []

    def test_get_tools_info_with_tools(self, tmp_path):
        """도구가 있는 경우"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        agent = MCPAgent(config_path=str(config_file))

        # 테스트 도구 추가
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "테스트 도구입니다."
        agent.tools = [mock_tool]

        tools_info = agent.get_tools_info()

        assert len(tools_info) == 1
        assert tools_info[0]["name"] == "test_tool"
        assert tools_info[0]["description"] == "테스트 도구입니다."

    def test_get_tools_info_long_description_truncated(self, tmp_path):
        """긴 설명은 잘림"""
        config_content = """
llm:
  base_url: http://localhost:9000/v1
  model_name: test-model
  temperature: 0.7
  max_tokens: 4096
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        agent = MCPAgent(config_path=str(config_file))

        mock_tool = MagicMock()
        mock_tool.name = "long_desc_tool"
        mock_tool.description = "A" * 200  # 200자
        agent.tools = [mock_tool]

        tools_info = agent.get_tools_info()

        # 100자 + "..."
        assert len(tools_info[0]["description"]) == 103


class TestMCPAgentSingleton:
    """싱글톤 인스턴스 테스트"""

    @pytest.mark.asyncio
    async def test_get_mcp_agent(self):
        """get_mcp_agent 함수 테스트"""
        import agents.mcp_agent as agent_module

        # 싱글톤 초기화
        agent_module._agent = None

        with patch.object(MCPAgent, '__init__', return_value=None) as mock_init:
            with patch.object(MCPAgent, 'initialize', new_callable=AsyncMock) as mock_initialize:
                # 객체의 속성 설정
                mock_agent_instance = MagicMock()
                mock_agent_instance.initialize = AsyncMock()

                with patch('agents.mcp_agent.MCPAgent', return_value=mock_agent_instance):
                    from agents.mcp_agent import get_mcp_agent

                    agent1 = await get_mcp_agent()
                    agent2 = await get_mcp_agent()

                    # 같은 인스턴스 반환
                    assert agent1 is agent2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
