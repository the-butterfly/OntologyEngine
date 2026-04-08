# KGML Schema 格式规范

**版本**: 1.0
**日期**: 2026-04-08
**状态**: 初稿

---

## 1. 概述

KGML (Knowledge Graph Markup Language) 是 OntologyEngine 的配置格式，通过 YAML 文件定义：
- 类型系统 (types)
- 枚举 (enums)
- 概念/本体 (concepts)
- 指标 (metrics)
- 规则 (rules)

---

## 2. Schema 文件结构

```yaml
# KGML Schema v3.0
metadata:          # 元信息层
types:             # 类型系统
enums:             # 枚举类型
concepts:          # 概念/本体
metrics:            # 指标层
rules:              # 规则推理层
data_sources:       # 数据源映射（可选）
vector_config:      # 向量检索配置（可选）
llm_config:        # 大模型配置（可选）
```

---

## 3. metadata 模块

```yaml
metadata:
  id: "kg://example/schema/1.0"   # 必须，唯一标识
  name: "schema name"              # 可选
  description: "description"       # 可选
  version: "1.0.0"                # 默认 "1.0.0"
  schema_version: "3.0"           # 默认 "3.0"
  domain: "domain/path"            # 可选
  language: ["zh", "en"]          # 可选
  license: "Apache-2.0"           # 可选
```

---

## 4. types 模块

定义复合类型。

```yaml
types:
  - name: "Money"                  # 必须，类型名
    description: "带货币的金额"     # 可选
    base_type: "object"            # 必须: object/string/integer/decimal/float/boolean/date
    properties:                    # 可选，base_type=object 时使用
      value:
        type: "decimal"            # 属性类型
        description: "数值"
      currency:
        type: "string"
        default: "CNY"            # 默认值
    min: 0.0                       # 可选，数值约束
    max: 100.0                     # 可选
    enum: ["A", "B", "C"]          # 可选，枚举值列表
```

**约定**：
- `name` 在所有 types 中必须唯一
- `base_type` 为 `object` 时 `properties` 必填
- `base_type` 为简单类型时不应有 `properties`

---

## 5. enums 模块

定义枚举类型。

```yaml
enums:
  - name: "SupplierStatus"          # 必须，枚举名
    description: "供应商经营状态"   # 可选
    values:
      - id: "ACTIVE"               # 必须，枚举值 ID
        label: "正常经营"           # 可选
        weight: 1.0                 # 可选，权重
        severity_score: 1           # 可选，严重程度
```

**约定**：
- `name` 在所有 enums 中必须唯一
- `values[].id` 在当前 enum 中必须唯一

---

## 6. concepts 模块

定义实体和关系类型。

```yaml
concepts:
  - name: "Supplier"                # 必须，概念名
    description: "供应商"            # 可选
    category: "entity"               # 必须: entity/relation
    attributes:                      # 属性列表
      - name: "supplier_id"         # 属性名
        type: "string"               # 类型引用（builtin/type/enum 名）
        required: true              # 可选，默认 false
        unique: true                # 可选，默认 false
        default: "default_value"    # 可选
        description: "描述"          # 可选
        validation:                  # 可选，验证规则
          pattern: "^[A-Z0-9]{18}$" # 正则验证
    relations:                       # 关系列表
      - name: "has_invoice"         # 关系名
        target: "Invoice"            # 目标概念名
        cardinality: "0..*"         # 基数: 1/0..1/0..*/1..*
        description: "描述"          # 可选
        inverse: "issued_by"         # 可选，反向关系名
```

**约定**：
- `name` 在所有 concepts 中必须唯一
- `category=relation` 时 attributes 通常为空
- `relations[].target` 必须引用已定义的概念
- `relations[].inverse` 引用目标概念中对应的反向关系

---

## 7. metrics 模块

定义指标计算规则。

```yaml
metrics:
  - name: "credit_score"             # 必须，指标名
    description: "综合信用评分"       # 可选
    type: "composite"                # 必须: atomic/derived/composite/graph
    scope: "Supplier"                # 适用的概念名
    formula: "SUM(component * weight)" # 指标公式（见下方说明）
    dependencies:                    # 依赖的其他指标
      - "business_stability_score"
      - "tax_compliance_score"
```

**指标类型说明**：

