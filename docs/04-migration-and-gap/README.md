# 当前实现 → 目标架构：迁移与差距

> **状态**: accepted
> **Phase**: phase1
> **Source of Truth**: true
> **Last Verified**: 2026-04-16 (含 subagent 代码核验)

## 作用

本目录统一回答一个问题：**当前代码 / 当前设计 / 目标架构之间，哪里一致，哪里冲突，接下来怎么迁移。**

以后凡是遇到"同一主题有多套说法"的情况，优先先落到这里，而不是分散修改多个目录又留下新的重复。

---

## 模块级差距总表 (2026-04-16)

| 模块 | 设计文档 | 代码路径 | 核验结果 | 关键偏差 |
|------|----------|----------|----------|----------|
| Rule Engine | `06-module-detailed-design/06-rule-engine.md` | `ontology_engine/engine/rule/` | ⚠️ 部分实现 | DAG 未实现，退化为 priority 排序；RuleLogic 未被使用 |
| Storage | `06-module-detailed-design/03-storage-layer.md` | `ontology_engine/storage/` | ⚠️ 部分实现 | audit_log/schema_versions 缺失；NetworkX 非按需加载；Faiss 退化为内存实现；缓存未实现 |
| Services | `06-module-detailed-design/09-services-layer.md` | `ontology_engine/services/` | ⚠️ 部分实现 | 权限检查缺失；事务管理为软失败而非原子回滚 |
| Expression | `06-module-detailed-design/07-expression-engine.md` | `ontology_engine/engine/expression/` | ⚠️ 部分实现 | L0/L1 未分离；函数库缺失 60%+；无资源限制 |
| Query Engine | `06-module-detailed-design/08-query-engine.md` | `ontology_engine/engine/query/` | ❌ 未实现 | 仅占位符，无任何实现 |
| API Layer | `06-module-detailed-design/10-api-layer.md` | `ontology_engine/api/routes/` | ✅ 基本符合 | 端点与路由已实现，与代码一致 |

---

## 1. Rule Engine 差距

> 核验日期: 2026-04-16

| 主题 | 设计目标 | 当前实现 | 差距 |
|------|----------|----------|------|
| DAG 构建 | `dag.py` + NetworkX 拓扑排序 | ❌ 未实现 | 实际仅 `priority` 降序排序 (`executor.py:424`) |
| RuleLogic 使用 | `rule_definitions + rule_logics` (ADR-008) | ⚠️ Schema 有定义，Executor 未引用 | RuleExecutor 仍用 V1 `when/then/else_` 直接执行 |
| 回滚机制 | Snapshot + Restore | ❌ 未实现 | 仅异常捕获继续执行 |
| 算子体系 | 16 个算子 | ✅ 已实现 | 与代码一致 |
| 决策结果判定 | `_determine_decision()` | ✅ 已实现 | 与代码一致 |

**关键决策**: ADR-008 双轨问题仍在 — Schema 层已统一为 `rule_definitions + rule_logics`，但执行层未切换。建议在 Phase 2 前冻结 `RuleExecutor` 是否迁移至 DAG 驱动，或明确保留当前顺序执行模型。

---

## 2. Storage 差距

> 核验日期: 2026-04-16

| 主题 | 设计目标 | 当前实现 | 差距 |
|------|----------|----------|------|
| DuckDB 核心表 | entities, relations, computed_metrics, category_tags, rule_execution_log | ✅ 已实现 | 一致 |
| audit_log 表 | 审计日志 | ❌ 未实现 | 表不存在 |
| schema_versions 表 | Schema 版本管理 | ❌ 未实现 | 表不存在 |
| NetworkX 图 | 按需从 DuckDB 加载子图 | ❌ 偏离 | 实际为独立内存图存储 (`upsert_node/edge`) |
| Faiss 向量索引 | `FaissVectorStore` 持久化 | ❌ 偏离 | 实际为 `LocalVectorStore` 内存实现 |
| 缓存 | `MetricCache` (LRU+TTL) | ❌ 未实现 | `storage/cache.py` 不存在 |

