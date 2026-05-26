# Agent 记忆系统简化优化实施计划

> **status**: implementing
> **phase**: phase2-memory-optimization
> **source_of_truth**: 本文档
> **last_verified**: 2026-05-17
> **verified_against**: `review/review_optimization-simplification_2026-05-14.md`, `docs/01-overview/10-kb-process.md`
> **implements_adr**: D-S1, D-S2, D-S3, D-S4, D-S5, D-S6

---

## 实施状态记录

### 2026-05-17 P0 第一轮实施

**已完成**:
- ✅ P0-1 StorageInterface 抽象层 + StorageRouting（14 种 memory_type）
- ✅ P0-2 SQLiteAdapter（cognitive_nodes 表 + FTS5 + triggers）
- ✅ P0-3 ChromaDBAdapter（ChromaDB cognitive collection）
- ✅ P0-4 RRF 混合检索（CognitiveStorage 组合类 + RRF k=60 融合）
- ✅ P0-5 CognitiveRepository 双接口兼容（CognitiveStorageBackend + StorageInterface）
- ✅ P0-5b oe_remember(text) 零参数模式（_infer_memory_type 启发式推断，7/8 模式匹配准确率）
- ✅ P0-6b KuzuGraphStore model_domain 清理 + save_cognitive_node 别名

**识别到的问题**:

| # | 问题 | 影响 | 处理 |
|---|------|------|------|
| Q1 | KuzuGraphStore 缺少 CognitiveStorageBackend 接口方法（list_cognitive_nodes, save_disposition 等） | 24 个 repository 测试失败 | ✅ 已添加 8 个别名方法桥接 |
| Q2 | model_domain 列在 schema/migration/SQL 中残留 6 处 | 数据迁移需要 ALTER TABLE | ✅ 已从 6 处移除 |
| Q3 | SQLiteAdapter 的 superseded_by 过滤条件 OR 优先级错误 | 搜索返回已删除节点 | ✅ 已加括号修复 |
| Q4 | SQLiteAdapter 新建节点缺少 created_at 自动填充 | IntegrityError NOT NULL constraint | ✅ 已在 save_node 中自动填充 |

**测试状态**: 130 tests passed (storage 106 + repository 24)

---

## 一、背景与目标

### 1.1 愿景

将 OntologyEngine 打造为 **Agent 知识库/记忆系统的基础工具**，实现：
- **快速接入**：零 Schema 即可 `oe_remember(text)` 完成知识摄入
- **整合编译**：自动抽取→消歧→链接→巩固的完整流水线
- **治理维护**：矛盾检测、信念修正、策略性遗忘、Dream Cycle 自动化维护
- **消费检索**：RRF 混合检索 + 自适应分层漏斗 + 证据链展开
- **分析洞察**：`oe_reflect` 深度分析 + 健康报告

### 1.2 前置文档

| 文档 | 作用 |
|------|------|
| `review/review_optimization-simplification_2026-05-14.md` | 六项核心架构决策（D-S1~D-S6）+ 执行路线图 + 验收标准 |
| `docs/01-overview/10-kb-process.md` | Build→Govern→Consume 全生命周期流程 |
| `docs/01-overview/09-agent-memory.md` | Agent 记忆概念框架 |
| `docs/02-design/agent-memory/` | 记忆系统详细设计（12 篇文档） |
| `docs/reference/agent-memory-paradigms.md` | 外部记忆系统对标（Mem0/Hindsight/Graphiti 等） |

### 1.3 已完成事项（P0 第一轮）

| 任务 | 状态 | 变更摘要 |
|------|------|---------|
| P0-6 VALID_MEMORY_TYPES 对齐 | ✅ | 14 种类型（D-S2 核心 10 种 + OE 扩展 4 种），所有映射点已更新 |
| P0-9 移除 auto_consolidate | ✅ | 从 8 处移除，consolidate 改为始终触发 |
| P0-7 写入后钩子 ≤500ms | ✅ | `asyncio.create_task` 异步触发，`post_write` 阈值=1 |
| P0-10 consolidate/forget 内部化 | ✅ | 路由移至 `/_internal/`，添加弃用文档 |
| P0-5 MCP 操作完善 | ✅ | tags 类型改为 dict，memory_type 描述更新 |

### 1.4 已知预存问题（非本次引入）

