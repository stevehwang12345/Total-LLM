# Total-LLM 프론트엔드 기능명세서

## 문서 정보
- **버전**: 1.2
- **작성일**: 2026-01-13
- **최종 수정**: 2026-01-13
- **상태**: ✅ 핵심 기능 + 품질 개선 완료

---

## 1. 개요

### 1.1 시스템 목적
Total-LLM은 AI 기반 통합 보안 관제 플랫폼으로, CCTV 영상 분석, 문서 검색, 외부 시스템 제어를 하나의 인터페이스에서 제공합니다.

### 1.2 핵심 기능 요약

| 기능 | 설명 | 구현 상태 |
|------|------|----------|
| **기능 1: 이미지 분석** | CCTV 이미지 보안 분석 및 사고 감지 | ✅ 95% |
| **기능 2: 문서 RAG QA** | AI 기반 문서 검색 및 질의응답 | ✅ 100% |
| **기능 3: 외부 시스템 제어** | ACU/CCTV 자연어 명령 제어 | ✅ 85% |

### 1.3 기술 스택
- **프레임워크**: React 19 + TypeScript
- **빌드 도구**: Vite 7
- **상태 관리**: Zustand
- **스타일링**: Tailwind CSS 4
- **라우팅**: React Router DOM 7

### 1.4 레이아웃 구조
```
┌──────────────────────────────────────────────────────────┐
│                      Header (64px)                       │
├────────────────┬─────────────────────────────────────────┤
│                │                                         │
│   Sidebar      │            Main Content                 │
│   (280px)      │            (flex-1)                     │
│                │                                         │
│   - 대시보드   │                                         │
│   - 채팅       │                                         │
│   - 이미지분석 │                                         │
│   - 시스템제어 │                                         │
│   - 보고서     │                                         │
│   - 문서관리   │                                         │
│   - 설정       │                                         │
│                │                                         │
└────────────────┴─────────────────────────────────────────┘
```

---

## 2. 기능 1: CCTV 이미지 분석

### 2.1 기능 설명
CCTV에서 캡처한 이미지를 AI(Qwen2-VL-7B)로 분석하여 보안 사고를 감지하고, 상세 보고서를 생성합니다.

### 2.2 사용자 시나리오

#### 시나리오 1: 단일 이미지 분석
1. 사용자가 이미지 분석 페이지에 접속
2. 이미지 파일을 드래그 앤 드롭 또는 파일 선택으로 업로드
3. "분석 시작" 버튼 클릭
4. 분석 진행 상태 표시 (로딩 스피너)
5. 분석 완료 후 결과 카드 표시:
   - 감지된 사고 유형 (뱃지)
   - 심각도 레벨 (색상 인디케이터)
   - 상세 설명 (텍스트)
   - 원본 이미지 프리뷰

#### 시나리오 2: 배치 분석
1. 여러 이미지를 동시에 업로드 (최대 10개)
2. 배치 분석 진행 (진행률 표시)
3. 결과 목록으로 표시
4. 개별 결과 상세 보기 가능

#### 시나리오 3: 보고서 생성
1. 분석 결과에서 "보고서 생성" 버튼 클릭
2. 보고서 형식 선택 (Markdown/PDF)
3. 보고서 미리보기
4. 보고서 다운로드

### 2.3 화면 구성

#### 2.3.1 ImageUploadCard ✅ 구현됨
이미지 업로드 인터페이스 컴포넌트

**위치**: `src/components/ImageAnalysis/ImageUploadCard.tsx`

**Props**:
```typescript
interface ImageUploadCardProps {
  onAnalysisComplete: (result: AnalysisResult) => void;
}
```

**기능**:
- 드래그 앤 드롭 영역
- 파일 선택 버튼
- 이미지 미리보기
- 분석 진행 상태 표시
- 지원 형식: JPEG, PNG, GIF, WebP (최대 10MB)

#### 2.3.2 AnalysisResultCard ✅ 구현됨
분석 결과 표시 카드 컴포넌트

**위치**: `src/components/ImageAnalysis/AnalysisResultCard.tsx`

**Props**:
```typescript
interface AnalysisResultCardProps {
  result: AnalysisResult;
  onGenerateReport?: () => void;
}
```

