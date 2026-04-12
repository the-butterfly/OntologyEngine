# L1: 事实对象 (Factual Objects)

---
status: draft
phase: phase1
source_of_truth: false
last_verified: 2026-04-12
verified_against: docs-only
related_docs:
  - 00-overview.md
  - 00b-semantic-space-architecture.md
  - 02-categorization.md
  - 03-analytical-elements.md
  - 04-business-logic.md
  - 06-dataset-and-sync.md
  - 09-canonical-schema-spec.md
---

> **Status**: v2.0 (with Declaration/Instance separation)
> **Date**: 2026-04-12

## 核心概念

L1 事实对象包含**声明**和**实例**两个层面：

| 层面 | 内容 | 说明 |
|------|------|------|
| **声明 (Declaration)** | 实体类型定义 | 属性、关系、约束 |
| **实例 (Instance)** | 具体实体数据 | entity_id + attributes + relations |

---

## 1. 声明：实体类型定义

### 1.1 结构

```yaml
fact_object_declaration:
  id: string                    # 全局唯一标识
  name: string                  # 类型名称 (如 Company, Supplier)
  description: string | null    # 描述

  # 事实属性定义
  properties:
    - name: string
      type: string | custom_type
      required: boolean
      unique: boolean
      default: any
      description: string

  # 关系定义
  relations:
    - name: string
      target: string            # 目标实体类型
      description: string
      attributes: [...]         # 关系的属性

  # 约束
  constraints:
    - type: unique
      fields: [string]
    - type: referential_integrity
      relation: string
      target: string
```

### 1.2 示例

```yaml
fact_object_declaration:
  id: Company
  name: 企业
  description: 企业法人主体

  properties:
    - name: unified_social_code
      type: string
      required: true
      unique: true
      description: 统一社会信用代码

    - name: company_name
      type: string
      required: true
      description: 企业名称

    - name: registered_capital
      type: Money
      description: 注册资本

    - name: establishment_date
      type: date
      description: 成立日期

    - name: legal_representative
      type: string
      description: 法定代表人

  relations:
    - name: Guarantee
      target: Company
      description: 担保关系
      attributes:
        - name: guarantee_amount
          type: Money
          required: true
        - name: guarantee_type
          type: enum
          enum_type: GuaranteeType

    - name: Transaction
      target: Company
      description: 交易关系
      attributes:
        - name: transaction_amount
          type: Money
        - name: transaction_date
          type: date
```

---

## 2. 声明：关系类型定义

### 2.1 结构

```yaml
relation_declaration:
  id: string                    # 全局唯一标识
  name: string                  # 关系名称
  source: string               # 源实体类型
  target: string               # 目标实体类型

  attributes: [...]             # 关系属性

  constraints:
    - type: cascade | restrict
      on_delete: ...
```

### 2.2 示例

```yaml
relation_declaration:
  id: Guarantee
  name: 担保
  source: Company  # 担保方
  target: Company  # 被担保方

  attributes:
    - name: guarantee_amount
      type: Money
      required: true
    - name: guarantee_type
      type: enum
      enum_type: GuaranteeType
    - name: start_date
      type: date
    - name: end_date
      type: date
```

---

## 3. 实例：实体数据

### 3.1 结构

```yaml
entity_instance:
  entity_id: string             # 实体唯一标识
  _concept: string              # 实体类型 (关联声明)
  _concept_type: string         # 同上，兼容旧字段

  # 事实属性
  properties:
    unified_social_code: "91110000XXXXXXXX"
    company_name: "XX 科技有限公司"
    registered_capital:
      value: 10000000
      currency: "CNY"
    establishment_date: "2020-01-15"

  # 关系
  relations:
    - relation_id: string
      relation_type: Guarantee
      target_id: string         # 目标实体 ID
      attributes:
        guarantee_amount:
          value: 5000000
          currency: "CNY"
        guarantee_type: MORTGAGE

  # 元数据
  _created_at: string
  _updated_at: string
  _version: integer
```

### 3.2 示例

```yaml
entity_instance:
  entity_id: SUP_001
  _concept: Company
  company_name: "XX 科技有限公司"
  registered_capital:
    value: 10000000
    currency: "CNY"
  establishment_date: "2020-01-15"
  industry_category: "C"        # L2 分类标签 (关联)

  relations:
    - relation_id: REL_001
      relation_type: Guarantee
      target_id: CORE_001
      attributes:
        guarantee_amount:
          value: 5000000
          currency: "CNY"
        guarantee_type: MORTGAGE
```

---

## 4. 属性类型

### 4.1 基础类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `string` | 字符串 | `"ABC Company"` |
| `integer` | 整数 | `1000000` |
| `decimal` | 精确小数 | `1000000.50` |
| `float` | 浮点数 | `3.14159` |
| `boolean` | 布尔 | `true` |
| `date` | 日期 | `2026-04-08` |
| `datetime` | 日期时间 | `2026-04-08T10:00:00Z` |

### 4.2 复合类型

```yaml
custom_types:
  - name: Money
    properties:
      value:
        type: decimal
      currency:
        type: string
        default: "CNY"

  - name: Address
    properties:
      province: string
      city: string
      district: string
```

### 4.3 枚举类型

```yaml
enums:
  - name: GuaranteeType
    values:
      - id: MORTGAGE
        label: "抵押担保"
      - id: PLEDGE
        label: "质押担保"
      - id: GUARANTEE
        label: "保证担保"
```

---

## 5. 设计原则

1. **纯粹性** —— 只包含可观测、可验证的事实
2. **稳定性** —— 事实结构变化频率低
3. **无业务含义** —— 不包含"评分"、"等级"等分析结果
4. **完备性** —— 支持业务所需的全部基础数据
5. **声明/实例分离** —— 类型定义与具体数据分离

---

## 6. 数据同步

实体实例可以通过 Dataset 同步：

```yaml
# Dataset 映射配置
dataset:
  id: erp_suppliers
  mapping_rules:
    - target_entity_type: Company
      field_mappings:
        supplier_code: entity_id
        company_name: company_name
        reg_capital: registered_capital.value
      filters:
        - field: status
          operator: eq
          value: ACTIVE
```

详见 [数据集与同步](./06-dataset-and-sync.md)

---

## 7. API 设计

### 7.1 声明 CRUD

```
GET    /v1/management/{spaceId}/schema/L1/fact-objects
POST   /v1/management/{spaceId}/schema/L1/fact-objects
GET    /v1/management/{spaceId}/schema/L1/fact-objects/{id}
PUT    /v1/management/{spaceId}/schema/L1/fact-objects/{id}
DELETE /v1/management/{spaceId}/schema/L1/fact-objects/{id}
```

### 7.2 实例 CRUD

```
GET    /v1/management/{spaceId}/instances/entities
POST   /v1/management/{spaceId}/instances/entities
GET    /v1/management/{spaceId}/instances/entities/{entityId}
PUT    /v1/management/{spaceId}/instances/entities/{entityId}
DELETE /v1/management/{spaceId}/instances/entities/{entityId}
GET    /v1/management/{spaceId}/instances/entities/{entityId}/versions
```

---

## 8. 与 v1 的区别

| v1 | v2 |
|-----|-----|
| concepts 混杂实体/关系 | 明确分为 entities/relations |
| 可含派生属性 | 只含事实属性 |
| 无类型/实例分离 | Declaration/Instance 分离 |
| dimension_attributes 误用 | 已移除 |

---

*文档结束*