| 问题 | 影响 | 修复入口 |
|------|------|---------|
| KuzuGraphStore 无 `save_cognitive_node` 方法 | 5 个单元测试失败 | P0-1 Phase 4 桥接层修复 |
| kuzu_store.py model_domain schema 列残留 | 数据迁移需要 | P0-6b 独立任务 |
| RRF fusion 4 个测试失败 | 预存 bug | 独立修复 |

---

## 二、详细实施计划

### Phase P0：架构基础（2-4 周）

#### P0-1: StorageInterface 抽象层

**目标**：创建统一的 CognitiveNode 存储接口，替代当前多接口分离模式。

**交付物**：
- `ontology_engine/storage/cognitive_interface.py`（新建）
- `ontology_engine/storage/cognitive_interface_test.py`（新建）

**接口定义**：

```python
class StorageInterface(ABC):
    """统一 CognitiveNode 存储接口。
    
    对 MemoryService 和 CognitiveRepository 暴露一致的存储操作，
    内部根据 memory_type 自动路由到正确的存储引擎。
    """
    
    @abstractmethod
    async def save_node(self, node: CognitiveNode) -> str:
        """写入节点，返回 node.id。根据 memory_type 自动路由。"""
    
    @abstractmethod
    async def get_node(self, node_id: str) -> CognitiveNode | None:
        """按 ID 读取节点。"""
    
    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResult:
        """混合检索（向量+关键词+metadata 过滤），RRF 融合。"""
    
    @abstractmethod
    async def delete_node(self, node_id: str, soft: bool = True) -> None:
        """软删除（默认）或硬删除。"""
    
    @abstractmethod
    async def batch_save(self, nodes: list[CognitiveNode]) -> list[str]:
        """批量写入。"""
    
    @abstractmethod
    async def count(self, filter: dict) -> int:
        """条件计数。"""
    
    async def traverse(self, node_id: str, relation: str | None = None, depth: int = 2) -> list[CognitiveNode]:
        """图遍历（委托给图引擎，默认回退 SQLite 关联查询）。"""


class StorageRouting:
    """按 memory_type 路由到目标存储引擎。"""
    
    ROUTING: dict[str, list[str]] = {
        "fragment":     ["chromadb"],
        "entity":       ["sqlite", "chromadb"],
        "relation":     ["sqlite", "chromadb"],
        "observation":  ["sqlite"],
        "mental_model": ["sqlite"],
        "episode":      ["sqlite"],
        "procedure":    ["sqlite"],
        "rule":         ["sqlite"],
        "opinion":      ["sqlite"],
        "metrics":      ["sqlite"],
    }
```

**存储路由规则**：

| memory_type | SQLite | ChromaDB | 说明 |
|---|---|---|---|
| fragment | — | ✅ | 纯向量，不存 SQLite |
| entity | ✅ | ✅ | 结构化 + entity_name 向量 |
| relation | ✅ | ✅ | 结构化 + edge_text 向量 |
| observation | ✅ | — | 仅结构化 |
| mental_model | ✅ | — | 仅结构化 |
| episode | ✅ | — | 仅结构化 |
| procedure | ✅ | — | 仅结构化 |
| rule | ✅ | — | 仅结构化 |
| opinion | ✅ | — | 仅结构化 |
| metrics | ✅ | — | 仅结构化 |

**验收标准**：
- [ ] StorageInterface 提供完整接口定义
- [ ] StorageRouting 正确路由所有 14 种 memory_type
- [ ] 单元测试覆盖接口契约和路由逻辑
- [ ] 现有 KuzuGraphStore 逻辑不受影响

---

#### P0-2: SQLiteAdapter

**目标**：实现 SQLite 存储适配器，处理结构化 CognitiveNode 数据。

**交付物**：
- `ontology_engine/storage/sqlite/cognitive_adapter.py`（新建）

**SQLite 表结构**：

