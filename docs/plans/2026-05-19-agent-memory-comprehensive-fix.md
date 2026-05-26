# Agent 记忆系统全面修复与补齐计划

> **status**: draft
> **phase**: phase2-memory-fix
> **source_of_truth**: 本文档
> **last_verified**: 2026-05-19
> **verified_against**: `docs/02-design/agent-memory/`, `docs-dev/03-rfc/RFC-020~025`, `docs/ROADMAP.md`
> **supersedes**: `2026-05-17-agent-memory-optimization.md`（P0 第一轮已完成部分纳入本文档）

---

## 一、总体改进方向与预期效果

### 1.1 核心目标

将 OntologyEngine 打造为 **Agent 易用的知识库和记忆系统工具**，完成知识资产的结构化 **构建→管理→消费→更新** 全生命周期闭环，使用混合存储保障应用效果和容易使用。

### 1.2 改进方向

| 方向 | 当前状态 | 目标状态 | 核心价值 |
|------|---------|---------|---------|
| **模块边界合规** | storage/ → engine/ 6 处反向依赖 | 零反向依赖 | 架构可维护性 |
| **知识资产 CRUD 闭环** | 缺 Update/Delete | 完整 CRUD | AGENT 生命周期管理 |
| **双层写入打通** | remember() 跳过 Layer-R | Layer-R + Layer-S 双写 | 证据链完整性 |
| **认知存储统一** | 双轨接口并存 | 渐进收敛到 StorageInterface | 降低维护成本 |
| **策略性遗忘** | 未实现 | 否定信号驱动遗忘 | 知识库质量治理 |
| **LLM 反思循环** | 未实现 | 混合模式（规则+LLM） | 矛盾检测深度 |
| **检索路径优化** | Analytical 返回空、FTS5 BM25 缺失 | 完整检索管线 10 步 | 检索效果 |
| **recall 检索管线** | 仅基础检索，缺分层漏斗/置信度过滤/Token裁剪 | 完整 10 步管线 | 检索精度与效率 |
| **遗忘策略完整性** | 仅 Ebbinghaus 衰减，缺 5 级策略 | 5 级遗忘 + Ebbinghaus + 策略性遗忘 | 知识库质量治理 |
| **存储三接口分离** | 接口未按 Graph/Vector/Meta 分离 | GraphStore + VectorStore + MetaStore + 工厂 | 存储可替换性 |
| **CognitiveNode 模型补齐** | 12 字段缺失 | 全字段 + KuzuDB 迁移 | 数据完整性 |

### 1.3 预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| 模块边界违规 | 6 处 | 0 处 |
| 知识资产 CRUD 覆盖 | 2/4（Create/Read） | 4/4 |
| 记忆系统 remember 编排链 | 2/6 步 | 6/6 步 |
| 认知存储接口统一度 | 双轨并存 | 单轨主导 + legacy 桥接 |
| MCP 工具 CRUD 覆盖 | 2/4 | 4/4 |
| 检索验收均值 | 0.767 | 0.85+ |
| 单元测试通过率 | ~70% | 95%+ |
| mypy --strict | 有预存错误 | 0 新增 |

---

## 二、实施阶段总览

```
Stage 0: 运行时 Bug 修复 ──────────────────────────────── [前置条件]
    ↓
Stage 1: 模块边界修复（CognitiveNode 下沉）────────────── [P0]
    ↓
Stage 2: 知识资产 CRUD 补齐 ────────────────────────────── [P0]
    ↓
Stage 3: COG_SUPPORTED_BY + 检索路径修复 ──────────────── [P1]
    ↓
Stage 4: 策略性遗忘 + 遗忘因子修正 ────────────────────── [P1]
    ↓
Stage 5: IngestionService 双层写入 ─────────────────────── [P1]
    ↓
Stage 6: LLM 反思混合模式 ─────────────────────────────── [P1]
    ↓
Stage 7: 认知存储接口收敛 + FTS5 抽象 ─────────────────── [P1→P2]
    ↓
Stage 8: 模型补齐 + 补偿日志持久化 + Examples 同步 ────── [P2]
```

**依赖关系**：

```
Stage 0 ──→ Stage 1 ──→ Stage 2 ──→ Stage 3
                                    ↓
                              Stage 5 ──→ Stage 6
                              Stage 4 ──→ Stage 6
                              Stage 7
                              Stage 8
```

- Stage 1→2：CognitiveNode 下沉是 CRUD 补齐的前置（模型位置确定后才能统一接口）
- Stage 3→5：COG_SUPPORTED_BY 是双层写入证据链的组成部分
- Stage 4+5→6：策略性遗忘和双层写入是 LLM 反思的数据基础
- Stage 7→8：接口收敛后才能做模型补齐和持久化

---

## 三、各阶段详细实施方案

---

### Stage 0: 运行时 Bug 修复

**目标**：修复已知的运行时 Bug，为后续重构建立稳定基线。

**对应 RFC**：RFC-024 Phase 1

#### 0-1: correct_memory space_id 未定义

| 维度 | 内容 |
|------|------|
| **问题** | `correct_memory()` 方法中 `space_id` 变量未定义，运行时抛 `NameError` |
| **位置** | `engine/cognitive/memory_api.py` → `correct_memory()` |
| **修复** | 从方法参数或上下文中获取 `space_id`，确保传递到存储层 |
| **验证** | `pytest tests/unit/engine/cognitive/test_evidence_correction.py -v` |

#### 0-2: update_node 遗漏 confirmation_count

| 维度 | 内容 |
|------|------|
| **问题** | `update_cognitive_node()` 未递增 `confirmation_count`，导致确认计数永远为初始值 |
| **位置** | `storage/graph/kuzu_store.py` → `update_cognitive_node()` |
| **修复** | 在 UPDATE Cypher 中添加 `SET confirmation_count = confirmation_count + 1` |
| **验证** | 单元测试验证 update 后 confirmation_count 递增 |

