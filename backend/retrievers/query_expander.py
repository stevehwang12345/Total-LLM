"""
Query Expansion using LLM for Multi-Query RAG

Generates multiple variations of a query to improve retrieval coverage.
This addresses the query ambiguity problem and improves recall.
"""

from typing import List, Dict, Optional
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from config.model_config import get_llm_model_name, get_llm_base_url

logger = logging.getLogger(__name__)


class QueryExpander:
    """
    LLM 기반 쿼리 확장 (Multi-Query Generation)

    하나의 쿼리를 여러 변형으로 확장하여 검색 커버리지를 향상시킵니다.

    Benefits:
    - 모호한 쿼리 처리 개선
    - 다양한 관점에서 검색
    - Recall 향상 (놓친 문서 발견)
    - 키워드 변형으로 BM25 성능 향상
    """

    def __init__(
        self,
        llm_base_url: str = None,
        llm_model: str = None,
        temperature: float = 0.7,
        num_queries: int = 3
    ):
        """
        Initialize Query Expander

        Args:
            llm_base_url: vLLM API base URL
            llm_model: Model name/path
            temperature: LLM temperature (higher = more diverse)
            num_queries: Number of query variations to generate
        """
        self.num_queries = num_queries
        self.temperature = temperature

        # 중앙 설정에서 기본값 가져오기
        effective_base_url = llm_base_url or get_llm_base_url()
        effective_model = llm_model or get_llm_model_name()

        # Initialize LLM
        try:
            self.llm = ChatOpenAI(
                base_url=effective_base_url,
                model=effective_model,
                temperature=temperature,
                max_tokens=512,
                api_key="dummy"  # vLLM doesn't need real API key
            )
            logger.info(f"QueryExpander initialized with {effective_base_url}, model={effective_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

        # Query expansion prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that generates alternative versions of user queries to improve search results.

Your task:
1. Analyze the user's original query
2. Generate {num_queries} alternative queries that:
   - Cover different aspects or perspectives of the question
   - Use different keywords and phrasings
   - Maintain the same search intent
   - Are specific and clear (not too broad)

Rules:
- Each query should be on a new line
- Do NOT number the queries
- Do NOT include explanations
- Keep queries concise (1-2 sentences max)
- Focus on retrieving relevant documents

Example:
Original: "What is machine learning?"
Alternatives:
How does machine learning work?
Explain the basics of ML algorithms
What are the key concepts in machine learning?"""),
            ("user", "Original query: {query}\n\nGenerate {num_queries} alternative queries:")
        ])

    def expand(self, query: str, num_queries: Optional[int] = None) -> List[str]:
        """
        Expand a single query into multiple variations

        Args:
            query: Original user query
            num_queries: Number of variations (overrides default)

        Returns:
            List of query variations (including original)
        """
        if num_queries is None:
            num_queries = self.num_queries

        try:
            # Generate query variations using LLM
            chain = self.prompt | self.llm
            response = chain.invoke({
                "query": query,
                "num_queries": num_queries
            })

            # Parse response into individual queries
            content = response.content.strip()
            expanded_queries = [
                q.strip()
                for q in content.split('\n')
                if q.strip() and not q.strip().startswith('#')
            ]

            # Filter out empty or invalid queries
            expanded_queries = [q for q in expanded_queries if len(q) > 5]

            # Always include original query
            all_queries = [query] + expanded_queries[:num_queries]

            logger.info(f"Expanded 1 query → {len(all_queries)} queries")
            logger.debug(f"Queries: {all_queries}")

            return all_queries

        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            # Fallback: return original query only
            return [query]

    def expand_with_metadata(
        self,
        query: str,
        num_queries: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Expand query and return with metadata

        Args:
            query: Original query
            num_queries: Number of variations

        Returns:
            {
                'original': str,
                'expanded': List[str],
                'all_queries': List[str],
                'count': int
            }
        """
        all_queries = self.expand(query, num_queries)

        return {
            'original': query,
            'expanded': all_queries[1:],  # Exclude original
            'all_queries': all_queries,
            'count': len(all_queries)
        }

    def expand_batch(
        self,
        queries: List[str],
        num_queries: Optional[int] = None
    ) -> List[List[str]]:
        """
        Expand multiple queries in batch

        Args:
            queries: List of original queries
            num_queries: Number of variations per query

        Returns:
            List of expanded query lists
        """
        return [self.expand(q, num_queries) for q in queries]


# Simpler rule-based expander (fallback or fast mode)
class RuleBasedQueryExpander:
    """
    규칙 기반 쿼리 확장 (LLM 없이 동작)

    간단한 규칙으로 쿼리 변형 생성:
    - 동의어 치환
    - 질문 형태 변환
    - 키워드 추출 및 재조합
    """

    def __init__(self):
        # Question transformations
        self.question_transforms = {
            "what is": ["explain", "describe", "define"],
            "how to": ["steps for", "way to", "method for"],
            "why": ["reason for", "cause of", "explanation of"],
            "when": ["time for", "timing of"],
            "where": ["location of", "place for"]
        }

    def expand(self, query: str, num_queries: int = 2) -> List[str]:
        """
        Generate query variations using rules

        Args:
            query: Original query
            num_queries: Number of variations

        Returns:
            List of query variations (including original)
        """
        queries = [query]
        query_lower = query.lower()

        # Try question transformations
        for pattern, replacements in self.question_transforms.items():
            if pattern in query_lower:
                for replacement in replacements[:num_queries]:
                    variant = query_lower.replace(pattern, replacement)
                    queries.append(variant.capitalize())
                    if len(queries) > num_queries:
                        break
                break

        # Add keyword-only version (remove question words)
        question_words = ["what", "how", "why", "when", "where", "is", "are", "the"]
        keywords = [w for w in query.lower().split() if w not in question_words]
        if len(keywords) >= 2:
            keyword_query = " ".join(keywords)
            queries.append(keyword_query)

        return queries[:num_queries + 1]  # +1 for original


# Example usage and testing
if __name__ == "__main__":
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("Query Expansion Testing")
    print("=" * 70)
    print()

    # Test 1: Rule-based expander (no LLM required)
    print("Test 1: Rule-Based Query Expander")
    print("-" * 70)
    rule_expander = RuleBasedQueryExpander()

    test_queries = [
        "What is machine learning?",
        "How to train a neural network?",
        "Why is Python popular?"
    ]

    for query in test_queries:
        expanded = rule_expander.expand(query, num_queries=2)
        print(f"\nOriginal: {query}")
        for i, q in enumerate(expanded[1:], 1):
            print(f"  {i}. {q}")

    print("\n" + "=" * 70)

    # Test 2: LLM-based expander (requires vLLM running)
    try:
        print("Test 2: LLM-Based Query Expander")
        print("-" * 70)
        print("Checking vLLM connection...")

        llm_expander = QueryExpander(
            num_queries=3  # 기본 URL과 모델은 중앙 설정에서 가져옴
        )

        test_query = "What is machine learning?"
        print(f"\nOriginal query: {test_query}")
        print("Generating variations with LLM...")

        result = llm_expander.expand_with_metadata(test_query)

        print(f"\nGenerated {result['count']} queries:")
        for i, q in enumerate(result['all_queries'], 1):
            marker = "(original)" if i == 1 else ""
            print(f"  {i}. {q} {marker}")

        print("\n✅ LLM-based expansion test passed!")

    except Exception as e:
        print(f"\n⚠️  LLM-based test skipped: {e}")
        print("   (This is expected if vLLM is not running)")

    print("\n" + "=" * 70)
    print("Testing complete!")
    print("=" * 70)
