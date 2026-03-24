# Total-LLM 통합 개발 가이드

## 1. 개요

### 1.1 프로젝트 소개
Total-LLM은 Qwen 모델 기반의 통합 AI 플랫폼으로, 3가지 독립적인 핵심 기능을 제공합니다.

| 기능 | 모델 | 설명 |
|------|------|------|
| **이미지 분석** | Qwen2-VL-7B-Instruct | CCTV/보안 이미지 분석 및 보고서 생성 |
| **문서 RAG QA** | Qwen2.5-14B-AWQ (vLLM) | LangGraph 기반 Agent 질의응답 |
| **외부 시스템 제어** | Qwen2.5-0.5B-Instruct | Function Calling 기반 ACU/CCTV 제어 |

### 1.2 시스템 아키텍처

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
│                    ┌──────────────────┼──────────────────┐                  │
│                    ▼                  ▼                  ▼                  │
│            ┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │
│            │  ACU 시스템  │    │ CCTV 시스템  │    │  기타 IoT   │           │
│            │ (출입통제)   │    │ (카메라제어) │    │   시스템    │           │
│            └─────────────┘    └─────────────┘    └─────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 개발 환경 설정

### 2.1 시스템 요구사항

| 항목 | 최소 사양 | 권장 사양 |
|------|----------|----------|
| GPU | RTX 4090 (24GB) | RTX 4090 × 2 또는 A100 (40GB) |
| RAM | 32GB | 64GB |
| Storage | 50GB SSD | 100GB NVMe SSD |
| CPU | 8코어 | 16코어 이상 |
| CUDA | 11.8+ | 12.1+ |
| Python | 3.10+ | 3.11+ |
| Node.js | 18+ | 20 LTS |

### 2.2 GPU 메모리 할당

| 모델 | 용도 | VRAM | GPU 할당 |
|------|------|------|----------|
| Qwen2.5-0.5B-Instruct | Function Calling | ~1GB | GPU 0 (공유) |
| Qwen2-VL-7B-Instruct | 이미지 분석 | ~14GB | GPU 1 |
| Qwen2.5-14B-AWQ | RAG Agent | ~10GB | GPU 0 |
| **총계** | | **~25GB** | |

### 2.3 프로젝트 구조

```
Total-LLM/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── image_api.py          # 이미지 분석 API
│   │   ├── agent_api.py          # RAG Agent API
│   │   ├── control_api.py        # 외부 시스템 제어 API
│   │   ├── acu_api.py            # ACU 전용 API
│   │   └── cctv_api.py           # CCTV 전용 API
│   ├── services/
│   │   ├── vision/
│   │   │   ├── vlm_analyzer.py   # VLM 분석기
│   │   │   ├── incident_detector.py
│   │   │   └── report_generator.py
│   │   ├── rag/
│   │   │   ├── embedder.py       # 임베딩 서비스
│   │   │   ├── searcher.py       # 벡터 검색
│   │   │   └── reranker.py       # 리랭킹
│   │   ├── agent/
│   │   │   ├── graph.py          # LangGraph 정의
│   │   │   ├── nodes/            # Agent 노드들
│   │   │   └── tools/            # Agent 도구들
│   │   └── control/
│   │       ├── system_controller.py  # Function Calling 엔진
│   │       ├── acu_controller.py     # ACU 제어기
│   │       ├── cctv_controller.py    # CCTV 제어기
│   │       └── adapters/             # 외부 시스템 어댑터
│   ├── models/
│   │   └── schemas.py            # Pydantic 모델
│   ├── config/
│   │   └── config.yaml           # 설정 파일
│   └── main.py                   # FastAPI 앱
├── frontend/
│   └── react-ui/
│       ├── src/
│       │   ├── components/
│       │   │   ├── chat/         # 채팅 컴포넌트
│       │   │   ├── vision/       # 이미지 분석 컴포넌트
│       │   │   └── control/      # 시스템 제어 컴포넌트
│       │   ├── pages/
│       │   ├── store/            # Zustand 상태관리
│       │   └── api/              # API 클라이언트
│       └── package.json
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── INTEGRATED_WBS.md
│   └── INTEGRATION_DEVELOPMENT_GUIDE.md
├── requirements.txt
└── README.md
```

### 2.4 환경 설정

**Python 환경 설정**:
```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

**requirements.txt**:
```
# Core
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.5.0

# LLM & Vision
torch>=2.1.0
transformers>=4.37.0
accelerate>=0.26.0
qwen-vl-utils>=0.0.8

# vLLM
vllm>=0.3.0

# RAG
langchain>=0.1.0
langgraph>=0.0.20
qdrant-client>=1.7.0
sentence-transformers>=2.3.0

# Utils
python-multipart>=0.0.6
aiofiles>=23.2.0
httpx>=0.26.0
pyyaml>=6.0.1
redis>=5.0.0

# Function Calling
ollama>=0.1.6

# Testing
pytest>=7.4.0
pytest-asyncio>=0.23.0
httpx>=0.26.0
```

---

## 3. 기능 1: 이미지 분석 (Vision Analysis)

### 3.1 VLM Analyzer 서비스

**vlm_analyzer.py**:
```python
"""
Qwen2-VL-7B 기반 이미지 분석 서비스
"""
import torch
from pathlib import Path
from typing import Union, Optional
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

