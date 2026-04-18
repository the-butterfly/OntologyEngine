# 技术选型

> **status**: proposed | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-19
> **[关键设计点]**: 本文档定义 OntologyEngine 的目标技术架构，非当前实现

---

## 核心原则

**本地优先**：零外部依赖，单机可运行
**预留接口**：Neo4j/PostgreSQL 仅保留适配层接口
**渐进扩展**：后期可无缝切换到生产级存储
**Knowledge 编译一次**：增量提取 + SHA256 缓存，只重处理变化文件

---

## 存储策略（目标架构）

### 存储职责矩阵

| 数据类型 | 本地实现 | 云端扩展 | 承载资产 | 核心设计来源 |
|---------|----------|----------|----------|-------------|
| **事务 + 元数据** | SQLite WAL | PostgreSQL / OpenGauss | Dataset/Schema/版本/矛盾报告 | m_flow FSCache + MAMGA |
| **实体关系主存储** | KuzuDB | Neo4j | Entity/Edge/Rule/互索引 | m_flow GraphProvider |
| **向量检索（<100K）** | ChromaDB | PGVector | KnowledgeFragment / 边向量 | MemPalace 96.6% R@5 |
| **向量检索（>100K）** | FAISS IVF+PQ | - | 规模扩展时的向量索引 | Graphify |
| **原文存储** | 文件系统 + ChromaDB metadata | S3 / OSS | KnowledgeFragment 原文 | MemPalace Drawer |
| **指标聚合缓存** | SQLite + diskcache | Redis | 分析结果 | m_flow FSCache 模式 |

---

## 存储架构图

```
┌──────────────────────────────────────────────────────────────┐
│                    OntologyEngine Storage Layer                              │
├──────────────────────────────────────────────────────────────┤
│                                                                      │
│  SQLite（本地事务 + 元数据）                                          │
│  ├── Dataset 元数据（source_uri, linkage_targets）                   │
│  ├── Schema 版本快照引用                                             │
│  ├── 矛盾检测报告                                                    │
│  ├── WAL 变更日志                                                    │
│  ├── entity_snapshots（版本引用）                                    │
│  └── diskcache（指标缓存/会话缓存）◀── m_flow FSCache 模式       │
│                                                                      │
│  KuzuDB（实体关系主存储）                                            │
│  ├── EntityInstance（完整属性 + 时序字段）                           │
│  ├── EdgeInstance（关系 + 关系属性 + edge_text 向量）               │
│  ├── RuleDefinition / RuleLogic                                     │
│  └── 互索引边（extracted_from, trace_to, supported_by, defined_in）│
│                                                                      │
│  ChromaDB / FAISS（向量检索）◀──────────────────                  │
│  ├── KnowledgeFragment 向量（Layer-R）    │                         │
│  └── 边向量索引 ◀──────────────────────┘ ── MemPalace 模式        │
│                                                                      │
│  文件系统                                                            │
│  └── KnowledgeFragment 原文（text 字段过大）                        │
│                                                                      │
└──────────────────────────────────────────────────────────────┘
```

### 向量存储选型决策

```
向量规模判断：
  │
  ├── <100K 向量
  │     └── ChromaDB（自动持久化 + 元数据过滤 + wing/room 过滤）
  │
  └── >100K 向量
        └── FAISS（IndexIVF + PQ 压缩 + 内存映射）

Phase 1 默认 ChromaDB，Phase 2 按规模切换
```

**来源依据**：MemPalace 验证 ChromaDB 达到 96.6% R@5；Graphify 验证 FAISS 适合 >100K 规模。

---

## Layer-R 提取管线（三通道设计）

来自 Graphify 的三通道提取架构，实现增量处理：

