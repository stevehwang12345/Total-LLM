#!/usr/bin/env python3
"""
RAG Service for Security Monitoring

문서 검색 기능을 Command Orchestrator에 제공하는 서비스
- Redis 기반 쿼리-응답 캐싱 지원
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from retrievers.adaptive_retriever import AdaptiveRetriever
from services.cache_service import CacheService, get_cache_service

logger = logging.getLogger(__name__)


class RAGService:
    """
    문서 검색 서비스 (보안 정책, 로그, 매뉴얼)

    역할:
    1. Adaptive RAG 기반 문서 검색
    2. 메타데이터 필터링 (문서 유형: policy, log, manual)
    3. 검색 결과 포맷팅
    4. Redis 기반 캐싱 (Phase 2)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        cache_service: Optional[CacheService] = None
    ):
        """
        Args:
            config_path: config.yaml 경로 (기본: backend/config/config.yaml)
            cache_service: 캐시 서비스 (선택, 없으면 싱글톤 사용)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        # Adaptive Retriever 초기화
        self.retriever = AdaptiveRetriever(config_path=str(config_path))

        # 캐시 서비스 (나중에 초기화)
        self._cache_service = cache_service
        self._cache_initialized = False

        logger.info("✅ RAGService initialized")

    async def _get_cache(self) -> Optional[CacheService]:
        """캐시 서비스 lazy 초기화"""
        if not self._cache_initialized:
            try:
                self._cache_service = await get_cache_service()
                self._cache_initialized = True
            except Exception as e:
                logger.warning(f"Cache service initialization failed: {e}")
                self._cache_initialized = True  # 재시도 방지

        return self._cache_service

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, str]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        문서 검색 (캐싱 지원)

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 개수
            filter_metadata: 메타데이터 필터 (예: {"type": "policy"})
            use_cache: 캐시 사용 여부 (기본: True)

        Returns:
            {
                "documents": [
                    {
                        "content": str,
                        "metadata": {...},
                        "score": float
                    }
                ],
                "strategy": str,
                "cached": bool
            }
        """
        logger.info(f"🔍 Searching documents: query='{query}', top_k={top_k}, filter={filter_metadata}")

        # 캐시 조회
        cache = await self._get_cache() if use_cache else None
        retriever_type = "adaptive"

        if cache:
            cached_result = await cache.get_rag_cache(query, retriever_type, filter_metadata)
            if cached_result:
                logger.info("   📦 Cache hit!")
                # 캐시된 결과에서 top_k 적용
                cached_result['documents'] = cached_result['documents'][:top_k]
                cached_result['cached'] = True
                return cached_result

        # Adaptive Retriever 호출
        result = self.retriever.retrieve(query)

        documents = result.get('documents', [])
        strategy = result.get('strategy', 'unknown')

        logger.info(f"   Strategy: {strategy}, Found: {len(documents)} documents")

        # 메타데이터 필터링
        if filter_metadata and documents:
            documents = self._filter_by_metadata(documents, filter_metadata)
            logger.info(f"   After filtering: {len(documents)} documents")

        # 결과 포맷팅
        formatted_documents = []
        for doc in documents:
            formatted_documents.append({
                "content": doc.get('content', ''),
                "metadata": doc.get('metadata', {}),
                "score": doc.get('score', 0.0)
            })

        result_data = {
            "documents": formatted_documents,
            "strategy": strategy,
            "cached": False
        }

        # 캐시 저장 (필터가 없고 결과가 있을 때만)
        if cache and formatted_documents:
            await cache.set_rag_cache(
                query=query,
                result=result_data,
                retriever_type=retriever_type,
                filter_metadata=filter_metadata
            )

        # top_k 제한
        result_data['documents'] = formatted_documents[:top_k]

        return result_data

    async def search_simple(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        간단한 문서 검색 (documents만 반환, 기존 호환성)

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 개수
            filter_metadata: 메타데이터 필터

        Returns:
            문서 목록
        """
        result = await self.search(query, top_k, filter_metadata)
        return result.get('documents', [])

    def _filter_by_metadata(
        self,
        documents: List[Dict[str, Any]],
        filter_metadata: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        메타데이터 기반 필터링

        Args:
            documents: 검색 결과 문서 리스트
            filter_metadata: 필터 조건 (예: {"type": "policy"})

        Returns:
            필터링된 문서 리스트
        """
        filtered = []

        for doc in documents:
            metadata = doc.get('metadata', {})

            # 모든 필터 조건이 매치되는지 확인
            match = True
            for key, value in filter_metadata.items():
                if metadata.get(key) != value:
                    match = False
                    break

            if match:
                filtered.append(doc)

        return filtered

    # ============================================
    # 문서 인덱싱 (관리용)
    # ============================================

    async def index_document(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        문서 인덱싱 (Qdrant에 추가)

        Args:
            content: 문서 내용
            metadata: 메타데이터 (type, source, page 등)

        Returns:
            Document ID
        """
        # RAGTool을 통해 문서 추가
        rag_tool = self.retriever.rag_tool

        # Qdrant에 추가
        doc_id = await rag_tool.add_document(content, metadata)

        logger.info(f"✅ Document indexed: {doc_id}")
        return doc_id

    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        컬렉션 통계 조회

        Returns:
            {
                "total_documents": int,
                "vector_size": int,
                "collection_name": str,
                "cache_stats": {...}
            }
        """
        rag_tool = self.retriever.rag_tool

        stats = {
            "collection_name": rag_tool.collection_name,
            "vector_size": rag_tool.vector_size,
            "total_documents": 0
        }

        try:
            # Qdrant 클라이언트로 통계 조회
            collection_info = rag_tool.qdrant_client.get_collection(rag_tool.collection_name)
            stats["total_documents"] = collection_info.points_count
        except Exception as e:
            logger.warning(f"Failed to get collection stats: {e}")

        # 캐시 통계 추가
        try:
            cache = await self._get_cache()
            if cache:
                cache_stats = await cache.get_cache_stats()
                stats["cache_stats"] = cache_stats
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")

        return stats

    async def invalidate_cache(self, pattern: str = "*") -> int:
        """
        RAG 캐시 무효화

        Args:
            pattern: 키 패턴 (기본: 전체)

        Returns:
            삭제된 키 수
        """
        try:
            cache = await self._get_cache()
            if cache:
                return await cache.invalidate_rag_cache(pattern)
            return 0
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
            return 0
