# L2: 归类分析 (Categorization)

---
status: draft
phase: phase1
source_of_truth: false
last_verified: 2026-04-12
verified_against: docs-only
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

> **Status**: v2.0 (with Declaration/Instance separation)
> **Date**: 2026-04-12

## 核心概念

L2 归类分析包含**声明**和**实例**两个层面：

| 层面 | 内容 | 说明 |
|------|------|------|
| **声明 (Declaration)** | 分类方案定义 | 维度、值范畴、打标规则 |
| **实例 (Instance)** | 实体的分类标签 | entity_id → dimension = value |

---

## 1. 声明：分类方案

### 1.1 结构

```yaml
categorization_declaration:
  id: string                    # 全局唯一标识
  name: string                  # 显示名称
  description: string | null    # 描述

  # 分类维度
  dimensions:
    - name: string              # 维度名称
      type: hierarchical | flat | derived | tags
      description: string

      # type = hierarchical 时
      levels:
        - name: string
          code_length: integer
      values:
        - code: string
          name: string
          children: [...]        # 层级结构

      # type = flat 时
      values:
        - id: string
          name: string

      # type = derived 时
      ruleset: string           # 引用打标规则 ID
      values:
        - id: string
          name: string

      # type = tags 时
      values:
        - id: string
          name: string
```

### 1.2 分类类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `hierarchical` | 层级分类 | 行业分类 (门类→大类→中类→小类) |
| `flat` | 平级分类 | 业务标签 (核心企业/白名单/重点供应商) |
| `derived` | 派生分类 | 由规则计算得出 (规模/风险等级) |
| `tags` | 多值标签 | 可同时打多个标签 |

### 1.3 示例

```yaml
# 行业分类 - 层级
categorization_declaration:
  id: industry_category
  name: 行业分类
  type: hierarchical

  levels:
    - name: section
      code_length: 1
    - name: division
      code_length: 2

  values:
    - code: "C"
      name: "制造业"
      children:
        - code: "31"
          name: "黑色金属冶炼和压延加工业"

# 企业规模 - 派生
categorization_declaration:
  id: company_scale
  name: 企业规模
  type: derived
  ruleset: determine_scale_rules
  values:
    - id: LARGE
      name: "大型企业"
    - id: MEDIUM
      name: "中型企业"
    - id: SMALL
      name: "小型企业"

# 风险等级 - 派生
categorization_declaration:
  id: risk_level
  name: 风险等级
  type: derived
  ruleset: assess_risk_rules
  values:
    - id: HIGH
      name: "高风险"
      color: "#FF4D4F"
    - id: MEDIUM
      name: "中风险"
      color: "#FAAD14"
    - id: LOW
      name: "低风险"
      color: "#52C41A"

# 业务标签 - 多值标签
categorization_declaration:
  id: business_tags
  name: 业务标签
  type: tags
  values:
    - id: CORE_ENTERPRISE
      name: "核心企业"
    - id: WHITELIST
      name: "白名单"
    - id: KEY_SUPPLIER
      name: "重点供应商"
```

---

## 2. 声明：打标规则

### 2.1 结构

```yaml
categorization_rules:
  id: string                    # 规则 ID
  name: string                  # 规则名称
  target_dimension: string       # 目标维度 ID

  rules:
    - priority: integer
      condition:
        and: [...]               # AND 条件
        or: [...]                # OR 条件
      result: string | list      # 单一值或标签列表
```

### 2.2 示例

```yaml
categorization_rules:
  id: determine_scale_rules
  name: 企业规模判定规则
  target_dimension: company_scale

  rules:
    - priority: 100
      condition:
        and:
          - fact: "annual_revenue"
            op: gte
            value: 400000000  # 4亿
          - fact: "employee_count"
            op: gte
            value: 1000
      result: LARGE

    - priority: 90
      condition:
        and:
          - fact: "annual_revenue"
            op: gte
            value: 20000000   # 2000万
          - fact: "employee_count"
            op: gte
            value: 300
      result: MEDIUM

    - priority: 0              # 默认
      condition: {}
      result: SMALL
```

---

## 3. 实例：分类标签

### 3.1 结构

```yaml
category_tag_instance:
  entity_id: string             # 实体 ID
  dimension: string             # 维度 ID
  value: string | list          # 分类值 (单一值或标签列表)
  source: string                # 来源: manual | rule | dataset
  rule_id: string | null       # 如果是规则打标，记录规则 ID
  timestamp: string             # 打标时间
```

### 3.2 示例

```yaml
# 实体的分类标签
category_tag_instances:
  - entity_id: SUP_001
    dimension: industry_category
    value: "C"                  # 制造业
    source: rule
    rule_id: null
    timestamp: "2026-04-12T10:00:00Z"

  - entity_id: SUP_001
    dimension: company_scale
    value: "MEDIUM"
    source: rule
    rule_id: determine_scale_rules
    timestamp: "2026-04-12T10:00:00Z"

  - entity_id: SUP_001
    dimension: business_tags
    value: ["CORE_ENTERPRISE", "WHITELIST"]  # 多标签
    source: manual
    timestamp: "2026-04-01T00:00:00Z"
```

---

## 4. 运行时行为

### 4.1 分类引擎

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
                # 编译 L2 规则为 L4 格式，复用 RuleExecutor
                rules = self._compile_to_l4_rules(declaration)
                result = self.rule_executor.execute(entity.id, dimension_id, rules)
                value = result.computed.get(dimension_id)
            elif declaration.type == "flat":
                value = self.match_flat(entity, declaration)
            elif declaration.type == "tags":
                value = self.apply_tag_rules(entity, declaration)

            tags.set(dimension_id, value)

        return tags
```

### 4.2 执行时机

| 来源 | 时机 |
|------|------|
| `manual` | 用户手动打标 |
| `rule` | 规则执行时自动打标 |
| `dataset` | Dataset 同步时更新 |

---

## 5. API 设计

### 5.1 声明 CRUD

```
GET    /v1/management/{spaceId}/schema/L2/categorizations
POST   /v1/management/{spaceId}/schema/L2/categorizations
GET    /v1/management/{spaceId}/schema/L2/categorizations/{id}
PUT    /v1/management/{spaceId}/schema/L2/categorizations/{id}
DELETE /v1/management/{spaceId}/schema/L2/categorizations/{id}
```

### 5.2 实例管理

```
GET    /v1/management/{spaceId}/instances/category-tags
POST   /v1/management/{spaceId}/instances/category-tags
PUT    /v1/management/{spaceId}/instances/category-tags/{entityId}/{dimension}
DELETE /v1/management/{spaceId}/instances/category-tags/{entityId}/{dimension}
```

---

## 6. 与 v1 的区别

| v1 | v2 |
|-----|-----|
| 无明确分类层 | 独立的 categorization 层 |
| 分类逻辑散落在 rules | 分类规则集中管理 |
| 无法多维度叠加 | 支持多维度分类共存 |
| 分类结果混在 entity.attributes | 分类标签独立存储 |

---

*文档结束*
