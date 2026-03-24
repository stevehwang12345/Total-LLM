#!/bin/bash

# Security Monitoring System Backend Start Script

echo "🚀 Starting Security Monitoring System Backend..."

# Activate conda environment
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate vllm-security

# Change to backend directory
cd /home/sphwang/dev/vLLM/backend

# Check services
echo "📊 Checking services..."

# Check PostgreSQL
if docker exec dify-db psql -U vllm_user -d security_monitoring -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ PostgreSQL is running"
else
    echo "❌ PostgreSQL is not accessible"
    exit 1
fi

# Check Qdrant
if curl -s http://localhost:6333/collections > /dev/null; then
    echo "✅ Qdrant is running"
else
    echo "❌ Qdrant is not running"
    echo "   Start with: docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest"
    exit 1
fi

# Check Kafka
if docker ps | grep vllm-kafka > /dev/null; then
    echo "✅ Kafka is running"
else
    echo "❌ Kafka is not running"
    echo "   Start with: cd kafka && docker compose up -d"
    exit 1
fi

# Check vLLM (optional)
if curl -s http://localhost:9000/v1/models > /dev/null 2>&1; then
    echo "✅ vLLM server is running"
else
    echo "⚠️ vLLM server is not running (optional - chat will not work)"
fi

echo ""
echo "🎯 Starting FastAPI server..."
echo "   API: http://localhost:9002"
echo "   WebSocket: ws://localhost:9003"
echo ""

# Run FastAPI
python main.py