```sql
CREATE TABLE cognitive_nodes (
    id              TEXT PRIMARY KEY,
    space_id        TEXT NOT NULL,
    memory_type     TEXT NOT NULL,
    cognitive_layer TEXT NOT NULL,
    content         TEXT NOT NULL,
    entity_name     TEXT,
    entity_type     TEXT,
    schema_ref      TEXT,
    tags            TEXT,           -- JSON: {"model": "world", "domain": ["finance"]}
    proof_count     INTEGER DEFAULT 1,
    source_ids      TEXT,           -- JSON array
    confidence      REAL DEFAULT 1.0,
    strength        REAL DEFAULT 1.0,
    access_count    INTEGER DEFAULT 0,
    last_accessed_at TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    superseded_by   TEXT,
    version         INTEGER DEFAULT 1,
    belief_status   TEXT DEFAULT 'accepted',
    visibility      TEXT DEFAULT 'shared',
    created_by      TEXT,
    domain_id       TEXT,
    occurred_at     TEXT,
    valid_from      TEXT,
    valid_to        TEXT,
    recorded_at     TEXT,
    attributes      TEXT,           -- JSON: type-specific attributes
    _store          TEXT DEFAULT 'sqlite'
);

CREATE INDEX idx_cognitive_type ON cognitive_nodes(memory_type);
CREATE INDEX idx_cognitive_layer ON cognitive_nodes(cognitive_layer);
CREATE INDEX idx_cognitive_space ON cognitive_nodes(space_id);
CREATE INDEX idx_cognitive_belief ON cognitive_nodes(belief_status);
CREATE INDEX idx_cognitive_tags ON cognitive_nodes(tags);  -- JSON index

-- FTS5 全文搜索
CREATE VIRTUAL TABLE cognitive_nodes_fts USING fts5(
    content, entity_name,
    content='cognitive_nodes',
    content_rowid='rowid'
);
```

**适配器方法映射**：

| StorageInterface 方法 | SQLiteAdapter 实现 |
|---|---|
| `save_node(node)` | INSERT OR REPLACE INTO cognitive_nodes |
| `get_node(id)` | SELECT * FROM cognitive_nodes WHERE id = ? |
| `search(query)` | FTS5 + JSON 过滤 + BM25 排序 |
| `delete_node(id)` | UPDATE ... SET superseded_by = 'deleted' (soft) |
| `batch_save(nodes)` | INSERT OR REPLACE ... (批量事务) |
| `count(filter)` | SELECT COUNT(*) ... WHERE ... |

**验收标准**：
- [ ] 能存储/读取 entity/relation/rule/observation/mental_model/episode/procedure/opinion/metrics
- [ ] FTS5 全文搜索可用
- [ ] tags JSON 字段可过滤检索
- [ ] 单元测试覆盖 CRUD 和搜索

---

#### P0-3: ChromaDBAdapter

**目标**：实现 ChromaDB 存储适配器，处理向量化 CognitiveNode 数据。

**交付物**：
- `ontology_engine/storage/vector/chromadb_adapter.py`（新建）

**ChromaDB 集合设计**：

```
Collection: cognitive_nodes
  - embedding: text-embedding-3-small (1536d)
  - metadata:
    - memory_type: str
    - cognitive_layer: str
    - space_id: str
    - tags: dict
    - entity_name: str
    - confidence: float
    - created_at: str

Collection: edge_texts (可选)
  - embedding: text-embedding-3-small (1536d)
  - metadata:
    - edge_type: str
    - from_id: str
    - to_id: str
    - space_id: str
```

**适配器方法映射**：

| StorageInterface 方法 | ChromaDBAdapter 实现 |
|---|---|
| `save_node(node)` | collection.add/upsert(ids=[id], documents=[content], metadatas=[...]) |
| `get_node(id)` | collection.get(ids=[id]) |
| `search(query)` | collection.query(query_texts=[...], where={...}, n_results=top_k) |
| `delete_node(id)` | collection.delete(ids=[id]) |
| `batch_save(nodes)` | collection.add(upsert=True, ...) |
| `count(filter)` | collection.count(where={...}) |

**验收标准**：
- [ ] fragment 写入路由到 ChromaDB
- [ ] entity_name 向量索引可用
- [ ] metadata 过滤支持（memory_type/tags/cognitive_layer）
- [ ] 语义检索通过

---

#### P0-4: RRF 混合检索对接

**目标**：StorageInterface.search() 实现 RRF 多路检索。

**交付物**：
- 修改 `ontology_engine/storage/cognitive_interface.py` 中的 `search` 实现

**检索流程**：

```
StorageInterface.search(query)
  ├── ChromaDBAdapter.search(query) → 向量检索结果
  ├── SQLiteAdapter.search(query)   → FTS5/BM25 关键词检索
  └── RRF 融合 → 重排序 → 返回
```

**验收标准**：
- [ ] `oe_recall` 返回结果覆盖语义和精确匹配
- [ ] P@5/R@5 可测量

