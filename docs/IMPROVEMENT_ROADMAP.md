# Total-LLM 프로젝트 Phase별 개선 계획

> 작성일: 2026-02-05
> 프로젝트 경로: `/home/sphwang/dev/Total-LLM`
> 현재 완성도: **~95%** ✅ (Phase 1-5 완료, Phase 3 스킵)

---

## 핵심 시나리오 플로우 현황

### 1. Vision AI Flow (98% ✅)
```
User Upload → Frontend → /image/analyze → VLM (Qwen2.5-VL-7B, port 9001)
→ Incident Detection (9종) → Severity 분류 → PostgreSQL 저장
→ WebSocket Alert → Dashboard 표시
```
**상태**: 전체 플로우 동작, VLM 업그레이드 완료 | **Gap**: 비디오 분석 추가 (선택)

### 2. RAG QA Flow (95% ✅)
```
User Question → Frontend → /api/security/chat → Adaptive Retriever
→ Qdrant Vector Search + BM25 → LangGraph (4 Nodes)
→ vLLM (Qwen2.5-14B, port 9000) → SSE Stream → Frontend 표시
```
**상태**: 전체 플로우 동작 | **Gap**: 캐싱 레이어, 대화 지속성

### 3. Device Control Flow (85% ⚠️)
```
Natural Language → Frontend → /control/command → LLM Function Calling
→ SystemController → ACU/CCTV Controller → Device API/ONVIF
→ Physical Device → Audit Log → WebSocket Broadcast → Dashboard
```
**상태**: Backend 완성, **Frontend UI 누락** | **Gap**: Control Page 전체

---

## 현재 상태 요약 (2026-02-05 검증 → 업데이트)

| 영역 | 완성도 | 플로우 상태 |
|------|--------|------------|
| Vision AI (CCTV 분석) | **98%** | ✅ **Qwen2.5-VL 업그레이드 완료** |
| Document RAG QA | **98%** | ✅ **캐싱 + 대화 지속성 완료** |
| Device Control | **95%** | ✅ **Backend + Frontend 모두 완성** |
| Frontend UI | **90%** | ✅ **Control 페이지 완전 구현** |
| Auth/Security | 80% | ⚠️ JWT만 구현 (Phase 3 스킵) |

### Control UI 구현 현황 (검증됨)
- ✅ ControlPage.tsx - 7개 탭 (command, acu, cctv, network, zone, audit, ratelimit)
- ✅ CommandBar.tsx - 자연어 명령 입력, 기기 목록 패널, 명령 기록
- ✅ DoorCard.tsx - 상태 표시, 잠금/해제, 출입 기록
- ✅ PTZControl.tsx - 8방향 조이스틱, 줌, 프리셋, 녹화
- ✅ controlApi.ts - 1,200+ 줄, 전체 API 연동 완료

---

## Phase 1: Device Control UI ✅ 완료

> **상태**: 2026-02-05 검증 완료 - 모든 UI 컴포넌트가 이미 구현되어 있음

### 구현된 컴포넌트
| 컴포넌트 | 파일 | 기능 |
|---------|------|------|
| ControlPage | `pages/ControlPage.tsx` | 7개 탭 네비게이션 |
| CommandBar | `components/Control/CommandBar.tsx` | 자연어 명령, 기기 목록, 명령 기록 |
| DoorCard | `components/Control/DoorCard.tsx` | 상태 표시, 잠금/해제, 출입 기록 |
| DoorGrid | `components/Control/DoorGrid.tsx` | 출입문 그리드 뷰 |
| CameraCard | `components/Control/CameraCard.tsx` | 카메라 상태, 프리뷰 |
| CameraGrid | `components/Control/CameraGrid.tsx` | 카메라 그리드 뷰 |
| PTZControl | `components/Control/PTZControl.tsx` | 8방향 조이스틱, 줌, 프리셋, 녹화 |
| NetworkDiscovery | `components/Control/NetworkDiscovery.tsx` | ONVIF 장치 탐색 |
| ZoneListPanel | `components/Control/ZoneListPanel.tsx` | 구역 관리 |
| AuditLogPanel | `components/Control/AuditLogPanel.tsx` | 감사 로그 |
| RateLimitPanel | `components/Control/RateLimitPanel.tsx` | Rate Limit 현황 |
| controlApi.ts | `services/controlApi.ts` | 1,200+ 줄 API 연동 |

