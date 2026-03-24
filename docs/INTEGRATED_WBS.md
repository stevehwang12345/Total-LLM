# Total-LLM 통합 프로젝트 WBS (Work Breakdown Structure)

## 프로젝트 개요

**프로젝트명**: Total-LLM - Qwen 기반 통합 AI 플랫폼
**목표**: 3가지 독립 기능을 통합한 엔터프라이즈 AI 플랫폼 구축
**기간**: 8 Phase, 총 180개 태스크

### 기술 스택

| 구분 | 기술 |
|------|------|
| **기능 제어** | Qwen2.5-0.5B-Instruct (Function Calling) |
| **이미지 분석** | Qwen2-VL-7B-Instruct |
| **텍스트 LLM** | Qwen2.5-14B-AWQ (vLLM) |
| **벡터 DB** | Qdrant |
| **Backend** | FastAPI, LangGraph |
| **Frontend** | React 18, TypeScript |
| **인프라** | Docker Compose, Ollama |

---

## 핵심 기능 (3가지 독립 기능)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Total-LLM 통합 플랫폼 아키텍처                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────────────┐  │
│  │ 기능 1            │ │ 기능 2            │ │ 기능 3                    │  │
│  │ 이미지 분석       │ │ 문서 RAG QA       │ │ 외부 시스템 제어          │  │
│  │                   │ │                   │ │                           │  │
│  │ Qwen2-VL-7B      │ │ Qwen2.5-14B-AWQ   │ │ Qwen2.5-0.5B-Instruct    │  │
│  │ 14GB VRAM        │ │ vLLM Server       │ │ ~1GB VRAM                 │  │
│  │                   │ │                   │ │ Function Calling          │  │
│  │ • CCTV 이미지    │ │ • 질문 입력       │ │                           │  │
│  │ • 사고 감지       │ │ • RAG 검색        │ │ • ACU 제어 (출입통제)     │  │
│  │ • 보고서 생성     │ │ • Agent 응답      │ │ • CCTV 제어 (카메라)      │  │
│  └─────────┬─────────┘ └─────────┬─────────┘ └─────────────┬─────────────┘  │
│            │                     │                         │                │
│            ▼                     ▼                         ▼                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        FastAPI Backend (Port 9002)                     │  │
│  │   /image/analyze    /query    /agent    /control/acu    /control/cctv │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                       │                                      │
│                                       ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Infrastructure Layer                               │  │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │  │
│  │   │ Qdrant  │  │  Redis  │  │ Ollama  │  │  vLLM   │  │  Nginx  │    │  │
│  │   │ :6333   │  │  :6379  │  │ :11434  │  │  :9000  │  │  :9004  │    │  │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                       │                                      │
│                    ┌──────────────────┼──────────────────┐                  │
│                    ▼                  ▼                  ▼                  │
│            ┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │
│            │  ACU 시스템  │    │ CCTV 시스템  │    │  기타 IoT   │           │
│            │ (출입통제)   │    │ (카메라제어) │    │   시스템    │           │
│            └─────────────┘    └─────────────┘    └─────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 기능 1: 이미지 분석 (Vision Analysis)
- **입력**: CCTV 캡처, 보안 카메라 이미지
- **모델**: Qwen2-VL-7B-Instruct (14GB VRAM)
- **처리**: 이미지 분석 → 사고 감지 (9유형/5심각도) → 한글 보고서 생성
- **출력**: 분석 결과 + 보안 보고서 (Markdown/PDF)

### 기능 2: 문서 RAG Agent QA
- **입력**: 사용자 자연어 질문
- **모델**: Qwen2.5-14B-AWQ (vLLM 서버)
- **처리**: 문서 벡터 검색 (Qdrant) → LangGraph Multi-Agent → LLM 응답 생성
- **출력**: RAG 기반 Agent 질의응답 (SSE 스트리밍)

