# L1: 事实对象 (Factual Objects)

> 客观存在、可观测、可验证的数据定义

## 核心概念

```yaml
fact_objects:
  entities:     # 实体类型
  relations:    # 关系类型
```

## 实体定义

```yaml
fact_objects:
  entities:
    - name: Company                    # 实体类型名
      description: "企业法人"
      attributes:                      # 事实属性
        - name: unified_social_code   # 统一社会信用代码
          type: string
          required: true
          unique: true

        - name: company_name          # 企业名称
          type: string
          required: true

        - name: registered_capital    # 注册资本
          type: Money

        - name: establishment_date    # 成立日期
          type: date

        - name: legal_representative  # 法定代表人
          type: string

        - name: registered_address    # 注册地址
          type: Address

        - name: business_scope        # 经营范围
          type: string
          cardinality: "0..*"         # 多值属性
```

## 关系定义

```yaml
    relations:
      - name: Guarantee               # 担保关系
        from: Company                 # 担保方
        to: Company                   # 被担保方
        attributes:
          - name: guarantee_amount    # 担保金额
            type: Money
            required: true

          - name: guarantee_type      # 担保类型
            type: enum
            enum_type: GuaranteeType  # 抵押/质押/保证

          - name: start_date          # 起始日
            type: date

          - name: end_date            # 到期日
            type: date

      - name: Transaction             # 交易关系
        from: Company                 # 买方
        to: Company                   # 卖方
        attributes:
          - name: transaction_amount  # 交易金额
            type: Money

          - name: transaction_date    # 交易日期
            type: date

          - name: invoice_no          # 发票号
            type: string
```

## 属性类型

### 基础类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `string` | 字符串 | `"ABC Company"` |
| `integer` | 整数 | `1000000` |
| `decimal` | 精确小数 | `1000000.50` |
| `float` | 浮点数 | `3.14159` |
| `boolean` | 布尔 | `true` |
| `date` | 日期 | `2026-04-08` |
| `datetime` | 日期时间 | `2026-04-08T10:00:00Z` |

### 复合类型

```yaml
types:
  - name: Money
    properties:
      value:
        type: decimal
      currency:
        type: string
        default: "CNY"

  - name: Address
    properties:
      province:
        type: string
      city:
        type: string
      district:
        type: string
      detail:
        type: string
```

### 枚举类型

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

## 设计原则

1. **纯粹性** —— 只包含可观测、可验证的事实
2. **稳定性** —— 事实结构变化频率低
3. **无业务含义** —— 不包含"评分"、"等级"等分析结果
4. **完备性** —— 支持业务所需的全部基础数据

## 与 v1 concepts 的区别

| v1 concepts | v2 fact_objects |
|-------------|-----------------|
| category: entity/relation | 明确分为 entities/relations |
| 可含派生属性 | 只含事实属性 |
| dimension_attributes 误用 | 无此概念 |

## 数据同步

```yaml
# data_sources.yaml (独立配置，非 Schema 部分)
data_sync:
  - source: erp_system
    target_fact_object: Company
    mapping:
      supplier_code: unified_social_code
      company_name: company_name
      reg_capital: registered_capital.value
```
