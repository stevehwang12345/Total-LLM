"""
Integration Tests for Adaptive RAG System
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from core.complexity_analyzer import ComplexityAnalyzer
from retrievers.adaptive_retriever import AdaptiveRetriever


def test_complexity_analyzer():
    """복잡도 분석기 테스트"""
    print("\n" + "=" * 60)
    print("Test 1: Complexity Analyzer")
    print("=" * 60)

    analyzer = ComplexityAnalyzer()

    test_cases = [
        ("안녕", "simple"),
        ("Python이 뭐야?", "simple"),
        ("Python과 JavaScript의 차이점을 설명해줘", "hybrid"),
        ("최근 AI 기술의 발전을 상세히 분석하고, 향후 전망과 과제를 비교해줘", "complex"),
    ]

    for query, expected_category in test_cases:
        result = analyzer.analyze(query)
        actual_category = result['category']
        status = "✅" if actual_category == expected_category else "❌"

        print(f"\n{status} Query: {query}")
        print(f"   Expected: {expected_category}")
        print(f"   Actual: {actual_category} (score: {result['score']})")

    print("\n✅ Complexity Analyzer Test Complete")


def test_rag_tool():
    """RAG 도구 테스트 (Qdrant 연결 필요)"""
    print("\n" + "=" * 60)
    print("Test 2: RAG Tool")
    print("=" * 60)

    try:
        from tools.rag_tool import RAGTool

        tool = RAGTool()

        # 테스트 문서 추가
        test_docs = [
            "Python은 간결하고 읽기 쉬운 프로그래밍 언어입니다.",
            "JavaScript는 웹 브라우저에서 실행되는 스크립트 언어입니다.",
            "Docker는 컨테이너 기반 가상화 플랫폼입니다."
        ]

        tool.add_documents(test_docs)
        print("✅ Documents added")

        # 검색 테스트
        results = tool.search("Python", k=2)
        print(f"✅ Search completed: {len(results)} results")

        if results:
            print(f"\n   Top result: {results[0]['text']}")
            print(f"   Score: {results[0]['score']:.3f}")

    except Exception as e:
        print(f"❌ RAG Tool Test Failed: {e}")
        print("   Make sure Qdrant is running: docker-compose up -d qdrant")

    print("\n✅ RAG Tool Test Complete")


def test_adaptive_retriever():
    """Adaptive Retriever 테스트"""
    print("\n" + "=" * 60)
    print("Test 3: Adaptive Retriever")
    print("=" * 60)

    try:
        retriever = AdaptiveRetriever()

        test_queries = [
            "안녕",
            "Python이 뭐야?",
            "Python과 JavaScript의 차이를 상세히 설명해줘",
        ]

        for query in test_queries:
            result = retriever.retrieve(query)

            print(f"\n📝 Query: {query}")
            print(f"   Complexity: {result['complexity']['score']} ({result['complexity']['category']})")
            print(f"   Strategy: {result['strategy']}")
            print(f"   k: {result['k']}")
            print(f"   Documents found: {len(result['documents'])}")

        print("\n✅ Adaptive Retriever Test Complete")

    except Exception as e:
        print(f"❌ Adaptive Retriever Test Failed: {e}")


def test_vllm_connection():
    """vLLM 서버 연결 테스트"""
    print("\n" + "=" * 60)
    print("Test 4: vLLM Connection")
    print("=" * 60)

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url="http://localhost:9000/v1",
            api_key="EMPTY"
        )

        # 간단한 추론 테스트
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": "안녕하세요"}],
            max_tokens=50
        )

        answer = response.choices[0].message.content

        print("✅ vLLM server connected")
        print(f"   Response: {answer[:100]}")

    except Exception as e:
        print(f"❌ vLLM Connection Failed: {e}")
        print("   Make sure vLLM is running: ./services/vllm/run_vllm.sh")

    print("\n✅ vLLM Connection Test Complete")


def test_end_to_end():
    """End-to-end 통합 테스트"""
    print("\n" + "=" * 60)
    print("Test 5: End-to-End Integration")
    print("=" * 60)

    try:
        from openai import OpenAI
        from retrievers.adaptive_retriever import AdaptiveRetriever

        # 1. Retriever 초기화
        retriever = AdaptiveRetriever()

        # 2. LLM 클라이언트
        client = OpenAI(
            base_url="http://localhost:9000/v1",
            api_key="EMPTY"
        )

        # 3. 테스트 쿼리
        query = "Python이 뭐야?"

        # 4. 검색
        retrieval_result = retriever.retrieve(query)
        print(f"✅ Retrieved {len(retrieval_result['documents'])} documents")

        # 5. 컨텍스트 구성
        if retrieval_result['documents']:
            context = retrieval_result['documents'][0]['text']
            prompt = f"Context: {context}\n\nQuestion: {query}\n\nAnswer:"
        else:
            prompt = f"Question: {query}\n\nAnswer:"

        # 6. LLM 생성
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )

        answer = response.choices[0].message.content

        print(f"✅ Generated answer")
        print(f"\n   Query: {query}")
        print(f"   Strategy: {retrieval_result['strategy']}")
        print(f"   Answer: {answer[:200]}...")

    except Exception as e:
        print(f"❌ End-to-End Test Failed: {e}")

    print("\n✅ End-to-End Test Complete")


def main():
    """모든 테스트 실행"""
    print("\n" + "=" * 60)
    print("🧪 Adaptive RAG Integration Tests")
    print("=" * 60)

    # 1. 복잡도 분석기 (의존성 없음)
    test_complexity_analyzer()

    # 2. RAG 도구 (Qdrant 필요)
    test_rag_tool()

    # 3. Adaptive Retriever (Qdrant 필요)
    test_adaptive_retriever()

    # 4. vLLM 연결 (vLLM 서버 필요)
    test_vllm_connection()

    # 5. End-to-end (모두 필요)
    test_end_to_end()

    print("\n" + "=" * 60)
    print("✅ All Tests Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