### 기능 3: 외부 시스템 제어 (Function Calling)
- **입력**: 사용자 자연어 명령 (예: "1번 출입문 열어줘", "CCTV 3번 녹화 시작")
- **모델**: Qwen2.5-0.5B-Instruct (~1GB VRAM)
- **처리**: 명령 파싱 → Function Calling → 외부 시스템 API 호출
- **출력**: 제어 결과 및 상태 응답
- **지원 시스템**:
  - **ACU (출입통제장치)**: 출입문 개폐, 잠금/해제, 출입 이력 조회, 권한 관리
  - **CCTV (영상감시)**: PTZ 제어 (Pan/Tilt/Zoom), 녹화 시작/중지, 프리셋 이동, 상태 조회

#### Function Calling 스키마 예시

**ACU 제어 함수**:
```json
{
  "name": "unlock_door",
  "description": "지정된 출입문을 열기 (잠금 해제)",
  "parameters": {
    "type": "object",
    "properties": {
      "door_id": {"type": "string", "description": "출입문 ID (예: 'door_01')"},
      "duration": {"type": "integer", "description": "개방 유지 시간(초)", "default": 5}
    },
    "required": ["door_id"]
  }
}
```

**CCTV 제어 함수**:
```json
{
  "name": "move_camera",
  "description": "CCTV 카메라 PTZ 제어",
  "parameters": {
    "type": "object",
    "properties": {
      "camera_id": {"type": "string", "description": "카메라 ID (예: 'cam_03')"},
      "pan": {"type": "number", "description": "수평 이동각 (-180 ~ 180)"},
      "tilt": {"type": "number", "description": "수직 이동각 (-90 ~ 90)"},
      "zoom": {"type": "number", "description": "줌 레벨 (1x ~ 20x)"}
    },
    "required": ["camera_id"]
  }
}
```

---

## 마일스톤 정의

| 마일스톤 | Phase | 완료 기준 |
|---------|-------|----------|
| M1 | Phase 1 | 프로젝트 구조 및 개발 환경 구축 완료 |
| M2 | Phase 2 | 외부 시스템 제어 모듈 (ACU/CCTV) 구현 완료 |
| M3 | Phase 3 | Vision 서비스 통합 완료 |
| M4 | Phase 4 | RAG Agent 서비스 통합 완료 |
| M5 | Phase 5 | API 엔드포인트 구현 완료 |
| M6 | Phase 6 | 프론트엔드 개발 완료 |
| M7 | Phase 7 | Docker 통합 배포 환경 구축 완료 |
| M8 | Phase 8 | 테스트 및 문서화 완료 |

---

## 의존성 다이어그램

```
Phase 1 (환경 설정)
    │
    ├──► Phase 2 (외부 시스템 제어: ACU/CCTV) ─────────┐
    │                                                   │
    ├──► Phase 3 (Vision 서비스) ──┐                   │
    │                              │                   │
    ├──► Phase 4 (RAG Agent) ─────┼──► Phase 5 (API) ─┼──► Phase 6 (Frontend)
    │                              │         │         │         │
    └──► Phase 7 (Docker) ────────┴─────────┴─────────┘         │
                                                                 │
                                            Phase 8 (테스트/문서화) ◄─┘
```

---

## Phase 1: 프로젝트 환경 설정 (20개 태스크)

### 1.1 디렉토리 구조 설정 (8개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 1.1.1 | 프로젝트 루트 구조화 | Total-LLM 디렉토리 정리 | - | 디렉토리 구조 |
| 1.1.2 | backend 구조 설정 | FastAPI 프로젝트 구조 | 1.1.1 | backend/ |
| 1.1.3 | frontend 구조 설정 | React 프로젝트 구조 | 1.1.1 | frontend/ |
| 1.1.4 | services 구조 설정 | 마이크로서비스 구조 | 1.1.1 | services/ |
| 1.1.5 | docs 디렉토리 생성 | 문서화 디렉토리 | 1.1.1 | docs/ |
| 1.1.6 | tests 디렉토리 구조화 | 테스트 디렉토리 | 1.1.1 | tests/ |
| 1.1.7 | config 디렉토리 설정 | 설정 파일 디렉토리 | 1.1.1 | config/ |
| 1.1.8 | scripts 디렉토리 설정 | 유틸리티 스크립트 | 1.1.1 | scripts/ |

