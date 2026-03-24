# Total-LLM 프로젝트 요약서

## 프로젝트 개요

**Total-LLM**은 LLM 기반 통합 보안 관제 시스템으로, 3가지 핵심 기능을 제공합니다:
1. **CCTV 이미지 분석** - Vision LLM 기반 보안 영상 분석
2. **문서 RAG QA** - 보안 정책/매뉴얼 검색 및 질의응답
3. **외부 시스템 제어** - CCTV PTZ, ACU 출입통제, 네트워크 장치 탐색

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + TypeScript)                 │
│                         http://localhost:9004                    │
├─────────────────────────────────────────────────────────────────┤
│                    Backend (FastAPI + Python)                    │
│                         http://localhost:9002                    │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│  Image API   │   RAG API    │ Control API  │   Device API       │
├──────────────┴──────────────┴──────────────┴────────────────────┤
│                         Services Layer                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │VLM       │ │RAG       │ │System        │ │Network         │  │
│  │Analyzer  │ │Service   │ │Controller    │ │Discovery       │  │
│  └──────────┘ └──────────┘ └──────────────┘ └────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                       External Services                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │vLLM      │ │Qdrant    │ │PostgreSQL│ │Redis     │           │
│  │(9000)    │ │(6333)    │ │(5432)    │ │(6379)    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 주요 기능 1: CCTV 이미지 분석

### 기능 설명
Qwen2-VL 기반 Vision LLM을 활용하여 CCTV 영상/이미지를 분석하고, 보안 사고를 자동 감지합니다.

### 핵심 파일

| 구분 | 파일 경로 | 역할 |
|------|----------|------|
| API | `backend/api/image_api.py` | 이미지 분석 엔드포인트 |
| Service | `backend/services/vlm_analyzer.py` | VLM 분석 로직 |
| Vision | `backend/services/vision/security_analyzer.py` | 보안 분석 |
| Prompts | `backend/services/vision/korean_prompts.py` | 한국어 프롬프트 |
| Frontend | `frontend/react-ui/src/components/ImageAnalysis/` | UI 컴포넌트 |
| API Client | `frontend/react-ui/src/services/imageAnalysisApi.ts` | API 호출 |

### API 엔드포인트

```
POST /image/analyze              # 기본 이미지 분석
POST /image/analyze/qa           # 4단계 QA 구조화 분석
POST /image/analyze/upload       # 파일 업로드 분석
POST /image/report/security      # 보안 보고서 생성
```

### 사고 유형 분류 (9종)
- `VIOLENCE` - 폭력
- `FIGHTING` - 싸움
- `FALLING` - 낙상
- `INTRUSION` - 침입
- `THREATENING` - 위협행위
- `ABNORMAL_BEHAVIOR` - 비정상행동
- `NORMAL` - 정상
- `NO_PERSON` - 사람없음
- `UNCLEAR` - 판단불가

### 현재 상태
- **완료도**: 95%
- **VLM 서버**: vLLM (port 9001) - Qwen2-VL-7B-Instruct

---

## 주요 기능 2: 문서 RAG QA

### 기능 설명
보안 정책, 매뉴얼, 로그 등을 Qdrant 벡터DB에 인덱싱하고, 자연어 질의에 대해 관련 문서를 검색하여 답변을 생성합니다.

### 핵심 파일

| 구분 | 파일 경로 | 역할 |
|------|----------|------|
| API | `backend/api/security_chat_api.py` | RAG 채팅 (SSE 스트리밍) |
| API | `backend/api/document_api.py` | 문서 업로드/관리 |
| Service | `backend/services/rag_service.py` | RAG 오케스트레이션 |
| Retriever | `backend/retrievers/adaptive_retriever.py` | 적응형 검색 |
| Retriever | `backend/retrievers/hybrid_retriever.py` | 하이브리드 검색 |
| Indexer | `backend/services/log_indexer.py` | 로그 인덱싱 |
| Frontend | `frontend/react-ui/src/components/Chat/` | 채팅 UI |
| Frontend | `frontend/react-ui/src/components/Document/` | 문서 관리 UI |
| API Client | `frontend/react-ui/src/services/api.ts` | SSE API 클라이언트 |

### API 엔드포인트

```
POST /api/rag/chat               # SSE 스트리밍 채팅
POST /api/rag/query              # 단일 질의
GET  /api/rag/conversations      # 대화 목록
POST /documents/upload           # 문서 업로드
GET  /documents                  # 문서 목록
DELETE /documents/{id}           # 문서 삭제
```

### 검색 전략
- **Simple Query**: 벡터 검색
- **Medium Query**: 하이브리드 검색 (Vector + BM25)
- **Complex Query**: 다중 쿼리 확장 + 재순위화

### Qdrant 컬렉션
- `documents`: 업로드된 문서
- `security_logs`: 보안 로그

### 현재 상태
- **완료도**: 95%
- **LLM 서버**: vLLM (port 9000) - Qwen2.5-14B-Instruct-AWQ

---

