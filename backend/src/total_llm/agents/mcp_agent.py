"""
Simple MCP Agent using LangGraph ReAct pattern
langchain-mcp-adapters 기반의 단일 에이전트

Usage:
    agent = MCPAgent()
    await agent.initialize()
    result = await agent.query("15 더하기 27은?")
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
import yaml


from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# Import MCP tools
from total_llm.tools.mcp_client import get_mcp_tools, get_fallback_tools


class MCPAgent:
    """
    Simple ReAct Agent with MCP Tools

    Features:
    - ReAct pattern for reasoning and tool use
    - MCP protocol compatible tools
    - Memory for conversation persistence
    - Streaming support
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize MCP Agent

        Args:
            config_path: Path to config.yaml (optional)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.llm_config = self.config['llm']
        self.llm: Optional[ChatOpenAI] = None
        self.tools: List[BaseTool] = []
        self.tool_dict: Dict[str, BaseTool] = {}
        self.agent = None
        self.memory = MemorySaver()
        self._initialized = False

    async def initialize(self, additional_tools: Optional[List[BaseTool]] = None) -> None:
        """
        Initialize agent with tools and LLM

        Args:
            additional_tools: Extra tools to add (e.g., RAG tool)
        """
        if self._initialized:
            return

        # Load MCP tools
        try:
            self.tools = await get_mcp_tools()
        except Exception as e:
            print(f"⚠️  Failed to load MCP tools: {e}")
            self.tools = get_fallback_tools()

        # Add additional tools
        if additional_tools:
            self.tools.extend(additional_tools)

        # Build tool dictionary for lookup
        self.tool_dict = {tool.name: tool for tool in self.tools}

        # Initialize LLM (vLLM with OpenAI compatibility)
        self.llm = ChatOpenAI(
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model_name'],
            temperature=self.llm_config.get('temperature', 0.7),
            max_tokens=self.llm_config.get('max_tokens', 4096),
            api_key="EMPTY"  # vLLM doesn't require API key
        )

        # Create ReAct agent
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            checkpointer=self.memory
        )

        self._initialized = True
        print(f"✅ MCP Agent initialized with {len(self.tools)} tools")
        print(f"   Tools: {', '.join(self.tool_dict.keys())}")

    async def query(
        self,
        user_input: str,
        thread_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Process user query through ReAct agent

        Args:
            user_input: User's question or command
            thread_id: Conversation thread ID for memory

        Returns:
            Dictionary with answer, tool_calls, and metadata
        """
        if not self._initialized or self.agent is None:
            await self.initialize()

        # Prepare input
        messages = [HumanMessage(content=user_input)]

        # Run agent with memory
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.agent.ainvoke({"messages": messages}, config)

        # Extract response
        output_messages = result.get("messages", [])

        # Get final answer
        final_answer = ""
        for msg in reversed(output_messages):
            if isinstance(msg, AIMessage) and msg.content:
                final_answer = msg.content
                break

        # Extract tool calls
        tool_calls = []
        for msg in output_messages:
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "name": tc.get("name", "unknown"),
                        "args": tc.get("args", {}),
                        "id": tc.get("id", "")
                    })

        return {
            "answer": final_answer,
            "tool_calls": tool_calls,
            "thread_id": thread_id,
            "tools_used": len(tool_calls)
        }

    async def query_stream(
        self,
        user_input: str,
        thread_id: str = "default"
    ):
        """
        Stream query processing for real-time updates

        Args:
            user_input: User's question
            thread_id: Conversation thread ID

        Yields:
            Dictionary events with type (token, tool_call, complete)
        """
        if not self._initialized or self.agent is None:
            await self.initialize()

        messages = [HumanMessage(content=user_input)]
        config = {"configurable": {"thread_id": thread_id}}

        tool_calls = []
        final_content = ""

        async for event in self.agent.astream_events(
            {"messages": messages},
            config,
            version="v2"
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                # Token streaming
                content = event.get("data", {}).get("chunk", {})
                if hasattr(content, 'content') and content.content:
                    final_content += content.content
                    yield {
                        "type": "token",
                        "content": content.content
                    }

            elif kind == "on_tool_start":
                # Tool invocation started
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield {
                    "type": "tool_start",
                    "name": tool_name,
                    "input": tool_input
                }

            elif kind == "on_tool_end":
                # Tool completed
                tool_name = event.get("name", "unknown")
                tool_output = event.get("data", {}).get("output", "")
                tool_calls.append({
                    "name": tool_name,
                    "output": str(tool_output)[:200]  # Truncate long outputs
                })
                yield {
                    "type": "tool_end",
                    "name": tool_name,
                    "output": str(tool_output)[:200]
                }

        # Final completion event
        yield {
            "type": "complete",
            "answer": final_content,
            "tool_calls": tool_calls,
            "thread_id": thread_id
        }

    def get_tools_info(self) -> List[Dict[str, str]]:
        """Get information about available tools"""
        return [
            {
                "name": tool.name,
                "description": tool.description[:100] + "..." if len(tool.description) > 100 else tool.description
            }
            for tool in self.tools
        ]


# Singleton instance
_agent: Optional[MCPAgent] = None


async def get_mcp_agent() -> MCPAgent:
    """Get or create singleton MCP Agent instance"""
    global _agent
    if _agent is None:
        _agent = MCPAgent()
        await _agent.initialize()
    return _agent


# Test
if __name__ == "__main__":
    import asyncio

    async def test():
        print("Testing MCP Agent...")

        agent = MCPAgent()
        await agent.initialize()

        # Test queries
        queries = [
            "15 더하기 27은?",
            "100을 5로 나누면?",
            "Python에 대해 알려줘"
        ]

        for query in queries:
            print(f"\n{'='*50}")
            print(f"Query: {query}")
            print(f"{'='*50}")

            result = await agent.query(query, thread_id="test")
            print(f"Answer: {result['answer']}")
            print(f"Tools used: {result['tools_used']}")

            if result['tool_calls']:
                print("Tool calls:")
                for tc in result['tool_calls']:
                    print(f"  - {tc['name']}: {tc['args']}")

    asyncio.run(test())
