# 实施 Backlog

> **作用**: `docs/` 下唯一开放事项列表
> **最后更新**: 2026-04-14
> **说明**: 本文件只保留进行中 / 未完成事项；文档状态看 [`STATUS.md`](./STATUS.md)，阶段路线看 [`ROADMAP.md`](./ROADMAP.md)

## 已完成事项归档

以下事项已完成，归档记录供参考：

### P0 完成项
- ✅ 同步 `05-schema-v2/05-complete-example.md` 到 canonical grammar
- ✅ 拆清 Current API 与 Target API 的文档边界（ADR-009）
- ✅ 核验 Expression / Formula 设计与当前代码差异
- ✅ 清理模块设计中不稳定的"固定数字真相"

### P1 完成项
- ✅ 统一术语表并给出对照关系（`01-overview/05-concepts.md`）
- ✅ 收敛 Rule 模型的历史写法（ADR-008）
- ✅ 为模块详细设计补充代码映射 / 测试要点
- ✅ 为关键目标态设计补 `last_verified` / `verified_against` 元数据
- ✅ 核验 Schema Loading 模块设计与代码差异（`06-module-detailed-design/01-schema-loading.md`）→ 差距已记录到 `04-migration-and-gap/README.md`
- ✅ 核验 Rule Engine 模块设计与代码差异（`06-module-detailed-design/06-rule-engine.md`）→ 差距已记录到 `04-migration-and-gap/README.md`
- ✅ 文档与实现一致性审视（docs/09-examples/），发现系统性断裂，详见 `REVIEW_REPORT.md`
- ✅ Canonical grammar 字段名对齐（element_type→type, target_objects→applies_to 等），代码/schema/example 全部更新

### P2 完成项
- ✅ DuckDB 新增 API 路由注册 — `server.py:374-376` 三条路由已注册，`tests/unit/services/test_dataset_and_incremental.py` 13 个单元测试覆盖
- ✅ 冻结空间状态机与版本管理的正式口径（ADR-010）
- ✅ 收敛平台化扩展边界（能力矩阵）
- ✅ 补全分层设计文档元数据（01-04 添加 related_adrs）
- ✅ 更新 `05-schema-v2/README.md` 导航（补充 07-rule-declaration-and-instance.md）

### ADR 新增
- ✅ ADR-007: L3-L4 计算边界
- ✅ ADR-008: Rule 模型统一
- ✅ ADR-009: API 架构演进
- ✅ ADR-010: 语义空间生命周期

---

## Now

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P1 | docs/09-examples/supply_chain_finance.md 重构完成 | ✅ 文档已有完整 deprecated 标注 + 不符点清单，无需重写 |
| P1 | MCP 工具实现（P1 核心 5 个）| RFC-013 | `oe_create_space/execute_rule/query/register_dataset/simulate` — 包装现有 API 为 MCP 工具 |
| P1 | 前端 Playwright 验证 | `ontology-engine-ui/` | 验证前端页面展示 Phase 1 新功能 |
| P1 | 全链路 API 验收 | API routes | 端到端测试新增功能（数据集/增量更新/分类） |
| P2 | NetworkXGraphStore 导出到 storage/__init__.py | `ontology_engine/storage/__init__.py` | 当前需直接导入 graph.networkx_store |
| P2 | LLMJudgeOperator._call_llm() 接入实际 LLM | `ontology_engine/engine/rule/operators/llm_judge.py` | 当前为 placeholder |

## Next

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P2 | Phase 2 RuleExecutor DAG 实现 | RFC-011 | 顺序执行 → steps[] DAG 拓扑排序（Phase 2 最高优先级） |
| P2 | Phase 2 kuzu 图存储升级 | RFC-012 | NetworkX → kuzu，支撑 100K 节点规模 |
| P2 | Phase 2 MCP 工具实现 | RFC-013 | P2/P3 工具（trace/define_rule/dataset_ops 等）；P1 核心 5 个已完成 |
| P2 | DuckDB 新增表 CRUD 方法 | `ontology_engine/storage/duckdb/store.py` | datasets/change_batches/entity_versions 等表的完整 CRUD |
| P3 | KuzuGraphStore 实现（Phase 2 存储） | RFC-012 | 现有 `07-phase1-enhancement/01-graph-storage-extension.md` 中的 kuzu 规划 |
| P3 | ValueDomainValidator enum 类型集成 Schema | `ontology_engine/engine/validation/value_domain_validator.py` | 当前 enum 验证为占位 |

## Later

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P3 | 关键设计完成实现后回写 accepted 状态 | [`STATUS.md`](./STATUS.md) | 让设计与代码持续闭环 |
| P3 | 清理旧文档中的 `rule_group` 写法 | `05-schema-v2/*` | 统一改为 canonical model |

## 使用规则

1. 完成项从本文件移除，不在此保留历史完成记录（本次为过渡保留，下次清理）
2. 本文件不再维护端点数、服务数、模块数等容易漂移的数据
3. 若事项属于"判断文档是否过期"，请更新 [`STATUS.md`](./STATUS.md)
4. 若事项属于"阶段目标变化"，请更新 [`ROADMAP.md`](./ROADMAP.md)
5. 若事项属于"当前态与目标态不一致"，先记录到 [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md)
