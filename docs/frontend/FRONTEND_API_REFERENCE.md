# Total-LLM 프론트엔드 API 참조 문서

## 문서 정보
- **버전**: 1.0
- **작성일**: 2026-01-13
- **Base URL**: `http://localhost:9002`
- **상태**: 초안

---

## 1. 개요

### 1.1 API 서버 정보

| 항목 | 값 |
|------|-----|
| **Base URL** | `http://localhost:9002` |
| **API Docs** | `http://localhost:9002/docs` (Swagger UI) |
| **ReDoc** | `http://localhost:9002/redoc` |
| **Health Check** | `GET /health` |

### 1.2 공통 헤더

```http
Content-Type: application/json
Accept: application/json
```

### 1.3 공통 응답 형식

**성공 응답**:
```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

**에러 응답**:
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": { ... }
  }
}
```

### 1.4 에러 코드

| HTTP 코드 | 에러 코드 | 설명 |
|----------|----------|------|
| 400 | `BAD_REQUEST` | 잘못된 요청 파라미터 |
| 401 | `UNAUTHORIZED` | 인증 필요 |
| 403 | `FORBIDDEN` | 권한 없음 |
| 404 | `NOT_FOUND` | 리소스를 찾을 수 없음 |
| 422 | `VALIDATION_ERROR` | 입력값 검증 실패 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |
| 503 | `SERVICE_UNAVAILABLE` | 서비스 일시 중단 |

---

## 2. RAG API (`/api/rag/*`) ✅ 구현됨

문서 검색 및 AI 질의응답 API

### 2.1 SSE 스트리밍 채팅

**엔드포인트**: `POST /api/rag/chat`

**설명**: SSE(Server-Sent Events)를 통한 실시간 스트리밍 채팅

**Request**:
```typescript
interface ChatRequest {
  message: string;              // 사용자 질문 (필수)
  conversation_id?: string;     // 대화 ID (선택, 없으면 새 대화)
  use_agent?: boolean;          // Agent 모드 사용 여부 (기본: false)
  stream?: boolean;             // 스트리밍 여부 (기본: true)
}
```

**Request 예시**:
```http
POST /api/rag/chat
Content-Type: application/json

{
  "message": "보안 정책에서 출입 권한 관련 내용을 알려줘",
  "conversation_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
  "use_agent": false,
  "stream": true
}
```

**Response**: Server-Sent Events

```
event: message
data: {"type": "token", "content": "보안"}

event: message
data: {"type": "token", "content": " 정책"}

event: message
data: {"type": "token", "content": "에 따르면"}

...

event: message
data: {"type": "sources", "content": [{"title": "보안정책.pdf", "page": 12}]}

event: message
data: {"type": "done", "conversation_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890"}
```

**프론트엔드 연동** (`src/services/api.ts`):
```typescript
export async function sendMessage(
  message: string,
  conversationId?: string,
  useAgent: boolean = false,
  onChunk?: (chunk: string) => void,
  onSources?: (sources: Source[]) => void
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/rag/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      use_agent: useAgent,
      stream: true
    })
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader!.read();
    if (done) break;

    const chunk = decoder.decode(value);
    // SSE 파싱 및 콜백 호출
  }
}
```

---

### 2.2 단일 질의 (Non-streaming)

**엔드포인트**: `POST /api/rag/query`

**설명**: 스트리밍 없이 완전한 응답을 한 번에 반환

**Request**:
```typescript
interface QueryRequest {
  query: string;        // 질의 내용 (필수)
  k?: number;           // 검색할 문서 수 (기본: 5)
  threshold?: number;   // 유사도 임계값 (기본: 0.7)
}
```

**Response**:
```typescript
interface QueryResponse {
  answer: string;           // AI 응답
  sources: Source[];        // 참조 문서 목록
  confidence: number;       // 응답 신뢰도 (0-1)
  processing_time: number;  // 처리 시간 (ms)
}

interface Source {
  document_id: string;
  title: string;
  content: string;      // 발췌 내용
  page?: number;
  score: number;        // 유사도 점수
}
```

**프론트엔드 연동**:
```typescript
export async function sendQuery(query: string, k: number = 5): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/rag/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, k })
  });
  return response.json();
}
```

---

### 2.3 대화 목록 조회

**엔드포인트**: `GET /api/rag/conversations`

**설명**: 사용자의 대화 이력 목록 조회

