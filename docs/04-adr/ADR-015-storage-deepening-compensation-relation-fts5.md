# ADR-015: 存储层架构深化 — 补偿日志抽象、Relation ID 定位、FTS5 统一异步

| 元数据 | 值 |
|--------|-----|
| 状态 | implemented |
| 日期 | 2026-05-21 |
| 决策者 | architecture-review |
| 关联 ADR | ADR-010（双写策略）、ADR-013（模型校验）、ADR-014（Entity/CognitiveNode 分离） |
| 待审视 | 是 — 两套并行数据修改通道需后续收敛 |

## 上下文

上一轮架构审查（ADR-014 实施后）发现 4 个架构深化机会：

1. **DualWriteCoordinator 补偿日志绕过 StorageBackend 抽象**：直接 `import sqlite3` 操作补偿日志，违反"API 边界封闭"约束（核心约束 #2）。`recover_pending_compensations` 仅覆盖 3 种 operation，其余永远 pending。`save_entity_with_graph` 和 `write_entity` 逻辑重复。
2. **API 层 relation 定位不安全**：PATCH/DELETE relation 端点使用列表 index 定位，并发不安全。`add_relation` 未自动生成 `relation_id`。
3. **FTS5Manager 接口与 FTSBackend ABC 不一致**：`FTSBackend.search` 要求 async，但 `FTS5Manager.search` 是 sync。`index_document` 硬编码 `cognitive_node_fts` 表，无法索引 fragment。两套 API（domain-specific + generic）并存。
4. **7 个模块零测试覆盖**：storage/models.py、FTSBackend、fts5_manager.py、recall_service.py、management.py PATCH/DELETE、entity_service update/delete、mcp management tools。

## 决策

### D15-1: 补偿日志走 CompensationStore 抽象

- 新增 `CompensationStore` ABC（4 个抽象方法：`save_compensation`、`get_pending_compensations`、`mark_compensation_done`、`increment_retry_count`），定义在 `storage/base.py`
- 新增 `LocalCompensationStore`（SQLite 实现），定义在 `storage/local/compensation_store.py`
- `DualWriteCoordinator` 构造函数参数从 `compensation_db_path: str` 改为 `compensation_store: CompensationStore | None`
- 移除 `dual_write.py` 中的 `import sqlite3`，解耦 SQLite 直接依赖

**影响分析**：
- 调用方：零外部调用方传入 `compensation_db_path`，变更无破坏性
- 测试：`test_dual_write.py` 和 `test_dual_write_compensation.py` 均使用新签名，全部兼容
- 文档：RFC-012 伪代码仍引用 `save_entity_with_graph`，需标注过时
- `LocalCompensationStore` 当前零引用（仅定义未集成），需后续在 `storage/local/__init__.py` 导出并打通集成链路

### D15-2: 合并 save_entity_with_graph 和 write_entity

- `save_entity_with_graph` 已删除，功能合并进 `write_entity(entity, relations=None, space_id="default")`
- `write_entity` 现在同时处理 entity 写入 + relation 批量写入 + Graph/Vector 同步 + 补偿记录

**影响分析**：
- 调用方：`save_entity_with_graph` 零外部调用方，变更无破坏性
- `write_entity` 签名向后兼容（`relations` 和 `space_id` 有默认值）

### D15-3: recover_pending_compensations 覆盖全量 operation

- 从 3 种 operation 扩展到 7 种：`graph_upsert`、`sync_to_graph`、`vector_upsert`、`delete_node`、`vector_delete`、`update_relation_graph`、`delete_relation_graph`
- 拆分为 `_recover_entity_operation` 和 `_recover_relation_operation` 两个内部方法
- relation 补偿使用 `target_id` 格式 `from_id:to_id:relation_name` 解析定位

**影响分析**：
- 签名未变，向后兼容
- 新增 4 种 operation 的恢复测试缺失（仅 `graph_upsert` 和 `vector_upsert` 有测试）

