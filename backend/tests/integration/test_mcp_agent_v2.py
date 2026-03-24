"""
Test script for Prompt Engineering MCP Agent
XML 기반 도구 호출 테스트
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from agents.mcp_agent_v2 import PromptEngineeringMCPAgent


async def test_basic_math():
    """기본 수학 연산 테스트"""
    print("\n" + "="*60)
    print("TEST 1: 기본 수학 연산 (25 곱하기 4)")
    print("="*60)

    agent = PromptEngineeringMCPAgent()
    await agent.initialize()

    result = await agent.query("25 곱하기 4는?")

    print(f"\n✅ 최종 답변: {result['answer']}")
    print(f"📊 반복: {result['iterations']}회")
    print(f"🔧 도구 호출: {len(result['tool_calls'])}번")

    if result['tool_calls']:
        print("\n📝 도구 호출 내역:")
        for i, tc in enumerate(result['tool_calls'], 1):
            print(f"   {i}. {tc['name']}({tc['args']})")

    assert len(result['tool_calls']) > 0, "도구 호출이 없습니다"
    assert 'multiply' in [tc['name'] for tc in result['tool_calls']], "multiply 도구가 호출되지 않았습니다"

    print("\n✅ TEST 1 PASSED")
    return result


async def test_search():
    """웹 검색 테스트"""
    print("\n" + "="*60)
    print("TEST 2: 웹 검색 (Python 검색)")
    print("="*60)

    agent = PromptEngineeringMCPAgent()
    await agent.initialize()

    result = await agent.query("Python에 대해 검색해줘")

    print(f"\n✅ 최종 답변: {result['answer']}")
    print(f"📊 반복: {result['iterations']}회")
    print(f"🔧 도구 호출: {len(result['tool_calls'])}번")

    if result['tool_calls']:
        print("\n📝 도구 호출 내역:")
        for i, tc in enumerate(result['tool_calls'], 1):
            print(f"   {i}. {tc['name']}({tc['args']})")

    assert len(result['tool_calls']) > 0, "도구 호출이 없습니다"
    assert 'web_search' in [tc['name'] for tc in result['tool_calls']], "web_search 도구가 호출되지 않았습니다"

    print("\n✅ TEST 2 PASSED")
    return result


async def test_complex_math():
    """복합 수학 연산 테스트"""
    print("\n" + "="*60)
    print("TEST 3: 복합 연산 (100을 3으로 나눈 값에 10을 더하기)")
    print("="*60)

    agent = PromptEngineeringMCPAgent()
    await agent.initialize()

    result = await agent.query("100을 3으로 나눈 값에 10을 더하면?")

    print(f"\n✅ 최종 답변: {result['answer']}")
    print(f"📊 반복: {result['iterations']}회")
    print(f"🔧 도구 호출: {len(result['tool_calls'])}번")

    if result['tool_calls']:
        print("\n📝 도구 호출 내역:")
        for i, tc in enumerate(result['tool_calls'], 1):
            print(f"   {i}. {tc['name']}({tc['args']})")

    # 이 테스트는 2번의 도구 호출이 필요: divide + add
    assert len(result['tool_calls']) >= 2, "복합 연산을 위한 충분한 도구 호출이 없습니다"

    print("\n✅ TEST 3 PASSED")
    return result


async def test_no_tool_needed():
    """도구가 필요 없는 질문 테스트"""
    print("\n" + "="*60)
    print("TEST 4: 일반 질문 (도구 불필요)")
    print("="*60)

    agent = PromptEngineeringMCPAgent()
    await agent.initialize()

    result = await agent.query("안녕하세요! 날씨가 좋네요.")

    print(f"\n✅ 최종 답변: {result['answer']}")
    print(f"📊 반복: {result['iterations']}회")
    print(f"🔧 도구 호출: {len(result['tool_calls'])}번")

    # 도구 호출이 없어야 정상
    assert len(result['tool_calls']) == 0, "불필요한 도구 호출이 발생했습니다"

    print("\n✅ TEST 4 PASSED")
    return result


async def test_detailed_steps():
    """실행 단계 상세 확인"""
    print("\n" + "="*60)
    print("TEST 5: 실행 단계 상세 분석")
    print("="*60)

    agent = PromptEngineeringMCPAgent()
    await agent.initialize()

    result = await agent.query("15에 7을 더하고 2를 빼면?")

    print(f"\n✅ 최종 답변: {result['answer']}")
    print(f"📊 반복: {result['iterations']}회")
    print(f"🔧 도구 호출: {len(result['tool_calls'])}번")

    print("\n📋 실행 단계:")
    for i, step in enumerate(result['steps'], 1):
        step_type = step['type']
        if step_type == 'user':
            print(f"   {i}. 👤 사용자: {step['content']}")
        elif step_type == 'assistant':
            content = step['content']
            if len(content) > 100:
                content = content[:100] + "..."
            print(f"   {i}. 🤖 어시스턴트: {content}")
        elif step_type == 'tool_call':
            print(f"   {i}. 🔧 도구 호출: {step['tool']}({step['args']})")
        elif step_type == 'tool_result':
            print(f"   {i}. ✅ 결과: {step['result']}")

    print("\n✅ TEST 5 PASSED")
    return result


async def main():
    """전체 테스트 실행"""
    print("\n" + "="*60)
    print("🧪 MCP Agent V2 (Prompt Engineering) 테스트 시작")
    print("="*60)

    tests = [
        ("기본 수학 연산", test_basic_math),
        ("웹 검색", test_search),
        ("복합 수학 연산", test_complex_math),
        ("일반 질문", test_no_tool_needed),
        ("실행 단계 상세", test_detailed_steps),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ TEST ERROR: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print("📊 테스트 결과")
    print("="*60)
    print(f"✅ 통과: {passed}/{len(tests)}")
    print(f"❌ 실패: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 모든 테스트 통과!")
    else:
        print(f"\n⚠️  {failed}개 테스트 실패")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