**关键决策**: 当前 Storage 实现已满足 Phase 1 功能需求，但设计与实现存在架构级偏差。`03-storage-design.md` 和 `06-module-detailed-design/03-storage-layer.md` 中描述的 "Faiss + NetworkX按需加载 + 缓存" 属于目标态，当前代码属于简化实现。建议文档明确区分 current/target。

---

## 3. Services 差距

> 核验日期: 2026-04-16

| 主题 | 设计目标 | 当前实现 | 差距 |
|------|----------|----------|------|
| 5 个核心 Service | Schema/Entity/Analysis/Query/Ingestion | ✅ 已实现 | 一致 |
| 用例编排 | L2→L3→L4 协调 | ✅ 已实现 | `analysis_service.py` 完整实现 |
| DTO 转换 | requests/responses/errors | ✅ 已实现 | `dto/` 目录完整 |
| 事务管理 | 原子性回滚 | ⚠️ 偏离 | `batch_create`/`import_instances` 为错误收集后继续执行 |
| 权限检查 | 接口级别权限验证 | ❌ 未实现 | 代码中无任何权限逻辑 |

**额外实现**: 代码中存在设计文档未覆盖的服务 — `dag_service.py`, `dataset_service.py`, `rule_service.py`, `simulation_service.py`, `visualization_service.py`, `incremental_update.py`。

---

## 4. Expression Engine 差距

> 核验日期: 2026-04-16

| 主题 | 设计目标 | 当前实现 | 差距 |
|------|----------|----------|------|
| L0/L1 两级模型 | `SimpleEvalExecutor` + `ASTSandboxExecutor` | ⚠️ 偏离 | simpleeval + asteval fallback，非独立执行器 |
| 数学函数 | abs, min, max, round, floor, ceil, pow, sqrt | ⚠️ 部分 | 缺 floor, ceil, pow, sqrt |
| 字符串函数 | len, upper, lower, contains, starts_with, ends_with | ❌ 未实现 | 全部缺失 |
| 日期函数 | today, now, days_between, months_between, years_between, add_days... | ⚠️ 部分 | 缺 months_between, years_between, add_days 等 |
| 聚合函数 | sum, avg, count, std | ❌ 未实现 | 全部缺失 |
| 资源限制 | 超时/内存/循环限制 | ❌ 未实现 | 无显式限制配置 |

**关键决策**: 当前 ExpressionEngine 足够支撑 Phase 1 规则表达式，但文档中大量描述的目标设计（L1 AST 沙箱、完整函数库）尚未实现。建议在 `07-expression-engine.md` 中明确标注 `[当前实现]` vs `[目标设计]`。

---

## 5. Query Engine 差距

> 核验日期: 2026-04-16

| 主题 | 设计目标 | 当前实现 | 差距 |
|------|----------|----------|------|
| 图遍历 DSL | 路径模式匹配 | ❌ 未实现 | `engine/query/__init__.py` 仅占位符 |
| 向量检索 | Faiss ANN | ❌ 未实现 | 无相关代码 |
| 混合融合 | semantic×0.6 + graph×0.4 | ❌ 未实现 | 无相关代码 |
| kuzu 协同 | 图遍历、路径查询 | ❌ 未实现 | 无相关代码 |

**关键决策**: QueryEngine 模块当前为空。`QueryService` 中部分查询方法可能通过 Storage 直接实现。建议在 Phase 2 按 RFC-012 (kuzu) 统一规划查询引擎实现。

---

## 6. API Layer 差距

> 核验日期: 2026-04-16

