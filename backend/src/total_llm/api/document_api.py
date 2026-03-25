"""
문서 관리 API

RAG 문서 업로드, 조회, 삭제 등의 엔드포인트를 제공합니다.
"""

from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import tempfile
import os
from pathlib import Path
import logging
import json
import asyncio

from total_llm.config.model_config import get_llm_model_name
from total_llm.core.dependencies import LLMClientDep, RAGToolDep

logger = logging.getLogger(__name__)

# Router 생성
router = APIRouter(tags=["Documents"])

class QueryRequest(BaseModel):
    """RAG 쿼리 요청"""
    query: str
    k: Optional[int] = 5


# =============================================================================
# Document Upload
# =============================================================================

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), rag_tool: RAGToolDep = None):
    """
    문서 업로드

    Args:
        file: 업로드할 파일

    Returns:
        업로드 결과
    """
    try:
        filename = file.filename or "upload.bin"
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # RAG 도구로 업로드
        rag_tool.upload_file(tmp_path)

        # 임시 파일 삭제
        os.unlink(tmp_path)

        logger.info(f"✅ Document uploaded: {filename} ({len(content)} bytes)")

        return {
            "status": "ok",
            "filename": filename,
            "size": len(content)
        }

    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# =============================================================================
# Document List
# =============================================================================

@router.get("/documents")
async def get_documents(rag_tool: RAGToolDep = None):
    """
    문서 목록 조회

    Returns:
        저장된 문서 목록
    """
    try:
        documents = rag_tool.get_documents()
        return documents
    except Exception as e:
        logger.error(f"❌ Failed to get documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}")


# =============================================================================
# Document Content
# =============================================================================

@router.get("/documents/{doc_id:path}/content")
async def get_document_content(doc_id: str, rag_tool: RAGToolDep = None):
    """
    문서 내용 조회

    Args:
        doc_id: 문서 ID (파일 경로)

    Returns:
        문서 내용
    """
    try:
        content = rag_tool.get_document_content(doc_id)

        if content is None:
            raise HTTPException(status_code=404, detail="Document not found")

        # 파일 이름 추출
        filename = Path(doc_id).name

        return {
            "content": content,
            "filename": filename
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get document content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document content: {str(e)}")


# =============================================================================
# Document Rename
# =============================================================================

@router.patch("/documents/{doc_id:path}")
async def rename_document(doc_id: str, request: dict, rag_tool: RAGToolDep = None):
    """
    문서 이름 변경

    Args:
        doc_id: 문서 ID (파일 경로)
        request: {"new_name": "새로운파일명.txt"}

    Returns:
        변경 결과
    """
    try:
        new_name = request.get('new_name')
        if not new_name:
            raise HTTPException(status_code=400, detail="new_name is required")

        chunks_updated = rag_tool.rename_document(doc_id, new_name)
        return {
            "status": "ok",
            "message": "Document renamed successfully",
            "chunks_updated": chunks_updated
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to rename document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rename document: {str(e)}")


# =============================================================================
# Document Delete
# =============================================================================

@router.delete("/documents/{doc_id:path}")
async def delete_document(doc_id: str, rag_tool: RAGToolDep = None):
    """
    문서 삭제

    Args:
        doc_id: 문서 ID (파일 경로)

    Returns:
        삭제 결과
    """
    try:
        rag_tool.delete_document(doc_id)
        logger.info(f"✅ Document deleted: {doc_id}")
        return {
            "status": "ok",
            "message": f"Document {doc_id} deleted successfully"
        }
    except Exception as e:
        logger.error(f"❌ Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


# =============================================================================
# Delete All Documents
# =============================================================================

@router.delete("/documents")
async def delete_all_documents(rag_tool: RAGToolDep = None):
    """
    모든 문서 삭제

    Returns:
        삭제 결과 (삭제된 문서 수)
    """
    try:
        deleted_count = rag_tool.clear_all_documents()
        logger.info(f"✅ All documents deleted: {deleted_count} chunks")
        return {
            "status": "ok",
            "message": "All documents deleted successfully",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"❌ Failed to delete all documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete all documents: {str(e)}")


# =============================================================================
# RAG Query (Streaming)
# =============================================================================

@router.post("/query/stream")
async def query_rag_stream(
    request: QueryRequest,
    rag_tool: RAGToolDep = None,
    llm_client: LLMClientDep = None,
):
    """
    RAG 쿼리 처리 (Streaming)

    문서를 검색하고 LLM을 통해 답변을 스트리밍합니다.

    Args:
        request: QueryRequest (query, k)

    Returns:
        Server-Sent Events stream
    """
    async def generate():
        try:
            query = request.query
            k = request.k or 5

            # 1. RAG 검색
            logger.info(f"🔍 RAG query: {query[:50]}...")
            search_results = rag_tool.search(query, k=k)

            # 2. 컨텍스트 구성
            context_parts = []
            for i, doc in enumerate(search_results, 1):
                text = doc.get('text', doc.get('content', ''))
                context_parts.append(f"[{i}] {text}")

            context = "\n\n".join(context_parts) if context_parts else "관련 문서를 찾을 수 없습니다."

            # 3. LLM 프롬프트
            prompt = f"""다음 문서들을 참고하여 질문에 답변해주세요.

문서:
{context}

질문: {query}

답변:"""

            # 4. LLM 스트리밍 (AsyncOpenAI)
            response = await llm_client.chat.completions.create(
                model=get_llm_model_name(),
                messages=[
                    {"role": "system", "content": "당신은 문서를 기반으로 정확하게 답변하는 AI 어시스턴트입니다. 문서에 관련 정보가 없으면 그렇게 말해주세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2048,
                stream=True
            )

            # 5. 스트리밍 응답
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'token': token, 'content': token})}\n\n"
                    await asyncio.sleep(0)

            # 완료 신호
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"❌ RAG query failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