### D15-4: Relation 定位改用唯一 ID 替代 index

- `SpaceService.update_relation_in_space` 和 `delete_relation_in_space` 参数从 `relation_index: int` 改为 `relation_id: str`
- API 路由参数从 `{relation_index}` 改为 `{relation_id}`
- `add_relation` 和 `load_instances_from_yaml` 自动生成 `relation_id`（格式 `from_id:to_id:rel_name`）

**影响分析**：
- API 破坏性：旧路径参数 `{relation_index}` (int) 不再有效，外部客户端需适配
- 数据兼容性：存量 `space.instances.relations` 中缺少 `relation_id` 的关系无法被 PATCH/DELETE 定位，需迁移或兼容处理
- `semantic_spaces.py` 的 `create_relation` 端点**遗漏**了自动生成 `relation_id` 逻辑（需修复）
- `relation_index` 旧参数名已在代码库中完全清除，无残留
- 示例文件（instances.yaml、demo_space.json）已包含 `relation_id`，无需修改

### D15-5: FTS5Manager.search 改为 async，消除 fts_search 适配层

- `FTS5Manager.search` 改为 `async`，内部用 `asyncio.to_thread` 包装 `_sync_search`
- `fts_search` 方法已移除（零引用，安全删除）
- `rrf_fusion.py` 调用方已适配为 `await self._fts5_manager.search(query, top_k, filters)`

**影响分析**：
- 所有调用方已使用 `await`，无破坏性变更
- `rrf_fusion.py` 中 `fts5_manager` 类型声明为 `Any`，应改为 `FTSBackend | None`（跨层违规待修）

### D15-6: index_document 增加 source_type 参数

- 通过 `metadata.source_type` 区分 node/fragment，分别路由到 `_index_node` / `_index_fragment`
- 新增 `knowledge_fragment_fts` 虚拟表，与 `cognitive_node_fts` 并存
- `_sync_search` 同时搜索两张表，合并结果

**影响分析**：
- `metadata` 参数可选，`source_type` 默认 `"node"`，向后兼容
- `ingestion_service.py` 对 fragment 仍调用 `on_node_created()` 而非 `on_fragment_created()`，导致 fragment 写入 `cognitive_node_fts` 而非 `knowledge_fragment_fts`（语义不一致，需修复）

### D15-7: rebuild_index 保留清空语义

- `rebuild_index` 仅清空两张 FTS5 表并返回 0
- 实际带数据的重建通过 `rebuild_fts5_if_needed` 执行（基于 diff ratio 触发）

**影响分析**：
- ABC 语义"rebuild"暗示重建，但实现只清空——接口语义与实现行为不匹配
- 调用方需知晓此行为差异

## 已知问题与待审视项

### P1: 两套并行数据修改通道（严重）

| 通道 | 路径 | 同步范围 |
|------|------|----------|
| DualWriteCoordinator | services → DualWriteCoordinator → storage + graph + vector | MetaStore + GraphStore + VectorStore |
| SpaceService | api → SpaceService → SemanticSpaceStorage | 仅 SemanticSpace JSON |

`SpaceService.update_relation_in_space` / `delete_relation_in_space` 走 SpaceService 通道，**不触发 Graph/Vector 同步**。同一业务操作可能产生数据不一致。

此问题非本次变更引入，但 D15-4 的改动使 SpaceService 通道的 relation 操作更易被使用，放大了不一致风险。

**后续方向**：SpaceService 的 relation 操作应通过 DualWriteCoordinator 执行，或将 DualWriteCoordinator 的同步逻辑下沉到 SpaceService。需在后续 ADR 中定义统一写入路径。

### P2: engine 层直接依赖 storage/local 具体实现（跨层违规）

`rrf_fusion.py` 的 `fts5_manager: Any | None` 直接使用 `FTS5Manager` 的具体方法。按模块边界规则 `engine/ → storage/base.py`，engine 应依赖 `FTSBackend` ABC。

