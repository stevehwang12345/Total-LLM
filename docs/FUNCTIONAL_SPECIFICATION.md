# Total-LLM 세부 기능명세서 및 시스템 아키텍처

> **문서 버전**: 1.0.0  
> **작성일**: 2026-03-20  
> **프로젝트**: Total-LLM — LLM 기반 통합 보안 모니터링 시스템

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [기능 명세: RAG 문서 QA](#3-기능-명세-rag-문서-qa)
4. [기능 명세: Vision AI 이미지 분석](#4-기능-명세-vision-ai-이미지-분석)
5. [기능 명세: 장치 제어 시스템](#5-기능-명세-장치-제어-시스템)
6. [기능 명세: 알람 및 실시간 모니터링](#6-기능-명세-알람-및-실시간-모니터링)
7. [기능 명세: 보고서 생성](#7-기능-명세-보고서-생성)
8. [기능 명세: 문서 관리](#8-기능-명세-문서-관리)
9. [기능 명세: 로그 수집 및 검색](#9-기능-명세-로그-수집-및-검색)
10. [기능 명세: API 코드 자동 생성기](#10-기능-명세-api-코드-자동-생성기)
11. [기능 명세: 인증 및 보안](#11-기능-명세-인증-및-보안)
12. [기능 명세: 시스템 관리](#12-기능-명세-시스템-관리)
13. [프론트엔드 아키텍처](#13-프론트엔드-아키텍처)
14. [데이터베이스 스키마](#14-데이터베이스-스키마)
15. [인프라 및 배포](#15-인프라-및-배포)
16. [서비스 간 의존성 맵](#16-서비스-간-의존성-맵)
17. [개발 현황 및 로드맵](#17-개발-현황-및-로드맵)

---

## 1. 시스템 개요

### 1.1 프로젝트 정의

Total-LLM은 **LLM 기반 통합 보안 모니터링 시스템**으로, 세 가지 핵심 AI 기능을 하나의 플랫폼으로 통합합니다:

| 핵심 기능 | 설명 | AI 모델 |
|-----------|------|---------|
| **Vision AI** | CCTV 영상/이미지에서 보안 사고를 자동 감지·분류 | Qwen2.5-VL-7B-Instruct |
| **RAG QA** | 보안 정책 문서 기반 질의응답 (적응형 검색) | Qwen2.5-14B-Instruct-AWQ |
| **장치 제어** | 자연어 명령으로 CCTV/ACU 장비를 제어 | Qwen2.5-14B (Function Calling) |

### 1.2 기술 스택 요약

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend    │ React 19 · TypeScript 5.9 · Vite 7 · Tailwind 4  │
│              │ Zustand 5 · TanStack Query 5 · React Router 7     │
├──────────────┼───────────────────────────────────────────────────┤
│  Backend     │ FastAPI · Python 3.11+ · Uvicorn · asyncpg        │
│              │ LangChain · OpenAI SDK · Pydantic 2               │
├──────────────┼───────────────────────────────────────────────────┤
│  AI/ML       │ vLLM (Qwen2.5-14B-AWQ, Qwen2.5-VL-7B)           │
│              │ BAAI/bge-small-en-v1.5 (Embedding, 384d)         │
│              │ cross-encoder/ms-marco-MiniLM-L-6-v2 (Reranking) │
├──────────────┼───────────────────────────────────────────────────┤
│  Data Layer  │ PostgreSQL 15 · Qdrant 1.7+ · Redis 7            │
├──────────────┼───────────────────────────────────────────────────┤
│  Infra       │ Docker Compose · Nginx · Kafka (Optional)         │
│              │ Fluentd · NVIDIA CUDA GPU                         │
└──────────────┴───────────────────────────────────────────────────┘
```

### 1.3 서비스 포트 맵

| 서비스 | 포트 | 프로토콜 | 설명 |
|--------|------|----------|------|
| Frontend | 9004 | HTTP | React UI (Nginx) |
| Backend API | 9002 | HTTP/REST | FastAPI 메인 API |
| WebSocket | 9003 | WS | 실시간 알림 |
| vLLM Text | 9000 | HTTP | Qwen2.5-14B-AWQ (OpenAI 호환) |
| vLLM Vision | 9001 | HTTP | Qwen2.5-VL-7B (OpenAI 호환) |
| Qdrant | 6333/6334 | HTTP/gRPC | 벡터 데이터베이스 |
| PostgreSQL | 5432 | TCP | 관계형 데이터베이스 |
| Redis | 6379 | TCP | 캐시 서버 |
| Kafka | 9092 | TCP | 메시지 브로커 (선택) |

---

## 2. 시스템 아키텍처

### 2.1 전체 시스템 구성도

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Total-LLM Platform                                    │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                 Layer 1: Presentation (Frontend)                           │  │
│  │                                                                            │  │
│  │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │  │
│  │   │Dashboard │ │ Chat     │ │ Analysis │ │ Control  │ │Documents │       │  │
│  │   │          │ │ (RAG QA) │ │(Vision)  │ │(ACU/CCTV)│ │(RAG Docs)│       │  │
│  │   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │  │
│  │        └─────────────┴────────────┴────────────┴────────────┘              │  │
│  │                              │                                              │  │
│  │        ┌─────────────────────┴─────────────────────┐                       │  │
│  │        │      Zustand Stores · React Query Cache    │                       │  │
│  │        │      SSE Client · WebSocket Hook           │                       │  │
│  │        └─────────────────────┬─────────────────────┘                       │  │
│  └──────────────────────────────┼──────────────────────────────────────────────┘  │
│                                 │                                                 │
│             HTTP/REST (9002) ───┼─── WebSocket (9003) ── SSE Streaming            │
│                                 │                                                 │
│  ┌──────────────────────────────┼──────────────────────────────────────────────┐  │
│  │                 Layer 2: API Gateway (FastAPI Routers)                      │  │
│  │                                                                            │  │
│  │   ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐             │  │
│  │   │security_   │ │control_    │ │image_      │ │document_   │             │  │
│  │   │chat_api    │ │api         │ │api         │ │api         │             │  │
│  │   └────────────┘ └────────────┘ └────────────┘ └────────────┘             │  │
│  │   ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐             │  │
│  │   │alarm_api   │ │device_api  │ │report_api  │ │auth_api    │             │  │
│  │   └────────────┘ └────────────┘ └────────────┘ └────────────┘             │  │
│  │   ┌────────────┐ ┌────────────┐                                           │  │
│  │   │log_api     │ │system_api  │ → 총 10개 라우터, 84+ 엔드포인트           │  │
│  │   └────────────┘ └────────────┘                                           │  │
│  └──────────────────────────────┼──────────────────────────────────────────────┘  │
│                                 │                                                 │
│  ┌──────────────────────────────┼──────────────────────────────────────────────┐  │
│  │                 Layer 3: Service Layer (Business Logic)                     │  │
│  │                                                                            │  │
│  │   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │  │
│  │   │  RAG Service      │  │  VLM Analyzer     │  │ System Controller│        │  │
│  │   │  ┌──────────────┐ │  │  ┌──────────────┐ │  │ ┌──────────────┐│        │  │
│  │   │  │Adaptive      │ │  │  │QA-Based      │ │  │ │Function      ││        │  │
│  │   │  │Retriever     │ │  │  │Analysis (4Q) │ │  │ │Calling (LLM) ││        │  │
│  │   │  ├──────────────┤ │  │  ├──────────────┤ │  │ ├──────────────┤│        │  │
│  │   │  │Hybrid Search │ │  │  │Incident      │ │  │ │CCTV Ctrl     ││        │  │
│  │   │  │(BM25+Vector) │ │  │  │Detector (9t) │ │  │ │ACU Ctrl      ││        │  │
│  │   │  ├──────────────┤ │  │  ├──────────────┤ │  │ │Protocol      ││        │  │
│  │   │  │Multi-Query   │ │  │  │Report Gen    │ │  │ │Adapters      ││        │  │
│  │   │  │Cross-Encoder │ │  │  │(Markdown/PDF)│ │  │ └──────────────┘│        │  │
│  │   │  └──────────────┘ │  │  └──────────────┘ │  └──────────────────┘        │  │
│  │   └──────────────────┘  └──────────────────┘                               │  │
│  │                                                                            │  │
│  │   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │  │
│  │   │Command           │  │Alarm Handler     │  │WebSocket         │        │  │
│  │   │Orchestrator      │  │(Kafka→DB→Alert)  │  │Broadcaster       │        │  │
│  │   └──────────────────┘  └──────────────────┘  └──────────────────┘        │  │
│  │   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │  │
│  │   │Cache Service     │  │Conversation      │  │Auth Service      │        │  │
│  │   │(Redis)           │  │Service (PG)      │  │(JWT+bcrypt)      │        │  │
│  │   └──────────────────┘  └──────────────────┘  └──────────────────┘        │  │
│  └──────────────────────────────┼──────────────────────────────────────────────┘  │
│                                 │                                                 │
│  ┌──────────────────────────────┼──────────────────────────────────────────────┐  │
│  │                 Layer 4: Data & External Services                           │  │
│  │                                                                            │  │
│  │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │  │
│  │   │PostgreSQL│ │Qdrant    │ │Redis     │ │vLLM      │ │Kafka     │       │  │
│  │   │(5432)    │ │(6333)    │ │(6379)    │ │(9000/01) │ │(9092)    │       │  │
│  │   │          │ │          │ │          │ │          │ │(Optional)│       │  │
│  │   │-devices  │ │-documents│ │-rag:*    │ │-Text LLM │ │-security │       │  │
│  │   │-alarms   │ │-security_│ │-conv:*   │ │-Vision   │ │ .alarms  │       │  │
│  │   │-reports  │ │ logs     │ │          │ │ LLM      │ │          │       │  │
│  │   │-convos   │ │          │ │          │ │          │ │          │       │  │
│  │   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘       │  │
│  │                                                                            │  │
│  │   ┌────────────────────────────────────────────────────────────────┐       │  │
│  │   │              Physical Devices (ONVIF / SSH / REST)             │       │  │
│  │   │   CCTV: 한화·하이크비전 (PTZ, 녹화)                            │       │  │
│  │   │   ACU:  ZKTeco·슈프리마 (출입문 제어)                          │       │  │
│  │   └────────────────────────────────────────────────────────────────┘       │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 설계 패턴

| 패턴 | 적용 위치 | 목적 |
|------|-----------|------|
| **Dependency Injection** | `main.py` lifespan | 서비스 인스턴스를 라우터에 주입 |
| **Strategy Pattern** | `AdaptiveRetriever` | 쿼리 복잡도에 따라 검색 전략 동적 선택 |
| **Factory Pattern** | `control/adapters/` | 프로토콜별 어댑터 동적 생성 |
| **Adapter Pattern** | ONVIF/SSH/REST 어댑터 | 이종 프로토콜 추상화 |
| **Command Pattern** | `CommandOrchestrator` | Function Call을 명령 객체로 캡슐화 |
| **Observer Pattern** | `WebSocketBroadcaster` | 실시간 이벤트 푸시 |
| **Repository Pattern** | `DeviceRegistry`, `RAGService` | 데이터 접근 추상화 |
| **Singleton** | `CacheService`, `ConversationService` | 전역 서비스 인스턴스 |

### 2.3 서비스 초기화 순서 (Lifespan)

```
main.py lifespan() 시작
  │
  ├─ 1. PostgreSQL 커넥션 풀 (asyncpg, min=5, max=pool_size)
  ├─ 2. RAG Service (AdaptiveRetriever + Qdrant + BM25)
  ├─ 3. Device Registry + Device Control (DB 연동)
  ├─ 4. Command Orchestrator (RAG + Device 통합)
  ├─ 5. LLM Client (AsyncOpenAI → vLLM:9000)
  ├─ 5.1 Cache Service (Redis, 선택적)
  ├─ 5.2 Conversation Service (PostgreSQL, 선택적)
  ├─ 6. VLM Analyzer (AsyncOpenAI → vLLM:9001)
  ├─ 7. WebSocket Broadcaster (Port 9003, 백그라운드)
  ├─ 8. Alarm Handler (DB + WS + VLM 통합)
  ├─ 8. Kafka Consumer (선택적, 백그라운드)
  ├─ 9. Report Generator
  ├─ 10. Log Indexer
  └─ 11. Document API 의존성 주입
```

---

## 3. 기능 명세: RAG 문서 QA

### 3.1 개요

보안 정책 문서(PDF, DOCX, TXT, MD)를 벡터화하여 저장하고, 사용자 질문에 대해 관련 문서를 검색한 후 LLM으로 답변을 생성하는 RAG 파이프라인.

### 3.2 핵심 기능

#### 3.2.1 적응형 검색 (Adaptive Retrieval)

질의 복잡도를 실시간 분석하여 최적의 검색 전략을 자동 선택합니다.

```
사용자 질의 → 복잡도 분석 → 전략 선택
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         Simple (0.0~0.3) Hybrid (0.3~0.6) Complex (0.6~1.0)
              │               │               │
         벡터 검색만       BM25 + 벡터      다중 쿼리 확장
          k=3              k=5              k=7
```

| 전략 | 복잡도 범위 | 검색 방식 | 반환 문서 수 |
|------|-------------|-----------|--------------|
| `simple_vector` | 0.0 ~ 0.3 | Qdrant 벡터 검색만 | 3 |
| `hybrid_search` | 0.3 ~ 0.6 | BM25(0.3) + Vector(0.7) + Cross-Encoder Reranking | 5 |
| `multi_query` | 0.6 ~ 1.0 | 쿼리 확장(3개) + 하이브리드 + RRF 통합 | 7 |

#### 3.2.2 하이브리드 검색 (Hybrid Search)

```
쿼리 ──┬── BM25 키워드 검색 (가중치 0.3) ──┐
       │                                    ├── RRF 통합 → Cross-Encoder 재순위화 → 결과
       └── Qdrant 벡터 검색 (가중치 0.7) ──┘
```

- **BM25**: `rank-bm25` 라이브러리, 키워드 정확 매칭
- **Vector**: Qdrant 코사인 유사도, 384차원 (bge-small-en-v1.5)
- **RRF**: Reciprocal Rank Fusion으로 두 결과 통합
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (임계값 0.0 이상)

#### 3.2.3 다중 쿼리 확장 (Multi-Query)

- **규칙 기반**: 동의어 치환, 어순 변경 등 (기본 모드)
- **LLM 기반**: vLLM으로 쿼리 변형 3개 생성 (선택적)
- **결과 통합**: RRF 방식으로 중복 제거 후 순위 통합

#### 3.2.4 SSE 스트리밍 응답

```
POST /api/security/chat
  ↓
[검색 단계] → data: {"type": "source", "sources": [...]}
  ↓
[생성 단계] → data: {"type": "token", "content": "응답..."}
              data: {"type": "token", "content": "계속..."}
  ↓
[완료]      → data: {"type": "done"}
```

#### 3.2.5 대화 지속성

- **저장**: PostgreSQL `conversations` + `conversation_messages` 테이블
- **캐싱**: Redis (`conv:*` 키, TTL 24시간)
- **컨텍스트 윈도우**: 최근 5턴 유지 (설정 가능)
- **모드**: `qa` (문서 QA), `device_register` (장비 등록), `device_control` (장비 제어)

#### 3.2.6 RAG 캐싱

- **위치**: Redis (`rag:*` 키)
- **TTL**: 3600초 (1시간)
- **캐시 키**: `query + retriever_type + filter_metadata` 해시
- **무효화**: 문서 업로드/삭제 시 전체 캐시 삭제

### 3.3 관련 파일

| 파일 | 역할 |
|------|------|
| `backend/api/security_chat_api.py` | SSE 스트리밍 채팅 API |
| `backend/services/rag_service.py` | RAG 오케스트레이션 |
| `backend/services/command_orchestrator.py` | Function Call 라우팅 |
| `backend/retrievers/adaptive_retriever.py` | 적응형 검색 전략 |
| `backend/retrievers/hybrid_retriever.py` | BM25+벡터 하이브리드 |
| `backend/retrievers/multi_query_retriever.py` | 다중 쿼리 확장 |
| `backend/retrievers/cross_encoder_reranker.py` | 교차 인코더 재순위화 |
| `backend/retrievers/bm25_indexer.py` | BM25 인덱서 |
| `backend/retrievers/query_expander.py` | 쿼리 확장기 |
| `backend/core/complexity_analyzer.py` | 복잡도 분석기 |
| `backend/tools/rag_tool.py` | Qdrant 연동 RAG 도구 |
| `backend/services/cache_service.py` | Redis 캐싱 |
| `backend/services/conversation_service.py` | 대화 지속성 |

### 3.4 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/security/chat` | SSE 스트리밍 RAG 채팅 |
| `GET` | `/api/security/modes` | 사용 가능 채팅 모드 목록 |
| `GET` | `/api/security/health` | 서비스 헬스체크 |

---

## 4. 기능 명세: Vision AI 이미지 분석

### 4.1 개요

CCTV 캡처 이미지를 Qwen2.5-VL-7B 비전 모델로 분석하여 보안 사고를 자동 감지, 분류, 보고하는 시스템.

### 4.2 분석 파이프라인

```
이미지 입력 (Base64 / 파일)
    │
    ▼
리사이즈 (max 512px, LANCZOS)
    │
    ▼
4단계 QA 기반 구조화 분석
    │
    ├── Q1: 폭력/범죄 활동 감지 여부
    ├── Q2: 사고 유형 분류 (9가지)
    ├── Q3: 관련 인물/행동 묘사
    └── Q4: 전체 상황 설명
    │
    ▼
사고 유형 + 심각도 추출
    │
    ▼
마크다운 보안 보고서 생성
    │
    ▼
결과 반환 + WebSocket 알림
```

### 4.3 사고 유형 분류 (9가지 + 정상)

| 코드 | 한국어 | 심각도 기본값 | 대응 시간 |
|------|--------|---------------|-----------|
| `fire` | 화재 | CRITICAL | 즉시 |
| `weapon` | 무기 | CRITICAL | 즉시 |
| `fight` | 싸움/폭력 | VERY_HIGH | 즉시 |
| `intrusion` | 침입 | HIGH | 5분 이내 |
| `vandalism` | 기물파손 | HIGH | 5분 이내 |
| `accident` | 사고/낙상 | HIGH | 5분 이내 |
| `smoke` | 연기 | MEDIUM | 30분 이내 |
| `abandoned_object` | 유기물 | MEDIUM | 30분 이내 |
| `crowd` | 군중 밀집 | MEDIUM | 30분 이내 |
| `normal` | 정상 | LOW | - |

### 4.4 분석 모드

| 모드 | 토큰 수 | 분석 깊이 | 용도 |
|------|---------|-----------|------|
| `quick` | 256 | 기본 감지 | 대량 배치, 실시간 모니터링 |
| `standard` | 512 | 상세 분석 | 일반 분석 (기본값) |
| `detailed` | 1024 | 전체 보고서 | 보안 보고서 생성 |

### 4.5 배치 분석

- **병렬 처리**: `asyncio.Semaphore`로 동시 실행 수 제한 (기본 5)
- **에러 격리**: 개별 분석 실패 시 나머지 계속 진행
- **결과 통합**: 다중 이미지 분석 결과를 LLM으로 종합 평가

### 4.6 관련 파일

| 파일 | 역할 |
|------|------|
| `backend/api/image_api.py` | 이미지 분석 API |
| `backend/services/vlm_analyzer.py` | VLM 통합 분석기 |
| `backend/services/vision/detection/incident_detector.py` | 사고 유형 분류 |
| `backend/services/vision/korean_prompts.py` | 한국어 프롬프트 |
| `backend/services/vision/security_analyzer.py` | 보안 특화 분석 |
| `backend/services/vision/templates/report_template.py` | 보고서 템플릿 |

### 4.7 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/image/analyze` | Base64 이미지 분석 |
| `POST` | `/image/analyze/upload` | 파일 업로드 분석 |
| `POST` | `/image/analyze/batch` | 배치 이미지 분석 |
| `POST` | `/image/analyze/report` | 보안 보고서 생성 |
| `GET` | `/image/results/{id}` | 분석 결과 조회 |
| `GET` | `/image/health` | 서비스 헬스체크 |

### 4.8 응답 스키마

```typescript
interface ImageAnalyzeResponse {
  success: boolean;
  analysis_id: string;          // 고유 분석 ID
  timestamp: string;            // ISO 8601
  location: string;             // 발생 위치
  incident_type: string;        // 영문 사고 유형 (fire, fight, ...)
  incident_type_ko: string;     // 한국어 (화재, 싸움, ...)
  severity: string;             // critical / high / medium / low
  severity_ko: string;          // 한국어 심각도
  confidence: number;           // 0.0 ~ 1.0
  description?: string;         // 상세 설명
  recommended_actions: string[]; // 권장 조치 (최대 3개)
  raw_analysis?: string;        // VLM 원본 응답
  qa_results?: {                // QA 기반 분석 시
    q1_detection: string;
    q2_classification: string;
    q3_subject: string;
    q4_description: string;
  };
}
```

---

## 5. 기능 명세: 장치 제어 시스템

### 5.1 개요

자연어 명령을 LLM Function Calling으로 파싱하여 CCTV(PTZ 제어, 녹화, 스냅샷)와 ACU(출입문 잠금/해제, 권한 관리)를 제어하는 통합 시스템.

### 5.2 자연어 명령 처리 흐름

```
"1번 카메라 왼쪽으로 30도 이동해줘"
    │
    ▼
System Controller → vLLM Function Calling (Qwen2.5-14B)
    │
    ▼
Function Call 파싱:
  { "name": "move_camera", "arguments": {"camera_id": "cam_001", "pan": -30} }
    │
    ▼
Function Handler → CCTVController.move_camera()
    │
    ▼
Protocol Adapter → ONVIF / Hanwha / Simulation
    │
    ▼
물리 장치 실행 + 감사 로그 기록
    │
    ▼
결과 반환 + WebSocket 알림
```

### 5.3 지원 함수 목록

#### CCTV 함수 (10개)

| 함수명 | 설명 | 주요 파라미터 |
|--------|------|---------------|
| `move_camera` | PTZ 이동 | camera_id, pan(-180~180), tilt(-90~90), zoom(1~20) |
| `go_to_preset` | 프리셋 이동 | camera_id, preset_id |
| `save_preset` | 프리셋 저장 | camera_id, preset_name |
| `start_recording` | 녹화 시작 | camera_id, duration, quality |
| `stop_recording` | 녹화 중지 | camera_id |
| `capture_snapshot` | 스냅샷 캡처 | camera_id, resolution |
| `get_camera_status` | 카메라 상태 | camera_id |
| `get_recording_list` | 녹화 목록 | camera_id, limit |
| `set_motion_detection` | 모션 감지 설정 | camera_id, enabled, sensitivity |
| `get_system_status` | 시스템 전체 상태 | - |

#### ACU 함수 (8개)

| 함수명 | 설명 | 주요 파라미터 |
|--------|------|---------------|
| `unlock_door` | 출입문 열기 | door_id, duration(초) |
| `lock_door` | 출입문 잠금 | door_id |
| `get_door_status` | 출입문 상태 | door_id |
| `get_access_log` | 출입 이력 | door_id, limit |
| `grant_access` | 출입 권한 부여 | user_id, door_ids[], valid_from, valid_until |
| `revoke_access` | 출입 권한 회수 | user_id, door_ids[] |
| `emergency_unlock_all` | 비상 전체 개방 | reason, authorized_by |
| `emergency_lock_all` | 비상 전체 잠금 | reason, authorized_by |

### 5.4 프로토콜 어댑터

| 어댑터 | 대상 장치 | 프로토콜 | 포트 |
|--------|----------|----------|------|
| `onvif.py` | IP 카메라 (범용) | ONVIF WS | 80, 8080 |
| `hanwha.py` | 한화 Wisenet | REST (v2) | 80, 443 |
| `hikvision.py` | 하이크비전 | REST (Digest Auth) | 80, 8000 |
| `zkteco.py` | ZKTeco ACU | SDK | 4370 |
| `suprema.py` | BioStar 2 | REST (v2.8) | 5005 |
| `simulation.py` | 테스트용 가상 장치 | 시뮬레이션 | - |

### 5.5 동작 모드

| 모드 | 설명 |
|------|------|
| `simulation` | 시뮬레이션만 사용 (테스트/개발) |
| `real` | 실제 장치만 사용 (연결 실패 시 오류) |
| `hybrid` | 실제 장치 우선, 실패 시 시뮬레이션 폴백 (기본값) |

### 5.6 보안 메커니즘

- **Credential Manager**: Fernet 암호화 (AES-128-CBC + HMAC)로 장치 인증정보 관리
- **Rate Limiter**: 장치별 요청 제한 (Auth: 5/5분, API: 100/분, Control: 30/분)
- **Audit Logger**: 모든 제어 명령 이력 기록 (사용자, 시간, 결과)
- **Rollback**: ACU 명령 실패 시 자동 롤백 (10초 타임아웃)
- **Zone Manager**: 보안 구역 기반 접근 제어

### 5.7 네트워크 자동 탐색

- **ONVIF WS-Discovery**: 서브넷 내 ONVIF 호환 장치 자동 탐색
- **포트 스캔**: 일반적인 장치 포트(80, 554, 8080, 4370, 5005) 스캔
- **핑거프린팅**: 서버 헤더, 오픈 포트로 제조사/모델 식별

### 5.8 관련 파일

| 파일 | 역할 |
|------|------|
| `backend/api/control_api.py` | 장치 제어 API (23개 엔드포인트) |
| `backend/services/control/system_controller.py` | LLM Function Calling 엔진 |
| `backend/services/control/cctv_controller.py` | CCTV PTZ/녹화 제어 |
| `backend/services/control/acu_controller.py` | ACU 출입문 제어 |
| `backend/services/control/function_schemas.py` | 함수 정의 스키마 |
| `backend/services/control/device_registry.py` | 장치 레지스트리 (JSON) |
| `backend/services/control/credential_manager.py` | 암호화 인증정보 |
| `backend/services/control/network_discovery.py` | 네트워크 탐색 |
| `backend/services/control/audit_logger.py` | 감사 로깅 |
| `backend/services/control/rate_limiter.py` | 속도 제한 |
| `backend/services/control/zone_manager.py` | 구역 관리 |
| `backend/services/control/connection_health.py` | 연결 상태 모니터링 |
| `backend/services/control/adapters/` | 프로토콜 어댑터들 |

### 5.9 API 엔드포인트 (23개)

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/control/command` | 자연어 명령 처리 |
| `POST` | `/control/function` | 함수 직접 호출 |
| `GET` | `/control/functions` | 사용 가능 함수 목록 |
| `POST` | `/control/acu/door/unlock` | 출입문 열기 |
| `POST` | `/control/acu/door/lock` | 출입문 잠금 |
| `GET` | `/control/acu/door/status` | 출입문 상태 |
| `GET` | `/control/acu/log` | 출입 이력 |
| `POST` | `/control/acu/permission/grant` | 출입 권한 부여 |
| `POST` | `/control/acu/permission/revoke` | 출입 권한 회수 |
| `POST` | `/control/acu/emergency/unlock` | 비상 전체 개방 |
| `POST` | `/control/acu/emergency/lock` | 비상 전체 잠금 |
| `POST` | `/control/cctv/camera/move` | 카메라 PTZ 제어 |
| `POST` | `/control/cctv/camera/preset` | 프리셋 이동 |
| `POST` | `/control/cctv/recording/start` | 녹화 시작 |
| `POST` | `/control/cctv/recording/stop` | 녹화 중지 |
| `POST` | `/control/cctv/snapshot` | 스냅샷 캡처 |
| `GET` | `/control/cctv/camera/status` | 카메라 상태 |
| `POST` | `/control/network/scan` | 네트워크 장치 스캔 |
| `GET` | `/control/devices` | 장치 목록 |
| `POST` | `/control/devices/register` | 장치 등록 |
| `PUT` | `/control/devices/{id}/credentials` | 인증정보 갱신 |
| `GET` | `/control/zones` | 보안 구역 목록 |
| `GET` | `/control/audit-log` | 감사 로그 |

---

## 6. 기능 명세: 알람 및 실시간 모니터링

### 6.1 알람 처리 파이프라인

```
[Kafka Topic: security.alarms]     [HTTP POST: /api/alarms]
        │                                    │
        ▼                                    ▼
   SecurityAlarmConsumer              Alarm API Router
        │                                    │
        └─────────────┬──────────────────────┘
                      ▼
              AlarmHandler.handle_alarm()
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   이미지 다운로드  DB 저장      VLM 분석
   (aiohttp)     (PostgreSQL)  (선택적)
        │             │             │
        └─────────────┼─────────────┘
                      ▼
           WebSocket Broadcast (Port 9003)
                      │
                      ▼
              Frontend 실시간 알림
```

### 6.2 알람 속성

| 필드 | 타입 | 설명 |
|------|------|------|
| `alarm_id` | VARCHAR(100) | 고유 식별자 |
| `alarm_type` | VARCHAR(50) | 침입 탐지, 배회, 미인가 출입 등 |
| `severity` | ENUM | CRITICAL, HIGH, MEDIUM, LOW |
| `location` | VARCHAR(200) | 발생 위치 |
| `zone` | VARCHAR(100) | 보안 구역 |
| `device_id` | VARCHAR(50) | 관련 장비 ID |
| `image_path` | VARCHAR(500) | 이미지 파일 경로 |
| `vlm_analysis` | JSONB | VLM 분석 결과 |
| `is_processed` | BOOLEAN | 처리 완료 여부 |
| `metadata` | JSONB | 추가 메타데이터 |

### 6.3 WebSocket 실시간 알림

- **서버**: `WebSocketBroadcaster` (Port 9003, 독립 서버)
- **프로토콜**: 표준 WebSocket
- **이벤트 형식**:
  ```json
  {
    "type": "alarm",
    "alarm_id": "ALM-2026-001",
    "severity": "HIGH",
    "location": "A동 3층",
    "timestamp": "2026-03-20T10:30:00Z"
  }
  ```

### 6.4 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/api/alarms` | 알람 목록 (필터링, 페이징) |
| `GET` | `/api/alarms/{id}` | 특정 알람 상세 |
| `POST` | `/api/alarms/mark-processed` | 처리 완료 표시 (배치) |
| `POST` | `/api/alarms/{id}/analyze` | VLM 분석 실행 |
| `POST` | `/api/alarms/analyze/batch` | 배치 VLM 분석 |
| `GET` | `/api/alarms/stats/summary` | 알람 통계 요약 |
| `DELETE` | `/api/alarms/cleanup` | 오래된 이미지 정리 |
| `GET` | `/api/alarms/health` | 헬스체크 |

---

## 7. 기능 명세: 보고서 생성

### 7.1 개요

선택된 알람 데이터와 VLM 이미지 분석 결과를 종합하여 PDF 보안 보고서를 자동 생성합니다.

### 7.2 보고서 생성 흐름

```
알람 ID 선택 (체크박스)
    │
    ▼
알람 데이터 조회 (PostgreSQL)
    │
    ▼
이미지 수집 + VLM 분석 (선택적)
    │
    ▼
보고서 구조 생성:
  ├── 1. 요약 (총 알람 수, 심각도별 통계)
  ├── 2. 개별 알람 분석 (이미지 + VLM 결과)
  ├── 3. 패턴 분석 (공통 위협, 위치별 빈도)
  ├── 4. 권장 조치 사항
  └── 5. 결론
    │
    ▼
PDF 렌더링 (ReportLab) → 파일 저장
    │
    ▼
보고서 메타데이터 DB 저장
```

### 7.3 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/reports/generate` | 보고서 생성 |
| `GET` | `/api/reports` | 보고서 목록 |
| `GET` | `/api/reports/{id}/download` | PDF 다운로드 |
| `GET` | `/api/reports/{id}` | 보고서 메타데이터 |
| `DELETE` | `/api/reports/{id}` | 보고서 삭제 |
| `GET` | `/api/reports/stats` | 보고서 통계 |

---

## 8. 기능 명세: 문서 관리

### 8.1 문서 업로드 및 인덱싱

```
파일 업로드 (PDF/DOCX/TXT/MD)
    │
    ▼
파일 파싱 (pypdf, python-docx, markdown)
    │
    ▼
텍스트 청킹 (chunk_size=512, overlap=50)
    │
    ▼
벡터 임베딩 (bge-small-en-v1.5, batch_size=32)
    │
    ▼
Qdrant 저장 (collection: documents, 384차원, Cosine)
    │
    ▼
BM25 인덱스 갱신
    │
    ▼
RAG 캐시 무효화
```

### 8.2 지원 파일 형식

| 형식 | 확장자 | 파서 | 비고 |
|------|--------|------|------|
| PDF | `.pdf` | pypdf | 텍스트 추출 |
| Word | `.docx` | python-docx | 단락별 추출 |
| Text | `.txt` | 내장 | UTF-8 |
| Markdown | `.md` | markdown | HTML 변환 후 추출 |

### 8.3 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/upload` | 문서 업로드 + 인덱싱 |
| `GET` | `/documents` | 문서 목록 |
| `GET` | `/documents/{id}/content` | 문서 내용 조회 |
| `DELETE` | `/documents/{id}` | 문서 삭제 |
| `DELETE` | `/documents` | 전체 문서 삭제 |
| `POST` | `/query/stream` | RAG 질의 (SSE) |
| `GET` | `/collection/stats` | 컬렉션 통계 |

---

## 9. 기능 명세: 로그 수집 및 검색

### 9.1 로그 수집 파이프라인

```
보안 장비 (CCTV/ACU/방화벽)
    │
    ▼
Fluentd 수집 → HTTP POST /api/logs/ingest
    │
    ▼
LogIndexer:
  ├── PostgreSQL 저장 (log_index 테이블)
  ├── Qdrant 벡터화 (security_logs 컬렉션)
  └── 메타데이터 인덱싱
```

### 9.2 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/logs/ingest` | 배치 로그 수집 |
| `POST` | `/api/logs/search` | 벡터 유사도 검색 |
| `GET` | `/api/logs/stats` | 로그 통계 |
| `GET` | `/api/logs/health` | 헬스체크 |

---

## 10. 기능 명세: API 코드 자동 생성기

### 10.1 개요

네트워크 스캔으로 발견된 장치를 LLM이 분석하고, 해당 장치용 프로토콜 어댑터 코드를 자동 생성하는 시스템.

### 10.2 워크플로우

```
1. /control/network/scan        → 장치 발견
2. /generator/analyze           → LLM 기반 장치 분석 (API 스펙 추론)
3. /generator/generate          → 어댑터 코드 자동 생성
4. /generator/artifact/preview  → 생성 코드 미리보기
5. /generator/review/submit     → 코드 리뷰 제출
6. /generator/review/{id}/approve → 승인
7. /generator/deploy            → 시스템 배포
```

### 10.3 관련 파일

| 파일 | 역할 |
|------|------|
| `backend/services/api_generator/analyzer.py` | LLM 기반 장치 분석 |
| `backend/services/api_generator/generators/` | 코드 생성기 |
| `backend/services/api_generator/spec_extractor.py` | API 스펙 추출 |
| `backend/services/api_generator/doc_parser.py` | 문서 파서 |
| `backend/services/api_generator/review/` | 코드 리뷰 시스템 |
| `backend/services/api_generator/templates/` | 코드 템플릿 |
| `backend/services/api_generator/prompts/` | LLM 프롬프트 |

---

## 11. 기능 명세: 인증 및 보안

### 11.1 JWT 인증

| 항목 | 설정 |
|------|------|
| 알고리즘 | HS256 |
| 토큰 만료 | 30분 (설정 가능) |
| 비밀번호 해싱 | bcrypt (passlib) |
| 비밀 키 | 환경변수 `JWT_SECRET_KEY` |

### 11.2 사용자 역할

| 역할 | 권한 |
|------|------|
| `admin` | 전체 시스템 접근, 사용자 관리, 서버 제어 |
| `operator` | 장치 제어, 알람 관리, 보고서 생성 |
| `user` | 읽기 전용, 채팅, 문서 열람 |

### 11.3 보안 계층

```
┌──────────────────────────────────────────────────┐
│                  Security Layer                    │
│                                                    │
│  ┌──────────────┐    ┌──────────────────────────┐ │
│  │  JWT Auth     │    │  Credential Manager      │ │
│  │  (HS256)      │    │  (Fernet AES-128-CBC)    │ │
│  └──────────────┘    └──────────────────────────┘ │
│                                                    │
│  ┌──────────────┐    ┌──────────────────────────┐ │
│  │  Rate Limiter │    │  Audit Logger            │ │
│  │  Auth: 5/5min │    │  모든 제어 명령 기록      │ │
│  │  API: 100/min │    │  인증 정보 접근 기록      │ │
│  │  Ctrl: 30/min │    │  사용자·시간·결과         │ │
│  └──────────────┘    └──────────────────────────┘ │
│                                                    │
│  ┌──────────────┐    ┌──────────────────────────┐ │
│  │  CORS         │    │  Input Validation        │ │
│  │  (설정 가능)   │    │  (Pydantic v2)           │ │
│  └──────────────┘    └──────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 11.4 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/auth/token` | OAuth2 토큰 발급 |
| `POST` | `/api/auth/login` | 로그인 |
| `GET` | `/api/auth/me` | 현재 사용자 정보 |
| `POST` | `/api/auth/change-password` | 비밀번호 변경 |
| `GET` | `/api/auth/verify` | 토큰 검증 |
| `POST` | `/api/auth/users` | 사용자 생성 (관리자) |
| `GET` | `/api/auth/users` | 사용자 목록 (관리자) |

---

## 12. 기능 명세: 시스템 관리

### 12.1 서버 프로세스 관리

vLLM/VLM 서버의 시작·중지·재시작을 API로 원격 관리합니다.

- Docker 컨테이너 감지 및 제어
- 프로세스 PID 관리
- 헬스체크 포트 확인

### 12.2 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/system/servers` | 전체 서버 상태 |
| `GET` | `/system/servers/{type}` | 특정 서버 상태 (llm/vlm) |
| `POST` | `/system/servers/{type}/start` | 서버 시작 |
| `POST` | `/system/servers/{type}/stop` | 서버 중지 |
| `POST` | `/system/servers/{type}/restart` | 서버 재시작 |
| `GET` | `/health` | 전체 시스템 헬스체크 |

---

## 13. 프론트엔드 아키텍처

### 13.1 페이지 구조

```
App.tsx (BrowserRouter)
 └─ MainLayout (Sidebar + Content)
     ├─ / .................. DashboardPage   (시스템 개요)
     ├─ /chat .............. ChatPage        (RAG 채팅)
     ├─ /analysis .......... AnalysisPage    (이미지 분석)
     ├─ /control ........... ControlPage     (장치 제어)
     ├─ /documents ......... DocumentsPage   (문서 관리)
     ├─ /reports ........... ReportsPage     (보고서)
     └─ /settings .......... SettingsPage    (설정)
```

### 13.2 상태 관리 (Zustand Stores)

| 스토어 | 파일 | 관리 데이터 |
|--------|------|-------------|
| `chatStore` | `stores/chatStore.ts` | 대화 목록, 현재 메시지, 스트리밍 상태 |
| `imageAnalysisStore` | `stores/imageAnalysisStore.ts` | 분석 결과, 이력, 필터 |
| `controlStore` | `stores/controlStore.ts` | 장치 목록, 제어 상태, 명령 이력 |
| `agentStore` | `stores/agentStore.ts` | 에이전트 실행 상태, 도구 호출 |
| `toastStore` | `stores/toastStore.ts` | 토스트 알림 큐 |

### 13.3 API 클라이언트 계층

| 파일 | 역할 |
|------|------|
| `services/api.ts` | 핵심 API (채팅 스트리밍, 문서 업로드, 헬스체크) |
| `services/securityApi.ts` | 보안/알람 API + WebSocket |
| `services/imageAnalysisApi.ts` | 이미지 분석 API |
| `services/controlApi.ts` | 장치 제어 API |
| `services/sseClient.ts` | SSE(Server-Sent Events) 클라이언트 |

### 13.4 컴포넌트 구조

```
components/
├── Chat/
│   ├── ChatMessage.tsx        # 메시지 렌더링 (마크다운 지원)
│   ├── CodeBlock.tsx          # 코드 구문 강조
│   ├── RAGMetrics.tsx         # RAG 검색 지표
│   └── RetrievalContext.tsx   # 검색된 문서 컨텍스트
│
├── ImageAnalysis/
│   ├── ImageUploadCard.tsx    # 이미지 업로드 UI
│   ├── AnalysisDashboard.tsx  # 분석 대시보드
│   ├── AnalysisResultCard.tsx # 개별 분석 결과
│   ├── AnalysisHistory.tsx    # 분석 이력
│   ├── AnalysisFilter.tsx     # 필터/검색
│   ├── ImageSearchPanel.tsx   # 유사 이미지 검색
│   ├── IncidentStats.tsx      # 사고 통계
│   └── ReportViewer.tsx       # 보고서 뷰어
│
├── Control/
│   ├── CameraGrid.tsx         # 카메라 그리드
│   ├── CameraCard.tsx         # 개별 카메라 카드
│   ├── DoorGrid.tsx           # 출입문 그리드
│   ├── DoorCard.tsx           # 개별 출입문 카드
│   ├── PTZControl.tsx         # PTZ 조이스틱 제어
│   ├── CommandBar.tsx         # 자연어 명령 입력
│   ├── NetworkDiscovery.tsx   # 네트워크 장치 탐색
│   ├── CredentialUpdateForm.tsx # 인증정보 관리
│   ├── AuditLogPanel.tsx      # 감사 로그
│   ├── RateLimitPanel.tsx     # 속도 제한 설정
│   └── ZoneListPanel.tsx      # 보안 구역 관리
│
├── Document/
│   ├── DocumentUpload.tsx     # 문서 업로드
│   ├── DocumentList.tsx       # 문서 목록
│   ├── DocumentManager.tsx    # 문서 관리
│   └── DocumentViewer.tsx     # 문서 미리보기
│
├── common/
│   ├── ErrorBoundary.tsx      # 에러 바운더리
│   ├── Toast.tsx              # 토스트 알림
│   ├── ToastContainer.tsx     # 토스트 컨테이너
│   ├── LoadingSpinner.tsx     # 로딩 스피너
│   ├── LLMStatusIndicator.tsx # LLM 상태 표시
│   └── ServerControlPanel.tsx # 서버 제어
│
├── RAGPanel/                  # RAG 설정 패널
├── Security/                  # 보안 전용 컴포넌트
├── Settings/                  # 설정 컴포넌트
├── Agent/                     # 에이전트 관련
└── Sidebar/                   # 사이드바 네비게이션
```

### 13.5 기술 특성

| 특성 | 구현 |
|------|------|
| 코드 분할 | React `lazy()` + `Suspense`로 페이지별 코드 분할 |
| 에러 처리 | `ErrorBoundary`로 페이지별 에러 격리 |
| 데이터 페칭 | TanStack React Query v5 (자동 캐싱, 리페칭) |
| 스타일링 | Tailwind CSS v4 (JIT 컴파일) |
| 빌드 | Vite 7 (esbuild + Rollup) |
| 테스트 | Vitest + Testing Library |
| SSE 스트리밍 | 커스텀 SSE 클라이언트 (EventSource 대체) |

---

## 14. 데이터베이스 스키마

### 14.1 PostgreSQL 테이블 (7개)

#### devices (장비 등록)
```sql
CREATE TABLE devices (
    device_id      VARCHAR(50) PRIMARY KEY,
    device_type    VARCHAR(20) NOT NULL,     -- 'CCTV' | 'ACU'
    manufacturer   VARCHAR(50) NOT NULL,     -- '한화' | '슈프리마' | '제네틱' | '머큐리'
    ip_address     VARCHAR(45) NOT NULL,
    port           INTEGER NOT NULL,
    protocol       VARCHAR(10) NOT NULL,     -- 'SSH' | 'REST' | 'SNMP'
    model          VARCHAR(100),
    location       VARCHAR(200),
    zone           VARCHAR(100),
    status         VARCHAR(20) DEFAULT 'offline',
    credentials_encrypted TEXT,              -- Fernet 암호화 JSON
    last_health_check TIMESTAMP,
    cpu_usage      DECIMAL(5,2),
    memory_usage   DECIMAL(5,2),
    uptime_seconds BIGINT,
    registered_by  VARCHAR(100),
    registered_at  TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW(),
    UNIQUE(ip_address, port)
);
```

#### device_controls (제어 이력)
```sql
CREATE TABLE device_controls (
    control_id        SERIAL PRIMARY KEY,
    device_id         VARCHAR(50) REFERENCES devices(device_id),
    command           VARCHAR(100) NOT NULL,
    parameters        JSONB,
    status            VARCHAR(20) NOT NULL,  -- pending|executing|success|failed|rollback
    result            TEXT,
    error_message     TEXT,
    rollback_required BOOLEAN DEFAULT FALSE,
    rollback_command  VARCHAR(100),
    rollback_status   VARCHAR(20),
    executed_by       VARCHAR(100) NOT NULL,
    executed_at       TIMESTAMP DEFAULT NOW(),
    completed_at      TIMESTAMP,
    execution_time_ms INTEGER
);
```

#### alarms (보안 알람)
```sql
CREATE TABLE alarms (
    alarm_id      VARCHAR(100) PRIMARY KEY,
    alarm_type    VARCHAR(50) NOT NULL,
    severity      VARCHAR(20) NOT NULL,      -- CRITICAL|HIGH|MEDIUM|LOW
    location      VARCHAR(200) NOT NULL,
    zone          VARCHAR(100),
    timestamp     TIMESTAMP NOT NULL,
    device_id     VARCHAR(50),
    image_path    VARCHAR(500),
    vlm_analysis  JSONB,
    is_processed  BOOLEAN DEFAULT FALSE,
    metadata      JSONB,
    kafka_offset  BIGINT,
    created_at    TIMESTAMP DEFAULT NOW()
);
```

#### conversations (대화 세션)
```sql
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(100) DEFAULT 'anonymous',
    title           VARCHAR(200),
    mode            VARCHAR(50) DEFAULT 'qa',
    is_active       BOOLEAN DEFAULT TRUE,
    message_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

#### conversation_messages (대화 메시지)
```sql
CREATE TABLE conversation_messages (
    message_id         SERIAL PRIMARY KEY,
    conversation_id    UUID REFERENCES conversations(conversation_id),
    role               VARCHAR(20) NOT NULL,  -- user|assistant|system|function
    content            TEXT NOT NULL,
    metadata           JSONB,
    source_documents   JSONB,
    retriever_strategy VARCHAR(50),
    created_at         TIMESTAMP DEFAULT NOW()
);
```

#### reports (보고서)
```sql
CREATE TABLE reports (
    report_id       SERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    report_type     VARCHAR(50) DEFAULT 'alarm_analysis',
    alarm_ids       TEXT[],
    analysis_summary TEXT,
    risk_level      VARCHAR(20),
    pdf_path        VARCHAR(500),
    file_size_kb    INTEGER,
    total_alarms    INTEGER,
    critical_count  INTEGER,
    generated_at    TIMESTAMP DEFAULT NOW()
);
```

#### log_index (로그 인덱스)
```sql
CREATE TABLE log_index (
    log_id              SERIAL PRIMARY KEY,
    source_type         VARCHAR(50) NOT NULL,
    source_device_id    VARCHAR(50),
    timestamp           TIMESTAMP NOT NULL,
    log_level           VARCHAR(20),
    raw_message         TEXT,
    qdrant_id           VARCHAR(100),
    qdrant_collection   VARCHAR(50) DEFAULT 'logs',
    indexed_at          TIMESTAMP DEFAULT NOW()
);
```

### 14.2 Qdrant 컬렉션

| 컬렉션 | 벡터 크기 | 거리 함수 | 용도 |
|--------|-----------|-----------|------|
| `documents` | 384 | Cosine | RAG 문서 임베딩 |
| `security_logs` | 384 | Cosine | 보안 로그 임베딩 |

### 14.3 Redis 키 구조

| 키 패턴 | TTL | 용도 |
|---------|-----|------|
| `rag:{hash}` | 3600초 (1시간) | RAG 쿼리-응답 캐시 |
| `conv:{id}` | 86400초 (24시간) | 대화 세션 캐시 |

---

## 15. 인프라 및 배포

### 15.1 Docker Compose 서비스

| 서비스 | 이미지 | 포트 | 프로필 | 의존성 |
|--------|--------|------|--------|--------|
| `frontend` | 빌드 (react-ui) | 9004:80 | 기본 | backend(healthy) |
| `backend` | 빌드 (backend) | 9002:9002 | 기본 | qdrant(healthy) |
| `qdrant` | qdrant/qdrant:latest | 6333, 6334 | 기본 | - |
| `redis` | redis:7-alpine | 6379 | 기본 | - |
| `postgres` | postgres:15-alpine | 5432 | `with-postgres` | - |

### 15.2 GPU 요구사항

| 모델 | GPU | VRAM | 포트 |
|------|-----|------|------|
| Qwen2.5-14B-Instruct-AWQ | GPU 1 (RTX 4000 Ada) | ~10GB | 9000 |
| Qwen2.5-VL-7B-Instruct | GPU 0 (RTX 4000 Ada) | ~8GB | 9001 |
| Embedding (bge-small) | CPU | ~200MB | - |

### 15.3 볼륨 매핑

| 호스트 경로 | 컨테이너 경로 | 용도 |
|-------------|---------------|------|
| `./data/qdrant_storage` | `/qdrant/storage` | 벡터 DB 영속화 |
| `./data/redis_data` | `/data` | Redis 영속화 |
| `./data/postgres_data` | `/var/lib/postgresql/data` | PostgreSQL 영속화 |
| `./data/uploads` | `/app/data/uploads` | 문서 업로드 파일 |
| `./data/logs` | `/app/logs` | 애플리케이션 로그 |
| `./backend/config` | `/app/config:ro` | 설정 파일 (읽기전용) |

### 15.4 환경 변수 요약 (30+ 변수)

| 카테고리 | 변수 | 기본값 | 필수 |
|----------|------|--------|------|
| **환경** | `ENVIRONMENT` | `development` | - |
| **DB** | `POSTGRES_PASSWORD` | - | **필수** |
| **DB** | `POSTGRES_HOST` | `localhost` | - |
| **DB** | `POSTGRES_PORT` | `5432` | - |
| **DB** | `POSTGRES_DB` | `total_llm` | - |
| **LLM** | `VLLM_BASE_URL` | `http://localhost:9000/v1` | - |
| **LLM** | `VLLM_MODEL_NAME` | `/model` | - |
| **VLM** | `VLM_BASE_URL` | `http://localhost:9001/v1` | - |
| **벡터DB** | `QDRANT_HOST` | `localhost` | - |
| **캐시** | `REDIS_HOST` | `localhost` | - |
| **보안** | `JWT_SECRET_KEY` | - | **필수 (프로덕션)** |
| **보안** | `DEVICE_CREDENTIAL_KEY` | - | **필수 (프로덕션)** |
| **API** | `CORS_ORIGINS` | `http://localhost:9004` | - |

---

## 16. 서비스 간 의존성 맵

```
┌─────────────────────────────────────────────────────────────┐
│                    Service Dependency Graph                    │
│                                                               │
│  security_chat_api ─────┬── CommandOrchestrator              │
│                         ├── LLM Client (vLLM:9000)           │
│                         ├── CacheService (Redis)             │
│                         └── ConversationService (PostgreSQL) │
│                                                               │
│  CommandOrchestrator ───┬── RAGService                       │
│                         ├── DeviceRegistry (PostgreSQL)       │
│                         └── DeviceControl (PostgreSQL)       │
│                                                               │
│  RAGService ────────────┬── AdaptiveRetriever                │
│                         └── CacheService (Redis)             │
│                                                               │
│  AdaptiveRetriever ─────┬── RAGTool (Qdrant)                │
│                         ├── HybridRetriever (BM25 + Vector)  │
│                         ├── MultiQueryRetriever              │
│                         └── ComplexityAnalyzer               │
│                                                               │
│  VLMAnalyzer ───────────── LLM Client (vLLM:9001)           │
│                                                               │
│  AlarmHandler ──────────┬── PostgreSQL (DB Pool)             │
│                         ├── VLMAnalyzer                       │
│                         └── WebSocketBroadcaster (Port 9003) │
│                                                               │
│  SystemController ──────┬── LLM Client (Function Calling)    │
│                         ├── CCTVController                    │
│                         ├── ACUController                     │
│                         └── Protocol Adapters                │
│                                                               │
│  KafkaConsumer ─────────── AlarmHandler                      │
│  ReportGenerator ───────── PostgreSQL + VLMAnalyzer          │
│  LogIndexer ────────────── PostgreSQL + RAGTool              │
└─────────────────────────────────────────────────────────────┘
```

---

## 17. 개발 현황 및 로드맵

### 17.1 현재 완성도

| 기능 | 완성도 | 상태 | 비고 |
|------|--------|------|------|
| Vision 이미지 분석 | **95%** | 프로덕션 준비 | QA 4단계 분석, 9가지 사고 유형 |
| 문서 RAG QA | **95%** | 프로덕션 준비 | 적응형 검색, 캐싱, 스트리밍 |
| 장치 제어 (CCTV/ACU) | **85%** | 실장치 테스트 필요 | Function Calling, 시뮬레이션 |
| 프론트엔드 UI | **90%** | 기능 완료 | 7개 페이지, 50+ 컴포넌트 |
| 인증/보안 | **80%** | RBAC 추가 예정 | JWT 구현, 역할 기반 권한 |
| 보고서 생성 | **85%** | 기능 완료 | PDF 생성, VLM 통합 |
| 로그 수집 | **80%** | 기능 완료 | Fluentd 연동, 벡터 검색 |
| API 코드 생성기 | **70%** | 개발 중 | LLM 분석, 코드 생성, 리뷰 |
| 대화 지속성 | **80%** | Phase 2 | PostgreSQL + Redis |
| 실시간 알림 | **90%** | 기능 완료 | WebSocket, Kafka |

### 17.2 미완료 항목 및 개선 사항

| 항목 | 우선순위 | 설명 |
|------|----------|------|
| RBAC 권한 시스템 | 높음 | 역할별 API 접근 제어 구현 |
| 실제 장치 통합 테스트 | 높음 | ONVIF/Hanwha/ZKTeco 실장치 검증 |
| 인증 프로덕션화 | 높음 | 임시 인메모리 → PostgreSQL 사용자 저장소 |
| HTTPS/TLS 설정 | 중간 | 프로덕션 SSL 인증서 설정 |
| 멀티 테넌시 | 중간 | 조직/팀별 데이터 격리 |
| 모니터링 대시보드 | 중간 | Prometheus + Grafana 통합 |
| E2E 테스트 | 중간 | Playwright 기반 통합 테스트 |
| 다국어 VLM 프롬프트 | 낮음 | 한국어 이외 언어 지원 |
| 모바일 반응형 UI | 낮음 | 태블릿/모바일 최적화 |

---

## 부록: 프로젝트 디렉토리 구조

```
Total-LLM/
├── backend/
│   ├── main.py                      # FastAPI 엔트리 포인트
│   ├── Dockerfile                   # 백엔드 컨테이너 이미지
│   ├── requirements.txt             # Python 의존성
│   ├── start.sh                     # 시작 스크립트
│   │
│   ├── api/                         # FastAPI 라우터 (10개)
│   │   ├── security_chat_api.py     # RAG 채팅
│   │   ├── control_api.py           # 장치 제어 (23 endpoints)
│   │   ├── image_api.py             # 이미지 분석
│   │   ├── document_api.py          # 문서 관리
│   │   ├── alarm_api.py             # 알람 관리
│   │   ├── device_api.py            # 장비 등록
│   │   ├── report_api.py            # 보고서
│   │   ├── log_ingestion_api.py     # 로그 수집
│   │   ├── system_api.py            # 시스템 관리
│   │   ├── auth_api.py              # 인증
│   │   └── generator_api.py         # API 코드 생성
│   │
│   ├── services/                    # 비즈니스 로직 (11+ 서비스)
│   │   ├── rag_service.py           # RAG 오케스트레이션
│   │   ├── command_orchestrator.py  # 명령 라우팅
│   │   ├── vlm_analyzer.py          # VLM 분석기
│   │   ├── alarm_handler.py         # 알람 처리
│   │   ├── websocket_broadcaster.py # WebSocket 서버
│   │   ├── report_generator.py      # 보고서 생성
│   │   ├── log_indexer.py           # 로그 인덱싱
│   │   ├── device_registry.py       # 장비 등록
│   │   ├── device_control.py        # 장비 제어
│   │   ├── cache_service.py         # Redis 캐싱
│   │   ├── conversation_service.py  # 대화 지속성
│   │   ├── auth_service.py          # JWT 인증
│   │   ├── kafka_consumer.py        # Kafka 소비자
│   │   ├── health_service.py        # 헬스 모니터링
│   │   │
│   │   ├── control/                 # 장치 제어 서브시스템
│   │   │   ├── system_controller.py # LLM Function Calling
│   │   │   ├── cctv_controller.py   # CCTV PTZ/녹화
│   │   │   ├── acu_controller.py    # ACU 출입문
│   │   │   ├── function_schemas.py  # 함수 정의
│   │   │   ├── device_registry.py   # 장치 레지스트리 (JSON)
│   │   │   ├── credential_manager.py# Fernet 암호화
│   │   │   ├── network_discovery.py # ONVIF 탐색
│   │   │   ├── audit_logger.py      # 감사 로깅
│   │   │   ├── rate_limiter.py      # 속도 제한
│   │   │   ├── zone_manager.py      # 구역 관리
│   │   │   ├── connection_health.py # 연결 상태
│   │   │   └── adapters/            # 프로토콜 어댑터
│   │   │       ├── cctv/onvif.py
│   │   │       ├── cctv/base.py
│   │   │       ├── acu/base.py
│   │   │       └── simulation.py
│   │   │
│   │   ├── vision/                  # 비전 분석 모듈
│   │   │   ├── vision_analyzer.py
│   │   │   ├── security_analyzer.py
│   │   │   ├── korean_prompts.py
│   │   │   ├── detection/
│   │   │   │   └── incident_detector.py
│   │   │   ├── models/
│   │   │   │   ├── qwen_vision.py
│   │   │   │   └── model_orchestrator.py
│   │   │   └── templates/
│   │   │       └── report_template.py
│   │   │
│   │   └── api_generator/           # API 코드 자동 생성
│   │       ├── analyzer.py
│   │       ├── spec_extractor.py
│   │       ├── doc_parser.py
│   │       ├── generators/
│   │       ├── prompts/
│   │       ├── review/
│   │       └── templates/
│   │
│   ├── retrievers/                  # RAG 검색기
│   │   ├── adaptive_retriever.py    # 적응형 (전략 선택)
│   │   ├── hybrid_retriever.py      # BM25 + 벡터
│   │   ├── multi_query_retriever.py # 다중 쿼리
│   │   ├── cross_encoder_reranker.py# 재순위화
│   │   ├── bm25_indexer.py          # 키워드 인덱서
│   │   └── query_expander.py        # 쿼리 확장
│   │
│   ├── tools/                       # 도구
│   │   ├── rag_tool.py              # Qdrant RAG 도구
│   │   └── mcp_client.py            # MCP 클라이언트
│   │
│   ├── agents/                      # 에이전트
│   │   ├── mcp_agent.py             # MCP ReAct 에이전트
│   │   └── multi_agent.py           # 멀티 에이전트
│   │
│   ├── functions/                   # LLM 함수 정의
│   │   └── security_functions.py
│   │
│   ├── core/                        # 핵심 유틸
│   │   └── complexity_analyzer.py
│   │
│   ├── config/                      # 설정
│   │   ├── config.yaml
│   │   └── model_config.py
│   │
│   ├── database/                    # DB
│   │   ├── schema.sql
│   │   └── init_db.py
│   │
│   ├── middleware/                   # 미들웨어
│   │   └── tracing.py
│   │
│   └── tests/                       # 테스트
│
├── frontend/
│   └── react-ui/
│       ├── src/
│       │   ├── App.tsx              # 라우팅
│       │   ├── main.tsx             # 엔트리 포인트
│       │   ├── pages/               # 7개 페이지
│       │   ├── components/          # 50+ 컴포넌트 (10개 폴더)
│       │   ├── services/            # 5개 API 클라이언트
│       │   ├── stores/              # 5개 Zustand 스토어
│       │   ├── hooks/               # 커스텀 훅
│       │   ├── types/               # TypeScript 타입
│       │   ├── layouts/             # 레이아웃
│       │   └── utils/               # 유틸리티
│       ├── package.json
│       ├── vite.config.ts
│       └── Dockerfile
│
├── services/
│   ├── vllm/                        # vLLM 실행 스크립트
│   │   ├── run_vllm.sh
│   │   ├── run_qwen2.5_14b.sh
│   │   └── run_qwen2.5_14b_tp2.sh
│   └── mcp/                         # MCP 서버
│       ├── search_server.py
│       └── math_server.py
│
├── data/                            # 데이터 저장소
│   ├── qdrant_storage/              # 벡터 DB
│   ├── redis_data/                  # Redis
│   ├── postgres_data/               # PostgreSQL
│   ├── uploads/                     # 문서 업로드
│   ├── documents/                   # 문서 원본
│   └── device_registry/             # 장치 레지스트리
│
├── docs/                            # 프로젝트 문서
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   ├── DEPLOYMENT.md
│   ├── DEVELOPMENT.md
│   └── FUNCTIONAL_SPECIFICATION.md  # ← 본 문서
│
├── scripts/                         # 유틸 스크립트
│   ├── backup.sh
│   ├── restore.sh
│   └── generate-secrets.sh
│
├── fluentd/                         # 로그 수집
│   ├── docker-compose.yml
│   └── fluent.conf
│
├── docker-compose.yml               # 메인 Docker Compose
├── .env.example                     # 환경 변수 템플릿
├── start_all.sh                     # 전체 서비스 시작
├── stop_all.sh                      # 전체 서비스 중지
└── README.md                        # 프로젝트 개요
```

---

*본 문서는 소스 코드 분석을 기반으로 자동 생성되었습니다.*
*마지막 업데이트: 2026-03-20*
