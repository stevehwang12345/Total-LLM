# Total-LLM 프로젝트 개발 현황

> 최종 업데이트: 2026-01-16

## 프로젝트 개요

**Total-LLM**은 LLM 기반 통합 보안 모니터링 시스템으로 3가지 핵심 기술을 결합합니다:
- **Vision AI** - CCTV 이미지 분석
- **Document RAG QA** - 문서 기반 질의응답
- **Device Control** - CCTV/ACU 장치 제어

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | FastAPI + Uvicorn, Python 3.11+ |
| Frontend | React 19 + TypeScript, Tailwind CSS 4, Vite |
| LLM (Text) | vLLM + Qwen2.5-14B-Instruct-AWQ |
| LLM (Vision) | Qwen2-VL-7B-Instruct |
| Vector DB | Qdrant (384-dim BAAI/bge-small-en-v1.5) |
| RDB | PostgreSQL + asyncpg |
| Cache | Redis |
| 배포 | Docker Compose |

---

## 서비스 포트

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 9004 | React UI |
| Backend API | 9002 | FastAPI REST API |
| WebSocket | 9003 | 실시간 알림 |
| vLLM Text | 9000 | Qwen2.5-14B-AWQ |
| vLLM Vision | 9001 | Qwen2-VL-7B |
| Qdrant | 6333/6334 | 벡터 데이터베이스 |
| PostgreSQL | 5432 | 관계형 데이터베이스 |
| Redis | 6379 | 캐시 |

---

## 기능별 개발 현황 요약

| 기능 | 완료율 | 상태 |
|------|--------|------|
| Vision AI (CCTV 분석) | 95% | ✅ 프로덕션 준비 |
| RAG QA (문서 검색) | 95% | ✅ 완전 기능 |
| Device Control (장치 제어) | 85% | ⚠️ UI 구현 필요 |
| Frontend UI | 90% | ⚠️ Control 페이지 필요 |
| 인증/보안 | 80% | ⚠️ 프로덕션 강화 필요 |

---

## 1. CCTV 이미지 분석 (Vision AI) - 95% 완료

### ✅ 완료된 기능

- **VLM Analyzer 서비스** - Qwen2-VL-7B 기반 이미지 분석
- **Image API 엔드포인트** - 15+ 엔드포인트
- **Vision 모듈**:
  - IncidentDetector: 9가지 사건 유형 분류
    - 폭력, 싸움, 낙상, 침입, 위협, 이상행동, 정상, 무인, 불명확
  - SeverityLevel: 5단계 심각도
    - CRITICAL, HIGH, MEDIUM, LOW, INFO
  - 한국어 보안 QA 프롬프트 (4단계 구조화 분석)
  - 6섹션 마크다운 리포트 템플릿
- **Alarm Handler와 VLM 분석 연동**
- **Frontend 컴포넌트** (ImageAnalysis)
- **보안 리포트 파이프라인** (end-to-end)

### API 엔드포인트

```
POST /image/analyze              # 기본 이미지 분석
POST /image/analyze/upload       # 업로드 후 분석
POST /image/batch                # 배치 분석
POST /image/analyze/qa           # 4단계 QA 분석
POST /image/analyze/qa/upload    # QA 분석용 업로드
POST /image/report               # 리포트 생성
POST /image/report/security      # 전체 보안 파이프라인
GET  /image/{analysis_id}        # 분석 결과 조회
GET  /image/health               # 서비스 상태
```

### ⚠️ 부분 완료

- WebSocket 실시간 스트리밍 분석 - 아키텍처 존재, 완전 통합 필요
- 배치 분석 진행률 UI - 엔드포인트 존재, UI 피드백 제한적

### ❌ 미구현

- VLM 추론 모니터링/메트릭
- 대규모 배치 성능 최적화

---

## 2. Document RAG QA - 95% 완료

### ✅ 완료된 기능

- **Adaptive RAG** (3가지 전략):
  - Simple (복잡도 0.0-0.3): BM25만, top 3
  - Hybrid (복잡도 0.3-0.6): BM25 + Vector (70/30), top 5
  - Complex (복잡도 0.6-1.0): Multi-Query + Cross-Encoder, top 7
