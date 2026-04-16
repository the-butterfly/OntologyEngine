# RFC-010: Phase 2 改进路线图

> **状态**: draft
> **创建日期**: 2026-04-14
> **作者**: the-butterfly
> **评审截止**: 待定
> **关联子 RFC**: [RFC-011](./RFC-011-rule-executor-dag.md) · [RFC-012](./RFC-012-kuzu-storage.md) · [RFC-013](./RFC-013-mcp-tool-implementation.md) · [RFC-014](./RFC-014-rule-orchestration-system.md) · [RFC-015](./RFC-015-rule-orchestration-frontend.md) · [RFC-016](./RFC-016-rule-orchestration-gap-analysis.md) · [RFC-017](./RFC-017-rule-orchestration-yaml-format.md)

## 摘要

本文档定义 OntologyEngine Phase 2 的改进路线，涵盖三大核心改进项：
**RuleExecutor DAG 引擎**、**kuzu 图存储升级**、**MCP 工具实现**。
采用"文档先行"策略，先冻结设计再实施代码。

## 背景与动机

### Phase 1 完成后的差距

Phase 1 已实现：
- DuckDB 本地持久化存储（Entity / Relation / Metric / Category / Dataset / Incremental Update）
- Schema v2 canonical grammar（fact_objects / categorizations / analytical_elements / business_logic）
- RuleExecutor 顺序执行引擎（`when` + `then_action` / `else_action`）
- NetworkX 内存图存储

Phase 1 未完成 / Phase 2 目标：

| 差距 | Phase 1 | Phase 2 目标 |
|------|---------|-------------|
| 规则执行模型 | 顺序 + if/else 分支 | steps[] DAG 拓扑排序，支持 `depends_on` |
| 图存储 | NetworkX 内存（< 1K 节点） | kuzu 持久化（100K 节点） |
| MCP 工具 | 文档定义 | 可执行 MCP 工具（Claude Desktop / Cursor 集成） |
| Schema 表达力 | when/then_action 单分支 | steps[] 多阶段 DAG，支持算子组合 |
| 文档一致性 | docs/09-examples 含虚构 Schema | 全部文档与代码核验一致 |

### Phase 1 文档审视发现（2026-04-14）

详见 [docs/09-examples/REVIEW_REPORT.md](../09-examples/REVIEW_REPORT.md)：
- `docs/09-examples/supply_chain_finance.md` 使用虚构 Schema（`Company`/`Guarantee`/`steps[]`），与实际 `Supplier`/`supplies_to`/`when/then_action` 完全不符 → **已标注为 deprecated**
- Phase 1/2 边界混淆：文档用 Phase 2 目标格式描述 Phase 1 实现
- `07-agent-interface.md` 定义的 MCP 工具尚未实现 → **`ontology_engine/mcp/` 从未创建**，详见 [TOOL_AUDIT.md](../09-examples/TOOL_AUDIT.md)

## 设计原则

1. **文档先行**: 每个子 RFC 先评审冻结，再实现代码
2. **向后兼容**: Phase 2 改进不破坏 Phase 1 已实现的 API 和存储格式
3. **可逆性**: 存储层支持 Schema 迁移，不引入不可回滚的破坏性变更
4. **渐进增强**: RuleExecutor 从顺序执行扩展为 DAG，不重写现有 `when/then_action` 逻辑

## 三大改进项概览

```
Phase 2 改进
├── 1. RuleExecutor DAG 引擎（RFC-011）
│   ├── rules[] → steps[] DAG 拓扑排序
│   ├── 支持 depends_on 显式依赖声明
│   ├── 支持 SCOREBOARD / DECISION_TABLE 等算子组合
│   └── 向后兼容现有 when/then_action 格式
│
├── 2. kuzu 图存储升级（RFC-012）
│   ├── NetworkX → kuzu 持久化图存储
│   ├── 支撑 100K 节点规模（Phase 1 node target）
│   ├── 与 DuckDB 双写协调（DualWriteCoordinator）
│   └── 支持 Cypher-like 查询语言
│
└── 3. MCP 工具实现（RFC-013）
    ├── 核验完成（docs/09-examples/TOOL_AUDIT.md）
    ├── P1 核心 5 个工具（execute_rule / query / simulate / create_space / register_dataset）
    └── Claude Desktop / Cursor MCP 集成
```

## 执行顺序

```
Step 0: 修文档（已完成）
  ├── ✅ docs/09-examples 重构 → REVIEW_REPORT.md + supply_chain_finance.md (deprecated)
  ├── ✅ MCP 工具核验 → TOOL_AUDIT.md（18 个工具逐一对照）
  └── ✅ RFC-013 修正 → P1/P2/P3 优先级对齐 TOOL_AUDIT

Step 1: RuleExecutor DAG（RFC-011）
  ├── 设计评审 → RFC 冻结
  ├── RuleStep 模型扩展
  ├── DAG 拓扑排序实现
  └── 集成测试

Step 2: kuzu 图存储（RFC-012）
  ├── 设计评审 → RFC 冻结
  ├── DuckDB → kuzu 数据迁移脚本
  ├── DualWriteCoordinator 改造
  └── 性能基准测试

Step 3: MCP 工具实现（RFC-013）
  ├── 按 TOOL_AUDIT P1 优先级包装 5 个核心工具
  ├── MCP Server 入口实现
  ├── Claude Desktop 集成测试
  └── P2 工具逐步落地
```

## 开放问题

| 问题 | 选项 | 推荐 |
|------|------|------|
| steps[] DAG 与现有 when/then_action 如何共存？ | A) 并存（两种格式都支持） B) 迁移（全部转为 steps[]） | A) 并存，loader 向下兼容 |
| kuzu 是否需要单独的 Schema 迁移脚本？ | A) 迁移脚本（推荐）B) 自动推断 | A) 提供显式迁移脚本 |
| MCP 工具的认证/授权模型？ | A) 无认证（开发模式）B) API Key | A) Phase 2 简化，Phase 3 考虑认证 |

## 相关文档

- **RFC-011** — [RuleExecutor DAG 引擎](./RFC-011-rule-executor-dag.md)
- **RFC-012** — [kuzu 图存储升级](./RFC-012-kuzu-storage.md)
- **RFC-013** — [MCP 工具实现](./RFC-013-mcp-tool-implementation.md)
- **MCP 工具核验** — [docs/09-examples/TOOL_AUDIT.md](../09-examples/TOOL_AUDIT.md) — **P1/P2/P3 优先级准据**
- **审视报告** — [docs/09-examples/REVIEW_REPORT.md](../09-examples/REVIEW_REPORT.md) — 文档一致性审查
- **ADR-008** — [Rule 模型统一](./../architecture/decisions/008-rule-model-unification.md)
- **CLAUDE.md** — [项目约束](../CLAUDE.md)