**표시 정보**:
- 분석 ID
- 타임스탬프
- 사고 유형 뱃지
- 심각도 인디케이터
- 상세 설명
- 원본 이미지 썸네일

#### 2.3.3 IncidentBadge ✅ 구현됨
사고 유형 뱃지 컴포넌트 (AnalysisResultCard에 통합)

**사고 유형별 색상**:
| 사고 유형 | 한글명 | 색상 |
|----------|--------|------|
| fire | 화재 | Red |
| smoke | 연기 | Orange |
| intrusion | 침입 | Blue |
| vandalism | 기물파손 | Purple |
| accident | 사고 | Yellow |
| abandoned_object | 유기물품 | Brown |
| crowd | 군중밀집 | Green |
| fight | 싸움 | Red |
| weapon | 무기 | Black |
| normal | 정상 | Gray |

#### 2.3.4 SeverityIndicator ✅ 구현됨
심각도 표시 컴포넌트 (AnalysisResultCard에 통합)

**심각도 레벨**:
| 레벨 | 설명 | 색상 | 아이콘 |
|------|------|------|--------|
| Critical | 즉시 대응 필요 | #EF4444 | AlertTriangle |
| High | 긴급 확인 필요 | #F97316 | AlertCircle |
| Medium | 주의 관찰 필요 | #EAB308 | Info |
| Low | 정보성 알림 | #22C55E | CheckCircle |

#### 2.3.5 ReportViewer 🚧 미구현
보고서 미리보기 컴포넌트

**예상 Props**:
```typescript
interface ReportViewerProps {
  report: IncidentReport;
  onDownload: (format: 'md' | 'pdf') => void;
}
```

**기능**:
- Markdown 렌더링 (react-markdown 사용)
- PDF 다운로드 버튼
- Markdown 다운로드 버튼
- 인쇄 버튼

#### 2.3.6 AnalysisHistory 🚧 미구현
분석 이력 목록 컴포넌트

**예상 Props**:
```typescript
interface AnalysisHistoryProps {
  analyses: AnalysisResult[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}
```

### 2.4 데이터 흐름

```
┌─────────────────┐
│ ImageUploadCard │
│  (파일 선택)    │
└────────┬────────┘
         │ File
         ▼
┌─────────────────┐
│ fileToBase64()  │
│  (Base64 변환)  │
└────────┬────────┘
         │ base64 string
         ▼
┌─────────────────┐
│ analyzeImage()  │
│  POST /image/   │
│  analyze        │
└────────┬────────┘
         │ AnalysisResult
         ▼
┌─────────────────────┐
│ imageAnalysisStore  │
│  (상태 저장)        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ AnalysisResultCard  │
│  (결과 표시)        │
└─────────────────────┘
```

### 2.5 상태 관리 (Zustand)

**Store**: `src/stores/imageAnalysisStore.ts` ✅ 구현됨

```typescript
interface ImageAnalysisState {
  analyses: AnalysisResult[];
  currentAnalysis: AnalysisResult | null;
  isAnalyzing: boolean;
  error: string | null;

  // Actions
  addAnalysis: (analysis: AnalysisResult) => void;
  setCurrentAnalysis: (analysis: AnalysisResult | null) => void;
  setIsAnalyzing: (isAnalyzing: boolean) => void;
  setError: (error: string | null) => void;
  clearAnalyses: () => void;
}
```

### 2.6 API 연동

**Service**: `src/services/imageAnalysisApi.ts` ✅ 구현됨

| 함수 | 설명 | 엔드포인트 |
|------|------|-----------|
| `analyzeImage()` | 이미지 분석 요청 | POST /image/analyze |
| `getAnalysisResult()` | 분석 결과 조회 | GET /image/{id} |
| `generateIncidentReport()` | 보고서 생성 | POST /report/generate |

---

## 3. 기능 2: 문서 RAG QA

### 3.1 기능 설명
RAG(Retrieval-Augmented Generation) 기반 문서 검색 및 AI 질의응답 시스템입니다.
SSE(Server-Sent Events) 스트리밍으로 실시간 응답을 제공합니다.

### 3.2 사용자 시나리오

#### 시나리오 1: 문서 질의
1. 사용자가 채팅 입력창에 질문 입력
2. 엔터 또는 전송 버튼 클릭
3. AI가 관련 문서를 검색하고 응답 생성
4. 스트리밍으로 응답이 실시간 표시
5. 응답 완료 후 출처 문서 표시

