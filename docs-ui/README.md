# docs-ui 目录说明

> 本目录包含 ontology-engine-ui 前端代码的审查和设计文档。

---

## 文档索引

| 文档 | 类型 | 内容概述 |
|------|------|---------|
| [`01-frontend-architecture-review.md`](./01-frontend-architecture-review.md) | 架构审查 | 基于代码静态分析的架构总览、功能覆盖矩阵、代码质量评估 |
| [`02-frontend-ux-audit-rfc.md`](./02-frontend-ux-audit-rfc.md) | UX 审计 RFC | 基于 Playwright 浏览器测试的 7 个 UX 问题根因分析和改进方案 |
| [`03-rule-management-ui-design.md`](./03-rule-management-ui-design.md) | UI 设计文档 | 规则管理页面需求设计（详细 UI 布局和交互） |
| [`rfc/RFC-UI-001-rule-orchestration-frontend.md`](./rfc/RFC-UI-001-rule-orchestration-frontend.md) | 前端 RFC | 规则编排前端实现 RFC，关联后端 RFC-015 |

---

## 两份文档的关系

```
01-frontend-architecture-review.md          02-frontend-ux-audit-rfc.md
├── 技术栈分析                              ├── Playwright 浏览器测试发现
├── 路由结构                               ├── P0 问题 (阻断性)
├── 功能覆盖矩阵 (✅/⚠️)                   │   ├── Space 头部标签渲染错误
├── 代码质量评估                           │   └── 菜单导航选择器歧义
├── 改进建议 (P1/P2/P3)                    ├── P1 问题 (重要)
│   ├── L2/L3 创建支持缺失                 │   ├── 激活状态阻塞消费面
│   ├── 实体编辑功能缺失                   │   └── L2/L3 Schema 数据为空
│   ├── ExecutionReplay 未集成             ├── P2 问题 (改进)
│   └── ...                                │   ├── SchemaGraph G6 交互
└── 后续工作建议                           │   ├── RuleChainDAG 未集成
                                           │   └── ExecutionReplay 未集成
                                           └── 实施计划 + 验收测试
```

---

## 使用指南

| 场景 | 推荐文档 |
|------|---------|
| 了解前端整体架构和技术选型 | `01-frontend-architecture-review.md` |
| 修复 UX bug 或改进 UX | `02-frontend-ux-audit-rfc.md` |
| 准备前端迭代计划 | 结合两份文档的"改进项"章节 |
| Playwright E2E 测试 | 参考 `02-frontend-ux-audit-rfc.md` 的测试用例 |

---

## 辅助文件

| 文件 | 说明 |
|------|------|
| `explore_ui.py` | Playwright 探索脚本 v1 |
| `explore_ui2.py` | Playwright 探索脚本 v2 |

---

## 更新记录

| 日期 | 文档 | 变更 |
|------|------|------|
| 2026-04-14 | 01-frontend-architecture-review.md | 初始版本 |
| 2026-04-15 | 02-frontend-ux-audit-rfc.md | 基于浏览器测试的 UX 审计 RFC |
