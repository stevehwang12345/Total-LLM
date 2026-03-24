# Total-LLM 통합 상태 문서

**최종 업데이트**: 2026-01-13

## 개요

Total-LLM 프로젝트의 3대 핵심 기능 통합 현황입니다.

---

## 1. CCTV 이미지 분석 (Image Analysis)

### 상태: ✅ 완료 (95%)

### 백엔드 구현
| 항목 | 상태 | 파일 |
|------|------|------|
| VLM Analyzer 서비스 | ✅ 완료 | `services/vlm_analyzer.py` |
| Image API 엔드포인트 | ✅ 완료 | `api/image_api.py` |
| main.py 라우터 등록 | ✅ 완료 | `main.py:313` |
| Alarm Handler VLM 통합 | ✅ 완료 | `services/alarm_handler.py` |
| Vision 모듈 통합 | ✅ 신규 완료 | `services/vision/` |

### Vision 모듈 (granite-vision-korean-poc 통합, 2026-01-13)
| 항목 | 상태 | 파일 |
|------|------|------|
| 사고 탐지기 | ✅ 완료 | `services/vision/detection/incident_detector.py` |
| 한국어 프롬프트 | ✅ 완료 | `services/vision/korean_prompts.py` |
| 보고서 템플릿 | ✅ 완료 | `services/vision/templates/report_template.py` |
| 보안 분석기 | ✅ 완료 | `services/vision/security_analyzer.py` |

### 사고 유형 분류 (9종)
| 유형 | 한국어 | 기본 심각도 |
|------|--------|------------|
| VIOLENCE | 폭력 | 매우높음 |
| FIGHTING | 싸움 | 높음 |
| FALLING | 넘어짐/낙상 | 높음 |
| INTRUSION | 침입 | 중간 |
| THREATENING | 위협행위 | 중간 |
| ABNORMAL_BEHAVIOR | 비정상행동 | 중간 |
| NORMAL | 정상 | 정보 |
| NO_PERSON | 분석불가-사람없음 | 정보 |
| UNCLEAR | 판단불가-불분명 | 정보 |

### 프론트엔드 구현
| 항목 | 상태 | 파일 |
|------|------|------|
| imageAnalysisApi.ts | ✅ 완료 | `services/imageAnalysisApi.ts` |
| ImageAnalysisCard 컴포넌트 | ✅ 완료 | `components/vision/` |
| 이미지 업로드 UI | ✅ 완료 | `pages/Dashboard.tsx` |

### API 엔드포인트
```
# 기본 분석
POST /image/analyze           - 이미지 분석
POST /image/analyze/upload    - 이미지 업로드 분석
POST /image/batch             - 배치 분석
GET  /image/{analysis_id}     - 분석 결과 조회
GET  /image/                  - 분석 결과 목록
POST /image/report            - 보고서 생성
GET  /image/health            - 서비스 상태 확인

# QA 기반 구조화 분석 (신규 2026-01-13)
POST /image/analyze/qa          - QA 기반 4단계 구조화 분석
POST /image/analyze/qa/upload   - 파일 업로드로 QA 분석
POST /image/report/security     - 전체 보안 보고서 생성 파이프라인
POST /image/report/security/upload - 파일 업로드로 보안 보고서 생성
```

### VLMAnalyzer 메서드 (2026-01-13 업데이트)
| 메서드 | 설명 | 지원 입력 |
|--------|------|-----------|
| `analyze_qa_based()` | 4단계 QA 기반 구조화 분석 | 파일 경로 또는 Base64 |
| `analyze_with_incident_detection()` | 사고 유형/심각도 자동 감지 | 파일 경로 |
| `generate_security_report()` | 전체 보안 분석 파이프라인 → 마크다운 보고서 | 파일 경로 또는 Base64 |

### QA 기반 분석 응답 형식
```json
{
  "success": true,
  "analysis_id": "91eec72d",
  "timestamp": "2026-01-13T16:20:00",
  "location": "지하 주차장 B1",
  "qa_results": {
    "q1_detection": "폭력/범죄 감지 결과",
    "q2_classification": "사고 유형 분류",
    "q3_subject": "관련 인물 설명",
    "q4_description": "상황 설명"
  },
  "incident_type": "NORMAL",
  "incident_type_ko": "정상",
  "severity": "INFO",
  "severity_ko": "정보",
  "confidence": 0.85,
  "recommended_actions": ["정기 모니터링 계속"]
}
```

