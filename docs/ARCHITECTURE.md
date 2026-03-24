# Total-LLM 시스템 아키텍처

## 목차
1. [개요](#개요)
2. [시스템 구성도](#시스템-구성도)
3. [계층 구조](#계층-구조)
4. [백엔드 아키텍처](#백엔드-아키텍처)
5. [프론트엔드 아키텍처](#프론트엔드-아키텍처)
6. [데이터 흐름](#데이터-흐름)
7. [외부 서비스 연동](#외부-서비스-연동)
8. [보안 아키텍처](#보안-아키텍처)

---

## 개요

Total-LLM은 LLM 기반 통합 보안 모니터링 시스템으로, 세 가지 핵심 기능을 제공합니다:
- **Vision AI**: CCTV 영상 분석 및 사고 감지
- **RAG QA**: 문서 기반 질의응답
- **Device Control**: 자연어 기반 장치 제어

---

## 시스템 구성도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Total-LLM Platform                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     Frontend Layer (React 19 + TypeScript)               │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │ │
│  │  │Dashboard │  │   Chat   │  │ Analysis │  │ Control  │  │Documents │  │ │
│  │  │   Page   │  │   Page   │  │   Page   │  │   Page   │  │   Page   │  │ │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │ │
│  │       └──────────────┴──────────────┴──────────────┴──────────────┘       │ │
│  │                                    │                                       │ │
│  │                           [API Services Layer]                            │ │
│  │                    Zustand State | React Query Cache                      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                       │
│                    HTTP/REST (9002) │ WebSocket (9003) │ SSE                  │
│                                       │                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     Backend Layer (FastAPI + Python)                     │ │
│  │                                                                           │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │ │
│  │  │                         API Routers (10)                           │   │ │
│  │  │  security_chat │ control │ image │ document │ alarm │ device │ ... │   │ │
│  │  └───────────────────────────────────────────────────────────────────┘   │ │
│  │                                    │                                       │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │ │
│  │  │                       Services Layer (11+)                         │   │ │
│  │  │                                                                     │   │ │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │ │
│  │  │  │ RAG Service │  │VLM Analyzer │  │System Ctrl  │               │   │ │
│  │  │  │             │  │             │  │             │               │   │ │
│  │  │  │ -Adaptive   │  │ -Qwen2-VL   │  │ -CCTV Ctrl  │               │   │ │
│  │  │  │ -Hybrid     │  │ -Incident   │  │ -ACU Ctrl   │               │   │ │
│  │  │  │ -MultiQuery │  │  Detection  │  │ -Function   │               │   │ │
│  │  │  └─────────────┘  └─────────────┘  │  Calling    │               │   │ │
│  │  │                                     └─────────────┘               │   │ │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │ │
│  │  │  │Command Orch │  │Alarm Handler│  │ WebSocket   │               │   │ │
│  │  │  │             │  │             │  │ Broadcaster │               │   │ │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘               │   │ │
│  │  └───────────────────────────────────────────────────────────────────┘   │ │
│  │                                    │                                       │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │ │
│  │  │                    Control Subsystem                               │   │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │ │
│  │  │  │ Network  │  │ Device   │  │Credential│  │  Audit   │          │   │ │
│  │  │  │Discovery │  │ Registry │  │ Manager  │  │ Logger   │          │   │ │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │ │
│  │  │                                                                     │   │ │
│  │  │  Protocol Adapters: ONVIF │ Hanwha │ Hikvision │ ZKTeco │ Suprema │   │ │
│  │  └───────────────────────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                       │
├───────────────────────────────────────┼───────────────────────────────────────┤
│                          External Services Layer                              │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   vLLM       │  │   Qdrant     │  │  PostgreSQL  │  │    Redis     │     │
│  │   (9000)     │  │   (6333)     │  │   (5432)     │  │   (6379)     │     │
│  │              │  │              │  │              │  │              │     │
│  │ Qwen2.5-14B  │  │ Vector DB    │  │ Relational   │  │ Cache        │     │
│  │ Qwen2-VL-7B  │  │ 384-dim      │  │ Database     │  │ LRU 256MB    │     │
│  │   (9001)     │  │              │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                                               │
│  ┌──────────────┐  ┌──────────────────────────────────────────────────────┐ │
│  │   Kafka      │  │                    Physical Devices                   │ │
│  │  (Optional)  │  │  CCTV Cameras (ONVIF) │ NVR │ ACU (ZKTeco/Suprema)   │ │
│  │  Event Stream│  │                                                       │ │
│  └──────────────┘  └──────────────────────────────────────────────────────┘ │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 계층 구조

### Layer 1: Presentation Layer (Frontend)
- **역할**: 사용자 인터페이스 제공
- **기술**: React 19, TypeScript, Tailwind CSS, Vite
- **상태 관리**: Zustand (로컬), React Query (서버)

### Layer 2: API Layer (Backend Routers)
- **역할**: HTTP 요청 라우팅 및 검증
- **기술**: FastAPI, Pydantic
- **특징**: SSE 스트리밍, WebSocket 지원

### Layer 3: Service Layer (Business Logic)
- **역할**: 비즈니스 로직 처리
- **주요 서비스**:
  - RAG Service: 문서 검색 및 응답 생성
  - VLM Analyzer: 이미지 분석
  - System Controller: 장치 제어 오케스트레이션

### Layer 4: Data Layer
- **역할**: 데이터 영속성 및 검색
- **구성**:
  - PostgreSQL: 관계형 데이터
  - Qdrant: 벡터 검색
  - Redis: 캐싱

### Layer 5: External Services
- **역할**: AI 추론 및 외부 장치 연동
- **구성**:
  - vLLM: LLM/VLM 추론
  - 물리 장치: CCTV, ACU

---

## 백엔드 아키텍처

### API 라우터 구조

```
backend/api/
├── security_chat_api.py    # RAG 채팅 (SSE 스트리밍)
├── control_api.py          # 장치 제어 (CCTV/ACU)
├── image_api.py            # Vision 분석
├── document_api.py         # 문서 관리
├── alarm_api.py            # 알람 처리
├── device_api.py           # 장치 등록
├── report_api.py           # 보고서 생성
├── log_ingestion_api.py    # 로그 수집
├── system_api.py           # 시스템 상태
└── auth_api.py             # 인증
```

### 서비스 레이어 구조

```
backend/services/
├── rag_service.py              # RAG 오케스트레이션
├── command_orchestrator.py     # 통합 명령 처리
├── vlm_analyzer.py             # Vision 분석기
├── alarm_handler.py            # 알람 처리
├── websocket_broadcaster.py    # 실시간 알림
├── report_generator.py         # 보고서 생성
├── log_indexer.py              # 로그 인덱싱
├── device_registry.py          # 장치 등록 (DB)
├── device_control.py           # 장치 명령 실행
├── auth_service.py             # 인증 서비스
│
└── control/                    # 장치 제어 서브시스템
    ├── system_controller.py    # 통합 제어기
    ├── cctv_controller.py      # CCTV 제어
    ├── acu_controller.py       # ACU 제어
    ├── device_registry.py      # 장치 레지스트리 (JSON)
    ├── network_discovery.py    # 네트워크 탐색
    ├── credential_manager.py   # 인증정보 관리
    ├── audit_logger.py         # 감사 로깅
    ├── zone_manager.py         # 존 관리
    ├── rate_limiter.py         # 속도 제한
    └── adapters/               # 프로토콜 어댑터
        ├── onvif.py
        ├── hanwha.py
        └── ...
```

### 검색기(Retriever) 구조

```
backend/retrievers/
├── adaptive_retriever.py       # 적응형 검색 (복잡도 기반)
├── hybrid_retriever.py         # 하이브리드 (Vector + BM25)
├── multi_query_retriever.py    # 멀티쿼리 확장
├── bm25_indexer.py             # 키워드 인덱서
├── cross_encoder_reranker.py   # 재순위화
└── query_expander.py           # 쿼리 확장
```

### 데이터베이스 스키마

```sql
-- 장치 관리
CREATE TABLE devices (
    device_id VARCHAR PRIMARY KEY,
    device_type VARCHAR,          -- 'CCTV', 'ACU'
    manufacturer VARCHAR,
    ip_address VARCHAR,
    credentials_encrypted TEXT,   -- Fernet 암호화
    status VARCHAR,
    zone_id VARCHAR
);

-- 장치 제어 이력
CREATE TABLE device_controls (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR,
    command_type VARCHAR,
    parameters JSONB,
    executed_at TIMESTAMP,
    rollback_available BOOLEAN
);

-- 알람/이벤트
CREATE TABLE alarms (
    id SERIAL PRIMARY KEY,
    alarm_type VARCHAR,
    severity VARCHAR,
    device_id VARCHAR,
    vlm_analysis JSONB,
    created_at TIMESTAMP
);

-- 보안 로그
CREATE TABLE security_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR,
    details JSONB,
    timestamp TIMESTAMP
);

-- 감사 로그
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR,
    action VARCHAR,
    target VARCHAR,
    details JSONB,
    timestamp TIMESTAMP
);
```

---

## 프론트엔드 아키텍처

### 디렉토리 구조

```
frontend/react-ui/src/
├── pages/                      # 페이지 컴포넌트
│   ├── DashboardPage.tsx       # 대시보드
│   ├── ChatPage.tsx            # RAG 채팅
│   ├── AnalysisPage.tsx        # 이미지 분석
│   ├── ControlPage.tsx         # 장치 제어
│   ├── DocumentsPage.tsx       # 문서 관리
│   ├── ReportsPage.tsx         # 보고서
│   └── SettingsPage.tsx        # 설정
│
├── components/                 # UI 컴포넌트
│   ├── Chat/                   # 채팅 관련
│   │   ├── ChatMessage.tsx
│   │   ├── CodeBlock.tsx
│   │   └── RAGMetrics.tsx
│   ├── ImageAnalysis/          # 이미지 분석
│   │   ├── ImageUploadCard.tsx
│   │   └── AnalysisResult.tsx
│   ├── Control/                # 장치 제어
│   │   ├── NetworkDiscovery.tsx
│   │   ├── DeviceCard.tsx
│   │   └── PTZControl.tsx
│   ├── common/                 # 공통 컴포넌트
│   │   ├── ErrorBoundary.tsx
│   │   ├── LoadingSpinner.tsx
│   │   └── ToastContainer.tsx
│   └── ...
│
├── services/                   # API 클라이언트
│   ├── api.ts                  # SSE 채팅 API
│   ├── imageAnalysisApi.ts     # Vision API
│   ├── controlApi.ts           # 제어 API
│   └── documentApi.ts          # 문서 API
│
├── stores/                     # Zustand 스토어
│   ├── chatStore.ts
│   ├── deviceStore.ts
│   └── settingsStore.ts
│
├── types/                      # TypeScript 타입
│   ├── chat.ts
│   ├── device.ts
│   └── analysis.ts
│
└── utils/                      # 유틸리티
    ├── formatters.ts
    └── validators.ts
```

### 상태 관리 패턴

```
┌────────────────────────────────────────────────────────────┐
│                    State Management                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌─────────────────────────┐  │
│  │   Zustand       │         │   React Query           │  │
│  │   (Client)      │         │   (Server)              │  │
│  │                 │         │                         │  │
│  │ - UI State      │         │ - API Data Cache        │  │
│  │ - User Prefs    │         │ - Auto Refetch          │  │
│  │ - Local Cache   │         │ - Optimistic Updates    │  │
│  └─────────────────┘         └─────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              SSE Stream State                        │  │
│  │                                                       │  │
│  │  - Real-time chat responses                          │  │
│  │  - Streaming tokens                                  │  │
│  │  - Connection state management                       │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

## 데이터 흐름

### RAG 채팅 흐름

```
┌──────┐    ┌─────────┐    ┌────────────────┐    ┌───────────┐
│ User │───▶│Frontend │───▶│ Backend API    │───▶│ RAG       │
│      │    │ (React) │    │ (FastAPI)      │    │ Service   │
└──────┘    └────┬────┘    └───────┬────────┘    └─────┬─────┘
                 │                 │                    │
                 │    SSE Stream   │                    │
                 │◀────────────────│                    │
                 │                 │                    ▼
                 │                 │            ┌───────────────┐
                 │                 │            │ Adaptive      │
                 │                 │            │ Retriever     │
                 │                 │            └───────┬───────┘
                 │                 │                    │
                 │                 │                    ▼
                 │                 │            ┌───────────────┐
                 │                 │            │   Qdrant      │
                 │                 │            │ (Vector DB)   │
                 │                 │            └───────┬───────┘
                 │                 │                    │
                 │                 │                    ▼
                 │                 │            ┌───────────────┐
                 │                 │◀───────────│    vLLM       │
                 │                 │            │ (Qwen2.5)     │
                 │                 │            └───────────────┘
                 ▼
        [Display Streaming Response]
```

### 이미지 분석 흐름

```
┌──────┐    ┌─────────┐    ┌────────────────┐    ┌───────────┐
│ User │───▶│Frontend │───▶│ Image API      │───▶│ VLM       │
│Upload│    │ (React) │    │ (FastAPI)      │    │ Analyzer  │
└──────┘    └────┬────┘    └───────┬────────┘    └─────┬─────┘
                 │                 │                    │
                 │                 │                    ▼
                 │                 │            ┌───────────────┐
                 │                 │            │ Qwen2-VL-7B   │
                 │                 │            │ (vLLM:9001)   │
                 │                 │            └───────┬───────┘
                 │                 │                    │
                 │                 │            ┌───────┴───────┐
                 │                 │            │ Incident      │
                 │                 │            │ Detection     │
                 │                 │            │ (9 Types)     │
                 │                 │            └───────┬───────┘
                 │                 │                    │
                 │                 │◀───────────────────┘
                 │                 │
                 │  ┌──────────────┤
                 │  │              │
                 │  ▼              ▼
                 │ [WebSocket]  [PostgreSQL]
                 │ Broadcast    Store Result
                 │
                 ▼
        [Display Analysis Result]
```

### 장치 제어 흐름

```
┌──────┐    ┌─────────┐    ┌────────────────┐    ┌────────────┐
│ User │───▶│Frontend │───▶│ Control API    │───▶│ System     │
│ NL   │    │ (React) │    │ (FastAPI)      │    │ Controller │
│Cmd   │    └─────────┘    └────────────────┘    └──────┬─────┘
└──────┘                                                │
                                                        │
                         ┌──────────────────────────────┤
                         │                              │
                         ▼                              ▼
                  ┌─────────────┐              ┌─────────────┐
                  │   vLLM      │              │ Function    │
                  │  (9000)     │              │ Router      │
                  │             │              │             │
                  │ Function    │              │ CCTV │ ACU  │
                  │ Calling     │              └──────┴──────┘
                  └──────┬──────┘                     │
                         │                            │
                         │    Parsed Function         │
                         │◀───────────────────────────┘
                         │
                         ▼
              ┌────────────────────┐
              │ Protocol Adapter   │
              │ (ONVIF/Hanwha/...) │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │   Physical Device  │
              │   (CCTV/ACU)       │
              └────────────────────┘
```

---

## 외부 서비스 연동

### vLLM 연동

```yaml
# Text LLM (Port 9000)
Model: Qwen/Qwen2.5-14B-Instruct-AWQ
GPU: RTX 4000 Ada (GPU 1)
API: OpenAI-compatible

# Vision LLM (Port 9001)
Model: Qwen/Qwen2-VL-7B-Instruct
GPU: RTX 4000 Ada (GPU 0)
API: OpenAI-compatible
```

### Qdrant 연동

```yaml
Collections:
  - documents:        # 업로드된 문서
      vector_size: 384
      distance: Cosine

  - security_logs:    # 보안 로그
      vector_size: 384
      distance: Cosine

Embedding Model: BAAI/bge-small-en-v1.5
```

### 장치 프로토콜

| 프로토콜 | 지원 장치 | 포트 |
|---------|----------|------|
| ONVIF | IP 카메라 (범용) | 80, 8080 |
| Hanwha Wisenet | 한화 카메라 | 80, 443 |
| Hikvision | 하이크비전 카메라 | 80, 8000 |
| RTSP | 영상 스트리밍 | 554 |
| ZKTeco | 출입통제 장치 | 4370 |
| Suprema | BioStar 2 ACU | 5005 |

---

## 보안 아키텍처

### 인증/인가

```
┌─────────────────────────────────────────────────────────┐
│                    Security Layer                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐    ┌──────────────────────────┐  │
│  │   JWT Auth       │    │   Credential Manager     │  │
│  │                  │    │                          │  │
│  │ - Access Token   │    │ - Fernet Encryption      │  │
│  │ - Refresh Token  │    │ - Device Passwords       │  │
│  │ - RBAC (예정)    │    │ - API Keys               │  │
│  └──────────────────┘    └──────────────────────────┘  │
│                                                          │
│  ┌──────────────────┐    ┌──────────────────────────┐  │
│  │   Rate Limiter   │    │   Audit Logger           │  │
│  │                  │    │                          │  │
│  │ - Auth: 5/5min   │    │ - Command History        │  │
│  │ - API: 100/min   │    │ - Credential Access      │  │
│  │ - Control: 30/min│    │ - Security Events        │  │
│  └──────────────────┘    └──────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 데이터 보안

| 데이터 유형 | 보안 조치 |
|------------|----------|
| 장치 인증정보 | Fernet 암호화 (AES-128-CBC + HMAC) |
| JWT 토큰 | HS256 서명 |
| API 통신 | HTTPS (프로덕션) |
| DB 연결 | asyncpg SSL |
| 파일 저장 | 디렉토리 권한 600 |

---

## 확장성 고려사항

### 수평 확장

- **Frontend**: Nginx 로드밸런싱
- **Backend**: 여러 FastAPI 인스턴스 + Redis 세션
- **vLLM**: 모델별 분리 배포

### 수직 확장

- **GPU**: 추가 GPU로 모델 분산
- **Qdrant**: 클러스터 모드 지원
- **PostgreSQL**: 읽기 복제본

### 캐싱 전략

```
Request → Redis Cache → Qdrant → PostgreSQL
              ↓
         Cache Hit? → Return Cached
              ↓
         Cache Miss → Fetch & Cache
```

---

## 모니터링 포인트

| 메트릭 | 위치 | 임계값 |
|--------|------|--------|
| API 응답 시간 | Backend | < 500ms |
| vLLM 추론 시간 | vLLM | < 5s |
| Qdrant 검색 시간 | Qdrant | < 100ms |
| WebSocket 연결 수 | Backend | < 1000 |
| 장치 연결 상태 | Control | > 80% |

---

## 버전 정보

| 컴포넌트 | 버전 |
|---------|------|
| Python | 3.11+ |
| FastAPI | 0.100+ |
| React | 19 |
| TypeScript | 5.x |
| Qdrant | 1.7+ |
| PostgreSQL | 15+ |
| Redis | 7+ |