class VLMAnalyzer:
    """Vision-Language Model 분석기"""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
        device: str = "cuda:1",
        torch_dtype: torch.dtype = torch.bfloat16,
    ):
        self.model_name = model_name
        self.device = device
        self.torch_dtype = torch_dtype
        self.model = None
        self.processor = None

    def load_model(self):
        """모델 로드"""
        if self.model is not None:
            return

        self.processor = AutoProcessor.from_pretrained(
            self.model_name,
            trust_remote_code=True
        )
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            self.model_name,
            torch_dtype=self.torch_dtype,
            device_map=self.device,
            trust_remote_code=True
        )

    def analyze_image(
        self,
        image: Union[str, Path, Image.Image],
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        """이미지 분석 수행"""
        self.load_model()

        # 이미지 로드
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        # 메시지 구성
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        # 처리
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[text],
            images=[image],
            return_tensors="pt"
        ).to(self.device)

        # 생성
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )

        # 디코딩
        generated_ids = outputs[:, inputs.input_ids.shape[1]:]
        response = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )[0]

        return response

    def analyze_security_scene(
        self,
        image: Union[str, Path, Image.Image],
        location: str,
        timestamp: str,
    ) -> str:
        """보안 CCTV 장면 분석"""
        prompt = f"""당신은 전문 보안 분석가입니다. 다음 CCTV 이미지를 분석해주세요.

위치: {location}
시간: {timestamp}

다음 항목을 분석해주세요:
1. 장면 설명: 이미지에서 보이는 전체적인 상황
2. 인물 분석: 등장 인물의 수, 행동, 특징
3. 이상 징후: 비정상적이거나 의심스러운 행동
4. 위험 요소: 잠재적인 보안 위협
5. 권장 조치: 보안팀이 취해야 할 조치

한글로 상세히 분석해주세요."""

        return self.analyze_image(image, prompt)
```

### 3.2 Incident Detector

**incident_detector.py**:
```python
"""
사고 유형 및 심각도 감지
"""
from enum import Enum
from typing import Tuple
from dataclasses import dataclass

class IncidentType(Enum):
    NORMAL = "정상"
    VIOLENCE = "폭력"
    INTRUSION = "침입"
    FALL = "넘어짐/낙상"
    THEFT = "절도"
    VANDALISM = "기물파손"
    FIRE = "화재"
    SUSPICIOUS = "의심행동"
    CROWD = "군중밀집"
    ABNORMAL = "비정상행동"

class SeverityLevel(Enum):
    INFO = "정보"
    LOW = "낮음"
    MEDIUM = "중간"
    HIGH = "높음"
    CRITICAL = "매우높음"

@dataclass
class IncidentResult:
    incident_type: IncidentType
    severity: SeverityLevel
    confidence: float
    description: str

class IncidentDetector:
    """사고 감지기"""

    # 키워드 패턴 (한글/영문)
    PATTERNS = {
        IncidentType.VIOLENCE: [
            "fight", "assault", "violence", "attack", "punch", "kick",
            "폭력", "싸움", "폭행", "공격", "때리"
        ],
        IncidentType.FALL: [
            "fall", "collapse", "slip", "trip",
            "넘어", "쓰러", "낙상", "미끄러"
        ],
        IncidentType.INTRUSION: [
            "intrusion", "trespass", "unauthorized", "break",
            "침입", "무단", "불법진입"
        ],
        IncidentType.FIRE: [
            "fire", "smoke", "flame", "burning",
            "화재", "연기", "불", "화염"
        ],
        IncidentType.THEFT: [
            "theft", "steal", "robbery",
            "절도", "도둑", "훔치"
        ],
    }

    SEVERITY_MAPPING = {
        IncidentType.NORMAL: SeverityLevel.INFO,
        IncidentType.VIOLENCE: SeverityLevel.CRITICAL,
        IncidentType.FIRE: SeverityLevel.CRITICAL,
        IncidentType.INTRUSION: SeverityLevel.HIGH,
        IncidentType.FALL: SeverityLevel.HIGH,
        IncidentType.THEFT: SeverityLevel.HIGH,
        IncidentType.SUSPICIOUS: SeverityLevel.MEDIUM,
        IncidentType.ABNORMAL: SeverityLevel.MEDIUM,
    }

    def detect(self, analysis_text: str) -> IncidentResult:
        """분석 텍스트에서 사고 유형 감지"""
        text_lower = analysis_text.lower()

        for incident_type, keywords in self.PATTERNS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    severity = self.SEVERITY_MAPPING.get(
                        incident_type, SeverityLevel.MEDIUM
                    )
                    return IncidentResult(
                        incident_type=incident_type,
                        severity=severity,
                        confidence=0.85,
                        description=f"'{keyword}' 키워드 감지"
                    )

        return IncidentResult(
            incident_type=IncidentType.NORMAL,
            severity=SeverityLevel.INFO,
            confidence=0.95,
            description="이상 징후 없음"
        )
```

### 3.3 이미지 분석 API

**image_api.py**:
```python
"""
이미지 분석 API 엔드포인트
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image

from ..services.vision.vlm_analyzer import VLMAnalyzer
from ..services.vision.incident_detector import IncidentDetector

router = APIRouter(prefix="/image", tags=["Image Analysis"])

# 서비스 인스턴스
vlm_analyzer = VLMAnalyzer()
incident_detector = IncidentDetector()

class AnalysisRequest(BaseModel):
    image_base64: Optional[str] = None
    location: str = "미지정"
    timestamp: Optional[str] = None

class AnalysisResponse(BaseModel):
    report_id: str
    location: str
    timestamp: str
    incident_type: str
    severity: str
    confidence: float
    analysis: str
    report: str

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    location: str = Form("미지정"),
    timestamp: Optional[str] = Form(None),
):
    """CCTV 이미지 분석"""

    # 타임스탬프 설정
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 이미지 로드
    if file:
        image_bytes = await file.read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    elif image_base64:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    else:
        raise HTTPException(status_code=400, detail="이미지가 필요합니다")

    # 분석 수행
    analysis = vlm_analyzer.analyze_security_scene(
        image=image,
        location=location,
        timestamp=timestamp,
    )

    # 사고 감지
    incident = incident_detector.detect(analysis)

    # 보고서 ID 생성
    report_id = f"RPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # 보고서 생성
    report = f"""# 보안 분석 보고서

