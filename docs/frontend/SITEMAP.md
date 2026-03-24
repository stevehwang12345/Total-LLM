# Total-LLM 프론트엔드 사이트맵

## 문서 정보
- **버전**: 1.1
- **작성일**: 2026-01-13
- **최종 수정**: 2026-01-13
- **상태**: 구현 완료

---

## 1. 전체 사이트 구조 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Total-LLM 프론트엔드                                │
│                        http://localhost:9004                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   / (Dashboard) │       │     /chat       │       │   /analysis     │
│   메인 대시보드  │       │   RAG 채팅      │       │  이미지 분석     │
│   ✅ 구현됨     │       │   ✅ 100%       │       │   ✅ 구현됨     │
└─────────────────┘       └─────────────────┘       └─────────────────┘

         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    /control     │       │   /documents    │       │    /reports     │
│  시스템 제어    │       │    문서 관리     │       │   보고서 관리    │
│   ✅ 85%        │       │    ✅ 구현됨    │       │   ✅ 구현됨     │
└─────────────────┘       └─────────────────┘       └─────────────────┘

                                     │
                                     ▼
                          ┌─────────────────┐
                          │    /settings    │
                          │      설정       │
                          │   ✅ 구현됨     │
                          └─────────────────┘
```

---

## 2. 페이지 계층 구조

### 2.1 전체 구조

```
/                                    # 메인 대시보드 (홈) ✅
│
├── /chat                            # RAG 채팅 (기능 2) ✅
│   - 이미지 분석 통합
│   - SSE 스트리밍
│   - Agent 모드 지원
│
├── /analysis                        # 이미지 분석 (기능 1) ✅
│   - AnalysisDashboard 래퍼
│   - 이미지 업로드/분석
│   - 분석 이력
│
├── /control                         # 시스템 제어 (기능 3) ✅
│   - 탭 기반 UI (자연어/ACU/CCTV)
│   - 자연어 명령 입력
│   - ACU 출입문 제어
│   - CCTV PTZ 제어
│
├── /documents                       # 문서 관리 ✅
│   - 문서 업로드
│   - 문서 목록/검색
│   - 문서 삭제
│
├── /reports                         # 보고서 관리 ✅
│   - 보고서 목록
│   - 필터링 (일일/주간/월간/사고)
│   - 보고서 생성/다운로드
│
└── /settings                        # 설정 ✅
    - RAG 하이브리드 검색 설정
    - 고급 검색 옵션 (리랭킹, 다중쿼리)
```

### 2.2 페이지별 상세

| 경로 | 페이지명 | 설명 | 상태 |
|------|---------|------|------|
| `/` | Dashboard | 메인 대시보드, 전체 현황 요약 | ✅ |
| `/chat` | RAG Chat | AI 문서 검색 채팅 | ✅ |
| `/chat/new` | New Chat | 새 대화 시작 | 🚧 |
| `/chat/:id` | Chat Detail | 특정 대화 내용 | 🚧 |
| `/analysis` | Image Analysis | 이미지 분석 메인 | ⚠️ |
| `/analysis/upload` | Upload Image | 이미지 업로드 | ⚠️ |
| `/analysis/:id` | Analysis Result | 분석 결과 상세 | 🚧 |
| `/analysis/history` | Analysis History | 분석 이력 목록 | 🚧 |
| `/control` | ControlPage | 시스템 제어 대시보드 (탭 기반) | ✅ |
| `/documents` | DocumentsPage | 문서 관리 메인 | ✅ |
| `/reports` | ReportsPage | 보고서 관리 | ✅ |
| `/settings` | SettingsPage | RAG 시스템 설정 | ✅ |

---

## 3. 네비게이션 흐름도

### 3.1 메인 사이드바 네비게이션

```
┌──────────────────────────────────────┐
│         Total-LLM                    │
│  ┌─────────────────────────────────┐ │
│  │  🏠 대시보드          /         │ │  ✅
│  ├─────────────────────────────────┤ │
│  │  💬 RAG 채팅         /chat      │ │  ✅
│  ├─────────────────────────────────┤ │
│  │  📷 이미지 분석      /analysis  │ │  ✅
│  ├─────────────────────────────────┤ │
│  │  🎮 시스템 제어      /control   │ │  ✅
│  ├─────────────────────────────────┤ │
│  │  📊 보고서           /reports   │ │  ✅
│  ├─────────────────────────────────┤ │
│  │  📄 문서 관리        /documents │ │  ✅
│  ├─────────────────────────────────┤ │
│  │  ⚙️ 설정            /settings  │ │  ✅
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### 3.2 기능별 서브 네비게이션