### 1.2 개발 환경 설정 (12개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 1.2.1 | Python 가상환경 설정 | Python 3.11+ venv | 1.1.2 | venv/ |
| 1.2.2 | requirements.txt 통합 | 전체 의존성 통합 | 1.2.1 | requirements.txt |
| 1.2.3 | Ollama 설치 및 설정 | 로컬 LLM 서버 | - | Ollama 환경 |
| 1.2.4 | Qwen2.5-0.5B 모델 다운로드 | Function Calling 모델 | 1.2.3 | 모델 파일 |
| 1.2.5 | Qwen2-VL-7B 모델 설정 | Vision 모델 | 1.2.1 | 모델 설정 |
| 1.2.6 | vLLM 서버 설정 | Qwen2.5-14B 서버 | 1.2.1 | vLLM 설정 |
| 1.2.7 | Node.js 환경 설정 | Node.js 18+ | 1.1.3 | node 환경 |
| 1.2.8 | .env 파일 설정 | 환경변수 설정 | 1.1.7 | .env |
| 1.2.9 | config.yaml 작성 | 통합 설정 파일 | 1.1.7 | config.yaml |
| 1.2.10 | Qdrant 설정 | 벡터 DB 설정 | 1.2.1 | Qdrant 설정 |
| 1.2.11 | GPU 환경 확인 | CUDA 설정 확인 | - | GPU 확인 |
| 1.2.12 | 개발 도구 설정 | pytest, black, ruff | 1.2.1 | pyproject.toml |

---

## Phase 2: 외부 시스템 제어 모듈 구현 (30개 태스크)

### 2.1 Function Calling 엔진 (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 2.1.1 | SystemController 클래스 설계 | 제어 인터페이스 | 1.2.4 | 설계 문서 |
| 2.1.2 | Qwen2.5-0.5B 로더 구현 | Ollama/HF 로딩 | 2.1.1 | system_controller.py |
| 2.1.3 | 함수 스키마 정의 | JSON Schema 정의 | 2.1.1 | function_schemas.py |
| 2.1.4 | ACU 함수 선언 | 출입통제 함수들 | 2.1.3 | acu_functions.py |
| 2.1.5 | CCTV 함수 선언 | 영상감시 함수들 | 2.1.3 | cctv_functions.py |
| 2.1.6 | 시스템 상태 함수 선언 | 전체 상태 조회 | 2.1.3 | status_functions.py |
| 2.1.7 | 프롬프트 템플릿 작성 | FC 프롬프트 | 2.1.3 | prompts.py |
| 2.1.8 | JSON 파싱 로직 구현 | 응답 파싱 | 2.1.2 | parser.py |
| 2.1.9 | 에러 핸들링 구현 | 예외 처리 | 2.1.8 | system_controller.py |
| 2.1.10 | 응답 포맷터 구현 | 사용자 친화적 응답 | 2.1.9 | response_formatter.py |

### 2.2 ACU (출입통제) 기능 (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 2.2.1 | ACUController 클래스 설계 | ACU 인터페이스 | 2.1.4 | acu_controller.py |
| 2.2.2 | unlock_door() 구현 | 출입문 열기 | 2.2.1 | acu_controller.py |
| 2.2.3 | lock_door() 구현 | 출입문 잠금 | 2.2.1 | acu_controller.py |
| 2.2.4 | get_door_status() 구현 | 출입문 상태 조회 | 2.2.1 | acu_controller.py |
| 2.2.5 | get_access_log() 구현 | 출입 이력 조회 | 2.2.1 | acu_controller.py |
| 2.2.6 | grant_access() 구현 | 출입 권한 부여 | 2.2.1 | acu_controller.py |
| 2.2.7 | revoke_access() 구현 | 출입 권한 취소 | 2.2.1 | acu_controller.py |
| 2.2.8 | emergency_unlock_all() 구현 | 비상 전체 개방 | 2.2.1 | acu_controller.py |
| 2.2.9 | ACU 프로토콜 어댑터 | 외부 API 연동 | 2.2.2-2.2.8 | acu_adapter.py |
| 2.2.10 | ACU 단위 테스트 | 기능 테스트 | 2.2.9 | test_acu.py |

