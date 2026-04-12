# 01-overview 目录说明

> **角色**: 项目认知入口
> **状态**: accepted
> **Phase**: mvp + phase1
> **Source of Truth**: true（仅针对愿景、目标、术语和边界）

## 适合谁看

- 第一次接触项目的人
- 需要快速建立系统边界感的实现者
- 需要确认目标 / 非目标的评审者

## 推荐阅读顺序

1. [`03-goals.md`](./03-goals.md)
2. [`04-modules.md`](./04-modules.md)
3. [`05-concepts.md`](./05-concepts.md)
4. [`06-tech-stack.md`](./06-tech-stack.md)
5. [`07-project-structure.md`](./07-project-structure.md)

## 目录内文档职责

| 文档 | 主要回答的问题 | 使用边界 |
|------|----------------|----------|
| `01-vision.md` | 为什么做这个项目 | 不承载实施细节 |
| `02-motivation.md` | 当前问题是什么 | 不承载具体 API / schema 设计 |
| `03-goals.md` | 各阶段要达到什么结果 | 阶段目标以此为主，不在实施文档重复 |
| `04-modules.md` | 系统有哪些大模块 | 只到模块级边界，不展开模块内实现 |
| `05-concepts.md` | 核心术语如何理解 | 需要继续与 Schema v2 术语收敛 |
| `06-tech-stack.md` | 当前技术路线原则是什么 | 不直接代表未来平台化能力边界 |
| `07-project-structure.md` | 代码如何组织 | 与当前仓库结构一致时才可视为真相 |

## 边界约束

- 本目录只表达 **愿景 / 目标 / 边界 / 术语 / 模块认知**
- 不在本目录定义详细字段结构、固定接口列表、实现级流程
- 若需要解释“当前实现”和“未来目标”的差异，应链接到 [`../04-migration-and-gap/README.md`](../04-migration-and-gap/README.md)

## 重点提示

- **[关键设计点]** 本目录是项目认知入口，不再承担详细设计说明书职责
- **[关键设计点]** `03-goals.md` 中的阶段目标仍是项目阶段判断的主入口
- **[待扩展]** `05-concepts.md` 仍需继续收敛 `Concept / Fact Object / Entity / Metric / Analytical Element` 的术语边界
- **[待核对代码]** `04-modules.md`、`07-project-structure.md` 中提到的模块命名，后续应与实际代码目录持续核验