**Query Parameters**:
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `page` | number | 아니오 | 1 | 페이지 번호 |
| `limit` | number | 아니오 | 20 | 페이지당 항목 수 |

**Response**:
```typescript
interface ConversationsResponse {
  conversations: Conversation[];
  total: number;
  page: number;
  limit: number;
}

interface Conversation {
  id: string;
  title: string;          // 첫 메시지 기반 자동 생성
  created_at: string;     // ISO 8601
  updated_at: string;
  message_count: number;
  preview: string;        // 마지막 메시지 미리보기
}
```

---

## 3. 이미지 분석 API (`/api/image/*`) ✅ 구현됨

CCTV 이미지 분석 및 보안 사고 감지 API

### 3.1 이미지 분석 요청

**엔드포인트**: `POST /api/image/analyze`

**설명**: 단일 이미지를 분석하여 보안 사고 감지

**Request**:
```typescript
// FormData 또는 JSON
interface AnalyzeRequest {
  image: File | string;      // 파일 또는 Base64 인코딩
  prompt?: string;           // 추가 분석 지시 (선택)
  detect_incidents?: boolean; // 사고 감지 여부 (기본: true)
}
```

**Request 예시 (FormData)**:
```http
POST /api/image/analyze
Content-Type: multipart/form-data

------boundary
Content-Disposition: form-data; name="image"; filename="cctv_001.jpg"
Content-Type: image/jpeg

[Binary image data]
------boundary
Content-Disposition: form-data; name="prompt"

이 이미지에서 보안 위협 요소를 분석해주세요
------boundary--
```

**Request 예시 (JSON/Base64)**:
```http
POST /api/image/analyze
Content-Type: application/json

{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "prompt": "이 이미지에서 보안 위협 요소를 분석해주세요",
  "detect_incidents": true
}
```

**Response**:
```typescript
interface AnalysisResult {
  id: string;                    // 분석 ID (UUID)
  timestamp: string;             // ISO 8601
  image_url?: string;            // 저장된 이미지 URL
  analysis: string;              // 전체 분석 텍스트
  incidents: Incident[];         // 감지된 사고 목록
  severity: SeverityLevel;       // 종합 심각도
  confidence: number;            // 분석 신뢰도 (0-1)
  processing_time: number;       // 처리 시간 (ms)
}

interface Incident {
  type: IncidentType;
  description: string;
  location?: string;             // 이미지 내 위치 설명
  confidence: number;
  bounding_box?: BoundingBox;    // 감지 영역 (선택)
}

type IncidentType =
  | 'fire'              // 화재
  | 'smoke'             // 연기
  | 'intrusion'         // 침입
  | 'vandalism'         // 기물파손
  | 'accident'          // 사고
  | 'abandoned_object'  // 유기물품
  | 'crowd'             // 군중밀집
  | 'fight'             // 싸움
  | 'weapon'            // 무기
  | 'normal';           // 정상

type SeverityLevel = 'Critical' | 'High' | 'Medium' | 'Low';

interface BoundingBox {
  x: number;      // 좌상단 X (0-1 정규화)
  y: number;      // 좌상단 Y
  width: number;
  height: number;
}
```

**프론트엔드 연동** (`src/services/imageAnalysisApi.ts`):
```typescript
export async function analyzeImage(
  imageBase64: string,
  prompt?: string
): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE_URL}/api/image/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image: imageBase64,
      prompt,
      detect_incidents: true
    })
  });
  return response.json();
}
```

---

### 3.2 배치 분석

**엔드포인트**: `POST /api/image/batch`

**설명**: 여러 이미지를 동시에 분석

**Request**:
```typescript
interface BatchAnalyzeRequest {
  images: Array<{
    id: string;           // 클라이언트 지정 ID
    image: string;        // Base64
  }>;
  prompt?: string;        // 공통 프롬프트
}
```

**Response**:
```typescript
interface BatchAnalyzeResponse {
  results: Array<{
    id: string;                   // 클라이언트 지정 ID
    analysis_id: string;          // 서버 생성 분석 ID
    status: 'success' | 'error';
    result?: AnalysisResult;
    error?: string;
  }>;
  total: number;
  success_count: number;
  error_count: number;
}
```

---

### 3.3 분석 결과 조회

**엔드포인트**: `GET /api/image/{analysis_id}`

**설명**: 특정 분석 결과 상세 조회

