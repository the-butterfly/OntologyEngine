# 实施计划归档

> **角色**: 已实施完毕的历史实施计划汇总，保留关键结论供追溯
> **创建日期**: 2026-05-15
> **来源**: 从 `docs/plans/` 迁移，原目录不再使用
> **治理规则**: 本目录仅存放已完成/已归档的实施计划；活跃实施计划不在此处

---

## 原始计划清单与关键结论

| 计划文件 | 原始路径 | 分类 | 关键结论 | 状态说明 |
|----------|----------|------|----------|----------|
| 2026-04-26-examples-verification-report.md | `docs/plans/` | ✅ 已验证数据 | 8 案例 232 checks, 95.3% 通过率；InstanceLoader 通用化、关系自动提取等优化已实施 | **已保留原始文件** — 验证指标有追溯价值 |
| use-case-plan-competitive-analysis.md | `docs/plans/` | ✅ 产品调研结论 | 6 大体验亮点 + 竞品对比矩阵 (KAG/Drools/Neo4j/GraphRAG)；7 案例分阶段实施路线；Case 4 半自动优先决策 | **已保留原始文件** — 产品视角结论在 02-design 中未完整覆盖 |
| 2026-04-20-rule-engine-dag-implementation.md | `docs/plans/` | 🔄 已归档 | 设计结论已融入 `02-design/rule-engine/` (DAGBuilder, DAGExecutor, PipelineStateManager) | 原始计划文件删除 |
| 2026-04-21-simulation-embeddable-ui.md | `docs/plans/` | ✅ 已完成 | Simulation Session API + Embeddable UI 已实现；STATUS 标记 **[已完成]** | 原始计划文件删除 |
| 2026-04-23-agent-friendly-infrastructure.md | `docs/plans/` | ⚠️ 部分完成 | 核心架构修复已完成；结论提炼至 `02-design/agent-friendly-design.md`；P2 任务 (错误码注册表等) 仍在 TODO.md | 原始计划文件删除 |
| 2026-04-23-rule-simulation-refactor.md | `docs/plans/` | ✅ 已完成 | RuleLocator + DependencyAnalyzer 已实现为共享服务 | 原始计划文件删除 |
| 2026-04-23-simulation-user-journey.md | `docs/plans/` | ✅ 已完成 | DAG 执行引擎 + 前端 DAG 可视化已实现 | 原始计划文件删除 |
| 2026-04-24-simulation-dag-optimization.md | `docs/plans/` | ✅ 已完成 | G6→ReactFlow+dagre 渲染引擎替换，为变更记录类文档 | 原始计划文件删除 |
| 2026-04-25-examples-case-optimization.md | `docs/plans/` | ✅ 已完成 | 4 特征补齐 (真实口径/资产可见/可编辑/可反证)，案例闭环能力 | 原始计划文件删除 |

---

## 分类标签说明

| 标签 | 含义 |
|------|------|
| ✅ 已完成 | 计划全部实施完毕，功能已上线 |
| ⚠️ 部分完成 | 核心功能完成，部分 P2/P3 任务待后续 |
| 🔄 已归档 | 计划未实施或已过时，设计结论已体现在其它正式文档中 |

## 关键提取结论

以下是从各计划中提炼的、未被 `02-design/` 或 RFC 明确记录的设计洞见：

1. **Agent 基础设施分阶段策略** (agent-friendly): P0(MCP架构+Schema修复+错误处理) → P1(描述增强+Dry-run) → P2(版本管理+影响分析)，优先级划分可复用
2. **竞争分析结论** (use-case-plan): 案例编号保留 case1/case3/case4.. 不补 case2；Case 4 采用半自动优先策略
3. **案例闭环标准** (examples-case-optimization): 4 特征标准 (真实口径/资产可见/可编辑/可反证) 作为后续案例验收依据
4. **DAG 讨论点** (rule-engine-dag): 跨规则组依赖格式、推理边存储 (KuzuDB vs 内存) 等 4 个问题未形成最终决策 — 实施前需重新讨论

---

## 与 `docs/` 的边界

| 场景 | 查阅位置 |
|------|----------|
| 当前模块详细设计 | `docs/02-design/` |
| 当前开放任务 | `docs/TODO.md` |
| 本阶段路线 | `docs/ROADMAP.md` |
| 实施计划追溯 (已完成) | `docs-dev/plans/` ← **本目录** |
| 活跃实施计划 | 不应存放在此；应在独立的 Session 或 Issue 中追踪 |