#### 0-3: query_cognitive_nodes SELECT 缺列

| 维度 | 内容 |
|------|------|
| **问题** | `query_cognitive_nodes()` 的 SELECT 语句缺少部分列，返回数据不完整 |
| **位置** | `storage/graph/kuzu_store.py` → `query_cognitive_nodes()` |
| **修复** | 补齐 SELECT 列表，与 CognitiveNode 字段对齐 |
| **验证** | 查询返回的 CognitiveNode 包含所有必要字段 |

#### 0-4: entity_resolver._store → _repo

| 维度 | 内容 |
|------|------|
| **问题** | `entity_resolver.py` 中引用 `self._store` 但实际属性名为 `self._repo` |
| **位置** | `engine/cognitive/` 下 entity_resolver 相关代码 |
| **修复** | 统一属性名为 `self._repo` 或 `self._store`，保持内部一致 |
| **验证** | `pytest tests/unit/engine/cognitive/ -v` |

**验收标准**：

- [ ] 4 个 Bug 全部修复
- [ ] `pytest tests/unit/engine/cognitive/ -v` 全部通过
- [ ] `mypy ontology_engine/engine/cognitive/ --strict` 无新增错误

---

### Stage 1: 模块边界修复 — CognitiveNode 模型下沉

**目标**：消除 storage/ → engine/ 的 6 处反向依赖，使模块边界合规。

**对应设计要求**：AGENTS.md 模块边界规则 `storage/local/ → 仅实现 base.py 接口 (禁止依赖上层)`

#### 1-1: 创建 storage/models.py

**方案**：在 `ontology_engine/storage/` 下新建 `models.py`，将 `CognitiveNode` 和 `VALID_MEMORY_TYPES` 从 `engine/cognitive/models.py` 迁移过来。

**选择 `storage/models.py` 而非 `storage/base.py` 的理由**：
- `base.py` 已有 6 个 ABC + 大量数据模型，职责过重
- 独立 `models.py` 遵循单一职责，且与 Python 社区惯例一致
- `base.py` 中的 ABC 可以 import `models.py` 中的数据类，不产生循环依赖

**具体步骤**：

1. 在 `ontology_engine/storage/models.py` 中定义：
   ```python
   # 从 engine/cognitive/models.py 迁移
   VALID_MEMORY_TYPES: Final[frozenset[str]] = frozenset({...})
   
   @dataclass
   class CognitiveNode:
       # 完整字段定义（含 Stage 8 补齐的 12 个新字段占位）
       ...
   ```

2. 在 `engine/cognitive/models.py` 中改为 re-export：
   ```python
   from ontology_engine.storage.models import CognitiveNode, VALID_MEMORY_TYPES
   # 保留 re-export，engine 层 22 个文件零修改
   ```

3. 修改 6 个反向依赖文件的导入路径：
   - `storage/cognitive_interface.py`: `from ontology_engine.storage.models import VALID_MEMORY_TYPES`
   - `storage/cognitive_storage.py`: `from ontology_engine.storage.models import CognitiveNode`
   - `storage/legacy_adapter.py`: `from ontology_engine.storage.models import CognitiveNode`
   - `storage/sqlite/cognitive_adapter.py`: `from ontology_engine.storage.models import CognitiveNode`
   - `storage/vector/chromadb_adapter.py`: `from ontology_engine.storage.models import CognitiveNode`
   - `storage/local/fts5_manager.py`: `from ontology_engine.storage.models import CognitiveNode`（TYPE_CHECKING 内）

**影响范围**：

| 文件 | 变更类型 | 风险 |
|------|---------|------|
| `storage/models.py` | 新建 | 低 |
| `engine/cognitive/models.py` | 改为 re-export | 低（接口不变） |
| 6 个 storage 文件 | 导入路径变更 | 低（仅 import 行） |

**验证**：

- [ ] `grep -r "from ontology_engine.engine" ontology_engine/storage/ --include="*.py"` 返回 0 结果
- [ ] `pytest tests/unit/ -v` 全部通过
- [ ] `mypy ontology_engine/storage/ --strict` 无新增错误
- [ ] engine/ 层所有文件导入 `CognitiveNode` 仍正常工作

---

### Stage 2: 知识资产 CRUD 补齐

**目标**：补齐实体/关系的 Update/Delete 操作，实现 AGENT 对知识资产的完整生命周期管理。

**对应设计要求**：
- `docs/02-design/agent-memory/consolidation-engine.md` 三动作模型（Create/Update/Delete）
- `docs/02-design/services/README.md` IncrementalUpdateService
- `docs/02-design/api/README.md` REST API 五大路由组

#### 2-1: Storage 层补齐

**当前状态**：
- `StorageBackend` 已有 `delete_entity()`，但 `update_entity()` 缺失
- `StorageBackend` 缺少 `update_relation()` 和 `delete_relation()`

**具体步骤**：

1. 在 `storage/base.py` 的 `StorageBackend` 中添加抽象方法：
   ```python
   @abstractmethod
   async def update_entity(self, space_id: str, entity_id: str, updates: dict) -> EntityInstance | None: ...
   
   @abstractmethod
   async def update_relation(self, space_id: str, relation_id: str, updates: dict) -> RelationInstance | None: ...
   
   @abstractmethod
   async def delete_relation(self, space_id: str, relation_id: str) -> bool: ...
   ```

2. 在 `storage/sqlite/store.py` 的 `SQLiteStorage` 中实现上述 3 个方法

3. 在 `storage/graph/kuzu_store.py` 的 `KuzuGraphStore` 中实现（Cypher UPDATE/DELETE）

4. 确保 `DualWriteCoordinator` 覆盖 update/delete 的双写同步

**验证**：
- [ ] `SQLiteStorage.update_entity()` 单元测试通过
- [ ] `SQLiteStorage.update_relation()` 单元测试通过
- [ ] `SQLiteStorage.delete_relation()` 单元测试通过
- [ ] `KuzuGraphStore` 对应方法单元测试通过
- [ ] `DualWriteCoordinator` 双写同步测试通过

