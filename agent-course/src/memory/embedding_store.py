"""
Embedding 语义检索 —— 用向量实现记忆召回。
参考 Claude Code 的记忆检索设计思路。
"""

import os
import json
import math
import time
import sqlite3
from typing import Optional
from dataclasses import dataclass

from .long_term import Memory, MemoryStore, MemoryType


# ============================================================
# Embedding 提供者
# ============================================================

class EmbeddingProvider:
    """Embedding 提供者的抽象接口。"""

    def embed(self, text: str) -> list:
        """将文本转为向量"""
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        """向量维度"""
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """
    基于哈希的简单 Embedding（无外部依赖的回退方案）。
    """

    def __init__(self, dimension: int = 128):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list:
        import hashlib
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()

        vector = []
        for i in range(self._dimension):
            chunk = h[i * 2:(i + 1) * 2]
            val = int(chunk, 16) / 255.0
            vector.append(val * 2 - 1)

        return vector


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI Embedding API 提供者。
    """

    def __init__(self, model: str = 'text-embedding-3-small'):
        self.model = model
        self._dimension = 1536 if 'small' in model else 3072

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list:
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"OpenAI Embedding failed: {e}, falling back to hash")
            return HashEmbeddingProvider(self._dimension).embed(text)


# ============================================================
# 余弦相似度
# ============================================================

def cosine_similarity(a: list, b: list) -> float:
    """
    计算两个向量的余弦相似度。
    """
    if len(a) != len(b):
        raise ValueError(f"Dimension mismatch: {len(a)} vs {len(b)}")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


# ============================================================
# Embedding 记忆存储
# ============================================================

class EmbeddingMemoryStore:
    """
    带语义检索的记忆存储。
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        db_path: str = ':memory:',
    ):
        self.store = store or MemoryStore(db_path)
        self.embedder = embedding_provider or HashEmbeddingProvider()

        # 内存中的向量索引：{memory_id: vector}
        self._vectors: dict = {}

        # 加载已有记忆的向量
        self._load_existing_vectors()

    def _load_existing_vectors(self):
        """为已有记忆生成向量"""
        for memory in self.store.get_all():
            if memory.id is not None:
                self._vectors[memory.id] = self.embedder.embed(memory.content)

    def add(self, memory: Memory) -> int:
        """添加记忆并自动生成 Embedding"""
        memory_id = self.store.add(memory)
        memory.id = memory_id
        self._vectors[memory_id] = self.embedder.embed(memory.content)
        return memory_id

    def add_many(self, memories: list) -> list:
        """批量添加"""
        ids = self.store.add_many(memories)
        for mid, m in zip(ids, memories):
            m.id = mid
            self._vectors[mid] = self.embedder.embed(m.content)
        return ids

    def search_semantic(
        self,
        query: str,
        top_k: int = 10,
        min_similarity: float = 0.0,
        memory_type: Optional[MemoryType] = None,
    ) -> list:
        """语义搜索记忆。"""
        query_vector = self.embedder.embed(query)

        candidates = self.store.get_all()
        if memory_type:
            candidates = [m for m in candidates if m.memory_type == memory_type]

        scored = []
        for memory in candidates:
            if memory.id not in self._vectors:
                continue
            sim = cosine_similarity(query_vector, self._vectors[memory.id])
            if sim >= min_similarity:
                scored.append((memory, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search_hybrid(
        self,
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list:
        """混合搜索：语义 + 关键词。"""
        semantic_results = self.search_semantic(query, top_k=top_k * 2)
        semantic_scores = {m.id: s for m, s in semantic_results}

        keyword_results = self.store.search(query, limit=top_k * 2)
        keyword_scores = {}
        if keyword_results:
            max_rank = len(keyword_results)
            for rank, m in enumerate(keyword_results):
                if m.id is not None:
                    keyword_scores[m.id] = 1.0 - (rank / max_rank)

        all_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())
        combined = []
        for mid in all_ids:
            sem = semantic_scores.get(mid, 0.0)
            kw = keyword_scores.get(mid, 0.0)
            score = semantic_weight * sem + keyword_weight * kw
            memory = self.store.get(mid)
            if memory:
                combined.append((memory, score))

        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:top_k]

    def update(self, memory_id: int, **kwargs) -> bool:
        """更新记忆并重新生成 Embedding"""
        success = self.store.update(memory_id, **kwargs)
        if success and 'content' in kwargs:
            self._vectors[memory_id] = self.embedder.embed(kwargs['content'])
        return success

    def delete(self, memory_id: int) -> bool:
        """删除记忆及其向量"""
        success = self.store.delete(memory_id)
        if success:
            self._vectors.pop(memory_id, None)
        return success

    def count(self) -> int:
        return self.store.count()

    def get_status(self) -> dict:
        return {
            'total_memories': self.count(),
            'vector_count': len(self._vectors),
            'embedding_dimension': self.embedder.dimension,
            'embedding_type': type(self.embedder).__name__,
        }

    def close(self):
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
