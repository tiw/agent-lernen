"""
长期记忆管理 —— 基于 SQLite 的记忆持久化。
参考 Claude Code 的 session-memory 和 extractMemories 设计。
从零手写 AI Agent 课程 · 第 6 章
"""

import os
import json
import time
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


# ============================================================
# 记忆类型
# ============================================================

class MemoryType(Enum):
    """记忆类型枚举"""
    USER_PREF = "user_preference"       # 用户偏好
    PROJECT_INFO = "project_info"       # 项目信息
    TECH_DECISION = "tech_decision"     # 技术决策
    CODE_PATTERN = "code_pattern"       # 代码模式
    LESSON_LEARNED = "lesson_learned"   # 经验教训
    FACT = "fact"                       # 事实信息
    CUSTOM = "custom"                   # 自定义


@dataclass
class Memory:
    """单条记忆"""
    id: Optional[int] = None
    content: str = ''
    memory_type: MemoryType = MemoryType.FACT
    source: str = ''            # 来源（会话 ID、用户输入等）
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0       # 访问次数
    importance: float = 1.0     # 重要性评分（0-1）
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['memory_type'] = self.memory_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'Memory':
        d = d.copy()
        d['memory_type'] = MemoryType(d.get('memory_type', 'fact'))
        return cls(**d)

    @property
    def age_days(self) -> float:
        """记忆存在了多少天"""
        return (time.time() - self.created_at) / 86400

    @property
    def freshness_note(self) -> str:
        """新鲜度提示"""
        days = self.age_days
        if days < 1:
            return "just now"
        elif days < 7:
            return f"{int(days)} days ago"
        elif days < 30:
            return f"{int(days / 7)} weeks ago"
        else:
            return f"{int(days / 30)} months ago"


# ============================================================
# SQLite 记忆存储
# ============================================================