#### 시나리오 2: 대화 이력 관리
1. 사이드바에서 이전 대화 목록 확인
2. 대화 선택하여 이어서 질문
3. 새 대화 시작 버튼으로 새 세션 생성

#### 시나리오 3: 문서 업로드
1. 문서 관리 탭으로 이동
2. 문서 파일 업로드 (txt, pdf, md, docx)
3. 업로드 진행률 표시
4. 완료 후 문서 목록에 추가

### 3.3 화면 구성

#### 3.3.1 ChatMessage ✅ 구현됨
채팅 메시지 표시 컴포넌트

**위치**: `src/components/Chat/ChatMessage.tsx`

**Props**:
```typescript
interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}
```

**기능**:
- 사용자/AI 메시지 구분 표시
- Markdown 렌더링
- 코드 블록 하이라이팅
- 스트리밍 중 커서 애니메이션

#### 3.3.2 ChatInput ✅ 구현됨 (App.tsx에 통합)
채팅 입력 컴포넌트

**기능**:
- 텍스트 입력 영역
- 파일 첨부 버튼
- 전송 버튼
- Enter 키로 전송 (Shift+Enter로 줄바꿈)

#### 3.3.3 ConversationSidebar ✅ 구현됨
대화 이력 사이드바

**위치**: `src/components/Sidebar/ConversationSidebar.tsx`

**Props**:
```typescript
interface ConversationSidebarProps {
  isOpen: boolean;
  onDocumentClick: () => void;
}
```

**기능**:
- 대화 목록 표시
- 새 대화 생성 버튼
- 대화 선택/삭제
- 문서 관리 탭 전환

#### 3.3.4 DocumentUpload 🚧 부분 구현
문서 업로드 컴포넌트

**기능**:
- 드래그 앤 드롭 업로드
- 지원 형식: txt, pdf, md, docx
- 업로드 진행률 표시
- 파일 크기 제한 (10MB)

#### 3.3.5 DocumentList 🚧 부분 구현
업로드된 문서 목록

**기능**:
- 문서 이름, 크기, 업로드 일시 표시
- 문서 삭제 버튼
- 문서 미리보기

### 3.4 데이터 흐름 (SSE 스트리밍)

```
┌─────────────────┐
│   ChatInput     │
│  (질문 입력)    │
└────────┬────────┘
         │ message
         ▼
┌─────────────────┐
│  sendMessage()  │
│  POST /api/rag/ │
│  chat (SSE)     │
└────────┬────────┘
         │ EventSource
         ▼
┌─────────────────┐
│  onmessage()    │
│  (청크 수신)    │
└────────┬────────┘
         │ text chunks
         ▼
┌─────────────────┐
│   chatStore     │
│  (메시지 업데이트)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ChatMessage    │
│ (실시간 렌더링) │
└─────────────────┘
```

### 3.5 상태 관리 (Zustand)

**Store**: `src/stores/chatStore.ts` ✅ 구현됨

```typescript
interface ChatState {
  messages: Message[];
  conversations: Conversation[];
  currentConversationId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;

  // Actions
  addMessage: (message: Message) => void;
  updateLastMessage: (content: string) => void;
  setConversations: (conversations: Conversation[]) => void;
  setCurrentConversation: (id: string | null) => void;
  setIsLoading: (isLoading: boolean) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  clearMessages: () => void;
}
```

### 3.6 API 연동

**Service**: `src/services/api.ts` ✅ 구현됨

| 함수 | 설명 | 엔드포인트 |
|------|------|-----------|
| `sendMessage()` | SSE 스트리밍 채팅 | POST /api/rag/chat |
| `sendQuery()` | 단일 질의 | POST /api/rag/query |
| `getConversations()` | 대화 목록 | GET /api/rag/conversations |
| `uploadDocument()` | 문서 업로드 | POST /api/documents/upload |

---

## 4. 기능 3: 외부 시스템 제어 ✅ 구현 완료

