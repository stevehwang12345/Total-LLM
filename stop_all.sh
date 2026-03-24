#!/bin/bash
# vLLM 프로젝트 통합 중지 스크립트

set -e

PROJECT_ROOT="/home/sphwang/dev/vLLM"
cd "$PROJECT_ROOT"

echo "======================================================"
echo "🛑 Stopping vLLM Project Services"
echo "======================================================"

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 1. Simple UI 중지
echo "1️⃣  Stopping Simple Web UI..."
if [ -f "frontend/simple_ui/simple_ui.pid" ]; then
    PID=$(cat frontend/simple_ui/simple_ui.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo -e "${GREEN}✅ Simple UI stopped (PID: $PID)${NC}"
    else
        echo "Simple UI already stopped"
    fi
    rm -f frontend/simple_ui/simple_ui.pid
else
    # PID 파일이 없으면 프로세스 찾아서 종료
    pkill -f "python3 -m http.server 9001" 2>/dev/null && echo -e "${GREEN}✅ Simple UI stopped${NC}" || echo "Simple UI not running"
fi

# 2. LangGraph Dev 중지
echo ""
echo "2️⃣  Stopping LangGraph Dev Server..."
if [ -f "frontend/langgraph.pid" ]; then
    PID=$(cat frontend/langgraph.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo -e "${GREEN}✅ LangGraph Dev stopped (PID: $PID)${NC}"
    else
        echo "LangGraph already stopped"
    fi
    rm -f frontend/langgraph.pid
else
    pkill -f "langgraph dev" 2>/dev/null && echo -e "${GREEN}✅ LangGraph Dev stopped${NC}" || echo "LangGraph not running"
fi

# 3. vLLM 서버 중지
echo ""
echo "3️⃣  Stopping vLLM Server..."
if [ -f "vllm.pid" ]; then
    PID=$(cat vllm.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo -e "${GREEN}✅ vLLM stopped (PID: $PID)${NC}"
    else
        echo "vLLM already stopped"
    fi
    rm -f vllm.pid
fi

# Docker 컨테이너도 확인
docker stop vllm-gpt-oss-20b 2>/dev/null && echo -e "${GREEN}✅ vLLM Docker container stopped${NC}" || echo "vLLM Docker container not running"

# 4. Qdrant 중지 (선택사항)
echo ""
echo "4️⃣  Stopping Qdrant Vector Database..."
read -p "Do you want to stop Qdrant? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose stop qdrant
    echo -e "${GREEN}✅ Qdrant stopped${NC}"
else
    echo "Qdrant kept running (use 'docker compose stop qdrant' to stop manually)"
fi

echo ""
echo "======================================================"
echo "✅ All services stopped"
echo "======================================================"
echo ""
echo "Remaining processes:"
ps aux | grep -E "vllm|langgraph|http.server 9001" | grep -v grep || echo "  (none)"