### 2.3 CCTV (영상감시) 기능 (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 2.3.1 | CCTVController 클래스 설계 | CCTV 인터페이스 | 2.1.5 | cctv_controller.py |
| 2.3.2 | move_camera() 구현 | PTZ 이동 제어 | 2.3.1 | cctv_controller.py |
| 2.3.3 | zoom_camera() 구현 | 줌 인/아웃 | 2.3.1 | cctv_controller.py |
| 2.3.4 | go_to_preset() 구현 | 프리셋 이동 | 2.3.1 | cctv_controller.py |
| 2.3.5 | start_recording() 구현 | 녹화 시작 | 2.3.1 | cctv_controller.py |
| 2.3.6 | stop_recording() 구현 | 녹화 중지 | 2.3.1 | cctv_controller.py |
| 2.3.7 | get_camera_status() 구현 | 카메라 상태 조회 | 2.3.1 | cctv_controller.py |
| 2.3.8 | capture_snapshot() 구현 | 스냅샷 캡처 | 2.3.1 | cctv_controller.py |
| 2.3.9 | CCTV 프로토콜 어댑터 | ONVIF/외부 API | 2.3.2-2.3.8 | cctv_adapter.py |
| 2.3.10 | CCTV 단위 테스트 | 기능 테스트 | 2.3.9 | test_cctv.py |

---

## Phase 3: Vision 서비스 구현 (25개 태스크)

### 3.1 VLM Analyzer 서비스 (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 3.1.1 | VLMAnalyzer 클래스 설계 | 분석기 인터페이스 | 1.2.5 | 설계 문서 |
| 3.1.2 | Qwen2-VL 모델 로더 구현 | 모델 로딩 | 3.1.1 | vlm_analyzer.py |
| 3.1.3 | GPU 디바이스 관리 | 디바이스 할당 | 3.1.2 | vlm_analyzer.py |
| 3.1.4 | 이미지 전처리 파이프라인 | PIL 처리 | 3.1.2 | preprocessor.py |
| 3.1.5 | 프롬프트 템플릿 적용 | 분석 프롬프트 | 3.1.2 | prompts.py |
| 3.1.6 | analyze_image() 구현 | 이미지 분석 | 3.1.4, 3.1.5 | vlm_analyzer.py |
| 3.1.7 | analyze_batch() 구현 | 배치 분석 | 3.1.6 | vlm_analyzer.py |
| 3.1.8 | 메모리 관리 구현 | VRAM 관리 | 3.1.6 | vlm_analyzer.py |
| 3.1.9 | 에러 핸들링 | 예외 처리 | 3.1.6 | vlm_analyzer.py |
| 3.1.10 | 로깅 시스템 통합 | 분석 로그 | 3.1.6 | vlm_analyzer.py |

### 3.2 Incident Detector 서비스 (8개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 3.2.1 | IncidentType Enum 정의 | 9가지 사고 유형 | 3.1.6 | incident_detector.py |
| 3.2.2 | SeverityLevel Enum 정의 | 5단계 심각도 | 3.2.1 | incident_detector.py |
| 3.2.3 | 키워드 패턴 정의 | 한글/영문 패턴 | 3.2.1 | patterns.py |
| 3.2.4 | detect_incident() 구현 | 사고 감지 | 3.2.3 | incident_detector.py |
| 3.2.5 | calculate_confidence() 구현 | 신뢰도 계산 | 3.2.4 | incident_detector.py |
| 3.2.6 | get_severity() 구현 | 심각도 결정 | 3.2.4 | incident_detector.py |
| 3.2.7 | 다국어 패턴 지원 | 한글/영어 | 3.2.3 | patterns.py |
| 3.2.8 | 단위 테스트 작성 | 감지 테스트 | 3.2.4 | test_detector.py |

### 3.3 Report Generator 서비스 (7개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 3.3.1 | ReportTemplate 클래스 설계 | 템플릿 설계 | 3.2.4 | report_template.py |
| 3.3.2 | 헤더 생성 로직 | 보고서 헤더 | 3.3.1 | report_template.py |
| 3.3.3 | 분석 섹션 생성 | 분석 내용 | 3.3.1 | report_template.py |
| 3.3.4 | 권장 조치 생성 | 조치사항 | 3.3.1 | report_template.py |
| 3.3.5 | format_report() 구현 | 전체 보고서 | 3.3.2-3.3.4 | report_template.py |
| 3.3.6 | PDF 변환 기능 | Markdown→PDF | 3.3.5 | pdf_generator.py |
| 3.3.7 | 보고서 저장 기능 | 파일 저장 | 3.3.5 | report_storage.py |