## 기본 정보
- **보고서 ID**: {report_id}
- **위치**: {location}
- **분석 시간**: {timestamp}

## 사고 정보
- **유형**: {incident.incident_type.value}
- **심각도**: {incident.severity.value}
- **신뢰도**: {incident.confidence * 100:.1f}%

## 상세 분석
{analysis}

## 권장 조치
{_get_recommendations(incident.incident_type, incident.severity)}
"""

    return AnalysisResponse(
        report_id=report_id,
        location=location,
        timestamp=timestamp,
        incident_type=incident.incident_type.value,
        severity=incident.severity.value,
        confidence=incident.confidence,
        analysis=analysis,
        report=report,
    )

def _get_recommendations(incident_type, severity) -> str:
    """권장 조치 생성"""
    if incident_type.value == "정상":
        return "- 정기 모니터링 유지"

    recommendations = ["- 현장 CCTV 집중 모니터링"]

    if severity.value in ["높음", "매우높음"]:
        recommendations.append("- 보안 요원 현장 파견")
        recommendations.append("- 관계 기관 신고 검토")

    return "\n".join(recommendations)
```

---

## 4. 기능 2: 문서 RAG Agent QA

> **중요 (2026-01-13 업데이트)**: Qdrant 컬렉션 분리
>
> RAG QA와 보안 로그 검색이 서로 다른 컬렉션을 사용하도록 분리되었습니다:
>
> | 용도 | 컬렉션명 | 설명 |
> |------|---------|------|
> | **문서 RAG** | `documents` | 업로드된 문서 (정책, 매뉴얼 등) |
> | **보안 로그** | `security_logs` | Fluentd로 수집된 보안 장비 로그 |
>
> `config.yaml` 설정:
> ```yaml
> qdrant:
>   collection_name: "documents"        # RAG 문서용
>   logs_collection_name: "security_logs"  # 보안 로그용 (분리됨)
> ```
>
> 이 분리로 인해 RAG 채팅에서 업로드된 문서만 검색되고, 보안 로그가 RAG 응답에 혼입되지 않습니다.

### 4.1 RAG 검색 엔진

**searcher.py**:
```python
"""
Qdrant 기반 벡터 검색
"""
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

class RAGSearcher:
    """RAG 검색 엔진"""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "documents",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
    ):
        self.client = QdrantClient(url=qdrant_url)
        self.collection_name = collection_name
        self.embedder = SentenceTransformer(embedding_model)
        self.vector_size = 384  # bge-small 차원

    def create_collection(self):
        """컬렉션 생성"""
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE,
            )
        )

    def index_documents(self, documents: List[Dict[str, Any]]):
        """문서 인덱싱"""
        points = []
        for i, doc in enumerate(documents):
            embedding = self.embedder.encode(doc["content"]).tolist()
            points.append(
                PointStruct(
                    id=i,
                    vector=embedding,
                    payload={
                        "content": doc["content"],
                        "metadata": doc.get("metadata", {}),
                    }
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """유사도 검색"""
        query_vector = self.embedder.encode(query).tolist()

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
        )

        return [
            {
                "content": hit.payload["content"],
                "metadata": hit.payload.get("metadata", {}),
                "score": hit.score,
            }
            for hit in results
        ]
```

### 4.2 LangGraph Agent

**graph.py**:
```python
"""
LangGraph 기반 Multi-Agent 시스템
"""
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
import operator

class AgentState(TypedDict):
    """Agent 상태"""
    messages: Annotated[List, operator.add]
    query: str
    context: List[str]
    plan: str
    analysis: str
    response: str

def create_agent_graph(
    llm_client,
    rag_searcher,
):
    """Agent 그래프 생성"""

    def planner_node(state: AgentState) -> AgentState:
        """계획 수립 노드"""
        query = state["query"]

        plan_prompt = f"""사용자 질문: {query}

이 질문에 답하기 위한 계획을 수립하세요:
1. 필요한 정보
2. 검색 전략
3. 응답 구조"""

        plan = llm_client.generate(plan_prompt)
        return {"plan": plan}

    def researcher_node(state: AgentState) -> AgentState:
        """RAG 검색 노드"""
        query = state["query"]

        # 벡터 검색
        results = rag_searcher.search(query, top_k=5)
        context = [r["content"] for r in results]

        return {"context": context}

    def analyzer_node(state: AgentState) -> AgentState:
        """분석 노드"""
        query = state["query"]
        context = state.get("context", [])

        analysis_prompt = f"""질문: {query}

참고 문서:
{chr(10).join(context)}

위 문서들을 분석하여 질문과 관련된 핵심 정보를 추출하세요."""

        analysis = llm_client.generate(analysis_prompt)
        return {"analysis": analysis}

    def responder_node(state: AgentState) -> AgentState:
        """응답 생성 노드"""
        query = state["query"]
        context = state.get("context", [])
        analysis = state.get("analysis", "")

        response_prompt = f"""질문: {query}

분석 결과:
{analysis}

참고 문서:
{chr(10).join(context[:3])}

