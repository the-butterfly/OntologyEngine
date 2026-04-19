# 05-schema-v2 目录说明

> **角色**: 目标架构 / Schema v2 规范区
> **状态**: draft
> **Phase**: phase1 + future
> **Source of Truth**: 主题级（其中根级 grammar 以 `09-canonical-schema-spec.md` 为准）

## 这个目录回答什么

本目录回答的是：**OntologyEngine 未来希望收敛到什么样的 Schema 结构、语义分层和空间化能力。**

它不是当前代码的直接镜像；若需要判断实现现状，请先回到 [`../02-design/README.md`](../02-design/README.md)。

## 推荐阅读顺序

1. [`00-overview.md`](./00-overview.md)
2. [`09-canonical-schema-spec.md`](./09-canonical-schema-spec.md)
3. [`00b-semantic-space-architecture.md`](./00b-semantic-space-architecture.md)
4. [`01-fact-objects.md`](./01-fact-objects.md)
5. [`02-categorization.md`](./02-categorization.md)
6. [`03-analytical-elements.md`](./03-analytical-elements.md)
7. [`04-business-logic.md`](./04-business-logic.md)
8. [`07-rule-declaration-and-instance.md`](./07-rule-declaration-and-instance.md)
9. [`06-dataset-and-sync.md`](./06-dataset-and-sync.md)
10. [`08-version-management.md`](./08-version-management.md)
11. [`05-complete-example.md`](./05-complete-example.md)

## 主题级 SoT 划分

| 主题 | 文档 | 说明 |
|------|------|------|
| 整体设计意图 | [`00-overview.md`](./00-overview.md) | 讲清目标与整体关系，不再承担 grammar 真相 |
| Schema v2 根语法 | [`09-canonical-schema-spec.md`](./09-canonical-schema-spec.md) | **[单一事实源]** |
| 语义空间容器 | [`00b-semantic-space-architecture.md`](./00b-semantic-space-architecture.md) | 空间概念、角色、状态 |
| 分层实体 / 归类 / 分析 / 业务逻辑 | `01` ～ `04` | 各层职责和语义边界 |
| 规则声明与实例分离 | [`07-rule-declaration-and-instance.md`](./07-rule-declaration-and-instance.md) | Rule Definition 与 Rule Logic 分离 |
| 数据集 / 同步 / 版本 | `06`、`08` | 目标态扩展能力 |
| 完整示例 | [`05-complete-example.md`](./05-complete-example.md) | 只作为说明性样例，不是 grammar SoT |

## 重点提示

- **[关键设计点]** 根级 Schema grammar 以后统一以 [`09-canonical-schema-spec.md`](./09-canonical-schema-spec.md) 为准
- **[关键设计点]** `00-overview.md` 是概览，不再承担“完整文件格式定义”的职责
- **[待扩展]** L3 / L4 计算边界、Rule authoring sugar、空间状态机仍需继续冻结为更稳定的决策文档
- **[待扩展]** `05-complete-example.md` 需要继续向 canonical grammar 靠拢
- **[待核对代码]** 本目录多数内容面向目标态，不能直接等价理解为当前代码已实现能力