**Path Parameters**:
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `analysis_id` | string | 분석 ID (UUID) |

**Response**: `AnalysisResult` (3.1 참조)

---

### 3.4 보고서 생성

**엔드포인트**: `POST /api/report/generate`

**설명**: 분석 결과를 기반으로 보고서 생성

**Request**:
```typescript
interface ReportGenerateRequest {
  analysis_id: string;               // 분석 ID
  format?: 'markdown' | 'pdf';       // 출력 형식 (기본: markdown)
  include_image?: boolean;           // 이미지 포함 여부 (기본: true)
  language?: 'ko' | 'en';            // 언어 (기본: ko)
}
```

**Response**:
```typescript
interface ReportGenerateResponse {
  report_id: string;
  format: string;
  content: string;            // Markdown 내용 (format=markdown)
  download_url?: string;      // 다운로드 URL (format=pdf)
  generated_at: string;
}
```

**프론트엔드 연동**:
```typescript
export async function generateIncidentReport(
  analysisId: string,
  format: 'markdown' | 'pdf' = 'markdown'
): Promise<ReportGenerateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/report/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analysis_id: analysisId,
      format,
      include_image: true,
      language: 'ko'
    })
  });
  return response.json();
}
```

---

## 4. 제어 API (`/control/*`) ✅ 구현됨

외부 시스템 (ACU/CCTV) 제어 API

> **업데이트 (2026-01-13)**: 백엔드 API 경로가 `/api/control/*`에서 `/control/*`로 변경됨. 프론트엔드 `controlApi.ts` 수정 완료.

### 4.1 자연어 명령 처리

**엔드포인트**: `POST /control/command`

**설명**: 자연어 명령을 분석하여 적절한 제어 액션 실행

**Request**:
```typescript
interface CommandRequest {
  command: string;           // 자연어 명령 (필수)
  target?: string;           // 대상 지정 (선택)
  confirm?: boolean;         // 실행 전 확인 필요 (기본: false)
}
```

**Request 예시**:
```json
{
  "command": "1번 출입문 5초간 열어줘",
  "target": "acu"
}
```

**Response**:
```typescript
interface CommandResponse {
  success: boolean;
  command: string;           // 원본 명령
  interpreted: string;       // 해석된 명령
  actions: CommandAction[];  // 실행된 액션 목록
  message: string;           // 결과 메시지
  timestamp: string;
}

interface CommandAction {
  type: 'acu_unlock' | 'acu_lock' | 'cctv_move' | 'cctv_preset';
  target_id: string;
  parameters: Record<string, unknown>;
  status: 'success' | 'failed' | 'pending';
  result?: unknown;
}
```

**예상 프론트엔드 연동** (`src/services/controlApi.ts`):
```typescript
export async function sendCommand(command: string): Promise<CommandResponse> {
  const response = await fetch(`${API_BASE_URL}/api/control/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command })
  });
  return response.json();
}
```

---

### 4.2 ACU 출입문 해제

**엔드포인트**: `POST /control/acu/door/unlock`

**설명**: 특정 출입문 잠금 해제

**Request**:
```typescript
interface UnlockRequest {
  door_id: string;           // 출입문 ID (필수)
  duration?: number;         // 해제 유지 시간 (초, 기본: 5)
  reason?: string;           // 해제 사유 (선택)
}
```

**Response**:
```typescript
interface DoorActionResponse {
  success: boolean;
  door_id: string;
  action: 'unlock' | 'lock';
  status: DoorStatus;
  message: string;
  expires_at?: string;       // 자동 잠금 시간 (unlock 시)
}