#### 2-2: Service 层补齐

**具体步骤**：

1. 在 `services/space_service.py`（或对应的实体管理 Service）中添加：
   ```python
   async def update_entity(self, space_id: str, entity_id: str, updates: dict) -> EntityInstance: ...
   async def delete_entity(self, space_id: str, entity_id: str) -> bool: ...
   async def update_relation(self, space_id: str, relation_id: str, updates: dict) -> RelationInstance: ...
   async def delete_relation(self, space_id: str, relation_id: str) -> bool: ...
   ```

2. Service 层编排逻辑：
   - `update_entity`：调用 storage 层 update → 触发影响分析 → 更新受影响的规则/指标
   - `delete_entity`：调用 storage 层 delete → 级联删除关联关系 → 触发影响分析
   - `update_relation`：调用 storage 层 update → 触发影响分析
   - `delete_relation`：调用 storage 层 delete → 触发影响分析

**验证**：
- [ ] Service 层 CRUD 方法单元测试通过
- [ ] 影响分析触发正确

#### 2-3: API 层补齐

**具体步骤**：

1. 在 `api/routes/management.py` 中添加端点：
   ```
   PATCH  /v1/spaces/{space_id}/entities/{entity_id}     → update_entity
   DELETE /v1/spaces/{space_id}/entities/{entity_id}     → delete_entity
   PATCH  /v1/spaces/{space_id}/relations/{relation_id}  → update_relation
   DELETE /v1/spaces/{space_id}/relations/{relation_id}  → delete_relation
   ```

2. 使用 `Depends()` 注入 Service，与现有端点风格一致

3. 添加请求体模型（Pydantic）和响应模型

**验证**：
- [ ] API 端点单元测试通过
- [ ] 请求/响应模型类型检查通过
- [ ] 错误处理覆盖（404/409/422）

#### 2-4: MCP 工具补齐

**具体步骤**：

1. 在 `mcp/` 目录下的工具定义中添加：
   - `oe_update_entity`：更新实体属性
   - `oe_delete_entity`：删除实体
   - `oe_update_relation`：更新关系属性
   - `oe_delete_relation`：删除关系

2. 工具参数设计遵循 AGENT 易用原则：
   - `oe_update_entity(space_id, entity_id, attributes: dict)` — 仅需指定变更字段
   - `oe_delete_entity(space_id, entity_id, cascade: bool = False)` — 可选级联删除
   - `oe_update_relation(space_id, relation_id, attributes: dict)`
   - `oe_delete_relation(space_id, relation_id)`

**验证**：
- [ ] MCP 工具注册成功
- [ ] 工具调用端到端测试通过
- [ ] AGENT 可通过 MCP 完成完整 CRUD 操作

**整体验收标准**：

- [ ] 从 storage → service → api → mcp 四层 CRUD 全链路贯通
- [ ] `pytest tests/unit/ -v` 全部通过
- [ ] `mypy ontology_engine/ --strict` 无新增错误
- [ ] 模块边界合规：api 只调 services，services 只调 engine/storage

---

### Stage 3: COG_SUPPORTED_BY 边 + 检索路径修复

**目标**：实现知识溯源链路，修复 Analytical 查询和 FTS5 BM25 缺失。

**对应 RFC**：RFC-020 G3（COG_SUPPORTED_BY）、RFC-023 G19/G20

#### 3-1: COG_SUPPORTED_BY 边实现

**设计要求**（来源：`memory-api.md` 认知边类型清单）：

COG_SUPPORTED_BY 是知识溯源的核心边类型，表示"某认知节点由哪些证据支撑"。

**具体步骤**：

1. 在 `storage/graph/kuzu_store.py` 中定义 COG_SUPPORTED_BY 边表：
   ```cypher
   CREATE REL TABLE COG_SUPPORTED_BY (
       FROM CognitiveNode TO CognitiveNode,
       evidence_type STRING,  -- direct|inferred|compiled
       confidence REAL DEFAULT 1.0,
       created_at STRING
   )
   ```

2. 在以下 3 处创建 COG_SUPPORTED_BY 边：
   - `remember_service.py` → `_remember()` → `execute_create()`：新节点 → 支撑碎片
   - `remember_service.py` → `_remember()` → `execute_update()`：更新节点 → 新支撑碎片
   - `consolidation_service.py` → 巩固时：编译节点 → 源碎片

3. 在 `recall_service.py` 中实现证据链展开：
   - 沿 COG_SUPPORTED_BY 反向遍历，获取完整证据链
   - 支持深度限制（默认 depth=3）

**验证**：
- [ ] remember 创建节点时自动创建 COG_SUPPORTED_BY 边
- [ ] 证据链遍历返回完整路径
- [ ] 边的 confidence 和 evidence_type 正确

#### 3-2: Analytical 查询修复

**问题**：Analytical 查询路由返回空结果。

**具体步骤**：

1. 在 `recall_service.py` 或 `query_service.py` 中修复 analytical 查询路径：
   - 路由到 `rrf_fusion` 的 analytical 路径
   - 确保 DispositionProfile 权重影响排序

2. 添加降级链路径切换（RFC-023 G21）：
   ```python
   DEGRADATION_PATHS = {
       "semantic": ["vector", "bm25", "substring"],
       "analytical": ["graph_traversal", "vector", "bm25"],
       "hybrid": ["rrf_fusion", "vector", "bm25"],
   }
   ```

**验证**：
- [ ] Analytical 查询返回非空结果
- [ ] 降级链在主路径失败时自动切换

#### 3-3: FTS5 BM25 双表索引

**问题**：FTS5 BM25 索引缺失，关键词搜索质量差。

**具体步骤**：