### 미완료 항목
- [ ] 실시간 스트리밍 분석 (WebSocket)
- [ ] 배치 분석 진행률 표시

---

## 2. 문서 RAG QA (Document RAG)

### 상태: ✅ 완료 (95%)

### 백엔드 구현
| 항목 | 상태 | 파일 |
|------|------|------|
| RAG Service | ✅ 완료 | `services/rag_service.py` |
| RAG Tool (Qdrant) | ✅ 완료 | `tools/rag_tool.py` |
| Document API | ✅ 완료 | `api/document_api.py` |
| Security Chat API | ✅ 완료 | `api/security_chat_api.py` |
| Log Indexer (분리됨) | ✅ 수정 완료 | `services/log_indexer.py` |

### Qdrant 컬렉션 분리 (2026-01-13 수정)
| 컬렉션 | 용도 | config.yaml 키 |
|--------|------|----------------|
| `documents` | 문서 관리 업로드 (RAG QA) | `collection_name` |
| `security_logs` | 보안 로그 인덱싱 | `logs_collection_name` |

### 프론트엔드 구현
| 항목 | 상태 | 파일 |
|------|------|------|
| api.ts (SSE 스트리밍) | ✅ 완료 | `services/api.ts` |
| ChatArea 컴포넌트 | ✅ 완료 | `components/ChatArea.tsx` |
| DocumentManagement 페이지 | ✅ 완료 | `pages/DocumentManagement.tsx` |
| useConversationStore | ✅ 완료 | `store/conversationStore.ts` |

### API 엔드포인트
```
POST /api/rag/chat         - SSE 스트리밍 채팅
POST /api/rag/query        - 단일 질의
GET  /api/rag/conversations - 대화 목록
DELETE /api/rag/conversations/{id} - 대화 삭제
POST /documents/upload     - 문서 업로드
GET  /documents            - 문서 목록
DELETE /documents/{id}     - 문서 삭제
```

### 수정 완료 (2026-01-13)
- ✅ LogIndexer가 `security_logs` 컬렉션 사용하도록 분리
- ✅ RAG QA가 업로드된 문서만 검색하도록 수정

---

## 3. 외부 시스템 제어 (Control System)

### 상태: ✅ 완료 (85%)

### 백엔드 구현
| 항목 | 상태 | 파일 |
|------|------|------|
| System Controller | ✅ 완료 | `services/control/system_controller.py` |
| ACU Controller | ✅ 완료 | `services/control/acu_controller.py` |
| CCTV Controller | ✅ 완료 | `services/control/cctv_controller.py` |
| Function Schemas | ✅ 완료 | `services/control/function_schemas.py` |
| Control API | ✅ 완료 | `api/control_api.py` |
| main.py 라우터 등록 | ✅ 수정 완료 | `main.py:315` |

### 프론트엔드 구현
| 항목 | 상태 | 파일 |
|------|------|------|
| controlApi.ts | ✅ 수정 완료 | `services/controlApi.ts` |
| types/control.ts | ✅ 완료 | `types/control.ts` |
| ControlPage 컴포넌트 | 🚧 미완료 | - |

### API 엔드포인트 (백엔드)
```
# 자연어 명령
POST /control/command              - 자연어 명령 처리
POST /control/function             - 함수 직접 호출
GET  /control/functions            - 사용 가능 함수 목록

# ACU (출입통제)
POST /control/acu/door/unlock      - 출입문 열기
POST /control/acu/door/lock        - 출입문 잠금
GET  /control/acu/door/status      - 출입문 상태 조회
GET  /control/acu/log              - 출입 이력 조회
POST /control/acu/permission/grant - 권한 부여
POST /control/acu/permission/revoke - 권한 취소
POST /control/acu/emergency/unlock - 비상 전체 개방
POST /control/acu/emergency/lock   - 비상 전체 잠금

# CCTV (영상감시)
POST /control/cctv/camera/move     - PTZ 제어
POST /control/cctv/camera/preset   - 프리셋 이동
POST /control/cctv/camera/preset/save - 프리셋 저장
POST /control/cctv/recording/start - 녹화 시작
POST /control/cctv/recording/stop  - 녹화 중지
POST /control/cctv/snapshot        - 스냅샷 캡처
GET  /control/cctv/camera/status   - 카메라 상태 조회
GET  /control/cctv/recordings      - 녹화 목록

# 시스템
GET  /control/system/status        - 시스템 전체 상태
GET  /control/system/alerts        - 활성 알림 조회
GET  /control/health               - 헬스 체크
```

