"""
MCP 서버 단위 테스트
Math Server와 Search Server의 도구 기능을 테스트합니다.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest


# MCP 서버 경로
BACKEND_DIR = Path(__file__).parent.parent.parent
MATH_SERVER = BACKEND_DIR / "services" / "mcp" / "math_server.py"
SEARCH_SERVER = BACKEND_DIR / "services" / "mcp" / "search_server.py"


class TestMathServer:
    """Math Server 도구 테스트"""

    def test_initialize(self):
        """서버 초기화 테스트"""
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        result = self._call_server(MATH_SERVER, request)

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["protocolVersion"] == "2024-11-05"
        assert result["result"]["serverInfo"]["name"] == "math-server"

    def test_tools_list(self):
        """도구 목록 조회 테스트"""
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        result = self._call_server(MATH_SERVER, request)

        assert "result" in result
        tools = result["result"]["tools"]
        assert len(tools) == 4
        tool_names = [t["name"] for t in tools]
        assert set(tool_names) == {"add", "subtract", "multiply", "divide"}

    def test_add_tool(self):
        """덧셈 도구 테스트"""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add",
                "arguments": {"a": 25, "b": 17}
            }
        }
        result = self._call_server(MATH_SERVER, request)

        assert "result" in result
        content = result["result"]["content"][0]["text"]
        assert "42" in content

    def test_multiply_tool(self):
        """곱셈 도구 테스트"""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "multiply",
                "arguments": {"a": 25, "b": 4}
            }
        }
        result = self._call_server(MATH_SERVER, request)

        assert "result" in result
        content = result["result"]["content"][0]["text"]
        assert "100" in content

    def test_divide_tool(self):
        """나눗셈 도구 테스트"""
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "divide",
                "arguments": {"a": 100, "b": 4}
            }
        }
        result = self._call_server(MATH_SERVER, request)

        assert "result" in result
        content = result["result"]["content"][0]["text"]
        assert "25" in content

    def test_divide_by_zero(self):
        """0으로 나누기 에러 테스트"""
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "divide",
                "arguments": {"a": 10, "b": 0}
            }
        }
        result = self._call_server(MATH_SERVER, request)

        assert "result" in result
        assert "error" in result["result"]

    def _call_server(self, server_path, request):
        """MCP 서버 호출 헬퍼"""
        proc = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, _ = proc.communicate(json.dumps(request) + "\n")
        return json.loads(stdout.strip())


class TestSearchServer:
    """Search Server 도구 테스트"""

    def test_initialize(self):
        """서버 초기화 테스트"""
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        result = self._call_server(SEARCH_SERVER, request)

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["protocolVersion"] == "2024-11-05"
        assert result["result"]["serverInfo"]["name"] == "search-server"

    def test_tools_list(self):
        """도구 목록 조회 테스트"""
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        result = self._call_server(SEARCH_SERVER, request)

        assert "result" in result
        tools = result["result"]["tools"]
        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert set(tool_names) == {"search_web", "search_documents"}

    def test_search_web_tool(self):
        """웹 검색 도구 테스트"""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_web",
                "arguments": {"query": "Python", "max_results": 3}
            }
        }
        result = self._call_server(SEARCH_SERVER, request)

        assert "result" in result
        content = result["result"]["content"][0]["text"]
        assert "Python" in content
        assert "검색 결과" in content

    def test_search_documents_tool(self):
        """문서 검색 도구 테스트"""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "search_documents",
                "arguments": {"query": "AI"}
            }
        }
        result = self._call_server(SEARCH_SERVER, request)

        assert "result" in result
        content = result["result"]["content"][0]["text"]
        assert "AI" in content or "내부 문서" in content

    def _call_server(self, server_path, request):
        """MCP 서버 호출 헬퍼"""
        proc = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, _ = proc.communicate(json.dumps(request) + "\n")
        return json.loads(stdout.strip())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
