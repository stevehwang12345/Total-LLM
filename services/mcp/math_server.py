#!/usr/bin/env python3
"""
Math MCP Server
기본 수학 연산을 제공하는 MCP 서버 (stdio transport)
"""

import asyncio
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field


# Tool input schemas
class AddInput(BaseModel):
    """두 숫자를 더합니다"""
    a: float = Field(..., description="첫 번째 숫자")
    b: float = Field(..., description="두 번째 숫자")


class SubtractInput(BaseModel):
    """두 숫자를 뺍니다"""
    a: float = Field(..., description="피감수")
    b: float = Field(..., description="감수")


class MultiplyInput(BaseModel):
    """두 숫자를 곱합니다"""
    a: float = Field(..., description="첫 번째 숫자")
    b: float = Field(..., description="두 번째 숫자")


class DivideInput(BaseModel):
    """두 숫자를 나눕니다"""
    a: float = Field(..., description="피제수")
    b: float = Field(..., description="제수")


# MCP Server
server = Server("math-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록"""
    return [
        Tool(
            name="add",
            description="두 숫자를 더합니다",
            inputSchema=AddInput.model_json_schema(),
        ),
        Tool(
            name="subtract",
            description="두 숫자를 뺍니다",
            inputSchema=SubtractInput.model_json_schema(),
        ),
        Tool(
            name="multiply",
            description="두 숫자를 곱합니다",
            inputSchema=MultiplyInput.model_json_schema(),
        ),
        Tool(
            name="divide",
            description="두 숫자를 나눕니다 (0으로 나누기 방지)",
            inputSchema=DivideInput.model_json_schema(),
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """도구 실행"""

    if name == "add":
        args = AddInput(**arguments)
        result = args.a + args.b
        return [TextContent(
            type="text",
            text=f"{args.a} + {args.b} = {result}"
        )]

    elif name == "subtract":
        args = SubtractInput(**arguments)
        result = args.a - args.b
        return [TextContent(
            type="text",
            text=f"{args.a} - {args.b} = {result}"
        )]

    elif name == "multiply":
        args = MultiplyInput(**arguments)
        result = args.a * args.b
        return [TextContent(
            type="text",
            text=f"{args.a} × {args.b} = {result}"
        )]

    elif name == "divide":
        args = DivideInput(**arguments)
        if args.b == 0:
            return [TextContent(
                type="text",
                text="오류: 0으로 나눌 수 없습니다"
            )]
        result = args.a / args.b
        return [TextContent(
            type="text",
            text=f"{args.a} ÷ {args.b} = {result}"
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
