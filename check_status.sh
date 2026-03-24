#!/bin/bash
# vLLM 프로젝트 상태 확인 스크립트

PROJECT_ROOT="/home/sphwang/dev/vLLM"

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "======================================================"
echo "🔍 vLLM Project Health Check"
echo "======================================================"

# 함수: 서비스 상태 확인
check_service() {
    local service_name=$1
    local port=$2
    local endpoint=$3

    echo ""
    echo -e "${BLUE}Checking $service_name...${NC}"

    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}✅ Port $port is open${NC}"

        if [ -n "$endpoint" ]; then
            if curl -s "$endpoint" > /dev/null 2>&1; then
                echo -e "${GREEN}✅ API endpoint responding${NC}"
                echo -e "   URL: $endpoint"
            else
                echo -e "${YELLOW}⚠️  Port open but endpoint not responding${NC}"
                echo -e "   URL: $endpoint"
            fi
        fi
    else
        echo -e "${RED}❌ Port $port is closed${NC}"
    fi
}

# 1. Qdrant
check_service "Qdrant Vector DB" 6333 "http://localhost:6333/dashboard"

# 2. vLLM
check_service "vLLM Server" 9000 "http://localhost:9000/v1/models"

# 3. LangGraph Dev
check_service "LangGraph Dev" 2024 ""

# 4. Simple UI
check_service "Simple Web UI" 9001 "http://localhost:9001"

# 5. Docker 컨테이너 상태
echo ""
echo -e "${BLUE}Docker Containers:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "qdrant|vllm" || echo -e "${YELLOW}No vLLM-related containers running${NC}"

# 6. 실행 중인 프로세스
echo ""
echo -e "${BLUE}Running Processes:${NC}"
ps aux | grep -E "vllm|langgraph|http.server 9001" | grep -v grep | awk '{print "  - PID " $2 ": " $11 " " $12 " " $13}' || echo "  (none)"

# 7. GPU 상태 (vLLM이 GPU 1 사용 중인지 확인)
echo ""
echo -e "${BLUE}GPU Status (GPU 1):${NC}"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi -i 1 --query-gpu=name,memory.used,memory.total --format=csv,noheader,nounits | awk -F',' '{printf "  GPU: %s\n  Memory: %.2f GB / %.2f GB\n", $1, $2/1024, $3/1024}'

    echo ""
    echo -e "${BLUE}GPU Processes (GPU 1):${NC}"
    nvidia-smi -i 1 --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits | awk -F',' '{printf "  - PID %s: %s (%.2f GB)\n", $1, $2, $3/1024}' || echo "  (no processes)"
else
    echo -e "${YELLOW}  nvidia-smi not available${NC}"
fi

# 8. 로그 파일 상태
echo ""
echo -e "${BLUE}Recent Log Files:${NC}"
if [ -f "$PROJECT_ROOT/vllm_server.log" ]; then
    SIZE=$(du -h "$PROJECT_ROOT/vllm_server.log" | cut -f1)
    MODIFIED=$(stat -c %y "$PROJECT_ROOT/vllm_server.log" | cut -d'.' -f1)
    echo -e "  - vllm_server.log: ${SIZE} (${MODIFIED})"
fi

if [ -f "$PROJECT_ROOT/frontend/langgraph_dev.log" ]; then
    SIZE=$(du -h "$PROJECT_ROOT/frontend/langgraph_dev.log" | cut -f1)
    MODIFIED=$(stat -c %y "$PROJECT_ROOT/frontend/langgraph_dev.log" | cut -d'.' -f1)
    echo -e "  - langgraph_dev.log: ${SIZE} (${MODIFIED})"
fi

if [ -f "$PROJECT_ROOT/frontend/simple_ui/simple_ui.log" ]; then
    SIZE=$(du -h "$PROJECT_ROOT/frontend/simple_ui/simple_ui.log" | cut -f1)
    MODIFIED=$(stat -c %y "$PROJECT_ROOT/frontend/simple_ui/simple_ui.log" | cut -d'.' -f1)
    echo -e "  - simple_ui.log: ${SIZE} (${MODIFIED})"
fi

# 9. 디스크 사용량
echo ""
echo -e "${BLUE}Disk Usage:${NC}"
echo -e "  Model: $(du -sh $PROJECT_ROOT/models/gpt-oss-20b 2>/dev/null | cut -f1)"
echo -e "  Data: $(du -sh $PROJECT_ROOT/data 2>/dev/null | cut -f1)"
echo -e "  Total Project: $(du -sh $PROJECT_ROOT 2>/dev/null | cut -f1)"

# 10. 요약
echo ""
echo "======================================================"
echo "📊 Summary"
echo "======================================================"

QDRANT=$(nc -z localhost 6333 2>/dev/null && echo "✅" || echo "❌")
VLLM=$(nc -z localhost 9000 2>/dev/null && echo "✅" || echo "❌")
LANGGRAPH=$(nc -z localhost 2024 2>/dev/null && echo "✅" || echo "❌")
SIMPLEUI=$(nc -z localhost 9001 2>/dev/null && echo "✅" || echo "❌")

echo -e "  Qdrant (6333):      $QDRANT"
echo -e "  vLLM (9000):        $VLLM"
echo -e "  LangGraph (2024):   $LANGGRAPH"
echo -e "  Simple UI (9001):   $SIMPLEUI"

echo ""
if [[ "$QDRANT" == "✅" && "$VLLM" == "✅" && "$LANGGRAPH" == "✅" ]]; then
    echo -e "${GREEN}🎉 All critical services are running!${NC}"
    echo ""
    echo "Access URLs:"
    echo "  - LangGraph Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"
    echo "  - Simple Web UI: http://localhost:9001"
else
    echo -e "${YELLOW}⚠️  Some services are not running. Run ./start_all.sh to start them.${NC}"
fi

echo "======================================================"