**后续方向**：将 `fts5_manager` 改为 `fts_backend: FTSBackend | None`，只通过 ABC 方法交互。FTS5Manager 的领域特定方法（`on_node_created` 等）需提取到适配器或移入 service 层。

### P3: delete_entity 未删除 MetaStore（数据不对称）

`DualWriteCoordinator.delete_entity` 只删 Graph/Vector，不调 `self.storage.delete_entity()`。与 `write_entity` 的"MetaStore 先写"策略不对称。

当前零外部调用方，但一旦被使用将产生孤儿数据。

**后续方向**：在 `delete_entity` 中添加 `await self.storage.delete_entity(...)` 调用，或在方法文档中显式标注"仅清理 Graph/Vector，调用方需自行处理 MetaStore 删除"。

### P4: LocalCompensationStore 四处静默返回（违反约束 #7）

`if self._conn is None: return` / `return []` 在连接关闭后静默失败，不抛异常也不记录降级原因。

**后续方向**：改为抛出 `RuntimeError("CompensationStore is closed")` 或显式记录降级原因。

### P5: semantic_spaces.py create_relation 缺少 relation_id 自动生成

`semantic_spaces.py` 的 `create_relation` 端点直接 `append(relation)` 到 `space.instances.relations`，未检查或自动生成 `relation_id`。通过此端点创建的关系后续无法被 PATCH/DELETE 定位。

**后续方向**：添加与 `management.py` 一致的自动生成逻辑。

### P6: ingestion_service.py fragment 写入表不一致

`ingestion_service.py` 对 fragment 调用 `on_node_created()` 而非 `on_fragment_created()`，导致 fragment 写入 `cognitive_node_fts` 而非 `knowledge_fragment_fts`。

**后续方向**：改为调用 `on_fragment_created()` 或 `index_document(source_type="fragment")`。

## 测试覆盖

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| test_models_contract.py | 35 | CognitiveNode from_dict/to_dict/can_transition_to/__post_init__ 校验 |
| test_fts5_manager.py | 6 | async search、node/fragment 索引、delete、rebuild、space_id 过滤 |
| test_dual_write_compensation.py | 8 | graph/vector 失败补偿、CompensationStore 持久化、恢复、retry |

### 仍缺失的测试

| 模块 | 缺失内容 |
|------|----------|
| dual_write.py | `update_relation` / `delete_relation` 双写测试 |
| dual_write.py | `delete_node` / `vector_delete` / `update_relation_graph` / `delete_relation_graph` 恢复测试 |
| space_service.py | `update_relation_in_space` / `delete_relation_in_space` 测试 |
| management.py | PATCH/DELETE relation 端点 API 测试 |
| compensation_store.py | LocalCompensationStore 集成测试（静默返回路径） |
| fts5_manager.py | `rebuild_fts5_if_needed`、`on_fragment_created/deleted` 直接测试 |
| recall_service.py | evidence fallback 测试 |
| mcp/tools/management.py | 4 个新工具测试 |

## 文档同步清单

| 文档 | 需更新内容 |
|------|-----------|
| docs/02-design/storage/sqlite-tables.md | 补充 compensation_log 表 DDL、knowledge_fragment_fts 虚拟表 DDL |
| docs/02-design/api/README.md | 补充 PATCH relation 端点记录 |
| docs-dev/03-rfc/RFC-012-kuzu-storage.md | 更新 DualWriteCoordinator 伪代码（save_entity_with_graph → write_entity） |
| docs-dev/03-rfc/RFC-023-retrieval-path-optimization.md | 标注 FTS5 双表设计实施状态 |
| docs-baseline/07-phase1-enhancement/01-graph-storage-extension.md | 添加 [已过期入口] 标注 |
| docs/STATUS.md | 新增本 ADR 条目 |
| docs/TODO.md | 新增待审视项和缺失测试条目 |