> **업데이트 (2026-01-13)**: API 경로 수정 완료
>
> `controlApi.ts`의 모든 API 경로가 백엔드 `control_api.py`와 일치하도록 수정되었습니다.
> - API Base: `/control` (Vite proxy → localhost:9002/control)
> - ACU: `/control/acu/door/status`, `/control/acu/door/unlock`, `/control/acu/door/lock`, `/control/acu/log`
> - CCTV: `/control/cctv/camera/status`, `/control/cctv/camera/move`, `/control/cctv/camera/preset`
> - 녹화: `/control/cctv/recording/start`, `/control/cctv/recording/stop`

### 4.1 기능 설명
자연어 명령을 통해 ACU(출입통제시스템) 및 CCTV를 제어합니다.
백엔드의 Function Calling을 통해 실제 장비와 연동됩니다.

### 4.2 사용자 시나리오

#### 시나리오 1: 자연어 명령
1. 명령 입력창에 자연어 명령 입력
   - 예: "1번 출입문 열어줘"
   - 예: "로비 카메라를 입구쪽으로 돌려"
2. AI가 명령을 분석하고 적절한 API 호출
3. 실행 결과 표시

#### 시나리오 2: ACU 직접 제어
1. ACU 제어 패널에서 출입문 목록 확인
2. 개별 출입문의 상태 확인 (잠금/해제)
3. 버튼 클릭으로 잠금/해제 전환
4. 출입 이력 로그 확인

#### 시나리오 3: CCTV PTZ 제어
1. CCTV 제어 패널에서 카메라 목록 확인
2. 카메라 선택하여 PTZ 조이스틱 표시
3. 조이스틱으로 Pan/Tilt 조작
4. 슬라이더로 Zoom 조작
5. 프리셋 버튼으로 저장된 위치 이동

### 4.3 화면 구성

#### 4.3.1 ControlPage ✅ 구현됨
시스템 제어 메인 페이지

**위치**: `src/pages/ControlPage.tsx`

**구조**:
- 탭 네비게이션 (자연어 명령 / ACU 제어 / CCTV 제어)
- 에러 알림 표시
- 각 탭별 컴포넌트 렌더링

#### 4.3.2 CommandBar ✅ 구현됨
자연어 명령 입력 및 기록 표시

**위치**: `src/components/Control/CommandBar.tsx`

**기능**:
- 자연어 명령 입력
- 명령 실행 상태 표시 (로딩 스피너)
- 명령 기록 목록 (성공/실패 표시)
- 실행된 액션 태그 표시

#### 4.3.3 DoorGrid ✅ 구현됨
출입문 그리드 뷰

**위치**: `src/components/Control/DoorGrid.tsx`

**기능**:
- 상태별 통계 카드 (전체/잠김/열림/오류)
- 출입문 카드 그리드
- 출입 이력 패널 (확장/축소)

#### 4.3.4 DoorCard ✅ 구현됨
개별 출입문 카드

**위치**: `src/components/Control/DoorCard.tsx`

**Props**:
```typescript
interface DoorCardProps {
  door: DoorStatus;
}
```

**기능**:
- 상태 아이콘 및 뱃지 표시
- 마지막 출입 정보 표시
- 열기/잠금 버튼 (로딩 상태 포함)
- 오류 메시지 표시

#### 4.3.5 CameraGrid ✅ 구현됨
카메라 그리드 뷰

**위치**: `src/components/Control/CameraGrid.tsx`

**기능**:
- 상태별 통계 카드 (전체/온라인/녹화중/오프라인)
- 카메라 카드 그리드
- PTZ 제어 패널 (카메라 선택 시)
- 빠른 제어 버튼 (전체 녹화 시작/중지/HOME)

#### 4.3.6 CameraCard ✅ 구현됨
개별 카메라 카드

**위치**: `src/components/Control/CameraCard.tsx`

**Props**:
```typescript
interface CameraCardProps {
  camera: CameraStatus;
  isSelected: boolean;
  onSelect: () => void;
}
```

**기능**:
- 카메라 미리보기 영역 (플레이스홀더)
- 녹화 상태 표시 (REC 배지)
- 오프라인 오버레이
- 현재 위치 정보 (P/T/Z)
- 프리셋 목록 미리보기
- 프리셋/PTZ 버튼

#### 4.3.7 PTZControl ✅ 구현됨
PTZ 조이스틱 컨트롤러

**위치**: `src/components/Control/PTZControl.tsx`

**Props**:
```typescript
interface PTZControlProps {
  camera: CameraStatus | null;
  onClose: () => void;
}
```

