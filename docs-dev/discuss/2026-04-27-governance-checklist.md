# 全面治理清单

**创建日期**: 2026-04-27
**状态**: active
**架构决策**: 存储层方案 B→C 渐进迁移（见 2026-04-27-storage-architecture-b-to-c-migration.md）

## 治理流程

每个治理项遵循：**文档修改 → 代码修改 → 测试验证 → 样例跑通**

验证方式：
- 3 个 subagent 并行审查（文档审查员 / 代码审查员 / 测试审查员）
- 2/3 通过即视为完成
- 不一致项弹出确认

---

## Phase 1: 设计文档治理（P0）

### 1.1 术语统一

| ID | 问题 | 影响文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| T-01 | API 路由文档 `concept_type` → `_fact_object` | spaces-routes.md, views-routes.md, actions-routes.md, query-routes.md, ontology-routes.md | 全局替换，保留 alias 兼容 | grep 零命中旧术语 |
| T-02 | API 路由文档 `properties` → `attributes` | spaces-routes.md, ontology-routes.md, storage/interfaces.md | 全局替换 | grep 零命中旧术语 |
| T-03 | API 路由文档 `element_type` → `type` | spaces-routes.md, feedback-service.md | 全局替换 | grep 零命中旧术语 |
| T-04 | storage/interfaces.md `NodeRecord.properties` → `attributes` | storage/interfaces.md | 字段重命名 | 与 Schema v2 术语一致 |

### 1.2 文档内部一致性

| ID | 问题 | 影响文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| D-01 | Formula 双重 [单一事实源] | formula/README.md, formula/06-formula-spec.md | README.md 为 SoT，06-formula-spec.md 标记 [已过期入口] | 仅一个 SoT |
| D-02 | Schema 算子枚举不一致（5 vs 6） | schema/01-schema-spec.md | 补充 FORMULA 算子 | 两文档枚举一致 |
| D-03 | README.md 审视状态与 STATUS.md 不一致 | docs/README.md | 更新 8 个模块状态为 draft | 与 STATUS.md 一致 |
| D-04 | api/README.md status(accepted) vs STATUS.md(draft) | api/README.md, STATUS.md | 统一为 draft | 一致 |
| D-05 | KuzuDB RuleDefinitionNode 与 Schema L4 不对齐 | storage/kuzudb-schema.md | 重设计 RuleDefinitionNode | 字段与 L1-L4-declarations.md 对齐 |
| D-06 | 06-formula-spec.md Bug 标注过时（B-1/B-2 已修复） | formula/06-formula-spec.md, formula/function-library.md | 更新 Bug 状态为已修复 | 与代码一致 |

### 1.3 存储层设计文档更新（方案C架构）

| ID | 问题 | 影响文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| S-01 | 存储架构描述与方案C不一致 | storage/README.md | 重写为方案C架构 | 与决策文档一致 |
| S-02 | 接口定义与代码四接口不一致 | storage/interfaces.md | 增加 RetrievalBackend，标注 StorageBackend 为过渡保留 | 与代码一致 |
| S-03 | SQLite 表设计需增加分库策略 | storage/sqlite-tables.md | 增加分库隔离章节 | 含分库方案 |
| S-04 | ChromaDB → LanceDB 迁移 | storage/chromadb-collections.md | 重命名为 lancedb-collections.md，更新内容 | LanceDB 方案 |
| S-05 | KuzuDB 职责调整为关系存储 | storage/kuzudb-schema.md | 移除实体属性存储，聚焦关系和互索引边 | 与方案C一致 |

### 1.4 缺失设计文档补全