---

## Phase 4: RAG Agent 서비스 구현 (25개 태스크)

### 4.1 RAG 검색 엔진 (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 4.1.1 | Qdrant 클라이언트 설정 | 벡터 DB 연결 | 1.2.10 | qdrant_client.py |
| 4.1.2 | Embedding 모델 설정 | BGE-small 설정 | 4.1.1 | embedder.py |
| 4.1.3 | documents 컬렉션 생성 | 문서 컬렉션 | 4.1.1 | collections.py |
| 4.1.4 | 문서 인덱싱 파이프라인 | 문서 임베딩 | 4.1.2 | indexer.py |
| 4.1.5 | 유사도 검색 구현 | 벡터 검색 | 4.1.3 | searcher.py |
| 4.1.6 | 하이브리드 검색 구현 | 키워드+벡터 | 4.1.5 | hybrid_search.py |
| 4.1.7 | 검색 결과 리랭킹 | 결과 정렬 | 4.1.5 | reranker.py |
| 4.1.8 | 컨텍스트 윈도우 관리 | 토큰 제한 | 4.1.7 | context_builder.py |
| 4.1.9 | 메타데이터 필터링 | 필터 검색 | 4.1.5 | filters.py |
| 4.1.10 | RAG 단위 테스트 | 검색 테스트 | 4.1.7 | test_rag.py |

### 4.2 LangGraph Agent (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 4.2.1 | AgentState 정의 | 상태 스키마 | 4.1.7 | agent_state.py |
| 4.2.2 | Planner 노드 구현 | 계획 수립 | 4.2.1 | planner_node.py |
| 4.2.3 | Researcher 노드 구현 | RAG 검색 | 4.2.1, 4.1.7 | researcher_node.py |
| 4.2.4 | Analyzer 노드 구현 | 정보 분석 | 4.2.1 | analyzer_node.py |
| 4.2.5 | Responder 노드 구현 | 응답 생성 | 4.2.1 | responder_node.py |
| 4.2.6 | StateGraph 구성 | 그래프 정의 | 4.2.2-4.2.5 | graph.py |
| 4.2.7 | 에지 조건 정의 | 전환 조건 | 4.2.6 | conditions.py |
| 4.2.8 | vLLM 클라이언트 연동 | LLM 호출 | 1.2.6 | llm_client.py |
| 4.2.9 | SSE 스트리밍 구현 | 실시간 응답 | 4.2.5 | streaming.py |
| 4.2.10 | Agent 통합 테스트 | 플로우 테스트 | 4.2.6 | test_agent.py |

### 4.3 도구 통합 (5개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 4.3.1 | RAGTool 구현 | 검색 도구 | 4.1.7 | rag_tool.py |
| 4.3.2 | VisionTool 연동 | Vision 도구 | 3.1.6 | vision_tool.py |
| 4.3.3 | 도구 레지스트리 | 도구 관리 | 4.3.1, 4.3.2 | tool_registry.py |
| 4.3.4 | 도구 스키마 정의 | JSON Schema | 4.3.3 | tool_schemas.py |
| 4.3.5 | 도구 통합 테스트 | 도구 테스트 | 4.3.3 | test_tools.py |

---

## Phase 5: API 엔드포인트 구현 (30개 태스크)