class MemoryStore:
    """
    基于 SQLite 的长期记忆存储。

    参考 Claude Code 的 session-memory 目录设计：
    - 每条记忆有类型、标签、重要性评分
    - 支持按类型、标签、时间范围查询
    - 自动维护访问计数和更新时间
    """

    def __init__(self, db_path: str = ':memory:'):
        """
        Args:
            db_path: SQLite 数据库路径（':memory:' 为内存数据库）
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'fact',
                source TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                importance REAL DEFAULT 1.0,
                metadata TEXT DEFAULT '{}'
            )
        ''')

        # 创建索引加速查询
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memory_type
            ON memories(memory_type)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memory_created
            ON memories(created_at)
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memory_importance
            ON memories(importance)
        ''')
        self.conn.commit()

    # --------------------------------------------------------
    # 写入
    # --------------------------------------------------------

    def add(self, memory: Memory) -> int:
        """
        添加一条记忆。

        Returns:
            新记忆的 ID
        """
        cursor = self.conn.execute('''
            INSERT INTO memories
                (content, memory_type, source, tags, created_at, updated_at,
                 access_count, importance, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            memory.content,
            memory.memory_type.value,
            memory.source,
            json.dumps(memory.tags, ensure_ascii=False),
            memory.created_at,
            memory.updated_at,
            memory.access_count,
            memory.importance,
            json.dumps(memory.metadata, ensure_ascii=False),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def add_many(self, memories: list[Memory]) -> list[int]:
        """批量添加记忆"""
        ids = []
        for m in memories:
            ids.append(self.add(m))
        return ids

    # --------------------------------------------------------
    # 更新
    # --------------------------------------------------------

    def update(self, memory_id: int, **kwargs) -> bool:
        """
        更新记忆。

        Args:
            memory_id: 记忆 ID
            **kwargs: 要更新的字段

        Returns:
            是否更新成功
        """
        if not kwargs:
            return False

        allowed_fields = {
            'content', 'memory_type', 'source', 'tags',
            'importance', 'metadata',
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        # 特殊处理 JSON 字段
        if 'tags' in updates:
            updates['tags'] = json.dumps(updates['tags'], ensure_ascii=False)
        if 'metadata' in updates:
            updates['metadata'] = json.dumps(
                updates['metadata'], ensure_ascii=False
            )
        if 'memory_type' in updates:
            updates['memory_type'] = updates['memory_type'].value

        updates['updated_at'] = time.time()

        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [memory_id]

        self.conn.execute(
            f'UPDATE memories SET {set_clause} WHERE id = ?',
            values,
        )
        self.conn.commit()
        return True

    def increment_access(self, memory_id: int) -> None:
        """增加访问计数"""
        self.conn.execute('''
            UPDATE memories
            SET access_count = access_count + 1,
                updated_at = ?
            WHERE id = ?
        ''', (time.time(), memory_id))
        self.conn.commit()

    # --------------------------------------------------------
    # 查询
    # --------------------------------------------------------

    def get(self, memory_id: int) -> Optional[Memory]:
        """根据 ID 获取记忆"""
        row = self.conn.execute(
            'SELECT * FROM memories WHERE id = ?', (memory_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_memory(row)

    def search(
        self,
        query: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[list[str]] = None,
        min_importance: float = 0.0,
        max_age_days: Optional[float] = None,
        limit: int = 20,
        sort_by: str = 'relevance',
    ) -> list[Memory]:
        """
        搜索记忆。

        Args:
            query: 关键词搜索（LIKE 匹配）
            memory_type: 按类型过滤
            tags: 按标签过滤（匹配任意一个）
            min_importance: 最低重要性
            max_age_days: 最大年龄（天）
            limit: 返回数量限制
            sort_by: 排序方式（'relevance'/'recent'/'importance'/'access'）

        Returns:
            匹配的记忆列表
        """
        conditions = []
        params = []

        if query:
            conditions.append('(content LIKE ? OR source LIKE ?)')
            params.extend([f'%{query}%', f'%{query}%'])

        if memory_type:
            conditions.append('memory_type = ?')
            params.append(memory_type.value)

        if tags:
            # SQLite JSON 数组包含检查
            tag_conditions = ' OR '.join(
                'json_each.value = ?' for _ in tags
            )
            conditions.append(
                f'EXISTS (SELECT 1 FROM json_each(tags) WHERE {tag_conditions})'
            )
            params.extend(tags)

        if min_importance > 0:
            conditions.append('importance >= ?')
            params.append(min_importance)

        if max_age_days is not None:
            cutoff = time.time() - (max_age_days * 86400)
            conditions.append('created_at >= ?')
            params.append(cutoff)

        where = ''
        if conditions:
            where = 'WHERE ' + ' AND '.join(conditions)

        # 排序
        sort_map = {
            'relevance': 'importance DESC, access_count DESC',
            'recent': 'created_at DESC',
            'importance': 'importance DESC',
            'access': 'access_count DESC',
        }
        order = sort_map.get(sort_by, sort_map['relevance'])

        rows = self.conn.execute(
            f'SELECT * FROM memories {where} ORDER BY {order} LIMIT ?',
            params + [limit],
        ).fetchall()

        return [self._row_to_memory(r) for r in rows]

    def get_recent(self, limit: int = 10) -> list[Memory]:
        """获取最近的记忆"""
        return self.search(limit=limit, sort_by='recent')

    def get_important(self, limit: int = 10) -> list[Memory]:
        """获取最重要的记忆"""
        return self.search(limit=limit, sort_by='importance')

    def get_all(self) -> list[Memory]:
        """获取所有记忆"""
        rows = self.conn.execute(
            'SELECT * FROM memories ORDER BY created_at DESC'
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    # --------------------------------------------------------
    # 删除 / 遗忘
    # --------------------------------------------------------

    def delete(self, memory_id: int) -> bool:
        """删除一条记忆"""
        cursor = self.conn.execute(
            'DELETE FROM memories WHERE id = ?', (memory_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def forget_old(
        self,
        max_age_days: float = 90,
        min_access_count: int = 0,
    ) -> int:
        """
        遗忘策略：删除过时且未被访问的记忆。

        Args:
            max_age_days: 超过此天数的记忆可能被删除
            min_access_count: 访问次数低于此值的记忆可能被删除

        Returns:
            删除的记忆数量
        """
        cutoff = time.time() - (max_age_days * 86400)
        cursor = self.conn.execute('''
            DELETE FROM memories
            WHERE created_at < ? AND access_count <= ?
        ''', (cutoff, min_access_count))
        self.conn.commit()
        return cursor.rowcount

    def count(self) -> int:
        """获取记忆总数"""
        row = self.conn.execute('SELECT COUNT(*) FROM memories').fetchone()
        return row[0]

    # --------------------------------------------------------
    # 内部方法
    # --------------------------------------------------------

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """将 SQLite 行转为 Memory 对象"""
        d = dict(row)
        d['tags'] = json.loads(d.get('tags', '[]'))
        d['metadata'] = json.loads(d.get('metadata', '{}'))
        d['memory_type'] = MemoryType(d.get('memory_type', 'fact'))
        return Memory(**d)

    def close(self):
        """关闭数据库连接"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ============================================================