현재 모든 페이지는 단일 페이지로 구현되어 있으며, 탭 기반 UI를 사용합니다.

#### 시스템 제어 (/control) - 탭 기반 UI
```
┌─────────────────────────────────────┐
│  🎮 시스템 제어                     │
│  ┌────────────────────────────────┐ │
│  │ [자연어 명령] [ACU 제어] [CCTV] │ │  ← 탭 네비게이션
│  └────────────────────────────────┘ │
│                                     │
│  • 자연어 명령: CommandBar 컴포넌트  │
│  • ACU 제어: DoorGrid + DoorCard    │
│  • CCTV 제어: CameraGrid + PTZ      │
└─────────────────────────────────────┘
```

### 3.3 브레드크럼 구조

```
홈 > 시스템 제어 > ACU 제어 > 1번 출입문
/     /control      /acu       /:doorId

홈 > 이미지 분석 > 분석 결과 > abc123
/     /analysis     /          /:analysisId

홈 > 보고서 > 2026-01-13 보안 보고서
/     /reports    /:reportId
```

---

## 4. React Router 경로 정의

### 4.1 라우터 설정 코드 (예상)

```typescript
// src/router/index.tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

// Layouts
import MainLayout from '../layouts/MainLayout';

// Pages
import Dashboard from '../pages/Dashboard';
import ChatPage from '../pages/Chat/ChatPage';
import ChatDetail from '../pages/Chat/ChatDetail';
import AnalysisPage from '../pages/Analysis/AnalysisPage';
import AnalysisUpload from '../pages/Analysis/AnalysisUpload';
import AnalysisDetail from '../pages/Analysis/AnalysisDetail';
import AnalysisHistory from '../pages/Analysis/AnalysisHistory';
import ControlDashboard from '../pages/Control/ControlDashboard';
import CommandPage from '../pages/Control/CommandPage';
import ACUControlPage from '../pages/Control/ACU/ACUControlPage';
import DoorDetail from '../pages/Control/ACU/DoorDetail';
import AccessLogs from '../pages/Control/ACU/AccessLogs';
import CCTVControlPage from '../pages/Control/CCTV/CCTVControlPage';
import CameraDetail from '../pages/Control/CCTV/CameraDetail';
import PresetManager from '../pages/Control/CCTV/PresetManager';
import DocumentsPage from '../pages/Documents/DocumentsPage';
import DocumentUpload from '../pages/Documents/DocumentUpload';
import DocumentList from '../pages/Documents/DocumentList';
import ReportsPage from '../pages/Reports/ReportsPage';
import ReportDetail from '../pages/Reports/ReportDetail';
import SettingsPage from '../pages/Settings/SettingsPage';
import NotFound from '../pages/NotFound';

const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      // Dashboard
      {
        index: true,
        element: <Dashboard />,
      },

      // Chat (RAG QA)
      {
        path: 'chat',
        children: [
          { index: true, element: <ChatPage /> },
          { path: 'new', element: <ChatPage isNew /> },
          { path: ':conversationId', element: <ChatDetail /> },
        ],
      },

      // Image Analysis
      {
        path: 'analysis',
        children: [
          { index: true, element: <AnalysisPage /> },
          { path: 'upload', element: <AnalysisUpload /> },
          { path: 'history', element: <AnalysisHistory /> },
          { path: ':analysisId', element: <AnalysisDetail /> },
        ],
      },

      // System Control (신규)
      {
        path: 'control',
        children: [
          { index: true, element: <ControlDashboard /> },
          { path: 'command', element: <CommandPage /> },
          {
            path: 'acu',
            children: [
              { index: true, element: <ACUControlPage /> },
              { path: 'logs', element: <AccessLogs /> },
              { path: ':doorId', element: <DoorDetail /> },
            ],
          },
          {
            path: 'cctv',
            children: [
              { index: true, element: <CCTVControlPage /> },
              { path: 'presets', element: <PresetManager /> },
              { path: ':cameraId', element: <CameraDetail /> },
            ],
          },
        ],
      },

      // Documents
      {
        path: 'documents',
        children: [
          { index: true, element: <DocumentsPage /> },
          { path: 'upload', element: <DocumentUpload /> },
          { path: 'list', element: <DocumentList /> },
        ],
      },

      // Reports (신규)
      {
        path: 'reports',
        children: [
          { index: true, element: <ReportsPage /> },
          { path: 'list', element: <ReportsPage /> },
          { path: ':reportId', element: <ReportDetail /> },
        ],
      },

      // Settings (신규)
      {
        path: 'settings',
        element: <SettingsPage />,
      },

      // 404
      {
        path: '*',
        element: <NotFound />,
      },
    ],
  },
]);

export default router;
```

