"""
Query Complexity Analyzer
쿼리 복잡도를 분석하여 적절한 검색 전략 결정
"""

import re
from typing import Dict


class ComplexityAnalyzer:
    """쿼리 복잡도 분석기"""

    def __init__(self):
        # 복잡한 질문 키워드 (한국어/영어)
        self.complex_keywords = [
            # 한국어
            '왜', '어떻게', '비교', '차이', '분석', '설명', '상세히',
            '자세히', '근거', '이유', '방법', '절차', '과정',
            # 영어
            'why', 'how', 'compare', 'difference', 'analyze', 'explain',
            'detail', 'reason', 'method', 'process', 'procedure'
        ]

        # 시간 관련 키워드
        self.temporal_keywords = [
            '최근', '오늘', '어제', '내일', '현재', '지금', '언제',
            'recent', 'today', 'yesterday', 'tomorrow', 'current', 'now', 'when'
        ]

    def analyze(self, query: str) -> Dict:
        """
        쿼리 복잡도 분석

        Args:
            query: 사용자 쿼리

        Returns:
            {
                'score': 0.0-1.0,
                'category': 'simple'|'hybrid'|'complex',
                'length_score': 0.0-1.0,
                'has_complex_intent': bool,
                'has_temporal': bool,
                'entity_count': int
            }
        """
        query_lower = query.lower()

        # 1. 길이 점수 (30 단어 이상이면 1.0)
        word_count = len(query.split())
        length_score = min(word_count / 30.0, 1.0)

        # 2. 복잡한 의도 검사
        has_complex_intent = any(
            keyword in query_lower
            for keyword in self.complex_keywords
        )

        # 3. 시간 정보 포함 여부
        has_temporal = any(
            keyword in query_lower
            for keyword in self.temporal_keywords
        )

        # 4. 엔티티 수 추정 (대문자로 시작하는 단어들)
        # 간단한 휴리스틱: 고유명사 수
        entities = re.findall(r'\b[A-Z][a-z]+\b', query)
        entity_count = len(set(entities))
        entity_score = min(entity_count / 5.0, 1.0)

        # 5. 질문 부호 개수
        question_marks = query.count('?')
        multi_question = question_marks > 1

        # 6. 최종 복잡도 점수 계산
        complexity_score = (
            length_score * 0.3 +
            float(has_complex_intent) * 0.4 +
            entity_score * 0.2 +
            float(multi_question) * 0.1
        )

        # 7. 카테고리 분류
        if complexity_score < 0.3:
            category = 'simple'
        elif complexity_score < 0.6:
            category = 'hybrid'
        else:
            category = 'complex'

        return {
            'score': round(complexity_score, 2),
            'category': category,
            'length_score': round(length_score, 2),
            'has_complex_intent': has_complex_intent,
            'has_temporal': has_temporal,
            'entity_count': entity_count,
            'multi_question': multi_question
        }


# 테스트
if __name__ == "__main__":
    analyzer = ComplexityAnalyzer()

    test_queries = [
        "안녕하세요",
        "Python이 뭐야?",
        "Python과 JavaScript의 차이점을 상세히 설명해줘",
        "최근 AI 기술 발전에 대해 분석해주고, 앞으로의 전망은 어떻게 되나요?",
    ]

    print("=" * 60)
    print("Query Complexity Analyzer Test")
    print("=" * 60)

    for query in test_queries:
        result = analyzer.analyze(query)
        print(f"\nQuery: {query}")
        print(f"  Score: {result['score']} ({result['category']})")
        print(f"  Length: {result['length_score']}")
        print(f"  Complex intent: {result['has_complex_intent']}")
        print(f"  Temporal: {result['has_temporal']}")
        print(f"  Entities: {result['entity_count']}")