---

#### P0-5: 完善 3 核心 Agent 操作端到端流程

**目标**：确保 `oe_remember` → `oe_recall` → `oe_reflect` 完整闭环。

**当前状态**：
- ✅ MCP 工具已注册（oe_remember/oe_recall/oe_reflect）
- ✅ tags 类型已改为 dict
- ✅ memory_type 描述已更新为完整 14 种列表
- ⚠️ 零参数 `oe_remember(text)` 模式不完全支持（仍需 memory_type 参数）

**待完成**：
- [ ] `oe_remember(text)` 零参数模式（自动推断 memory_type）
- [ ] 端到端测试脚本

---

### Phase P1：能力增强（4-8 周）

#### P1-1: Dream Cycle 重构为 6 阶段

**目标**：将 DreamCycle 从当前 5 阶段重构为 D-S6 定义的 6 阶段序列。

**当前**：contradiction detection → expiry check → orphan cleanup → self-link → graph completion
**目标**：lint → consolidate → enrich → forget → reflect → health_report

**交付物**：
- 修改 `ontology_engine/engine/cognitive/lifecycle.py`

**验收标准**：
- [ ] 6 阶段可独立执行（`--phase lint` 等）
- [ ] 每日定时运行输出健康报告

---

#### P1-2: Schema Light 最小实现

**目标**：`oe_remember(text)` 无 Schema 也能正常存储和检索。

**交付物**：
- 修改 `ontology_engine/engine/cognitive/memory_api.py` 的 `_remember` 流程

**验收标准**：
- [ ] `oe_remember("Alice works at Google")` 不依赖 Schema 也能工作
- [ ] 自动推断 memory_type = "fragment"

---

#### P1-3: 3 个 Schema 模板

**交付物**：
- `docs/02-design/schema/templates/knowledge-base.yaml`
- `docs/02-design/schema/templates/memory-system.yaml`
- `docs/02-design/schema/templates/financial-risk.yaml`

---

#### P1-4: 文档合并（12→4-5 篇）

**目标**：将 `docs/02-design/agent-memory/` 从 12 篇合并为 4-5 篇。

**当前文档**（12 篇）：
1. README.md
2. arbitration-engine.md
3. consolidation-engine.md
4. memory-api.md
5. memory-hierarchy.md
6. memory-lifecycle.md
7. modeling-objects.md
8. optimization-sota.md
9. permission-service.md
10. query-understanding-layer.md
11. reflect-agent.md
12. session-context-layer.md

**目标文档**（5 篇）：
1. `README.md` — 核心概念 + 3+1 API + 快速入门 + 分类体系 + 标签指南 + Schema Light + 扩展指南
2. `consolidation-engine.md` — 保留（已有代码实现）
3. `storage-schema.md` — 存储架构 + CognitiveNode 数据模型 + 标签系统 + 适配器接口
4. `retrieval-strategy.md` — 检索策略 + RRF 融合 + 分层漏斗 + 证据链
5. `lifecycle-governance.md` — Dream Cycle + 遗忘 + 矛盾治理 + 版本控制

**合并映射**：

| 旧文档 | 并入 |
|--------|------|
| memory-hierarchy.md → | storage-schema.md |
| memory-lifecycle.md → | lifecycle-governance.md |
| memory-api.md → | README.md §API 参考 |
| modeling-objects.md → | README.md §建模对象 |
| query-understanding-layer.md → | retrieval-strategy.md |
| reflect-agent.md → | consolidation-engine.md §反思 |
| optimization-sota.md → | docs-dev/ 研究参考 |
| permission-service.md → | lifecycle-governance.md §权限 |
| session-context-layer.md → | README.md §上下文层 |
| arbitration-engine.md → | lifecycle-governance.md §仲裁 |

---

#### P1-9: QueryUnderstandingLayer 实现

**目标**：任务约束提取 → 驱动检索策略。

**交付物**：
- 新建或扩展现有 `query_understanding_layer.py`

**验收标准**：
- [ ] 8 种约束类型全部实现（当前 3/8）
- [ ] 约束驱动检索策略调整生效

---

#### P1-10: DeduplicationGate 实现

**目标**：写入前去重 + 边际价值判断 + 矛盾前置检测。

**交付物**：
- 已有 `deduplication_gate.py`，需验证与 _remember 集成