### 4.2 동적 라우트 파라미터

| 파라미터 | 사용 경로 | 타입 | 예시 |
|---------|----------|------|------|
| `:conversationId` | /chat/:conversationId | string (UUID) | `c1a2b3c4-d5e6-7890-abcd-ef1234567890` |
| `:analysisId` | /analysis/:analysisId | string (UUID) | `a1b2c3d4-e5f6-7890-1234-567890abcdef` |
| `:doorId` | /control/acu/:doorId | string | `door-001`, `main-entrance` |
| `:cameraId` | /control/cctv/:cameraId | string | `cam-001`, `lobby-cam` |
| `:reportId` | /reports/:reportId | string (UUID) | `r1a2b3c4-d5e6-7890-abcd-ef1234567890` |

### 4.3 쿼리 파라미터

| 경로 | 쿼리 파라미터 | 설명 |
|------|--------------|------|
| `/analysis/history` | `?page=1&limit=10` | 페이지네이션 |
| `/analysis/history` | `?severity=critical` | 심각도 필터 |
| `/analysis/history` | `?type=fire` | 사고 유형 필터 |
| `/control/acu/logs` | `?doorId=door-001` | 출입문 필터 |
| `/control/acu/logs` | `?from=2026-01-01&to=2026-01-13` | 날짜 필터 |
| `/reports/list` | `?status=generated` | 상태 필터 |

---

## 5. 레이아웃 구조

### 5.1 MainLayout

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Header (64px)                              │
│  ┌──────┐                                           ┌────┐ ┌────┐  │
│  │ Logo │  Total-LLM                               │알림│ │프로필│ │
│  └──────┘                                           └────┘ └────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  │                                                                 │
│  │  ┌─────────────────────────────────────────────────────────┐   │
│S │  │                                                          │   │
│i │  │                      Main Content                        │   │
│d │  │                                                          │   │
│e │  │                      <Outlet />                          │   │
│b │  │                                                          │   │
│a │  │                                                          │   │
│r │  │                                                          │   │
│  │  │                                                          │   │
│240│ │                                                          │   │
│px │  │                                                          │   │
│  │  │                                                          │   │
│  │  └─────────────────────────────────────────────────────────┘   │
│  │                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 반응형 브레이크포인트

| 브레이크포인트 | 너비 | 레이아웃 변경 |
|---------------|------|--------------|
| Mobile | < 640px | 사이드바 숨김, 햄버거 메뉴 |
| Tablet | 640px - 1024px | 사이드바 축소 (아이콘만) |
| Desktop | > 1024px | 전체 사이드바 표시 |

---

## 6. 페이지 디렉토리 구조 (목표)