| ID | 缺失文档 | 对应代码 | 优先级 |
|----|---------|---------|--------|
| M-01 | datasets 路由设计 | api/routes/datasets.py | P1 |
| M-02 | categories 路由设计 | api/routes/categories.py | P1 |
| M-03 | incremental 路由设计 | api/routes/incremental.py | P1 |
| M-04 | ingestion 路由设计 | api/routes/ingestion.py | P1 |
| M-05 | simulation 路由设计 | api/routes/simulation.py | P2 |
| M-06 | RuleService 详细设计 | services/rule_service.py | P1 |
| M-07 | SpaceService 详细设计 | services/space_service.py | P1 |
| M-08 | DAGService 详细设计 | services/dag_service.py | P2 |
| M-09 | SimulationService 详细设计 | services/simulation_service.py | P2 |

---

## Phase 2: 核心数据模型对齐（P1）

### 2.1 实例层数据类补全

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-01 | EntityInstance 缺 valid_from/valid_to/confidence/source_*/feedback_weight/domain_id | storage/base.py | 补全字段 | 与 instance-layer.md 一致 |
| C-02 | RelationInstance 缺 id/edge_text/weight/valid_from/valid_to/confidence/source_* | storage/base.py | 补全字段 | 与 instance-layer.md 一致 |
| C-03 | 无独立 MetricValue 数据类 | storage/base.py | 新增 MetricValue dataclass | 与 instance-layer.md 一致 |
| C-04 | 无独立 KnowledgeFragment 数据类 | storage/base.py | 新增 KnowledgeFragment dataclass | 与 instance-layer.md 一致 |
| C-05 | CategoryTags 结构偏差（dict vs 独立记录） | engine/categorization/models.py | 重构为独立记录模型 | 与 instance-layer.md 一致 | **部分完成**：storage 层已实现 CategoryTag 独立记录，engine/categorization 层待对齐 |

### 2.2 Schema 声明层模型对齐

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-06 | FactObjectEntity 缺 identity_fields/temporal/key_attributes | core/schema/models.py | 补全字段 | 与 L1-L4-declarations.md 一致 |
| C-07 | AttributeDefinition 缺 10 个字段 | core/schema/models.py | 补全 index_fields/display_only/source_*/currency/pattern/min/max | 与 L1-L4-declarations.md 一致 |
| C-08 | RelationDefinition 缺 from/attributes/logical_type | core/schema/models.py | 补全字段，重命名 target→to | 与 L1-L4-declarations.md 一致 |
| C-09 | CategorizationDimension.type 枚举不一致 | core/schema/models.py | 统一为 hierarchical/derived/tag_based | 与 L1-L4-declarations.md 一致 |
| C-10 | MetricDefinitionV2 缺 value_type/overridable_by/溯源字段 | core/schema/models.py | 补全字段 | 与 L1-L4-declarations.md 一致 |
| C-11 | RuleDefinitionV2 缺 overrides/applicability，applies_to 扁平化 | core/schema/models.py | 补全字段，结构化 applies_to | 与 L1-L4-declarations.md 一致 |
| C-12 | RuleLogic 缺 type 枚举，Step.action 扁平化 | core/schema/models.py | 补全 type，结构化 action | 与 L1-L4-declarations.md 一致 |

### 2.3 核心机制实现

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-13 | temporal 声明缺失 | core/schema/models.py | FactObjectEntity 增加 temporal: bool | Schema YAML 可声明时序实体 |
| C-14 | identity_fields 声明缺失 | core/schema/models.py | FactObjectEntity 增加 identity_fields | Schema YAML 可声明唯一性字段 |
| C-15 | UUID5 确定性 ID 未在 InstanceLoader 中使用 | core/instances/loader.py | 基于 identity_fields 生成 UUID5 | 幂等写入验证 |
| C-16 | overrides 声明和覆盖优先级逻辑缺失 | core/schema/models.py + engine/rule/ | 补全 overrides 字段 + 覆盖逻辑 | What-if 模拟验证 | **拆分为 C-16a/C-16b**：C-16a 声明层已完成（C-11），C-16b 执行层覆盖逻辑待实现 |
| C-17 | 声明约束未在实例层强制执行 | core/instances/loader.py | 增加属性合规校验 | 非法属性被拒绝 |

---