위 정보를 바탕으로 사용자 질문에 정확하고 친절하게 답변하세요.
한글로 답변해주세요."""

        response = llm_client.generate(response_prompt)
        return {"response": response}

    # 그래프 구성
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("responder", responder_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "analyzer")
    workflow.add_edge("analyzer", "responder")
    workflow.add_edge("responder", END)

    return workflow.compile()
```

### 4.3 Agent API

**agent_api.py**:
```python
"""
RAG Agent API 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, AsyncGenerator
import json

router = APIRouter(prefix="/agent", tags=["RAG Agent"])

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    stream: bool = False

class QueryResponse(BaseModel):
    response: str
    sources: List[str]
    session_id: str

@router.post("/query")
async def query_agent(request: QueryRequest):
    """RAG Agent 질의"""
    from ..services.agent.graph import create_agent_graph
    from ..services.rag.searcher import RAGSearcher
    from ..services.llm_client import LLMClient

    # 서비스 초기화
    llm_client = LLMClient()
    rag_searcher = RAGSearcher()
    agent = create_agent_graph(llm_client, rag_searcher)

    # 실행
    result = agent.invoke({
        "query": request.query,
        "messages": [],
        "context": [],
        "plan": "",
        "analysis": "",
        "response": "",
    })

    return QueryResponse(
        response=result["response"],
        sources=[],
        session_id=request.session_id or "new-session",
    )

@router.post("/query/stream")
async def query_agent_stream(request: QueryRequest):
    """SSE 스트리밍 응답"""

    async def generate() -> AsyncGenerator[str, None]:
        # Agent 실행 및 스트리밍
        response = "이것은 스트리밍 응답 예시입니다."

        for char in response:
            yield f"data: {json.dumps({'content': char})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
```

---

## 5. 기능 3: 외부 시스템 제어 (Function Calling)

> **중요 (2026-01-13 업데이트)**: Control API 경로 변경
>
> 백엔드 Control API가 `/control` prefix를 사용합니다:
>
> | 기능 | 엔드포인트 | 설명 |
> |------|-----------|------|
> | 자연어 명령 | `POST /control/command` | Function Calling 연동 |
> | 출입문 상태 | `GET /control/acu/door/status` | 전체/특정 출입문 상태 |
> | 출입문 해제 | `POST /control/acu/door/unlock` | 잠금 해제 |
> | 출입문 잠금 | `POST /control/acu/door/lock` | 잠금 |
> | 출입 이력 | `GET /control/acu/log` | 출입 이력 조회 |
> | 카메라 상태 | `GET /control/cctv/camera/status` | 전체/특정 카메라 상태 |
> | PTZ 이동 | `POST /control/cctv/camera/move` | Pan/Tilt/Zoom 제어 |
> | 프리셋 이동 | `POST /control/cctv/camera/preset` | 프리셋 위치로 이동 |
> | 녹화 시작 | `POST /control/cctv/recording/start` | 녹화 시작 |
> | 녹화 중지 | `POST /control/cctv/recording/stop` | 녹화 중지 |
>
> 프론트엔드 `controlApi.ts`와 백엔드 `control_api.py`가 이 경로로 통일되었습니다.

### 5.1 Function Calling 스키마

**function_schemas.py**:
```python
"""
Function Calling JSON Schema 정의
"""

# ACU (출입통제) 함수들
ACU_FUNCTIONS = [
    {
        "name": "unlock_door",
        "description": "지정된 출입문을 열기 (잠금 해제)",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID (예: 'door_01', 'main_entrance')"
                },
                "duration": {
                    "type": "integer",
                    "description": "개방 유지 시간(초), 기본값 5초",
                    "default": 5
                }
            },
            "required": ["door_id"]
        }
    },
    {
        "name": "lock_door",
        "description": "지정된 출입문을 잠금",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID"
                }
            },
            "required": ["door_id"]
        }
    },
    {
        "name": "get_door_status",
        "description": "출입문 상태 조회 (열림/닫힘/잠금)",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID, 생략 시 전체 조회"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_access_log",
        "description": "출입 이력 조회",
        "parameters": {
            "type": "object",
            "properties": {
                "door_id": {
                    "type": "string",
                    "description": "출입문 ID, 생략 시 전체"
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 최대 기록 수",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "name": "emergency_unlock_all",
        "description": "비상 시 모든 출입문 개방 (긴급 상황용)",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "비상 개방 사유"
                }
            },
            "required": ["reason"]
        }
    },
]

# CCTV (영상감시) 함수들
CCTV_FUNCTIONS = [
    {
        "name": "move_camera",
        "description": "CCTV 카메라 PTZ(Pan/Tilt/Zoom) 제어",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID (예: 'cam_01', 'lobby_cam')"
                },
                "pan": {
                    "type": "number",
                    "description": "수평 이동각도 (-180 ~ 180도)"
                },
                "tilt": {
                    "type": "number",
                    "description": "수직 이동각도 (-90 ~ 90도)"
                },
                "zoom": {
                    "type": "number",
                    "description": "줌 레벨 (1x ~ 20x)"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "go_to_preset",
        "description": "카메라를 미리 설정된 프리셋 위치로 이동",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                },
                "preset_id": {
                    "type": "string",
                    "description": "프리셋 ID (예: 'entrance', 'parking')"
                }
            },
            "required": ["camera_id", "preset_id"]
        }
    },
    {
        "name": "start_recording",
        "description": "카메라 녹화 시작",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                },
                "duration": {
                    "type": "integer",
                    "description": "녹화 시간(분), 0이면 수동 중지까지"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "stop_recording",
        "description": "카메라 녹화 중지",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "capture_snapshot",
        "description": "현재 화면 스냅샷 캡처",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "get_camera_status",
        "description": "카메라 상태 조회 (온라인/오프라인, 녹화 상태 등)",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "카메라 ID, 생략 시 전체 조회"
                }
            },
            "required": []
        }
    },
]