**验收标准**：
- [ ] 相似度 > 0.92 标记 DUPLICATE
- [ ] 语义矛盾标记 CONTRADICTION_CANDIDATE
- [ ] 边际价值低于阈值延迟写入

---

#### P1-11: ArbitrationEngine 实现

**目标**：证据权重自动裁决矛盾。

**交付物**：
- 已有 `arbitration_engine.py`，需验证功能完整性

---

### Phase P2：规模扩展（8-16 周）

| 任务 | 说明 |
|------|------|
| P2-1 | Postgres+pgvector Adapter |
| P2-2 | Neo4j Adapter |
| P2-3 | 增量 manifest 追踪（SHA-256） |
| P2-4 | 信念修正形式化保证（AGM） |
| P2-5 | 多 Agent 并发控制 |
| P2-6 | 检索延迟 KPI（p95 < 500ms） |
| P2-7 | Self Model / Task Model 详细设计+实现 |
| P2-8 | 策略性遗忘（否定信号驱动） |
| P2-9 | 来源可信层级实施 |
| P2-10 | 端到端用户旅程验证场景 |

---

## 三、关联影响分析

### 3.1 文件影响矩阵

| 文件 | 改动类型 | 影响 Phase | 风险等级 |
|------|---------|-----------|---------|
| `storage/base.py` | 新增类 | P0-1 | 低（仅新增） |
| `storage/cognitive_interface.py` | 新建 | P0-1 | 低 |
| `storage/sqlite/cognitive_adapter.py` | 新建 | P0-2 | 中 |
| `storage/vector/chromadb_adapter.py` | 新建 | P0-3 | 中 |
| `engine/cognitive/repository.py` | 修改 | P0-4 | 高（核心路径） |
| `engine/cognitive/factory.py` | 修改 | P0-5 | 中 |
| `engine/cognitive/memory_api.py` | 修改 | P0-5, P1-2 | 中 |
| `engine/cognitive/consolidation_engine.py` | 修改 | P0-7, P1-1 | 低 |
| `engine/cognitive/lifecycle.py` | 修改 | P1-1 | 中 |
| `api/routes/memory.py` | 修改 | P0-10 | 低 |
| `mcp/tools/memory.py` | 修改 | P0-5 | 低 |
| `mcp/server.py` | 修改 | P0-5 | 低 |
| `cli/memory.py` | 修改 | P0-9 | 低 |
| `tests/unit/engine/cognitive/test_memory_api.py` | 修改 | P0-9 | 低 |
| `docs/02-design/agent-memory/` | 重组 | P1-4 | 低（仅文档） |

### 3.2 接口变更清单

#### 新增接口

| 接口 | 类型 | 所属模块 | Phase |
|------|------|---------|-------|
| `StorageInterface` | 抽象类 | storage/cognitive_interface.py | P0-1 |
| `StorageRouting` | 工具类 | storage/cognitive_interface.py | P0-1 |
| `SQLiteAdapter` | 实现类 | storage/sqlite/cognitive_adapter.py | P0-2 |
| `ChromaDBAdapter` | 实现类 | storage/vector/chromadb_adapter.py | P0-3 |
| `SearchQuery` | 数据类 | storage/cognitive_interface.py | P0-1 |
| `SearchResult` | 数据类 | storage/cognitive_interface.py | P0-1 |

#### 修改接口

| 接口 | 变更内容 | Phase |
|------|---------|-------|
| `CognitiveRepository.__init__` | storage 参数类型从 CognitiveStorageBackend 改为 StorageInterface | P0-4 |
| `CognitiveRepository.create_node` | 内部调用改为 self._storage.save_node() | P0-4 |
| `CognitiveRepository.get_node` | 内部调用改为 self._storage.get_node() | P0-4 |
| `MemoryAPI._remember` | consolidation 改为异步触发 | P0-7 |
| `MemoryAPI._infer_tags` | 新增 metrics/relation 映射 | P0-6 |
| `MemoryAPI._infer_cognitive_layer` | 新增 metrics/relation 映射 | P0-6 |
| `MemoryAPI._extract_attributes` | 新增 metrics/relation 属性键 | P0-6 |
| `ConsolidationEngine.maybe_trigger_consolidation` | 新增 post_write 触发器 | P0-7 |
| `MemoryService.remember` | 移除 auto_consolidate 参数 | P0-9 |
| `MCP oe_remember` | tags 类型改为 dict，移除 auto_consolidate | P0-5 |
| `CLI remember` | 移除 --auto-consolidate 选项 | P0-9 |