interface DoorStatus {
  id: string;
  name: string;
  location: string;
  status: 'locked' | 'unlocked' | 'error';
  last_action: {
    type: string;
    timestamp: string;
    user_id?: string;
  };
}
```

**예상 프론트엔드 연동**:
```typescript
export async function unlockDoor(
  doorId: string,
  duration: number = 5
): Promise<DoorActionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/control/acu/unlock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ door_id: doorId, duration })
  });
  return response.json();
}
```

---

### 4.3 ACU 출입문 잠금

**엔드포인트**: `POST /control/acu/door/lock`

**설명**: 특정 출입문 잠금

**Request**:
```typescript
interface LockRequest {
  door_id: string;           // 출입문 ID (필수)
  reason?: string;           // 잠금 사유 (선택)
}
```

**Response**: `DoorActionResponse` (4.2 참조)

---

### 4.4 ACU 상태 조회

**엔드포인트**: `GET /control/acu/door/status`

**설명**: 전체 또는 특정 출입문 상태 조회

**Query Parameters**:
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `door_id` | string | 아니오 | 특정 출입문 ID |

**Response**:
```typescript
interface ACUStatusResponse {
  doors: DoorStatus[];
  total: number;
  online: number;
  offline: number;
  timestamp: string;
}
```

---

### 4.5 출입 이력 조회

**엔드포인트**: `GET /control/acu/log`

**설명**: 출입 이력 로그 조회

**Query Parameters**:
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `door_id` | string | 아니오 | - | 특정 출입문 필터 |
| `from` | string | 아니오 | 24시간 전 | 시작 시간 (ISO 8601) |
| `to` | string | 아니오 | 현재 | 종료 시간 (ISO 8601) |
| `limit` | number | 아니오 | 100 | 최대 결과 수 |
| `action` | string | 아니오 | - | 액션 필터 (entry/exit/denied) |

**Response**:
```typescript
interface AccessLogsResponse {
  logs: AccessLog[];
  total: number;
  has_more: boolean;
}

