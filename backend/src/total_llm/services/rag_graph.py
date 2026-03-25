from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from total_llm.retrievers.adaptive_retriever import AdaptiveRetriever


class RAGState(TypedDict, total=False):
    query: str
    top_k: int
    filter_metadata: Dict[str, str]
    complexity: Dict[str, Any]
    strategy: str
    documents: List[Dict[str, Any]]
    attempts: int
    error: Optional[str]


class AdaptiveRAGGraph:
    def __init__(self, retriever: AdaptiveRetriever):
        self.retriever = retriever
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(RAGState)

        builder.add_node("classify_query", self.classify_query)
        builder.add_node("retrieve_simple", self.retrieve_simple)
        builder.add_node("retrieve_hybrid", self.retrieve_hybrid)
        builder.add_node("retrieve_complex", self.retrieve_complex)
        builder.add_node("quality_gate", self.quality_gate)
        builder.add_node("format_output", self.format_output)

        builder.set_entry_point("classify_query")

        builder.add_conditional_edges(
            "classify_query",
            self._route_by_complexity,
            {
                "retrieve_simple": "retrieve_simple",
                "retrieve_hybrid": "retrieve_hybrid",
                "retrieve_complex": "retrieve_complex",
            },
        )

        builder.add_edge("retrieve_simple", "quality_gate")
        builder.add_edge("retrieve_hybrid", "quality_gate")
        builder.add_edge("retrieve_complex", "quality_gate")

        builder.add_conditional_edges(
            "quality_gate",
            self._route_by_quality,
            {
                "retrieve_simple": "retrieve_simple",
                "retrieve_hybrid": "retrieve_hybrid",
                "retrieve_complex": "retrieve_complex",
                "format_output": "format_output",
            },
        )

        builder.add_edge("format_output", END)
        return builder.compile()

    async def classify_query(self, state: RAGState) -> RAGState:
        query = state.get("query", "")
        complexity = self.retriever.analyzer.analyze(query)
        category = complexity.get("category", "simple")
        strategy = {
            "simple": "retrieve_simple",
            "hybrid": "retrieve_hybrid",
            "complex": "retrieve_complex",
        }.get(category, "retrieve_simple")

        return {
            **state,
            "complexity": complexity,
            "strategy": strategy,
            "attempts": int(state.get("attempts", 0)),
            "error": None,
        }

    async def retrieve_simple(self, state: RAGState) -> RAGState:
        try:
            top_k = int(state.get("top_k", self.retriever.adaptive_config.simple_k))
            docs = await self.retriever._simple_search(state.get("query", ""), top_k)
            return {**state, "documents": docs, "strategy": "simple_vector", "error": None}
        except Exception as exc:
            return {**state, "documents": [], "error": str(exc)}

    async def retrieve_hybrid(self, state: RAGState) -> RAGState:
        try:
            top_k = int(state.get("top_k", self.retriever.adaptive_config.hybrid_k))
            docs = await self.retriever._hybrid_search(state.get("query", ""), top_k)
            return {**state, "documents": docs, "strategy": "hybrid_search", "error": None}
        except Exception as exc:
            return {**state, "documents": [], "error": str(exc)}

    async def retrieve_complex(self, state: RAGState) -> RAGState:
        try:
            top_k = int(state.get("top_k", self.retriever.adaptive_config.complex_k))
            docs = await self.retriever._multi_query_search(state.get("query", ""), top_k)
            return {**state, "documents": docs, "strategy": "multi_query", "error": None}
        except Exception as exc:
            return {**state, "documents": [], "error": str(exc)}

    async def quality_gate(self, state: RAGState) -> RAGState:
        attempts = int(state.get("attempts", 0)) + 1
        return {**state, "attempts": attempts}

    async def format_output(self, state: RAGState) -> RAGState:
        documents = state.get("documents", [])
        filter_metadata = state.get("filter_metadata") or {}

        if filter_metadata:
            filtered = []
            for doc in documents:
                metadata = doc.get("metadata", {})
                matched = all(metadata.get(k) == v for k, v in filter_metadata.items())
                if matched:
                    filtered.append(doc)
            documents = filtered

        top_k = int(state.get("top_k", len(documents) or 0))
        return {**state, "documents": documents[:top_k]}

    def _route_by_complexity(self, state: RAGState) -> str:
        return state.get("strategy", "retrieve_simple")

    def _route_by_quality(self, state: RAGState) -> str:
        documents = state.get("documents", [])
        attempts = int(state.get("attempts", 0))

        if documents:
            return "format_output"

        if attempts <= 1:
            strategy = state.get("strategy")
            if strategy == "simple_vector":
                return "retrieve_hybrid"
            if strategy == "hybrid_search":
                return "retrieve_complex"
            return "retrieve_complex"

        return "format_output"

    async def ainvoke(self, query: str, top_k: int = 5, filter_metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        initial_state: RAGState = {
            "query": query,
            "top_k": top_k,
            "filter_metadata": filter_metadata or {},
            "documents": [],
            "attempts": 0,
        }
        final_state = await self.graph.ainvoke(initial_state)
        return {
            "query": query,
            "complexity": final_state.get("complexity", {}),
            "strategy": final_state.get("strategy", "unknown"),
            "documents": final_state.get("documents", []),
            "k": top_k,
            "error": final_state.get("error"),
        }