1. 在 `storage/sqlite/cognitive_adapter.py` 中创建双表 FTS5 索引：
   ```sql
   CREATE VIRTUAL TABLE cognitive_nodes_fts USING fts5(
       content, entity_name,
       content='cognitive_nodes',
       content_rowid='rowid'
   );
   CREATE VIRTUAL TABLE knowledge_fragment_fts USING fts5(
       content,
       content='knowledge_fragments',
       content_rowid='rowid'
   );
   ```

2. 在 `storage/local/fts5_manager.py` 中添加 BM25 搜索方法：
   - 支持 jieba 中文分词（可选）
   - BM25 评分排序
   - 自动索引重建触发器

3. 将 BM25 结果接入 RRF 融合管线

**验证**：
- [ ] FTS5 BM25 搜索返回带评分的结果
- [ ] 中文分词（jieba）可选启用
- [ ] BM25 结果参与 RRF 融合
- [ ] 索引自动重建在数据变更后触发

#### 3-4: Recall 检索管线 10 步补齐

**设计要求**（来源：`memory-api.md` recall 完整检索管线）：

```
recall 检索管线 10 步：
  1. 类型过滤        → memory_type 过滤
  2. 置信度过滤      → confidence ≥ threshold
  3. 信念状态过滤    → belief_status ∈ {accepted, pending_review}
  4. 可见性过滤      → visibility ∈ {shared, private(仅自己)}
  5. Disposition 过滤 → DispositionProfile 7维度动态权重影响排序
  6. 时序评分        → valid_from/valid_to 有效期 + 时序衰减
  7. RRF 融合        → 向量/图/BM25/Temporal 四路融合
  8. 证据链展开      → 沿 COG_SUPPORTED_BY 反向遍历
  9. Token 预算裁剪  → 按 Token 限制截断结果
  10. 返回           → 结构化返回 + 证据链
```

**当前状态**：仅实现了基础检索（步骤 1/7/10），步骤 2-6/8-9 缺失。

**具体步骤**：

1. 在 `recall_service.py` 中实现完整的 10 步管线：
   ```python
   async def recall(self, space_id: str, query: str, **kwargs) -> RecallResult:
       # Step 1: 类型过滤
       candidates = await self._filter_by_type(raw_results, kwargs.get("memory_types"))
       # Step 2: 置信度过滤
       candidates = [c for c in candidates if c.confidence >= kwargs.get("min_confidence", 0.5)]
       # Step 3: 信念状态过滤
       candidates = [c for c in candidates if c.belief_status in {"accepted", "pending_review"}]
       # Step 4: 可见性过滤
       candidates = self._filter_visibility(candidates, kwargs.get("user_id"))
       # Step 5: Disposition 动态权重
       candidates = self._apply_disposition_weights(candidates, space_id)
       # Step 6: 时序评分
       candidates = self._apply_temporal_scoring(candidates)
       # Step 7: RRF 融合（已在 CognitiveStorage 中实现）
       fused = await self._storage.search(SearchQuery(...))
       # Step 8: 证据链展开
       for c in fused:
           c.evidence_chain = await self._traverse_evidence(c.id, depth=3)
       # Step 9: Token 预算裁剪
       final = self._trim_to_token_budget(fused, kwargs.get("max_tokens", 4096))
       # Step 10: 返回
       return RecallResult(memories=final, total=len(fused))
   ```

2. 实现 DispositionProfile 7 维度动态权重：
   - 7 维度：recency_bias, confidence_weight, evidence_weight, source_trust_weight, domain_relevance, task_alignment, novelty_bonus
   - 加载策略：scene → default → 基础权重
   - 权重影响检索排序分数

3. 实现 valid_from/valid_to 有效期过滤：
   - 过滤已过期的记忆（valid_to < now）
   - 时序衰减评分：越近期的记忆权重越高

4. 实现 Token 预算裁剪：
   - 按优先级排序后截断
   - 保留证据链摘要

**验证**：
- [ ] 10 步管线全部实现
- [ ] DispositionProfile 7 维度权重影响排序
- [ ] valid_from/valid_to 过滤生效
- [ ] Token 预算裁剪不破坏证据链
- [ ] 端到端：`oe_recall("query")` 返回含证据链的裁剪结果

**整体验收标准**：

- [ ] COG_SUPPORTED_BY 边在 remember/consolidate 时自动创建
- [ ] 证据链可遍历
- [ ] Analytical 查询返回有效结果
- [ ] BM25 搜索质量可测量（P@5/R@5）

---

### Stage 4: 策略性遗忘 + 遗忘因子修正

**目标**：实现否定信号驱动的策略性遗忘，修正遗忘因子计算偏差。

**对应 RFC**：RFC-022 G10/G13/G14/G15

#### 4-1: 策略性遗忘实现

**设计要求**（来源：`memory-lifecycle.md`）：

遗忘策略 5 级：软衰减 → 类型降级 → 归档 → 硬删除 → 保护

策略性遗忘由否定信号驱动：
- `superseded`：strength × 0.5
- `rejected`：strength × 0.2 + valid_to 提前 + 级联 stale 标记

**具体步骤**：

1. 在 `engine/cognitive/maintenance_service.py` 中实现 5 级遗忘策略：
   ```python
   class ForgettingStrategy(Enum):
       SOFT_DECAY = "soft_decay"         # strength 衰减，不改变类型
       TYPE_DEMOTE = "type_demote"       # cognitive_layer 降级（opinion→observation）
       ARCHIVE = "archive"               # 标记 archived，不参与检索
       HARD_DELETE = "hard_delete"       # 物理删除
       PROTECT = "protect"               # 保护标记，永不遗忘
   
   async def apply_forgetting(self, space_id: str, node_id: str, strategy: ForgettingStrategy) -> None:
       if strategy == ForgettingStrategy.SOFT_DECAY:
           node.strength *= self._decay_factor(node)
       elif strategy == ForgettingStrategy.TYPE_DEMOTE:
           node.cognitive_layer = self._demote_layer(node.cognitive_layer)
       elif strategy == ForgettingStrategy.ARCHIVE:
           node.visibility = "archived"
       elif strategy == ForgettingStrategy.HARD_DELETE:
           await self._storage.delete_node(node_id, soft=False)
       elif strategy == ForgettingStrategy.PROTECT:
           node.tags["protected"] = True
   ```

