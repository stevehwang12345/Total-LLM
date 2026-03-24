#!/usr/bin/env python3
"""
Search MCP Server
웹 검색 기능을 제공하는 MCP 서버 (HTTP transport)
POC용으로 간단한 시뮬레이션 구현
"""

import asyncio
from typing import Dict, List
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field


# Tool input schemas
class SearchInput(BaseModel):
    """검색어를 입력받습니다"""
    query: str = Field(..., description="검색어")
    max_results: int = Field(default=3, description="최대 결과 개수")


# 시뮬레이션 검색 데이터베이스
MOCK_DATABASE = {
    "python": [
        {"title": "Python 공식 문서", "url": "https://docs.python.org", "snippet": "Python 3.x 공식 문서입니다."},
        {"title": "Python Tutorial", "url": "https://www.python.org/about/gettingstarted/", "snippet": "Python 시작 가이드"},
        {"title": "Real Python", "url": "https://realpython.com", "snippet": "Python 튜토리얼과 예제"},
    ],
    "machine learning": [
        {"title": "Scikit-learn", "url": "https://scikit-learn.org", "snippet": "Python 머신러닝 라이브러리"},
        {"title": "TensorFlow", "url": "https://tensorflow.org", "snippet": "구글의 딥러닝 프레임워크"},
        {"title": "PyTorch", "url": "https://pytorch.org", "snippet": "Facebook의 딥러닝 라이브러리"},
    ],
    "rag": [
        {"title": "LangChain RAG", "url": "https://langchain.com/rag", "snippet": "LangChain을 사용한 RAG 구현"},
        {"title": "Qdrant Vector DB", "url": "https://qdrant.tech", "snippet": "고성능 벡터 데이터베이스"},
        {"title": "OpenAI Embeddings", "url": "https://openai.com/embeddings", "snippet": "텍스트 임베딩 API"},
    ],
    "default": [
        {"title": "검색 결과", "url": "https://example.com", "snippet": "관련 정보를 찾을 수 없습니다."},
    ]
}


# MCP Server
server = Server("search-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록"""
    return [
        Tool(
            name="web_search",
            description="웹에서 정보를 검색합니다 (시뮬레이션)",
            inputSchema=SearchInput.model_json_schema(),
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """도구 실행"""

    if name == "web_search":
        args = SearchInput(**arguments)
        query_lower = args.query.lower()

        # 키워드 매칭
        results = None
        for keyword, data in MOCK_DATABASE.items():
            if keyword in query_lower:
                results = data[:args.max_results]
                break

        if results is None:
            results = MOCK_DATABASE["default"][:args.max_results]

        # 결과 포맷팅
        formatted_results = f"🔍 검색어: '{args.query}'\n\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"{i}. {result['title']}\n"
            formatted_results += f"   URL: {result['url']}\n"
            formatted_results += f"   {result['snippet']}\n\n"

        return [TextContent(
            type="text",
            text=formatted_results.strip()
        )]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """MCP 서버 시작"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
