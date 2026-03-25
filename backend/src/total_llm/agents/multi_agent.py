"""
Multi-Agent System with LangGraph StateGraph
여러 Agent가 협업하는 고급 시스템
"""

from typing import List, Dict, Optional, Annotated, Literal, TypedDict
from pathlib import Path
import yaml
from operator import add


from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from total_llm.tools.mcp_client import get_mcp_tools


# Agent State 정의
class AgentState(TypedDict):
    """Multi-Agent 시스템의 상태"""
    messages: Annotated[List[BaseMessage], add]  # 메시지 기록
    current_agent: str  # 현재 활성 Agent
    task_type: str  # 작업 유형 (research, analysis, execution)
    context: Dict  # 공유 컨텍스트
    final_answer: Optional[str]  # 최종 답변
    tool_calls: List[Dict]  # 도구 호출 기록


class MultiAgentSystem:
    """
    Multi-Agent 협업 시스템

    Agents:
    - Researcher: 정보 수집 및 검색 전문
    - Analyzer: 데이터 분석 및 해석 전문
    - Executor: 실행 및 최종 답변 생성 전문
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Multi-Agent System

        Args:
            config_path: Path to config.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.llm_config = self.config['llm']
        self.workflow = None
        self.llm = None
        self.tools: List[BaseTool] = []
        self.memory = MemorySaver()  # 대화 기록 저장

        print("✅ Multi-Agent System initialized")

    async def initialize(self, additional_tools: Optional[List[BaseTool]] = None):
        """
        시스템 초기화 및 Agent 그래프 생성

        Args:
            additional_tools: MCP 도구 외 추가 도구 (예: RAG 도구)
        """
        # MCP 도구 로드
        self.tools = await get_mcp_tools()

        # 추가 도구 병합
        if additional_tools:
            self.tools.extend(additional_tools)

        # LLM 초기화 (vLLM with OpenAI compatibility)
        self.llm = ChatOpenAI(
            base_url=self.llm_config['base_url'],
            model=self.llm_config['model_name'],
            temperature=self.llm_config['temperature'],
            max_tokens=self.llm_config['max_tokens'],
            api_key="EMPTY"  # vLLM doesn't need API key
        )

        # StateGraph 생성
        workflow = StateGraph(AgentState)

        # Node 추가
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("researcher", self._researcher_node)
        workflow.add_node("analyzer", self._analyzer_node)
        workflow.add_node("executor", self._executor_node)

        # Entry Point
        workflow.set_entry_point("planner")

        # Conditional Edges
        workflow.add_conditional_edges(
            "planner",
            self._route_task,
            {
                "research": "researcher",
                "analysis": "analyzer",
                "execution": "executor",
                "end": END
            }
        )

        workflow.add_edge("researcher", "analyzer")
        workflow.add_edge("analyzer", "executor")
        workflow.add_edge("executor", END)

        # Compile with memory
        self.workflow = workflow.compile(checkpointer=self.memory)

        print(f"✅ Multi-Agent Workflow created with {len(self.tools)} tools")
        print("   Agents: Planner → Researcher → Analyzer → Executor")

    def _planner_node(self, state: AgentState) -> AgentState:
        """
        Planner Agent: 작업 분석 및 라우팅 결정
        """
        messages = state["messages"]
        user_query = messages[-1].content if messages else ""

        # 작업 유형 판별
        task_type = "research"  # 기본값

        # 키워드 기반 판별
        if any(kw in user_query.lower() for kw in ["검색", "찾아", "search", "알려줘", "정보"]):
            task_type = "research"
        elif any(kw in user_query.lower() for kw in ["분석", "analyze", "계산", "평가"]):
            task_type = "analysis"
        elif any(kw in user_query.lower() for kw in ["실행", "해줘", "만들어", "생성"]):
            task_type = "execution"

        planning_msg = AIMessage(content=f"[Planner] 작업 유형: {task_type}")

        return {
            **state,
            "messages": [planning_msg],
            "current_agent": "planner",
            "task_type": task_type,
            "context": {"original_query": user_query}
        }

    def _route_task(self, state: AgentState) -> Literal["research", "analysis", "execution", "end"]:
        """
        조건부 라우팅: 작업 유형에 따라 다음 Agent 결정
        """
        task_type = state.get("task_type", "research")

        # 간단한 질문은 바로 실행
        messages = state["messages"]
        user_query = messages[0].content if messages else ""

        if len(user_query) < 10:
            return "execution"

        return task_type

    async def _researcher_node(self, state: AgentState) -> AgentState:
        """
        Researcher Agent: 정보 수집 및 검색
        """
        messages = state["messages"]
        context = state.get("context", {})
        original_query = context.get("original_query", "")

        # Researcher 전용 도구 필터링 (search 관련)
        research_tools = [t for t in self.tools if "search" in t.name.lower()]

        if not research_tools:
            research_tools = self.tools  # 모든 도구 사용

        # Researcher Agent 생성
        researcher_agent = create_react_agent(
            self.llm,
            research_tools
        )

        # Agent 실행
        result = await researcher_agent.ainvoke({
            "messages": [HumanMessage(content=original_query)]
        })

        # 결과에서 정보 추출
        final_msg = result["messages"][-1]
        research_result = final_msg.content if isinstance(final_msg, AIMessage) else ""

        research_msg = AIMessage(content=f"[Researcher] {research_result}")

        # 도구 호출 기록
        tool_calls = []
        for msg in result["messages"]:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "agent": "researcher",
                        "name": tc["name"],
                        "args": tc.get("args", {})
                    })

        return {
            **state,
            "messages": [research_msg],
            "current_agent": "researcher",
            "context": {**context, "research_result": research_result},
            "tool_calls": state.get("tool_calls", []) + tool_calls
        }

    async def _analyzer_node(self, state: AgentState) -> AgentState:
        """
        Analyzer Agent: 데이터 분석 및 해석
        """
        messages = state["messages"]
        context = state.get("context", {})
        research_result = context.get("research_result", "")
        original_query = context.get("original_query", "")

        # Analyzer 전용 도구 (수학 계산 등)
        analysis_tools = [t for t in self.tools if any(kw in t.name.lower() for kw in ["add", "subtract", "multiply", "divide"])]

        if not analysis_tools:
            analysis_tools = self.tools

        # Analyzer Agent 생성
        analyzer_agent = create_react_agent(
            self.llm,
            analysis_tools
        )

        # Agent 실행
        result = await analyzer_agent.ainvoke({
            "messages": [HumanMessage(content="수집된 정보를 분석해주세요")]
        })

        # 결과 추출
        final_msg = result["messages"][-1]
        analysis_result = final_msg.content if isinstance(final_msg, AIMessage) else ""

        analysis_msg = AIMessage(content=f"[Analyzer] {analysis_result}")

        # 도구 호출 기록
        tool_calls = []
        for msg in result["messages"]:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "agent": "analyzer",
                        "name": tc["name"],
                        "args": tc.get("args", {})
                    })

        return {
            **state,
            "messages": [analysis_msg],
            "current_agent": "analyzer",
            "context": {**context, "analysis_result": analysis_result},
            "tool_calls": state.get("tool_calls", []) + tool_calls
        }

    async def _executor_node(self, state: AgentState) -> AgentState:
        """
        Executor Agent: 최종 답변 생성
        """
        context = state.get("context", {})
        original_query = context.get("original_query", "")
        research_result = context.get("research_result", "")
        analysis_result = context.get("analysis_result", "")

        # Executor는 도구를 사용하지 않고 최종 답변만 생성
        executor_prompt = f"""당신은 최종 답변 생성 전문 Executor입니다.