## Phase 3: 存储层接口对齐（P1）

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-18 | StorageBackend 巨型单体需拆分 | storage/base.py | 按领域分组方法，增加 RetrievalBackend 方法 | 接口清晰分组 |
| C-19 | SQLite 表结构与设计文档不对齐 | storage/sqlite/store.py | 按 storage/sqlite-tables.md 调整表结构 | 表与文档一致 |
| C-20 | KuzuDB 互索引边方向偏差 | storage/graph/kuzu_store.py | 修正 EXTRACTED_FROM/TRACE_TO 方向 | 与 mutual-index-edges.md 一致 |
| C-21 | KuzuDB RuleDefinitionNode 与 Schema L4 不对齐 | storage/graph/kuzu_store.py | 重设计节点表 | 与 L1-L4-declarations.md 一致 |
| C-22 | DualWriteCoordinator 未完善 | storage/dual_write.py | 完善 SQLite↔KuzuDB 双写逻辑 | 双写一致性测试 |
| C-23 | StorageConfig 缺分库配置 | storage/config.py | 增加分库隔离配置 | 可按空间分库 |

---

## Phase 4: 引擎层修复（P1）

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-24 | LogicalEdgeEngine 完全未实现 | engine/rule/ | 新增 logical_edges.py | 三类逻辑边可区分 |
| C-25 | DAGExecutor 未集成 PipelineStateManager | engine/rule/dag_executor.py | 执行时调用 PipelineStateManager | 断点续跑可用 |
| C-26 | PipelineStateManager 步骤生命周期不完整 | engine/rule/pipeline_state.py | 补全 start/complete/fail/skip/rollback | 步骤状态完整 |
| C-27 | PipelineState 仅内存存储 | engine/rule/pipeline_state.py | SQLite 持久化 | 进程重启可恢复 |
| C-28 | RuleExecutor 缺 MetricEngine 注入 | engine/rule/executor.py | 构造函数注入 MetricEngine | 指标预计算可用 |
| C-29 | RuleExecutor 无 execute_rule_group | engine/rule/executor.py | 新增方法，集成 DAGExecutor | 规则组 DAG 执行 |
| C-30 | 语义缓存 save 未实现 | engine/extraction/cache.py | 实现 save_semantic_cache | LLM 结果可缓存 |
| C-31 | CategorizationEngine._compile_to_l4_rules 未实现 | engine/categorization/engine.py | 实现 L2→L4 编译 | 派生分类可用 |
| C-32 | graph_traversal 算子为 placeholder | engine/rule/operators/ | 实现图遍历算子 | 图聚合计算可用 |

---

## Phase 5: API 层修复（P1）

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-33 | /v1/actions 路由组缺失 | api/routes/ | 新增 actions.py | 5 个端点可用 |
| C-34 | /v1/ontology 路由组缺失 | api/routes/ | 新增 ontology.py | 8 个端点可用 |
| C-35 | 兼容层 70+ 条映射未实现 | api/ | 实现 DeprecationMiddleware + 301 重定向 | 旧端点有 Deprecation Header |
| C-36 | management.py 与 semantic_spaces.py 路由重复 | api/routes/ | 合并为单一入口 | 无重复路由 |
| C-37 | Explain 端点缺失 | api/routes/ | 新增 explain 端点 | Agent 可获取执行解释 |
| C-38 | API 术语混用 | api/dto/, api/routes/ | 统一为 _fact_object/attributes/type | grep 零命中旧术语 |

---

## Phase 6: 服务层修复（P2）

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-39 | FeedbackService 完全缺失 | services/ | 新增 feedback_service.py | 反馈闭环可用 |
| C-40 | IngestionService 无双通道 | services/ingestion_service.py | 实现快/慢双通道 | 双通道导入验证 |
| C-41 | QueryService 无三层接口 | services/query_service.py | 实现 query_raw/query_structured/query_hybrid | 三层检索可用 |
| C-42 | AnalysisService 无并行/缓存/快照 | services/analysis_service.py | 实现六步执行序列 | 并行指标预计算 |
| C-43 | 事务边界全部 soft-fail | services/ | 增加 atomic 事务选项 | 可选原子事务 |