# 전체 함수 목록
ALL_FUNCTIONS = ACU_FUNCTIONS + CCTV_FUNCTIONS
```

### 5.2 System Controller

**system_controller.py**:
```python
"""
Function Calling 기반 시스템 제어기
"""
import json
from typing import Dict, Any, Optional
import ollama
from .function_schemas import ALL_FUNCTIONS, ACU_FUNCTIONS, CCTV_FUNCTIONS
from .acu_controller import ACUController
from .cctv_controller import CCTVController

class SystemController:
    """외부 시스템 제어 엔진"""

    def __init__(
        self,
        model_name: str = "qwen2.5:0.5b-instruct",
        ollama_host: str = "http://localhost:11434",
    ):
        self.model_name = model_name
        self.ollama_host = ollama_host
        self.acu = ACUController()
        self.cctv = CCTVController()

        # 함수 매핑
        self.function_handlers = {
            # ACU 함수들
            "unlock_door": self.acu.unlock_door,
            "lock_door": self.acu.lock_door,
            "get_door_status": self.acu.get_door_status,
            "get_access_log": self.acu.get_access_log,
            "emergency_unlock_all": self.acu.emergency_unlock_all,
            # CCTV 함수들
            "move_camera": self.cctv.move_camera,
            "go_to_preset": self.cctv.go_to_preset,
            "start_recording": self.cctv.start_recording,
            "stop_recording": self.cctv.stop_recording,
            "capture_snapshot": self.cctv.capture_snapshot,
            "get_camera_status": self.cctv.get_camera_status,
        }

    def process_command(self, user_input: str) -> Dict[str, Any]:
        """
        사용자 자연어 명령 처리

        Args:
            user_input: 자연어 명령 (예: "1번 출입문 열어줘")

        Returns:
            실행 결과
        """
        # Function Calling 프롬프트
        system_prompt = """당신은 보안 시스템 제어 AI입니다.
사용자의 명령을 분석하여 적절한 함수를 호출하세요.

지원하는 시스템:
1. ACU (출입통제): 출입문 개폐, 잠금, 이력 조회
2. CCTV (영상감시): PTZ 제어, 녹화, 스냅샷

사용자 명령을 분석하여 JSON 형식으로 함수 호출을 반환하세요.
"""

        # Ollama에 Function Calling 요청
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            tools=ALL_FUNCTIONS,
        )

        # 함수 호출 처리
        if response.message.tool_calls:
            results = []
            for tool_call in response.message.tool_calls:
                func_name = tool_call.function.name
                func_args = tool_call.function.arguments

                if func_name in self.function_handlers:
                    handler = self.function_handlers[func_name]
                    result = handler(**func_args)
                    results.append({
                        "function": func_name,
                        "arguments": func_args,
                        "result": result,
                    })

            return {
                "success": True,
                "command": user_input,
                "executions": results,
                "message": self._format_response(results),
            }
        else:
            # 일반 응답 (함수 호출 없음)
            return {
                "success": True,
                "command": user_input,
                "executions": [],
                "message": response.message.content,
            }

    def _format_response(self, results: list) -> str:
        """실행 결과를 사용자 친화적 메시지로 변환"""
        messages = []
        for r in results:
            func = r["function"]
            result = r["result"]

            if func == "unlock_door":
                messages.append(f"✅ {result['door_id']} 출입문이 열렸습니다.")
            elif func == "lock_door":
                messages.append(f"🔒 {result['door_id']} 출입문이 잠겼습니다.")
            elif func == "start_recording":
                messages.append(f"🔴 {result['camera_id']} 카메라 녹화를 시작했습니다.")
            elif func == "move_camera":
                messages.append(f"🎥 {result['camera_id']} 카메라가 이동했습니다.")
            else:
                messages.append(f"✅ {func} 실행 완료")

        return "\n".join(messages)