interface AccessLog {
  id: string;
  door_id: string;
  door_name: string;
  user_id: string;
  user_name: string;
  action: 'entry' | 'exit' | 'denied' | 'forced';
  method: 'card' | 'pin' | 'biometric' | 'remote';
  timestamp: string;
  details?: string;
}
```

---

### 4.6 CCTV PTZ 이동

**엔드포인트**: `POST /control/cctv/camera/move`

**설명**: CCTV PTZ (Pan/Tilt/Zoom) 제어

**Request**:
```typescript
interface PTZMoveRequest {
  camera_id: string;         // 카메라 ID (필수)
  pan?: number;              // Pan 각도 (-180 ~ 180)
  tilt?: number;             // Tilt 각도 (-90 ~ 90)
  zoom?: number;             // Zoom 레벨 (0 ~ 100)
  relative?: boolean;        // 상대 이동 여부 (기본: false)
}
```

**Response**:
```typescript
interface PTZMoveResponse {
  success: boolean;
  camera_id: string;
  position: {
    pan: number;
    tilt: number;
    zoom: number;
  };
  message: string;
}
```

**예상 프론트엔드 연동**:
```typescript
export async function moveCamera(
  cameraId: string,
  pan?: number,
  tilt?: number,
  zoom?: number
): Promise<PTZMoveResponse> {
  const response = await fetch(`${API_BASE_URL}/api/control/cctv/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      camera_id: cameraId,
      pan,
      tilt,
      zoom
    })
  });
  return response.json();
}
```

---

### 4.7 CCTV 프리셋 이동

**엔드포인트**: `POST /control/cctv/camera/preset`

**설명**: 저장된 프리셋 위치로 카메라 이동

**Request**:
```typescript
interface PresetMoveRequest {
  camera_id: string;         // 카메라 ID (필수)
  preset_id: string;         // 프리셋 ID (필수)
}
```

**Response**: `PTZMoveResponse` (4.6 참조)

---

### 4.8 CCTV 상태 조회

**엔드포인트**: `GET /control/cctv/camera/status`

**설명**: 전체 또는 특정 카메라 상태 조회

**Query Parameters**:
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `camera_id` | string | 아니오 | 특정 카메라 ID |

**Response**:
```typescript
interface CCTVStatusResponse {
  cameras: CameraStatus[];
  total: number;
  online: number;
  offline: number;
  recording: number;
  timestamp: string;
}

interface CameraStatus {
  id: string;
  name: string;
  location: string;
  status: 'online' | 'offline' | 'error';
  position: {
    pan: number;
    tilt: number;
    zoom: number;
  };
  recording: boolean;
  presets: Preset[];
  stream_url?: string;
}

interface Preset {
  id: string;
  name: string;
  position: {
    pan: number;
    tilt: number;
    zoom: number;
  };
}
```

---

## 5. 문서 관리 API (`/api/documents/*`) ⚠️ 부분 구현

RAG 검색용 문서 업로드 및 관리 API

### 5.1 문서 업로드

**엔드포인트**: `POST /api/documents/upload`

**설명**: RAG 인덱싱을 위한 문서 업로드

**Request**:
```http
POST /api/documents/upload
Content-Type: multipart/form-data

------boundary
Content-Disposition: form-data; name="file"; filename="manual.pdf"
Content-Type: application/pdf

[Binary file data]
------boundary
Content-Disposition: form-data; name="metadata"

{"category": "manual", "tags": ["security", "policy"]}
------boundary--
```

**지원 형식**: txt, pdf, md, docx (최대 10MB)

**Response**:
```typescript
interface UploadResponse {
  document_id: string;
  filename: string;
  size: number;              // bytes
  status: 'processing' | 'indexed' | 'error';
  chunks: number;            // 분할된 청크 수
  created_at: string;
}
```

---

### 5.2 문서 목록 조회

**엔드포인트**: `GET /api/documents`

**Query Parameters**:
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `page` | number | 아니오 | 1 | 페이지 번호 |
| `limit` | number | 아니오 | 20 | 페이지당 항목 수 |
| `status` | string | 아니오 | - | 상태 필터 |

**Response**:
```typescript
interface DocumentsResponse {
  documents: Document[];
  total: number;
  page: number;
  limit: number;
}

interface Document {
  id: string;
  filename: string;
  size: number;
  mime_type: string;
  status: 'processing' | 'indexed' | 'error';
  chunks: number;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}
```

---

### 5.3 문서 삭제

**엔드포인트**: `DELETE /api/documents/{document_id}`

**Path Parameters**:
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `document_id` | string | 문서 ID |

**Response**:
```typescript
interface DeleteResponse {
  success: boolean;
  document_id: string;
  message: string;
}
```

---

## 6. 프론트엔드 서비스 매핑

### 6.1 현재 구현된 서비스

| 서비스 파일 | 담당 API | 상태 |
|------------|---------|------|
| `src/services/api.ts` | RAG API | ✅ 구현됨 |
| `src/services/imageAnalysisApi.ts` | 이미지 분석 API | ✅ 구현됨 |

### 6.2 신규 생성 필요 서비스

| 서비스 파일 | 담당 API | 상태 |
|------------|---------|------|
| `src/services/controlApi.ts` | 제어 API | ✅ 구현됨 |
| `src/services/documentsApi.ts` | 문서 관리 API | 🚧 신규 필요 |
| `src/services/reportsApi.ts` | 보고서 API | 🚧 신규 필요 |

### 6.3 controlApi.ts 구현 (구현 완료)

> **업데이트 (2026-01-13)**: `src/services/controlApi.ts` 파일이 올바른 API 경로로 구현됨.

```typescript
// src/services/controlApi.ts
// Vite proxy가 /control → localhost:9002/control로 라우팅
const API_BASE = '/control';

// 자연어 명령
export async function sendCommand(request: SendCommandRequest): Promise<CommandResult> {
  const response = await fetch(`${API_BASE}/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error('명령 실행에 실패했습니다.');
  return response.json();
}

// ACU 제어
export async function getDoorStatus(): Promise<DoorStatus[]> {
  const response = await fetch(`${API_BASE}/acu/door/status`);
  if (!response.ok) throw new Error('출입문 상태 조회에 실패했습니다.');
  const result = await response.json();
  return result.doors || (Array.isArray(result) ? result : [result]);
}

export async function unlockDoor(request: UnlockDoorRequest): Promise<DoorStatus> {
  const response = await fetch(`${API_BASE}/acu/door/unlock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error('출입문 해제에 실패했습니다.');
  return response.json();
}

export async function lockDoor(doorId: string): Promise<DoorStatus> {
  const response = await fetch(`${API_BASE}/acu/door/lock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doorId)
  });
  if (!response.ok) throw new Error('출입문 잠금에 실패했습니다.');
  return response.json();
}

export async function getAccessLogs(doorId?: string, limit: number = 50): Promise<AccessLog[]> {
  const params = new URLSearchParams();
  if (doorId) params.append('door_id', doorId);
  params.append('limit', limit.toString());
  const response = await fetch(`${API_BASE}/acu/log?${params}`);
  if (!response.ok) throw new Error('출입 이력 조회에 실패했습니다.');
  const result = await response.json();
  return result.logs || result;
}

// CCTV 제어
export async function getCameraStatus(): Promise<CameraStatus[]> {
  const response = await fetch(`${API_BASE}/cctv/camera/status`);
  if (!response.ok) throw new Error('카메라 상태 조회에 실패했습니다.');
  const result = await response.json();
  return result.cameras || (Array.isArray(result) ? result : [result]);
}