**기능**:
- 방향 제어 버튼 (상/하/좌/우/HOME)
- 줌 제어 버튼 (In/Out)
- 현재 위치 표시
- 프리셋 목록 및 선택
- 현재 위치 프리셋 저장
- 녹화 시작/중지 토글

### 4.4 데이터 흐름

```
┌─────────────────┐
│   CommandBar    │
│ (자연어 명령)   │
└────────┬────────┘
         │ command string
         ▼
┌─────────────────┐
│ sendCommand()   │
│ POST /api/      │
│ control/command │
└────────┬────────┘
         │ CommandResult
         ▼
┌─────────────────────┐
│  Function Calling   │
│  (백엔드에서 처리)  │
└────────┬────────────┘
         │ 실행 결과
         ▼
┌─────────────────────┐
│   controlStore      │
│  (상태 업데이트)    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  DoorCard/CameraCard│
│  (UI 업데이트)      │
└─────────────────────┘
```

### 4.5 상태 관리 (Zustand) ✅ 구현됨

**Store**: `src/stores/controlStore.ts`

```typescript
interface ControlState {
  // ACU 상태
  doors: DoorStatus[];
  accessLogs: AccessLog[];

  // CCTV 상태
  cameras: CameraStatus[];
  selectedCameraId: string | null;

  // 명령 상태
  commandHistory: CommandResult[];
  isExecuting: boolean;
  error: string | null;

  // Actions
  setDoors: (doors: DoorStatus[]) => void;
  updateDoor: (doorId: string, status: Partial<DoorStatus>) => void;
  addAccessLog: (log: AccessLog) => void;
  setCameras: (cameras: CameraStatus[]) => void;
  updateCamera: (cameraId: string, status: Partial<CameraStatus>) => void;
  setSelectedCamera: (cameraId: string | null) => void;
  addCommandResult: (result: CommandResult) => void;
  setIsExecuting: (isExecuting: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
}
```

### 4.6 API 연동 ✅ 구현됨

**Service**: `src/services/controlApi.ts`

**API Base**: `/control` (Vite proxy → localhost:9002/control)

| 함수 | 엔드포인트 | 메서드 |
|------|-----------|--------|
| `sendCommand()` | `/control/command` | POST |
| `getDoorStatus()` | `/control/acu/door/status` | GET |
| `getDoorById()` | `/control/acu/door/status?door_id=` | GET |
| `unlockDoor()` | `/control/acu/door/unlock` | POST |
| `lockDoor()` | `/control/acu/door/lock` | POST |
| `getAccessLogs()` | `/control/acu/log` | GET |
| `getCameraStatus()` | `/control/cctv/camera/status` | GET |
| `getCameraById()` | `/control/cctv/camera/status?camera_id=` | GET |
| `moveCamera()` | `/control/cctv/camera/move` | POST |
| `goToPreset()` | `/control/cctv/camera/preset` | POST |
| `savePreset()` | `/control/cctv/camera/preset/save` | POST |
| `deletePreset()` | `/control/cctv/preset/{cameraId}/{presetId}` | DELETE |
| `startRecording()` | `/control/cctv/recording/start` | POST |
| `stopRecording()` | `/control/cctv/recording/stop` | POST |

```typescript
// 자연어 명령
export async function sendCommand(request: SendCommandRequest): Promise<CommandResult>;

// ACU 제어
export async function getDoorStatus(): Promise<DoorStatus[]>;
export async function getDoorById(doorId: string): Promise<DoorStatus>;
export async function unlockDoor(request: UnlockDoorRequest): Promise<DoorStatus>;
export async function lockDoor(doorId: string): Promise<DoorStatus>;
export async function getAccessLogs(doorId?: string, limit?: number): Promise<AccessLog[]>;

// CCTV 제어
export async function getCameraStatus(): Promise<CameraStatus[]>;
export async function getCameraById(cameraId: string): Promise<CameraStatus>;
export async function moveCamera(request: MoveCameraRequest): Promise<CameraStatus>;
export async function goToPreset(request: GoToPresetRequest): Promise<CameraStatus>;
export async function savePreset(request: SavePresetRequest): Promise<Preset>;
export async function deletePreset(cameraId: string, presetId: string): Promise<void>;
export async function startRecording(cameraId: string, duration?: number, quality?: string): Promise<CameraStatus>;
export async function stopRecording(cameraId: string): Promise<CameraStatus>;

// Mock 데이터 (백엔드 없이 테스트용)
export async function getMockDoors(): Promise<DoorStatus[]>;
export async function getMockCameras(): Promise<CameraStatus[]>;
```

