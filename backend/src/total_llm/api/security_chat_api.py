#!/usr/bin/env python3
"""
Security Chat API

Qwen Function Calling 기반 보안 모니터링 채팅 API
- Phase 2: 대화 지속성 지원 (PostgreSQL + Redis 캐싱)
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import logging
import asyncio

from total_llm.functions.security_functions import SECURITY_FUNCTIONS, get_system_prompt
from total_llm.config.model_config import get_llm_model_name
from total_llm.services.conversation_service import ConversationService
from total_llm.services.cache_service import CacheService
from total_llm.core.dependencies import (
    CacheServiceDep,
    CommandOrchestratorDep,
    ConversationServiceDep,
    LLMClientDep,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security", tags=["security"])


# ============================================
# Request/Response Models
# ============================================

class Message(BaseModel):
    """채팅 메시지"""
    role: str = Field(..., description="메시지 역할 (user, assistant)")
    content: str = Field(..., description="메시지 내용")


class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str = Field(..., description="사용자 메시지")
    mode: str = Field(default="qa", description="채팅 모드 (qa, device_register, device_control)")
    conversation_id: Optional[str] = Field(default=None, description="대화 ID (없으면 새 대화 생성)")
    conversation_history: List[Message] = Field(default_factory=list, description="대화 히스토리 (conversation_id가 없을 때 사용)")
    user_id: str = Field(default="anonymous", description="사용자 ID")
    context_window: int = Field(default=5, description="컨텍스트 윈도우 크기 (턴 수)")


class ChatResponse(BaseModel):
    """채팅 응답"""
    response: str
    conversation_id: Optional[str] = None
    function_calls: Optional[List[Dict[str, Any]]] = None
    mode: str


async def _get_or_create_conversation(
    conversation_id: Optional[str],
    user_id: str,
    mode: str,
    conversation_service: Optional[ConversationService],
) -> str:
    """대화 ID 조회 또는 생성"""
    if conversation_id:
        # 기존 대화 확인
        if conversation_service:
            conv = await conversation_service.get_conversation(conversation_id)
            if conv:
                return conversation_id
        # 유효하지 않은 ID면 새로 생성
        logger.warning(f"Conversation {conversation_id} not found, creating new")

    # 새 대화 생성
    if conversation_service:
        new_id = await conversation_service.create_conversation(user_id, mode)
        if new_id:
            return new_id

    # 서비스 없으면 임시 ID 생성
    import uuid
    return str(uuid.uuid4())


# ============================================
# API Endpoints
# ============================================

@router.post("/chat")
async def security_chat(
    request: ChatRequest,
    command_orchestrator: CommandOrchestratorDep = None,
    llm_client: LLMClientDep = None,
    conversation_service: ConversationServiceDep = None,
    cache_service: CacheServiceDep = None,
):
    """
    보안 모니터링 채팅 (SSE 스트리밍)

    Args:
        request: 채팅 요청

    Returns:
        Server-Sent Events 스트림
        - 첫 번째 이벤트에 conversation_id 포함
    """
    logger.info(f"💬 Chat request: mode={request.mode}, message='{request.message[:50]}...'")

    # 대화 ID 조회 또는 생성
    conv_id = await _get_or_create_conversation(
        request.conversation_id,
        request.user_id,
        request.mode,
        conversation_service,
    )

    async def generate_stream():
        """SSE 스트리밍 생성기"""
        try:
            # 0. 대화 ID 전송 (첫 번째 이벤트)
            yield f"data: {json.dumps({'conversation_id': conv_id})}\n\n"

            # 1. 시스템 프롬프트 가져오기
            system_prompt = get_system_prompt(request.mode)

            # 2. 대화 히스토리 구성
            messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

            # 대화 지속성: PostgreSQL에서 이전 대화 로드
            if conversation_service and request.conversation_id:
                context_messages = await conversation_service.get_context_messages(
                    conv_id,
                    context_window=request.context_window
                )
                messages.extend(context_messages)
            elif request.conversation_history:
                # 클라이언트 제공 히스토리 사용 (fallback)
                messages.extend([msg.dict() for msg in request.conversation_history])

            messages.append({"role": "user", "content": request.message})

            # 3. 사용자 메시지 저장
            if conversation_service:
                await conversation_service.add_message(
                    conversation_id=conv_id,
                    role="user",
                    content=request.message
                )

            # 4. Qwen Function Calling
            response = await llm_client.chat.completions.create(
                model=get_llm_model_name(),
                messages=messages,
                functions=SECURITY_FUNCTIONS,
                function_call="auto",
                stream=True,
                temperature=0.7,
                max_tokens=2048
            )

            # 5. 스트리밍 응답 처리
            full_content = ""
            final_content = ""  # 최종 응답 (function call 포함)
            function_call_data = None

            async for chunk in response:
                delta = chunk.choices[0].delta

                # 텍스트 컨텐츠
                if delta.content:
                    full_content += delta.content
                    yield f"data: {json.dumps({'content': delta.content})}\n\n"

                # Function Call
                if delta.function_call:
                    if not function_call_data:
                        function_call_data = {
                            "name": "",
                            "arguments": ""
                        }

                    if delta.function_call.name:
                        function_call_data["name"] = delta.function_call.name

                    if delta.function_call.arguments:
                        function_call_data["arguments"] += delta.function_call.arguments

            final_content = full_content

            # 6. Function Call 실행 (있는 경우)
            if function_call_data and function_call_data["name"]:
                logger.info(f"🔧 Executing function: {function_call_data['name']}")

                try:
                    # 함수 인자 파싱
                    function_args = json.loads(function_call_data["arguments"])

                    # Command Orchestrator를 통해 실행
                    result = await command_orchestrator.execute_function(
                        function_name=function_call_data["name"],
                        arguments=function_args,
                        user_id="web_user"
                    )

                    # 결과를 LLM에게 다시 전달하여 최종 응답 생성
                    function_result_message = {
                        "role": "function",
                        "name": function_call_data["name"],
                        "content": json.dumps(result, ensure_ascii=False)
                    }

                    messages.append({
                        "role": "assistant",
                        "content": full_content or "",
                        "function_call": function_call_data
                    })
                    messages.append(function_result_message)

                    # 최종 응답 생성
                    final_response = await llm_client.chat.completions.create(
                        model=get_llm_model_name(),
                        messages=messages,
                        stream=True,
                        temperature=0.7,
                        max_tokens=1024
                    )

                    function_response_content = ""
                    async for chunk in final_response:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            function_response_content += delta.content
                            yield f"data: {json.dumps({'content': delta.content})}\n\n"

                    # Function 실행 결과를 포함한 최종 응답
                    final_content = function_response_content

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to parse function arguments: {e}")
                    error_msg = f"\n\n오류: 함수 인자 파싱 실패 - {e}"
                    final_content = full_content + error_msg
                    yield f"data: {json.dumps({'content': error_msg})}\n\n"
                except Exception as e:
                    logger.error(f"❌ Function execution failed: {e}", exc_info=True)
                    error_msg = f"\n\n오류: {str(e)}"
                    final_content = full_content + error_msg
                    yield f"data: {json.dumps({'content': error_msg})}\n\n"

            # 7. 어시스턴트 응답 저장
            if conversation_service and final_content:
                await conversation_service.add_message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=final_content,
                    metadata={
                        "function_call": function_call_data
                    } if function_call_data else None
                )

            # 8. 스트림 종료
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"❌ Chat stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/modes")
async def get_chat_modes():
    """
    사용 가능한 채팅 모드 목록 조회

    Returns:
        {
            "modes": [
                {"id": "qa", "name": "문서 QA", "description": "..."},
                ...
            ]
        }
    """
    modes = [
        {
            "id": "qa",
            "name": "문서 QA",
            "description": "보안 정책, 로그, 매뉴얼 검색",
            "icon": "📚"
        },
        {
            "id": "device_register",
            "name": "장비 등록",
            "description": "CCTV/ACU 장비 등록",
            "icon": "📝"
        },
        {
            "id": "device_control",
            "name": "장비 제어",
            "description": "녹화, 도어 제어, 알람 해제",
            "icon": "🎛️"
        }
    ]

    return {"modes": modes}


@router.get("/health")
async def health_check(
    command_orchestrator: CommandOrchestratorDep = None,
    llm_client: LLMClientDep = None,
    conversation_service: ConversationServiceDep = None,
    cache_service: CacheServiceDep = None,
):
    """
    헬스 체크

    Returns:
        {"status": "healthy", "orchestrator": bool, "llm": bool, ...}
    """
    conv_healthy = False
    cache_healthy = False

    if conversation_service:
        conv_healthy = await conversation_service.health_check()

    if cache_service:
        cache_healthy = await cache_service.health_check()

    all_healthy = command_orchestrator and llm_client

    return {
        "status": "healthy" if all_healthy else "not_initialized",
        "orchestrator": command_orchestrator is not None,
        "llm": llm_client is not None,
        "conversation_service": conv_healthy,
        "cache_service": cache_healthy,
    }


# ============================================
# Conversation Management Endpoints
# ============================================

@router.get("/conversations")
async def list_conversations(
    user_id: str = Query(default="anonymous", description="사용자 ID"),
    limit: int = Query(default=20, ge=1, le=100, description="최대 조회 수"),
    include_inactive: bool = Query(default=False, description="비활성 대화 포함"),
    conversation_service: ConversationServiceDep = None,
):
    """
    대화 목록 조회

    Args:
        user_id: 사용자 ID
        limit: 최대 조회 수
        include_inactive: 비활성 대화 포함 여부

    Returns:
        {"conversations": [...]}
    """
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service not available")

    conversations = await conversation_service.list_conversations(
        user_id=user_id,
        limit=limit,
        include_inactive=include_inactive
    )

    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, conversation_service: ConversationServiceDep = None):
    """
    대화 세션 조회

    Args:
        conversation_id: 대화 ID

    Returns:
        대화 정보
    """
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service not available")

    conversation = await conversation_service.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=500, description="최대 조회 수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 메시지 수"),
    conversation_service: ConversationServiceDep = None,
):
    """
    대화 메시지 조회

    Args:
        conversation_id: 대화 ID
        limit: 최대 조회 수
        offset: 건너뛸 메시지 수

    Returns:
        {"messages": [...]}
    """
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service not available")

    messages = await conversation_service.get_messages(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset
    )

    return {"messages": messages}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    conversation_service: ConversationServiceDep = None,
    cache_service: CacheServiceDep = None,
):
    """
    대화 삭제

    Args:
        conversation_id: 대화 ID

    Returns:
        {"success": bool}
    """
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service not available")

    success = await conversation_service.delete_conversation(conversation_id)

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found or delete failed")

    # 캐시도 삭제
    if cache_service:
        await cache_service.delete_conversation_context(conversation_id)

    return {"success": True}


@router.post("/conversations/{conversation_id}/close")
async def close_conversation(conversation_id: str, conversation_service: ConversationServiceDep = None):
    """
    대화 세션 종료 (비활성화)

    Args:
        conversation_id: 대화 ID

    Returns:
        {"success": bool}
    """
    if not conversation_service:
        raise HTTPException(status_code=503, detail="Conversation service not available")

    success = await conversation_service.close_conversation(conversation_id)

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"success": True}


@router.get("/conversations/stats")
async def get_conversation_stats(
    conversation_service: ConversationServiceDep = None,
    cache_service: CacheServiceDep = None,
):
    """
    대화 통계 조회

    Returns:
        통계 정보
    """
    stats = {}

    if conversation_service:
        stats["conversation"] = await conversation_service.get_stats()

    if cache_service:
        stats["cache"] = await cache_service.get_cache_stats()

    return stats
