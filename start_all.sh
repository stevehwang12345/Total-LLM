#!/bin/bash
# vLLM 프로젝트 통합 시작 스크립트
# GPT-OSS-20B + LangGraph + MCP 통합 시스템

set -e

PROJECT_ROOT="/home/sphwang/dev/vLLM"
cd "$PROJECT_ROOT"

echo "======================================================"
echo "🚀 Starting vLLM Project"
echo "======================================================"

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 함수: 서비스 상태 확인
check_service() {
    local service_name=$1
    local port=$2

    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}✅ $service_name (port $port) is already running${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ $service_name (port $port) not running${NC}"
        return 1
    fi
}

# 1. Qdrant 시작
echo ""
echo "======================================================"
echo "1️⃣  Starting Qdrant Vector Database..."
echo "======================================================"

if check_service "Qdrant" 6333; then
    echo "Qdrant already running, skipping..."
else
    docker compose up -d qdrant
    echo "Waiting for Qdrant to be ready..."
    sleep 5

    if check_service "Qdrant" 6333; then
        echo -e "${GREEN}✅ Qdrant started successfully${NC}"
    else
        echo -e "${RED}❌ Failed to start Qdrant${NC}"
        exit 1
    fi
fi

# 2. vLLM 서버 시작
echo ""
echo "======================================================"
echo "2️⃣  Starting vLLM Server (GPT-OSS-20B on GPU 1)..."
echo "======================================================"

if check_service "vLLM" 9000; then
    echo "vLLM already running, skipping..."
else
    # 백그라운드로 vLLM 실행
    nohup ./services/vllm/run_vllm.sh > vllm_server.log 2>&1 &
    echo $! > vllm.pid

    echo "Waiting for vLLM to load model (this may take 1-2 minutes)..."
    for i in {1..60}; do
        if check_service "vLLM" 9000; then
            echo -e "${GREEN}✅ vLLM started successfully${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done

    if ! check_service "vLLM" 9000; then
        echo -e "${RED}❌ vLLM failed to start. Check vllm_server.log${NC}"
        exit 1
    fi
fi

# 3. LangGraph Dev 서버 시작
echo ""
echo "======================================================"
echo "3️⃣  Starting LangGraph Dev Server (MCP + Agent)..."
echo "======================================================"

if check_service "LangGraph" 2024; then
    echo "LangGraph Dev already running, skipping..."
else
    cd "$PROJECT_ROOT/frontend"

    # 백그라운드로 LangGraph dev 실행
    nohup langgraph dev --port 2024 > langgraph_dev.log 2>&1 &
    echo $! > langgraph.pid

    echo "Waiting for LangGraph to be ready..."
    sleep 10

    if check_service "LangGraph" 2024; then
        echo -e "${GREEN}✅ LangGraph Dev started successfully${NC}"
    else
        echo -e "${RED}❌ LangGraph failed to start. Check frontend/langgraph_dev.log${NC}"
        exit 1
    fi

    cd "$PROJECT_ROOT"
fi

# 4. Simple Web UI 서버 시작 (독립)
echo ""
echo "======================================================"
echo "4️⃣  Starting Simple Web UI..."
echo "======================================================"

if check_service "Simple UI" 9001; then
    echo "Simple UI already running, skipping..."
else
    cd "$PROJECT_ROOT/frontend/simple_ui"

    # 백그라운드로 HTTP 서버 실행 (포트 9001)
    nohup python3 -m http.server 9001 > simple_ui.log 2>&1 &
    echo $! > simple_ui.pid

    sleep 3

    if check_service "Simple UI" 9001; then
        echo -e "${GREEN}✅ Simple Web UI started successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Simple UI may have failed. Check frontend/simple_ui/simple_ui.log${NC}"
    fi

    cd "$PROJECT_ROOT"
fi

# 5. 최종 상태 확인
echo ""
echo "======================================================"
echo "✨ Startup Complete! Service Status:"
echo "======================================================"

check_service "Qdrant" 6333 && echo "  - Qdrant Vector DB: http://localhost:6333" || echo -e "${RED}  - Qdrant: FAILED${NC}"
check_service "vLLM" 9000 && echo "  - vLLM API: http://localhost:9000/v1" || echo -e "${RED}  - vLLM: FAILED${NC}"
check_service "LangGraph" 2024 && echo "  - LangGraph Dev: http://localhost:2024" || echo -e "${RED}  - LangGraph: FAILED${NC}"
check_service "Simple UI" 9001 && echo "  - Simple Web UI: http://localhost:9001" || echo -e "${YELLOW}  - Simple UI: FAILED (optional)${NC}"

echo ""
echo "======================================================"
echo "🎯 Access Points:"
echo "======================================================"
echo "  📊 LangGraph Studio:"
echo "     https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"
echo ""
echo "  💻 Simple Web UI:"
echo "     http://localhost:9001"
echo ""
echo "  🔧 API Docs:"
echo "     vLLM: http://localhost:9000/docs"
echo "     Qdrant: http://localhost:6333/dashboard"
echo ""
echo "======================================================"
echo "📝 Logs:"
echo "======================================================"
echo "  - vLLM: tail -f vllm_server.log"
echo "  - LangGraph: tail -f frontend/langgraph_dev.log"
echo "  - Simple UI: tail -f frontend/simple_ui/simple_ui.log"
echo ""
echo "======================================================"
echo "🛑 To stop all services: ./stop_all.sh"
echo "======================================================"