2. 实现策略性遗忘（否定信号驱动）：
   ```python
   async def strategic_forget(self, space_id: str, signal: ForgettingSignal) -> None:
       if signal.type == "superseded":
           node.strength *= 0.5
       elif signal.type == "rejected":
           node.strength *= 0.2
           node.valid_to = now()
           await self._cascade_stale_mark(space_id, node.id)
   ```

3. 实现 `_cascade_stale_mark()`：BFS 遍历 SUMMARIZED_AS/CONSOLIDATED_INTO/COGNITIVE_RELATES_TO 边，标记下游节点为 stale

4. 防风暴机制：>100 节点需审批

**验证**：
- [ ] 5 级遗忘策略全部实现
- [ ] superseded 信号正确降低 strength
- [ ] rejected 信号正确降低 strength + 提前过期 + 级联标记
- [ ] 级联标记遵循边类型
- [ ] >100 节点触发审批
- [ ] 保护标记的记忆永不遗忘

#### 4-1b: Ebbinghaus 衰减实现

**设计要求**（来源：`memory-lifecycle.md` 遗忘 = 价值感知 Ebbinghaus 衰减）：

**具体步骤**：

1. 在 `maintenance_service.py` 中实现 Ebbinghaus 衰减函数：
   ```python
   def ebbinghaus_decay(self, node: CognitiveNode) -> float:
       days_since_access = (now() - node.last_accessed_at).days
       # 基础衰减率（基于 strength 而非 confidence）
       base_rate = 0.01 * (1.0 - node.strength)
       # confirmation 因子修正
       days_since_confirm = (now() - node.last_confirmed_at).days
       confirmation_factor = math.exp(-0.05 * days_since_confirm)
       # Ebbinghaus 衰减
       retention = math.exp(-base_rate * days_since_access * confirmation_factor)
       return retention
   ```

2. 在 DreamCycle 中集成衰减检查：
   - 每日运行衰减计算
   - strength 低于阈值（0.1）的记忆自动降级
   - strength 低于极低阈值（0.01）的记忆标记归档

**验证**：
- [ ] Ebbinghaus 衰减计算与设计文档一致
- [ ] 衰减率基于 strength（非 confidence）
- [ ] confirmation 因子使用 exp(-0.05 × days)
- [ ] DreamCycle 自动触发衰减

#### 4-2: 遗忘因子修正

**问题**：
- G13：confirmation 因子用 `days_since_confirm` 但计算偏差
- G14：衰减率选择用 `confidence` 而非 `strength`

**具体步骤**：

1. 修正 confirmation 因子：`exp(-0.05 × days_since_confirm)`
2. 修正衰减率选择：使用 `strength` 而非 `confidence` 作为衰减基准
3. 修正 CorrectionPropagation 下游差异化：
   - `mental_model` → `is_stale`
   - `entity` → `needs_attribute_update`
   - `observation` → `needs_reinduction`

**验证**：
- [ ] confirmation 因子计算与设计文档一致
- [ ] 衰减率基于 strength
- [ ] CorrectionPropagation 差异化传播正确

---

### Stage 5: IngestionService 双层写入

**目标**：实现 remember() 编排链的完整 6 步，打通 Layer-R/Layer-S 双层写入。

**对应 RFC**：RFC-020 G1（核心 GAP）

**设计要求**（来源：`memory-api.md` remember 编排链）：

```
remember() 编排链 6 步：
  1. DeduplicationGate    → 去重 + 矛盾前置检测
  2. IngestionService     → 创建 KnowledgeFragment (Layer-R) + ChromaDB 向量索引
  3. ExtractionPipeline   → 从碎片提取 entities/relations
  4. EntityResolver       → 实体消歧（L1 精确 + L2 模糊 + L3 LLM）
  5. CognitiveNode 创建   → Layer-S 写入 + COG_SUPPORTED_BY 边
  6. Consolidation 触发   → 异步巩固
```

**当前状态**：步骤 2-3 未实现，remember() 直接创建 CognitiveNode 跳过了 Layer-R。

#### 5-1: KnowledgeFragment 数据模型

**具体步骤**：

1. 在 `storage/models.py` 中定义 `KnowledgeFragment`：
   ```python
   @dataclass
   class KnowledgeFragment:
       id: str
       space_id: str
       content: str
       source_type: str          # text|document|api
       embedding: list[float] | None
       metadata: dict[str, Any]
       created_at: str
       _store: str = "chromadb"  # Layer-R 默认存储
   ```

2. 在 `storage/cognitive_interface.py` 的 `StorageRouting` 中添加 fragment 路由

3. 在 `storage/vector/chromadb_adapter.py` 中实现 fragment 的向量存储

**验证**：
- [ ] KnowledgeFragment 可存储到 ChromaDB
- [ ] fragment 向量检索可用

#### 5-2: IngestionService 实现

**具体步骤**：

1. 在 `engine/cognitive/ingestion_service.py` 中实现：
   ```python
   async def ingest(self, space_id: str, content: str, **kwargs) -> KnowledgeFragment:
       fragment = KnowledgeFragment(
           id=generate_fragment_id(),
           space_id=space_id,
           content=content,
           ...
       )
       await self._storage.save_node(fragment)  # 路由到 ChromaDB
       return fragment
   ```

2. 修改 `remember_service.py` 的编排链：
   ```python
   async def _remember(self, ...):
       # Step 1: DeduplicationGate
       dedup_result = await self._dedup_gate.check(...)
       # Step 2: IngestionService (Layer-R)
       fragment = await self._ingestion.ingest(...)
       # Step 3: ExtractionPipeline
       extracted = await self._extraction.extract(fragment)
       # Step 4: EntityResolver
       resolved = await self._resolver.resolve(extracted)
       # Step 5: CognitiveNode (Layer-S) + COG_SUPPORTED_BY
       node = await self._create_cognitive_node(resolved, fragment.id)
       # Step 6: Consolidation trigger
       await self._trigger_consolidation(...)
   ```

