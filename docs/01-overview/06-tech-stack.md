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

### 向量数据库

| 方案 | 用途 | 选型依据 |
|------|------|----------|
| **ChromaDB**（主，<100K） | 知识碎片嵌入 + 语义检索 | 轻量嵌入，支持元数据过滤，Python 原生 |
| **LanceDB**（>100K） | 大规模向量索引 + 性能优先场景 | GPU 加速，m_flow 默认选择，性能更优 |
| FAISS（辅） | 离线批量相似度计算 | 高性能，适合离线索引构建 |

**来源依据**：MemPalace 验证 ChromaDB 达到 96.6% R@5；Graphify 验证 FAISS 适合 >100K 规模。

## LLM 与嵌入

### LLM 网关

| 方案 | 用途 | 选型依据 |
|------|------|----------|
| **litellm**（主） | 统一 LLM 调用接口 | 支持 OpenAI/Anthropic/Mistral/Groq/Ollama 等 14+ 提供商 |
| **BAML**（可选） | 结构化输出框架 | 类型安全，适合复杂提取任务 |

### 嵌入引擎（双模式）

| 模式 | 方案 | 用途 | 选型依据 |
|------|------|------|----------|
| **云端模式**（默认） | qwen3-embedding-8b | 高质量嵌入 | 质量最优，需配置网络和 API Key |
| **本地模式** | Fastembed / Ollama | 隐私优先，零网络依赖 | 本地部署场景，384-768 维 |

**配置切换**：
```yaml
embedding:
  mode: cloud  # cloud | local
  cloud:
    model: qwen3-embedding-8b
    dimension: 4096
  local:
    model: jina-v5-text-nano
    dimension: 768
```

### 存储层技术实现框架

```
图数据库实现（参考 Cognee KuzuAdapter + m_flow GraphProvider）：

Cognee KuzuAdapter 设计（2400+ 行，最完整的 Kuzu 适配器）：
  - Schema 设计：仅两张表 Node(id, name, type, created_at, updated_at, properties) + EDGE(FROM Node TO Node, relationship_name, properties)
  - 动态属性存储在 JSON properties 字段中
  - 异步执行：ThreadPoolExecutor + run_in_executor 将同步 Kuzu 查询包装为异步
  - 并发控制：asyncio.Lock 保护连接变更；可选 Redis 分布式锁
  - 批量操作：UNWIND Cypher 子句实现批量节点/边 MERGE
  - 反馈权重：节点和边都支持 feedback_weight 属性，用于记忆强化
  - 子图查询：get_neighborhood() 支持 k-hop 遍历，get_nodeset_subgraph() 支持按类型和名称过滤

m_flow GraphProvider 适配器模式：
  - GraphProvider 抽象基类，定义 Cypher 查询、节点/边 CRUD、子图提取、邻居遍历等接口
  - _track_changes 装饰器，自动记录节点/边变更到 GraphRelationshipLedger
  - 实现：KuzuDB（默认嵌入式）、Neo4j、Neptune
  - 数据集隔离：DatasetDatabaseHandler 接口，Kuzu 和 LanceDB 各有实现

codebase-memory-mcp RAM-first 设计：
  - SQLite WAL 模式，ACID 安全
  - 预编译语句缓存：所有 SQL 语句预编译并缓存，避免重复解析
  - 空闲驱逐：60 秒无活动后关闭缓存的项目 store，释放 SQLite 内存
  - 文件哈希：stmt_upsert_file_hash / stmt_get_file_hashes 用于增量索引

向量数据库实现（参考 m_flow VectorProvider + Cognee VectorDBInterface）：

m_flow VectorProvider Protocol：
  - 定义集合管理、MemoryNode CRUD、语义搜索、嵌入生成
  - 多租户钩子：create_dataset / delete_dataset
  - 实现：LanceDB（默认）、ChromaDB、PGVector、Pinecone、Milvus

Cognee VectorDBInterface（Protocol）：
  - has_collection, create_collection, create_data_points, search, batch_search, embed_data
  - 上下文感知配置：get_vectordb_context_config() 允许不同异步任务使用不同数据库配置
  - 多租户隔离：ENABLE_BACKEND_ACCESS_CONTROL=True 时，每个 user+dataset 组合可拥有独立实例

嵌入引擎实现（参考 m_flow + QMD）：

m_flow 嵌入引擎：
  - LiteLLMEmbeddingEngine（默认 OpenAI）
  - FastembedEmbeddingEngine（本地）
  - OllamaEmbeddingEngine
  - MemoryNode.extract_index_text() 方法将索引字段拼接为 " | " 分隔的字符串进行向量化

QMD 双模型族嵌入格式：
  EmbeddingGemma（默认）：
    query: "task: search result | query: {query}"
    doc:   "title: {title} | text: {content}"
  Qwen3-Embedding（多语言/CJK）：
    query: "Instruct: Retrieve relevant documents for the given query\nQuery: {query}"
    doc:   "{title}\n{content}"  # 无特殊前缀
  并行嵌入：GPU 根据 VRAM 的 25% 计算并行度（上限 8），CPU 根据数学核心数/4（上限 4）
```

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

## 图算法

| 算法 | 用途 | 选型依据 |
|------|------|----------|
| **Leiden**（优先） | 社区检测 | graspologic 实现，社区质量高于 Louvain，Graphify 验证 |
| **Louvain**（回退） | 社区检测 | NetworkX 内置，graspologic 不可用时回退 |
| **PageRank** | 节点重要性 | KAG PPR 概率传播检索 |
| **最短路径** | 关系链分析 | NetworkX 内置 |
| **BFS/DFS** | 子图遍历 | 图查询基础 |

### 社区检测策略

```
参考 Graphify cluster.py：
  - 优先使用 Leiden（graspologic），回退到 Louvain（networkx）
  - 超大社区拆分：超过图节点 25%（最少 10 个节点）的社区会被二次 Leiden 划分
  - 孤立节点处理：度为 0 的节点不参与 Leiden，每个孤立节点自成单节点社区
  - 确定性排序：社区按大小降序重新编号，确保跨运行稳定
  - 内聚度评分：cohesion_score() = 社区内实际边数 / 最大可能边数
  - 聚类基于图拓扑（边密度），不使用嵌入向量——语义相似性边已存在于图中
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