---

## Phase 2: RAG 플로우 최적화 ✅ 완료

> **상태**: 2026-02-05 구현 완료

### 구현된 기능

#### 2.1 RAG 응답 캐싱 ✅
- **파일**: `backend/services/cache_service.py` (신규)
- Redis 기반 쿼리-응답 캐싱
- 캐시 키: `rag:{query_hash}:{retriever_type}`
- TTL: 1시간 (config.yaml에서 설정 가능)
- RAG 서비스 통합: `backend/services/rag_service.py` 수정

#### 2.2 대화 지속성 (PostgreSQL) ✅
- **파일**: `backend/services/conversation_service.py` (신규)
- 대화 세션 저장/복원
- 컨텍스트 윈도우 관리 (최근 5턴)
- **스키마**: `backend/database/schema.sql`에 `conversations`, `conversation_messages` 테이블 추가

#### 2.3 Chat API 통합 ✅
- **파일**: `backend/api/security_chat_api.py` 수정
- `conversation_id` 파라미터 지원
- 대화 관리 API 엔드포인트 추가:
  - `GET /api/security/conversations` - 대화 목록
  - `GET /api/security/conversations/{id}` - 대화 조회
  - `GET /api/security/conversations/{id}/messages` - 메시지 조회
  - `DELETE /api/security/conversations/{id}` - 대화 삭제
  - `POST /api/security/conversations/{id}/close` - 대화 종료
  - `GET /api/security/conversations/stats` - 통계 조회

#### 2.4 설정 추가 ✅
- **파일**: `backend/config/config.yaml`
- Redis 설정 섹션 추가 (host, port, TTL 등)

### 신규 파일 목록
```
backend/services/
├── cache_service.py            # Redis 캐싱 서비스
└── conversation_service.py     # 대화 지속성 서비스

backend/database/
└── schema.sql                  # conversations, conversation_messages 테이블 추가
```

### 검증 방법
```bash
# 캐싱 확인
redis-cli KEYS "rag:*"

# 성능 테스트 (동일 쿼리 2회)
time curl -X POST http://localhost:9002/api/security/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "CCTV 설치 기준이 뭐야?"}'
# 2회차 응답 시간 50%+ 감소 확인

# 대화 지속성 테스트
# 1. 첫 번째 이벤트에서 conversation_id 확인
# 2. 같은 conversation_id로 후속 질문
curl -X POST http://localhost:9002/api/security/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "추가 질문", "conversation_id": "<id>"}'

# 대화 목록 조회
curl http://localhost:9002/api/security/conversations?user_id=anonymous
```

### 남은 작업 (Phase 2.5)
- [ ] 소스 문서 미리보기 UI (Frontend)
- [ ] 테스트 커버리지 확대 (60% → 75%)

---

## Phase 3: 인증 및 보안 강화 (5-6주)

### 목표
프로덕션 보안 수준 달성 (80% → 95%)

### 플로우별 보안 적용
```
[Vision] 이미지 업로드 → 파일 검증, 크기 제한
[RAG] 문서 업로드 → 악성 파일 스캔
[Control] 장치 제어 → RBAC 권한 검증, 감사 로그
```

### 작업 항목

#### 3.1 JWT 인증 강화
- Refresh Token Rotation
- Token Blacklist (로그아웃/탈취 시)

#### 3.2 RBAC 권한 시스템
- **파일**: `backend/services/rbac_service.py` (신규)
- 역할: `admin`, `operator`, `viewer`
- Device Control: `operator` 이상만 허용
- 문서 삭제: `admin`만 허용

#### 3.3 보안 헤더 적용
- **파일**: `backend/main.py`
- CSP, X-Frame-Options, HSTS

#### 3.4 Rate Limiting 강화
- Control 명령: 30회/분
- 이미지 분석: 10회/분
- 문서 업로드: 5회/분