### 5.1 외부 시스템 제어 API (12개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 5.1.1 | control_api.py 생성 | 제어 API 모듈 | 2.3.10 | control_api.py |
| 5.1.2 | POST /control/command 구현 | 자연어 명령 처리 | 5.1.1 | control_api.py |
| 5.1.3 | POST /control/acu/unlock 구현 | 출입문 열기 | 5.1.1 | acu_api.py |
| 5.1.4 | POST /control/acu/lock 구현 | 출입문 잠금 | 5.1.1 | acu_api.py |
| 5.1.5 | GET /control/acu/status 구현 | 출입문 상태 조회 | 5.1.1 | acu_api.py |
| 5.1.6 | GET /control/acu/logs 구현 | 출입 이력 조회 | 5.1.1 | acu_api.py |
| 5.1.7 | POST /control/cctv/move 구현 | PTZ 제어 | 5.1.1 | cctv_api.py |
| 5.1.8 | POST /control/cctv/preset 구현 | 프리셋 이동 | 5.1.1 | cctv_api.py |
| 5.1.9 | POST /control/cctv/record 구현 | 녹화 제어 | 5.1.1 | cctv_api.py |
| 5.1.10 | GET /control/cctv/status 구현 | 카메라 상태 조회 | 5.1.1 | cctv_api.py |
| 5.1.11 | GET /control/status 구현 | 전체 시스템 상태 | 5.1.1 | control_api.py |
| 5.1.12 | 제어 API 라우터 등록 | main.py 등록 | 5.1.2-5.1.11 | main.py |

### 5.2 이미지 분석 API (8개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 5.2.1 | image_api.py 생성 | 이미지 API | 3.3.5 | image_api.py |
| 5.2.2 | POST /image/analyze 구현 | 단일 분석 | 5.2.1 | image_api.py |
| 5.2.3 | POST /image/batch 구현 | 배치 분석 | 5.2.2 | image_api.py |
| 5.2.4 | POST /image/report 구현 | 보고서 생성 | 5.2.1 | image_api.py |
| 5.2.5 | GET /image/{id} 구현 | 결과 조회 | 5.2.1 | image_api.py |
| 5.2.6 | 파일 업로드 처리 | multipart | 5.2.2 | upload.py |
| 5.2.7 | Base64 처리 | Base64 디코딩 | 5.2.2 | image_api.py |
| 5.2.8 | 이미지 API 라우터 등록 | main.py 등록 | 5.2.2-5.2.5 | main.py |

### 5.3 RAG Agent API (9개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 5.3.1 | agent_api.py 생성 | Agent API | 4.2.6 | agent_api.py |
| 5.3.2 | POST /query 구현 | 질의 API | 5.3.1 | agent_api.py |
| 5.3.3 | POST /query/stream 구현 | SSE 스트리밍 | 5.3.2 | agent_api.py |
| 5.3.4 | POST /agent/invoke 구현 | Agent 호출 | 5.3.1 | agent_api.py |
| 5.3.5 | GET /documents 구현 | 문서 목록 | 5.3.1 | agent_api.py |
| 5.3.6 | POST /documents 구현 | 문서 업로드 | 5.3.5 | agent_api.py |
| 5.3.7 | DELETE /documents/{id} 구현 | 문서 삭제 | 5.3.5 | agent_api.py |
| 5.3.8 | WebSocket 엔드포인트 | 실시간 통신 | 5.3.3 | websocket.py |
| 5.3.9 | Agent API 라우터 등록 | main.py 등록 | 5.3.2-5.3.7 | main.py |

---

## Phase 6: 프론트엔드 개발 (25개 태스크)

### 6.1 공통 컴포넌트 (8개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 6.1.1 | React 프로젝트 설정 | Vite + TypeScript | 1.2.7 | 프로젝트 설정 |
| 6.1.2 | 라우팅 설정 | React Router | 6.1.1 | router.tsx |
| 6.1.3 | 상태 관리 설정 | Zustand | 6.1.1 | store/ |
| 6.1.4 | API 클라이언트 설정 | Axios/Fetch | 6.1.1 | api/ |
| 6.1.5 | 공통 UI 컴포넌트 | Button, Input 등 | 6.1.1 | components/ui/ |
| 6.1.6 | 레이아웃 컴포넌트 | Header, Sidebar | 6.1.5 | components/layout/ |
| 6.1.7 | 테마 설정 | Tailwind CSS | 6.1.1 | tailwind.config.js |
| 6.1.8 | 타입 정의 | TypeScript 타입 | 6.1.1 | types/ |

