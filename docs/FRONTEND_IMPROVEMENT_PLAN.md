# Total-LLM 프론트엔드 개선 방향 문서

## 개요

이 문서는 `INTEGRATED_WBS.md`에 정의된 기능 요구사항과 현재 프론트엔드 구현 상태를 비교 분석하여,
누락된 기능과 개선이 필요한 영역을 정리합니다.

**분석일**: 2026-01-13
**현재 버전**: 0.1.0 (초기 구현)

---

## 1. WBS 요구사항 vs 현재 구현 상태

### 1.1 핵심 기능 3가지 구현 현황

| 기능 | WBS 요구사항 | 현재 상태 | 구현율 |
|------|-------------|----------|--------|
| **기능 1: 이미지 분석** | CCTV 이미지 분석, 사고 감지, 보고서 생성 | ⚠️ 부분 구현 | 40% |
| **기능 2: 문서 RAG QA** | RAG 검색, Agent 응답, SSE 스트리밍 | ✅ 구현됨 | 80% |
| **기능 3: 외부 시스템 제어** | ACU/CCTV 제어, Function Calling | ❌ 미구현 | 0% |

---

## 2. Phase 6 (프론트엔드) 상세 분석

### 2.1 공통 컴포넌트 (Phase 6.1) - ✅ 80% 완료

| ID | 태스크 | 상태 | 비고 |
|----|--------|------|------|
| 6.1.1 | React 프로젝트 설정 | ✅ 완료 | Vite + TypeScript |
| 6.1.2 | 라우팅 설정 | ⚠️ 부분 | 탭 기반, React Router 미사용 |
| 6.1.3 | 상태 관리 설정 | ✅ 완료 | Zustand |
| 6.1.4 | API 클라이언트 설정 | ✅ 완료 | services/api.ts |
| 6.1.5 | 공통 UI 컴포넌트 | ⚠️ 부분 | 기본 컴포넌트만 존재 |
| 6.1.6 | 레이아웃 컴포넌트 | ✅ 완료 | Header, Sidebar |
| 6.1.7 | 테마 설정 | ✅ 완료 | Tailwind CSS |
| 6.1.8 | 타입 정의 | ⚠️ 부분 | 일부 타입 누락 |

### 2.2 채팅 인터페이스 (Phase 6.2) - ✅ 85% 완료

| ID | 태스크 | 상태 | 비고 |
|----|--------|------|------|
| 6.2.1 | ChatContainer 구현 | ✅ 완료 | App.tsx에 통합 |
| 6.2.2 | MessageList 구현 | ✅ 완료 | ChatMessage.tsx |
| 6.2.3 | MessageItem 구현 | ✅ 완료 | ChatMessage.tsx |
| 6.2.4 | ChatInput 구현 | ✅ 완료 | App.tsx에 통합 |
| 6.2.5 | ImageUpload 구현 | ⚠️ 부분 | 파일 첨부 버튼만 존재 |
| 6.2.6 | StreamingMessage 구현 | ✅ 완료 | SSE 스트리밍 지원 |
| 6.2.7 | 채팅 상태 관리 | ✅ 완료 | chatStore.ts |
| 6.2.8 | 채팅 API 연동 | ✅ 완료 | api.ts |
| 6.2.9 | 채팅 페이지 통합 | ✅ 완료 | App.tsx |

### 2.3 분석 결과 표시 (Phase 6.3) - ⚠️ 50% 완료

| ID | 태스크 | 상태 | 비고 |
|----|--------|------|------|
| 6.3.1 | AnalysisResult 구현 | ✅ 완료 | AnalysisResultCard.tsx |
| 6.3.2 | IncidentBadge 구현 | ✅ 완료 | AnalysisResultCard.tsx에 통합 |
| 6.3.3 | SeverityIndicator 구현 | ✅ 완료 | AnalysisResultCard.tsx에 통합 |
| 6.3.4 | ReportViewer 구현 | ❌ 미구현 | 보고서 뷰어 없음 |
| 6.3.5 | ImagePreview 구현 | ⚠️ 부분 | 기본 프리뷰만 |
| 6.3.6 | ReportDownload 구현 | ❌ 미구현 | 다운로드 기능 없음 |
| 6.3.7 | 분석 상태 관리 | ✅ 완료 | imageAnalysisStore.ts |
| 6.3.8 | 분석 API 연동 | ✅ 완료 | imageAnalysisApi.ts |