**验证**：
- [ ] remember() 创建 KnowledgeFragment (Layer-R)
- [ ] remember() 创建 CognitiveNode (Layer-S)
- [ ] COG_SUPPORTED_BY 边连接 CognitiveNode → KnowledgeFragment
- [ ] recall 可从 Layer-R 和 Layer-S 双路检索

#### 5-3: ExtractionPipeline 实现

**具体步骤**：

1. 在 `engine/cognitive/` 下实现提取管线：
   - 从 KnowledgeFragment 提取 entities 和 relations
   - 支持三种通道：规则提取、LLM 提取、混合提取

2. 提取结果传递给 EntityResolver 进行消歧

**验证**：
- [ ] 规则提取通道可用
- [ ] LLM 提取通道可用（降级到规则）
- [ ] 提取结果可传递给 EntityResolver

**整体验收标准**：

- [ ] remember 编排链 6 步全部实现
- [ ] Layer-R (KnowledgeFragment) + Layer-S (CognitiveNode) 双写
- [ ] COG_SUPPORTED_BY 边连接两层
- [ ] recall 可从两层检索
- [ ] 端到端测试：`oe_remember(text)` → `oe_recall(query)` 返回含证据链的结果

---

### Stage 6: LLM 反思混合模式

**目标**：实现 ReflectAgent 的 LLM 调用循环，混合模式（规则 + LLM）。

**对应 RFC**：RFC-022 G11/G12

#### 6-1: LLM 反思混合模式

**设计要求**（来源：`memory-lifecycle.md` ReflectAgent）：

```
混合模式：
  规则矛盾检测 (always) → LLM 反思循环 (if available) → 合并去重
```

**具体步骤**：

1. 在 `engine/cognitive/reflect_orchestrator.py` 中实现：
   ```python
   async def reflect(self, space_id: str, query: str, **kwargs) -> ReflectResult:
       # Phase 1: 规则矛盾检测 (always)
       rule_contradictions = await self._detect_contradictions(space_id)
       
       # Phase 2: LLM 反思循环 (if available)
       if self._llm_available():
           llm_insights = await self._llm_reflect(space_id, query)
           # 合并去重
           contradictions = self._merge_dedup(rule_contradictions, llm_insights)
       else:
           contradictions = rule_contradictions
       
       # Phase 3: 自动裁决
       resolutions = await self._arbitrate(contradictions)
       return ReflectResult(contradictions=contradictions, resolutions=resolutions)
   ```

2. LLM 反思循环实现：
   - 按类型权重递减检索（mental_model > entity > observation > fragment）
   - LLM 分析矛盾并生成修正建议
   - 降级：LLM 不可用时仅使用规则检测

**验证**：
- [ ] 规则矛盾检测始终运行
- [ ] LLM 可用时调用 LLM 反思
- [ ] LLM 不可用时降级为纯规则
- [ ] 合并去重正确

#### 6-2: DreamCycle Phase5 修正

**问题**：DreamCycle Phase5 偏离设计（词重叠候选 → LLM 验证 → 创建边）。

**具体步骤**：

1. 修正 Phase5 实现：
   - 词重叠生成候选边
   - LLM 验证候选边的语义合理性
   - 验证通过后创建边

**验证**：
- [ ] Phase5 生成候选边
- [ ] LLM 验证候选边
- [ ] 验证通过的边被创建

---

### Stage 7: 认知存储接口收敛 + FTS5 抽象

**目标**：渐进收敛认知存储双轨接口，抽象 FTS5 全文搜索。

**对应设计要求**：
- `docs/02-design/storage/interfaces.md` 三接口分离
- 用户确认：渐进收敛策略

#### 7-1: 认知存储接口收敛

**策略**：渐进收敛，不一次性废弃 `CognitiveStorageBackend`。

**具体步骤**：

1. **Phase A（标记废弃）**：
   - 在 `CognitiveStorageBackend` 类和其方法上添加 `DeprecationWarning`
   - 在文档中标注 `CognitiveStorageBackend` 为 `[已过期入口]`
   - 新代码统一使用 `StorageInterface`

2. **Phase B（桥接完善）**：
   - 确保 `LegacyStorageAdapter` 完整桥接所有 `CognitiveStorageBackend` 方法到 `StorageInterface`
   - 添加桥接层的单元测试

3. **Phase C（迁移调用方）**：
   - 逐个将 `CognitiveRepository` 等调用方从 `CognitiveStorageBackend` 迁移到 `StorageInterface`
   - 每迁移一个调用方，确保测试通过

4. **Phase D（移除旧接口）**：
   - 当所有调用方都迁移后，移除 `CognitiveStorageBackend`
   - 移除 `LegacyStorageAdapter`

**验证**：
- [ ] Phase A：DeprecationWarning 正确触发
- [ ] Phase B：桥接层测试覆盖所有方法
- [ ] Phase C：每个调用方迁移后测试通过
- [ ] Phase D：旧接口完全移除

#### 7-2: FTS5 全文搜索抽象

**具体步骤**：

1. 在 `storage/base.py` 中新增 `FTSBackend` ABC：
   ```python
   class FTSBackend(ABC):
       @abstractmethod
       async def index_document(self, doc_id: str, content: str, metadata: dict) -> None: ...
       
       @abstractmethod
       async def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[SearchResult]: ...
       
       @abstractmethod
       async def delete_document(self, doc_id: str) -> None: ...
       
       @abstractmethod
       async def rebuild_index(self) -> None: ...
   ```

2. 将 `FTS5Manager` 重构为 `SQLiteFTSBackend(FTSBackend)` 实现

3. 未来可扩展 `ElasticsearchFTSBackend` 等