```
src/
├── pages/
│   ├── Dashboard/
│   │   └── index.tsx                 ✅ (현재 App.tsx에 통합)
│   │
│   ├── Chat/
│   │   ├── ChatPage.tsx              ✅ (현재 App.tsx에 통합)
│   │   └── ChatDetail.tsx            🚧
│   │
│   ├── Analysis/
│   │   ├── AnalysisPage.tsx          ⚠️
│   │   ├── AnalysisUpload.tsx        ⚠️
│   │   ├── AnalysisDetail.tsx        🚧
│   │   └── AnalysisHistory.tsx       🚧
│   │
│   ├── Control/                      🚧 전체 신규
│   │   ├── ControlDashboard.tsx
│   │   ├── CommandPage.tsx
│   │   ├── ACU/
│   │   │   ├── ACUControlPage.tsx
│   │   │   ├── DoorDetail.tsx
│   │   │   └── AccessLogs.tsx
│   │   └── CCTV/
│   │       ├── CCTVControlPage.tsx
│   │       ├── CameraDetail.tsx
│   │       └── PresetManager.tsx
│   │
│   ├── Documents/
│   │   ├── DocumentsPage.tsx         ⚠️
│   │   ├── DocumentUpload.tsx        ⚠️
│   │   └── DocumentList.tsx          ⚠️
│   │
│   ├── Reports/                      🚧 전체 신규
│   │   ├── ReportsPage.tsx
│   │   └── ReportDetail.tsx
│   │
│   ├── Settings/                     🚧 전체 신규
│   │   └── SettingsPage.tsx
│   │
│   └── NotFound.tsx                  🚧
│
├── layouts/
│   └── MainLayout.tsx                🚧 (현재 App.tsx에 통합)
│
└── router/
    └── index.tsx                     🚧 (React Router 미사용)
```

---

## 7. 현재 vs 목표 비교

### 7.1 현재 상태 (탭 기반)

```
┌─────────────────────────────────────┐
│  [채팅] [이미지 분석] [보안 대시보드] │  ← 탭 네비게이션
├─────────────────────────────────────┤
│                                     │
│         선택된 탭 콘텐츠             │
│                                     │
└─────────────────────────────────────┘
```

- URL 라우팅 없음
- 직접 링크 불가
- 브라우저 뒤로가기 미지원
- 북마크 불가

### 7.2 목표 상태 (URL 라우팅)

```
┌─────────────────────────────────────┐
│  사이드바 네비게이션                 │
│  - 대시보드 (/)                      │
│  - RAG 채팅 (/chat)                  │
│  - 이미지 분석 (/analysis)           │
│  - 시스템 제어 (/control)            │
│  - 문서 관리 (/documents)            │
│  - 보고서 (/reports)                 │
│  - 설정 (/settings)                  │
├─────────────────────────────────────┤
│                                     │
│         라우트 콘텐츠                │
│         <Outlet />                  │
│                                     │
└─────────────────────────────────────┘
```

- URL 기반 라우팅
- 직접 링크 가능
- 브라우저 히스토리 지원
- 북마크 가능

---

## 8. 마이그레이션 계획

### Phase 1: React Router 설치 및 기본 설정
1. `npm install react-router-dom`
2. `router/index.tsx` 생성
3. `MainLayout.tsx` 생성

### Phase 2: 기존 페이지 분리
1. App.tsx에서 각 탭 콘텐츠를 별도 페이지로 분리
2. 기존 기능 유지하면서 라우트 연결

### Phase 3: 신규 페이지 추가
1. Control 관련 페이지 생성 (가장 시급)
2. Reports 관련 페이지 생성
3. Settings 페이지 생성

### Phase 4: 네비게이션 개선
1. 사이드바 라우트 연동
2. 브레드크럼 컴포넌트 추가
3. 반응형 네비게이션

---

## 범례

| 기호 | 의미 |
|-----|------|
| ✅ | 구현됨 |
| ⚠️ | 부분 구현 |
| 🚧 | 미구현 (신규 필요) |