---

## Phase 7: 模块边界违规修复（P1）

| ID | 问题 | 代码文件 | 修复动作 | 验证标准 |
|----|------|---------|---------|---------|
| C-44 | api/routes/rules.py 直接导入 engine 层 | api/routes/rules.py | 通过 DAGService 间接使用 | 无跨层导入 |
| C-45 | mcp/server.py 直接导入 storage/sqlite | mcp/server.py | 通过依赖注入获取 | 无跨层导入 |
| C-46 | mcp/server.py 直接导入 core/schema | mcp/server.py | 通过 SchemaService 间接使用 | 无跨层导入 |

---

## Phase 8: 测试补全 + 样例验证（P2）

| ID | 缺失测试 | 对应模块 | 修复动作 |
|----|---------|---------|---------|
| T-01 | engine/extraction/ 单元测试 | 提取引擎 | 新增测试 |
| T-02 | engine/query/ 单元测试 | 查询引擎 | 新增测试 |
| T-03 | engine/validation/ 单元测试 | 验证引擎 | 新增测试 |
| T-04 | core/semantic_space/ 单元测试 | 语义空间 | 新增测试 |
| T-05 | core/dataset/ 单元测试 | 数据集 | 新增测试 |
| T-06 | core/instances/ 单元测试 | 实例加载 | 新增测试 |
| T-07 | storage/dual_write.py 测试 | 双写协调 | 新增测试 |
| T-08 | services/SpaceService 测试 | 空间服务 | 新增测试 |
| T-09 | 样例 case1 端到端验证 | consumer_credit | API/MCP/CLI 跑通 |
| T-10 | 样例 case3 端到端验证 | tax_simulation | API/MCP/CLI 跑通 |

---

## 2026-04-28 修复进度

### 已完成修复项

| 优先级 | ID | 修复内容 | 影响文件 |
|--------|-----|---------|---------|
| P0 | P0-2 | dag_executor.py PSM async 调用缺 await + create_run 签名不匹配 | engine/rule/dag_executor.py |
| P0 | P0-3 | ontology.py/actions.py EntityService 方法名不匹配 + 边界违规 | api/routes/ontology.py, api/routes/actions.py |
| P1 | P1-1 | feedback_weight 默认值 1.0→0.5 | storage/base.py, storage/sqlite/store.py |
| P1 | P1-2 | SQLite entities 表缺 created_at/updated_at + computed_metrics 缺字段 | storage/sqlite/store.py |
| P1 | P1-3 | query_entities 返回部分 EntityInstance | storage/sqlite/store.py |
| P1 | P1-4 | 添加 delete_entity 方法到 StorageBackend + SQLite 实现 | storage/base.py, storage/sqlite/store.py |
| P1 | P1-5 | KuzuDB Cypher 注入 + KnowledgeFragment 缺字段 | storage/graph/kuzu_store.py, storage/retrieval.py |
| P1 | P1-6 | retrieval.py hybrid_search 错误的向量检索 + 元数据获取 | storage/retrieval.py |
| P1 | P1-7 | entity_service.py atomic 参数无效 + pipeline_state fail_step + 步骤持久化 | services/entity_service.py, engine/rule/pipeline_state.py |
| P2 | P2-1 | API 层边界违规 (categories 消除 get_storage 直接调用) | api/routes/categories.py, services/category_service.py, api/dependencies.py, api/server.py |
| P2 | P2-2 | logical_edges max_depth 未使用 + query_service filters mutation + 返回类型不一致 | engine/rule/logical_edges.py, services/query_service.py |
| P2 | P2-3 | 更新 5 份严重偏离的设计文档标注 [待核对代码] | docs/02-design/ 下 5 份文档 |
| P2 | P2-4 | 更新 STATUS.md + governance-checklist 进度 | docs/STATUS.md, docs-dev/discuss/2026-04-27-governance-checklist.md |