**验证**：
- [ ] `FTSBackend` 抽象接口定义完整
- [ ] `SQLiteFTSBackend` 实现所有抽象方法
- [ ] 现有 FTS5 功能不受影响

#### 7-3: 存储三接口分离 + 工厂模式

**设计要求**（来源：`docs/02-design/storage/interfaces.md`）：

存储层应按职责分离为三个正交接口 + 工厂模式创建：
- `GraphStore`：图拓扑 CRUD + Cypher + 图算法
- `VectorStore`：向量索引 + ANN 搜索
- `MetaStore`：Schema 版本 + 审计日志 + 管道状态 + 文件哈希 + 矛盾报告

**当前状态**：`StorageBackend` 是 8 个子接口的聚合（30+ 方法），职责过重；`GraphStoreBackend` 和 `VectorStoreBackend` 已存在但与 `StorageBackend` 的关系不清晰。

**具体步骤**：

1. 确认现有接口与设计文档的映射：
   - `GraphStoreBackend` → 对应设计文档 `GraphStore`（已存在，需确认方法完整性）
   - `VectorStoreBackend` → 对应设计文档 `VectorStore`（已存在，需确认方法完整性）
   - `StorageBackend` → 需拆分出 `MetaStore` 子接口

2. 从 `StorageBackend` 中提取 `MetaStore` 接口：
   ```python
   class MetaStore(ABC):
       """事务元数据 + Schema版本 + 审计日志 + 管道状态 + 文件哈希 + 矛盾报告"""
       @abstractmethod
       async def get_schema_version(self, space_id: str) -> str | None: ...
       @abstractmethod
       async def set_schema_version(self, space_id: str, version: str) -> None: ...
       @abstractmethod
       async def log_audit(self, space_id: str, action: str, details: dict) -> None: ...
       @abstractmethod
       async def get_pipeline_state(self, space_id: str) -> dict | None: ...
       @abstractmethod
       async def save_file_hash(self, space_id: str, file_path: str, hash: str) -> None: ...
       @abstractmethod
       async def save_contradiction_report(self, space_id: str, report: dict) -> None: ...
   ```

3. 实现工厂模式：
   ```python
   def create_graph_store(config: StorageConfig) -> GraphStoreBackend: ...
   def create_vector_store(config: StorageConfig) -> VectorStoreBackend: ...
   def create_meta_store(config: StorageConfig) -> MetaStore: ...
   ```

4. 确认 `StorageBackend` 保留的职责（EntityStorage + MetricStorage + CategoryStorage + DatasetStorage + VersionStorage + DimensionStorage + ChangeStorage），作为"实体/指标/分类/数据集"的统一 CRUD 接口

**验证**：
- [ ] GraphStore / VectorStore / MetaStore 三接口与设计文档对齐
- [ ] 工厂模式创建各存储实例
- [ ] 上层只依赖接口，不依赖具体实现
- [ ] `StorageBackend` 职责明确（实体/指标 CRUD）

---

### Stage 8: 模型补齐 + 补偿日志持久化 + Examples 同步

**目标**：补齐 CognitiveNode 12 个缺失字段，持久化补偿日志，同步 Examples。

**对应 RFC**：RFC-024 Phase 4（字段补齐）

#### 8-1: CognitiveNode 字段补齐

**设计要求**（来源：`memory-hierarchy.md` CognitiveNode 核心字段）：

缺失的 12 个字段：
1. `strength` — 记忆强度（衰减计算基准）
2. `entity_name` — 实体名称（消歧用）
3. `entity_type` — 实体类型
4. `version` — 版本号（OCC 并发控制）
5. `last_confirmed_at` — 最后确认时间
6. `consolidation_reasoning` — 巩固推理过程
7. `compiled_at` — 编译时间
8. `model_domain` — 模型域（已迁移到 tags，但保留字段兼容）
9. `source_trust_tier` — 来源可信层级
10. `scope` — 作用域
11. `source_pipeline` — 来源管线
12. `source_content_hash` — 内容哈希

**具体步骤**：

1. 在 `storage/models.py` 的 `CognitiveNode` 中添加 12 个字段（带默认值）

2. KuzuDB Schema 迁移：
   ```cypher
   ALTER TABLE cognitive_node ADD PROPERTY strength DOUBLE DEFAULT 1.0;
   ALTER TABLE cognitive_node ADD PROPERTY entity_name STRING DEFAULT NULL;
   -- ... 逐字段添加
   ```

3. SQLite cognitive_nodes 表迁移：
   ```sql
   ALTER TABLE cognitive_nodes ADD COLUMN strength REAL DEFAULT 1.0;
   ALTER TABLE cognitive_nodes ADD COLUMN entity_name TEXT;
   -- ... 逐字段添加
   ```

4. ChromaDB metadata 扩展（新增字段纳入 metadata）

**验证**：
- [ ] CognitiveNode 包含所有 32+ 字段
- [ ] KuzuDB Schema 迁移成功
- [ ] SQLite 表迁移成功
- [ ] 现有数据兼容（新字段有默认值）

#### 8-2: DualWriteCoordinator 补偿日志持久化

**问题**：`_compensation_log` 仅在内存中，进程崩溃丢失。

**具体步骤**：

1. 在 SQLite 中创建补偿日志表：
   ```sql
   CREATE TABLE compensation_log (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       operation TEXT NOT NULL,
       target_engine TEXT NOT NULL,
       target_id TEXT NOT NULL,
       compensation_action TEXT NOT NULL,
       created_at TEXT NOT NULL,
       status TEXT DEFAULT 'pending'
   );
   ```

2. 修改 `DualWriteCoordinator`：写入操作时同步写入补偿日志到 SQLite

3. 启动时检查未完成的补偿日志并执行

**验证**：
- [ ] 补偿日志持久化到 SQLite
- [ ] 进程重启后未完成的补偿操作自动执行
- [ ] 补偿完成后日志状态更新

#### 8-3: Examples 样例同步

**具体步骤**：