### 4.7 타입 정의 ✅ 구현됨

**위치**: `src/types/control.ts`

```typescript
// ACU 타입
export type DoorStatusType = 'locked' | 'unlocked' | 'error';
export interface DoorStatus { ... }
export interface AccessEvent { ... }
export interface AccessLog { ... }

// CCTV 타입
export type CameraStatusType = 'online' | 'offline' | 'recording' | 'error';
export interface PTZPosition { pan: number; tilt: number; zoom: number; }
export interface Preset { ... }
export interface CameraStatus { ... }

// 명령 타입
export interface CommandAction { ... }
export interface CommandResult { ... }

// API 요청 타입
export interface UnlockDoorRequest { ... }
export interface MoveCameraRequest { ... }
export interface GoToPresetRequest { ... }
export interface SavePresetRequest { ... }
export interface SendCommandRequest { ... }
```

---

## 5. 공통 컴포넌트

### 5.1 MainLayout ✅ 구현됨
사이드바 레이아웃

**위치**: `src/layouts/MainLayout.tsx`

**기능**:
- 고정 사이드바 (280px)
- 메인 콘텐츠 영역
- React Router Outlet

### 5.2 Header ✅ 구현됨
상단 헤더 컴포넌트

**위치**: `src/components/Layout/Header.tsx`

### 5.3 Sidebar ✅ 구현됨
사이드바 네비게이션

**위치**: `src/components/Layout/Sidebar.tsx`

**메뉴 항목**:
- 대시보드 (`/`)
- 채팅 (`/chat`)
- 이미지 분석 (`/analysis`)
- 시스템 제어 (`/control`)
- 보고서 (`/reports`)
- 문서 관리 (`/documents`)
- 설정 (`/settings`)

### 5.4 LoadingSpinner ✅ 구현됨
로딩 스피너

### 5.5 ErrorBoundary 🚧 미구현
에러 경계 컴포넌트

### 5.6 Toast/Notification 🚧 미구현
토스트 알림 컴포넌트

---

## 6. 타입 정의

### 6.1 공통 타입

**위치**: `src/types/`

```typescript
// types/analysis.ts ✅
interface AnalysisResult { ... }
interface Incident { ... }
type IncidentType = 'fire' | 'smoke' | 'intrusion' | ...;

// types/chat.ts ✅
interface Message { ... }
interface Conversation { ... }

// types/control.ts ✅
interface DoorStatus { ... }
interface CameraStatus { ... }
interface CommandResult { ... }
```

---

## 7. 구현 우선순위

### Phase A: 핵심 기능 완성 ✅ 완료
1. ~~외부 시스템 제어 UI 전체 구현~~ ✅
   - ~~ControlPage~~ ✅
   - ~~CommandBar~~ ✅
   - ~~DoorGrid, DoorCard~~ ✅
   - ~~CameraGrid, CameraCard~~ ✅
   - ~~PTZControl~~ ✅
   - ~~controlStore~~ ✅
   - ~~controlApi~~ ✅

2. ~~React Router 도입~~ ✅

3. ~~사이드바 레이아웃~~ ✅

### Phase B: 기능 고도화 ✅ 완료
1. ~~**보고서 뷰어/다운로드**~~ ✅
   - ~~ReportViewer 컴포넌트~~ ✅
   - ~~Markdown 렌더링~~ ✅

2. ~~**분석 이력 관리**~~ ✅
   - ~~AnalysisHistory 컴포넌트~~ ✅
   - ~~AnalysisDashboard 통합~~ ✅

3. ~~**문서 관리 완성**~~ ✅
   - ~~DocumentUpload 완성~~ ✅
   - ~~DocumentList 완성~~ ✅
   - ~~DocumentsPage 완성~~ ✅

4. ~~**설정 페이지**~~ ✅
   - ~~SettingsPage 완성~~ ✅
   - ~~RAG 설정 UI~~ ✅