### 6.2 채팅 인터페이스 (9개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 6.2.1 | ChatContainer 구현 | 채팅 컨테이너 | 6.1.6 | ChatContainer.tsx |
| 6.2.2 | MessageList 구현 | 메시지 목록 | 6.2.1 | MessageList.tsx |
| 6.2.3 | MessageItem 구현 | 개별 메시지 | 6.2.2 | MessageItem.tsx |
| 6.2.4 | ChatInput 구현 | 입력 컴포넌트 | 6.2.1 | ChatInput.tsx |
| 6.2.5 | ImageUpload 구현 | 이미지 업로드 | 6.2.4 | ImageUpload.tsx |
| 6.2.6 | StreamingMessage 구현 | SSE 메시지 | 6.2.3 | StreamingMessage.tsx |
| 6.2.7 | 채팅 상태 관리 | chatStore | 6.1.3 | chatStore.ts |
| 6.2.8 | 채팅 API 연동 | API 호출 | 6.1.4 | chatApi.ts |
| 6.2.9 | 채팅 페이지 통합 | ChatPage | 6.2.1-6.2.6 | ChatPage.tsx |

### 6.3 분석 결과 표시 (8개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 6.3.1 | AnalysisResult 구현 | 분석 결과 | 6.2.3 | AnalysisResult.tsx |
| 6.3.2 | IncidentBadge 구현 | 사고 유형 배지 | 6.3.1 | IncidentBadge.tsx |
| 6.3.3 | SeverityIndicator 구현 | 심각도 표시 | 6.3.1 | SeverityIndicator.tsx |
| 6.3.4 | ReportViewer 구현 | 보고서 뷰어 | 6.3.1 | ReportViewer.tsx |
| 6.3.5 | ImagePreview 구현 | 이미지 미리보기 | 6.3.1 | ImagePreview.tsx |
| 6.3.6 | ReportDownload 구현 | 보고서 다운로드 | 6.3.4 | ReportDownload.tsx |
| 6.3.7 | 분석 상태 관리 | analysisStore | 6.1.3 | analysisStore.ts |
| 6.3.8 | 분석 API 연동 | API 호출 | 6.1.4 | analysisApi.ts |

---

## Phase 7: Docker 통합 배포 (20개 태스크)

### 7.1 Docker 이미지 (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 7.1.1 | backend Dockerfile 작성 | FastAPI 이미지 | 5.3.9 | Dockerfile |
| 7.1.2 | frontend Dockerfile 작성 | React 이미지 | 6.3.8 | Dockerfile |
| 7.1.3 | ollama 서비스 설정 | FC 모델 서비스 | 2.3.7 | docker-compose.yml |
| 7.1.4 | vision 서비스 설정 | Vision 모델 서비스 | 3.3.7 | docker-compose.yml |
| 7.1.5 | vllm 서비스 설정 | LLM 서비스 | 4.2.10 | docker-compose.yml |
| 7.1.6 | qdrant 서비스 설정 | 벡터 DB 서비스 | 4.1.10 | docker-compose.yml |
| 7.1.7 | redis 서비스 설정 | 캐시 서비스 | - | docker-compose.yml |
| 7.1.8 | nginx 설정 | 리버스 프록시 | 7.1.2 | nginx.conf |
| 7.1.9 | .dockerignore 작성 | 제외 파일 | 7.1.1 | .dockerignore |
| 7.1.10 | 이미지 빌드 스크립트 | 빌드 자동화 | 7.1.1-7.1.8 | build.sh |

### 7.2 Docker Compose 구성 (10개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 7.2.1 | docker-compose.yml 작성 | 통합 구성 | 7.1.10 | docker-compose.yml |
| 7.2.2 | 네트워크 설정 | 서비스 간 네트워크 | 7.2.1 | docker-compose.yml |
| 7.2.3 | 볼륨 설정 | 데이터 영속성 | 7.2.1 | docker-compose.yml |
| 7.2.4 | GPU 리소스 할당 | NVIDIA GPU | 7.2.1 | docker-compose.yml |
| 7.2.5 | 환경변수 설정 | env_file | 7.2.1 | .env.docker |
| 7.2.6 | 헬스체크 설정 | 서비스 헬스체크 | 7.2.1 | docker-compose.yml |
| 7.2.7 | 의존성 순서 설정 | depends_on | 7.2.1 | docker-compose.yml |
| 7.2.8 | 로깅 설정 | 컨테이너 로깅 | 7.2.1 | docker-compose.yml |
| 7.2.9 | 배포 스크립트 작성 | deploy.sh | 7.2.1 | deploy.sh |
| 7.2.10 | 통합 배포 테스트 | 전체 테스트 | 7.2.9 | 테스트 결과 |