1. 修复 `examples/agent_memory/01-10/` 中的导入路径变化
2. 修复 API 签名变化（consolidate/forget 路径改为 `/_internal/`）
3. 验证每个样例可运行

**验证**：
- [ ] 所有 examples 可运行
- [ ] 评估结果与预期一致

---

## 四、跨阶段一致性检查

### 4.1 与设计文档的对齐验证

| 设计要求 | 对应 Stage | 验证方式 |
|---------|-----------|---------|
| 模块边界：storage/ 不依赖上层 | Stage 1 | `grep -r "from ontology_engine.engine" ontology_engine/storage/` |
| 三动作模型：Create/Update/Delete | Stage 2 | API + MCP 端到端测试 |
| 双层存储：Layer-R + Layer-S | Stage 5 | remember 双写测试 |
| COG_SUPPORTED_BY 边 | Stage 3 | 证据链遍历测试 |
| RRF 四路融合 | Stage 3 | 检索验收测试 |
| Recall 检索管线 10 步 | Stage 3-4 | 端到端 recall 测试 |
| DispositionProfile 7 维度 | Stage 3 | 权重影响检索排序验证 |
| 遗忘策略 5 级 + Ebbinghaus 衰减 | Stage 4 | 遗忘因子计算验证 |
| 策略性遗忘（否定信号驱动） | Stage 4 | superseded/rejected 信号测试 |
| LLM 反思混合模式 | Stage 6 | 反思降级测试 |
| CognitiveNode 完整字段 | Stage 8 | Schema 迁移验证 |
| valid_from/valid_to 过滤 | Stage 3 | 有效期查询测试 |
| 存储三接口分离 + 工厂模式 | Stage 7 | 接口对齐验证 |
| FTS5 抽象接口 | Stage 7 | FTSBackend 实现验证 |
| 认知存储接口收敛 | Stage 7 | 旧接口废弃验证 |
| DeduplicationGate 写入前治理 | Stage 5 | 去重+矛盾前置测试 |
| 实体消歧三级（L1/L2/L3） | Stage 5 | 消歧准确率测试 |
| CorrectionPropagation 差异化 | Stage 4 | 下游传播验证 |
| DreamCycle 5→6 阶段 | Stage 6 | 阶段独立执行测试 |

### 4.2 与 ROADMAP 5 个严重一致性问题的覆盖

| 问题 | 覆盖 Stage | 说明 |
|------|-----------|------|
| S-1: TRACE_TO 源端类型不一致 | Stage 3 | COG_SUPPORTED_BY 实现时统一边类型 |
| S-2: DEFINED_IN 不支持 MetricDeclaration | Stage 2 | CRUD 补齐时修复 |
| S-3: API 旧术语 concept_type | Stage 2 | API 层补齐时统一术语 |
| S-4: API 查询缺少时序参数 | Stage 3 | 检索路径修复时添加 |
| S-5: KuzuDB 未定义 7 种时序边表 | Stage 3 | COG_SUPPORTED_BY 实现时补齐 |

### 4.3 质量门禁

每个 Stage 完成后必须通过：

```bash
mypy ontology_engine/ --strict
ruff check ontology_engine/
pytest tests/unit/ -v --cov=ontology_engine --cov-report=term-missing
```

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| CognitiveNode 下沉导致循环依赖 | 编译失败 | 使用 re-export 模式，engine 层零修改 |
| KuzuDB ALTER TABLE 不支持某些操作 | 迁移失败 | 预验证 KuzuDB DDL 支持；备选：重建表+数据迁移 |
| 双层写入增加 remember 延迟 | 用户体验下降 | Layer-R 异步写入，不阻塞主路径 |
| LLM 反思循环成本高 | 资源消耗 | 混合模式降级策略；频率限制 |
| 接口收敛期间双轨维护成本 | 开发效率 | Phase A 标记废弃后限制新代码使用旧接口 |
| 补偿日志持久化影响写入性能 | 吞吐量下降 | 批量写入补偿日志；WAL 模式 |

---

## 六、进度追踪

| Stage | 任务 | 状态 | 完成日期 |
|-------|------|------|---------|
| 0 | 运行时 Bug 修复 | ⏳ 待启动 | — |
| 1 | CognitiveNode 模型下沉 | ⏳ 待启动 | — |
| 2 | 知识资产 CRUD 补齐 | ⏳ 待启动 | — |
| 3 | COG_SUPPORTED_BY + 检索路径修复 | ⏳ 待启动 | — |
| 4 | 策略性遗忘 + 遗忘因子修正 | ⏳ 待启动 | — |
| 5 | IngestionService 双层写入 | ⏳ 待启动 | — |
| 6 | LLM 反思混合模式 | ⏳ 待启动 | — |
| 7 | 认知存储接口收敛 + FTS5 抽象 | ⏳ 待启动 | — |
| 8 | 模型补齐 + 补偿日志 + Examples | ⏳ 待启动 | — |

---

## 七、前置文档索引

| 文档 | 作用 |
|------|------|
| `docs-dev/03-rfc/RFC-020` | 记忆生成路径优化（双层写入 + COG_SUPPORTED_BY） |
| `docs-dev/03-rfc/RFC-022` | LLM 反思 + 策略性遗忘 |
| `docs-dev/03-rfc/RFC-023` | 检索路径优化（FTS5 BM25 + Analytical） |
| `docs-dev/03-rfc/RFC-024` | CognitiveNode 模型补齐 + Bug 修复 |
| `docs-dev/03-rfc/RFC-025` | Agent Memory 全旅程优化总览 |
| `docs/02-design/agent-memory/` | 记忆系统详细设计（12 篇） |
| `docs/02-design/storage/` | 存储设计总览 + 接口规范 |
| `docs/02-design/services/` | 服务层设计 |
| `docs/02-design/api/` | API 设计 |
| `docs/ROADMAP.md` | 阶段路线 |
| `docs/STATUS.md` | 文档状态 |
