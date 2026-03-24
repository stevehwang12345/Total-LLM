"""
Cross-Encoder Re-ranker for improving search result quality.

Cross-encoder models directly compute relevance scores between query-document pairs,
providing more accurate ranking than bi-encoder (vector similarity) approaches.
"""

from typing import List, Dict, Optional
import logging
from sentence_transformers import CrossEncoder
import numpy as np

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    Cross-Encoder 기반 재순위화 (Re-ranking)

    하이브리드 검색 결과를 Cross-Encoder로 재평가하여
    더 정확한 관련성 점수를 계산합니다.

    Features:
    - Cross-encoder 모델로 query-document 관련성 직접 계산
    - 기존 검색 결과의 순위 개선
    - 상위 k개 결과만 재순위화하여 성능 최적화
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        max_length: int = 512
    ):
        """
        Initialize Cross-Encoder Re-ranker

        Args:
            model_name: Cross-encoder model name
                - "cross-encoder/ms-marco-MiniLM-L-6-v2" (default, fast, 80MB)
                - "cross-encoder/ms-marco-MiniLM-L-12-v2" (better, 120MB)
                - "cross-encoder/ms-marco-electra-base" (best, 400MB)
            device: Device to run model on ("cpu" or "cuda")
            max_length: Maximum sequence length for input
        """
        self.model_name = model_name
        self.device = device
        self.max_length = max_length

        logger.info(f"Loading Cross-Encoder model: {model_name}")
        try:
            self.model = CrossEncoder(
                model_name,
                max_length=max_length,
                device=device
            )
            logger.info(f"Cross-Encoder model loaded successfully on {device}")
        except Exception as e:
            logger.error(f"Failed to load Cross-Encoder model: {e}")
            raise

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Re-rank documents using Cross-Encoder

        Args:
            query: Search query
            documents: List of documents with 'text', 'score', etc.
            top_k: Number of top results to return (None = all)

        Returns:
            Re-ranked documents with updated 'rerank_score' field
        """
        if not documents:
            return []

        # Prepare query-document pairs for Cross-Encoder
        pairs = []
        for doc in documents:
            text = doc.get('text', '')
            pairs.append([query, text])

        try:
            # Compute relevance scores with Cross-Encoder
            logger.debug(f"Re-ranking {len(documents)} documents with Cross-Encoder")
            scores = self.model.predict(pairs, show_progress_bar=False)

            # Convert to numpy array if not already
            if not isinstance(scores, np.ndarray):
                scores = np.array(scores)

            # Attach re-rank scores to documents
            reranked_docs = []
            for idx, doc in enumerate(documents):
                doc_copy = doc.copy()
                doc_copy['rerank_score'] = float(scores[idx])
                doc_copy['original_score'] = doc.get('score', 0.0)
                reranked_docs.append(doc_copy)

            # Sort by re-rank score (descending)
            reranked_docs.sort(key=lambda x: x['rerank_score'], reverse=True)

            # Return top_k results if specified
            if top_k is not None:
                reranked_docs = reranked_docs[:top_k]

            logger.debug(f"Re-ranking complete. Top score: {reranked_docs[0]['rerank_score']:.4f}")
            return reranked_docs

        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            # Return original documents on failure
            return documents

    def rerank_with_threshold(
        self,
        query: str,
        documents: List[Dict],
        threshold: float = 0.0,
        top_k: Optional[int] = None
    ) -> List[Dict]:
        """
        Re-rank documents and filter by score threshold

        Args:
            query: Search query
            documents: List of documents
            threshold: Minimum rerank_score to include (default: 0.0)
            top_k: Maximum number of results

        Returns:
            Filtered and re-ranked documents
        """
        reranked = self.rerank(query, documents, top_k=None)

        # Filter by threshold
        filtered = [doc for doc in reranked if doc['rerank_score'] >= threshold]

        # Apply top_k limit
        if top_k is not None:
            filtered = filtered[:top_k]

        logger.debug(
            f"Filtered {len(documents)} → {len(filtered)} documents "
            f"(threshold: {threshold})"
        )

        return filtered

    def compute_score(self, query: str, text: str) -> float:
        """
        Compute relevance score for a single query-text pair

        Args:
            query: Search query
            text: Document text

        Returns:
            Relevance score (float)
        """
        try:
            score = self.model.predict([[query, text]], show_progress_bar=False)
            return float(score[0])
        except Exception as e:
            logger.error(f"Score computation failed: {e}")
            return 0.0

    def batch_score(
        self,
        query: str,
        texts: List[str],
        batch_size: int = 32
    ) -> List[float]:
        """
        Compute relevance scores for multiple texts in batches

        Args:
            query: Search query
            texts: List of document texts
            batch_size: Batch size for processing

        Returns:
            List of relevance scores
        """
        if not texts:
            return []

        pairs = [[query, text] for text in texts]

        try:
            scores = self.model.predict(
                pairs,
                batch_size=batch_size,
                show_progress_bar=False
            )
            return [float(s) for s in scores]
        except Exception as e:
            logger.error(f"Batch scoring failed: {e}")
            return [0.0] * len(texts)


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize reranker
    reranker = CrossEncoderReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu"
    )

    # Test data
    query = "What is machine learning?"

    documents = [
        {
            'id': '1',
            'text': 'Machine learning is a subset of artificial intelligence.',
            'score': 0.75
        },
        {
            'id': '2',
            'text': 'Deep learning uses neural networks with multiple layers.',
            'score': 0.70
        },
        {
            'id': '3',
            'text': 'Python is a popular programming language.',
            'score': 0.65
        },
        {
            'id': '4',
            'text': 'Machine learning algorithms learn patterns from data.',
            'score': 0.60
        }
    ]

    print("Original ranking:")
    for i, doc in enumerate(documents, 1):
        print(f"{i}. (score={doc['score']:.2f}) {doc['text'][:50]}...")

    # Re-rank
    reranked = reranker.rerank(query, documents, top_k=3)

    print("\nRe-ranked results (top 3):")
    for i, doc in enumerate(reranked, 1):
        print(
            f"{i}. (rerank={doc['rerank_score']:.4f}, original={doc['original_score']:.2f}) "
            f"{doc['text'][:50]}..."
        )

    # Test single score
    single_score = reranker.compute_score(
        query,
        "Machine learning enables computers to learn without explicit programming."
    )
    print(f"\nSingle score test: {single_score:.4f}")
