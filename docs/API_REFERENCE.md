# Total-LLM API Reference

이 문서는 Total-LLM 백엔드 API의 완전한 명세서입니다.

---

## 목차

1. [개요](#개요)
2. [인증](#인증)
3. [공통 응답 형식](#공통-응답-형식)
4. [Security Chat API](#1-security-chat-api)
5. [Control API](#2-control-api)
6. [Image Analysis API](#3-image-analysis-api)
7. [Document API](#4-document-api)
8. [Alarm API](#5-alarm-api)
9. [Device API](#6-device-api)
10. [Report API](#7-report-api)
11. [Log Ingestion API](#8-log-ingestion-api)
12. [System Control API](#9-system-control-api)
13. [API Generator](#10-api-generator)
14. [에러 코드](#에러-코드)

---

## 개요

### 기본 정보

| 항목 | 값 |
|------|-----|
| Base URL | `http://localhost:9002` |
| 프로토콜 | HTTP/1.1, WebSocket |
| 인코딩 | UTF-8 |
| 콘텐츠 타입 | `application/json` |
| API 문서 | `http://localhost:9002/docs` (Swagger UI) |
| ReDoc | `http://localhost:9002/redoc` |

### API 통계

| API 라우터 | 엔드포인트 수 | 주요 기능 |
|-----------|-------------|----------|
| Security Chat | 3 | LLM 기반 보안 모니터링 채팅 |
| Control | 23 | ACU/CCTV 장치 제어 |
| Image Analysis | 6 | Vision AI 이미지 분석 |
| Document | 7 | RAG 문서 관리 |
| Alarm | 8 | 알람 관리 |
| Device | 7 | 장치 등록/관리 |
| Report | 6 | 보고서 생성 |
| Log Ingestion | 4 | 로그 인덱싱/검색 |
| System Control | 6 | 서버 관리 |
| API Generator | 14 | 자동 코드 생성 |
| **총계** | **84** | |

---

## 인증

현재 버전은 인증이 구현되어 있지 않습니다. 프로덕션 환경에서는 JWT 기반 인증을 추가할 예정입니다.

```http
# 향후 인증 헤더 형식
Authorization: Bearer <jwt_token>
```

---

## 공통 응답 형식

### 성공 응답

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}
```

### 에러 응답

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2026-01-16T12:00:00Z"
}
```

---

## 1. Security Chat API

LLM 기반 보안 모니터링 채팅 시스템. SSE(Server-Sent Events) 스트리밍 지원.

**Prefix**: `/api/security`
**Tags**: `security`

### 스키마

#### ChatRequest

```typescript
interface ChatRequest {
  message: string;              // 사용자 메시지 (필수)
  mode?: string;                // "qa" | "device_register" | "device_control" (기본: "qa")
  conversation_history?: Message[];  // 대화 이력 (기본: [])
}

interface Message {
  role: "user" | "assistant";
  content: string;
}
```

#### ChatResponse

```typescript
interface ChatResponse {
  response: string;
  function_calls?: FunctionCall[];
  mode: string;
}
```

### 엔드포인트

#### POST /api/security/chat

보안 모니터링 채팅 (SSE 스트리밍)

**Request Body**: `ChatRequest`

**Response**: `text/event-stream` (Server-Sent Events)

```bash
curl -X POST "http://localhost:9002/api/security/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "CCTV 설치 기준에 대해 알려줘",
    "mode": "qa",
    "conversation_history": []
  }'
```

**SSE 이벤트 형식**:
```
data: {"type": "token", "content": "응답 내용..."}
data: {"type": "source", "sources": [...]}
data: {"type": "done"}
```

---

#### GET /api/security/modes

사용 가능한 채팅 모드 목록 조회

**Response**:
```json
{
  "modes": [
    {
      "id": "qa",
      "name": "문서 Q&A",
      "description": "보안 문서 기반 질의응답",
      "icon": "📚"
    },
    {
      "id": "device_control",
      "name": "장치 제어",
      "description": "자연어로 CCTV/ACU 제어",
      "icon": "🎛️"
    }
  ]
}
```

---

#### GET /api/security/health

서비스 상태 확인

**Response**:
```json
{
  "status": "healthy",
  "orchestrator": true,
  "llm": true
}
```

---

## 2. Control API

ACU(출입통제) 및 CCTV 장치 제어 API. 자연어 명령 및 직접 함수 호출 지원.

**Prefix**: `/control`
**Tags**: `Control`

### 스키마

#### CommandRequest

```typescript
interface CommandRequest {
  command: string;      // 자연어 명령 (필수)
  use_llm?: boolean;    // LLM 사용 여부 (기본: true)
}
```

#### FunctionCallRequest

```typescript
interface FunctionCallRequest {
  function_name: string;         // 함수 이름 (필수)
  arguments?: Record<string, any>;  // 함수 인자 (기본: {})
}
```

#### PTZRequest

```typescript
interface PTZRequest {
  camera_id: string;    // 카메라 ID (필수)
  pan?: number;         // 수평 이동 (-180 ~ 180)
  tilt?: number;        // 수직 이동 (-90 ~ 90)
  zoom?: number;        // 줌 레벨 (1 ~ 20)
}
```

### 자연어 명령

#### POST /control/command

자연어 명령 처리

```bash
curl -X POST "http://localhost:9002/control/command" \
  -H "Content-Type: application/json" \
  -d '{"command": "1번 카메라 왼쪽으로 30도 이동해줘"}'
```

**Response**:
```json
{
  "success": true,
  "result": {
    "action": "move_camera",
    "camera_id": "cam_001",
    "pan": -30
  },
  "message": "카메라가 왼쪽으로 30도 이동했습니다."
}
```

---

#### POST /control/function

함수 직접 호출

```bash
curl -X POST "http://localhost:9002/control/function" \
  -H "Content-Type: application/json" \
  -d '{
    "function_name": "move_camera",
    "arguments": {"camera_id": "cam_001", "pan": -30}
  }'
```

---

#### GET /control/functions

사용 가능한 함수 목록 조회

**Response**:
```json
{
  "total": 18,
  "categories": {
    "ACU": ["unlock_door", "lock_door", "get_door_status", ...],
    "CCTV": ["move_camera", "go_to_preset", "start_recording", ...]
  },
  "schemas": [...]
}
```

---

### ACU 제어

#### POST /control/acu/door/unlock

출입문 열기

**Request Body**:
```json
{
  "door_id": "door_001",
  "duration": 5
}
```

**Response**:
```json
{
  "success": true,
  "door_id": "door_001",
  "status": "unlocked",
  "duration": 5,
  "message": "출입문이 5초간 열립니다."
}
```

---

#### POST /control/acu/door/lock

출입문 잠금

**Request Body**:
```json
{
  "door_id": "door_001"
}
```

---

#### GET /control/acu/door/status

출입문 상태 조회

**Query Parameters**:
- `door_id` (optional): 특정 출입문 ID

**Response**:
```json
{
  "doors": [
    {
      "door_id": "door_001",
      "name": "정문",
      "status": "locked",
      "last_access": "2026-01-16T10:30:00Z"
    }
  ]
}
```

---

#### GET /control/acu/log

출입 이력 조회

**Query Parameters**:
- `door_id` (optional): 특정 출입문 ID
- `limit` (1-100, default: 50): 조회 개수

---

#### POST /control/acu/permission/grant

출입 권한 부여

**Request Body**:
```json
{
  "user_id": "user_001",
  "door_ids": ["door_001", "door_002"],
  "valid_from": "2026-01-16T00:00:00Z",
  "valid_until": "2026-12-31T23:59:59Z"
}
```

---

#### POST /control/acu/emergency/unlock

비상 전체 개방

**Request Body**:
```json
{
  "reason": "화재 대피",
  "authorized_by": "admin"
}
```

---

### CCTV 제어

#### POST /control/cctv/camera/move

카메라 PTZ 제어

**Request Body**:
```json
{
  "camera_id": "cam_001",
  "pan": 45,
  "tilt": -15,
  "zoom": 2
}
```

---

#### POST /control/cctv/camera/preset

프리셋으로 이동

**Request Body**:
```json
{
  "camera_id": "cam_001",
  "preset_id": "preset_lobby"
}
```

---

#### POST /control/cctv/recording/start

녹화 시작

**Request Body**:
```json
{
  "camera_id": "cam_001",
  "duration": 60,
  "quality": "high"
}
```

---

#### POST /control/cctv/snapshot

스냅샷 캡처

**Request Body**:
```json
{
  "camera_id": "cam_001",
  "resolution": "1080p"
}
```

**Response**:
```json
{
  "success": true,
  "camera_id": "cam_001",
  "image_path": "/data/snapshots/cam_001_20260116_103000.jpg",
  "timestamp": "2026-01-16T10:30:00Z"
}
```

---

### 네트워크 스캔

#### POST /control/network/scan

네트워크 장치 스캔

**Request Body**:
```json
{
  "subnet": "192.168.1.0/24",
  "device_types": ["ip_camera", "nvr", "acu"]
}
```

**Response**:
```json
{
  "success": true,
  "subnet": "192.168.1.0/24",
  "total_found": 5,
  "devices": [
    {
      "ip": "192.168.1.100",
      "port": 80,
      "device_type": "ip_camera",
      "manufacturer": "Hanwha",
      "model": "XNV-8080R"
    }
  ]
}
```

---

## 3. Image Analysis API

Qwen2-VL 기반 CCTV 이미지 분석. 9가지 보안 사고 유형 자동 분류.

**Prefix**: `/image`
**Tags**: `Image Analysis`

### 사고 유형

| 코드 | 한국어 | 설명 |
|------|-------|------|
| `fire` | 화재 | 불꽃, 연기 감지 |
| `smoke` | 연기 | 연기만 감지 (화재 전조) |
| `intrusion` | 침입 | 비인가 구역 침입 |
| `vandalism` | 기물파손 | 시설물 손상 행위 |
| `accident` | 사고 | 교통/안전 사고 |
| `abandoned_object` | 유기물 | 방치된 물품 |
| `crowd` | 군중 | 비정상적 군중 밀집 |
| `fight` | 싸움 | 폭력/다툼 행위 |
| `weapon` | 무기 | 위험 물품 소지 |
| `normal` | 정상 | 이상 없음 |

### 심각도 레벨

| 레벨 | 설명 | 대응 시간 |
|------|------|----------|
| `critical` | 즉시 대응 필요 | 즉시 |
| `high` | 긴급 확인 필요 | 5분 이내 |
| `medium` | 주의 관찰 | 30분 이내 |
| `low` | 참고 사항 | 업무 시간 내 |

### 스키마

#### ImageAnalyzeRequest

```typescript
interface ImageAnalyzeRequest {
  image_base64: string;     // Base64 인코딩된 이미지 (필수)
  prompt?: string;          // 추가 분석 프롬프트
  location?: string;        // 위치 정보 (기본: "미지정")
  mode?: "quick" | "standard" | "detailed";  // 분석 모드 (기본: "standard")
}
```

#### ImageAnalyzeResponse

```typescript
interface ImageAnalyzeResponse {
  success: boolean;
  analysis_id: string;
  timestamp: string;
  location: string;
  incident_type: string;        // 영문 사고 유형
  incident_type_ko: string;     // 한국어 사고 유형
  severity: string;             // 영문 심각도
  severity_ko: string;          // 한국어 심각도
  confidence: number;           // 신뢰도 (0-1)
  description?: string;         // 상세 설명
  recommended_actions: string[]; // 권장 조치
  raw_analysis?: string;        // VLM 원본 응답
}
```

### 엔드포인트

#### POST /image/analyze

Base64 이미지 분석

```bash
curl -X POST "http://localhost:9002/image/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "/9j/4AAQSkZJRg...",
    "location": "A동 로비",
    "mode": "standard"
  }'
```

**Response**:
```json
{
  "success": true,
  "analysis_id": "img_20260116_001",
  "timestamp": "2026-01-16T10:30:00Z",
  "location": "A동 로비",
  "incident_type": "normal",
  "incident_type_ko": "정상",
  "severity": "low",
  "severity_ko": "낮음",
  "confidence": 0.95,
  "description": "로비 공간에 이상 징후가 감지되지 않았습니다.",
  "recommended_actions": ["정기 모니터링 유지"]
}
```

---

#### POST /image/analyze/upload

파일 업로드 이미지 분석

```bash
curl -X POST "http://localhost:9002/image/analyze/upload" \
  -F "file=@cctv_image.jpg" \
  -F "location=A동 로비" \
  -F "mode=standard"
```

---

#### POST /image/analyze/batch

배치 이미지 분석

**Request Body**:
```json
{
  "images": [
    {"image_base64": "...", "location": "A동 1층"},
    {"image_base64": "...", "location": "B동 2층"}
  ],
  "mode": "quick"
}
```

---

#### POST /image/analyze/report

보안 보고서 생성

**Request Body**:
```json
{
  "analysis_ids": ["img_001", "img_002"],
  "format": "pdf",
  "include_images": true
}
```

---

#### GET /image/results/{analysis_id}

분석 결과 조회

```bash
curl "http://localhost:9002/image/results/img_20260116_001"
```

---

## 4. Document API

RAG(Retrieval-Augmented Generation) 문서 관리. 벡터 검색 기반 질의응답.

**Prefix**: `/`
**Tags**: `Documents`

### 지원 파일 형식

| 형식 | 확장자 | 설명 |
|------|-------|------|
| PDF | `.pdf` | Adobe PDF 문서 |
| Word | `.docx` | Microsoft Word 문서 |
| Text | `.txt` | 일반 텍스트 파일 |
| Markdown | `.md` | 마크다운 문서 |

### 엔드포인트

#### POST /upload

문서 업로드 및 인덱싱

```bash
curl -X POST "http://localhost:9002/upload" \
  -F "file=@security_manual.pdf"
```

**Response**:
```json
{
  "status": "ok",
  "filename": "security_manual.pdf",
  "size": 1048576,
  "chunks_indexed": 45
}
```

---

#### GET /documents

문서 목록 조회

**Response**:
```json
{
  "documents": [
    {
      "id": "doc_001",
      "filename": "security_manual.pdf",
      "size": 1048576,
      "uploaded_at": "2026-01-15T09:00:00Z",
      "chunks": 45
    }
  ]
}
```

---

#### GET /documents/{doc_id}/content

문서 내용 조회

```bash
curl "http://localhost:9002/documents/doc_001/content"
```

---

#### DELETE /documents/{doc_id}

문서 삭제

```bash
curl -X DELETE "http://localhost:9002/documents/doc_001"
```

---

#### POST /query/stream

RAG 질의 (스트리밍)

**Request Body**:
```json
{
  "query": "CCTV 설치 기준이 뭐야?",
  "k": 5
}
```

**Response**: `text/event-stream`
```
data: {"type": "source", "sources": [...]}
data: {"type": "token", "content": "CCTV 설치 기준은..."}
data: {"type": "done"}
```

---

## 5. Alarm API

보안 알람 관리 및 VLM 기반 이미지 분석.

**Prefix**: `/api/alarms`
**Tags**: `alarms`

### 스키마

#### Alarm

```typescript
interface Alarm {
  alarm_id: string;
  alarm_type: string;
  severity: string;
  location: string;
  timestamp: string;
  image_path?: string;
  device_id?: string;
  description: string;
  vlm_analysis?: object;
  is_processed: boolean;
  created_at: string;
}
```

### 엔드포인트

#### GET /api/alarms

알람 목록 조회

**Query Parameters**:
- `limit` (1-200, default: 50): 조회 개수
- `offset` (default: 0): 시작 위치
- `severity_filter` (optional): 심각도 필터
- `processed_only` (default: false): 처리된 알람만

---

#### GET /api/alarms/{alarm_id}

특정 알람 조회

---

#### POST /api/alarms/mark-processed

알람 처리 완료 표시

**Request Body**:
```json
{
  "alarm_ids": ["alarm_001", "alarm_002"]
}
```

---

#### GET /api/alarms/stats/summary

알람 통계 조회

**Response**:
```json
{
  "total_alarms": 150,
  "by_severity": {
    "critical": 5,
    "high": 20,
    "medium": 50,
    "low": 75
  },
  "unprocessed_count": 30,
  "recent_count_24h": 12
}
```

---

#### POST /api/alarms/{alarm_id}/analyze

알람 이미지 VLM 분석

**Request Body**:
```json
{
  "force": false
}
```

---

## 6. Device API

장치 등록 및 관리 (PostgreSQL 기반).

**Prefix**: `/api/devices`
**Tags**: `devices`

### 스키마

#### Device

```typescript
interface Device {
  device_id: string;
  device_type: "CCTV" | "ACU";
  manufacturer: string;
  ip_address: string;
  port: number;
  protocol: "SSH" | "REST" | "SNMP";
  location?: string;
  zone?: string;
  status: "online" | "offline" | "error";
  last_health_check?: string;
  cpu_usage?: number;
  memory_usage?: number;
  uptime_seconds?: number;
}
```

#### DeviceRegisterRequest

```typescript
interface DeviceRegisterRequest {
  device_type: "CCTV" | "ACU";
  manufacturer: string;
  ip_address: string;
  port?: number;           // default: 22
  protocol: "SSH" | "REST" | "SNMP";
  location?: string;
  zone?: string;
  username?: string;
  password?: string;
  api_key?: string;
}
```

### 엔드포인트

#### GET /api/devices

장비 목록 조회

**Query Parameters**:
- `device_type` ("all" | "CCTV" | "ACU", default: "all")
- `status_filter` ("all" | "online" | "offline", default: "all")

---

#### POST /api/devices/register

장비 등록

```bash
curl -X POST "http://localhost:9002/api/devices/register" \
  -H "Content-Type: application/json" \
  -d '{
    "device_type": "CCTV",
    "manufacturer": "한화",
    "ip_address": "192.168.1.100",
    "port": 80,
    "protocol": "REST",
    "location": "A동 1층",
    "username": "admin",
    "password": "password123"
  }'
```

---

#### POST /api/devices/control

장비 제어

**Request Body**:
```json
{
  "device_id": "CCTV-A101",
  "command": "move_camera",
  "duration_seconds": 5,
  "reason": "정기 순찰"
}
```

---

#### GET /api/devices/commands/available

사용 가능한 제어 명령 조회

**Response**:
```json
{
  "CCTV": [
    "move_camera", "go_to_preset", "start_recording",
    "stop_recording", "capture_snapshot"
  ],
  "ACU": [
    "unlock_door", "lock_door", "grant_permission",
    "revoke_permission"
  ]
}
```

---

## 7. Report API

보안 보고서 생성 및 관리.

**Prefix**: `/api/reports`
**Tags**: `reports`

### 엔드포인트

#### POST /api/reports/generate

보고서 생성

**Request Body**:
```json
{
  "alarm_ids": ["alarm_001", "alarm_002"],
  "include_images": true,
  "analyze_with_vlm": true
}
```

**Response**:
```json
{
  "report_id": 1,
  "pdf_path": "/data/reports/report_001.pdf",
  "total_alarms": 2,
  "critical_count": 1,
  "file_size_kb": 256.5
}
```

---

#### GET /api/reports/{report_id}/download

보고서 다운로드 (PDF)

```bash
curl -O "http://localhost:9002/api/reports/1/download"
```

---

#### GET /api/reports

보고서 목록 조회

**Query Parameters**:
- `limit` (default: 50): 조회 개수
- `offset` (default: 0): 시작 위치

---

## 8. Log Ingestion API

Fluentd 연동 로그 수집 및 벡터 검색.

**Prefix**: `/api/logs`
**Tags**: `logs`

### 스키마

#### LogEntry

```typescript
interface LogEntry {
  source_type: string;      // 로그 소스 (필수)
  timestamp?: string;       // ISO 8601 형식
  message: string;          // 로그 메시지 (필수)
  level?: string;           // "INFO" | "WARNING" | "ERROR" (기본: "INFO")
  host?: string;            // 호스트명 (기본: "unknown")
  metadata?: object;        // 추가 메타데이터
}
```

### 엔드포인트

#### POST /api/logs/ingest

로그 배치 수집

**Request Body**:
```json
{
  "logs": [
    {
      "source_type": "cctv",
      "timestamp": "2026-01-16T10:30:00Z",
      "message": "Motion detected in zone A",
      "level": "WARNING",
      "host": "cam-001"
    }
  ]
}
```

**Response**:
```json
{
  "status": "success",
  "indexed_count": 1,
  "failed_count": 0,
  "qdrant_ids": ["log_001"]
}
```

---

#### POST /api/logs/search

로그 검색 (벡터 유사도)

**Request Body**:
```json
{
  "query": "모션 감지 이벤트",
  "source_type_filter": "cctv",
  "top_k": 10
}
```

---

#### GET /api/logs/stats

로그 통계 조회

**Response**:
```json
{
  "total_logs": 10000,
  "by_source_type": {
    "cctv": 5000,
    "acu": 3000,
    "system": 2000
  },
  "last_indexed": "2026-01-16T10:30:00Z"
}
```

---

## 9. System Control API

vLLM 및 VLM 서버 프로세스 관리.

**Prefix**: `/system`
**Tags**: `System Control`

### 스키마

#### ServerStatus

```typescript
interface ServerStatus {
  server_type: string;      // "llm" | "vlm"
  name: string;
  running: boolean;
  pid?: string;             // PID 또는 Docker 컨테이너 ID
  port: number;
  message: string;
  is_docker: boolean;
}
```

### 엔드포인트

#### GET /system/servers

모든 서버 상태 확인

**Response**:
```json
{
  "servers": {
    "llm": {
      "server_type": "llm",
      "name": "vLLM Server (Qwen2.5-14B-AWQ)",
      "running": true,
      "pid": "12345",
      "port": 9000,
      "message": "Running",
      "is_docker": false
    },
    "vlm": {
      "server_type": "vlm",
      "name": "VLM Server (Qwen2-VL-7B)",
      "running": true,
      "pid": "abc123def",
      "port": 9001,
      "message": "Running in Docker",
      "is_docker": true
    }
  }
}
```

---

#### POST /system/servers/{server_type}/start

서버 시작

```bash
curl -X POST "http://localhost:9002/system/servers/llm/start"
```

---

#### POST /system/servers/{server_type}/stop

서버 중지

---

#### POST /system/servers/{server_type}/restart

서버 재시작

---

## 10. API Generator

LLM 기반 장치 분석 및 어댑터 코드 자동 생성.

**Prefix**: `/generator`
**Tags**: `API Generator`

### 워크플로우

```
1. 네트워크 스캔 → 장치 발견
2. /generator/analyze → LLM 기반 장치 분석
3. /generator/generate → 어댑터 코드 생성
4. /generator/review/submit → 리뷰 제출
5. /generator/review/{id}/approve → 승인
6. /generator/deploy → 시스템 배포
```

### 엔드포인트

#### POST /generator/analyze

장치 분석 (LLM 기반)

**Request Body**:
```json
{
  "device_id": "discovered_001",
  "ip": "192.168.1.100",
  "port": 80,
  "fingerprint": {
    "server_header": "nginx",
    "open_ports": [80, 554]
  },
  "include_docs": true
}
```

**Response**:
```json
{
  "analysis_id": "analysis_001",
  "device_type": "cctv",
  "manufacturer": "Hanwha",
  "model": "XNV-8080R",
  "protocols": ["onvif", "rtsp"],
  "confidence": 0.92,
  "status": "completed",
  "api_spec": {
    "base_url": "/stw-cgi",
    "auth_type": "digest",
    "endpoints": [...]
  }
}
```

---

#### POST /generator/generate

코드 생성

**Request Body**:
```json
{
  "analysis_id": "analysis_001",
  "targets": ["adapter", "schema", "endpoint"]
}
```

**Response**:
```json
{
  "generation_id": "gen_001",
  "artifacts": [
    {
      "id": "artifact_001",
      "type": "adapter",
      "file_name": "hanwha_adapter.py",
      "status": "draft"
    }
  ],
  "status": "completed"
}
```

---

#### GET /generator/artifact/{artifact_id}/preview

생성된 코드 미리보기

**Query Parameters**:
- `lines` (default: 50): 미리보기 줄 수

---

#### POST /generator/review/submit

리뷰 제출

**Request Body**:
```json
{
  "artifact_id": "artifact_001",
  "auto_validate": true
}
```

---

#### POST /generator/review/{review_id}/approve

리뷰 승인

**Request Body**:
```json
{
  "comment": "코드 검토 완료, 배포 승인"
}
```

---

#### POST /generator/deploy

어댑터 배포

**Request Body**:
```json
{
  "review_id": "review_001",
  "dry_run": false
}
```

**Response**:
```json
{
  "success": true,
  "artifact_type": "adapter",
  "file_path": "backend/services/control/adapters/cctv/hanwha.py",
  "deployed_at": "2026-01-16T10:30:00Z",
  "dry_run": false
}
```

---

## 에러 코드

### HTTP 상태 코드

| 코드 | 설명 | 대응 방법 |
|------|------|----------|
| 200 | 성공 | - |
| 201 | 생성됨 | - |
| 400 | 잘못된 요청 | 요청 파라미터 확인 |
| 401 | 인증 필요 | 인증 토큰 확인 |
| 403 | 권한 없음 | 접근 권한 확인 |
| 404 | 찾을 수 없음 | 리소스 ID 확인 |
| 422 | 유효성 검사 실패 | 요청 본문 형식 확인 |
| 500 | 서버 오류 | 서버 로그 확인 |
| 503 | 서비스 불가 | 외부 서비스 상태 확인 |

### 비즈니스 에러 코드

| 코드 | 설명 |
|------|------|
| `DEVICE_NOT_FOUND` | 장치를 찾을 수 없음 |
| `DEVICE_OFFLINE` | 장치가 오프라인 상태 |
| `INVALID_COMMAND` | 잘못된 명령 |
| `LLM_UNAVAILABLE` | LLM 서버 연결 불가 |
| `VLM_UNAVAILABLE` | VLM 서버 연결 불가 |
| `ANALYSIS_FAILED` | 이미지 분석 실패 |
| `DOCUMENT_TOO_LARGE` | 문서 크기 초과 |
| `RATE_LIMIT_EXCEEDED` | 요청 한도 초과 |

---

## 부록: cURL 예제 모음

### 이미지 분석

```bash
# 이미지 파일 분석
curl -X POST "http://localhost:9002/image/analyze/upload" \
  -F "file=@cctv_capture.jpg" \
  -F "location=A동 로비" \
  -F "mode=detailed"
```

### RAG 채팅

```bash
# 스트리밍 채팅
curl -N -X POST "http://localhost:9002/api/security/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "CCTV 설치 기준은?"}'
```

### 장치 제어

```bash
# 자연어 명령
curl -X POST "http://localhost:9002/control/command" \
  -H "Content-Type: application/json" \
  -d '{"command": "정문 출입문 5초간 열어줘"}'

# PTZ 제어
curl -X POST "http://localhost:9002/control/cctv/camera/move" \
  -H "Content-Type: application/json" \
  -d '{"camera_id": "cam_001", "pan": 45, "tilt": -10, "zoom": 2}'
```

### 서버 관리

```bash
# 서버 상태 확인
curl "http://localhost:9002/system/servers"

# VLM 서버 재시작
curl -X POST "http://localhost:9002/system/servers/vlm/restart"
```

---

*Last Updated: 2026-01-16*