export async function moveCamera(request: MoveCameraRequest): Promise<CameraStatus> {
  const response = await fetch(`${API_BASE}/cctv/camera/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error('카메라 이동에 실패했습니다.');
  return response.json();
}

export async function goToPreset(request: GoToPresetRequest): Promise<CameraStatus> {
  const response = await fetch(`${API_BASE}/cctv/camera/preset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error('프리셋 이동에 실패했습니다.');
  return response.json();
}

export async function startRecording(
  cameraId: string,
  duration: number = 0,
  quality: string = 'high'
): Promise<CameraStatus> {
  const response = await fetch(`${API_BASE}/cctv/recording/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ camera_id: cameraId, duration, quality })
  });
  if (!response.ok) throw new Error('녹화 시작에 실패했습니다.');
  return response.json();
}

export async function stopRecording(cameraId: string): Promise<CameraStatus> {
  const response = await fetch(`${API_BASE}/cctv/recording/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cameraId)
  });
  if (!response.ok) throw new Error('녹화 중지에 실패했습니다.');
  return response.json();
}
```

---

## 7. TypeScript 타입 정의

### 7.1 현재 구현된 타입

**위치**: `src/types/`

```typescript
// src/types/analysis.ts ✅
export interface AnalysisResult { ... }
export interface Incident { ... }
export type IncidentType = ...;
export type SeverityLevel = ...;

// src/types/chat.ts ✅
export interface Message { ... }
export interface Conversation { ... }
export interface Source { ... }
```

### 7.2 신규 생성 필요 타입

```typescript
// src/types/control.ts 🚧 신규

// 공통
export interface CommandResponse {
  success: boolean;
  command: string;
  interpreted: string;
  actions: CommandAction[];
  message: string;
  timestamp: string;
}

export interface CommandAction {
  type: 'acu_unlock' | 'acu_lock' | 'cctv_move' | 'cctv_preset';
  target_id: string;
  parameters: Record<string, unknown>;
  status: 'success' | 'failed' | 'pending';
  result?: unknown;
}

// ACU
export interface DoorStatus {
  id: string;
  name: string;
  location: string;
  status: 'locked' | 'unlocked' | 'error';
  last_action: {
    type: string;
    timestamp: string;
    user_id?: string;
  };
}

export interface DoorActionResponse {
  success: boolean;
  door_id: string;
  action: 'unlock' | 'lock';
  status: DoorStatus;
  message: string;
  expires_at?: string;
}

export interface ACUStatusResponse {
  doors: DoorStatus[];
  total: number;
  online: number;
  offline: number;
  timestamp: string;
}

export interface AccessLog {
  id: string;
  door_id: string;
  door_name: string;
  user_id: string;
  user_name: string;
  action: 'entry' | 'exit' | 'denied' | 'forced';
  method: 'card' | 'pin' | 'biometric' | 'remote';
  timestamp: string;
  details?: string;
}

export interface AccessLogsResponse {
  logs: AccessLog[];
  total: number;
  has_more: boolean;
}

// CCTV
export interface CameraStatus {
  id: string;
  name: string;
  location: string;
  status: 'online' | 'offline' | 'error';
  position: PTZPosition;
  recording: boolean;
  presets: Preset[];
  stream_url?: string;
}

export interface PTZPosition {
  pan: number;
  tilt: number;
  zoom: number;
}

export interface Preset {
  id: string;
  name: string;
  position: PTZPosition;
}

export interface PTZMoveResponse {
  success: boolean;
  camera_id: string;
  position: PTZPosition;
  message: string;
}

export interface CCTVStatusResponse {
  cameras: CameraStatus[];
  total: number;
  online: number;
  offline: number;
  recording: number;
  timestamp: string;
}
```

---

## 8. 환경 변수

### 8.1 프론트엔드 환경 변수 (.env)

```env
# API 서버 설정
VITE_API_BASE_URL=http://localhost:9002

# 개발 모드 설정
VITE_DEV_MODE=true

# SSE 타임아웃 (ms)
VITE_SSE_TIMEOUT=60000
```

### 8.2 사용 예시

```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:9002';
```

---

## 범례

| 기호 | 의미 |
|-----|------|
| ✅ | 구현됨 (백엔드 + 프론트엔드) |
| ⚠️ | 부분 구현 |
| 🚧 | 미구현 (신규 필요) |
