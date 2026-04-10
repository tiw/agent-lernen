"""
长期记忆管理 —— 基于 SQLite 的记忆持久化。
参考 Claude Code 的 session-memory 和 extractMemories 设计。
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
    USER_PREF = "user_preference"
    PROJECT_INFO = "project_info"
    TECH_DECISION = "tech_decision"
    CODE_PATTERN = "code_pattern"
    LESSON_LEARNED = "lesson_learned"
    FACT = "fact"
    CUSTOM = "custom"


@dataclass
class Memory:
    """单条记忆"""
    id: Optional[int] = None
    content: str = ''
    memory_type: MemoryType = MemoryType.FACT
    source: str = ''
    tags: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 1.0
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
    """

    def __init__(self, db_path: str = ':memory:'):
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

    def add(self, memory: Memory) -> int:
        """添加一条记忆。"""
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

    def add_many(self, memories: list) -> list:
        """批量添加记忆"""
        ids = []
        for m in memories:
            ids.append(self.add(m))
        return ids

    def update(self, memory_id: int, **kwargs) -> bool:
        """更新记忆。"""
        if not kwargs:
            return False

        allowed_fields = {
            'content', 'memory_type', 'source', 'tags',
            'importance', 'metadata',
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

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
        tags: Optional[list] = None,
        min_importance: float = 0.0,
        max_age_days: Optional[float] = None,
        limit: int = 20,
        sort_by: str = 'relevance',
    ) -> list:
        """搜索记忆。"""
        conditions = []
        params = []

        if query:
            conditions.append('(content LIKE ? OR source LIKE ?)')
            params.extend([f'%{query}%', f'%{query}%'])

        if memory_type:
            conditions.append('memory_type = ?')
            params.append(memory_type.value)

        if tags:
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

    def get_recent(self, limit: int = 10) -> list:
        """获取最近的记忆"""
        return self.search(limit=limit, sort_by='recent')

    def get_important(self, limit: int = 10) -> list:
        """获取最重要的记忆"""
        return self.search(limit=limit, sort_by='importance')

    def get_all(self) -> list:
        """获取所有记忆"""
        rows = self.conn.execute(
            'SELECT * FROM memories ORDER BY created_at DESC'
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

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
        """遗忘策略：删除过时且未被访问的记忆。"""
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
    """

    def __init__(self, store: MemoryStore, llm_callback=None):
        self.store = store
        self.llm_callback = llm_callback

    def extract_from_conversation(
        self,
        messages: list,
        source: str = '',
    ) -> list:
        """从对话中提取记忆。"""
        if not self.llm_callback:
            return self._rule_based_extract(messages, source)

        text = '\n'.join(
            f"[{m.get('role', 'unknown')}] {m.get('content', '')}"
            for m in messages
        )

        extracted = self.llm_callback(text)

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
        messages: list,
        source: str,
    ) -> list:
        """基于规则的简单提取（无 LLM 时的回退）"""
        ids = []
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str) and len(content) > 50:
                memory = Memory(
                    content=content[:500],
                    memory_type=MemoryType.FACT,
                    source=source,
                    importance=0.3,
                )
                ids.append(self.store.add(memory))
        return ids
