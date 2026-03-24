# Total-LLM

**LLM 기반 통합 보안 모니터링 시스템**

Vision 분석, 문서 RAG QA, 자연어 장치 제어를 통합한 AI 보안 플랫폼

---

## 주요 기능

### 1. CCTV 이미지 분석 (Vision AI)
- Qwen2-VL-7B 기반 영상 분석
- 9가지 사고 유형 자동 분류 (폭력, 싸움, 낙상, 침입 등)
- 심각도 레벨 및 신뢰도 점수
- 보안 보고서 자동 생성

### 2. 문서 RAG QA
- Adaptive 검색 전략 (Simple/Hybrid/Complex)
- Multi-Query 확장 및 Cross-Encoder 재순위화
- BM25 + 벡터 하이브리드 검색
- SSE 스트리밍 응답
- PDF, DOCX, TXT, MD 문서 지원

### 3. 장치 제어 (CCTV/ACU)
- 자연어 명령 → LLM Function Calling
- CCTV PTZ 제어, 녹화, 프리셋, 스냅샷
- ACU 출입문 잠금/해제, 출입 권한 관리
- ONVIF 프로토콜 기반 자동 장치 탐색
- 암호화된 인증정보 관리

---

## 기술 스택

### Backend
- **Framework**: FastAPI + Uvicorn
- **LLM**: vLLM (Qwen2.5-14B-AWQ, Qwen2-VL-7B)
- **Vector DB**: Qdrant
- **Database**: PostgreSQL + asyncpg
- **Cache**: Redis
- **Embedding**: BAAI/bge-small-en-v1.5

### Frontend
- **Framework**: React 19 + TypeScript + Vite
- **Styling**: Tailwind CSS 4
- **State**: Zustand
- **Data Fetching**: TanStack React Query v5
- **Routing**: React Router v7

### Infrastructure
- Docker Compose 기반 컨테이너 배포
- WebSocket 실시간 알림 (Port 9003)

---

## 빠른 시작

### 사전 요구사항
- Docker & Docker Compose
- NVIDIA GPU (CUDA 지원)
- Python 3.11+
- Node.js 18+

### 1. 저장소 클론
```bash
git clone https://github.com/your-org/Total-LLM.git
cd Total-LLM
```

### 2. 환경 설정
```bash
cp .env.example .env
# .env 파일 편집하여 필요한 설정 수정
```

### 3. 인프라 서비스 시작
```bash
# 필수 서비스 (Qdrant, Redis, PostgreSQL)
docker compose --profile with-postgres up -d
```

### 4. vLLM 서버 시작
```bash
# 텍스트 LLM (GPU 1)
cd backend/services/vllm
./run_vllm.sh
```

### 5. 백엔드 서버 시작
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 9002 --reload
```

### 6. 프론트엔드 개발 서버 시작
```bash
cd frontend/react-ui
npm install
npm run dev -- --port 9004
```

### 7. 접속
- **Frontend**: http://localhost:9004
- **Backend API**: http://localhost:9002
- **API Docs**: http://localhost:9002/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

---

## 서비스 포트

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 9004 | React UI |
| Backend API | 9002 | FastAPI REST API |
| WebSocket | 9003 | 실시간 알림 |
| vLLM (Text) | 9000 | Qwen2.5-14B-AWQ |
| vLLM (Vision) | 9001 | Qwen2-VL-7B |
| Qdrant | 6333/6334 | Vector DB |
| PostgreSQL | 5432 | 관계형 DB |
| Redis | 6379 | 캐시 |

---

## 프로젝트 구조

```
Total-LLM/
├── backend/
│   ├── api/                    # FastAPI 라우터
│   ├── services/               # 비즈니스 로직
│   │   ├── control/            # 장치 제어 서브시스템
│   │   ├── vision/             # VLM 분석
│   │   └── api_generator/      # API 코드 생성기
│   ├── retrievers/             # RAG 검색기
│   ├── tools/                  # LangChain 도구
│   ├── core/                   # 핵심 유틸리티
│   ├── config/                 # 설정 파일
│   ├── database/               # DB 스키마
│   └── tests/                  # 테스트
├── frontend/
│   └── react-ui/
│       ├── src/
│       │   ├── pages/          # 페이지 컴포넌트
│       │   ├── components/     # UI 컴포넌트
│       │   ├── services/       # API 클라이언트
│       │   ├── stores/         # Zustand 스토어
│       │   └── types/          # TypeScript 타입
│       └── public/
├── docs/                       # 프로젝트 문서
├── data/                       # 데이터 저장소
└── docker-compose.yml
```

---

## 문서

| 문서 | 설명 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 시스템 아키텍처 |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | API 명세서 |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | 배포 가이드 |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | 개발 환경 설정 |
| [INTEGRATION_STATUS.md](docs/INTEGRATION_STATUS.md) | 통합 현황 |

---

## API 개요

### RAG 채팅
```bash
# SSE 스트리밍 채팅
curl -X POST http://localhost:9002/api/security/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "CCTV 설치 기준에 대해 알려줘", "conversation_id": "conv-001"}'
```

### 이미지 분석
```bash
# 이미지 업로드 및 분석
curl -X POST http://localhost:9002/image/analyze \
  -F "file=@image.jpg" \
  -F "location=로비"
```

### 장치 제어
```bash
# 자연어 명령
curl -X POST http://localhost:9002/control/command \
  -H "Content-Type: application/json" \
  -d '{"command": "1번 카메라 왼쪽으로 30도 이동"}'
```

---

## 개발 상태

| 기능 | 완성도 | 상태 |
|------|--------|------|
| Vision 이미지 분석 | 95% | 프로덕션 준비 완료 |
| 문서 RAG QA | 95% | 프로덕션 준비 완료 |
| 장치 제어 | 85% | 실제 장치 테스트 필요 |
| 프론트엔드 UI | 90% | 기능 완료, 세부 개선 중 |
| 인증/보안 | 80% | JWT 구현, RBAC 추가 예정 |

---

## 라이선스

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 기여

기여를 환영합니다! [CONTRIBUTING.md](CONTRIBUTING.md)를 참조해주세요.