### 수정 완료 (2026-01-13)
- ✅ main.py에 control_api 라우터 등록
- ✅ controlApi.ts API 경로를 백엔드와 일치하도록 수정
  - ACU 엔드포인트 경로 수정
  - CCTV 엔드포인트 경로 수정
  - 녹화 API를 start/stop으로 분리

### 미완료 항목
- [ ] ControlPage UI 컴포넌트 구현
- [ ] DoorCard, CameraCard 컴포넌트 구현
- [ ] PTZControl 조이스틱 컴포넌트 구현
- [ ] CommandBar 자연어 명령 입력 UI

---

## 수정 이력

### 2026-01-13
1. **LogIndexer 컬렉션 분리**
   - 문제: RAG QA가 보안 로그를 검색하는 문제
   - 해결: `security_logs` 컬렉션 분리
   - 수정 파일:
     - `config/config.yaml`: `logs_collection_name` 추가
     - `services/log_indexer.py`: 별도 컬렉션 사용

2. **Control API 라우터 등록**
   - 문제: control_api.py가 main.py에 등록되지 않음
   - 해결: `app.include_router(control_router)` 추가
   - 수정 파일: `main.py`

3. **프론트엔드 API 경로 수정**
   - 문제: controlApi.ts 경로가 백엔드와 불일치
   - 해결: 모든 ACU/CCTV 엔드포인트 경로 수정
   - 수정 파일: `services/controlApi.ts`

4. **Vision 모듈 통합 (granite-vision-korean-poc)**
   - 통합 내용:
     - 4단계 QA 기반 구조화 분석 프롬프트
     - 9가지 사고 유형 분류 (IncidentDetector)
     - 5단계 심각도 평가 (SeverityLevel)
     - 6섹션 마크다운 보고서 템플릿
   - 수정 파일:
     - `services/vision/__init__.py`: 모듈 export 추가
     - `services/vision/korean_prompts.py`: 보안 QA 프롬프트 추가
     - `services/vlm_analyzer.py`: QA 기반 분석 및 보고서 생성 메서드 추가
   - 신규 VLMAnalyzer 메서드:
     - `analyze_qa_based()`: 4단계 QA 분석
     - `analyze_with_incident_detection()`: 사고 감지
     - `generate_security_report()`: 전체 파이프라인

5. **QA 기반 API 엔드포인트 추가**
   - 신규 API 엔드포인트:
     - `POST /image/analyze/qa`: QA 기반 4단계 구조화 분석
     - `POST /image/analyze/qa/upload`: 파일 업로드 QA 분석
     - `POST /image/report/security`: 전체 보안 보고서 파이프라인
     - `POST /image/report/security/upload`: 파일 업로드 보안 보고서
   - 수정 파일:
     - `api/image_api.py`: 신규 모델 및 엔드포인트 추가 (11개 라우트)
     - `services/vlm_analyzer.py`: Base64 이미지 입력 지원, VLM 오류 시 폴백 보고서
   - 테스트 완료:
     - 서버 실행 확인 (port 9002)
     - QA 분석 API 테스트 완료
     - 보안 보고서 생성 API 테스트 완료
     - VLM 서버 미실행 시 폴백 로직 동작 확인

---

## 실행 방법

### 1. 인프라 서비스 시작
```bash
cd /home/sphwang/dev/Total-LLM
docker compose --profile with-postgres up -d
```

### 2. 백엔드 서버 시작
```bash
cd /home/sphwang/dev/Total-LLM/backend
python -m uvicorn main:app --host 0.0.0.0 --port 9002 --reload
```

### 3. 프론트엔드 개발 서버 시작
```bash
cd /home/sphwang/dev/Total-LLM/frontend/react-ui
npm run dev -- --port 9004 --host
```

### 접속 URL
- Frontend: http://localhost:9004
- Backend API: http://localhost:9002
- API Docs: http://localhost:9002/docs
- Qdrant Dashboard: http://localhost:6333/dashboard

---

## 다음 단계

### 우선순위 높음
1. Control 페이지 UI 컴포넌트 구현
2. 실시간 WebSocket 알림 연동

### 우선순위 중간
1. 이미지 배치 분석 진행률 표시
2. 보고서 생성 UI 개선

### 우선순위 낮음
1. 다국어 지원
2. 테마 커스터마이징