---

## Phase 8: 테스트 및 문서화 (15개 태스크)

### 8.1 테스트 (8개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 8.1.1 | pytest 설정 | 테스트 프레임워크 | 7.2.10 | pytest.ini |
| 8.1.2 | 단위 테스트 통합 | 모든 단위 테스트 | 8.1.1 | tests/unit/ |
| 8.1.3 | 통합 테스트 작성 | API 통합 테스트 | 8.1.1 | tests/integration/ |
| 8.1.4 | E2E 테스트 작성 | 전체 플로우 | 8.1.3 | tests/e2e/ |
| 8.1.5 | 성능 테스트 작성 | 응답 시간 | 8.1.3 | tests/performance/ |
| 8.1.6 | 부하 테스트 작성 | 동시 접속 | 8.1.5 | tests/load/ |
| 8.1.7 | 테스트 커버리지 확인 | 80% 이상 | 8.1.2-8.1.4 | coverage report |
| 8.1.8 | CI 파이프라인 설정 | GitHub Actions | 8.1.7 | .github/workflows/ |

### 8.2 문서화 (7개)

| ID | 태스크 | 설명 | 선행 | 산출물 |
|----|--------|------|------|--------|
| 8.2.1 | README.md 작성 | 프로젝트 개요 | 8.1.7 | README.md |
| 8.2.2 | API 문서 생성 | OpenAPI/Swagger | 8.2.1 | docs/api/ |
| 8.2.3 | 사용자 가이드 작성 | 사용 방법 | 8.2.1 | docs/USER_GUIDE.md |
| 8.2.4 | 개발자 가이드 작성 | 개발 환경 | 8.2.1 | docs/DEVELOPER_GUIDE.md |
| 8.2.5 | 배포 가이드 작성 | 배포 절차 | 8.2.1 | docs/DEPLOYMENT.md |
| 8.2.6 | 아키텍처 문서 작성 | 시스템 구조 | 8.2.1 | docs/ARCHITECTURE.md |
| 8.2.7 | CHANGELOG 작성 | 변경 이력 | 8.2.1 | CHANGELOG.md |

---

## 태스크 요약

| Phase | 영역 | 태스크 수 |
|-------|------|----------|
| Phase 1 | 프로젝트 환경 설정 | 20 |
| Phase 2 | 외부 시스템 제어 (ACU/CCTV) | 30 |
| Phase 3 | Vision 서비스 | 25 |
| Phase 4 | RAG Agent 서비스 | 25 |
| Phase 5 | API 엔드포인트 | 30 |
| Phase 6 | 프론트엔드 | 25 |
| Phase 7 | Docker 배포 | 20 |
| Phase 8 | 테스트/문서화 | 15 |
| **총계** | | **190** |

---

## 리소스 요구사항

### GPU 메모리 (VRAM)

| 모델 | 용도 | VRAM |
|------|------|------|
| Qwen2.5-0.5B-Instruct | 기능 제어 | ~1GB |
| Qwen2-VL-7B-Instruct | 이미지 분석 | ~14GB |
| Qwen2.5-14B-AWQ | RAG Agent | ~10GB |
| **총계** | | **~25GB** |

### 권장 사양

- GPU: NVIDIA RTX 4090 (24GB) × 2 또는 A100 (40GB)
- RAM: 64GB 이상
- Storage: 100GB SSD 이상
- CPU: 16코어 이상

---

## 품질 기준

### 코드 품질
- 테스트 커버리지: ≥80%
- 린트 에러: 0
- 타입 체크 통과: 100%

### 성능 기준
- 기능 제어 라우팅: <100ms
- 이미지 분석: <5s
- RAG 응답 (첫 토큰): <500ms
- 동시 접속: ≥50 users

---

**문서 버전**: 2.0
**최종 수정일**: 2025-01-12
**작성자**: Total-LLM 개발팀