---

## 3. 누락된 핵심 기능

### 3.1 외부 시스템 제어 UI (기능 3) - ❌ 완전 누락

WBS에서 요구하는 기능 3 "외부 시스템 제어"를 위한 프론트엔드가 **전혀 구현되지 않았습니다.**

#### 필요한 컴포넌트

```
components/
  Control/
    ControlPanel.tsx          # 제어 메인 패널
    CommandInput.tsx          # 자연어 명령 입력
    ACUControl/
      DoorList.tsx            # 출입문 목록
      DoorCard.tsx            # 개별 출입문 카드
      AccessLogTable.tsx      # 출입 이력 테이블
      EmergencyButton.tsx     # 비상 전체 개방 버튼
    CCTVControl/
      CameraGrid.tsx          # 카메라 그리드 뷰
      CameraCard.tsx          # 개별 카메라 카드
      PTZController.tsx       # PTZ 조이스틱 컨트롤러
      PresetSelector.tsx      # 프리셋 선택기
      RecordingStatus.tsx     # 녹화 상태 표시
    StatusDashboard.tsx       # 전체 시스템 상태 대시보드
```

#### 필요한 API 연동

```typescript
// services/controlApi.ts
export async function sendCommand(command: string): Promise<CommandResult>
export async function unlockDoor(doorId: string, duration?: number): Promise<DoorStatus>
export async function lockDoor(doorId: string): Promise<DoorStatus>
export async function getDoorStatus(doorId?: string): Promise<DoorStatus[]>
export async function getAccessLogs(doorId?: string, limit?: number): Promise<AccessLog[]>
export async function moveCamera(cameraId: string, pan?: number, tilt?: number, zoom?: number): Promise<CameraStatus>
export async function goToPreset(cameraId: string, presetId: string): Promise<CameraStatus>
export async function startRecording(cameraId: string): Promise<RecordingStatus>
export async function stopRecording(cameraId: string): Promise<RecordingStatus>
export async function getCameraStatus(cameraId?: string): Promise<CameraStatus[]>
```

### 3.2 보고서 기능 - ⚠️ 부분 구현

| 기능 | 상태 | 설명 |
|------|------|------|
| 보고서 생성 API 호출 | ✅ 완료 | generateIncidentReport() |
| 보고서 미리보기 | ❌ 미구현 | Markdown 렌더링 필요 |
| 보고서 다운로드 | ❌ 미구현 | PDF/Markdown 다운로드 |
| 보고서 이력 관리 | ❌ 미구현 | 생성된 보고서 목록 |

### 3.3 보안 대시보드 - ⚠️ 부분 구현

SecurityApp.tsx와 관련 컴포넌트가 존재하지만, 메인 App.tsx와 분리되어 있음.

---

## 4. UI/UX 개선 필요 사항

### 4.1 네비게이션 구조

**현재 문제**:
- 탭 기반 네비게이션만 존재
- URL 라우팅 미지원 (직접 링크 불가)
- 깊은 네비게이션 구조 없음

**개선 방안**:
```
/                       # 메인 대시보드
/chat                   # RAG 채팅
/chat/:conversationId   # 특정 대화
/documents              # 문서 관리
/analysis               # 이미지 분석
/analysis/:id           # 특정 분석 결과
/control                # 시스템 제어
/control/acu            # ACU 제어
/control/cctv           # CCTV 제어
/reports                # 보고서
/settings               # 설정
```

### 4.2 반응형 디자인

**현재 문제**:
- 모바일 최적화 부족
- 사이드바 반응형 처리 미흡

**개선 방안**:
- 모바일 네비게이션 (햄버거 메뉴)
- 반응형 그리드 레이아웃
- 터치 친화적 UI

### 4.3 접근성 (Accessibility)

**현재 문제**:
- ARIA 레이블 부족
- 키보드 네비게이션 미흡
- 색상 대비 일부 부족

**개선 방안**:
- WCAG 2.1 AA 준수
- 스크린 리더 지원
- 키보드 단축키 추가

---

## 5. 개선 우선순위 및 로드맵