# 记忆提取器
# ============================================================

class MemoryExtractor:
    """
    从对话中提取记忆。

    参考 Claude Code 的 extractMemories 服务。
    实际使用时需要接入 LLM API 进行智能提取。
    """

    def __init__(self, store: MemoryStore, llm_callback=None):
        """
        Args:
            store: 记忆存储
            llm_callback: LLM 回调函数，接收对话文本，返回提取的记忆列表
        """
        self.store = store
        self.llm_callback = llm_callback

    def extract_from_conversation(
        self,
        messages: list[dict],
        source: str = '',
    ) -> list[int]:
        """
        从对话中提取记忆。

        Args:
            messages: 对话消息列表
            source: 来源标识

        Returns:
            新添加的记忆 ID 列表
        """
        if not self.llm_callback:
            # 无 LLM 时回退到简单规则提取
            return self._rule_based_extract(messages, source)

        # 将对话转为文本
        text = '\n'.join(
            f"[{m.get('role', 'unknown')}] {m.get('content', '')}"
            for m in messages
        )

        # 调用 LLM 提取
        extracted = self.llm_callback(text)

        # 写入存储
        ids = []
        for item in extracted:
            memory = Memory(
                content=item.get('content', ''),
                memory_type=MemoryType(item.get('type', 'fact')),
                source=source,
                tags=item.get('tags', []),
                importance=item.get('importance', 0.5),
            )
            ids.append(self.store.add(memory))

        return ids

    def _rule_based_extract(
        self,
        messages: list[dict],
        source: str,
    ) -> list[int]:
        """基于规则的简单提取（无 LLM 时的回退）"""
        ids = []
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str) and len(content) > 50:
                # 简单的长内容提取
                memory = Memory(
                    content=content[:500],  # 截断
                    memory_type=MemoryType.FACT,
                    source=source,
                    importance=0.3,
                )
                ids.append(self.store.add(memory))
        return ids


# === 测试 ===
if __name__ == "__main__":
    print("=== 长期记忆测试 ===\n")

    # 测试 1: 创建记忆存储
    print("测试 1: 创建记忆存储（内存数据库）")
    store = MemoryStore(':memory:')
    print(f"  数据库：{store.db_path}")
    print(f"  初始数量：{store.count()}\n")

    # 测试 2: 添加记忆
    print("测试 2: 添加记忆")
    m1 = Memory(
        content="用户喜欢使用 VS Code 作为编辑器",
        memory_type=MemoryType.USER_PREF,
        source="chat_001",
        tags=["editor", "preference"],
        importance=0.8,
    )
    id1 = store.add(m1)
    print(f"  添加记忆 ID={id1}: {m1.content[:30]}...")

    m2 = Memory(
        content="项目使用 Python 3.9 版本",
        memory_type=MemoryType.PROJECT_INFO,
        source="chat_001",
        tags=["python", "version"],
        importance=0.6,
    )
    id2 = store.add(m2)
    print(f"  添加记忆 ID={id2}: {m2.content[:30]}...\n")

    # 测试 3: 查询记忆
    print("测试 3: 查询记忆")
    all_memories = store.get_all()
    print(f"  所有记忆：{len(all_memories)} 条")

    recent = store.get_recent(limit=5)
    print(f"  最近记忆：{len(recent)} 条")

    important = store.get_important(limit=5)
    print(f"  重要记忆：{len(important)} 条\n")

    # 测试 4: 搜索记忆
    print("测试 4: 搜索记忆")
    results = store.search(query="Python")
    print(f"  搜索 'Python': {len(results)} 条结果")
    for r in results:
        print(f"    - {r.content[:40]}...")

    results = store.search(memory_type=MemoryType.USER_PREF)
    print(f"  用户偏好：{len(results)} 条\n")

    # 测试 5: 访问计数
    print("测试 5: 访问计数")
    store.increment_access(id1)
    store.increment_access(id1)
    m1_updated = store.get(id1)
    print(f"  记忆 {id1} 访问次数：{m1_updated.access_count}\n")

    # 测试 6: 遗忘策略
    print("测试 6: 遗忘策略")
    deleted = store.forget_old(max_age_days=90, min_access_count=0)
    print(f"  删除过时记忆：{deleted} 条\n")

    # 测试 7: 记忆新鲜度
    print("测试 7: 记忆新鲜度")
    for m in all_memories:
        print(f"  {m.content[:20]}... - {m.freshness_note}")

    print("\n✅ 所有测试完成！")
