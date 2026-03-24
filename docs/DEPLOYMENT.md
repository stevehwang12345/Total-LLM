# Total-LLM Deployment Guide

이 문서는 Total-LLM 시스템의 배포 가이드입니다.

---

## 목차

1. [사전 요구사항](#사전-요구사항)
2. [환경 설정](#환경-설정)
3. [로컬 개발 환경](#로컬-개발-환경)
4. [Docker 배포](#docker-배포)
5. [vLLM 서버 설정](#vllm-서버-설정)
6. [프로덕션 배포](#프로덕션-배포)
7. [모니터링](#모니터링)
8. [백업 및 복구](#백업-및-복구)
9. [트러블슈팅](#트러블슈팅)

---

## 사전 요구사항

### 하드웨어

| 구성요소 | 최소 사양 | 권장 사양 |
|---------|----------|----------|
| CPU | 8 cores | 16+ cores |
| RAM | 32GB | 64GB+ |
| GPU | 1x RTX 3090 (24GB) | 2x RTX 4000 Ada (16GB each) |
| Storage | 100GB SSD | 500GB+ NVMe SSD |

### 소프트웨어

| 소프트웨어 | 버전 |
|-----------|------|
| Ubuntu | 22.04 LTS |
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| NVIDIA Driver | 535+ |
| CUDA | 12.1+ |
| Python | 3.11+ |
| Node.js | 18+ |

### GPU 구성 권장

```
GPU 0 (RTX 4000 Ada 16GB): Vision Model (Qwen2-VL-7B)
GPU 1 (RTX 4000 Ada 16GB): Text LLM (Qwen2.5-14B-AWQ)
```

---

## 환경 설정

### 1. 저장소 클론

```bash
git clone https://github.com/your-org/Total-LLM.git
cd Total-LLM
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env
```

### 3. 필수 환경 변수 편집

```bash
nano .env
```

**필수 변경 항목**:

```bash
# 데이터베이스 비밀번호 (강력한 비밀번호 사용)
POSTGRES_PASSWORD=your_strong_password_here

# 장치 인증 암호화 키 (Fernet 키 생성)
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DEVICE_CREDENTIAL_KEY=your_fernet_key_here

# JWT 비밀 키 (프로덕션용)
# openssl rand -hex 32
JWT_SECRET_KEY=your_jwt_secret_here
```

### 4. 데이터 디렉토리 생성

```bash
mkdir -p data/{qdrant_storage,redis_data,postgres_data,uploads,logs,reports}
```

---

## 로컬 개발 환경

빠른 개발 테스트를 위한 로컬 실행 방법입니다.

### 1. 인프라 서비스 시작

```bash
# PostgreSQL 포함 전체 서비스
docker compose --profile with-postgres up -d

# 또는 기본 서비스만 (Qdrant, Redis)
docker compose up -d qdrant redis
```

### 2. 서비스 상태 확인

```bash
docker compose ps
```

예상 출력:
```
NAME                    STATUS          PORTS
total-llm-qdrant        Up (healthy)    0.0.0.0:6333-6334->6333-6334/tcp
total-llm-redis         Up (healthy)    0.0.0.0:6379->6379/tcp
total-llm-postgres      Up (healthy)    0.0.0.0:5432->5432/tcp
```

### 3. vLLM 서버 시작

```bash
cd services/vllm
./run_vllm.sh
```

### 4. 백엔드 서버 시작

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 9002 --reload
```

### 5. 프론트엔드 개발 서버 시작

```bash
cd frontend/react-ui
npm install
npm run dev -- --port 9004
```

### 6. 접속 확인

| 서비스 | URL |
|--------|-----|
| Frontend | http://localhost:9004 |
| Backend API | http://localhost:9002 |
| API Docs | http://localhost:9002/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |

---

## Docker 배포

Docker Compose를 사용한 전체 스택 배포입니다.

### 서비스 구성

```yaml
services:
  frontend:      # React UI (Nginx)
  backend:       # FastAPI 백엔드
  qdrant:        # 벡터 데이터베이스
  redis:         # 캐시
  postgres:      # 관계형 DB (선택적)
```

### 기본 배포

```bash
# 전체 빌드 및 배포
docker compose up -d --build

# 로그 확인
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f backend
```

### PostgreSQL 포함 배포

```bash
docker compose --profile with-postgres up -d --build
```

### 서비스별 재시작

```bash
# 백엔드만 재시작
docker compose restart backend

# 전체 재시작
docker compose restart
```

### 서비스 중지

```bash
# 서비스만 중지 (데이터 유지)
docker compose down

# 볼륨 포함 삭제 (주의: 데이터 삭제됨)
docker compose down -v
```

---

## vLLM 서버 설정

vLLM은 GPU 자원 관리를 위해 Docker Compose와 별도로 실행합니다.

### 모델 다운로드

#### 옵션 1: Qwen2.5-14B-AWQ (권장)

```bash
# Hugging Face CLI로 다운로드
pip install huggingface_hub
huggingface-cli download Qwen/Qwen2.5-14B-Instruct-AWQ \
  --local-dir ./models/qwen2.5-14b-awq
```

#### 옵션 2: 커스텀 모델

```bash
# 모델 경로 수정
export MODEL_PATH=/path/to/your/model
```

### vLLM Docker 실행

```bash
# GPU 1에서 실행
docker run --rm -d \
    --gpus '"device=1"' \
    --name vllm-qwen2.5-14b \
    --network total-llm-network \
    -v /path/to/models:/models \
    -p 9000:9000 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model /models/qwen2.5-14b-awq \
    --dtype auto \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 \
    --port 9000 \
    --host 0.0.0.0
```

### VLM (Vision) 서버 실행

```bash
# GPU 0에서 실행
docker run --rm -d \
    --gpus '"device=0"' \
    --name vllm-qwen2-vl \
    --network total-llm-network \
    -v /path/to/models:/models \
    -p 9001:9001 \
    --ipc=host \
    vllm/vllm-openai:latest \
    --model Qwen/Qwen2-VL-7B-Instruct \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 2048 \
    --port 9001 \
    --host 0.0.0.0
```

### vLLM 연결 확인

```bash
# 모델 목록 확인
curl http://localhost:9000/v1/models

# 테스트 요청
curl http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/models/qwen2.5-14b-awq",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'
```

---

## 프로덕션 배포

### 체크리스트

- [ ] 환경 변수에서 `DEBUG=false` 설정
- [ ] 강력한 데이터베이스 비밀번호 설정
- [ ] Fernet 암호화 키 생성 및 설정
- [ ] JWT 비밀 키 생성 및 설정
- [ ] CORS 오리진을 특정 도메인으로 제한
- [ ] HTTPS/TLS 설정 (Nginx 리버스 프록시)
- [ ] 방화벽 규칙 설정
- [ ] 자동 백업 스크립트 구성
- [ ] 모니터링 시스템 연동 (Sentry, Prometheus)

### Nginx 리버스 프록시 설정

```nginx
# /etc/nginx/sites-available/total-llm
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:9004;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:9002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 지원
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://localhost:9003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### SSL 인증서 설정 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d your-domain.com

# 자동 갱신 확인
sudo certbot renew --dry-run
```

### 방화벽 설정

```bash
# UFW 방화벽 설정
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# 내부 서비스 포트는 외부 차단
# 9000, 9001, 9002, 6333, 6379, 5432는 localhost만 접근
```

### Systemd 서비스 등록

```bash
# /etc/systemd/system/total-llm.service
[Unit]
Description=Total-LLM Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/Total-LLM
ExecStart=/usr/bin/docker compose --profile with-postgres up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 등록 및 활성화
sudo systemctl daemon-reload
sudo systemctl enable total-llm
sudo systemctl start total-llm
```

---

## 모니터링

### 헬스 체크 엔드포인트

| 서비스 | 엔드포인트 |
|--------|----------|
| Backend | `GET /health` |
| Security Chat | `GET /api/security/health` |
| Control | `GET /control/health` |
| Image Analysis | `GET /image/health` |
| Alarm | `GET /api/alarms/health` |
| Device | `GET /api/devices/health` |
| System | `GET /system/status` |

### 로그 확인

```bash
# Docker 로그
docker compose logs -f --tail=100 backend

# 애플리케이션 로그
tail -f data/logs/app.log
```

### Sentry 연동 (선택적)

```bash
# .env에 추가
SENTRY_DSN=https://your-sentry-dsn
SENTRY_ENVIRONMENT=production
```

### Prometheus 메트릭 (향후 지원)

```bash
# /metrics 엔드포인트 활성화
# prometheus.yml에서 scrape 설정
```

---

## 백업 및 복구

### 자동 백업 스크립트

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR=/opt/backups/total-llm
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# PostgreSQL 백업
docker exec total-llm-postgres pg_dump -U total_llm total_llm | \
  gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Qdrant 스냅샷
curl -X POST "http://localhost:6333/collections/documents/snapshots" | \
  jq -r '.result.name' > $BACKUP_DIR/qdrant_snapshot_$DATE.txt

# Redis RDB 백업
docker exec total-llm-redis redis-cli BGSAVE
cp data/redis_data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# 업로드 파일 백업
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz data/uploads/

# 30일 이상 된 백업 삭제
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

### Cron 설정

```bash
# crontab -e
# 매일 새벽 3시 백업
0 3 * * * /opt/Total-LLM/scripts/backup.sh >> /var/log/total-llm-backup.log 2>&1
```

### 복구 절차

```bash
# PostgreSQL 복구
gunzip < postgres_20260116.sql.gz | \
  docker exec -i total-llm-postgres psql -U total_llm total_llm

# Qdrant 복구
# 스냅샷에서 컬렉션 복원
curl -X PUT "http://localhost:6333/collections/documents/snapshots/{snapshot_name}/recover"

# Redis 복구
docker stop total-llm-redis
cp redis_backup.rdb data/redis_data/dump.rdb
docker start total-llm-redis

# 업로드 파일 복구
tar -xzf uploads_20260116.tar.gz -C data/
```

---

## 트러블슈팅

### 일반적인 문제

#### Docker Compose 시작 실패

```bash
# 로그 확인
docker compose logs

# 컨테이너 상태 확인
docker compose ps -a

# 네트워크 재생성
docker network rm total-llm-network
docker compose up -d
```

#### vLLM GPU 메모리 부족

```bash
# GPU 메모리 확인
nvidia-smi

# 메모리 사용률 낮추기
--gpu-memory-utilization 0.75

# 컨텍스트 길이 줄이기
--max-model-len 2048
```

#### 백엔드 데이터베이스 연결 실패

```bash
# PostgreSQL 상태 확인
docker compose logs postgres

# 연결 테스트
docker exec -it total-llm-postgres psql -U total_llm -c "SELECT 1"

# 환경 변수 확인
echo $POSTGRES_PASSWORD
```

#### Qdrant 컬렉션 없음

```bash
# 컬렉션 목록 확인
curl http://localhost:6333/collections

# 컬렉션 생성 (백엔드 시작 시 자동 생성됨)
curl -X PUT http://localhost:6333/collections/documents \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 384, "distance": "Cosine"}}'
```

#### 프론트엔드 API 연결 실패

```bash
# CORS 설정 확인
# .env의 CORS_ORIGINS 확인

# 네트워크 연결 확인
docker network inspect total-llm-network

# 프록시 설정 확인 (vite.config.ts)
```

### 로그 레벨 조정

```bash
# 디버그 로그 활성화
export LOG_LEVEL=DEBUG
docker compose restart backend
```

### 서비스 완전 재시작

```bash
# 모든 서비스 중지 및 볼륨 삭제
docker compose down -v

# 이미지 재빌드 및 시작
docker compose up -d --build --force-recreate
```

---

## 서비스 포트 요약

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 9004 | React UI (Nginx) |
| Backend | 9002 | FastAPI REST API |
| WebSocket | 9003 | 실시간 알림 |
| vLLM (Text) | 9000 | Qwen2.5-14B-AWQ |
| vLLM (Vision) | 9001 | Qwen2-VL-7B |
| Qdrant HTTP | 6333 | 벡터 DB REST API |
| Qdrant gRPC | 6334 | 벡터 DB gRPC |
| PostgreSQL | 5432 | 관계형 DB |
| Redis | 6379 | 캐시 |

---

*Last Updated: 2026-01-16*
