# ADR-005: Agent Memory 服务设计

**状态**: Accepted
**日期**: 2026-04-07
**来源**: critical-review-response.md 问题6

---

## 背景

Agent Memory 是核心功能但原设计缺失。需要补充完整的数据模型和服务设计。

---

## 内存类型

| 类型 | 描述 | TTL |
|------|------|-----|
| EpisodicMemory | 具体事件/对话记录 | 30天 |
| SemanticMemory | 知识、概念、事实 | 不过期 |
| ProceduralMemory | 操作流程、最佳实践 | 3个月更新 |
| WorkingMemory | 当前对话上下文 | 30分钟 |

---

## 数据模型

```yaml
memory_types:
  - name: "MemoryFragment"
    attributes:
      - fragment_id: uuid (identifier)
      - memory_type: MemoryType (required)
      - content: string (文本/结构化数据)
      - embedding: vector (1536维)
      - importance_score: float [0.0, 1.0]
      - access_count: integer (default: 0)
      - last_accessed: datetime
      - created_at: datetime
      - expires_at: datetime
      - agent_id: string
      - session_id: string
      - source_entity_id: string
      - source_entity_type: string
    relations:
      - related_to: MemoryFragment (0..*)
      - derived_from: MemoryFragment (0..1)
```

---

## 服务接口

```python
class AgentMemoryService:
    async def store(
        self,
        agent_id: str,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        session_id: str | None = None,
        entity_refs: list[tuple[str, str]] | None = None
    ) -> str:
        """存储记忆片段"""

    async def retrieve(self, query: MemoryQuery) -> list[MemoryFragment]:
        """检索记忆（语义+关联）"""

    async def retrieve_with_context(
        self,
        agent_id: str,
        text_query: str,
        context_depth: int = 2
    ) -> AsyncIterator[MemoryFragment]:
        """带上下文的记忆检索"""

    async def compress(self, agent_id: str, memory_type: str):
        """记忆压缩（相似合并）"""
```

---

## 淘汰策略

| 内存类型 | 策略 | 规则 |
|----------|------|------|
| EpisodicMemory | hybrid | TTL(30天) + 重要性阈值(0.3) + LRU(10000) |
| WorkingMemory | ttl_only | 30分钟 |
| SemanticMemory | importance_only | 重要性 > 0.5 |

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Memory 架构                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐     │
│  │   Agent A   │      │   Agent B   │      │   Agent C   │     │
│  │  (隔离边界)  │      │  (隔离边界)  │      │  (隔离边界)  │     │
│  └──────┬──────┘      └──────┬──────┘      └──────┬──────┘     │
│         └────────────────────┼────────────────────┘             │
│                    ┌─────────┴─────────┐                        │
│                    │ AgentMemoryService │                        │
│                    └─────────┬─────────┘                        │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐     │
│  │    FAISS    │      │   SQLite    │      │  NetworkX   │     │
│  │  (向量索引)  │      │   (图存储)   │      │  (关系图)   │     │
│  └─────────────┘      └─────────────┘      └─────────────┘     │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │  KnowledgeGraph │                          │
│                    │   (共享知识库)   │                          │
│                    └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 安全隔离

Agent 间强制隔离，确保 Agent 只能访问自己的记忆：

```python
async def _enforce_isolation(self, query: MemoryQuery):
    """强制Agent间隔离"""
    if not query.agent_id:
        raise PermissionError("Agent ID required for memory access")
```

---

## 相关文档

- ADR-002: FaissVectorStore 持久化 ([002-faiss-vectorstore-persistence.md](./002-faiss-vectorstore-persistence.md))
- ADR-004: KGML LinkML 集成 ([004-kgml-linkml-integration.md](./004-kgml-linkml-integration.md))
