# ADR-006: DuckDB + NetworkX 混合存储决策

**状态**: Accepted
**日期**: 2026-04-08
**来源**: 设计决策讨论 + critical-review-response.md

---

## 背景问题

原有设计使用 SQLite + NetworkX 双存储存在以下问题：

| 问题 | 影响 | 根源 |
|------|------|------|
| 双存储同步 | 数据不一致风险 | SQLite 与 NetworkX 状态分裂 |
| SQLite 并发限制 | FastAPI async 性能瓶颈 | SQLite WAL 但连接池不完善 |
| 图查询效率低 | 复杂分析性能差 | JSON 存储在 SQLite 中不适合图遍历 |

---

## 决策

### 采用 DuckDB 作为主存储

DuckDB 特性：
- 列式存储，适合 OLAP 工作负载
- 内置 JSON 支持，实体数据作为 JSON 存储
- 向量化执行，性能优秀
- 支持 Parquet/CSV 导入导出
- 单文件持久化，无需复杂配置

### 采用 NetworkX 按需加载（图算法）

NetworkX 仅用于图算法，不作为主图存储：
- 担保链检测（guarantee_circle）
- 路径查询（path queries）
- 从 DuckDB 按需加载子图，不加载全图

### 异步包装

DuckDB Python 绑定是同步的，使用 `asyncio.to_thread()` 包装：

```python
async def save_entity(self, entity: EntityInstance) -> str:
    await asyncio.to_thread(
        self._conn.execute,
        "INSERT OR REPLACE INTO entities VALUES (?, ?, ?)",
        [entity.concept, entity.entity_id, json.dumps(entity.data)]
    )
```

---

## 存储架构

```
┌─────────────────────────────────────────────────────────┐
│                    Storage Layer                        │
├─────────────────────────────────────────────────────────┤
│  DuckDBStorage (主存储)                                 │
│  ├── entities 表: concept, entity_id, data (JSON)      │
│  ├── relations 表: relation_type, from, to, data      │
│  └── 索引: concept, from_entity_id                      │
├─────────────────────────────────────────────────────────┤
│  NetworkX (按需加载)                                    │
│  ├── 从 DuckDB relations 表加载                         │
│  ├── 用于图算法: 担保链、路径查询                        │
│  └── 不作为持久化存储                                   │
└─────────────────────────────────────────────────────────┘
```

---

## Schema 设计

```sql
-- 实体表
CREATE TABLE entities (
    concept VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    data JSON NOT NULL,
    PRIMARY KEY (concept, entity_id)
);

-- 关系表
CREATE TABLE relations (
    relation_type VARCHAR NOT NULL,
    from_entity_id VARCHAR NOT NULL,
    to_entity_id VARCHAR NOT NULL,
    data JSON,
    PRIMARY KEY (relation_type, from_entity_id, to_entity_id)
);

-- 索引
CREATE INDEX idx_entities_concept ON entities(concept);
CREATE INDEX idx_relations_from ON relations(from_entity_id);
```

---

## 为什么不是 SQLite

| 方面 | SQLite | DuckDB |
|------|--------|--------|
| 并发模型 | 读并发尚可，写锁粒度粗 | 更好的并发写支持 |
| OLAP 性能 | 一般 | 列式存储，向量化执行优秀 |
| JSON 支持 | 弱 | 内置 JSON 函数 |
| 生态 | 广泛使用 | 分析场景首选 |

---

## 为什么不是 Neo4j

- 违反"本地优先"原则（需要额外部署）
- MVP 阶段复杂度不必要
- DuckDB 已满足当前分析需求

---

## 相关文档

- [tech-stack.md](../tech-stack.md)
- [architecture.md](../architecture.md)
- [project-structure.md](../project-structure.md)
- ADR-001: SQLiteGraphStore 并发与一致性改进（已废弃）
