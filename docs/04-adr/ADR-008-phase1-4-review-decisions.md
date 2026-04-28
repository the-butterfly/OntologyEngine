# ADR-008: Phase 1-4 审查关键决策

| 字段 | 值 |
|------|-----|
| 状态 | accepted |
| 日期 | 2026-04-28 |
| 决策者 | 项目治理审查 |
| 关联 | governance-checklist, Phase 1-4 审查 |

## 背景

Phase 1-4 治理审查发现 10 个严重问题、18 个中等问题和多个不确定项。以下记录审查过程中确认的关键架构决策。

## 决策记录

### D1: CategoryTag 接口统一

**问题**: `StorageBackend.get_category_tags` 被定义两次，返回类型冲突（`list[CategoryTag]` vs `dict[str, str]|None`），后者覆盖前者。

**决策**: 保留 `list[CategoryTag]` 版本作为主接口，旧版 dict 接口重命名为 `get_category_tags_dict`。

**理由**:
- `list[CategoryTag]` 包含完整信息（assigned_at, confidence, assigned_by）
- dict 版本信息量少，仅作为便捷方法保留
- SQLite 实现已遵循此模式

### D2: SchemaService 加载方式

**问题**: API 端点传入 dict 数据，但 `SchemaService.load_schema` 只接受文件路径。

**决策**: 在 `SchemaService` 中新增 `load_schema_from_data(data: dict)` 方法，`load_schema` 保持文件路径语义不变。

**理由**:
- 职责分离：文件加载和数据加载是不同关注点
- 向后兼容：不改变现有 load_schema 签名
- API 层直接调用新方法，无需临时文件 hack

### D3: KuzuGraphStore 异步化

**问题**: KuzuGraphStore 所有操作为同步调用，阻塞事件循环。

**决策**: ~~Phase 1 立即修复~~ **回退**。Kuzu Python binding 不支持多线程访问，`asyncio.to_thread` 导致 segfault。保持同步调用，Phase 2 使用专用线程池或切换到支持异步的图数据库。

**理由**:
- Kuzu 的 `QueryResult.__del__` 在不同线程被调用时触发 segfault
- Kuzu connection 对象不是线程安全的
- 同步调用在当前单用户场景下可接受
- Phase 2 可考虑：a) 专用单线程 executor；b) 连接池 + thread-local；c) 切换到 Neo4j 等支持异步的图数据库

### D4: 时间点查询语义

**问题**: `get_entity_at` 使用 `updated_at` 而非 `valid_from/valid_to` 做时间点查询。

**决策**: 改用 `valid_from/valid_to` 做时间区间过滤，符合 Schema 时态建模语义。

**理由**:
- Schema 设计中 `valid_from/valid_to` 是时态建模的核心字段
- `updated_at` 仅反映记录修改时间，不代表业务有效期
- 需确保 entity_versions 表有这两个字段

### D5: upsert_edge 幂等性

**问题**: `kuzu_store.upsert_edge` 使用 CREATE 而非 MERGE，重复调用产生重复边。

**决策**: 先查询是否存在，再决定 CREATE 或 SET 属性。

**理由**:
- kuzu 的 MERGE 对关系属性的行为需确认，查询后决定更安全
- 保证幂等性，避免重复边
- 逻辑清晰，易于调试

### D6: delete_entity 级联删除

**问题**: SQLite `delete_entity` 缺少级联删除，产生孤立记录。

**决策**: 应用层级联删除，在 `delete_entity` 方法中显式删除所有关联表记录。

**理由**:
- 逻辑清晰，易于理解和维护
- 不依赖数据库外键特性，跨数据库兼容
- 可在删除前添加业务校验

### D7: query_hybrid 返回类型统一

**问题**: `query_hybrid` 的 `independent_then_fuse` 分支返回 ID 列表，其他分支返回完整对象。

**决策**: 所有分支统一返回 `[{id, score, metadata}]` 格式，`independent_then_fuse` 分支补全 metadata。

**理由**:
- API 一致性：调用方无需根据策略判断返回格式
- 前端/客户端代码简化
- metadata 可从 storage 补全

### D8: Kuzu KnowledgeFragment 字段补全

**问题**: kuzu KnowledgeFragment 节点表缺少 chunk_index、vector_id、metadata 字段。

**决策**: 补全 kuzu DDL 字段，同步逻辑中补全字段映射。

**理由**:
- 保证数据完整性，图存储与关系存储一致
- chunk_index 和 vector_id 对知识检索至关重要
- metadata 存储额外属性，支持图查询时的属性过滤

### D9: entity_versions 时态字段

**问题**: `entity_versions` 表缺少 `valid_from`/`valid_to` 字段，`get_entity_at` 使用 `updated_at` 做时间点查询。

**决策**: 在 `entity_versions` 表中添加 `valid_from`/`valid_to` 字段，`get_entity_at` 改用区间查询。

**理由**:
- 与 `entities` 表的时态查询模式一致
- `valid_from`/`valid_to` 表达业务有效时间，`updated_at` 仅是记录修改时间
- 语义更精确：支持"某版本在特定时间区间内有效"的查询

### D10: KnowledgeFragment 图存储支持

**问题**: `upsert_node`/`get_node`/`delete_node` 只处理 Entity 类型，KnowledgeFragment 节点无法写入图存储。`create_mutual_index_edge` 硬编码 `to_label = "Entity"`，不支持 KnowledgeFragment 目标。

**决策**: 扩展三个节点方法支持 KnowledgeFragment 类型，`create_mutual_index_edge` 根据 `edge_type` 和 `from_id` 前缀动态确定 `to_label`。

**理由**:
- `_MUTUAL_INDEX_QUERIES` 中有 4 条查询目标是 KnowledgeFragment
- EXTRACTED_FROM、DEFINED_IN_FROM_METRIC/RULE、TRACE_TO 边需要 KnowledgeFragment 目标
- `get_neighbors` 已有 Entity vs KnowledgeFragment 分支模式

### D11: C-05/C-16 状态判定

**问题**: governance-checklist 中 C-05 和 C-16 状态不明确。

**决策**:
- C-05 标记为"部分完成"：storage 层已实现 CategoryTag 独立记录，engine/categorization 层待对齐
- C-16 拆分为 C-16a（声明层，已完成）和 C-16b（执行层覆盖逻辑，待实现）

### D12: 大型重构项安排

**问题**: P0-3（规则模型双分离）和 P1-1（Step.action 结构化）涉及核心数据模型变更。

**决策**: 作为独立会话执行，先写 RFC 冻结设计，再逐模块迁移。

**理由**:
- 影响面广：executor/dag_executor/pipeline_state 等多个模块
- 需要向后兼容和全量测试验证
- RFC 先行确保设计收敛后再实施

## 影响范围

| 决策 | 影响文件 | 影响层级 |
|------|----------|----------|
| D1 | storage/base.py, storage/sqlite/store.py | Storage |
| D2 | services/schema_service.py, api/routes/ontology.py, core/schema/loader.py | Service + API + Core |
| D3 | storage/graph/kuzu_store.py | Storage |
| D4 | storage/sqlite/store.py | Storage |
| D5 | storage/graph/kuzu_store.py | Storage |
| D6 | storage/sqlite/store.py | Storage |
| D7 | services/query_service.py, storage/retrieval.py | Service + Storage |
| D8 | storage/graph/kuzu_store.py | Storage |
| D9 | storage/sqlite/store.py | Storage |
| D10 | storage/graph/kuzu_store.py | Storage |
| D11 | governance-checklist.md | Docs |
| D12 | docs/03-rfc/ (待创建) | Docs |