- **Security Chat API** - SSE 스트리밍 응답
- **Multi-Query 확장** (규칙 기반 + LLM 기반)
- **Cross-Encoder 재랭킹** (ms-marco-MiniLM-L-6-v2)
- **Frontend 컴포넌트** (Chat, Document Management)
- **Qdrant 컬렉션 분리**: `documents` vs `security_logs`
- **Function Calling 연동**

### API 엔드포인트

```
POST /api/security/chat              # SSE 스트리밍 채팅
POST /api/rag/chat                   # RAG 채팅 대안
GET  /api/rag/conversations          # 대화 기록 조회
DELETE /api/rag/conversations/{id}   # 대화 삭제
POST /documents/upload               # 문서 업로드
GET  /documents                      # 문서 목록
DELETE /documents/{id}               # 문서 삭제
```

### 지원 포맷

- PDF, DOCX, TXT, MD

### ❌ 미구현

- 대화 영속성 (현재 인메모리)
- 다국어 지원

---

## 3. 장치 제어 시스템 - 85% 완료

### ✅ 완료된 기능

- **System Controller** - Function Calling 오케스트레이터
- **CCTV Controller** - PTZ, 녹화, 프리셋, 스냅샷
- **ACU Controller** - 도어 잠금/해제, 권한, 비상 모드
- **Network Discovery** - ONVIF 프로토콜 탐색
- **Device Registry** - 장치 관리 DB
- **Credential Manager** - 암호화된 자격증명 저장 (Fernet)
- **Rate Limiter** - API 레이트 제한
- **Audit Logger** - 명령 실행 로깅
- **Control API** - 50+ 엔드포인트
- **프로토콜 어댑터**: ONVIF, Hanwha, Hikvision, ZKTeco, Suprema
- **시뮬레이션 모드** (하이브리드: 실제 + 폴백)
- **ACU 명령 롤백 메커니즘**

### API 엔드포인트

```
# 자연어 명령
POST /control/command              # 자연어 명령 실행
POST /control/function             # 직접 함수 호출
GET  /control/functions            # 사용 가능 함수 목록

# ACU (출입통제)
POST /control/acu/door/unlock      # 도어 해제
POST /control/acu/door/lock        # 도어 잠금
GET  /control/acu/door/status      # 도어 상태
GET  /control/acu/log              # 출입 로그
POST /control/acu/permission/grant # 권한 부여
POST /control/acu/permission/revoke # 권한 해제
POST /control/acu/emergency/unlock # 비상 전체 해제
POST /control/acu/emergency/lock   # 비상 전체 잠금

# CCTV (영상감시)
POST /control/cctv/camera/move     # PTZ 제어
POST /control/cctv/camera/preset   # 프리셋 이동
POST /control/cctv/recording/start # 녹화 시작
POST /control/cctv/recording/stop  # 녹화 중지
POST /control/cctv/snapshot        # 스냅샷 캡처
GET  /control/cctv/camera/status   # 카메라 상태
```

### ❌ 미구현

- **ControlPage UI** (DoorCard, CameraCard, PTZControl, CommandBar)
- 실제 장치 통합 테스트

---

## 4. Frontend UI - 90% 완료

### ✅ 구현된 페이지

| 페이지 | 경로 | 설명 |
|--------|------|------|
| Dashboard | `/` | 개요, 최근 알람, 알림 |
| Chat | `/chat` | SSE 스트리밍 RAG QA |
| Analysis | `/analysis` | 이미지 분석 결과 |
| Documents | `/documents` | 문서 관리 |
| Reports | `/reports` | PDF 리포트 생성 |
| Settings | `/settings` | 설정 |

### ❌ 미구현 페이지

| 페이지 | 경로 | 상태 |
|--------|------|------|
| **Control** | `/control` | 백엔드 API 완료, UI 컴포넌트 미완성 |

### 미구현 컴포넌트

- `ControlPage` - 메인 제어 페이지
- `DoorCard` - 도어 잠금/해제 UI
- `CameraCard` - 카메라 상태/제어
- `PTZControl` - 조이스틱 PTZ 인터페이스
- `CommandBar` - 자연어 명령 입력

