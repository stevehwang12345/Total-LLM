from __future__ import annotations

import asyncio
import pickle
import re
from pathlib import Path
from typing import Dict, List, Tuple

from rank_bm25 import BM25Okapi


class BM25Indexer:
    def __init__(self, cache_path: str | None = None):
        self.bm25 = None
        self.documents: List[Dict] = []
        self.doc_ids: List[str] = []
        self.cache_path = cache_path or "data/bm25_index.pkl"
        if Path(self.cache_path).exists():
            self.load_index_sync()

    def tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^가-힣a-z0-9\s]", " ", text)
        return text.split()

    def build_index_sync(self, documents: List[Dict]) -> None:
        self.documents = documents
        self.doc_ids = [str(doc["id"]) for doc in documents]
        tokenized_docs = [self.tokenize(doc.get("text", "")) for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        self.save_index_sync()

    async def build_index(self, documents: List[Dict]) -> None:
        await asyncio.to_thread(self.build_index_sync, documents)

    def add_documents_sync(self, new_documents: List[Dict]) -> None:
        self.documents.extend(new_documents)
        self.build_index_sync(self.documents)

    async def add_documents(self, new_documents: List[Dict]) -> None:
        await asyncio.to_thread(self.add_documents_sync, new_documents)

    def search_sync(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        if self.bm25 is None:
            return []
        query_tokens = self.tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        doc_scores = list(zip(self.doc_ids, scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        return [(str(doc_id), float(score)) for doc_id, score in doc_scores[:k]]

    async def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        return await asyncio.to_thread(self.search_sync, query, k)

    def save_index_sync(self) -> None:
        cache_dir = Path(self.cache_path).parent
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "wb") as f:
            pickle.dump(
                {
                    "bm25": self.bm25,
                    "documents": self.documents,
                    "doc_ids": self.doc_ids,
                },
                f,
            )

    async def save_index(self) -> None:
        await asyncio.to_thread(self.save_index_sync)

    def load_index_sync(self) -> None:
        try:
            with open(self.cache_path, "rb") as f:
                data = pickle.load(f)
            self.bm25 = data.get("bm25")
            self.documents = data.get("documents", [])
            self.doc_ids = [str(x) for x in data.get("doc_ids", [])]
        except Exception:
            self.bm25 = None
            self.documents = []
            self.doc_ids = []

    async def load_index(self) -> None:
        await asyncio.to_thread(self.load_index_sync)
