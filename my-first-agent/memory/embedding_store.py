"""
Embedding 语义检索 —— 用向量实现记忆召回。
参考 Claude Code 的记忆检索设计思路。
从零手写 AI Agent 课程 · 第 6 章
"""

import os
import json
import math
import time
import sqlite3
from typing import Optional
from dataclasses import dataclass, field

# 支持直接运行和模块导入两种模式
import sys
if __name__ == "__main__":
    # 直接运行时，导入 long_term 模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("long_term", os.path.join(os.path.dirname(__file__), "long_term.py"))
    long_term = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(long_term)
    Memory = long_term.Memory
    MemoryStore = long_term.MemoryStore
    MemoryType = long_term.MemoryType
else:
    from .long_term import Memory, MemoryStore, MemoryType


# ============================================================
# Embedding 提供者
# ============================================================

class EmbeddingProvider:
    """
    Embedding 提供者的抽象接口。

    支持多种后端：
    - OpenAI Embedding API
    - 本地 sentence-transformers
    - 简单哈希回退
    """

    def embed(self, text: str) -> list[float]:
        """将文本转为向量"""
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        """向量维度"""
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """
    基于哈希的简单 Embedding（无外部依赖的回退方案）。

    将文本哈希为固定维度的向量。虽然不具备语义理解能力，
    但可以用于演示和测试。
    """

    def __init__(self, dimension: int = 128):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        import hashlib
        
        # SHA256 产生 64 个十六进制字符 = 32 字节 = 256 bits
        # 每个字符可以产生一个 0-15 的值
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()
        
        # 使用多个哈希函数来扩展维度
        vector = []
        for i in range(self._dimension):
            # 使用不同的种子产生不同的哈希
            seed_hash = hashlib.sha256(f"{text}:{i}".encode('utf-8')).hexdigest()
            # 取前两个字符产生一个浮点数
            val = int(seed_hash[:2], 16) / 255.0
            vector.append(val * 2 - 1)  # 归一化到 [-1, 1]
        
        return vector


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI Embedding API 提供者。

    需要设置 OPENAI_API_KEY 环境变量。
    """

    def __init__(self, model: str = 'text-embedding-3-small'):
        self.model = model
        self._dimension = 1536 if 'small' in model else 3072

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
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

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    计算两个向量的余弦相似度。

    Returns:
        相似度 [-1, 1]，1 表示完全相同
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
# 向量存储
# ============================================================

@dataclass
class EmbeddingRecord:
    """向量记录"""
    memory_id: int
    embedding: list[float]
    created_at: float = field(default_factory=time.time)


class EmbeddingStore:
    """
    基于 SQLite 的向量存储。

    使用余弦相似度进行语义检索。
    对于大规模应用，建议使用专门的向量数据库（如 Chroma、Pinecone）。
    """

    def __init__(
        self,
        db_path: str = ':memory:',
        provider: Optional[EmbeddingProvider] = None,
    ):
        """
        Args:
            db_path: SQLite 数据库路径
            provider: Embedding 提供者（默认使用 HashEmbeddingProvider）
        """
        self.db_path = db_path
        self.provider = provider or HashEmbeddingProvider(dimension=128)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                memory_id INTEGER PRIMARY KEY,
                embedding TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        ''')
        self.conn.commit()

    def add(self, memory_id: int, text: str) -> None:
        """
        添加记忆的向量。

        Args:
            memory_id: 记忆 ID
            text: 要嵌入的文本（通常是记忆内容）
        """
        embedding = self.provider.embed(text)
        embedding_json = json.dumps(embedding)

        self.conn.execute('''
            INSERT OR REPLACE INTO embeddings
                (memory_id, embedding, created_at)
            VALUES (?, ?, ?)
        ''', (memory_id, embedding_json, time.time()))
        self.conn.commit()

    def add_many(self, memories: list[Memory]) -> None:
        """批量添加记忆的向量"""
        for m in memories:
            self.add(m.id, m.content)

    def search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[tuple[int, float]]:
        """
        语义搜索记忆。

        Args:
            query: 搜索查询
            limit: 返回数量限制
            min_similarity: 最低相似度阈值

        Returns:
            [(memory_id, similarity), ...] 列表
        """
        query_embedding = self.provider.embed(query)

        # 获取所有向量
        rows = self.conn.execute(
            'SELECT memory_id, embedding FROM embeddings'
        ).fetchall()

        # 计算相似度
        results = []
        for row in rows:
            memory_id = row['memory_id']
            embedding = json.loads(row['embedding'])
            similarity = cosine_similarity(query_embedding, embedding)

            if similarity >= min_similarity:
                results.append((memory_id, similarity))

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]

    def get(self, memory_id: int) -> Optional[list[float]]:
        """获取记忆的向量"""
        row = self.conn.execute(
            'SELECT embedding FROM embeddings WHERE memory_id = ?',
            (memory_id,)
        ).fetchone()
        if not row:
            return None
        return json.loads(row['embedding'])

    def delete(self, memory_id: int) -> bool:
        """删除记忆的向量"""
        cursor = self.conn.execute(
            'DELETE FROM embeddings WHERE memory_id = ?',
            (memory_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        """获取向量总数"""
        row = self.conn.execute(
            'SELECT COUNT(*) FROM embeddings'
        ).fetchone()
        return row[0]

    def close(self):
        """关闭数据库连接"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ============================================================