| 主题 | 设计目标 | 当前实现 | 差距 |
|------|----------|----------|------|
| FastAPI 路由结构 | `/v1/schema`, `/v1/entities`, `/v1/rules` 等 | ✅ 已实现 | 一致 |
| DTO 设计 | Pydantic 请求/响应模型 | ✅ 已实现 | `dto/` 目录完整 |
| 错误处理 | ServiceError + 异常处理 | ✅ 已实现 | 一致 |
| 流式响应 | `/v1/rules/execute/stream` | ❌ 未实现 | SSE 端点不存在 |

**说明**: API 层是文档与代码一致性最好的模块。`10-api-layer.md` 已标注 `[已核对代码]`，状态稳定。

---

## Schema Loading 模块核验结论 (2026-04-13)

> 核验文档: `06-module-detailed-design/01-schema-loading.md`
> 核验范围: `ontology_engine/core/schema/`

### 当前态 vs 设计差异

| 主题 | 设计 (v2 canonical) | 当前实现 | 差距 |
|------|---------------------|----------|------|
| KGMLSchema 结构 | `entities`, `relations`, `categories`, `rule_dimensions`, `rules` 分离 | `concepts` (含 entity/relation), `rules: RulesDefinition` | **[关键设计点]** v2 分离式模型尚未实现 |
| CategoryDimension | `categories: list[CategoryDimension]` | 不存在 | 缺失 |
| RuleDimension | `rule_dimensions: list[RuleDimension]` | `rules.rule_dimensions: list[RuleDimension]` (在 RulesDefinition 内) | 结构差异 |
| v1 兼容映射 | `v1_compat.py` 完整实现 | 不存在 | 待实现 |
| 版本管理器 | `version_manager.py` 完整实现 | 不存在 | 待实现 |
| Schema 差异计算 | `diff.py` 完整实现 | 不存在 | 待实现 |

### 迁移建议
- 当前 `KGMLSchema` 仍保持 v1 风格 (`concepts` 统一列表)
- v2 分离式模型需等 canonical grammar 稳定后逐步迁移
- v1_compat、version_manager、diff 列入 Phase 2

---

## 迁移矩阵 (精简版)

| 主题 | 当前态 | 目标态 | 当前判断 |
|------|--------|--------|----------|
| Schema 根结构 + 内层 grammar | `02-design/01-schema-spec.md` | `05-schema-v2/09-canonical-schema-spec.md` | ✅ L1-L4 grammar 已冻结 |
| Rule 模型 | 旧 `ruleset / rule_group` 叙述 | `rule_definitions + rule_logics` | ⚠️ Schema 已统一，Executor 未使用 (2026-04-16) |
| Formula / Expression | `02-design/06-formula-spec.md` | `05-schema-v2/*` 目标算子 | ⚠️ 当前实现满足 Phase 1，目标设计待 Phase 2 |
| API 形态 | `/v1/*` FastAPI | `/v2/*` 空间 API | ✅ Current API 已稳定，Target API 待 Phase 2 |
| 引擎拆分 | `RuleExecutor` 顺序执行 | `RuleEngine` DAG 驱动 | ⚠️ 当前实现可用，目标态需 RFC-011 规划 |
| 查询引擎 | 无 | Vector/Hybrid/DSL + kuzu | ❌ 未启动，待 Phase 2 |
| Storage | 简化本地实现 | Faiss + 按需子图 + 缓存 | ⚠️ 当前实现可用，目标态待 Phase 2 |
| 平台化能力 | 本地优先 | 空间、同步、管理面 | **[待扩展]** 详见 `05-schema-v2/06-dataset-and-sync.md` |

---

## 使用规则

1. 发现冲突时，先记录"冲突双方 + 影响 + 收敛建议"，不要直接在多个目录复制同一段说明
2. 迁移说明必须同时给出：当前态入口、目标态入口、实施入口
3. 若冲突已经解决，要同步更新 `STATUS.md` 和相关主题文档
4. 若迁移涉及关键取舍，应沉淀到 `architecture/decisions/` 或 `03-rfc/`
