# docs-ui 目录说明

> 本目录包含 ontology-engine-ui 前端代码的审查和设计文档。

---

## 文档索引

| 文档 | 类型 | 内容概述 |
|------|------|---------|
| [`01-frontend-architecture-review.md`](./01-frontend-architecture-review.md) | 架构审查 | 基于代码静态分析的架构总览、功能覆盖矩阵、代码质量评估 |
| [`02-frontend-ux-audit-rfc.md`](./02-frontend-ux-audit-rfc.md) | UX 审计 RFC | 基于 Playwright 浏览器测试的 7 个 UX 问题根因分析和改进方案 |
| [`03-rule-management-ui-design.md`](./03-rule-management-ui-design.md) | UI 设计文档 | 规则管理页面需求设计（详细 UI 布局和交互） |
| [`04-knowledge-lifecycle-ui-design.md`](./04-knowledge-lifecycle-ui-design.md) | **UI 设计文档** | **知识库全生命周期交互设计：构建/管理/消费三阶段 + Agent活动日志** |
| [`rfc/RFC-UI-001-rule-orchestration-frontend.md`](./rfc/RFC-UI-001-rule-orchestration-frontend.md) | 前端 RFC | 规则编排前端实现 RFC，关联后端 RFC-015 |

---

## 文档关系

```
01-frontend-architecture-review.md          02-frontend-ux-audit-rfc.md
├── 技术栈分析                              ├── Playwright 浏览器测试发现
├── 路由结构                               ├── P0 问题 (阻断性)
├── 功能覆盖矩阵 (✅/⚠️)                   ├── P1 问题 (重要)
├── 代码质量评估                           ├── P2 问题 (改进)
└── 后续工作建议                           └── 实施计划 + 验收测试

03-rule-management-ui-design.md             04-knowledge-lifecycle-ui-design.md
├── 规则管理页面设计                        ├── 知识库构建页面（导入+提取+待审区）
├── 规则四元素交互                          ├── 知识库管理页面（矛盾看板+审批+更正时间线）
├── 规则编排画布                            ├── 知识库消费页面（分层检索+证据链+溯源）
└── 验证与发布流程                          ├── Agent活动日志
                                           └── 16个体验点 + API端点 + 组件设计
```

---

## 使用指南

| 场景 | 推荐文档 |
|------|---------|
| 了解前端整体架构和技术选型 | `01-frontend-architecture-review.md` |
| 修复 UX bug 或改进 UX | `02-frontend-ux-audit-rfc.md` |
| 规则管理页面设计 | `03-rule-management-ui-design.md` |
| **知识库构建/管理/消费交互设计** | **`04-knowledge-lifecycle-ui-design.md`** |
| **Agent与人的协作交互** | **`04-knowledge-lifecycle-ui-design.md`** |
| 准备前端迭代计划 | 结合所有文档的改进项章节 |
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
| 2026-04-15 | 03-rule-management-ui-design.md | 规则管理页面设计 |
| 2026-04-30 | 04-knowledge-lifecycle-ui-design.md | 知识库全生命周期交互设计（新增） |