# 语义检索记忆系统
# ============================================================

class SemanticMemorySearch:
    """
    结合 SQLite 和 Embedding 的语义记忆搜索。

    提供两种搜索模式：
    1. 关键词搜索（LIKE 匹配）
    2. 语义搜索（向量相似度）
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        embedding_store: EmbeddingStore,
    ):
        """
        Args:
            memory_store: 记忆存储
            embedding_store: 向量存储
        """
        self.memory_store = memory_store
        self.embedding_store = embedding_store

    def search(
        self,
        query: str,
        mode: str = 'semantic',
        limit: int = 10,
    ) -> list[Memory]:
        """
        搜索记忆。

        Args:
            query: 搜索查询
            mode: 搜索模式（'semantic'/'keyword'/'hybrid'）
            limit: 返回数量限制

        Returns:
            匹配的记忆列表
        """
        if mode == 'keyword':
            return self.memory_store.search(query=query, limit=limit)

        if mode == 'semantic':
            return self._semantic_search(query, limit)

        if mode == 'hybrid':
            return self._hybrid_search(query, limit)

        return []

    def _semantic_search(self, query: str, limit: int) -> list[Memory]:
        """纯语义搜索"""
        results = self.embedding_store.search(query, limit=limit * 2)

        memories = []
        for memory_id, similarity in results:
            memory = self.memory_store.get(memory_id)
            if memory:
                self.memory_store.increment_access(memory_id)
                memories.append(memory)

        return memories[:limit]

    def _hybrid_search(self, query: str, limit: int) -> list[Memory]:
        """混合搜索（关键词 + 语义）"""
        # 关键词搜索
        keyword_results = self.memory_store.search(query=query, limit=limit)

        # 语义搜索
        semantic_results = self._semantic_search(query, limit=limit)

        # 合并去重
        seen_ids = set()
        merged = []
        for m in keyword_results + semantic_results:
            if m.id and m.id not in seen_ids:
                seen_ids.add(m.id)
                merged.append(m)

        return merged[:limit]


# === 测试 ===
if __name__ == "__main__":
    print("=== Embedding 语义检索测试 ===\n")

    # 测试 1: 创建存储
    print("测试 1: 创建存储")
    memory_store = MemoryStore(':memory:')
    embedding_store = EmbeddingStore(':memory:')
    print(f"  记忆存储：{memory_store.db_path}")
    print(f"  向量存储：{embedding_store.db_path}")
    print(f"  向量维度：{embedding_store.provider.dimension}\n")

    # 测试 2: 添加记忆和向量
    print("测试 2: 添加记忆和向量")
    memories = [
        Memory(
            content="用户喜欢使用 Python 编程",
            memory_type=MemoryType.USER_PREF,
            source="test",
            importance=0.8,
        ),
        Memory(
            content="项目使用 FastAPI 框架",
            memory_type=MemoryType.PROJECT_INFO,
            source="test",
            importance=0.7,
        ),
        Memory(
            content="数据库使用 PostgreSQL",
            memory_type=MemoryType.PROJECT_INFO,
            source="test",
            importance=0.6,
        ),
    ]

    for m in memories:
        id = memory_store.add(m)
        embedding_store.add(id, m.content)
        print(f"  添加记忆 ID={id}: {m.content[:20]}...")

    print(f"  记忆总数：{memory_store.count()}")
    print(f"  向量总数：{embedding_store.count()}\n")

    # 测试 3: 语义搜索
    print("测试 3: 语义搜索")
    search = SemanticMemorySearch(memory_store, embedding_store)

    # 搜索"编程"
    results = search.search("编程", mode='semantic', limit=5)
    print(f"  搜索 '编程': {len(results)} 条结果")
    for r in results:
        print(f"    - {r.content}")

    # 搜索"框架"
    results = search.search("框架", mode='semantic', limit=5)
    print(f"\n  搜索 '框架': {len(results)} 条结果")
    for r in results:
        print(f"    - {r.content}")

    # 搜索"数据库"
    results = search.search("数据库", mode='semantic', limit=5)
    print(f"\n  搜索 '数据库': {len(results)} 条结果")
    for r in results:
        print(f"    - {r.content}")

    print("\n✅ 所有测试完成！")
