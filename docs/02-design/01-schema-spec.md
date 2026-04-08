# Schema 规范

> **Version**: 1.0
> **Status**: MVP
> **Format**: KGML (YAML)

## 文件结构

```yaml
metadata:        # 版本与标识
types:           # 复合类型
enums:           # 枚举定义
concepts:        # 本体概念
metrics:         # 分析指标
rules:           # 业务规则
```

---

## 1. metadata

```yaml
metadata:
  id: "kg://supply_chain_finance/v1.0"  # 必须，全局唯一
  version: "1.0.0"                       # SemVer
  domain: "finance/supply_chain"         # 领域分类
  description: "供应链金融风控模型"       # 可选
```

---

## 2. types

定义复合数据结构。

```yaml
types:
  - name: Money
    base_type: object
    properties:
      value:
        type: decimal
        min: 0
      currency:
        type: string
        default: "CNY"

  - name: Percentage
    base_type: decimal
    min: 0
    max: 100
```

**约束**:
- `name` 全 Schema 唯一
- `base_type`: `string | integer | decimal | float | boolean | date | object`

---

## 3. enums

```yaml
enums:
  - name: RiskGrade
    values:
      - id: A
        label: "低风险"
        weight: 1.0
      - id: B
        label: "中风险"
        weight: 0.7
      - id: C
        label: "高风险"
        weight: 0.3
```

---

## 4. concepts

### 实体 (category: entity)

```yaml
concepts:
  - name: Supplier
    category: entity
    attributes:
      - name: supplier_id
        type: string
        required: true
        unique: true
      - name: registered_capital
        type: Money
      - name: risk_grade
        type: RiskGrade
    relations:
      - name: guarantees
        target: Supplier
        cardinality: "0..*"
        inverse: guaranteed_by
```

### 关系 (category: relation)

```yaml
  - name: GuaranteeRelation
    category: relation
    attributes:
      - name: amount
        type: Money
      - name: start_date
        type: date
```

**属性类型**:
- Builtin: `string`, `integer`, `decimal`, `float`, `boolean`, `date`
- Custom: `types` 或 `enums` 中定义的

**基数**:
- `1`: 必须且仅一个
- `0..1`: 可选
- `0..*`: 零到多个
- `1..*`: 至少一个

---

## 5. metrics

```yaml
metrics:
  - name: credit_score
    type: composite           # atomic | derived | composite
    scope: Supplier
    formula: "SUM(sub * weight)"  # 占位符，实际由算子执行
    dependencies:
      - business_stability
      - tax_compliance
```

| 类型 | 说明 |
|------|------|
| atomic | 原始输入，直接存储 |
| derived | 单实体计算，如 `score = f(attr)` |
| composite | 多指标聚合，如加权求和 |

---

## 6. rules

### 维度定义

```yaml
rule_dimensions:
  dimensions:
    - name: credit_assessment
      description: "融资授信评估"
      applicable_entities: [Supplier]
```

### 规则集

```yaml
ruleset:
  - id: R001_basic_eligibility
    priority: 100
    type: constraint           # constraint | inference | alert | decision
    scope:
      dimensions: [credit_assessment]
      entity_types: [Supplier]
    when:
      expression: "status == 'ACTIVE' AND registered_capital.value >= 1000000"
    then:
      action: approve_eligibility
      output:
        eligible: true
    else:
      action: reject_eligibility
      output:
        eligible: false
```

### when 表达式语法

| 类型 | 语法 | 示例 |
|------|------|------|
| 字段引用 | `field` / `field.sub` | `status`, `capital.value` |
| 比较 | `==`, `!=`, `>`, `<`, `>=`, `<=` | `score >= 80` |
| 逻辑 | `AND`, `OR`, `NOT` | `A AND B OR NOT C` |
| 字面量 | `'string'`, `123` | `'ACTIVE'`, `100` |
| 函数 | `today()`, `days_between(a, b)` | `days_between(d1, today()) < 30` |

### then/else action

内置 action:

| Action | 说明 | 输出 |
|--------|------|------|
| `approve_eligibility` | 准入通过 | `{eligible: true}` |
| `reject_eligibility` | 准入拒绝 | `{eligible: false, reason}` |
| `calculate_credit_score` | 信用评分 | `{score, grade}` |
| `trigger_alert` | 触发预警 | Alert 对象 |

---

## 校验清单

- [ ] `metadata.id` 全局唯一
- [ ] 所有 `name` 字段在各自作用域唯一
- [ ] `concepts[].relations[].target` 指向已定义概念
- [ ] `concepts[].attributes[].type` 有效
- [ ] `ruleset[].id` 唯一
- [ ] `when` 表达式语法正确
- [ ] `then.action` 为已知 action

---

## 完整示例

见 `examples/supply_chain_finance/schema.yaml`