```

### 5.3 ACU Controller

**acu_controller.py**:
```python
"""
ACU (출입통제장치) 제어기
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class DoorStatus:
    door_id: str
    name: str
    is_locked: bool
    is_open: bool
    last_access: Optional[datetime]

class ACUController:
    """ACU 출입통제 제어기"""

    def __init__(self, api_endpoint: Optional[str] = None):
        """
        Args:
            api_endpoint: 실제 ACU 시스템 API 엔드포인트
                         None이면 시뮬레이션 모드
        """
        self.api_endpoint = api_endpoint
        self._simulation_mode = api_endpoint is None

        # 시뮬레이션용 상태
        self._doors = {
            "door_01": DoorStatus("door_01", "정문", True, False, None),
            "door_02": DoorStatus("door_02", "후문", True, False, None),
            "door_03": DoorStatus("door_03", "주차장입구", True, False, None),
        }
        self._access_logs = []

    def unlock_door(
        self,
        door_id: str,
        duration: int = 5,
    ) -> Dict[str, Any]:
        """출입문 열기"""
        logger.info(f"ACU: Unlocking door {door_id} for {duration}s")

        if self._simulation_mode:
            if door_id in self._doors:
                self._doors[door_id].is_locked = False
                self._doors[door_id].is_open = True
                self._doors[door_id].last_access = datetime.now()
                self._access_logs.append({
                    "door_id": door_id,
                    "action": "unlock",
                    "timestamp": datetime.now().isoformat(),
                })
                return {
                    "success": True,
                    "door_id": door_id,
                    "action": "unlocked",
                    "duration": duration,
                }
            else:
                return {"success": False, "error": f"Door {door_id} not found"}
        else:
            # 실제 ACU API 호출
            return self._call_api("unlock", door_id=door_id, duration=duration)

    def lock_door(self, door_id: str) -> Dict[str, Any]:
        """출입문 잠금"""
        logger.info(f"ACU: Locking door {door_id}")

        if self._simulation_mode:
            if door_id in self._doors:
                self._doors[door_id].is_locked = True
                self._doors[door_id].is_open = False
                return {
                    "success": True,
                    "door_id": door_id,
                    "action": "locked",
                }
            else:
                return {"success": False, "error": f"Door {door_id} not found"}
        else:
            return self._call_api("lock", door_id=door_id)

    def get_door_status(
        self,
        door_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """출입문 상태 조회"""
        if self._simulation_mode:
            if door_id:
                if door_id in self._doors:
                    door = self._doors[door_id]
                    return {
                        "door_id": door.door_id,
                        "name": door.name,
                        "is_locked": door.is_locked,
                        "is_open": door.is_open,
                    }
                else:
                    return {"error": f"Door {door_id} not found"}
            else:
                return {
                    "doors": [
                        {
                            "door_id": d.door_id,
                            "name": d.name,
                            "is_locked": d.is_locked,
                            "is_open": d.is_open,
                        }
                        for d in self._doors.values()
                    ]
                }
        else:
            return self._call_api("status", door_id=door_id)

    def get_access_log(
        self,
        door_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """출입 이력 조회"""
        if self._simulation_mode:
            logs = self._access_logs
            if door_id:
                logs = [l for l in logs if l["door_id"] == door_id]
            return {"logs": logs[-limit:]}
        else:
            return self._call_api("logs", door_id=door_id, limit=limit)

    def emergency_unlock_all(self, reason: str) -> Dict[str, Any]:
        """비상 전체 개방"""
        logger.warning(f"ACU: EMERGENCY UNLOCK ALL - Reason: {reason}")

        if self._simulation_mode:
            for door in self._doors.values():
                door.is_locked = False
                door.is_open = True
            return {
                "success": True,
                "action": "emergency_unlock_all",
                "doors_unlocked": list(self._doors.keys()),
                "reason": reason,
            }
        else:
            return self._call_api("emergency_unlock", reason=reason)

    def _call_api(self, action: str, **kwargs) -> Dict[str, Any]:
        """실제 ACU API 호출 (구현 필요)"""
        # TODO: 실제 ACU 시스템 API 연동
        raise NotImplementedError("Real ACU API not implemented")
```

### 5.4 CCTV Controller

**cctv_controller.py**:
```python
"""
CCTV (영상감시) 제어기
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class CameraStatus:
    camera_id: str
    name: str
    is_online: bool
    is_recording: bool
    pan: float
    tilt: float
    zoom: float