### Phase C: 품질 개선 ✅ 완료
1. ✅ ErrorBoundary 추가
   - `src/components/common/ErrorBoundary.tsx`
   - 에러 캐치 및 사용자 친화적 폴백 UI
   - 재시도 기능 포함
2. ✅ Toast/Notification 시스템
   - `src/stores/toastStore.ts` (Zustand 스토어)
   - `src/components/common/Toast.tsx`
   - success/error/warning/info 유형 지원
3. ✅ 성능 최적화 (코드 분할)
   - React.lazy() + Suspense 적용
   - 페이지별 청크 분리
   - LoadingSpinner 폴백 UI

### Phase D: 추가 품질 개선 (다음 단계)
1. 🚧 반응형 디자인 개선
2. 🚧 접근성 개선 (ARIA)
3. 🚧 테스트 코드 작성

### Phase E: 백엔드 연동 (다음 단계)
1. 🚧 실제 API 연결
2. 🚧 WebSocket/SSE 스트리밍
3. 🚧 인증/인가 구현

---

## 부록 A: 컴포넌트 디렉토리 구조 (현재)

```
src/
├── components/
│   ├── Agent/
│   │   ├── AgentControlPanel.tsx ✅
│   │   ├── AgentHistory.tsx ✅
│   │   ├── AgentSettings.tsx ✅
│   │   └── ToolCard.tsx ✅
│   │
│   ├── Chat/
│   │   ├── ChatMessage.tsx ✅
│   │   ├── CodeBlock.tsx ✅
│   │   ├── RAGMetrics.tsx ✅
│   │   └── RetrievalContext.tsx ✅
│   │
│   ├── Control/ ✅
│   │   ├── CommandBar.tsx ✅
│   │   ├── DoorCard.tsx ✅
│   │   ├── DoorGrid.tsx ✅
│   │   ├── CameraCard.tsx ✅
│   │   ├── CameraGrid.tsx ✅
│   │   ├── PTZControl.tsx ✅
│   │   └── index.ts ✅
│   │
│   ├── Document/ ✅
│   │   ├── DocumentUpload.tsx ✅
│   │   ├── DocumentList.tsx ✅
│   │   ├── DocumentManager.tsx ✅
│   │   └── DocumentViewer.tsx ✅
│   │
│   ├── ImageAnalysis/ ✅
│   │   ├── AnalysisDashboard.tsx ✅
│   │   ├── AnalysisFilter.tsx ✅
│   │   ├── AnalysisHistory.tsx ✅
│   │   ├── AnalysisResultCard.tsx ✅
│   │   ├── ImagePreviewModal.tsx ✅
│   │   ├── ImageSearchPanel.tsx ✅
│   │   ├── ImageUploadCard.tsx ✅
│   │   ├── IncidentStats.tsx ✅
│   │   └── ReportViewer.tsx ✅
│   │
│   ├── RAGPanel/
│   │   └── RAGControlPanel.tsx ✅
│   │
│   ├── Security/
│   │   ├── ImageAnalysisPage.tsx ✅
│   │   ├── ModeSelector.tsx ✅
│   │   └── SecurityChatPage.tsx ✅
│   │
│   ├── Settings/
│   │   └── RAGSettings.tsx ✅
│   │
│   └── Sidebar/
│       └── ConversationSidebar.tsx ✅
│
├── layouts/
│   └── MainLayout.tsx ✅
│
├── pages/ ✅ 전체 구현 완료
│   ├── DashboardPage.tsx ✅
│   ├── ChatPage.tsx ✅
│   ├── AnalysisPage.tsx ✅
│   ├── ControlPage.tsx ✅
│   ├── ReportsPage.tsx ✅
│   ├── DocumentsPage.tsx ✅
│   └── SettingsPage.tsx ✅
│
├── stores/
│   ├── chatStore.ts ✅
│   ├── agentStore.ts ✅
│   ├── imageAnalysisStore.ts ✅
│   └── controlStore.ts ✅
│
├── services/
│   ├── api.ts ✅
│   ├── imageAnalysisApi.ts ✅
│   └── controlApi.ts ✅
│
└── types/
    ├── analysis.ts ✅
    ├── chat.ts ✅
    ├── control.ts ✅
    └── index.ts ✅
```

**범례**:
- ✅ 구현됨