### 검증 방법
```bash
# RBAC 테스트
curl -X POST http://localhost:9002/control/command \
  -H "Authorization: Bearer {viewer_token}" \
  -d '{"command": "문 열어"}'
# 403 Forbidden 확인

# Rate Limit 테스트
for i in {1..35}; do curl -X POST .../control/command; done
# 31번째부터 429 Too Many Requests 확인
```

---

## Phase 4: Vision AI 업그레이드 ✅ 완료

> **상태**: 2026-02-05 설정 업데이트 완료

### 목표
VLM 성능 향상, 분석 정확도 개선

### 완료된 작업

#### 4.1 Qwen2.5-VL 업그레이드 ✅
- **파일**: `backend/config/config.yaml`
- 모델 변경: `Qwen/Qwen2-VL-7B-Instruct` → `Qwen/Qwen2.5-VL-7B-Instruct`
- 성능 향상: GPT-4o-mini 수준

### vLLM 서버 배포 방법
```bash
# 1. 기존 VLM 서버 중지
docker stop vllm-qwen2-vl

# 2. 새 모델로 vLLM 서버 시작
docker run -d --gpus all \
  -p 9001:8000 \
  --name vllm-qwen25-vl \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-VL-7B-Instruct \
  --dtype auto \
  --max-model-len 4096

# 3. 기존 모델 삭제 (선택)
rm -rf ~/.cache/huggingface/hub/models--Qwen--Qwen2-VL-7B-Instruct

# 4. 버전 확인
curl http://localhost:9001/v1/models
```

### 남은 작업 (선택)
- [ ] 비디오 분석 지원 (프레임 샘플링, 타임라인 기반 이벤트 감지)
- [ ] 배치 분석 진행률 UI

### 검증 방법
```bash
# VLM 버전 확인
curl http://localhost:9001/v1/models
# 응답: {"data": [{"id": "Qwen/Qwen2.5-VL-7B-Instruct", ...}]}

# 이미지 분석 테스트
curl -X POST http://localhost:9002/image/analyze \
  -F "file=@test_image.jpg" \
  -F "location=테스트"
```

---

## Phase 5: 모니터링 및 DevOps ✅ 완료

> **상태**: 2026-02-05 구현 완료

### 목표
운영 가시성 확보, 자동화된 배포

### 완료된 작업

#### 5.1 구조화된 로깅 ✅
- **파일**: `backend/utils/logging_config.py` (신규)
- JSON 형식 로거 (`JSONFormatter`)
- 개발용 컬러 콘솔 포매터 (`ColoredConsoleFormatter`)
- 요청 추적 컨텍스트 (`trace_id`, `user_id`)
- ELK 스택 연동 준비 완료

#### 5.2 요청 추적 미들웨어 ✅
- **파일**: `backend/middleware/tracing.py` (신규)
- `TracingMiddleware` - 요청별 trace_id 생성/전파
- `X-Trace-ID` 헤더 지원
- 요청/응답 시간 측정 및 로깅

#### 5.3 확장 Health 모니터링 ✅
- **파일**: `backend/services/health_service.py` (신규)
- 의존성 상태 체크 (Qdrant, Redis, PostgreSQL, vLLM, VLM)
- 시스템 리소스 모니터링 (CPU, Memory, Disk)
- `/health/full` 상세 진단 엔드포인트

#### 5.4 CI/CD 파이프라인 ✅
- **파일**: `.github/workflows/ci.yml` (신규)
- Backend 테스트 (pytest, coverage)
- Frontend 테스트 및 빌드
- Security 스캔 (bandit, safety)
- Docker 이미지 빌드
- 배포 준비 (production environment)

### 신규 파일 목록
```
backend/
├── utils/
│   ├── __init__.py
│   └── logging_config.py       # 구조화된 로깅
├── middleware/
│   ├── __init__.py
│   └── tracing.py              # 요청 추적 미들웨어
└── services/
    └── health_service.py       # 확장 헬스 체크

.github/
└── workflows/
    └── ci.yml                  # CI/CD 파이프라인
```

### 사용 방법

