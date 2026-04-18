# 技术选型

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-19

## 核心原则

**本地优先**: 零外部依赖，单机可运行
**预留接口**: Neo4j/PostgreSQL 仅保留适配层接口
**渐进扩展**: 后期可无缝切换到生产级存储
**三层资产统一存储**: IT 资产、个人知识沉淀、组织级资产共用同一存储基础设施

---

## 废弃方案说明

| 废弃方案 | 原因 | 参考 |
|---------|------|------|
| ~~DuckDB 作为主存储~~ | 分析引擎不适合高频写入，MVCC 写入代价高 | [#1 分析报告](#一duckdb-事务分析) |
| ~~Entity/Edge 存 DuckDB~~ | 频繁更新的字段（如 risk_level）导致版本膨胀 | m_flow 架构分析 |
| ~~Faiss 作为唯一向量索引~~ | 无原生元数据过滤，100K 以下向量 ChromaDB 更简单 | MemPalace 实践 |

---

## 存储策略（2026-04-19 更新）

### 存储职责矩阵

| 数据类型 | 本地实现 | 云端扩展 | 承载资产 | 说明 |
|---------|----------|----------|----------|------|
| **事务 + 元数据** | SQLite | PostgreSQL / OpenGauss | Dataset/Schema/版本 | WAL 模式，低延迟写入 |
| **实体关系主存储** | KuzuDB | Neo4j | Entity/Edge/Rule/互索引 | 图结构遍历，含边向量 |
| **向量检索** | ChromaDB / FAISS | PGVector | KnowledgeFragment / 边向量 | 规模 >100K 切换 FAISS |
| **指标聚合缓存** | SQLite + diskcache | PostgreSQL | 分析结果 | m_flow FSCache 模式 |
| **图实例版本** | SQLite | PostgreSQL | 版本元数据 | Kuzu checkpoint 快照 |

### 存储架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OntologyEngine Storage Layer                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SQLite（本地事务 + 元数据）                                          │
│  ├── Dataset 元数据（source_uri, linkage_targets）                   │
│  ├── Schema 版本快照引用                                             │
│  ├── 矛盾检测报告                                                    │
│  ├── 变更日志 WAL                                                    │
│  ├── entity_snapshots（版本引用）                                    │
│  └── diskcache（指标缓存/会话缓存）◀─── m_flow FSCache 模式        │
│                                                                      │
│  KuzuDB（实体关系主存储）                                            │
│  ├── EntityInstance（完整属性 + 时序字段）                           │
│  ├── EdgeInstance（关系 + 关系属性）                                 │
│  ├── 边向量（edge_text_embedding 属性）◀── 主存储                   │
│  ├── RuleDefinition / RuleLogic                                     │
│  └── 互索引边（extracted_from, trace_to, supported_by, defined_in）  │
│                                                                      │
│  ChromaDB / FAISS（向量检索）◀───────────────                       │
│  ├── KnowledgeFragment 向量（Layer-R）    │                         │
│  └── 边向量索引 ◀────────────────────┘ ── 加速检索                  │
│                                                                      │
│  文件系统                                                            │
│  └── KnowledgeFragment 原文（text 字段过大）                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 向量存储选型决策

```
向量规模判断：
  │
  ├── <100K 向量
  │     └── ChromaDB（自动持久化 + 元数据过滤 + 简单配置）
  │
  └── >100K 向量
        └── FAISS（IndexIVF + PQ 压缩 + 内存映射）

Phase 1 默认 ChromaDB，Phase 2 按规模切换
```

**参考**: MemPalace 使用 ChromaDB 达到 96.6% R@5；m_flow 统一 ChromaDB 接口

---

## 设计来源

| 来源 | 贡献的设计点 |
|------|-------------|
| **m_flow** | FSCacheAdapter 模式、GraphProvider 抽象接口、Kuzu 边分区优化、checkpoint 机制 |
| **MemPalace** | ChromaDB 向量存储、SQLite 时序三元租（KnowledgeGraph） |
| **KAG (OpenSPG)** | 存储层职责分离（事务/分析/图）|
| **MAMGA** | SQLite 事务日志、NetworkX 图接口 |

---

## 上下文栈集成架构

```
┌─────────────────────────────────────────────────────────┐
│  Agent 上下文栈查询时的四阶段集成流程                      │
│                                                          │
│  ① Layer-R: ChromaDB/FAISS → 向量检索碎片             │
│     └─ 查询相关 Fragment，返回原文证据                      │
│                                                          │
│  ② extracted_from: 碎片 → EntityInstance 扩展           │
│     └─ 通过互索引边建立碎片到实体的导航                    │
│                                                          │
│  ③ Layer-S: KuzuDB → 图遍历推理                          │
│     └─ 实体推理、规则执行、trace_to 溯源                  │
│                                                          │
│  ④ Memory 层: 外部 Agent 框架提供                        │
│     └─ 注入会话和用户上下文（OntologyEngine 提供知识接口）│
└─────────────────────────────────────────────────────────┘
```

---

## 核心依赖

```toml
[project]
dependencies = [
    # Web 框架
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",

    # 数据验证
    "pydantic>=2.0",
    "pydantic-settings>=2.0",

    # 本地存储
    "sqlite-utils>=3.36",        # SQLite 操作辅助
    "diskcache>=5.6",            # 本地缓存（m_flow 模式）
    "kuzu>=0.4",                 # 图数据库
    "chroma>=0.5,<0.7",         # 向量存储（Phase 1）
    # "faiss-cpu>=1.7",         # Phase 2 按需启用

    # 数据处理
    "pyyaml>=6.0",
    "pandas>=2.0",

    # 工具
    "httpx>=0.27",
    "structlog>=24.0",
    "typer>=0.12",

    # 预留驱动（可选安装）
    # "neo4j>=5.0",               # 云端图数据库
    # "psycopg[binary]>=3.0",     # PostgreSQL
    # "pgvector>=0.3",            # 云端向量
    # "redis>=5.0",                # 分布式缓存
]

[project.optional-dependencies]
ai = [
    "openai>=1.0",
    "sentence-transformers>=2.5",  # 本地 Embedding
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "black>=24.0",
    "ruff>=0.3",
    "mypy>=1.0",
]
```

---

## 适配器接口设计（参考 m_flow）

### 存储适配器抽象

```python
# 存储层统一抽象（参考 m_flow GraphProvider）
class StorageAdapter(ABC):
    """存储适配器基类"""

    @abstractmethod
    async def query(self, cypher: str, params: dict) -> list:
        pass

    @abstractmethod
    async def transaction(self, operations: list) -> None:
        pass

# 图存储适配器
class KuzuAdapter(StorageAdapter):
    """Kuzu 本地实现"""
    pass

class Neo4jAdapter(StorageAdapter):
    """Neo4j 云端实现"""
    pass

# 向量存储适配器
class ChromaAdapter(VectorAdapter):
    """ChromaDB 本地实现（<100K 向量）"""
    pass

class FaissAdapter(VectorAdapter):
    """FAISS 实现（>100K 向量）"""
    pass

class PGVectorAdapter(VectorAdapter):
    """PGVector 云端实现"""
    pass

# 缓存适配器
class FSCacheAdapter(CacheAdapter):
    """diskcache 本地实现（参考 m_flow）"""
    pass

class RedisCacheAdapter(CacheAdapter):
    """Redis 分布式实现"""
    pass
```

### 配置切换

```python
class StorageConfig(BaseSettings):
    # 存储模式
    mode: str = "local"  # local | cloud | hybrid

    # 本地
    graph_backend: str = "kuzu"
    vector_backend: str = "chroma"  # chroma | faiss
    cache_backend: str = "diskcache"

    # 云端（扩展用）
    neo4j_uri: str | None = None
    postgres_dsn: str | None = None
    pgvector_dsn: str | None = None
```

---

## 边向量双写策略

### 问题

Kuzu 和 Faiss 是独立引擎，无法跨引擎 ACID 事务。

### 解决方案：WAL + 最终一致

```
写入流程：
  1. 写入 Kuzu（主存储，含 edge_text_embedding）
  2. 写入 Faiss/Chroma（索引加速）
  3. 记录 SQLite WAL：{edge_id, vector_id, status}

故障恢复：
  重启时 → 读取 WAL → 同步 pending 记录到向量索引
```

**同步模式**：
- **同步双写**：写入 Kuzu 后立即写向量索引，失败标记 WAL
- **异步同步**：后台任务定期同步

---

## 复杂查询处理（路径 + 向量约束）

### 本地分层查询

```
查询："担保圈中涉及高风险客户的关联关系"

Step 1：向量预过滤
  ChromaDB query_vector("高风险客户") → {ent_A, ent_B}

Step 2：图约束过滤
  Kuzu traverse(ent_A, relation="guarantees", depth=3) → {edge_1, edge_2}

Step 3：边向量二次过滤（可选）
  边向量相似度过滤

Step 4：结果合并
  路径结果 ∩ 向量过滤结果
```

### 云端方案（PostgreSQL + PGVector）

```sql
-- 原生混合查询（GaussV / PostgreSQL）
SELECT e.name, e.credit_score,
       e.embedding <-> '[0.1, 0.2, ...]' as distance
FROM entities e
JOIN edges ed ON ed.from_entity = e.id
WHERE ed.relation_type = 'guarantees'
ORDER BY distance;
```

---

## 本地与云端融合

```
本地部署                          云端部署
──────────────────────────────────────────────────────────────
SQLite ←─────────────────────────→ PostgreSQL / OpenGauss
KuzuDB ←──────────────────────────→ Neo4j
ChromaDB / FAISS ←───────────────→ PGVector
文件系统 ←─────────────────────────→ S3 / OSS

同步策略：手动触发（用户确认）
```

---

## 数据目录结构

```
data/
├── ontology.db              # SQLite（元数据/版本/日志）
├── kuzu_db/                 # KuzuDB（图数据）
│   └── kuzu.db
├── vectors/                 # 向量索引
│   ├── fragments/          # KnowledgeFragment 向量（ChromaDB）
│   └── edges/              # 边向量索引（Faiss）
├── cache/                   # diskcache（指标缓存/会话）
├── snapshots/               # 版本快照
└── raw_text/               # KnowledgeFragment 原文
```

---

## 迁移路径

```
Phase 1: SQLite + Kuzu + ChromaDB + diskcache
Phase 2: SQLite + Kuzu + FAISS（规模 >100K 时切换）
Phase 3: 可选云端扩展（Neo4j + PGVector + PostgreSQL）
```

---

## **[待确认]**

| # | 问题 | 选项 |
|---|------|------|
| 1 | **边向量存储位置** | A) Kuzu 主存 + Faiss 索引双写  B) 仅 Faiss（Kuzu 不存边向量）|
| 2 | **向量规模阈值** | A) 100K（ChromaDB/FAISS 分界）B) 其他（请说明）|
| 3 | **同步触发方式** | A) 手动触发（当前决策）B) 自动 + 人工确认 |

---

*参考来源: m_flow 存储架构 | MemPalace ChromaDB 实践 | KAG 存储分层设计 | MAMGA 图接口*