| 类型 | 说明 | 当前状态 |
|------|------|----------|
| `atomic` | 直接输入的指标 | 已实现 |
| `derived` | 基于 atomic 指标计算 | 部分实现（公式为占位符） |
| `composite` | 多维度聚合 | 部分实现（公式为占位符） |
| `graph` | 图算法指标 | 未实现 |

**⚠️ 重要**：当前 `formula` 字段为**占位符**，引擎不会执行这些公式。
实际计算逻辑在 `executor.py` 的 `_calculate_credit_score()` 等方法中实现。
这意味着 schema.yaml 定义的公式和实际执行的算法可能不一致。

---

## 8. rules 模块

定义规则推理逻辑。

### 8.1 rule_dimensions

```yaml
rule_dimensions:
  dimensions:
    - name: "credit_assessment"      # 维度名
      description: "融资授信评估"     # 可选
      applicable_entities: ["Supplier"] # 适用的概念
      triggers:                      # 可选，触发条件
        - event: "financing_application_submitted"
          entity: "Supplier"
```

### 8.2 ruleset

```yaml
ruleset:
  - id: "R001_basic_eligibility"     # 必须，唯一规则 ID
    name: "基础准入检查"               # 可选
    description: "供应商融资基础资质"  # 可选
    type: "constraint"               # 类型: constraint/inference/alert/decision
    priority: 100                    # 优先级，数字越大越先执行
    enabled: true                    # 是否启用
    scope:                           # 作用范围
      dimensions: ["credit_assessment"]
      entity_types: ["Supplier"]
    when:                            # 触发条件
      expression: "status == 'ACTIVE'"  # 简单表达式
      # 或
      allOf:                         # 所有条件同时满足
        - expression: "status == 'ACTIVE'"
        - expression: "registered_capital.value >= 1000000"
      # 或
      anyOf:                         # 任一条件满足
        - expression: "overdue_ratio >= 15"
        - expression: "negative_news >= 3"
    then:                            # 满足条件时执行
      action: "approve_eligibility"  # 内置 action（见 8.3）
      output:                        # 输出数据
        eligible: true
      computation:                   # 可选，计算定义
        formula: "..."               # ⚠️ 当前不生效，仅占位
    else:                            # 不满足条件时执行（注意是 else 非 else_）
      action: "reject_eligibility"
      output:
        eligible: false
```

### 8.3 内置 Action

引擎内置以下 action：

| Action | 说明 | 输出字段 |
|--------|------|---------|
| `approve_eligibility` | 设置 eligible=true | `eligible: true` |
| `reject_eligibility` | 设置 eligible=false | `eligible: false`, `rejection_reason` |
| `calculate_credit_score` | 计算信用评分 | `credit_score`, `credit_grade` |
| `calculate_credit_limit` | 计算授信额度 | `credit_limit`, `level` |
| `determine_interest_rate` | 确定利率 | `interest_rate` |
| `trigger_alert` | 触发预警 | Alert 对象加入 context.alerts |
| `generate_decision` | 生成综合决策 | 当前为 no-op |

**未知 action 行为**：
- 引擎**忽略**未知 action，不抛出错误
- **建议**：在 schema 校验工具中添加非内置 action 的警告

### 8.4 Expression 语法

#### 支持的操作

| 类型 | 语法 |
|------|------|
| 字段引用 | `status`, `registered_capital.value` |
| 字符串字面量 | `'ACTIVE'`, `"string"` |
| 数值字面量 | `100`, `3.14` |
| 比较 | `==`, `!=`, `>`, `<`, `>=`, `<=` |
| 逻辑 | `AND`, `OR`, `NOT` |
| 成员检查 | `IN ('A', 'B')`, `IS NULL`, `IS NOT NULL` |
| 函数 | `today()`, `days_between(date1, date2)` |

#### 运算符优先级

`NOT` > `AND` > `OR`（左到右）

#### ⚠️ 危险模式

**已修复**：表达式解析器现在正确保护字符串字面量内的单个字母（如 `A>B`）。

**仍需注意**：字段值中包含 ` AND ` 或 ` OR `（带空格）可能导致误解析，因为 `AND`/`OR` 操作符通过字符串 split 实现，无法识别字符串字面量内的分隔符。例如：

