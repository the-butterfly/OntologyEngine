# L2: 归类分析 (Categorization)

---
status: draft
phase: phase1
source_of_truth: false
last_verified: 2026-04-14
verified_against: docs/05-schema-v2/09-canonical-schema-spec.md
related_docs:
  - 00-overview.md
  - 00b-semantic-space-architecture.md
  - 01-fact-objects.md
  - 03-analytical-elements.md
  - 04-business-logic.md
  - 09-canonical-schema-spec.md
related_adrs:
  - architecture/decisions/010-semantic-space-lifecycle.md
---

> **Status**: v2.0 (aligned with Canonical Grammar)
> **Last Verified**: 2026-04-14
> **verified_against**: docs/05-schema-v2/09-canonical-schema-spec.md

## 核心概念

L2 归类分析包含**声明**和**实例**两个层面：

| 层面 | 内容 | 说明 |
|------|------|------|
| **声明 (Declaration)** | 分类方案定义 | 维度、值范畴、打标规则 |
| **实例 (Instance)** | 实体的分类标签 | entity_id → dimension = value |

---

## 1. 声明：分类方案

### 1.1 结构

在 Schema v2 中，分类维度通过 `categorizations.dimensions[]` 声明：

```yaml
categorizations:
  dimensions:
    - name: string                    # 维度名，全局唯一
      description: string?
      type: enum                      # hierarchical | derived | tag_based
      values: [ValueDefinition]?      # 当 type=hierarchical 或 tag_based 时
      rule_logic: string?             # 当 type=derived 时，引用 RuleLogicDeclaration.name
      color: string?                  # 可选，hex 色值，用于可视化（如 "#FF4D4F"）
```

### ValueDefinition

```yaml
- code: string | integer          # 分类编码
  name: string                    # 人类可读名称
  description: string?
  color: string?                  # 可选色值
```

### 1.2 分类类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `hierarchical` | 层级分类 | 行业分类 (门类→大类→中类→小类) |
| `derived` | 派生分类 | 由 L4 规则逻辑计算得出 (规模/风险等级) |
| `tag_based` | 多值标签 | 可同时打多个标签 |

### 1.3 示例

```yaml
# 行业分类 - 层级
categorizations:
  dimensions:
    - name: industry_category
      description: 行业分类
      type: hierarchical
      values:
        - code: "C"
          name: "制造业"
          children:
            - code: "31"
              name: "黑色金属冶炼和压延加工业"

# 企业规模 - 派生
    - name: company_scale
      description: 企业规模
      type: derived
      rule_logic: determine_scale    # 引用 business_logic.rule_logics[].name
      values:
        - code: LARGE
          name: "大型企业"
        - code: MEDIUM
          name: "中型企业"
        - code: SMALL
          name: "小型企业"
        - code: MICRO
          name: "微型企业"

# 风险等级 - 派生
    - name: risk_level
      description: 风险等级
      type: derived
      rule_logic: assess_risk
      color: "#FF4D4F"
      values:
        - code: HIGH
          name: "高风险"
          color: "#FF4D4F"
        - code: MEDIUM
          name: "中风险"
          color: "#FAAD14"
        - code: LOW
          name: "低风险"
          color: "#52C41A"

# 业务标签 - 多值标签
    - name: business_tags
      description: 业务标签
      type: tag_based
      values:
        - code: CORE_ENTERPRISE
          name: "核心企业"
        - code: WHITELIST
          name: "白名单"
        - code: KEY_SUPPLIER
          name: "重点供应商"
```

---

## 2. L2 → L4 复用语义

### 2.1 derived 维度的工作原理

`type=derived` 的维度通过 `rule_logic` 引用 **L4 规则逻辑** 的输出：

```
L2 derived 维度 ──引用──► L4 rule_logic ──包含──► steps[].condition/result
                                              │
                                              ▼
                                       维度值列表（values）
                                       与规则逻辑中的 result 值对应
```

**核心语义**：
- 维度声明本身只定义维度的"槽位"（name、values），不重复定义计算逻辑
- 计算逻辑由 L4 `rule_logics` 提供，通过 `rule_logic` 字段引用
- 维度值（`values` 中的 `code`）与规则逻辑中 `result` 返回的枚举值一一对应

### 2.2 示例说明

```yaml
# L2: 声明 derived 维度，引用 L4 规则逻辑
categorizations:
  dimensions:
    - name: company_scale
      type: derived
      rule_logic: determine_scale    # ← 引用 L4 rule_logic.name
      values:
        - code: LARGE
          name: "大型企业"
        - code: MEDIUM
          name: "中型企业"
        - code: SMALL
          name: "小型企业"
        - code: MICRO
          name: "微型企业"

# L4: 规则逻辑输出维度值（result 对应 dimensions.values[].code）
business_logic:
  rule_logics:
    - name: determine_scale
      type: switch
      steps:
        - id: step1
          condition:
            expression: "annual_revenue >= 400000000 AND employee_count >= 1000"
          action:
            type: assign_category
            category: LARGE    # ← 与 dimensions.values[].code 对应
        - id: step2
          condition:
            expression: "annual_revenue >= 20000000 AND employee_count >= 300"
          action:
            type: assign_category
            category: MEDIUM
        - id: step3
          condition: {}
          action:
            type: assign_category
            category: SMALL    # 默认
```

