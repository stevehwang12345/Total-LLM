"""
MCP Client Integration using langchain-mcp-adapters
표준 MCP 서버와 연동하는 클라이언트

지원 방식:
1. Stdio Transport: 로컬 MCP 서버 프로세스 실행
2. HTTP Transport: 원격 MCP 서버 연결
3. Fallback: MCP 서버 없을 시 기본 도구 제공
"""

import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
from langchain_core.tools import BaseTool, tool

# MCP Adapters import (optional - fallback if not available)
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️  langchain-mcp-adapters not installed. Using fallback tools.")


# ============================================================
# Fallback Tools (MCP 서버 없을 때 사용)
# ============================================================

@tool
def add(a: float, b: float) -> float:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b


@tool
def subtract(a: float, b: float) -> float:
    """Subtract second number from first number.

    Args:
        a: First number
        b: Second number to subtract

    Returns:
        Result of a minus b
    """
    return a - b


@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of a and b
    """
    return a * b


@tool
def divide(a: float, b: float) -> str:
    """Divide first number by second number.

    Args:
        a: Dividend (number to be divided)
        b: Divisor (number to divide by)

    Returns:
        Result of division or error message if dividing by zero
    """
    if b == 0:
        return "Error: Division by zero is not allowed"
    return str(a / b)


@tool
def search_web(query: str) -> str:
    """Search the web for information.

    Args:
        query: Search query string

    Returns:
        Search results summary
    """
    # Placeholder - 실제 구현시 웹 검색 API 연동
    return f"Web search results for '{query}': This is a placeholder. Integrate with actual search API for real results."


@tool
def search_documents(query: str) -> str:
    """Search documents in the RAG system.

    Args:
        query: Search query for document retrieval

    Returns:
        Relevant document excerpts
    """
    # Placeholder - RAG 시스템과 연동
    return f"Document search for '{query}': This searches the local document database. Connect to RAG retriever for actual results."


# ============================================================
# Fallback Tools List
# ============================================================

FALLBACK_TOOLS: List[BaseTool] = [
    add,
    subtract,
    multiply,
    divide,
    search_web,
    search_documents,
]


# ============================================================
# MCP Server Configuration
# ============================================================

def get_mcp_server_config() -> Dict[str, Any]:
    """
    MCP 서버 설정 반환

    환경에 맞게 수정하세요:
    - stdio: 로컬 Python 스크립트 실행
    - http: 원격 MCP 서버 연결
    - streamable_http: 스트리밍 지원 HTTP
    """
    config = {}

    # Example: Math MCP Server (stdio)
    # math_server_path = Path(__file__).parent.parent / "services" / "mcp" / "math_server.py"
    # if math_server_path.exists():
    #     config["math"] = {
    #         "command": "python",
    #         "args": [str(math_server_path)],
    #         "transport": "stdio",
    #     }

    # Example: Remote MCP Server (http)
    # config["remote_tools"] = {
    #     "url": "http://localhost:8000/mcp",
    #     "transport": "http",
    # }

    # Example: Streamable HTTP
    # config["weather"] = {
    #     "url": "http://localhost:8001/mcp",
    #     "transport": "streamable_http",
    # }

    return config


# ============================================================
# MCP Client Manager
# ============================================================

class MCPClientManager:
    """MCP 클라이언트 매니저 - 싱글톤 패턴"""

    _instance: Optional['MCPClientManager'] = None
    _client: Optional['MultiServerMCPClient'] = None
    _tools: Optional[List[BaseTool]] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """MCP 클라이언트 초기화"""
        if self._initialized:
            return

        if not MCP_AVAILABLE:
            print("⚠️  MCP adapters not available. Using fallback tools.")
            self._tools = FALLBACK_TOOLS
            self._initialized = True
            return

        config = get_mcp_server_config()

        if not config:
            print("ℹ️  No MCP servers configured. Using fallback tools.")
            self._tools = FALLBACK_TOOLS
            self._initialized = True
            return

        try:
            self._client = MultiServerMCPClient(config)
            self._tools = await self._client.get_tools()
            print(f"✅ MCP Client initialized with {len(self._tools)} tools from {len(config)} server(s)")
            self._initialized = True
        except Exception as e:
            print(f"⚠️  MCP initialization failed: {e}")
            print("   Falling back to default tools.")
            self._tools = FALLBACK_TOOLS
            self._initialized = True

    async def get_tools(self) -> List[BaseTool]:
        """도구 목록 반환"""
        if not self._initialized:
            await self.initialize()
        return self._tools or FALLBACK_TOOLS

    async def close(self) -> None:
        """클라이언트 종료"""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
        self._initialized = False
        self._tools = None


# ============================================================
# Public API
# ============================================================

_manager: Optional[MCPClientManager] = None


async def get_mcp_tools() -> List[BaseTool]:
    """
    MCP 도구 목록 반환 (메인 API)

    사용법:
        tools = await get_mcp_tools()
        agent = create_react_agent(llm, tools)

    Returns:
        List of LangChain-compatible tools
    """
    global _manager

    if _manager is None:
        _manager = MCPClientManager()

    return await _manager.get_tools()


async def close_mcp_client() -> None:
    """MCP 클라이언트 종료"""
    global _manager

    if _manager:
        await _manager.close()
        _manager = None


def get_fallback_tools() -> List[BaseTool]:
    """
    동기 방식으로 기본 도구 반환
    MCP 서버 연결 없이 즉시 사용 가능
    """
    return FALLBACK_TOOLS


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    async def test():
        print("Testing MCP Client...")

        tools = await get_mcp_tools()
        print(f"\nLoaded {len(tools)} tools:")

        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")

        # Test calculator tools
        print("\n\nTesting calculator tools:")
        print(f"  add(10, 5) = {add.invoke({'a': 10, 'b': 5})}")
        print(f"  subtract(10, 5) = {subtract.invoke({'a': 10, 'b': 5})}")
        print(f"  multiply(10, 5) = {multiply.invoke({'a': 10, 'b': 5})}")
        print(f"  divide(10, 5) = {divide.invoke({'a': 10, 'b': 5})}")

        await close_mcp_client()
        print("\n✅ Test completed!")

    asyncio.run(test())