```python
# main.py에서 구조화된 로깅 활성화
from utils.logging_config import setup_logging, get_logging_config_from_env

config = get_logging_config_from_env()
setup_logging(**config)

# 미들웨어 추가
from middleware import TracingMiddleware
app.add_middleware(TracingMiddleware)

# 확장 헬스 체크
from services.health_service import get_health_service
health_service = get_health_service()

@app.get("/health/full")
async def health_full():
    return await health_service.get_full_health(app.state)
```

### 환경변수 설정
```bash
# 로깅 설정
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json         # json 또는 console
LOG_FILE=/var/log/app.log  # 선택

# 환경
ENVIRONMENT=production  # development, production
APP_VERSION=1.0.0
```

---

## 우선순위 매트릭스

| Phase | 플로우 영향 | 비즈니스 가치 | 상태 |
|-------|-----------|--------------|------|
| **Phase 1** | ~~Device Control UI~~ | 높음 | ✅ **완료** (이미 구현됨) |
| **Phase 2** | ~~성능 개선~~ | 높음 | ✅ **완료** (캐싱 + 대화 지속성) |
| **Phase 3** | ~~보안~~ | 높음 | ⏭️ **스킵** |
| **Phase 4** | ~~Vision AI 업그레이드~~ | 중간 | ✅ **완료** (Qwen2.5-VL) |
| **Phase 5** | ~~모니터링/DevOps~~ | 중간 | ✅ **완료** (로깅 + CI/CD) |

---

## 핵심 파일 목록 (플로우 기준)

### Phase 1 - Device Control UI (신규 생성)
```
frontend/react-ui/src/
├── pages/ControlPage.tsx              # 메인 페이지
├── components/Control/
│   ├── CommandBar.tsx                 # 자연어 입력
│   ├── DeviceList.tsx                 # 장치 목록
│   ├── DoorCard.tsx                   # ACU 제어
│   ├── CameraCard.tsx                 # CCTV 표시
│   └── PTZControl.tsx                 # PTZ 조이스틱
├── hooks/useDeviceStatus.ts           # WebSocket 훅
└── services/controlApi.ts             # API 확장
```

### Phase 2 - RAG 최적화 ✅ (완료)
```
backend/services/
├── rag_service.py                     # ✅ 캐싱 추가 완료
├── cache_service.py                   # ✅ 신규: Redis 캐싱
└── conversation_service.py            # ✅ 신규: 대화 지속성

backend/api/
└── security_chat_api.py               # ✅ 대화 관리 API 추가

backend/config/
└── config.yaml                        # ✅ Redis 설정 추가

backend/database/
└── schema.sql                         # ✅ conversations 테이블 추가
```

### Phase 3 - 보안 (신규/수정)
```
backend/
├── main.py                            # 보안 헤더
├── services/auth_service.py           # JWT 강화
└── services/rbac_service.py           # 신규: RBAC
```

### Phase 4 - Vision (수정)
```
backend/services/
└── vlm_analyzer.py                    # Qwen2.5-VL
```

---

## 참고: API 엔드포인트 매핑

| 플로우 단계 | 엔드포인트 | UI 컴포넌트 |
|------------|-----------|-------------|
| Vision 업로드 | `POST /image/analyze` | ImageUploader ✅ |
| Vision 결과 | `GET /image/results/{id}` | AnalysisResult ✅ |
| RAG 질의 | `POST /api/security/chat` | ChatInput ✅ |
| RAG 스트림 | SSE | ChatMessage ✅ |
| 문서 업로드 | `POST /upload` | DocumentUploader ✅ |
| **장치 명령** | `POST /control/command` | **CommandBar** ❌ |
| **도어 제어** | `POST /control/acu/door/*` | **DoorCard** ❌ |
| **카메라 제어** | `POST /control/cctv/camera/*` | **PTZControl** ❌ |

---

## 참고 자료

- [프로젝트 시나리오 문서](PROJECT_SUMMARY.md)
- [API 레퍼런스](API_REFERENCE.md)
- [vLLM Qwen 배포](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)
- [Qwen2.5-VL 릴리스](https://qwenlm.github.io/blog/qwen2.5-vl/)
- [React 19 Features](https://react.dev/blog/2025/10/01/react-19-2)