### 2.3 为什么复用 L4？

1. **避免重复定义**：计算逻辑只需在 L4 定义一次
2. **统一执行引擎**：分类计算与业务规则复用同一执行器
3. **可组合性**：derived 维度可以引用任何 L4 规则逻辑，包括复合规则

---

## 3. 声明：打标规则

### 3.1 结构

打标规则在 L4 `rule_logics` 中定义，L2 只通过 `rule_logic` 引用。

### 3.2 示例

```yaml
# L4 rule_logic: 企业规模判定规则
business_logic:
  rule_logics:
    - name: determine_scale
      description: 企业规模判定规则
      type: switch
      steps:
        - id: check_large
          priority: 100
          condition:
            and:
              - "annual_revenue >= 400000000"  # 4亿
              - "employee_count >= 1000"
          action:
            type: assign_category
            category: LARGE

        - id: check_medium
          priority: 90
          condition:
            and:
              - "annual_revenue >= 20000000"    # 2000万
              - "employee_count >= 300"
          action:
            type: assign_category
            category: MEDIUM

        - id: default_small
          priority: 0                          # 默认
          condition: {}
          action:
            type: assign_category
            category: SMALL
```

---

## 4. 实例：分类标签

### 4.1 结构

```yaml
category_tag_instance:
  entity_id: string             # 实体 ID
  dimension: string             # 维度 ID
  value: string | list          # 分类值 (单一值或标签列表)
  source: string                # 来源: manual | rule | dataset
  rule_id: string | null       # 如果是规则打标，记录规则 ID
  timestamp: string             # 打标时间
```

### 4.2 示例

```yaml
# 实体的分类标签
category_tag_instances:
  - entity_id: SUP_001
    dimension: industry_category
    value: "C"                  # 制造业
    source: rule
    rule_id: null
    timestamp: "2026-04-14T10:00:00Z"

  - entity_id: SUP_001
    dimension: company_scale
    value: "MEDIUM"
    source: rule
    rule_id: determine_scale
    timestamp: "2026-04-14T10:00:00Z"

  - entity_id: SUP_001
    dimension: business_tags
    value: ["CORE_ENTERPRISE", "WHITELIST"]  # 多标签
    source: manual
    timestamp: "2026-04-01T00:00:00Z"
```

---

## 5. 运行时行为

### 5.1 分类引擎

L2 复用 L4 规则引擎执行：

```python
class CategorizationEngine:
    """L2 归类引擎 - 复用 L4 规则引擎"""

    def categorize(self, entity: Entity, dimensions: list[str]) -> CategoryTags:
        """为实体打标"""
        tags = CategoryTags()

        for dimension_id in dimensions:
            declaration = self.get_declaration(dimension_id)

            if declaration.type == "hierarchical":
                value = self.match_hierarchical(entity, declaration)
            elif declaration.type == "derived":
                # 通过 rule_logic 引用执行 L4 规则逻辑
                rule_logic = self.get_rule_logic(declaration.rule_logic)
                result = self.rule_executor.execute(entity.id, dimension_id, rule_logic)
                value = result.computed.get(dimension_id)
            elif declaration.type == "tag_based":
                value = self.apply_tag_rules(entity, declaration)

            tags.set(dimension_id, value)

        return tags
```

### 5.2 执行时机

| 来源 | 时机 |
|------|------|
| `manual` | 用户手动打标 |
| `rule` | 规则执行时自动打标（通过 L4 rule_logic） |
| `dataset` | Dataset 同步时更新 |

---

## 6. API 设计

### 6.1 声明 CRUD

```
GET    /v1/management/{spaceId}/schema/L2/categorizations
POST   /v1/management/{spaceId}/schema/L2/categorizations
GET    /v1/management/{spaceId}/schema/L2/categorizations/{id}
PUT    /v1/management/{spaceId}/schema/L2/categorizations/{id}
DELETE /v1/management/{spaceId}/schema/L2/categorizations/{id}
```

### 6.2 实例管理

```
GET    /v1/management/{spaceId}/instances/category-tags
POST   /v1/management/{spaceId}/instances/category-tags
PUT    /v1/management/{spaceId}/instances/category-tags/{entityId}/{dimension}
DELETE /v1/management/{spaceId}/instances/category-tags/{entityId}/{dimension}
```

---

## 7. 与 v1 的区别

| v1 | v2 (Canonical) |
|-----|----------------|
| 无明确分类层 | 独立的 categorization 层 |
| `ruleset` | `rule_logic` 引用 L4 规则逻辑 |
| 分类逻辑散落在 rules | 分类规则集中在 L4 rule_logics |
| 无法多维度叠加 | 支持多维度分类共存 |
| 分类结果混在 entity.attributes | 分类标签独立存储 |

---

## 8. 完整结构参考

完整 Schema v2 语法结构参见 [09-canonical-schema-spec.md](./09-canonical-schema-spec.md) 的 **L2: categorizations** 节。

*文档结束*