#### 废弃接口

| 接口 | 替代方案 | Phase |
|------|---------|-------|
| `POST /v1/spaces/{id}/memory/consolidate` | `POST /v1/spaces/{id}/memory/_internal/consolidate` | P0-10 |
| `POST /v1/spaces/{id}/memory/forget` | `POST /v1/spaces/{id}/memory/_internal/forget` | P0-10 |
| `auto_consolidate` 参数 | 始终自动触发 | P0-9 |

#### 删除接口

| 接口 | 原因 | Phase |
|------|------|-------|
| `CognitiveNode.model_domain` 字段 | 已迁移到 tags["model"] | P0-6（模型层已删除） |

### 3.3 数据迁移需求

| 迁移项 | 源 | 目标 | 复杂度 |
|--------|---|------|--------|
| model_domain → tags["model"] | KuzuDB cognitive_node 列 | tags JSON 字段 | 中 |
| CognitiveNode 数据迁移 | KuzuDB | SQLite + ChromaDB | 高 |
| kuzu_store.py schema 清理 | ALTER TABLE DROP COLUMN | — | 低 |

### 3.4 向后兼容策略

| 组件 | 兼容策略 |
|------|---------|
| CognitiveStorageBackend | 保留为 StorageInterface 的 fallback 适配器 |
| KuzuGraphStore | 保留 EntityInstance/RelationInstance 路径，仅迁移 CognitiveNode 路径 |
| DualWriteCoordinator | 保留，不影响 CognitiveNode 路径 |
| 现有测试 | 新增测试覆盖新功能，现有测试修复预存 bug |

---

## 四、关键问题点与决策

### Q1: KuzuGraphStore 接口不匹配

**问题**：KuzuGraphStore 有 `upsert_cognitive_node` 但 CognitiveRepository 调用 `save_cognitive_node`。
**影响**：5 个单元测试失败。
**解决方案**：在 KuzuGraphStore 添加 `save_cognitive_node` 别名方法指向 `upsert_cognitive_node`。
**优先级**：P0-4 修复。

### Q2: kuzu_store.py model_domain schema 残留

**问题**：KuzuDB schema 定义中仍有 `model_domain STRING` 列。
**影响**：数据迁移需要 ALTER TABLE。
**解决方案**：添加迁移脚本，保留向后兼容读取。
**优先级**：P0-6b 独立任务。

### Q3: asyncio.create_task 进程退出丢失

**问题**：异步 consolidation 在进程退出时可能被取消。
**影响**：少量 consolidation 任务丢失。
**解决方案**：使用 `self._background_tasks` 集合追踪，shutdown 时 await 所有任务。
**优先级**：P0-7 后续完善。

### Q4: SQLite 表设计复杂度

**问题**：CognitiveNode 有 30+ 字段。
**影响**：存储效率、查询性能。
**解决方案**：核心字段独立列，attributes/tags 使用 JSON 列。
**优先级**：P0-2 设计时确定。

### Q5: 测试防护网不足

**问题**：现有测试 9 个失败（预存 bug），区分度低。
**影响**：重构时无法快速发现回归。
**解决方案**：
1. 先修复预存 bug
2. 新增 StorageInterface 接口契约测试
3. 新增端到端验收场景（examples/agent_memory/13_e2e_journey/）
**优先级**：P0 实施前完成。

---

## 五、测试策略

### 5.1 新增测试清单

| 测试文件 | 覆盖内容 | Phase |
|---------|---------|-------|
| `test_storage_interface.py` | StorageInterface 接口契约 | P0-1 |
| `test_storage_routing.py` | memory_type → 存储引擎路由 | P0-1 |
| `test_sqlite_adapter.py` | SQLiteAdapter CRUD + FTS5 | P0-2 |
| `test_chromadb_adapter.py` | ChromaDBAdapter 向量存储 + 检索 | P0-3 |
| `test_repository_integration.py` | CognitiveRepository + StorageInterface | P0-4 |
| `test_consolidation_async.py` | 异步 consolidation 不丢失 | P0-7 |
| `test_dream_cycle_six_phases.py` | Dream Cycle 6 阶段 | P1-1 |
| `test_schema_light.py` | 零 Schema 模式 | P1-2 |

### 5.2 回归测试命令

