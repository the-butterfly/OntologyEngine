# Schema v2 Canonical Grammar Spec

> **状态**: accepted
> **Phase**: phase1
> **Source of Truth**: true（仅针对 Schema v2 根级 grammar）
> **Last Verified**: 2026-04-12 (`docs-only`)

## 作用范围

本文件只负责冻结一件事：**Schema v2 完整文档的根级组织方式与命名约定。**

它不试图一次性冻结所有字段细节，也不替代各层专题文档。今后如果 `00-overview.md`、分层专题、完整示例之间出现根级结构不一致，以本文件为准。

## Canonical 根级结构

```yaml
schema_version: "2.0"
semantic_space:
  id: "space.supply_chain_finance"
  name: "供应链金融语义空间"
  type: management
  status: DRAFT

fact_objects:
  # L1 声明集合；内部可继续细分为 entities / relations / shared_types

categorizations:
  # L2 声明集合；内部可继续细分为 dimensions / tag_sets / mappings

analytical_elements:
  # L3 声明集合；内部可继续细分为 metrics / indicators / scorecards

business_logic:
  rule_definitions: []
  rule_logics: []
```

## Canonical 命名约定

1. `semantic_space` 是完整 Schema v2 文档的顶层容器元数据
2. `fact_objects`、`categorizations`、`analytical_elements`、`business_logic` 是四层主容器
3. `business_logic.rule_definitions` 与 `business_logic.rule_logics` 是当前推荐的规范化规则组织方式
4. 单篇主题文档中出现的 `fact_object_declaration`、`analytical_element_declaration` 等名字，只是**局部片段示意**，不是完整文件的根级键名

## 非 Canonical 写法与迁移建议

| 历史 / 示例写法 | 当前判断 | 迁移建议 |
|----------------|----------|----------|
| `categorization` | 非 canonical | 统一改为 `categorizations` |
| `business_logic.rule_groups` | 非 canonical | 拆分为 `rule_definitions + rule_logics` |
| `fact_object_declaration` | 片段示例 | 仅在局部文档中保留，不作为完整文件根键 |
| `analytical_element_declaration` | 片段示例 | 仅在局部文档中保留，不作为完整文件根键 |

## 与其他文档的关系

- [`00-overview.md`](./00-overview.md): 负责讲设计意图，不再定义根级 grammar 真相
- [`05-complete-example.md`](./05-complete-example.md): 负责展示可读样例，后续需要继续向本文件同步
- [`01-fact-objects.md`](./01-fact-objects.md) ～ [`04-business-logic.md`](./04-business-logic.md): 负责定义各层语义，不重复定义根级组织方式

## 当前仍未冻结的内容

- **[待扩展]** `fact_objects`、`categorizations`、`analytical_elements` 容器内部的最终子键命名
- **[待扩展]** L3 是否允许保留标准 `formula` 以及与 L4 的覆盖关系
- **[待扩展]** `rule_group` 是否允许作为 authoring sugar 存在，并在加载阶段编译为 canonical model
- **[待扩展]** `semantic_space.status` 中 `PUBLISHED` 应表达为状态还是快照事件

## 使用规则

1. 新增或重写 Schema v2 文档时，不得再次自定义另一套完整根级 grammar
2. 完整 YAML 示例若与本文件不一致，应标记 **[待扩展]** 或直接修正
3. 若要变更本文件，需要同步更新 [`../STATUS.md`](../STATUS.md) 与迁移层文档