### 测试验证

- pytest: 648 passed, 5 failed (5 个失败为预存在的 simulation_tree_builder 问题，非本次修改引起)
- ruff: 通过（仅预存在的 lint 警告）

### 待后续处理

| 项目 | 说明 |
|------|------|
| simulation_tree_builder.py | 5 个预存在的测试失败，RuleGroupDefinition.get() AttributeError |
| 语义缓存 save_semantic_cache | C-30 仍未实现 |
| CategorizationEngine._compile_to_l4_rules | C-31 仍未实现 |
| Phase 8 测试补全 | T-01~T-10 仍未执行 |
| T-11 | 样例 supply_chain 端到端验证 | supply_chain_finance | API/MCP/CLI 跑通 |

---

## 执行进度

| Phase | 总项数 | 已完成 | 进行中 | 待开始 |
|-------|--------|--------|--------|--------|
| Phase 1: 文档治理 | 24 | 14 | 0 | 10 |
| Phase 2: 数据模型 | 17 | 15 | 0 | 2 |
| Phase 3: 存储层 | 6 | 0 | 0 | 6 |
| Phase 4: 引擎层 | 9 | 0 | 0 | 9 |
| Phase 5: API 层 | 6 | 0 | 0 | 6 |
| Phase 6: 服务层 | 5 | 0 | 0 | 5 |
| Phase 7: 边界违规 | 3 | 0 | 0 | 3 |
| Phase 8: 测试验证 | 11 | 0 | 0 | 11 |
| **合计** | **81** | **29** | **0** | **52** |

### Phase 1 已完成项

- [x] T-01: API 路由文档 concept_type → _fact_object（19 处替换）
- [x] T-02: API 路由文档 properties → attributes（2 处替换）
- [x] T-03: API 路由文档 element_type → type（1 处替换）
- [x] T-04: storage/interfaces.md properties → attributes
- [x] D-01: Formula 双重 SoT 修复（06-formula-spec.md 标记为 [已过期入口]）
- [x] D-02: Schema 算子枚举统一（补充 FORMULA 算子）
- [x] D-03: README.md 审视状态同步（8 个模块）
- [x] D-04: api/README.md status 统一为 draft
- [x] D-06: Formula Bug B-1/B-2 状态更新为已修复
- [x] 服务层文档术语统一（analysis-service, feedback-service, 04-rule-engine-design, 05-services-design）

### Phase 2 已完成项

- [x] C-01: EntityInstance 补全 valid_from/valid_to/confidence/source_*/feedback_weight/domain_id
- [x] C-02: RelationInstance 补全 id/edge_text/weight/valid_from/valid_to/confidence/source_*
- [x] C-03: 新增 MetricValue 数据类
- [x] C-04: 新增 KnowledgeFragment 数据类
- [x] C-06: FactObjectEntity 补全 identity_fields/temporal/key_attributes
- [x] C-07: AttributeDefinition 补全 10 个字段
- [x] C-08: RelationDefinition 补全 from_entity/attributes/logical_type
- [x] C-09: CategorizationDimension.type 枚举统一
- [x] C-10: MetricDefinitionV2 补全 value_type/overridable_by/溯源字段
- [x] C-11: RuleDefinitionV2 补全 overrides/applicability
- [x] C-12: RuleLogic 补全 type 枚举
- [x] C-13: temporal 声明（FactObjectEntity.temporal）
- [x] C-14: identity_fields 声明（FactObjectEntity.identity_fields）
- [x] C-15: UUID5 确定性 ID（InstanceLoader._generate_uuid5_id）
- [x] C-17: 声明约束校验（InstanceLoader._validate_entity_against_schema）

### 测试验证

- 617 passed, 5 failed（5 个失败为预先存在的 bug，与本次修改无关）
- 所有新增字段均有默认值，完全向后兼容