```bash
# 每次改动后运行
pytest tests/unit/engine/cognitive/ -v
python examples/agent_memory/11_acpt_retrieval/run_eval.py
python examples/agent_memory/12_acpt_management/run_eval.py
mypy ontology_engine/engine/cognitive/ --strict
```

### 5.3 验收阈值

| 指标 | 当前 | 目标 |
|------|------|------|
| 单元测试通过率 | 70%（预存 bug） | 95%+ |
| 检索验收均值 | 0.767 | 0.85+ |
| 资产管理验收均值 | 0.963 | 0.95+ |
| 类型检查 | 6 个预存错误 | 0 个新增 |

---

## 六、执行顺序与依赖

```
P0-1 StorageInterface 抽象层
    ↓
P0-2 SQLiteAdapter ──┐
    ↓                ├── 可并行
P0-3 ChromaDBAdapter ─┘
    ↓
P0-4 RRF 混合检索对接
    ↓
P0-5 CognitiveRepository 桥接 + Factory 更新
    ↓
P0-6b kuzu_store model_domain 清理
    ↓
P1-1 Dream Cycle 6 阶段
P1-2 Schema Light
P1-3 Schema 模板
P1-4 文档合并
P1-9 QUL 扩展
P1-10 DeduplicationGate 验证
P1-11 ArbitrationEngine 验证
    ↓
P2-1~P2-10 规模扩展
```

**并行机会**：
- P0-2 和 P0-3 可并行（不同存储引擎）
- P1-1~P1-4 可并行（独立模块）
- P1-9~P1-11 可并行（独立模块）

**回滚策略**：每 Phase 完成后确保测试通过。任何 Phase 失败可回退到上一 Phase 的稳定状态。

---

## 七、端到端用户旅程设计

参考 `docs/01-overview/10-kb-process.md` §5 供应链金融 30 天案例，新建 `examples/agent_memory/13_e2e_journey/`：

```
场景：供应链金融风控 Agent 的完整生命周期

Day 1-3:  Build（构建）
  → 导入企业年报/新闻/征信报告
  → 验证：实体提取、关系建立、Schema 对齐、质量评分

Day 4-7:  Govern（管理）
  → 矛盾检测（新旧数据冲突）
  → 用户更正（诉讼撤诉）
  → Dream Cycle 自动维护
  → 验证：矛盾标记、信念修正、级联更新

Day 8-10: Consume（消费）
  → Agent 查询"华为风险如何？"
  → 时序追溯"为什么波动？"
  → 验证：分层漏斗检索、证据链展开、置信度

Day 11-14: Reflect（分析）
  → oe_reflect("近30天风险模式")
  → 生成 mental_model
  → 验证：新结论归档、溯源完整
```

---

## 八、进度追踪

| Phase | 任务 | 状态 | 完成日期 |
|-------|------|------|---------|
| P0-6 | VALID_MEMORY_TYPES 对齐 | ✅ 完成 | 2026-05-17 |
| P0-9 | 移除 auto_consolidate | ✅ 完成 | 2026-05-17 |
| P0-7 | 写入后钩子 ≤500ms | ✅ 完成 | 2026-05-17 |
| P0-10 | consolidate/forget 内部化 | ✅ 完成 | 2026-05-17 |
| P0-5 | MCP 操作完善 | ✅ 完成 | 2026-05-17 |
| P0-1 | StorageInterface 抽象层 | ⏳ 待启动 | — |
| P0-2 | SQLiteAdapter | ⏳ 待启动 | — |
| P0-3 | ChromaDBAdapter | ⏳ 待启动 | — |
| P0-4 | RRF 混合检索对接 | ⏳ 待启动 | — |
| P0-5 | 端到端流程完善 | ⏳ 待启动 | — |
| P0-6b | kuzu_store model_domain 清理 | ⏳ 待启动 | — |
| P1-1 | Dream Cycle 6 阶段 | ⏳ 待启动 | — |
| P1-2 | Schema Light | ⏳ 待启动 | — |
| P1-3 | Schema 模板 | ⏳ 待启动 | — |
| P1-4 | 文档合并 | ⏳ 待启动 | — |
| P1-9 | QUL 扩展 | ⏳ 待启动 | — |
| P1-10 | DeduplicationGate | ⏳ 待启动 | — |
| P1-11 | ArbitrationEngine | ⏳ 待启动 | — |
