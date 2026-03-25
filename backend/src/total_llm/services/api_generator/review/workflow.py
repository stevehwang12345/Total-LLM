"""
ReviewWorkflow - 코드 리뷰 워크플로우 관리

생성된 코드의 자동 테스트, 검증, 승인 워크플로우를 관리합니다.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path
import uuid

from .validator import CodeValidator, ValidationResult
from ..generators.base import GeneratedArtifact, ArtifactStatus, ArtifactType

logger = logging.getLogger(__name__)


class ReviewStatus(Enum):
    """리뷰 상태"""
    PENDING = "pending"           # 리뷰 대기
    VALIDATING = "validating"     # 자동 검증 중
    VALIDATION_FAILED = "validation_failed"  # 검증 실패
    AWAITING_REVIEW = "awaiting_review"      # 리뷰 대기
    IN_REVIEW = "in_review"       # 리뷰 중
    APPROVED = "approved"         # 승인됨
    REJECTED = "rejected"         # 거부됨
    DEPLOYED = "deployed"         # 배포됨


@dataclass
class ReviewComment:
    """리뷰 코멘트"""
    reviewer_id: str
    content: str
    line_number: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ReviewItem:
    """리뷰 아이템"""
    id: str
    artifact: GeneratedArtifact
    status: ReviewStatus = ReviewStatus.PENDING
    validation_result: Optional[ValidationResult] = None
    comments: List[ReviewComment] = field(default_factory=list)
    reviewer_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    reviewed_at: Optional[str] = None
    deployed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "artifact": {
                "type": self.artifact.artifact_type.value,
                "file_name": self.artifact.file_name,
                "status": self.artifact.status.value,
                "metadata": self.artifact.metadata,
            },
            "status": self.status.value,
            "validation_result": self.validation_result.to_dict() if self.validation_result else None,
            "comments": [
                {
                    "reviewer_id": c.reviewer_id,
                    "content": c.content,
                    "line_number": c.line_number,
                    "created_at": c.created_at,
                }
                for c in self.comments
            ],
            "reviewer_id": self.reviewer_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewed_at": self.reviewed_at,
            "deployed_at": self.deployed_at,
        }


class ReviewWorkflow:
    """
    코드 리뷰 워크플로우 관리자

    1. 자동 검증 (CodeValidator)
    2. 리뷰 대기열 관리
    3. 승인/거부 처리
    4. 배포 트리거
    """

    def __init__(
        self,
        validator: Optional[CodeValidator] = None,
        auto_approve_threshold: float = 95.0,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            validator: 코드 검증기
            auto_approve_threshold: 자동 승인 임계값 (점수)
            config: 추가 설정
        """
        self.validator = validator or CodeValidator()
        self.auto_approve_threshold = auto_approve_threshold
        self.config = config or {}

        # 리뷰 큐 (in-memory, 실제 구현에서는 DB 사용)
        self._review_queue: Dict[str, ReviewItem] = {}

    async def submit_for_review(
        self,
        artifact: GeneratedArtifact,
        auto_validate: bool = True
    ) -> ReviewItem:
        """
        리뷰 제출

        Args:
            artifact: 생성된 아티팩트
            auto_validate: 자동 검증 수행 여부

        Returns:
            생성된 리뷰 아이템
        """
        # 리뷰 아이템 생성
        review_id = str(uuid.uuid4())[:8]
        review_item = ReviewItem(
            id=review_id,
            artifact=artifact,
            status=ReviewStatus.PENDING,
        )

        # 큐에 추가
        self._review_queue[review_id] = review_item

        logger.info(f"Submitted artifact for review: {review_id}")

        # 자동 검증
        if auto_validate:
            review_item = await self.validate(review_id)

        return review_item

    async def validate(self, review_id: str) -> ReviewItem:
        """
        자동 검증 수행

        Args:
            review_id: 리뷰 ID

        Returns:
            업데이트된 리뷰 아이템
        """
        review_item = self._review_queue.get(review_id)
        if not review_item:
            raise ValueError(f"Review not found: {review_id}")

        review_item.status = ReviewStatus.VALIDATING
        review_item.updated_at = datetime.now().isoformat()

        # 아티팩트 타입별 검증
        artifact_type = review_item.artifact.artifact_type
        code = review_item.artifact.content

        if artifact_type == ArtifactType.ADAPTER:
            result = self.validator.validate_adapter(code)
        elif artifact_type == ArtifactType.SCHEMA:
            result = self.validator.validate_schema(code)
        elif artifact_type == ArtifactType.ENDPOINT:
            result = self.validator.validate_router(code)
        else:
            result = self.validator.validate(code)

        review_item.validation_result = result

        # 검증 결과에 따른 상태 업데이트
        if not result.valid:
            review_item.status = ReviewStatus.VALIDATION_FAILED
            review_item.artifact.status = ArtifactStatus.REJECTED
            logger.warning(f"Validation failed for {review_id}: {result.error_count} errors")
        elif result.score >= self.auto_approve_threshold:
            # 자동 승인
            review_item.status = ReviewStatus.APPROVED
            review_item.artifact.status = ArtifactStatus.REVIEWED
            review_item.reviewed_at = datetime.now().isoformat()
            logger.info(f"Auto-approved {review_id} with score {result.score}")
        else:
            # 리뷰 필요
            review_item.status = ReviewStatus.AWAITING_REVIEW
            logger.info(f"Review required for {review_id} (score: {result.score})")

        review_item.updated_at = datetime.now().isoformat()
        return review_item

    async def start_review(self, review_id: str, reviewer_id: str) -> ReviewItem:
        """
        리뷰 시작

        Args:
            review_id: 리뷰 ID
            reviewer_id: 리뷰어 ID

        Returns:
            업데이트된 리뷰 아이템
        """
        review_item = self._review_queue.get(review_id)
        if not review_item:
            raise ValueError(f"Review not found: {review_id}")

        if review_item.status not in [ReviewStatus.AWAITING_REVIEW, ReviewStatus.VALIDATION_FAILED]:
            raise ValueError(f"Review {review_id} is not awaiting review")

        review_item.status = ReviewStatus.IN_REVIEW
        review_item.reviewer_id = reviewer_id
        review_item.updated_at = datetime.now().isoformat()

        logger.info(f"Review started for {review_id} by {reviewer_id}")
        return review_item

    async def add_comment(
        self,
        review_id: str,
        reviewer_id: str,
        content: str,
        line_number: Optional[int] = None
    ) -> ReviewItem:
        """
        코멘트 추가

        Args:
            review_id: 리뷰 ID
            reviewer_id: 리뷰어 ID
            content: 코멘트 내용
            line_number: 라인 번호 (선택)

        Returns:
            업데이트된 리뷰 아이템
        """
        review_item = self._review_queue.get(review_id)
        if not review_item:
            raise ValueError(f"Review not found: {review_id}")

        comment = ReviewComment(
            reviewer_id=reviewer_id,
            content=content,
            line_number=line_number,
        )
        review_item.comments.append(comment)
        review_item.updated_at = datetime.now().isoformat()

        logger.info(f"Comment added to {review_id} by {reviewer_id}")
        return review_item

    async def approve(
        self,
        review_id: str,
        reviewer_id: str,
        comment: Optional[str] = None
    ) -> ReviewItem:
        """
        승인

        Args:
            review_id: 리뷰 ID
            reviewer_id: 리뷰어 ID
            comment: 승인 코멘트 (선택)

        Returns:
            업데이트된 리뷰 아이템
        """
        review_item = self._review_queue.get(review_id)
        if not review_item:
            raise ValueError(f"Review not found: {review_id}")

        if comment:
            await self.add_comment(review_id, reviewer_id, f"[APPROVED] {comment}")

        review_item.status = ReviewStatus.APPROVED
        review_item.artifact.status = ArtifactStatus.REVIEWED
        review_item.reviewer_id = reviewer_id
        review_item.reviewed_at = datetime.now().isoformat()
        review_item.updated_at = datetime.now().isoformat()

        logger.info(f"Review {review_id} approved by {reviewer_id}")
        return review_item

    async def reject(
        self,
        review_id: str,
        reviewer_id: str,
        reason: str
    ) -> ReviewItem:
        """
        거부

        Args:
            review_id: 리뷰 ID
            reviewer_id: 리뷰어 ID
            reason: 거부 사유

        Returns:
            업데이트된 리뷰 아이템
        """
        review_item = self._review_queue.get(review_id)
        if not review_item:
            raise ValueError(f"Review not found: {review_id}")

        await self.add_comment(review_id, reviewer_id, f"[REJECTED] {reason}")

        review_item.status = ReviewStatus.REJECTED
        review_item.artifact.status = ArtifactStatus.REJECTED
        review_item.reviewer_id = reviewer_id
        review_item.reviewed_at = datetime.now().isoformat()
        review_item.updated_at = datetime.now().isoformat()

        logger.info(f"Review {review_id} rejected by {reviewer_id}: {reason}")
        return review_item

    async def request_changes(
        self,
        review_id: str,
        reviewer_id: str,
        changes: List[str]
    ) -> ReviewItem:
        """
        변경 요청

        Args:
            review_id: 리뷰 ID
            reviewer_id: 리뷰어 ID
            changes: 요청 변경사항 목록

        Returns:
            업데이트된 리뷰 아이템
        """
        review_item = self._review_queue.get(review_id)
        if not review_item:
            raise ValueError(f"Review not found: {review_id}")

        changes_text = "\n".join(f"- {c}" for c in changes)
        await self.add_comment(review_id, reviewer_id, f"[CHANGES REQUESTED]\n{changes_text}")

        review_item.status = ReviewStatus.AWAITING_REVIEW
        review_item.updated_at = datetime.now().isoformat()

        logger.info(f"Changes requested for {review_id} by {reviewer_id}")
        return review_item

    def get_review(self, review_id: str) -> Optional[ReviewItem]:
        """리뷰 아이템 조회"""
        return self._review_queue.get(review_id)

    def get_pending_reviews(self) -> List[ReviewItem]:
        """대기 중인 리뷰 목록"""
        return [
            item for item in self._review_queue.values()
            if item.status in [ReviewStatus.AWAITING_REVIEW, ReviewStatus.VALIDATION_FAILED]
        ]

    def get_approved_reviews(self) -> List[ReviewItem]:
        """승인된 리뷰 목록"""
        return [
            item for item in self._review_queue.values()
            if item.status == ReviewStatus.APPROVED
        ]

    def get_reviews_by_status(self, status: ReviewStatus) -> List[ReviewItem]:
        """상태별 리뷰 목록"""
        return [
            item for item in self._review_queue.values()
            if item.status == status
        ]

    def get_all_reviews(self) -> List[ReviewItem]:
        """모든 리뷰 목록"""
        return list(self._review_queue.values())

    async def batch_validate(self, review_ids: List[str]) -> Dict[str, ReviewItem]:
        """
        일괄 검증

        Args:
            review_ids: 리뷰 ID 목록

        Returns:
            검증된 리뷰 아이템 딕셔너리
        """
        results = {}
        tasks = [self.validate(rid) for rid in review_ids]
        validated = await asyncio.gather(*tasks, return_exceptions=True)

        for rid, result in zip(review_ids, validated):
            if isinstance(result, Exception):
                logger.error(f"Validation failed for {rid}: {result}")
            else:
                results[rid] = result

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """리뷰 통계"""
        total = len(self._review_queue)
        by_status = {}

        for status in ReviewStatus:
            count = len([i for i in self._review_queue.values() if i.status == status])
            by_status[status.value] = count

        # 평균 점수
        scores = [
            i.validation_result.score
            for i in self._review_queue.values()
            if i.validation_result
        ]
        avg_score = sum(scores) / len(scores) if scores else 0

        return {
            "total": total,
            "by_status": by_status,
            "average_score": avg_score,
            "pending_count": by_status.get("awaiting_review", 0),
            "approved_count": by_status.get("approved", 0),
            "rejected_count": by_status.get("rejected", 0),
        }