```yaml
# 危险示例
# 如果 company_name 值为 "A AND B Corp"，且表达式为:
# company_name == 'A AND B Corp'
# 会被误解析
```

**长期方案**：ADR-003 规划的 AST 解析方案将彻底解决这些问题。

#### 已知限制

| 限制 | 状态 | 说明 |
|------|------|------|
| 字符串字面量内单个操作符 | ✅ 已修复 | `'A>B'` 不再误解析 |
| 字符串字面量内 ` AND ` / ` OR ` | ⚠️ 限制 | 避免在字段值中使用带空格的逻辑操作符 |
| CASE WHEN / IF ELSE 表达式 | ❌ 不支持 | schema.yaml 中的 CASE WHEN 公式为占位符 |
| 图查询表达式 | ❌ 不支持 | `graph_query` 字段不执行 |

#### 表达式求值上下文

`when` 表达式可用的字段：
- `entity_data`: 实体的原始属性（如 `status`, `registered_capital.value`）
- `computed_metrics`: 已计算的指标（如 `eligible`, `credit_score`）
- 函数: `today()`, `days_between()`

**注意**：`computation.formula` 当前**不执行**，实际计算由 executor.py 中的方法实现。

---

## 9. else 字段约定

### YAML 语法

YAML 中使用 `else`（非 Python 关键字 `else_`）：

```yaml
else:
  action: "reject_eligibility"
  output:
    eligible: false
```

### Pydantic 模型映射

```python
class RuleDefinition(BaseModel):
    else_: dict | None = Field(default=None, alias="else")
```

Loader 正确使用 alias 传值：

```python
RuleDefinition(..., **{"else": r.get("else")})
```

### ⚠️ 序列化陷阱

```python
# 正确：使用 by_alias 确保字段名为 "else"
rule.model_dump(by_alias=True)

# 错误：使用字段名 "else_"，可能导致消费者丢失字段
rule.model_dump()
```

**约定**：项目内统一使用 `model_dump(by_alias=True)` 进行序列化。

---

## 10. data_sources 模块

定义外部数据源映射。

```yaml
data_sources:
  - name: "erp_system"              # 数据源名
    type: "postgresql"               # 类型: postgresql/rest_api/...
    connection: "${ERP_DB_CONNECTION}" # 环境变量引用
    description: "核心ERP系统"        # 可选
    tables:                          # 表映射
      - source_table: "suppliers"
        target_concept: "Supplier"
        mapping:
          supplier_code: "supplier_id"
          company_full_name: "company_name"
    relations:                       # 关系映射
      - source_join:
          table: "invoices"
          field: "supplier_code"
        target:
          concept: "Supplier"
          field: "supplier_id"
        relation: "has_invoice"
```

---

## 11. 未实现功能

以下 schema 功能**已定义但未实现**，使用时不会报错但不会生效：

| 功能 | 位置 | 状态 |
|------|------|------|
| `computation.formula` | `then.computation.formula` | 占位符，不执行 |
| `switch` 语法 | `then.switch` | 已移除（v1.0 spec） |
| `metrics[].formula` | 各指标定义 | 占位符，不执行 |
| Graph 查询 | `metrics[].graph_query` | 未实现 |
| Vector 配置 | `vector_config` | 未实现 |
| LLM 配置 | `llm_config` | 未实现 |

---

## 12. Schema 校验清单

创建 schema 后，使用以下清单检查：

- [ ] `metadata.id` 唯一
- [ ] `types[].name` 无重复
- [ ] `enums[].name` 无重复
- [ ] `concepts[].name` 无重复
- [ ] `concepts[].relations[].target` 引用已定义概念
- [ ] `concepts[].attributes[].type` 为 builtin/type/enum 之一
- [ ] `ruleset[].id` 唯一
- [ ] `ruleset[].then.action` 为内置 action 或已知 action
- [ ] `ruleset[].when` 表达式语法正确
- [ ] `else` 字段使用 YAML `else` 语法（非 `else_`）

---

## 13. 相关文档

- [api-design.md](./api-design.md) - API 接口设计
- [operator.md](./operator.md) - 算子开发指南（过时，待更新）
- [testing.md](./testing.md) - 测试指南
- [ADR-003](../architecture/decisions/003-expression-engine-security.md) - 表达式引擎安全