## 주요 기능 3: 외부 시스템 제어

### 기능 설명
LLM Function Calling을 활용하여 자연어 명령으로 CCTV PTZ 제어, ACU 출입통제, 네트워크 장치 탐색/등록을 수행합니다.

### 핵심 파일

| 구분 | 파일 경로 | 역할 |
|------|----------|------|
| API | `backend/api/control_api.py` | 제어 API 엔드포인트 |
| Controller | `backend/services/control/system_controller.py` | 통합 제어 오케스트레이터 |
| CCTV | `backend/services/control/cctv_controller.py` | PTZ/녹화 제어 |
| ACU | `backend/services/control/acu_controller.py` | 출입통제 제어 |
| Discovery | `backend/services/control/network_discovery.py` | 네트워크 장치 탐색 |
| Registry | `backend/services/control/device_registry.py` | 장치 등록/관리 |
| Schemas | `backend/services/control/function_schemas.py` | Function Calling 스키마 |
| Frontend | `frontend/react-ui/src/components/Control/` | 제어 UI |
| Frontend | `frontend/react-ui/src/pages/ControlPage.tsx` | 제어 페이지 |
| API Client | `frontend/react-ui/src/services/controlApi.ts` | API 클라이언트 |

### API 엔드포인트

```
# 자연어 명령
POST /control/command                # 자연어 명령 처리
POST /control/function               # 함수 직접 호출

# CCTV 제어
POST /control/cctv/move              # PTZ 이동
POST /control/cctv/preset            # 프리셋 이동
POST /control/cctv/recording/start   # 녹화 시작/중지
POST /control/cctv/snapshot          # 스냅샷

# ACU 제어
POST /control/acu/unlock             # 출입문 열기
POST /control/acu/lock               # 출입문 잠금
GET  /control/acu/status             # 상태 조회
GET  /control/acu/log                # 출입 이력

# 네트워크 탐색 (신규)
POST /control/network/scan           # 서브넷 스캔
POST /control/network/scan/ip        # 단일 IP 스캔
GET  /control/devices                # 등록된 장치 목록
POST /control/devices/register       # 장치 등록
POST /control/devices/sync           # LLM 제어 동기화
GET  /control/devices/controller-status  # 연동 상태
```

### 지원 제조사 (네트워크 탐색)
- Hanwha Vision (Wisenet)
- Hikvision
- Dahua
- Axis
- ZKTeco (ACU)
- Suprema (ACU)

### 현재 상태
- **완료도**: 85%
- **시뮬레이션 모드**: 기본 활성화 (실제 장치 연결 가능)
- **vLLM Function Calling**: `--enable-auto-tool-choice` 옵션 필요

---

## 서비스 포트 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend (React) | 9004 | 웹 UI |
| Backend (FastAPI) | 9002 | REST API |
| vLLM Text | 9000 | Qwen2.5-14B-Instruct-AWQ |
| vLLM Vision | 9001 | Qwen2-VL-7B-Instruct |
| Qdrant | 6333 | 벡터 DB |
| PostgreSQL | 5432 | 관계형 DB |
| Redis | 6379 | 캐시 |

---

## 시작/종료 명령

### 전체 시작
```bash
cd /home/sphwang/dev/Total-LLM
./start_all.sh
```

### 개별 시작
```bash
# 백엔드
cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 9002 --reload

# 프론트엔드
cd frontend/react-ui && pnpm dev --port 9004

# vLLM (Function Calling 지원)
docker run --gpus '"device=1"' -p 9000:8000 vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-14B-Instruct-AWQ \
  --enable-auto-tool-choice --tool-call-parser hermes
```

### 전체 종료
```bash
./stop_all.sh
# 또는
docker stop vllm-text-server
pkill -f "uvicorn main:app"
```

---

## 설정 파일

| 파일 | 용도 |
|------|------|
| `backend/config/config.yaml` | LLM/VLM/임베딩 설정 |
| `backend/docker-compose.yml` | DB 서비스 (PostgreSQL, Redis, Qdrant) |
| `docker-compose.yml` | 전체 서비스 오케스트레이션 |

---

## 다음 작업 (Cleanup & 개선 방향)

### 즉시 필요
1. [ ] vLLM 시작 스크립트에 `--enable-auto-tool-choice` 옵션 추가
2. [ ] 중복 device_registry.py 통합 (services/ vs services/control/)
3. [ ] 미사용 import 및 dead code 정리

### 단기 개선
1. [ ] 네트워크 탐색 ONVIF 프로토콜 완전 지원
2. [ ] 실제 CCTV/ACU 장치 연동 테스트
3. [ ] 프론트엔드 에러 핸들링 강화
4. [ ] API 응답 표준화 (일관된 응답 형식)

### 중장기 개선
1. [ ] 인증/권한 시스템 추가
2. [ ] 다중 사용자 지원
3. [ ] 알림 시스템 고도화 (이메일, SMS, 푸시)
4. [ ] 대시보드 실시간 모니터링 강화

---

*Last Updated: 2026-01-15*