```
原始文档
    ↓
┌─────────────────────────────────────────────────────────┐
│  Pass 1: 确定性提取（零 LLM 成本）                       │
│  ├── 结构化文档：段落/表格/API 字段                       │
│  ├── 代码文件：AST 解析（类/函数/导入/调用）              │
│  └── 按内容 SHA256 缓存，变化时只重处理变化文件            │
├─────────────────────────────────────────────────────────┤
│  Pass 2: LLM 语义提取（仅处理变化文件）                   │
│  ├── 概念/关系/设计意图/超边                             │
│  ├── Confidence: EXTRACTED(1.0) / INFERRED(0.4-0.9)   │
│  └── SHA256 缓存，增量更新                               │
├─────────────────────────────────────────────────────────┤
│  Pass 3: 互索引构建                                      │
│  ├── extracted_from：实体 → 碎片                         │
│  ├── supported_by：碎片 → 实体                            │
│  ├── defined_in：规则/指标 → 碎片                         │
│  └── trace_to：推理步骤 → 碎片                           │
└─────────────────────────────────────────────────────────┘
    ↓
KnowledgeFragment（Layer-R）+ EntityInstance（Layer-S）
```

---

## 边语义设计（m_flow Bundle Search 机制）

Kuzu 边向量双写策略：

```
写入流程：
  1. 写入 Kuzu（主存储，含 edge_text_embedding）
  2. 写入 ChromaDB/FAISS（索引加速）
  3. 记录 SQLite WAL：{edge_id, vector_id, status}

故障恢复：
  重启时 → 读取 WAL → 同步 pending 记录到向量索引
```

**路径成本公式（Bundle Search）**：
```
路径成本 = 起始节点向量距离
         + Σ(边向量距离 + 跳数惩罚)
         + miss_penalty（边未被向量检索命中的惩罚）

Episode 最终得分 = min(所有路径成本)  ← 一条强证据链即可证明相关性
```

---

## 适配器接口设计（参考 m_flow + Understand-Anything）

### 存储适配器抽象

```python
# 存储层统一抽象（参考 m_flow GraphProvider）
class StorageAdapter(ABC):
    @abstractmethod
    async def query(self, cypher: str, params: dict) -> list: pass

    @abstractmethod
    async def transaction(self, operations: list) -> None: pass

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

## 上下文栈集成架构（目标态）

```
┌──────────────────────────────────────────────────────────────┐
│  Agent 上下文栈查询时的四阶段集成流程                           │
│                                                              │
│  ① Layer-R: ChromaDB → 向量检索碎片                          │
│     └─ Wing/Room metadata 过滤（MemPalace 模式）             │
│                                                              │
│  ② extracted_from: 碎片 → EntityInstance 扩展               │
│     └─ 互索引边建立碎片到实体的导航                          │
│                                                              │
│  ③ Layer-S: KuzuDB → 图遍历推理 + Bundle Search             │
│     └─ 实体推理、规则执行、trace_to 溯源                     │
│                                                              │
│  ④ Memory 层: 外部 Agent 框架提供                           │
│     └─ 注入会话和用户上下文（OntologyEngine 提供知识接口）    │
└──────────────────────────────────────────────────────────────┘
```

---

## 核心依赖（目标态）

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

## 数据目录结构（目标态）

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

## 设计来源

| 来源 | 贡献的设计点 |
|------|-------------|
| **m_flow** | FSCacheAdapter 模式、GraphProvider 抽象接口、Kuzu 边分区优化、checkpoint 机制、Bundle Search |
| **MemPalace** | ChromaDB 向量存储、Wing/Room metadata 过滤、SQLite 时序三元组、verbatim 存储 |
| **Graphify** | 三通道提取、SHA256 缓存、Leiden 社区检测、Confidence 标签 |
| **KAG** | 存储层职责分离（事务/分析/图）、IndexManager 可插拔框架 |
| **MAMGA** | SQLite 事务日志、NetworkX 图接口、时序多图、causal 链接 |
| **LLM-Wiki-Agent** | ingest 时矛盾检测、SHA256 缓存增量处理 |
