# Total-LLM Development Guide

이 문서는 Total-LLM 프로젝트의 개발 환경 설정 및 개발 가이드입니다.

---

## 목차

1. [개발 환경 설정](#개발-환경-설정)
2. [프로젝트 구조](#프로젝트-구조)
3. [백엔드 개발](#백엔드-개발)
4. [프론트엔드 개발](#프론트엔드-개발)
5. [테스트](#테스트)
6. [코드 스타일](#코드-스타일)
7. [API 개발 가이드](#api-개발-가이드)
8. [디버깅](#디버깅)

---

## 개발 환경 설정

### 사전 요구사항

| 도구 | 버전 | 설치 확인 |
|------|------|----------|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Git | 2.40+ | `git --version` |

### 1. 저장소 클론

```bash
git clone https://github.com/your-org/Total-LLM.git
cd Total-LLM
```

### 2. Python 가상환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 활성화 (Linux/macOS)
source venv/bin/activate

# 활성화 (Windows)
.\venv\Scripts\activate
```

### 3. 백엔드 의존성 설치

```bash
cd backend
pip install -r requirements.txt

# 개발 도구 추가 설치
pip install pytest pytest-asyncio pytest-cov black isort mypy
```

### 4. 프론트엔드 의존성 설치

```bash
cd frontend/react-ui
npm install
```

### 5. 환경 변수 설정

```bash
# 프로젝트 루트에서
cp .env.example .env

# 개발용 기본값 설정
nano .env
```

**개발용 `.env` 예시**:

```bash
ENVIRONMENT=development
DEBUG=true

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=total_llm
POSTGRES_USER=total_llm
POSTGRES_PASSWORD=dev_password

QDRANT_HOST=localhost
QDRANT_PORT=6333

REDIS_HOST=localhost
REDIS_PORT=6379

VLLM_BASE_URL=http://localhost:9000/v1
VLM_BASE_URL=http://localhost:9001/v1
VLM_SIMULATION_MODE=true  # 개발 시 시뮬레이션 모드
```

### 6. 인프라 서비스 시작

```bash
# Qdrant, Redis, PostgreSQL 시작
docker compose --profile with-postgres up -d
```

### 7. 데이터베이스 초기화

```bash
cd backend
python scripts/init_db.py  # DB 스키마 생성 (있는 경우)
```

---

## 프로젝트 구조

```
Total-LLM/
├── backend/                    # FastAPI 백엔드
│   ├── api/                    # API 라우터
│   │   ├── security_chat_api.py
│   │   ├── control_api.py
│   │   ├── image_api.py
│   │   ├── document_api.py
│   │   └── ...
│   ├── services/               # 비즈니스 로직
│   │   ├── control/            # 장치 제어 서브시스템
│   │   │   ├── adapters/       # 프로토콜 어댑터
│   │   │   ├── device_registry.py
│   │   │   └── system_controller.py
│   │   ├── vision/             # VLM 분석
│   │   │   └── vision_analyzer.py
│   │   └── api_generator/      # API 코드 생성기
│   ├── retrievers/             # RAG 검색기
│   │   └── adaptive_retriever.py
│   ├── tools/                  # LangChain 도구
│   ├── core/                   # 핵심 유틸리티
│   ├── config/                 # 설정 파일
│   │   └── config.yaml
│   ├── database/               # DB 스키마
│   ├── tests/                  # 테스트
│   ├── main.py                 # 앱 진입점
│   └── requirements.txt
│
├── frontend/
│   └── react-ui/               # React 프론트엔드
│       ├── src/
│       │   ├── pages/          # 페이지 컴포넌트
│       │   ├── components/     # UI 컴포넌트
│       │   ├── services/       # API 클라이언트
│       │   ├── stores/         # Zustand 스토어
│       │   └── types/          # TypeScript 타입
│       ├── package.json
│       └── vite.config.ts
│
├── services/
│   └── vllm/                   # vLLM 실행 스크립트
│       └── run_vllm.sh
│
├── data/                       # 데이터 저장소
│   ├── uploads/
│   ├── logs/
│   └── reports/
│
├── docs/                       # 문서
├── docker-compose.yml
└── .env.example
```

---

## 백엔드 개발

### 개발 서버 실행

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 9002 --reload
```

`--reload` 옵션으로 코드 변경 시 자동 재시작됩니다.

### 핵심 기술 스택

| 기술 | 용도 |
|------|------|
| FastAPI | 웹 프레임워크 |
| Pydantic | 데이터 검증 |
| LangChain | LLM 오케스트레이션 |
| Qdrant | 벡터 검색 |
| asyncpg | 비동기 PostgreSQL |
| aiohttp | 비동기 HTTP |

### 새 API 엔드포인트 추가

1. **라우터 파일 생성** (`backend/api/new_api.py`):

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/new", tags=["New Feature"])

class NewRequest(BaseModel):
    field1: str
    field2: int = 10

class NewResponse(BaseModel):
    success: bool
    result: str

@router.post("/action", response_model=NewResponse)
async def perform_action(request: NewRequest):
    """새로운 액션 수행"""
    try:
        result = f"Processed: {request.field1}"
        return NewResponse(success=True, result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "healthy"}
```

2. **main.py에 라우터 등록**:

```python
from api.new_api import router as new_router

app.include_router(new_router)
```

### 서비스 레이어 패턴

```python
# services/new_service.py
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class NewService:
    """새 기능 서비스"""

    def __init__(self, db_pool, config: dict):
        self.db_pool = db_pool
        self.config = config
        logger.info("NewService initialized")

    async def process(self, data: str) -> dict:
        """데이터 처리"""
        try:
            # 비즈니스 로직
            result = await self._internal_process(data)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Process failed: {e}")
            raise

    async def _internal_process(self, data: str) -> str:
        """내부 처리 로직"""
        async with self.db_pool.acquire() as conn:
            # DB 작업
            pass
        return data.upper()
```

### 의존성 주입

```python
# main.py에서 서비스 초기화
from services.new_service import NewService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    app.state.new_service = NewService(db_pool, config)
    yield
    # 종료 시
    await app.state.new_service.cleanup()

# API에서 사용
@router.post("/action")
async def action(request: Request):
    service = request.app.state.new_service
    return await service.process(request.data)
```

---

## 프론트엔드 개발

### 개발 서버 실행

```bash
cd frontend/react-ui
npm run dev -- --port 9004
```

### 핵심 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| React | 19 | UI 프레임워크 |
| TypeScript | 5.9 | 타입 시스템 |
| Vite | 7 | 빌드 도구 |
| Tailwind CSS | 4 | 스타일링 |
| Zustand | 5 | 상태 관리 |
| TanStack Query | 5 | 서버 상태 관리 |
| React Router | 7 | 라우팅 |

### 새 페이지 추가

1. **페이지 컴포넌트 생성** (`src/pages/NewPage.tsx`):

```tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchData } from '../services/api';

export default function NewPage() {
  const [filter, setFilter] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['newData', filter],
    queryFn: () => fetchData(filter),
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">New Page</h1>
      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="border rounded px-3 py-2 mb-4"
        placeholder="Filter..."
      />
      <div className="grid gap-4">
        {data?.map((item: any) => (
          <div key={item.id} className="bg-white p-4 rounded shadow">
            {item.name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

2. **라우트 추가** (`src/App.tsx`):

```tsx
import { Routes, Route } from 'react-router-dom';
import NewPage from './pages/NewPage';

function App() {
  return (
    <Routes>
      <Route path="/new" element={<NewPage />} />
      {/* 기존 라우트들 */}
    </Routes>
  );
}
```

### API 서비스 함수 추가

```typescript
// src/services/api.ts
const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:9002';

export async function fetchData(filter?: string): Promise<Data[]> {
  const params = filter ? `?filter=${encodeURIComponent(filter)}` : '';
  const response = await fetch(`${API_BASE}/new/data${params}`);

  if (!response.ok) {
    throw new Error(`HTTP error: ${response.status}`);
  }

  return response.json();
}

export async function createItem(data: CreateItemRequest): Promise<Item> {
  const response = await fetch(`${API_BASE}/new/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create item');
  }

  return response.json();
}
```

### Zustand 스토어 생성

```typescript
// src/stores/newStore.ts
import { create } from 'zustand';

interface NewState {
  items: Item[];
  selectedId: string | null;
  setItems: (items: Item[]) => void;
  selectItem: (id: string | null) => void;
  addItem: (item: Item) => void;
  removeItem: (id: string) => void;
}

export const useNewStore = create<NewState>((set) => ({
  items: [],
  selectedId: null,
  setItems: (items) => set({ items }),
  selectItem: (id) => set({ selectedId: id }),
  addItem: (item) => set((state) => ({ items: [...state.items, item] })),
  removeItem: (id) => set((state) => ({
    items: state.items.filter((i) => i.id !== id),
  })),
}));
```

### 컴포넌트 구조

```
src/components/
├── common/              # 공통 컴포넌트
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Modal.tsx
│   └── index.ts
├── Chat/                # 채팅 관련
│   ├── ChatMessage.tsx
│   ├── ChatInput.tsx
│   └── index.ts
├── Control/             # 장치 제어
│   ├── DeviceCard.tsx
│   ├── PTZControl.tsx
│   └── index.ts
└── ImageAnalysis/       # 이미지 분석
    ├── ImageUploadCard.tsx
    ├── AnalysisResultCard.tsx
    └── index.ts
```

---

## 테스트

### 백엔드 테스트

```bash
cd backend

# 전체 테스트 실행
pytest

# 특정 파일 테스트
pytest tests/test_api_generator.py -v

# 커버리지 포함
pytest --cov=. --cov-report=html

# 비동기 테스트
pytest tests/test_async.py -v --asyncio-mode=auto
```

**테스트 파일 예시**:

```python
# tests/test_new_api.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/new/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_action_success():
    response = client.post("/new/action", json={
        "field1": "test",
        "field2": 20
    })
    assert response.status_code == 200
    assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_async_operation():
    # 비동기 테스트
    from services.new_service import NewService
    service = NewService(mock_pool, {})
    result = await service.process("data")
    assert result["success"] is True
```

### 프론트엔드 테스트

```bash
cd frontend/react-ui

# 테스트 실행
npm test

# 한 번만 실행
npm run test:run

# 커버리지 포함
npm run test:coverage
```

**테스트 파일 예시**:

```tsx
// src/components/__tests__/Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Button from '../common/Button';

describe('Button', () => {
  it('renders correctly', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    fireEvent.click(screen.getByText('Click'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when loading', () => {
    render(<Button loading>Submit</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

---

## 코드 스타일

### Python (Black + isort)

```bash
# 포맷팅
black backend/
isort backend/

# 타입 체크
mypy backend/
```

**설정 파일** (`pyproject.toml`):

```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
```

### TypeScript/React (ESLint)

```bash
cd frontend/react-ui

# 린트 실행
npm run lint

# 자동 수정
npm run lint -- --fix
```

**ESLint 설정** (`eslint.config.js`):

```javascript
import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  }
);
```

### 커밋 메시지 규칙

```
<type>(<scope>): <subject>

<body>

<footer>
```

**타입**:
- `feat`: 새 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `style`: 코드 포맷팅
- `refactor`: 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드/설정 변경

**예시**:
```
feat(control): add PTZ preset management

- Add save/delete preset endpoints
- Implement preset list UI component
- Add preset validation logic

Closes #123
```

---

## API 개발 가이드

### REST API 설계 원칙

1. **리소스 중심 URL**
   - ✅ `GET /devices/{id}`
   - ❌ `GET /getDevice?id=123`

2. **적절한 HTTP 메서드 사용**
   - `GET`: 조회
   - `POST`: 생성
   - `PUT`: 전체 업데이트
   - `PATCH`: 부분 업데이트
   - `DELETE`: 삭제

3. **일관된 응답 형식**

```python
# 성공
{
    "success": True,
    "data": {...},
    "message": "Operation completed"
}

# 실패
{
    "detail": "Error message",
    "error_code": "VALIDATION_ERROR"
}
```

4. **페이지네이션**

```python
@router.get("/items")
async def list_items(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    items = await service.list(limit=limit, offset=offset)
    total = await service.count()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }
```

### SSE (Server-Sent Events) 구현

```python
from fastapi import Response
from fastapi.responses import StreamingResponse
import asyncio

@router.post("/chat")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for token in llm.generate_stream(request.message):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 에러 처리

```python
from fastapi import HTTPException

class DeviceNotFoundError(Exception):
    pass

@router.get("/devices/{device_id}")
async def get_device(device_id: str):
    try:
        device = await service.get_device(device_id)
        if not device:
            raise HTTPException(
                status_code=404,
                detail=f"Device {device_id} not found"
            )
        return device
    except DeviceNotFoundError:
        raise HTTPException(status_code=404, detail="Device not found")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 디버깅

### 백엔드 디버깅

**VS Code launch.json**:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Debug",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--host", "0.0.0.0", "--port", "9002", "--reload"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

**로깅 설정**:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 사용
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

### 프론트엔드 디버깅

**React DevTools 사용**:
- Chrome 확장 프로그램: React Developer Tools
- 컴포넌트 트리, props, state 검사

**네트워크 요청 디버깅**:
```typescript
// API 요청 로깅
const response = await fetch(url);
console.log('Request:', url);
console.log('Status:', response.status);
console.log('Response:', await response.clone().json());
```

**Zustand DevTools**:
```typescript
import { devtools } from 'zustand/middleware';

const useStore = create(
  devtools((set) => ({
    // ...state and actions
  }), { name: 'MyStore' })
);
```

### Docker 디버깅

```bash
# 컨테이너 로그
docker logs -f total-llm-backend

# 컨테이너 쉘 접속
docker exec -it total-llm-backend /bin/bash

# 네트워크 검사
docker network inspect total-llm-network

# 리소스 사용량
docker stats
```

---

## 유용한 명령어

### 데이터베이스

```bash
# PostgreSQL 접속
docker exec -it total-llm-postgres psql -U total_llm

# 테이블 목록
\dt

# 쿼리 실행
SELECT * FROM devices LIMIT 10;
```

### Qdrant

```bash
# 컬렉션 정보
curl http://localhost:6333/collections/documents

# 포인트 개수
curl http://localhost:6333/collections/documents/points/count
```

### Redis

```bash
# Redis CLI 접속
docker exec -it total-llm-redis redis-cli

# 키 목록
KEYS *

# 값 조회
GET key_name
```

---

*Last Updated: 2026-01-16*