---

## 5. 인증 및 보안 - 80% 완료

### ✅ 구현됨

- JWT 인증 구조
- 암호화된 자격증명 저장 (Fernet)
- 모든 장치 제어 감사 로깅
- API 레이트 제한
- CORS 설정 (개발용)

### ❌ 미구현

- 프로덕션 CORS 설정
- 세분화된 RBAC 권한 시스템
- 다중 인증 (MFA)
- OAuth2 통합

---

## 데이터베이스 스키마

### PostgreSQL 테이블

| 테이블 | 설명 |
|--------|------|
| `devices` | 장치 레지스트리 (ID, 유형, 제조사, 암호화된 자격증명, 상태) |
| `device_controls` | 제어 명령 이력 (명령, 파라미터, 상태, 롤백 정보) |
| `alarms` | 보안 알람 (유형, 심각도, 위치, VLM 분석 결과 JSONB) |
| `reports` | 생성된 보안 리포트 (제목, 유형, 분석 요약, PDF 경로) |
| `log_index` | Fluentd 로그 매핑 (Qdrant 참조) |

### Qdrant 컬렉션

| 컬렉션 | 설명 |
|--------|------|
| `documents` | 사용자 업로드 문서 (384-dim, Cosine) |
| `security_logs` | 시스템 보안 로그 (384-dim, Cosine) |

---

## 아키텍처 다이어그램

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend (React)                       │
│  Dashboard │ Chat │ Analysis │ Documents │ Reports │ Control │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP/WebSocket
┌──────────────────────────────┴───────────────────────────────┐
│                     Backend (FastAPI)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │ RAG Service │  │ VLM Analyzer│  │ Device Control      │   │
│  │ (Adaptive)  │  │ (Qwen2-VL)  │  │ (ACU/CCTV)          │   │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │
└─────────┼────────────────┼────────────────────┼──────────────┘
          │                │                    │
    ┌─────┴─────┐    ┌─────┴─────┐        ┌────┴────┐
    │  Qdrant   │    │   vLLM    │        │ Devices │
    │ (Vector)  │    │ (LLM/VLM) │        │(ACU/CCTV)│
    └───────────┘    └───────────┘        └─────────┘
          │
    ┌─────┴─────┐
    │PostgreSQL │
    │  + Redis  │
    └───────────┘
```

---

## 개발 우선순위

### 🔴 높음

1. **Control Page UI 컴포넌트 구현**
   - DoorCard, CameraCard, PTZControl, CommandBar
2. **WebSocket 실시간 알림 통합**

### 🟡 중간

1. 이미지 배치 분석 진행률 UI
2. 대화 영속성 구현 (PostgreSQL 저장)
3. 리포트 생성 UI 개선

### 🟢 낮음

1. 다국어 지원
2. MFA 인증
3. 테마 커스터마이징

---

## 실행 방법

### 1. Docker 서비스 시작

```bash
cd /home/sphwang/dev/Total-LLM
docker compose --profile with-postgres up -d
```

### 2. vLLM 서버 시작 (GPU 1)

```bash
./services/vllm/run_qwen2.5_14b.sh 1
```

### 3. 백엔드 서버 시작

```bash
cd backend
DEVICE_CREDENTIAL_KEY="your-fernet-key" \
python -m uvicorn main:app --host 0.0.0.0 --port 9002 --reload
```

### 4. 프론트엔드 서버 시작

```bash
cd frontend/react-ui
npm run dev -- --port 9004
```

### 5. 접속

- Frontend: http://localhost:9004
- Backend API: http://localhost:9002
- API Docs: http://localhost:9002/docs

---

## 관련 문서

- [MODEL_CONFIG.md](./MODEL_CONFIG.md) - LLM/VLM 모델 설정 가이드
- [INTEGRATION_DEVELOPMENT_GUIDE.md](./INTEGRATION_DEVELOPMENT_GUIDE.md) - 통합 개발 가이드
- [INTEGRATED_WBS.md](./INTEGRATED_WBS.md) - 작업 분류 체계