원래 질문:
{original_query}

Researcher 수집 정보:
{research_result}

Analyzer 분석 결과:
{analysis_result}

위 정보를 종합하여 사용자에게 명확하고 완전한 답변을 생성하세요.
답변은 한국어로 작성하세요."""

        result = await self.llm.ainvoke([
            SystemMessage(content=executor_prompt),
            HumanMessage(content="최종 답변을 생성해주세요")
        ])

        final_answer = result.content
        executor_msg = AIMessage(content=f"[Executor] {final_answer}")

        return {
            **state,
            "messages": [executor_msg],
            "current_agent": "executor",
            "final_answer": final_answer
        }

    async def query(self, user_input: str, thread_id: str = "default") -> Dict:
        """
        사용자 쿼리 처리 (Multi-Agent 협업)

        Args:
            user_input: 사용자 입력
            thread_id: 대화 스레드 ID (메모리 관리용)

        Returns:
            응답 딕셔너리 (answer, steps, agents_used, tool_calls)
        """
        if self.workflow is None:
            await self.initialize()

        # 초기 상태
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "current_agent": "",
            "task_type": "",
            "context": {},
            "final_answer": None,
            "tool_calls": []
        }

        # Workflow 실행 (메모리 포함)
        config = {"configurable": {"thread_id": thread_id}}
        final_state = await self.workflow.ainvoke(initial_state, config)

        # 결과 파싱
        messages = final_state["messages"]
        final_answer = final_state.get("final_answer", "답변을 생성할 수 없습니다.")
        tool_calls = final_state.get("tool_calls", [])

        # Agent 실행 단계 추출
        steps = []
        agents_used = []

        for msg in messages:
            if isinstance(msg, AIMessage):
                content = msg.content
                if content.startswith("["):
                    agent_name = content.split("]")[0][1:]
                    agents_used.append(agent_name)
                    steps.append({
                        "agent": agent_name,
                        "message": content.split("]", 1)[1].strip() if "]" in content else content
                    })

        return {
            "answer": final_answer,
            "steps": steps,
            "agents_used": list(set(agents_used)),  # 중복 제거
            "tool_calls": tool_calls,
            "thread_id": thread_id
        }


# 글로벌 인스턴스
_multi_agent: Optional[MultiAgentSystem] = None


async def get_multi_agent() -> MultiAgentSystem:
    """글로벌 Multi-Agent 인스턴스 반환"""
    global _multi_agent
    if _multi_agent is None:
        _multi_agent = MultiAgentSystem()
        await _multi_agent.initialize()
    return _multi_agent


if __name__ == "__main__":
    """테스트용"""
    import asyncio

    async def test():
        system = MultiAgentSystem()
        await system.initialize()

        # 테스트 쿼리
        queries = [
            "Python에 대해 검색하고 주요 특징 3가지를 알려줘",
            "100을 3으로 나눈 값에 20을 곱하면?",
            "웹 검색으로 AI agent에 대해 찾아서 요약해줘"
        ]

        for i, query in enumerate(queries):
            print(f"\n{'='*60}")
            print(f"🔵 질문 {i+1}: {query}")
            print(f"{'='*60}")

            result = await system.query(query, thread_id=f"test_{i}")

            print(f"\n✅ 최종 답변:")
            print(f"{result['answer']}")

            print(f"\n📊 사용된 Agents: {', '.join(result['agents_used'])}")
            print(f"🔧 도구 호출: {len(result['tool_calls'])}번")

            if result['tool_calls']:
                for tc in result['tool_calls']:
                    print(f"   - [{tc['agent']}] {tc['name']}: {tc['args']}")

            print(f"\n📝 실행 단계:")
            for step in result['steps']:
                print(f"   [{step['agent']}] {step['message'][:100]}...")

    asyncio.run(test())