class CCTVController:
    """CCTV 영상감시 제어기"""

    def __init__(self, api_endpoint: Optional[str] = None):
        """
        Args:
            api_endpoint: ONVIF 또는 CCTV API 엔드포인트
                         None이면 시뮬레이션 모드
        """
        self.api_endpoint = api_endpoint
        self._simulation_mode = api_endpoint is None

        # 시뮬레이션용 상태
        self._cameras = {
            "cam_01": CameraStatus("cam_01", "로비 카메라", True, False, 0, 0, 1.0),
            "cam_02": CameraStatus("cam_02", "주차장 카메라", True, False, 45, -15, 2.0),
            "cam_03": CameraStatus("cam_03", "후문 카메라", True, True, 0, 0, 1.0),
        }

        # 프리셋 정의
        self._presets = {
            "entrance": {"pan": 0, "tilt": 0, "zoom": 1.0},
            "parking": {"pan": 45, "tilt": -15, "zoom": 2.0},
            "wide": {"pan": 0, "tilt": 0, "zoom": 1.0},
        }

    def move_camera(
        self,
        camera_id: str,
        pan: Optional[float] = None,
        tilt: Optional[float] = None,
        zoom: Optional[float] = None,
    ) -> Dict[str, Any]:
        """카메라 PTZ 제어"""
        logger.info(f"CCTV: Moving camera {camera_id} - pan={pan}, tilt={tilt}, zoom={zoom}")

        if self._simulation_mode:
            if camera_id in self._cameras:
                cam = self._cameras[camera_id]
                if pan is not None:
                    cam.pan = max(-180, min(180, pan))
                if tilt is not None:
                    cam.tilt = max(-90, min(90, tilt))
                if zoom is not None:
                    cam.zoom = max(1.0, min(20.0, zoom))

                return {
                    "success": True,
                    "camera_id": camera_id,
                    "position": {
                        "pan": cam.pan,
                        "tilt": cam.tilt,
                        "zoom": cam.zoom,
                    }
                }
            else:
                return {"success": False, "error": f"Camera {camera_id} not found"}
        else:
            return self._call_api("move", camera_id=camera_id, pan=pan, tilt=tilt, zoom=zoom)

    def go_to_preset(
        self,
        camera_id: str,
        preset_id: str,
    ) -> Dict[str, Any]:
        """프리셋 위치로 이동"""
        logger.info(f"CCTV: Moving camera {camera_id} to preset {preset_id}")

        if preset_id not in self._presets:
            return {"success": False, "error": f"Preset {preset_id} not found"}

        preset = self._presets[preset_id]
        return self.move_camera(
            camera_id,
            pan=preset["pan"],
            tilt=preset["tilt"],
            zoom=preset["zoom"],
        )

    def start_recording(
        self,
        camera_id: str,
        duration: Optional[int] = None,
    ) -> Dict[str, Any]:
        """녹화 시작"""
        logger.info(f"CCTV: Starting recording on {camera_id}")

        if self._simulation_mode:
            if camera_id in self._cameras:
                self._cameras[camera_id].is_recording = True
                return {
                    "success": True,
                    "camera_id": camera_id,
                    "action": "recording_started",
                    "duration": duration,
                }
            else:
                return {"success": False, "error": f"Camera {camera_id} not found"}
        else:
            return self._call_api("record_start", camera_id=camera_id, duration=duration)

    def stop_recording(self, camera_id: str) -> Dict[str, Any]:
        """녹화 중지"""
        logger.info(f"CCTV: Stopping recording on {camera_id}")

        if self._simulation_mode:
            if camera_id in self._cameras:
                self._cameras[camera_id].is_recording = False
                return {
                    "success": True,
                    "camera_id": camera_id,
                    "action": "recording_stopped",
                }
            else:
                return {"success": False, "error": f"Camera {camera_id} not found"}
        else:
            return self._call_api("record_stop", camera_id=camera_id)

    def capture_snapshot(self, camera_id: str) -> Dict[str, Any]:
        """스냅샷 캡처"""
        logger.info(f"CCTV: Capturing snapshot from {camera_id}")

        if self._simulation_mode:
            if camera_id in self._cameras:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"snapshot_{camera_id}_{timestamp}.jpg"
                return {
                    "success": True,
                    "camera_id": camera_id,
                    "filename": filename,
                    "timestamp": timestamp,
                }
            else:
                return {"success": False, "error": f"Camera {camera_id} not found"}
        else:
            return self._call_api("snapshot", camera_id=camera_id)

    def get_camera_status(
        self,
        camera_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """카메라 상태 조회"""
        if self._simulation_mode:
            if camera_id:
                if camera_id in self._cameras:
                    cam = self._cameras[camera_id]
                    return {
                        "camera_id": cam.camera_id,
                        "name": cam.name,
                        "is_online": cam.is_online,
                        "is_recording": cam.is_recording,
                        "position": {
                            "pan": cam.pan,
                            "tilt": cam.tilt,
                            "zoom": cam.zoom,
                        }
                    }
                else:
                    return {"error": f"Camera {camera_id} not found"}
            else:
                return {
                    "cameras": [
                        {
                            "camera_id": c.camera_id,
                            "name": c.name,
                            "is_online": c.is_online,
                            "is_recording": c.is_recording,
                        }
                        for c in self._cameras.values()
                    ]
                }
        else:
            return self._call_api("status", camera_id=camera_id)

    def _call_api(self, action: str, **kwargs) -> Dict[str, Any]:
        """실제 CCTV API 호출 (ONVIF 등)"""
        # TODO: 실제 CCTV 시스템 API 연동
        raise NotImplementedError("Real CCTV API not implemented")
```

### 5.5 제어 API

**control_api.py**:
```python
"""
외부 시스템 제어 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from ..services.control.system_controller import SystemController

router = APIRouter(prefix="/control", tags=["System Control"])

# 서비스 인스턴스
system_controller = SystemController()

class CommandRequest(BaseModel):
    command: str  # 자연어 명령

class CommandResponse(BaseModel):
    success: bool
    command: str
    message: str
    executions: list

# === 자연어 명령 처리 ===
@router.post("/command", response_model=CommandResponse)
async def process_command(request: CommandRequest):
    """
    자연어 명령을 분석하여 시스템 제어 실행

    예시:
    - "1번 출입문 열어줘"
    - "로비 카메라 녹화 시작"
    - "전체 출입문 상태 확인"
    """
    result = system_controller.process_command(request.command)
    return CommandResponse(**result)

# === ACU 직접 제어 API ===
class ACUUnlockRequest(BaseModel):
    door_id: str
    duration: int = 5

@router.post("/acu/unlock")
async def unlock_door(request: ACUUnlockRequest):
    """출입문 열기"""
    return system_controller.acu.unlock_door(request.door_id, request.duration)

@router.post("/acu/lock")
async def lock_door(door_id: str):
    """출입문 잠금"""
    return system_controller.acu.lock_door(door_id)

@router.get("/acu/status")
async def get_door_status(door_id: Optional[str] = None):
    """출입문 상태 조회"""
    return system_controller.acu.get_door_status(door_id)

@router.get("/acu/logs")
async def get_access_logs(door_id: Optional[str] = None, limit: int = 10):
    """출입 이력 조회"""
    return system_controller.acu.get_access_log(door_id, limit)

# === CCTV 직접 제어 API ===
class CCTVMoveRequest(BaseModel):
    camera_id: str
    pan: Optional[float] = None
    tilt: Optional[float] = None
    zoom: Optional[float] = None

@router.post("/cctv/move")
async def move_camera(request: CCTVMoveRequest):
    """카메라 PTZ 제어"""
    return system_controller.cctv.move_camera(
        request.camera_id, request.pan, request.tilt, request.zoom
    )

@router.post("/cctv/preset")
async def goto_preset(camera_id: str, preset_id: str):
    """프리셋 이동"""
    return system_controller.cctv.go_to_preset(camera_id, preset_id)

@router.post("/cctv/record/start")
async def start_recording(camera_id: str, duration: Optional[int] = None):
    """녹화 시작"""
    return system_controller.cctv.start_recording(camera_id, duration)

@router.post("/cctv/record/stop")
async def stop_recording(camera_id: str):
    """녹화 중지"""
    return system_controller.cctv.stop_recording(camera_id)

@router.get("/cctv/status")
async def get_camera_status(camera_id: Optional[str] = None):
    """카메라 상태 조회"""
    return system_controller.cctv.get_camera_status(camera_id)

# === 전체 시스템 상태 ===
@router.get("/status")
async def get_system_status():
    """전체 시스템 상태 조회"""
    return {
        "acu": system_controller.acu.get_door_status(),
        "cctv": system_controller.cctv.get_camera_status(),
    }
```

---

## 6. Docker 통합 배포

### 6.1 Docker Compose

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  # Qdrant 벡터 데이터베이스
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  # Redis 캐시
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

  # Ollama (Function Calling 모델)
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  # vLLM 서버 (RAG Agent LLM)
  vllm:
    image: vllm/vllm-openai:latest
    ports:
      - "9000:8000"
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    command: >
      --model Qwen/Qwen2.5-14B-Instruct-AWQ
      --quantization awq
      --max-model-len 8192
      --tensor-parallel-size 1
      --gpu-memory-utilization 0.8
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
    restart: unless-stopped

  # FastAPI Backend
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    ports:
      - "9002:9002"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - REDIS_URL=redis://redis:6379
      - OLLAMA_URL=http://ollama:11434
      - VLLM_URL=http://vllm:8000
    volumes:
      - ./backend:/app
      - model_cache:/root/.cache
    depends_on:
      - qdrant
      - redis
      - ollama
      - vllm
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1']
              capabilities: [gpu]
    restart: unless-stopped

  # React Frontend
  frontend:
    build:
      context: .
      dockerfile: docker/Dockerfile.frontend
    ports:
      - "9004:80"
    depends_on:
      - backend
    restart: unless-stopped

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

volumes:
  qdrant_data:
  ollama_data:
  model_cache:
```

### 6.2 Backend Dockerfile

**Dockerfile.backend**:
```dockerfile
FROM nvidia/cuda:12.1-runtime-ubuntu22.04

WORKDIR /app

# Python 설치
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 의존성 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY backend/ .

# 환경 변수
ENV PYTHONUNBUFFERED=1

# 포트 노출
EXPOSE 9002

# 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9002"]
```

### 6.3 배포 명령어

```bash
# 환경 변수 설정
cp .env.example .env
# .env 파일에 HF_TOKEN 등 설정

# Ollama 모델 다운로드 (별도 실행)
docker-compose up -d ollama
docker exec -it total-llm-ollama-1 ollama pull qwen2.5:0.5b-instruct

# 전체 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f backend

# 서비스 중지
docker-compose down
```

---

## 7. 테스트

### 7.1 단위 테스트

**test_acu.py**:
```python
"""ACU 제어기 테스트"""
import pytest
from backend.services.control.acu_controller import ACUController

@pytest.fixture
def acu():
    return ACUController()

def test_unlock_door(acu):
    result = acu.unlock_door("door_01", duration=5)
    assert result["success"] is True
    assert result["door_id"] == "door_01"

def test_lock_door(acu):
    result = acu.lock_door("door_01")
    assert result["success"] is True

def test_get_status(acu):
    result = acu.get_door_status("door_01")
    assert "is_locked" in result

def test_invalid_door(acu):
    result = acu.unlock_door("invalid_door")
    assert result["success"] is False
```

### 7.2 통합 테스트

**test_control_api.py**:
```python
"""제어 API 통합 테스트"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_natural_language_command():
    response = client.post(
        "/control/command",
        json={"command": "1번 출입문 열어줘"}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_acu_unlock_api():
    response = client.post(
        "/control/acu/unlock",
        json={"door_id": "door_01", "duration": 5}
    )
    assert response.status_code == 200

def test_cctv_status_api():
    response = client.get("/control/cctv/status")
    assert response.status_code == 200
    assert "cameras" in response.json()
```

---

## 8. API 명세 (OpenAPI)

### 8.1 엔드포인트 요약

| 메서드 | 경로 | 설명 |
|--------|------|------|
| **이미지 분석** | | |
| POST | `/image/analyze` | 이미지 분석 및 보고서 생성 |
| POST | `/image/batch` | 배치 이미지 분석 |
| GET | `/image/{id}` | 분석 결과 조회 |
| **RAG Agent** | | |
| POST | `/agent/query` | RAG Agent 질의 |
| POST | `/agent/query/stream` | SSE 스트리밍 응답 |
| GET | `/agent/documents` | 문서 목록 |
| POST | `/agent/documents` | 문서 업로드 |
| **외부 시스템 제어** | | |
| POST | `/control/command` | 자연어 명령 처리 |
| POST | `/control/acu/unlock` | 출입문 열기 |
| POST | `/control/acu/lock` | 출입문 잠금 |
| GET | `/control/acu/status` | 출입문 상태 |
| GET | `/control/acu/logs` | 출입 이력 |
| POST | `/control/cctv/move` | PTZ 제어 |
| POST | `/control/cctv/preset` | 프리셋 이동 |
| POST | `/control/cctv/record/start` | 녹화 시작 |
| POST | `/control/cctv/record/stop` | 녹화 중지 |
| GET | `/control/cctv/status` | 카메라 상태 |
| GET | `/control/status` | 전체 상태 |

---

## 9. 성능 기준

| 항목 | 목표값 |
|------|-------|
| 이미지 분석 응답 시간 | < 5초 |
| RAG Agent 첫 토큰 | < 500ms |
| Function Calling 라우팅 | < 100ms |
| 시스템 제어 명령 실행 | < 200ms |
| 동시 접속 사용자 | ≥ 50명 |
| 테스트 커버리지 | ≥ 80% |

---

**문서 버전**: 2.0
**최종 수정일**: 2025-01-12
**작성자**: Total-LLM 개발팀