### Phase A: 핵심 기능 완성 (높음)

| 우선순위 | 작업 | 예상 공수 |
|---------|------|----------|
| A1 | 외부 시스템 제어 UI 구현 | 3-5일 |
| A2 | 보고서 뷰어/다운로드 구현 | 1-2일 |
| A3 | React Router 도입 | 1일 |

### Phase B: 기능 고도화 (중간)

| 우선순위 | 작업 | 예상 공수 |
|---------|------|----------|
| B1 | 보안 대시보드 통합 | 2-3일 |
| B2 | 실시간 알림 시스템 | 2일 |
| B3 | 이미지 분석 고도화 | 2일 |

### Phase C: 품질 개선 (보통)

| 우선순위 | 작업 | 예상 공수 |
|---------|------|----------|
| C1 | 반응형 디자인 개선 | 2일 |
| C2 | 접근성 개선 | 1-2일 |
| C3 | 성능 최적화 | 1일 |

---

## 6. 구현 가이드

### 6.1 외부 시스템 제어 UI 구현 가이드

#### 디렉토리 구조
```
src/
  components/
    Control/
      index.ts
      ControlDashboard.tsx      # 메인 대시보드
      CommandBar.tsx            # 자연어 명령 바
      ACU/
        index.ts
        DoorGrid.tsx            # 출입문 그리드
        DoorCard.tsx            # 출입문 카드
        AccessLogPanel.tsx      # 출입 이력
      CCTV/
        index.ts
        CameraGrid.tsx          # 카메라 그리드
        CameraCard.tsx          # 카메라 카드
        PTZControl.tsx          # PTZ 조이스틱
  stores/
    controlStore.ts             # 제어 상태 관리
  services/
    controlApi.ts               # 제어 API
  types/
    control.ts                  # 타입 정의
```

#### 핵심 컴포넌트 설계

**ControlDashboard.tsx**
```tsx
// 메인 제어 대시보드
// - 자연어 명령 입력
// - ACU 상태 요약
// - CCTV 상태 요약
// - 최근 활동 로그
```

**PTZControl.tsx**
```tsx
// CCTV PTZ 조이스틱 컨트롤러
// - 8방향 이동 버튼
// - 줌 슬라이더
// - 프리셋 버튼
// - 녹화 시작/중지
```

### 6.2 보고서 기능 구현 가이드

#### 필요 라이브러리
```bash
npm install react-markdown remark-gfm html2pdf.js
```

#### 컴포넌트 구조
```
src/
  components/
    Report/
      ReportViewer.tsx          # Markdown 렌더러
      ReportDownload.tsx        # 다운로드 버튼
      ReportHistory.tsx         # 보고서 이력
```

---

## 7. 기술 스택 권장사항

### 추가 권장 라이브러리

| 용도 | 라이브러리 | 이유 |
|------|-----------|------|
| 라우팅 | react-router-dom v6 | URL 기반 네비게이션 |
| 폼 처리 | react-hook-form | 복잡한 폼 관리 |
| 테이블 | @tanstack/react-table | 출입 이력 등 테이블 |
| 차트 | recharts | 통계 시각화 |
| 날짜 | date-fns | 날짜 포맷팅 |
| 마크다운 | react-markdown | 보고서 렌더링 |
| 알림 | react-hot-toast | 토스트 알림 |
| 아이콘 | lucide-react | 일관된 아이콘 |

---

## 8. 결론

### 현재 구현율
- **전체**: 약 **55%** 완료
- **기능 1 (이미지 분석)**: 40%
- **기능 2 (RAG QA)**: 80%
- **기능 3 (시스템 제어)**: 0%

### 즉시 필요한 작업
1. **외부 시스템 제어 UI 전체 구현** - 가장 시급
2. **보고서 뷰어/다운로드 기능** - 이미지 분석 완성에 필수
3. **React Router 도입** - 확장성을 위해 필요

### 권장 접근 방식
1. 백엔드 API가 준비되면, 외부 시스템 제어 UI를 우선 구현
2. 기존 SecurityApp.tsx를 메인 App.tsx에 통합
3. 단계적으로 React Router 마이그레이션

---

**문서 버전**: 1.0
**작성일**: 2026-01-13
**작성자**: Claude AI Assistant
