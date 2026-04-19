# KGML v3.0 知识图谱语义声明式格式设计

## Context

需要设计一个新一代知识图谱语义声明式格式，融合 KGPack 和 KGML 的优点，覆盖从数据集到推理分析的完整链路。要求：
- 分层解耦：各子格式可独立使用或组合
- 双格式支持：YAML（人类可读）+ JSON（机器运行）
- 参考标准：JSON-LD、LinkML、OWL、SPG、OpenSPG
- 完整链路：数据集→对象/关系/属性→分类/概念→指标→规则推理（数值/图/LLM）
- Agent友好：结构清晰、工具调用显式声明
- 谓词语义 + 向量检索融合
- 支持动态计算复合指标属性

---

## 设计总览：模块化分层架构

```
KGML Schema (YAML/JSON)
├── metadata        # 元信息
├── types          # 类型系统（标量/向量/复合）
├── enums          # 枚举类型
├── concepts       # 概念/类（本体层）
│   ├── attributes # 属性/槽（可带 vector_config）
│   └── relations  # 关系/谓词（可带 semantic_role）
├── metrics        # 指标（静态/动态/复合）
├── rules          # 规则（符号/图模式/LLM推理）
├── data_sources   # 数据集→图映射
├── vector_config  # 向量索引配置
└── llm_config     # LLM调用配置

KGML Instances (YAML/JSON)
└── instances      # 实例数据（节点+边）
```

---

## 模块 1：metadata - 元信息层

**设计要点：**
- 命名空间、版本、领域、语言
- 依赖的其他 KGML schema
- 建模者、创建时间等审计信息

**YAML 示例：**
```yaml
metadata:
  id: "kg://finance/risk/2.0"
  name: "金融风控知识图谱"
  description: "覆盖银行账户、交易、欺诈检测等"
  version: "2.0.0"
  schema_version: "3.0"
  domain: "finance/risk-management"
  language: ["zh", "en"]
  license: "Apache-2.0"
  authors:
    - name: "KG Team"
      contact: "kg@example.com"
  dependencies:
    - id: "kg://common/person-ontology/1.0"
      type: "import"
  metadata:
    created: "2026-03-30T00:00:00Z"
    modified: "2026-03-30T00:00:00Z"
```

**JSON 等价：**
```json
{
  "metadata": {
    "id": "kg://finance/risk/2.0",
    "name": "金融风控知识图谱",
    "version": "2.0.0",
    "schema_version": "3.0",
    "domain": "finance/risk-management",
    "language": ["zh", "en"]
  }
}
```

---

## 模块 2：types - 类型系统

**设计要点：**
- 基础类型：string, integer, float, boolean, datetime, uri
- 复合类型：Money, Percentage, Address, JSON, Vector
- 向量配置内嵌：支持向量字段的类型自动开启语义检索
- 单位系统：数值类型可带单位（USD, kg, meter）

**YAML 示例：**
```yaml
types:
  - name: "Money"
    description: "带货币的金额"
    base_type: "object"
    properties:
      value:
        type: "decimal"
        description: "数值"
      currency:
        type: "string"
        default: "USD"
        description: "货币代码"
    vector_config:
      enabled: true
      model: "text-embedding-3-small"
      dimension: 1536
      fields: ["value", "currency"]

  - name: "Percentage"
    description: "百分比 0-100"
    base_type: "float"
    min: 0.0
    max: 100.0
    unit: "%"

  - name: "SemanticText"
    description: "用于语义检索的文本"
    base_type: "string"
    vector_config:
      enabled: true
      model: "text-embedding-3-small"
      dimension: 1536
      preprocessing: "normalize_text"
```

---

## 模块 3：enums - 枚举类型

**设计要点：**
- 枚举值带语义权重（用于向量检索排序）
- 支持层级枚举（broader/narrower）
- 每个值可带 color、severity_score 等元数据

**YAML 示例：**
```yaml
enums:
  - name: "RiskLevel"
    description: "风险等级"
    values:
      - id: "LOW"
        label: "低风险"
        weight: 0.1
        severity_score: 1
      - id: "MEDIUM"
        label: "中风险"
        weight: 0.5
        severity_score: 3
      - id: "HIGH"
        label: "高风险"
        weight: 1.0
        severity_score: 5

  - name: "TransactionType"
    description: "交易类型"
    values:
      - id: "TRANSFER"
        label: "转账"
        weight: 0.8
      - id: "PAYMENT"
        label: "支付"
        weight: 0.6
```

---

## 模块 4：concepts - 概念/本体层（核心）

**设计要点：**
- 类似 OWL Class / LinkML Class / SPG EntityType
- attributes：数据属性（datatype property）
- relations：对象属性（object property）
- 每个属性/关系可带 vector_config 开启向量语义
- relations 携带 semantic_role 支持图推理
- **属性维度上下文**：同一实体类型在不同业务维度下有不同派生属性
- **派生属性（Derived Attributes）**：动态计算的复合指标挂载在属性上

### 4.1 属性类型详解

```yaml
attribute_types:
  # 普通属性
  basic:
    description: "静态属性，存储直接录入的数据"
    stored: true
    indexed: true

  # 派生属性
  derived:
    description: "动态计算属性，由其他属性或外部数据计算得出"
    stored: false  # 可选择是否缓存
    computed_on: ["read", "write", "scheduled"]
    recalculate_triggers:
      - "source_property_changed"
      - "scheduled"
      - "manual"

  # 聚合属性
  aggregated:
    description: "聚合多个关联实体的属性值"
    aggregation_type: ["sum", "avg", "min", "max", "count", "collect"]

  # 虚拟属性
  virtual:
    description: "不存储，仅在查询时计算"
    computed_lazily: true
```

### 4.2 派生属性计算配置详解

```yaml
concepts:
  - name: "Account"
    description: "银行账户"
    category: "entity"
    attributes:
      - name: "account_number"
        type: "string"
        required: true
        unique: true

      - name: "balance"
        type: "Money"
        required: true
        vector_config:
          enabled: true
          weight: 1.0

      # === 派生属性（多策略计算）===
      - name: "account_risk_score"
        type: "integer"
        description: "账户风险评分（动态计算）"
        derived: true

        # 触发条件
        compute_on:
          - type: "change"
            fields: ["balance", "account_status"]
            debounce_seconds: 60
          - type: "scheduled"
            cron: "0 */6 * * *"  # 每6小时
          - type: "manual"

        # 计算策略（多策略回退）
        calculation:
          type: "multi_strategy"
          fallback_mode: "sequential"  # sequential | parallel | weighted

          strategies:
            # 策略1：本地表达式（最快）
            - priority: 1
              type: "formula"
              engine: "local"
              expression: |
                if balance.value > 1000000:
                    return 90
                elif balance.value > 100000:
                    return 60
                else: return 30
              # 依赖属性
              dependencies:
                - "balance.value"

            # 策略2：图查询（引入关联数据）
            - priority: 2
              type: "graph"
              language: "cypher"
              timeout_ms: 5000
              query: |
                MATCH (a:Account {account_number: $account_number})
                OPTIONAL MATCH (p:Customer)-[:holds]->(a)
                OPTIONAL MATCH (a)<-[:transacts]-(t:Transaction {status: 'COMPLETED'})
                WHERE t.date >= date_sub(today(), 30)
                RETURN COALESCE(p.credit_score, 650) * 0.4 +
                       (CASE WHEN COUNT(t) > 100 THEN 30 ELSE COUNT(t) * 0.3 END) +
                       (CASE WHEN a.balance.value > 1000000 THEN 20 ELSE 0 END) AS risk_score
              params:
                - name: "account_number"
                  source: "Account.account_number"
                  binding: "context"  # context | direct
              dependencies:
                - "Account.balance"
                - "Account.holds.Customer.credit_score"
              confidence: 0.85

            # 策略3：外部服务调用
            - priority: 3
              type: "remote"
              service: "risk-scoring-service"
              endpoint: "/api/v1/accounts/{{account_number}}/risk-score"
              method: "GET"
              timeout_ms: 10000
              retry:
                max_attempts: 2
                backoff_ms: 1000
              cache:
                enabled: true
                ttl_seconds: 3600
              dependencies:
                - "Account.account_number"
                - "Account.balance"
              confidence: 0.9

            # 策略4：LLM推理（复杂上下文）
            - priority: 4
              type: "llm"
              model: "gpt-4o"
              prompt: |
                分析账户风险评分(0-100)：
                账户信息：
                - 账户号: {account_number}
                - 余额: {balance}
                - 账户年龄: {account_age_months}
                - 持有人信息: {customer_info}

                交易历史摘要：
                {transaction_summary}

                最近告警：
                {recent_alerts}

                请给出综合风险评分和关键风险因素。
              variables:
                - name: "account_number"
                  source: "Account.account_number"
                - name: "balance"
                  source: "Account.balance"
                - name: "account_age_months"
                  source: "Account.account_age_months"
                - name: "customer_info"
                  source: "Account.holds.Customer"
                  format: "{name}, 信用分: {credit_score}"
                - name: "transaction_summary"
                  source: "Account.transactions"
                  format: "近30天交易{count}笔, 总金额{sum}"
                  limit: 5
                - name: "recent_alerts"
                  source: "Account.alerts"
                  filter: "date > date_sub(today(), 30)"
                  format: "{severity}: {message}"
              validation:
                min_value: 0
                max_value: 100
                data_type: "integer"
              confidence: 0.8

        # 结果缓存
        cache:
          enabled: true
          ttl_seconds: 3600
          invalidate_on:
            - "balance_changed"
            - "new_transaction"
            - "alert_triggered"

        # 错误处理
        error_handling:
          on_calculation_error: "log_and_return_null"
          on_timeout: "use_cached_or_null"
          fallback_value: 50  # 默认中等风险

        # 向量配置
        vector_config:
          enabled: true
          weight: 0.7
          update_on_recalculate: true

      # === 聚合属性 ===
      - name: "total_transaction_amount_30d"
        type: "Money"
        description: "30天交易总额"
        derived: true
        aggregation:
          type: "sum"
          source_relation: "transacts"
          source_field: "amount.value"
          time_window:
            days: 30
            field: "date"
        vector_config:
          enabled: true
          weight: 0.6

      - name: "avg_monthly_balance"
        type: "Money"
        description: "月均余额"
        derived: true
        aggregation:
          type: "avg"
          source_relation: "transactions"
          source_field: "balance.value"
          time_window:
            months: 3

      - name: "transaction_count"
        type: "integer"
        description: "交易笔数"
        derived: true
        aggregation:
          type: "count"
          source_relation: "transacts"

      # === 条件属性（根据条件返回不同字段）===
      - name: "effective_interest_rate"
        type: "Percentage"
        description: "实际有效利率（考虑优惠）"
        derived: true
        calculation:
          type: "formula"
          expression: |
            base_rate = self.nominal_rate
            if self.has_discount == true:
                return base_rate * (1 - self.discount_rate / 100)
            else:
                return base_rate

      # === 跨维度属性 ===
      - name: "loan_approval_score"
        type: "integer"
        description: "贷款审批评分（仅在贷款审批维度下计算）"
        derived: true
        scope:
          # 该属性仅在特定维度下激活
          dimensions:
            - "loan_approval"
        calculation:
          type: "formula"
          expression: |
            credit_component = min(credit_score / 850 * 40, 40)
            income_component = min(annual_income.value / 1000000 * 30, 30)
            asset_component = min(total_assets.value / 5000000 * 20, 20)
            existing_debt_component = min(existing_debt.value / annual_income.value * 10, 10)
            return credit_component + income_component + asset_component - existing_debt_component

      - name: "aml_risk_score"
        type: "float"
        description: "反洗钱风险评分（仅在AML监控维度下计算）"
        derived: true
        scope:
          dimensions:
            - "aml_monitoring"
        calculation:
          type: "multi_strategy"
          strategies:
            - priority: 1
              type: "graph"
              query: |
                MATCH (c:Customer)-[:transacts]->(a:Account)-[:transacts]->(t:Transaction)
                WHERE t.date >= date_sub(today(), 180)
                WITH c, COUNT(DISTINCT t) AS txn_count,
                     SUM(t.amount.value) AS total_amount,
                     MAX(t.amount.value) AS max_single
                RETURN txn_count * 0.2 + total_amount / 100000 * 0.4 +
                       max_single / 50000 * 0.4 AS aml_score
```

### 4.3 实体维度上下文示例

```yaml
concepts:
  - name: "Customer"
    description: "银行客户"
    category: "entity"

    # 维度特定的属性集合
    dimension_attributes:
      # 贷款审批维度
      loan_approval:
        - name: "debt_to_income_ratio"
          type: "Percentage"
          derived: true
          calculation:
            type: "graph"
            query: |
              MATCH (c:Customer {id: $customer_id})-[:has_loan]->(l:Loan)
              RETURN SUM(l.monthly_payment.value) * 12 / c.annual_income.value * 100 AS dti

        - name: "existing_loan_count"
          type: "integer"
          derived: true
          calculation:
            type: "graph"
            query: "MATCH (c:Customer)-[:has_loan]->(l:Loan) WHERE l.status != 'PAID_OFF' RETURN COUNT(l)"

        - name: "loan_approval_eligibility"
          type: "string"
          derived: true
          calculation:
            type: "formula"
            expression: |
              if debt_to_income_ratio > 50: return "INELIGIBLE"
              elif existing_loan_count >= 5: return "INELIGIBLE"
              elif credit_score < 600: return "INELIGIBLE"
              elif credit_score >= 750: return "FULL_ELIGIBILITY"
              else: return "CONDITIONAL_ELIGIBILITY"

      # AML监控维度
      aml_monitoring:
        - name: "transaction_velocity_1h"
          type: "integer"
          derived: true
          calculation:
            type: "stream"
            query: "..."

        - name: "cross_border_ratio"
          type: "Percentage"
          derived: true
          calculation:
            type: "graph"
            query: |
              MATCH (c:Customer)-[:transacts]->(a:Account)-[:transacts]->(t:Transaction)
              WHERE t.date >= date_sub(today(), 30)
              WITH c, t,
                   CASE WHEN t.is_cross_border THEN t.amount ELSE 0 END AS cb_amount,
                   CASE WHEN NOT t.is_cross_border THEN t.amount ELSE 0 END AS domestic_amount
              RETURN SUM(cb_amount) / (SUM(cb_amount) + SUM(domestic_amount)) * 100

        - name: "high_risk_country_exposure"
          type: "integer"
          derived: true
          calculation:
            type: "graph"
            query: "..."

      # 客户价值维度
      customer_valuation:
        - name: "lifetime_value"
          type: "Money"
          derived: true
          calculation:
            type: "llm"
            model: "gpt-4o"
            prompt: |
              估算客户 {name} 的终身价值：
              - 年龄: {age}
              - 年收入: {annual_income}
              - 持有产品: {products}
              - 信用等级: {credit_level}
              输出JSON：{"ltv": number, "confidence": float}

        - name: "product_penetration"
          type: "Percentage"
          description: "产品渗透率"
          derived: true
          calculation:
            type: "formula"
            expression: "count(current_products) / max_products * 100"

        - name: "relationship_tenure_years"
          type: "integer"
          derived: true
          calculation:
            type: "formula"
            expression: "days_between(first_account_open_date, today()) / 365"

    # 默认/通用属性
    attributes:
      - name: "customer_id"
        type: "string"
        required: true
        unique: true

      - name: "name"
        type: "string"
        required: true
        vector_config:
          enabled: true
          weight: 1.0
                MATCH (p:Person)-[:owns]->(a:Account {account_number: $account_number})
                RETURN AVG(p.credit_score) AS avg_score
            - priority: 3
              type: "llm"
              model: "gpt-4o"
              prompt: |
                请分析账户风险评分(0-100)：
                - 余额：{balance}
                - 持有人信用分均值：{avg_score}
                只输出：{"risk_score": number}

    relations:
      - name: "belongs_to"
        target: "Person"
        inverse: "owns"

  - name: "ChronicDisease"
    description: "慢性疾病（概念，抽象）"
    category: "concept"
    parent: "Disease"  # 概念继承
    skos_broader: "Disease"
    skos_narrower: []

  - name: "Disease"
    description: "疾病实体"
    category: "entity"
    attributes:
      - name: "icd10_code"
        type: "string"
        description: "ICD-10编码"
    relations:
      - name: "causes"
        target: "Disease"
        description: "并发症"
```

**JSON 等价结构：**
```json
{
  "concepts": [
    {
      "name": "Person",
      "description": "个人客户",
      "category": "entity",
      "attributes": [
        {
          "name": "id",
          "type": "string",
          "required": true,
          "unique": true
        },
        {
          "name": "name",
          "type": "string",
          "vector_config": {
            "enabled": true,
            "weight": 1.0
          }
        }
      ],
      "relations": [
        {
          "name": "owns",
          "target": "Account",
          "cardinality": "1..*",
          "inverse": "belongs_to"
        }
      ]
    }
  ]
}
```

---

## 模块 5：metrics - 指标层

**设计要点：**
- 指标分为：静态（常量）、动态（计算）、复合（多来源聚合）
- 每个指标支持多种计算策略：sql/graph/formula/llm/rest_api/stream
- 指标可挂载在概念上（scope），也可独立存在
- **数据取数细节**：支持多种数据源接入方式和参数映射

### 5.1 数据取数类型详解

```yaml
data_fetch_types:
  # 1. SQL查询
  sql:
    description: "从关系型数据库取数"
    capabilities:
      - single_query: "单表/单查询"
      - multi_query: "多查询联合"
      - window_function: "窗口函数"
      - cte: "公用表表达式"
      - subquery: "子查询"

  # 2. 图查询
  graph:
    description: "从图数据库取数"
    languages:
      - "cypher"      # Neo4j
      - "gremlin"     # Apache TinkerPop
      - "ngql"        # NebulaGraph
      - "gsql"        # TigerGraph
      - "opencypher"  # 开放Cypher

  # 3. REST API
  rest_api:
    description: "从外部HTTP API取数"
    capabilities:
      - get: "GET请求"
      - post: "POST请求（带body）"
      - pagination: "分页处理"
      - rate_limit: "限流处理"
      - retry: "重试策略"

  # 4. 消息流
  stream:
    description: "从消息队列/流处理系统取数"
    systems:
      - "kafka"
      - "pulsar"
      - "kinesis"

  # 5. 文件
  file:
    description: "从文件取数"
    formats:
      - "csv"
      - "parquet"
      - "json"
      - "xml"
```

### 5.2 SQL取数详细配置

```yaml
metrics:
  - name: "capital_adequacy_ratio"
    description: "资本充足率"
    type: "Percentage"
    scope: "Bank"

    calculation:
      # 主计算方式
      type: "sql"
      engine: "banking_core_db"
      priority: 1

      # SQL查询定义
      query: |
        WITH bank_capital AS (
          SELECT
            b.bank_id,
            b.tier1_capital + b.tier2_capital AS total_capital
          FROM banks b
          WHERE b.bank_id = :bank_id
        ),
        risk_assets AS (
          SELECT
            a.bank_id,
            SUM(
              a.balance * CASE a.asset_type
                WHEN 'LOAN' THEN 1.0
                WHEN 'MORTGAGE' THEN 0.5
                WHEN 'CONSUMER' THEN 0.75
                ELSE 0.0
              END
            ) AS risk_weighted_assets
          FROM accounts a
          WHERE a.bank_id = :bank_id
          GROUP BY a.bank_id
        )
        SELECT
          bc.total_capital / ra.risk_weighted_assets * 100 AS capital_adequacy_ratio,
          bc.total_capital,
          ra.risk_weighted_assets
        FROM bank_capital bc
        JOIN risk_assets ra ON bc.bank_id = ra.bank_id

      # 参数映射
      params:
        - name: "bank_id"
          type: "string"
          source: "Bank.bank_id"
          required: true

      # 结果映射
      result_mapping:
        capital_adequacy_ratio: "value"
        total_capital: "metadata.capital"
        risk_weighted_assets: "metadata.rwa"

      # 缓存配置
      cache:
        enabled: true
        ttl: 3600  # 秒
        strategy: "refresh_before_expiry"

      # 错误处理
      error_handling:
        on_zero_division: "return_null"
        on_null_result: "return_default"
        default_value: 0.0

  - name: "peer_bank_average"
    description: "同业平均指标（用于对比）"
    type: "Percentage"
    scope: "Bank"

    calculation:
      type: "sql"
      engine: "banking_core_db"
      query: |
        SELECT AVG(capital_adequacy_ratio) AS peer_avg
        FROM bank_metrics
        WHERE bank_id != :bank_id
          AND report_date = (
            SELECT MAX(report_date)
            FROM bank_metrics
            WHERE bank_id = :bank_id
          )
          AND asset_size BETWEEN :asset_size * 0.5 AND :asset_size * 2.0
      params:
        - name: "bank_id"
          source: "Bank.bank_id"
        - name: "asset_size"
          source: "Bank.total_assets.value"
      result_mapping:
        peer_avg: "value"
```

### 5.3 图查询详细配置

```yaml
metrics:
  - name: "customer_network_score"
    description: "客户关联网络评分"
    type: "float"
    scope: "Customer"

    calculation:
      type: "graph"
      language: "cypher"
      priority: 1

      query: |
        // 计算客户的网络中心性指标
        MATCH (c:Customer {customer_id: $customer_id})

        // 1. 直接关联账户数
        WITH c, SIZE((c)-[:holds]->(:Account)) AS direct_accounts

        // 2. 关联账户的总交易对手数
        OPTIONAL MATCH (c)-[:holds]->(a:Account)-[:transacts]->(t:Transaction)-[:involves_account]->(other:Account)
        WHERE other <> a
        WITH c, direct_accounts, COUNT(DISTINCT other) AS counterparty_count

        // 3. 二度关联客户数
        OPTIONAL MATCH (c)-[:transacts]->(:Account)<-[:transacts]-(c2:Customer)
        WITH c, direct_accounts, counterparty_count, COUNT(DISTINCT c2) AS second_degree_customers

        // 4. 计算网络得分
        RETURN (
          direct_accounts * 1.0 +
          counterparty_count * 0.5 +
          second_degree_customers * 0.3
        ) AS network_score,
        direct_accounts,
        counterparty_count,
        second_degree_customers

      params:
        - name: "customer_id"
          source: "Customer.customer_id"

      result_mapping:
        network_score: "value"
        direct_accounts: "metadata.direct_accounts"
        counterparty_count: "metadata.counterparties"
        second_degree_customers: "metadata.second_degree"

      # 图查询特有配置
      graph_config:
        timeout: 30000  # ms
        max_hops: 3     # 最大跳数
        direction: "both"  # 入出方向

  - name: "loan_portfolio_concentration"
    description: "贷款集中度（最大单一客户占比）"
    type: "Percentage"
    scope: "Branch"

    calculation:
      type: "graph"
      language: "cypher"
      query: |
        MATCH (b:Branch {branch_id: $branch_id})<-[:granted_by]-(l:Loan)
        WITH b, SUM(l.remaining_balance.value) AS total_branch_loans

        MATCH (b)<-[:granted_by]-(largest:Loan)
        WITH b, total_branch_loans, largest,
             MAX(largest.remaining_balance.value) AS max_single_loan

        RETURN max_single_loan / total_branch_loans * 100 AS concentration_ratio,
               total_branch_loans,
               max_single_loan.loan_id AS largest_loan_id,
               max_single_loan.granted_to.name AS largest_borrower
```

### 5.4 REST API取数详细配置

```yaml
metrics:
  - name: "central_bank_rate"
    description: "央行基准利率"
    type: "Percentage"
    scope: "Bank"

    calculation:
      type: "rest_api"
      priority: 1

      # API配置
      api:
        method: "GET"
        url: "https://api.centralbank.gov.cn/v1/interest_rates/benchmark"
        auth:
          type: "bearer_token"
          token: "${CENTRAL_BANK_API_TOKEN}"

        # 请求头
        headers:
          Accept: "application/json"
          "X-API-Key": "${API_KEY}"

        # URL参数
        params:
          effective_date: "latest"
          category: "lending_rate"

      # 响应映射
      response_mapping:
        # JSONPath表达式
        value: "$.data[0].rate_value"
        description: "$.data[0].description"
        effective_date: "$.data[0].effective_date"

      # 分页配置（如果需要）
      pagination:
        enabled: false

      # 限流重试配置
      rate_limit:
        max_requests_per_minute: 60
        retry:
          enabled: true
          max_attempts: 3
          backoff: "exponential"
          initial_delay_ms: 1000

      # 缓存
      cache:
        enabled: true
        ttl: 86400  # 一天

      error_handling:
        on_timeout: "use_cached"
        on_403: "return_null"
        default_value: 0.0

  - name: "external_credit_rating"
    description: "外部信用评级（从评级机构API获取）"
    type: "RatingGrade"
    scope: "Bank"

    calculation:
      type: "rest_api"
      api:
        method: "POST"
        url: "https://api.rating-agency.com/v2/ratings/query"
        auth:
          type: "api_key"
          key: "${RATING_AGENCY_API_KEY}"
        headers:
          Content-Type: "application/json"
        body: |
          {
            "entity_id": "{{bank.bank_id}}",
            "entity_type": "BANK",
            "rating_type": "LTFC"  # 长期发行人信用评级
          }
      response_mapping:
        rating: "$.ratings[0].grade"
        outlook: "$.ratings[0].outlook"
        rating_date: "$.ratings[0].rating_date"
        next_review_date: "$.ratings[0].next_review_date"
```

### 5.5 多策略回退与聚合

```yaml
metrics:
  - name: "customer_lifetime_value"
    description: "客户终身价值"
    type: "Money"
    scope: "Customer"

    calculation:
      # 多策略聚合模式
      aggregation_mode: "fallback"  # fallback | parallel | weighted

      # 策略列表（按优先级）
      strategies:
        # 策略1：图计算（首选）
        - priority: 1
          type: "graph"
          language: "cypher"
          query: |
            MATCH (c:Customer {customer_id: $customer_id})
            OPTIONAL MATCH (c)-[:holds]->(a:Account)
            OPTIONAL MATCH (c)-[:has_loan]->(l:Loan) WHERE l.loan_status = 'NORMAL'
            RETURN
              SUM(a.balance.value) AS current_assets +
              SUM(l.remaining_balance.value) * 0.3 AS potential_liability +
              COUNT(DISTINCT a) * 5000 AS service_value AS clv
          params:
            - name: "customer_id"
              source: "Customer.customer_id"
          confidence: 0.9

        # 策略2：SQL计算（备选）
        - priority: 2
          type: "sql"
          engine: "banking_analytics_db"
          query: |
            SELECT
              COALESCE(SUM(current_assets), 0) +
              COALESCE(SUM(potential_liability), 0) * 0.3 +
              COALESCE(account_count, 0) * 5000 AS clv
            FROM customer_ltv_view
            WHERE customer_id = :customer_id
          params:
            - name: "customer_id"
              source: "Customer.customer_id"
          confidence: 0.85

        # 策略3：LLM估算（最后备选）
        - priority: 3
          type: "llm"
          model: "gpt-4o"
          prompt: |
            估算客户 {customer_name} 的终身价值：
            - 年龄: {age}
            - 职业: {occupation}
            - 年收入: {annual_income}
            - 当前资产: {current_assets}
            - 持有产品数: {product_count}
            - 客户等级: {customer_tier}
            基于行业标准估算该客户的5年终身价值。
          variables:
            - name: "customer_name"
              source: "Customer.name"
            - name: "age"
              source: "Customer.age"
            - name: "annual_income"
              source: "Customer.annual_income.value"
            - name: "current_assets"
              source: "derived.total_assets"
            - name: "product_count"
              source: "derived.product_count"
            - name: "customer_tier"
              source: "Customer.tier"
          confidence: 0.7
          # LLM返回结果校验
          validation:
            min_value: 0
            max_value: 100000000
            data_type: "Money"

      # 置信度加权
      confidence_weighting:
        enabled: true
        formula: "sum(value * confidence) / sum(confidence)"

      # 结果后处理
      post_processing:
        - type: "round"
          decimals: 2
        - type: "currency_convert"
          target_currency: "CNY"
          source_field: "value"
```

### 5.6 流式/实时指标

```yaml
metrics:
  - name: "realtime_account_balance"
    description: "实时账户余额"
    type: "Money"
    scope: "Account"
    realtime: true

    calculation:
      type: "stream"
      source: "kafka"

      # Kafka配置
      kafka:
        bootstrap_servers: "${KAFKA_BROKERS}"
        topic: "account.transactions"
        consumer_group: "metrics-realtime"
        offset: "latest"

      # 流处理配置
      processing:
        type: "stateful"
        window:
          type: "tumbling"
          size_seconds: 60

        # 状态聚合
        aggregation: |
          SELECT
            account_number,
            SUM(CAST(amount AS DECIMAL)) AS balance_change,
            COUNT(*) AS txn_count
          FROM transaction_events
          WHERE account_number IN (:account_numbers)
          GROUP BY account_number

      # 初始值来源
      initial_value:
        type: "graph"
        query: "MATCH (a:Account {account_number: $account_number}) RETURN a.balance.value AS balance"

  - name: "transaction_velocity"
    description: "交易速率（每分钟交易数）"
    type: "float"
    scope: "Account"
    realtime: true

    calculation:
      type: "stream"
      source: "kafka"
      kafka:
        topic: "account.transactions"
      processing:
        type: "streaming"
        window:
          type: "sliding"
          size_seconds: 60
          slide_seconds: 10
        aggregation: |
          SELECT
            account_number,
            COUNT(*) / 60.0 AS txn_per_second
          FROM transaction_events
          GROUP BY account_number
      alert:
        threshold: 10  # 每秒超过10笔告警
        severity: "HIGH"
```

### 5.7 完整指标定义示例

```yaml
metrics:
  - name: "total_assets"
    description: "个人总资产"
    type: "Money"
    scope: "Person"

    calculation:
      priority: 1
      methods:
        - type: "sql"
          engine: "banking_db"
          query: |
            SELECT SUM(balance_amount) FROM accounts
            WHERE owner_id = :person_id
          params:
            - name: "person_id"
              source: "Person.id"

        - type: "graph"
          language: "cypher"
          query: |
            MATCH (p:Person {id: $person_id})-[:owns]->(a:Account)
            RETURN SUM(a.balance.value) AS total

        - type: "llm"
          model: "gpt-4o"
          prompt: |
            分析客户 {person_name} 的总资产结构：
            {accounts_detail}
            输出：{"total": number, "analysis": string}
          variables: ["person_name", "accounts_detail"]

  - name: "avg_transaction_amount"
    description: "平均交易金额"
    type: "Money"
    scope: "Account"
    calculation:
      type: "graph"
      language: "cypher"
      query: |
        MATCH (a:Account {account_number: $account_number})-[:transacts]->(t:Transaction)
        RETURN AVG(t.amount.value) AS avg_amount

  - name: "disease_incidence_rate"
    description: "疾病发病率"
    type: "Percentage"
    scope: "Disease"
    calculation:
      type: "sql"
      query: |
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM patients) AS rate
        FROM diagnoses WHERE disease_id = :disease_id
```

---

## 模块 6：rules - 规则推理层

**设计要点：**
- 规则类型：constraint（约束）/ inference（推理）/ alert（告警）/ action（动作）
- 条件支持：graph_pattern / expression / llm
- 动作支持：tool_call / log / alert / update
- 规则可链式组合（rule chaining）
- **规则维度上下文**：同一对象类型在不同上下文维度下适用不同规则

### 6.1 表达式引擎详细设计

#### 支持的运算符

```yaml
# 算术运算符
arithmetic_operators:
  - "+"   # 加法
  - "-"   # 减法
  - "*"   # 乘法
  - "/"   # 除法
  - "%"   # 取模
  - "**"  # 幂运算
  - "//"  # 整除

# 比较运算符
comparison_operators:
  - "=="  # 等于
  - "!="  # 不等于
  - ">"   # 大于
  - "<"   # 小于
  - ">="  # 大于等于
  - "<="  # 小于等于
  - "IN"  # 属于集合
  - "NOT IN"  # 不属于集合
  - "BETWEEN" # 范围
  - "LIKE"    # 模糊匹配
  - "ILIKE"   # 大小写无关匹配

# 逻辑运算符
logical_operators:
  - "AND"  # 逻辑与
  - "OR"   # 逻辑或
  - "NOT"  # 逻辑非
  - "&&"   # 短路与
  - "||"   # 短路或

# 字符串运算符
string_operators:
  - "CONTAINS"      # 包含子串
  - "STARTS WITH"   # 开头匹配
  - "ENDS WITH"     # 结尾匹配
  - "REGEX"         # 正则表达式
  - "LENGTH"        # 字符串长度

# 集合运算符
collection_operators:
  - "ANY"    # 集合中任意满足
  - "ALL"    # 集合中全部满足
  - "NONE"   # 集合中无满足
  - "SIZE"   # 集合大小
  - "FIRST"  # 集合第一个元素
  - "LAST"   # 集合最后一个元素

# 时间/日期运算符
temporal_operators:
  - "days_between(a, b)"    # 两日期相差天数
  - "months_between(a, b)"  # 两日期相差月数
  - "add_days(d, n)"       # 日期加减天数
  - "today()"              # 当前日期
  - "now()"                # 当前时间戳
  - "date_format(d, fmt)"  # 日期格式化
```

#### 内置函数库

```yaml
builtin_functions:
  # 数学函数
  math:
    - "abs(x)"              # 绝对值
    - "round(x, n)"         # 四舍五入
    - "floor(x)"            # 向下取整
    - "ceil(x)"             # 向上取整
    - "sqrt(x)"             # 平方根
    - "pow(x, n)"           # x的n次方
    - "log(x, base)"        # 对数
    - "min(a, b, ...)"      # 最小值
    - "max(a, b, ...)"      # 最大值
    - "sum(a, b, ...)"      # 求和
    - "avg(a, b, ...)"      # 平均值
    - "clamp(x, min, max)"  # 限制在范围内

  # 字符串函数
  string:
    - "upper(s)"             # 转大写
    - "lower(s)"             # 转小写
    - "trim(s)"              # 去空格
    - "concat(s1, s2, ...)"  # 字符串拼接
    - "split(s, delim)"      # 分割字符串
    - "replace(s, old, new)" # 替换
    - "substring(s, start, len)" # 子串

  # 聚合函数
  aggregation:
    - "count(collection)"          # 计數
    - "sum(collection)"            # 求和
    - "avg(collection)"            # 平均
    - "min(collection)"            # 最小
    - "max(collection)"            # 最大
    - "collect(collection)"         # 收集为数组
    - "distinct(collection)"        # 去重

  # 条件函数
  conditional:
    - "if(condition, then, else)"  # 条件表达式
    - "coalesce(v1, v2, ...)"     # 返回第一个非null
    - "nullif(a, b)"              # 相等返回null
    - "case(value, when1, then1, ...)" # 多条件

  # 图函数
  graph:
    - "degree(node)"               # 节点度数
    - "in_degree(node)"           # 入度
    - "out_degree(node)"          # 出度
    - "neighbors(node)"           # 邻居节点
    - "shortest_path(start, end)" # 最短路径
    - "has_path(start, end)"      # 是否连通
    - "related_to(node, type)"     # 按类型找关联

  # 类型转换
  casting:
    - "to_string(x)"              # 转字符串
    - "to_int(x)"                 # 转整数
    - "to_float(x)"               # 转浮点
    - "to_bool(x)"                # 转布尔
    - "to_date(s, fmt)"           # 转日期
    - "to_list(x)"                # 转列表
```

#### 表达式语法示例

```yaml
expressions:
  # 简单比较
  - expression: "age >= 18 AND age <= 65"
  - expression: "credit_score IN [650, 700, 750]"
  - expression: "name LIKE '张%'"

  # 数值计算
  - expression: "balance.value * 0.5 > 100000"
  - expression: "sqrt(power(x, 2) + power(y, 2)) < 1000"

  # 字符串操作
  - expression: "email CONTAINS '@company.com'"
  - expression: "phone REGEX '^1[3-9]\\d{9}$'"

  # 时间计算
  - expression: "days_between(today(), open_date) > 180"
  - expression: "add_days(today(), -30) > last_transaction_date"

  # 集合操作
  - expression: "SIZE(accounts) >= 2"
  - expression: "ALL(loans, loan.status == 'NORMAL')"
  - expression: "ANY(transactions, amount > 1000000)"

  # 嵌套属性访问
  - expression: "branch.bank.registered_capital.value > 10000000"
  - expression: "customer.accounts[0].balance.value > 10000"

  # 复杂条件组合
  - expression: |
      credit_score >= 650
      AND debt_to_income_ratio < 40
      AND count(overdue_loans) == 0
      OR (credit_score >= 750 AND verified == true)

  # 调用内置函数
  - expression: "clamp(score, 0, 100) > 80"
  - expression: "if(risk_level == 'HIGH', score * 1.5, score) > threshold"
```

### 6.2 规则维度上下文（Rule Dimension Context）

**核心概念**：同一个对象类型（如Customer）在不同业务维度下应适用不同规则。

```yaml
rule_dimensions:
  # 维度定义：定义规则适用的业务维度
  dimensions:
    - name: "loan_approval"
      description: "贷款审批维度"
      applicable_entities: ["Customer", "Loan", "Account"]

    - name: "account_management"
      description: "账户管理维度"
      applicable_entities: ["Customer", "Account"]

    - name: "aml_monitoring"
      description: "反洗钱监控维度"
      applicable_entities: ["Customer", "Account", "Transaction"]

    - name: "risk_management"
      description: "风险管理维度"
      applicable_entities: ["Bank", "Branch", "Customer", "Loan"]

  # 维度上下文：在特定维度下激活的规则
  contexts:
    - dimension: "loan_approval"
      context_id: "personal_loan"
      description: "个人消费贷审批"
      triggers:
        - event: "loan_application_submitted"
          entity: "Loan"

      # 该维度下Customer适用的规则
      entity_rules:
        Customer:
          - rule_ref: "credit_score_threshold"
            params:
              min_score: 600
          - rule_ref: "debt_to_income_check"
            params:
              max_dti: 50
          - rule_ref: "employment_stability_check"
          - rule_ref: "cross_border_restriction"  # 跨境人员限制

    - dimension: "aml_monitoring"
      context_id: "transaction_surveillance"
      description: "交易监控"
      triggers:
        - event: "large_transaction_detected"
          entity: "Transaction"
        - event: "newBeneficiaryAdded"
          entity: "Account"

      entity_rules:
        Customer:
          - rule_ref: "sanctions_list_screen"
          - rule_ref: "structuring_detection"
          - rule_ref: "high_risk_country_check"
          - rule_ref: "frequency_anomaly_detection"

        Account:
          - rule_ref: "rapid_movement_detection"
          - rule_ref: "round_amount_detection"
```

#### 规则作用域（Rule Scope）

```yaml
rules:
  - name: "credit_score_threshold"
    description: "信用评分阈值检查"
    type: "constraint"
    scope:
      # 规则应用的维度上下文
      dimensions:
        - "loan_approval:personal_loan"
        - "loan_approval:business_loan"
        - "credit_card_application"
      # 规则应用的实体类型
      entity_types:
        - "Customer"
      # 规则应用的条件前置
      preconditions:
        - expression: "customer.age >= 18"
        - expression: "customer.verified == true"

    condition:
      type: "expression"
      expression: "credit_score >= min_score"
      vars:
        min_score:
          type: "param"  # 从维度上下文参数获取
          source: "params.min_score"

    actions:
      - type: "{{#if passes}}proceed{{else}}reject{{/if}}"
        message: "客户 {{customer.name}} 信用评分不足"

  - name: "structuring_detection"
    description: "拆分交易检测（化整为零）"
    type: "inference"
    scope:
      dimensions:
        - "aml_monitoring:transaction_surveillance"
      entity_types:
        - "Customer"
        - "Transaction"
    condition:
      type: "graph_pattern"
      language: "cypher"
      pattern: |
        (c:Customer)-[:transacts]->(a1:Account)-[:transacts]->(t1:Transaction)
        (c)-[:transacts]->(a2:Account)-[:transacts]->(t2:Transaction)
        WHERE t1 <> t2
        AND abs(t2.date - t1.date) <= 24 * 60 * 60 * 1000
        AND t1.amount.value + t2.amount.value > 100000
        AND t1.amount.value < 10000
        AND t2.amount.value < 10000
    actions:
      - type: "alert"
        severity: "CRITICAL"
        message: "检测到疑似拆分交易"
      - type: "update"
        field: "customer.aml_risk_level"
        value: "HIGH"

  - name: "high_value_customer_priority"
    description: "高价值客户优先处理"
    type: "ranking"
    scope:
      dimensions:
        - "loan_approval"
        - "account_management"
      entity_types:
        - "Customer"
    condition:
      type: "expression"
      expression: |
        total_assets = sum(account.balance.value for account in customer.accounts)
        return total_assets > 1000000 OR avg_balance > 500000
    ranking:
      score: |
        customer.credit_score * 0.3 +
        total_assets / 10000 * 0.5 +
        years_relationship * 0.2
      order: "DESC"
```

#### 规则链与依赖

```yaml
rule_chains:
  - chain_id: "loan_approval_workflow"
    description: "贷款审批工作流规则链"
    execution: "sequential"  # sequential | parallel | cascade

    rules:
      - rule_ref: "basic_eligibility_check"
        on_result:
          pass: "credit_score_check"
          fail: "reject_application"

      - rule_ref: "credit_score_check"
        on_result:
          pass: "debt_analysis"
          fail: "conditional_approval_review"

      - rule_ref: "debt_analysis"
        on_result:
          pass: "collateral_evaluation"
          fail: "debt_restructuring_recommendation"

      - rule_ref: "collateral_evaluation"
        on_result:
          pass: "final_approval"
          fail: "additional_collateral_required"

      - rule_ref: "final_approval"
        actions:
          - type: "approve_loan"
          - type: "generate_offer"
          - type: "notify_customer"

  - chain_id: "aml_investigation_flow"
    description: "AML调查工作流"
    execution: "parallel"  # 并行触发多个规则

    rules:
      - rule_ref: "sanctions_screening"
      - rule_ref: "pep_check"  # 政治敏感人物检查
      - rule_ref: "adverse_media_check"
      - rule_ref: "counterparty_risk_assessment"

    aggregation:
      type: "all_pass"  # all_pass | any_fail | weighted_score
      on_complete:
        - rule_ref: "risk_score_calculation"
        - rule_ref: "decision_tree_routing"
```

### 6.3 完整规则 YAML 示例

```yaml
rules:
  - name: "high_value_minor_alert"
    description: "高余额低龄账户告警"
    type: "alert"
    priority: 1
    scope:
      dimensions: ["account_management", "risk_management"]
      entity_types: ["Account", "Customer"]

    condition:
      type: "and"
      conditions:
        - type: "graph_pattern"
          language: "cypher"
          pattern: |
            (p:Customer)-[:holds]->(a:Account)
            WHERE a.balance.value > 1000000 AND p.age < 30
        - type: "expression"
          expression: "a.account_risk_score > 80"

    actions:
      - type: "alert"
        severity: "HIGH"
        message: "检测到高余额低龄高风险账户"
        channels: ["email", "sms"]

      - type: "tool_call"
        name: "freeze_account"
        parameters:
          account_number: "{{a.account_number}}"

  - name: "drug_allergy_constraint"
    description: "药物过敏约束"
    type: "constraint"
    scope:
      dimensions: ["clinical_decision_support"]
      entity_types: ["Patient", "Drug"]

    condition:
      type: "graph_pattern"
      pattern: |
        (p:Patient)-[:takesMedicine]->(d:Drug)
        WHERE p.allergy CONTAINS d.name
    actions:
      - type: "reject"
        message: "患者对药物存在过敏史"
      - type: "tool_call"
        name: "notify_physician"
        parameters:
          patient_id: "{{p.id}}"
          drug_id: "{{d.id}}"

  - name: "disease_correlation_inference"
    description: "疾病关联推理（LLM增强）"
    type: "inference"
    scope:
      dimensions: ["clinical_research", "diagnostic_support"]
      entity_types: ["Disease", "Symptom"]

    condition:
      type: "graph_pattern"
      pattern: |
        (d1:Disease)-[:hasSymptom]->(s:Symptom)<-[:hasSymptom]-(d2:Disease)
        WHERE d1 != d2
    actions:
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          基于以下疾病共享症状信息，推断可能的关联：
          - 疾病1: {d1_name} (症状: {d1_symptoms})
          - 疾病2: {d2_name} (症状: {d2_symptoms})
          - 共享症状: {shared_symptoms}
          输出：{"correlation": string, "confidence": float, "reasoning": string}
        variables: ["d1_name", "d1_symptoms", "d2_name", "d2_symptoms", "shared_symptoms"]
```

---

## 模块 7：data_sources - 数据源映射层

**设计要点：**
- 描述外部数据集（DB/CSV/API）到图概念的 ETL 映射
- 支持字段映射、关系构造（通过外键）
- 支持增量同步策略

**YAML 示例：**
```yaml
data_sources:
  - name: "banking_db"
    type: "postgresql"
    connection: "${DB_CONNECTION}"  # 环境变量引用
    description: "银行核心系统"

    tables:
      - source_table: "customers"
        target_concept: "Person"
        mapping:
          customer_id: "id"
          full_name: "name"
          age: "age"
          credit_score: "credit_score"
        constraints:
          - type: "unique"
            field: "customer_id"

      - source_table: "accounts"
        target_concept: "Account"
        mapping:
          account_number: "account_number"
          balance: "balance"
          owner_id: "owner_id"  # 外键，用于构造关系

    relations:
      - source_join:
          table: "accounts"
          field: "owner_id"
        target:
          concept: "Person"
          field: "id"
        relation: "owns"

  - name: "transaction_api"
    type: "rest_api"
    endpoint: "https://api.example.com/transactions"
    auth: "bearer_token"
    description: "交易数据API"
```

---

## 模块 8：vector_config - 向量检索配置

**设计要点：**
- 全局向量索引配置
- 支持多模型、多索引类型
- 向量字段自动从 concepts.attributes.vector_config 汇总

**YAML 示例：**
```yaml
vector_config:
  global:
    index_type: "IVF_FLAT"
    distance_metric: "cosine"
    dimension: 1536
    model: "text-embedding-3-small"

  models:
    - name: "text-embedding-3-small"
      provider: "openai"
      dimension: 1536
      cost: "low"

    - name: "bge-m3"
      provider: "local"
      dimension: 1024
      cost: "medium"

  indexes:
    - name: "semantic_search"
      type: "HNSW"
      metric: "cosine"
      fields:
        - "Person.name"
        - "Account.account_number"
      concepts: ["Person", "Account"]

    - name: "risk_analysis"
      type: "IVF_FLAT"
      metric: "l2"
      fields:
        - "Person.credit_score"
        - "Account.account_risk_score"
```

---

## 模块 9：llm_config - 大模型配置层

**设计要点：**
- 全局 LLM 提供者配置
- Prompt 模板库
- 渐进式披露策略（Progressive Disclosure）

**YAML 示例：**
```yaml
llm_config:
  providers:
    - name: "openai"
      type: "openai"
      model: "gpt-4o"
      api_key: "${OPENAI_API_KEY}"
      default: true
      config:
        temperature: 0.3
        max_tokens: 2000

    - name: "claude"
      type: "anthropic"
      model: "claude-3-5-sonnet"
      api_key: "${ANTHROPIC_API_KEY}"
      config:
        temperature: 0.3

  prompt_templates:
    entity_description: |
      请用简洁的{language}描述实体"{name}"（类型:{type}）：
      主要属性：{attributes}
      限制{max_tokens}字。

    relationship_explanation: |
      请解释实体"{e1}"和"{e2}"之间关系"{relation}"的语义含义。

    rule_explanation: |
      请用通俗语言解释以下推理规则：
      {rule_logic}
      输出格式：{"explanation": string, "examples": [string]}

    question_answering: |
      基于以下知识图谱信息回答问题：
      图谱结构：
      {subgraph}
      问题：
      {question}
      请给出简洁准确的回答。

  progressive_disclosure:
    level_1:
      description: "仅实体名和类型"
      template: "实体: {name} (类型: {type})"

    level_2:
      description: "核心属性+直接关系"
      template: |
        实体: {name} ({type})
        核心属性: {core_attributes}
        直接关系: {direct_relations}

    level_3:
      description: "全属性+多跳关系+推理结论"
      template: |
        实体: {name} ({type})
        所有属性: {all_attributes}
        关系视图: {relation_graph}
        推理结果: {inferred_facts}
```

---

## 模块 10：instances - 实例数据层

**设计要点：**
- 与 Schema 解耦，单独文件
- 支持 YAML/JSON 双格式
- 关系通过 target_id 引用

**YAML 示例：**
```yaml
instances:
  - concept: "Person"
    data:
      - id: "person-001"
        name: "张三"
        age: 35
        credit_score: 720
        owns:
          - account_number: "ACC-001"
          - account_number: "ACC-003"

      - id: "person-002"
        name: "李四"
        age: 27
        credit_score: 580
        owns:
          - account_number: "ACC-002"

  - concept: "Account"
    data:
      - account_number: "ACC-001"
        balance:
          value: 500000
          currency: "USD"
        belongs_to: "person-001"

      - account_number: "ACC-002"
        balance:
          value: 1500000
          currency: "USD"
        belongs_to: "person-002"

      - account_number: "ACC-003"
        balance:
          value: 80000
          currency: "USD"
        belongs_to: "person-001"
```

**JSON 等价：**
```json
{
  "instances": {
    "Person": [
      {
        "id": "person-001",
        "name": "张三",
        "age": 35,
        "credit_score": 720,
        "owns": [{"account_number": "ACC-001"}, {"account_number": "ACC-003"}]
      }
    ],
    "Account": [
      {
        "account_number": "ACC-001",
        "balance": {"value": 500000, "currency": "USD"},
        "belongs_to": "person-001"
      }
    ]
  }
}
```

---

## 端到端示例：银行系统评级模型

### 场景设定

构建一个**银行系统评级模型**，覆盖：
- 数据源：银行核心系统（ PostgreSQL）+ 外部评级数据（REST API）
- 实体对象：Bank（银行）、Branch（分行）、Account（账户）、Customer（客户）、Loan（贷款）、Transaction（交易）
- 关系：grants（发放）、holds（持有）、belongs_to（属于）、rates（评级）、transacts（交易）
- 分类：RiskLevel（风险等级）、RatingGrade（评级等级）、AccountType（账户类型）
- 指标：资本充足率、不良贷款率、流动性比率、客户信用评分
- 规则推理：监管合规检查、信用风险预警、评级调整触发
- LLM推理：评级解释生成、异常模式分析

---

### 完整 KGML 文档

#### 1. metadata - 元信息

```yaml
metadata:
  id: "kg://banking/system-rating/2.0"
  name: "银行系统评级知识图谱"
  description: "覆盖银行、分行、客户、账户、贷款、交易及评级关系的完整链路"
  version: "2.0.0"
  schema_version: "3.0"
  domain: "finance/banking/risk-management"
  language: ["zh", "en"]
  license: "Apache-2.0"
  authors:
    - name: "Risk Analytics Team"
      contact: "risk@example.com"
  dependencies:
    - id: "kg://common/financial-ontology/1.0"
      type: "import"
```

#### 2. types - 类型系统

```yaml
types:
  - name: "Money"
    description: "货币金额"
    base_type: "object"
    properties:
      value:
        type: "decimal"
        description: "数值"
      currency:
        type: "string"
        default: "CNY"
    vector_config:
      enabled: true
      model: "text-embedding-3-small"
      dimension: 1536

  - name: "Percentage"
    description: "百分比 0-100"
    base_type: "float"
    min: 0.0
    max: 100.0
    unit: "%"

  - name: "RatingScore"
    description: "评级分数（如AAA=100, D=0）"
    base_type: "integer"
    min: 0
    max: 100

  - name: "DateRange"
    description: "日期范围"
    base_type: "object"
    properties:
      start: {type: "date"}
      end: {type: "date"}
```

#### 3. enums - 枚举类型

```yaml
enums:
  - name: "RiskLevel"
    description: "风险等级"
    values:
      - id: "LOW"
        label: "低风险"
        weight: 0.1
        severity_score: 1
        color: "#00ff00"
      - id: "MEDIUM"
        label: "中风险"
        weight: 0.5
        severity_score: 3
        color: "#ffff00"
      - id: "HIGH"
        label: "高风险"
        weight: 0.8
        severity_score: 5
        color: "#ff8800"
      - id: "CRITICAL"
        label: "极高风险"
        weight: 1.0
        severity_score: 10
        color: "#ff0000"

  - name: "RatingGrade"
    description: "评级等级（参考标普）"
    values:
      - id: "AAA"
        label: "AAA"
        weight: 1.0
        score: 100
      - id: "AA"
        label: "AA+"
        weight: 0.95
        score: 90
      - id: "A"
        label: "A"
        weight: 0.8
        score: 75
      - id: "BBB"
        label: "BBB"
        weight: 0.65
        score: 60
      - id: "BB"
        label: "BB"
        weight: 0.5
        score: 45
      - id: "B"
        label: "B"
        weight: 0.35
        score: 30
      - id: "CCC"
        label: "CCC"
        weight: 0.2
        score: 15
      - id: "D"
        label: "D"
        weight: 0.05
        score: 5

  - name: "AccountType"
    description: "账户类型"
    values:
      - id: "CHECKING"
        label: "活期账户"
        weight: 0.5
      - id: "SAVINGS"
        label: "储蓄账户"
        weight: 0.3
      - id: "FIXED_DEPOSIT"
        label: "定期存款"
        weight: 0.2
      - id: "LOAN"
        label: "贷款账户"
        weight: 0.8
```

#### 4. concepts - 概念/本体层（核心）

```yaml
concepts:
  # ========== 实体对象 (Entity Objects) ==========

  - name: "Bank"
    description: "银行机构"
    category: "entity"
    attributes:
      - name: "bank_id"
        type: "string"
        required: true
        unique: true
        description: "银行唯一标识"
      - name: "name"
        type: "string"
        required: true
        vector_config:
          enabled: true
          weight: 1.0
          searchable: true
      - name: "registered_capital"
        type: "Money"
        description: "注册资本"
      - name: "establishment_date"
        type: "date"
        description: "成立日期"
    relations:
      - name: "has_branch"
        target: "Branch"
        description: "拥有分行"
        cardinality: "1..*"
        inverse: "belongs_to"
        semantic_role: "ownership"
        vector_config:
          enabled: true
          weight: 0.8
      - name: "rates"
        target: "Bank"
        description: "评级（自评或互评）"
        cardinality: "0..*"
        symmetric: true

  - name: "Branch"
    description: "银行分行"
    category: "entity"
    attributes:
      - name: "branch_id"
        type: "string"
        required: true
        unique: true
      - name: "name"
        type: "string"
        required: true
        vector_config:
          enabled: true
          weight: 1.0
      - name: "address"
        type: "string"
        vector_config:
          enabled: true
          weight: 0.7
      - name: "total_deposits"
        type: "Money"
        description: "总存款"
        derived: true
        calculation:
          type: "graph"
          language: "cypher"
          query: |
            MATCH (b:Branch {branch_id: $branch_id})<-[:belongs_to]-(a:Account)
            RETURN SUM(a.balance.value) AS total_deposits
      - name: "branch_risk_score"
        type: "integer"
        description: "分行风险评分（动态计算）"
        derived: true
        calculation:
          type: "multi_strategy"
          strategies:
            - priority: 1
              type: "formula"
              expression: |
                # 基于不良贷款率和流动性比率计算
                npl_ratio = self.non_performing_loan_ratio or 0
                liquidity_ratio = self.liquidity_ratio or 70
                if npl_ratio > 5: return 80 + min(npl_ratio * 5, 20)
                elif liquidity_ratio < 30: return 70
                else: return 50
            - priority: 2
              type: "llm"
              model: "gpt-4o"
              prompt: |
                分析分行 {branch_name} 的风险评分(0-100)：
                - 不良贷款率: {npl_ratio}%
                - 流动性比率: {liquidity_ratio}%
                - 客户投诉数: {complaint_count}
                输出：{"risk_score": number, "key_factors": [string]}
              variables: ["branch_name", "npl_ratio", "liquidity_ratio", "complaint_count"]
    relations:
      - name: "belongs_to"
        target: "Bank"
        inverse: "has_branch"
      - name: "holds"
        target: "Account"
        description: "持有账户"
        cardinality: "1..*"
        inverse: "branch_of"

  - name: "Customer"
    description: "银行客户"
    category: "entity"
    attributes:
      - name: "customer_id"
        type: "string"
        required: true
        unique: true
      - name: "name"
        type: "string"
        required: true
        vector_config:
          enabled: true
          weight: 1.0
          searchable: true
      - name: "id_card"
        type: "string"
        description: "身份证号"
        required: true
      - name: "age"
        type: "integer"
        min: 18
        max: 100
      - name: "credit_score"
        type: "integer"
        description: "信用评分（央行征信）"
        min: 300
        max: 850
        vector_config:
          enabled: true
          weight: 0.9
      - name: "credit_level"
        type: "RiskLevel"
        description: "信用等级（派生）"
        derived: true
        calculation:
          type: "formula"
          expression: |
            if credit_score >= 720: return "LOW"
            elif credit_score >= 680: return "MEDIUM"
            elif credit_score >= 600: return "HIGH"
            else: return "CRITICAL"
      - name: "annual_income"
        type: "Money"
        description: "年收入"
      - name: "debt_to_income_ratio"
        type: "Percentage"
        description: "负债收入比"
        derived: true
        calculation:
          type: "graph"
          language: "cypher"
          query: |
            MATCH (c:Customer {customer_id: $customer_id})-[:has_loan]->(l:Loan)
            RETURN SUM(l.monthly_payment.value) * 12 / c.annual_income.value * 100 AS dti
    relations:
      - name: "holds"
        target: "Account"
        description: "持有账户"
        cardinality: "1..*"
        inverse: "held_by"
      - name: "has_loan"
        target: "Loan"
        description: "有贷款"
        cardinality: "0..*"
        inverse: "granted_to"

  - name: "Account"
    description: "银行账户"
    category: "entity"
    attributes:
      - name: "account_number"
        type: "string"
        required: true
        unique: true
      - name: "account_type"
        type: "AccountType"
        required: true
      - name: "balance"
        type: "Money"
        required: true
        vector_config:
          enabled: true
          weight: 1.0
      - name: "open_date"
        type: "date"
        required: true
      - name: "account_age_months"
        type: "integer"
        description: "账户月龄"
        derived: true
        calculation:
          type: "formula"
          expression: "months_between(today(), open_date)"
      - name: "avg_monthly_balance"
        type: "Money"
        description: "月均余额"
        derived: true
        calculation:
          type: "graph"
          language: "cypher"
          query: |
            MATCH (a:Account {account_number: $account_number})-[:transacts]->(t:Transaction)
            WHERE t.date >= date_sub(today(), 12, 'MONTH')
            RETURN AVG(t.amount.value) AS avg_balance
    relations:
      - name: "held_by"
        target: "Customer"
        inverse: "holds"
      - name: "branch_of"
        target: "Branch"
        inverse: "holds"
      - name: "transacts"
        target: "Transaction"
        description: "发生交易"
        cardinality: "0..*"
        inverse: "involves_account"

  - name: "Loan"
    description: "贷款"
    category: "entity"
    attributes:
      - name: "loan_id"
        type: "string"
        required: true
        unique: true
      - name: "loan_type"
        type: "string"
        description: "贷款类型（房贷/车贷/消费贷）"
        vector_config:
          enabled: true
          weight: 0.6
      - name: "principal"
        type: "Money"
        required: true
        description: "贷款本金"
      - name: "interest_rate"
        type: "Percentage"
        required: true
        description: "年利率"
      - name: "monthly_payment"
        type: "Money"
        required: true
        description: "月还款额"
      - name: "remaining_balance"
        type: "Money"
        required: true
        description: "剩余本金"
      - name: "loan_status"
        type: "string"
        description: "正常/逾期/不良"
      - name: "days_overdue"
        type: "integer"
        description: "逾期天数"
        derived: true
        calculation:
          type: "formula"
          expression: |
            if loan_status == "OVERDUE":
                return days_since(last_payment_date)
            return 0
      - name: "loan_risk_score"
        type: "integer"
        description: "贷款风险评分"
        derived: true
        calculation:
          type: "multi_strategy"
          strategies:
            - priority: 1
              type: "formula"
              expression: |
                score = 30  # 基础分
                if days_overdue > 90: score += 50
                elif days_overdue > 30: score += 30
                elif days_overdue > 0: score += 15
                ltv = remaining_balance.value / collateral_value.value if collateral_value else 1.0
                if ltv > 0.9: score += 20
                return min(score, 100)
            - priority: 2
              type: "llm"
              model: "gpt-4o"
              prompt: |
                评估贷款风险评分(0-100)：
                - 贷款ID: {loan_id}
                - 贷款类型: {loan_type}
                - 逾期天数: {days_overdue}
                - 剩余本金/抵押价值比: {ltv_ratio}
                - 借款人信用等级: {credit_level}
                输出：{"risk_score": number, "main_factors": [string]}
              variables: ["loan_id", "loan_type", "days_overdue", "ltv_ratio", "credit_level"]
    relations:
      - name: "granted_by"
        target: "Branch"
        description: "发放机构"
      - name: "granted_to"
        target: "Customer"
        inverse: "has_loan"

  - name: "Transaction"
    description: "金融交易"
    category: "event"
    attributes:
      - name: "transaction_id"
        type: "string"
        required: true
        unique: true
      - name: "transaction_type"
        type: "string"
        description: "交易类型"
        vector_config:
          enabled: true
          weight: 0.7
      - name: "amount"
        type: "Money"
        required: true
      - name: "date"
        type: "datetime"
        required: true
      - name: "description"
        type: "string"
        vector_config:
          enabled: true
          weight: 0.5
    relations:
      - name: "involves_account"
        target: "Account"
        inverse: "transacts"
      - name: "counterparty"
        target: "Account"
        description: "对手账户"

  - name: "RatingAgency"
    description: "评级机构"
    category: "entity"
    attributes:
      - name: "agency_id"
        type: "string"
        required: true
        unique: true
      - name: "name"
        type: "string"
        required: true
        vector_config:
          enabled: true
          weight: 1.0
      - name: "global_ranking"
        type: "integer"
        description: "全球排名"
    relations:
      - name: "assigns"
        target: "Bank"
        description: "评级银行"
        cardinality: "1..*"

  # ========== 概念/分类 (Concepts/Taxonomies) ==========

  - name: "BankRiskMetric"
    description: "银行风险指标（概念）"
    category: "concept"
    attributes:
      - name: "metric_name"
        type: "string"
      - name: "threshold"
        type: "float"
      - name: "description"
        type: "string"

  - name: "RegulatoryStandard"
    description: "监管标准（概念）"
    category: "concept"
    attributes:
      - name: "standard_id"
        type: "string"
      - name: "name"
        type: "string"
      - name: "issuing_authority"
        type: "string"
```

#### 5. metrics - 指标层

```yaml
metrics:
  # === 银行级别指标 ===

  - name: "capital_adequacy_ratio"
    description: "资本充足率（监管指标）"
    type: "Percentage"
    scope: "Bank"
    regulatory: true  # 标记为监管指标
    calculation:
      priority: 1
      methods:
        - type: "sql"
          engine: "banking_core_db"
          query: |
            SELECT tier1_capital + tier2_capital AS total_capital,
                   risk_weighted_assets
            FROM bank_metrics
            WHERE bank_id = :bank_id
          formula: "total_capital / risk_weighted_assets * 100"

        - type: "graph"
          language: "cypher"
          query: |
            MATCH (b:Bank {bank_id: $bank_id})
            OPTIONAL MATCH (b)<-[:belongs_to]-(br:Branch)<-[:holds]-(a:Account)
            RETURN b.registered_capital.value AS capital,
                   SUM(a.balance.value * 0.5) AS weighted_assets  # 简化权重

  - name: "non_performing_loan_ratio"
    description: "不良贷款率"
    type: "Percentage"
    scope: "Bank"
    calculation:
      type: "graph"
      language: "cypher"
      query: |
        MATCH (b:Bank {bank_id: $bank_id})<-[:granted_by]-(l:Loan)
        WHERE l.loan_status IN ['OVERDUE', 'NPL']
        WITH COUNT(l) AS npl_count
        MATCH (b)<-[:granted_by]-(l2:Loan)
        RETURN npl_count * 100.0 / COUNT(l2) AS npl_ratio

  - name: "liquidity_ratio"
    description: "流动性比率"
    type: "Percentage"
    scope: "Bank"
    calculation:
      type: "multi_strategy"
      strategies:
        - priority: 1
          type: "sql"
          query: |
            SELECT liquid_assets / total_liabilities * 100 AS liquidity
            FROM bank_financials WHERE bank_id = :bank_id
        - priority: 2
          type: "graph"
          query: |
            MATCH (b:Bank {bank_id: $bank_id})<-[:belongs_to]-(br:Branch)
            OPTIONAL MATCH (br)<-[:holds]-(a:Account {account_type: 'CHECKING'})
            WITH SUM(a.balance.value) AS liquid_assets
            MATCH (b)<-[:belongs_to]-(br2:Branch)<-[:holds]-(a2:Account)
            RETURN liquid_assets / SUM(a2.balance.value) * 100

  # === 分行级别指标 ===

  - name: "branch_profit_margin"
    description: "分行利润率"
    type: "Percentage"
    scope: "Branch"
    calculation:
      type: "graph"
      query: |
        MATCH (br:Branch {branch_id: $branch_id})
        OPTIONAL MATCH (br)<-[:belongs_to]-(a:Account)
        WITH br, SUM(a.balance.value * 0.03) AS estimated_income  # 简化
        OPTIONAL MATCH (br)<-[:granted_by]-(l:Loan)
        WITH br, estimated_income, SUM(l.monthly_payment.value * 12 * 0.05) AS interest_income
        RETURN (estimated_income + interest_income) / estimated_income * 100

  # === 客户级别指标 ===

  - name: "customer_credit_score_v2"
    description: "客户信用评分v2（复合指标）"
    type: "integer"
    scope: "Customer"
    calculation:
      type: "multi_strategy"
      strategies:
        - priority: 1
          type: "graph"
          language: "cypher"
          query: |
            MATCH (c:Customer {customer_id: $customer_id})
            OPTIONAL MATCH (c)-[:has_loan]->(l:Loan)
            OPTIONAL MATCH (c)-[:holds]->(a:Account)
            RETURN COALESCE(c.credit_score, 650) * 0.6 +
                   COALESCE(l.loan_risk_score, 50) * 0.25 +
                   COALESCE(a.avg_monthly_balance.value, 10000) / 1000 * 0.15 AS composite_score
        - priority: 2
          type: "llm"
          model: "gpt-4o"
          prompt: |
            综合分析客户信用评分(300-850)：
            客户信息：
            - 姓名: {name}
            - 年龄: {age}
            - 当前信用评分: {current_score}
            - 负债收入比: {dti}%
            - 贷款账户数: {loan_count}
            - 逾期记录: {overdue_records}
            - 账户平均余额: {avg_balance}
            输出：{"credit_score": integer, "main_positive_factors": [string], "main_negative_factors": [string]}
          variables: ["name", "age", "current_score", "dti", "loan_count", "overdue_records", "avg_balance"]

  # === 贷款级别指标 ===

  - name: "loan_default_probability"
    description: "贷款违约概率"
    type: "Percentage"
    scope: "Loan"
    calculation:
      type: "llm"
      model: "gpt-4o"
      prompt: |
        预测贷款违约概率(0-100%)：
        贷款信息：
        - 贷款ID: {loan_id}
        - 贷款类型: {loan_type}
        - 贷款状态: {loan_status}
        - 逾期天数: {days_overdue}
        - 剩余本金: {remaining_balance}
        - 借款人年龄: {customer_age}
        - 借款人信用等级: {customer_credit_level}
        - 借款人负债收入比: {dti}%
        输出：{"default_probability": float, "risk_factors": [string]}
      variables: ["loan_id", "loan_type", "loan_status", "days_overdue", "remaining_balance", "customer_age", "customer_credit_level", "dti"]
```

#### 6. rules - 规则推理层

```yaml
rules:
  # === 监管合规规则 ===

  - name: "capital_adequacy_check"
    description: "资本充足率合规检查"
    type: "constraint"
    severity: "CRITICAL"
    condition:
      type: "and"
      conditions:
        - type: "metric_threshold"
          metric: "capital_adequacy_ratio"
          operator: "<"
          value: 8.0  # 监管要求最低8%
        - type: "expression"
          expression: "bank.tier1_capital > 0"
    actions:
      - type: "alert"
        severity: "CRITICAL"
        message: "银行 {{bank.name}} 资本充足率不足！当前值: {{capital_adequacy_ratio}}%，监管要求: 8%"
        channels: ["regulator", "board"]
      - type: "update"
        field: "bank.compliance_status"
        value: "NON_COMPLIANT"
      - type: "tool_call"
        name: "submit_regulatory_report"
        parameters:
          bank_id: "{{bank.bank_id}}"
          metric_name: "capital_adequacy_ratio"
          actual_value: "{{capital_adequacy_ratio}}"
          required_value: 8.0

  - name: "liquidity_check"
    description: "流动性比率检查"
    type: "constraint"
    condition:
      type: "metric_threshold"
      metric: "liquidity_ratio"
      operator: "<"
      value: 25.0
    actions:
      - type: "alert"
        severity: "HIGH"
        message: "银行 {{bank.name}} 流动性不足！"
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          银行流动性风险分析：
          - 银行: {bank_name}
          - 当前流动性比率: {liquidity_ratio}%
          - 分行数: {branch_count}
          - 高风险分行: {high_risk_branches}
          请生成流动性改善建议。
        variables: ["bank_name", "liquidity_ratio", "branch_count", "high_risk_branches"]

  # === 风险预警规则 ===

  - name: "high_risk_customer_alert"
    description: "高风险客户预警"
    type: "alert"
    priority: 1
    condition:
      type: "and"
      conditions:
        - type: "expression"
          expression: "customer.credit_score < 600"
        - type: "expression"
          expression: "customer.debt_to_income_ratio > 50"
    actions:
      - type: "alert"
        severity: "HIGH"
        message: "客户 {{customer.name}} 存在高风险"
        channels: ["risk_team", "relationship_manager"]
      - type: "update"
        field: "customer.credit_level"
        value: "HIGH"
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          分析高风险客户 {{customer_name}}：
          - 信用评分: {credit_score}
          - 负债收入比: {dti}%
          - 持有账户: {accounts}
          - 贷款情况: {loans}
          输出：{"risk_summary": string, "recommended_actions": [string]}
        variables: ["customer_name", "credit_score", "dti", "accounts", "loans"]

  - name: "loan_default_prediction"
    description: "贷款违约预测与自动触发"
    type: "inference"
    trigger:
      type: "scheduled"
      cron: "0 2 * * *"  # 每天凌晨2点执行
    condition:
      type: "metric_threshold"
      metric: "loan_default_probability"
      operator: ">"
      value: 30.0
    actions:
      - type: "alert"
        severity: "HIGH"
        message: "贷款 {{loan.loan_id}} 存在违约风险"
      - type: "update"
        field: "loan.loan_status"
        value: "AT_RISK"
      - type: "tool_call"
        name: "create_collection_case"
        parameters:
          loan_id: "{{loan.loan_id}}"
          priority: "HIGH"
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          为违约风险贷款生成处置建议：
          - 贷款ID: {loan_id}
          - 贷款类型: {loan_type}
          - 剩余本金: {remaining_balance}
          - 借款人: {customer_name}
          - 违约概率: {default_probability}%
          输出：{"recommended_actions": [string], "expected_recovery_rate": float}
        variables: ["loan_id", "loan_type", "remaining_balance", "customer_name", "default_probability"]

  # === 图关系推理规则 ===

  - name: "branch_interconnection_risk"
    description: "分行关联风险传导分析"
    type: "inference"
    condition:
      type: "graph_pattern"
      language: "cypher"
      pattern: |
        (b1:Branch)-[:belongs_to]->(bank:Bank)
        (b2:Branch)-[:belongs_to]->(bank)
        WHERE b1 <> b2
        AND b1.branch_risk_score > 70
        AND b2.branch_risk_score > 70
    actions:
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          分析分行间风险传导：
          - 高风险分行1: {branch1_name} (评分: {branch1_score})
          - 高风险分行2: {branch2_name} (评分: {branch2_score})
          - 共同所属银行: {bank_name}
          - 两分行间交易量: {transaction_volume}
          分析是否存在风险放大效应。
        variables: ["branch1_name", "branch1_score", "branch2_name", "branch2_score", "bank_name", "transaction_volume"]

  - name: "customer_network_fraud"
    description: "客户关联网络欺诈检测"
    type: "inference"
    condition:
      type: "graph_pattern"
      language: "cypher"
      pattern: |
        (c1:Customer)-[:transacts]->(a1:Account)<-[:transacts]-(c2:Customer)
        WHERE c1 <> c2
        AND c1.credit_level = 'CRITICAL'
        AND c2.credit_level = 'CRITICAL'
        AND COUNT((a1)<-[:transacts]-()) > 10
    actions:
      - type: "alert"
        severity: "CRITICAL"
        message: "检测到疑似欺诈网络"
      - type: "tool_call"
        name: "freeze_accounts_in_network"
        parameters:
          center_account: "{{a1.account_number}}"

  # === 评级相关规则 ===

  - name: "rating_downgrade_trigger"
    description: "评级下调触发"
    type: "inference"
    condition:
      type: "or"
      conditions:
        - type: "metric_threshold"
          metric: "non_performing_loan_ratio"
          operator: ">"
          value: 5.0
        - type: "metric_threshold"
          metric: "capital_adequacy_ratio"
          operator: "<"
          value: 10.0
    actions:
      - type: "update"
        field: "bank.current_rating"
        value: "{{calculated_downgrade}}"
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          生成评级调整报告：
          - 银行: {bank_name}
          - 原评级: {old_rating}
          - 新评级: {new_rating}
          - 触发原因: {trigger_reasons}
          - 监管建议: {regulatory_recommendations}
          输出：{"rating_report": string, "stakeholder_communication": string}
        variables: ["bank_name", "old_rating", "new_rating", "trigger_reasons", "regulatory_recommendations"]
```

#### 7. data_sources - 数据源映射

```yaml
data_sources:
  - name: "banking_core_db"
    type: "postgresql"
    connection: "${BANKING_DB_CONNECTION}"
    description: "银行核心系统"

    tables:
      - source_table: "banks"
        target_concept: "Bank"
        mapping:
          bank_id: "bank_id"
          name: "name"
          registered_capital: "registered_capital"
          establishment_date: "establishment_date"

      - source_table: "branches"
        target_concept: "Branch"
        mapping:
          branch_id: "branch_id"
          name: "name"
          address: "address"
          bank_id: "bank_id"  # 外键 → 关系

      - source_table: "customers"
        target_concept: "Customer"
        mapping:
          customer_id: "customer_id"
          name: "name"
          id_card: "id_card"
          age: "age"
          credit_score: "credit_score"
          annual_income: "annual_income"

      - source_table: "accounts"
        target_concept: "Account"
        mapping:
          account_number: "account_number"
          account_type: "account_type"
          balance: "balance"
          open_date: "open_date"
          customer_id: "customer_id"  # 外键
          branch_id: "branch_id"      # 外键

      - source_table: "loans"
        target_concept: "Loan"
        mapping:
          loan_id: "loan_id"
          loan_type: "loan_type"
          principal: "principal"
          interest_rate: "interest_rate"
          monthly_payment: "monthly_payment"
          remaining_balance: "remaining_balance"
          loan_status: "loan_status"
          customer_id: "customer_id"
          branch_id: "branch_id"

      - source_table: "transactions"
        target_concept: "Transaction"
        mapping:
          transaction_id: "transaction_id"
          transaction_type: "transaction_type"
          amount: "amount"
          date: "date"
          from_account: "from_account"  # 外键
          to_account: "to_account"      # 外键

    relations:
      - source_join:
          table: "branches"
          field: "bank_id"
        target:
          concept: "Bank"
          field: "bank_id"
        relation: "belongs_to"

      - source_join:
          table: "accounts"
          field: "customer_id"
        target:
          concept: "Customer"
          field: "customer_id"
        relation: "held_by"

      - source_join:
          table: "accounts"
          field: "branch_id"
        target:
          concept: "Branch"
          field: "branch_id"
        relation: "branch_of"

      - source_join:
          table: "loans"
          field: "customer_id"
        target:
          concept: "Customer"
          field: "customer_id"
        relation: "has_loan"

      - source_join:
          table: "loans"
          field: "branch_id"
        target:
          concept: "Branch"
          field: "branch_id"
        relation: "granted_by"

  - name: "rating_agency_api"
    type: "rest_api"
    endpoint: "https://api.rating-agency.com/v1"
    auth: "bearer_token"
    description: "评级机构数据"

    mappings:
      - source_field: "bank_rating"
        target_concept: "Bank"
        target_field: "external_rating"
        transform: |
          def map_rating(agency, grade):
              rating_map = {"AAA": 100, "AA+": 95, ...}
              return rating_map.get(grade, 50)

  - name: "credit_bureau_api"
    type: "rest_api"
    endpoint: "https://api.credit-bureau.com/credit"
    auth: "api_key"
    description: "央行征信数据"
    mappings:
      - source_field: "credit_record"
        target_concept: "Customer"
        target_field: "credit_score"
        sync_frequency: "daily"
```

#### 8. vector_config - 向量检索配置

```yaml
vector_config:
  global:
    index_type: "IVF_FLAT"
    distance_metric: "cosine"
    dimension: 1536
    model: "text-embedding-3-small"

  models:
    - name: "text-embedding-3-small"
      provider: "openai"
      dimension: 1536
      cost: "low"

    - name: "bge-m3"
      provider: "local"
      dimension: 1024
      cost: "medium"
      description: "中文embedding模型"

  indexes:
    - name: "bank_semantic_search"
      type: "HNSW"
      metric: "cosine"
      concepts: ["Bank", "Branch"]
      fields:
        - "Bank.name"
        - "Branch.name"
        - "Branch.address"
      description: "银行和分行语义搜索"

    - name: "customer_risk_analysis"
      type: "IVF_FLAT"
      metric: "l2"
      concepts: ["Customer", "Loan"]
      fields:
        - "Customer.credit_score"
        - "Loan.loan_risk_score"
        - "Loan.loan_type"
      description: "客户风险分析向量"

    - name: "transaction_pattern"
      type: "HNSW"
      metric: "cosine"
      concepts: ["Transaction"]
      fields:
        - "Transaction.transaction_type"
        - "Transaction.description"
      description: "交易模式识别"
```

#### 9. llm_config - 大模型配置

```yaml
llm_config:
  providers:
    - name: "openai"
      type: "openai"
      model: "gpt-4o"
      api_key: "${OPENAI_API_KEY}"
      default: true
      config:
        temperature: 0.3
        max_tokens: 4000

    - name: "claude"
      type: "anthropic"
      model: "claude-3-5-sonnet"
      api_key: "${ANTHROPIC_API_KEY}"
      config:
        temperature: 0.2

    - name: "local"
      type: "ollama"
      model: "llama3:70b"
      endpoint: "http://localhost:11434"
      config:
        temperature: 0.1

  prompt_templates:
    risk_assessment: |
      你是一个专业的银行风险分析师。请基于以下信息进行风险评估：
      {{context}}
      问题：{{question}}
      请给出专业、准确的分析。

    rating_explanation: |
      请解释以下银行评级变动的具体原因：
      - 银行名称: {{bank_name}}
      - 原评级: {{old_rating}}
      - 新评级: {{new_rating}}
      - 关键指标变化: {{metric_changes}}
      请用通俗语言解释，并说明对银行的影响。

    fraud_detection: |
      请分析以下交易是否涉嫌欺诈：
      - 交易ID: {{transaction_id}}
      - 金额: {{amount}}
      - 交易类型: {{transaction_type}}
      - 交易时间: {{timestamp}}
      - 账户历史: {{account_history}}
      输出JSON：{"is_fraud": boolean, "confidence": float, "reasons": [string]}

  progressive_disclosure:
    level_1:
      description: "基础信息（用户界面展示）"
      template: |
        银行: {{bank.name}}
        评级: {{bank.current_rating}}
        风险等级: {{bank.risk_level}}

    level_2:
      description: "详细信息（风控人员）"
      template: |
        银行: {{bank.name}} ({{bank.bank_id}})
        评级: {{bank.current_rating}} ({{rating_date}})
        风险等级: {{bank.risk_level}}
        关键指标：
        - 资本充足率: {{capital_adequacy_ratio}}%
        - 不良贷款率: {{non_performing_loan_ratio}}%
        - 流动性比率: {{liquidity_ratio}}%
        分行数: {{branch_count}}

    level_3:
      description: "完整信息（监管报告）"
      template: |
        === 银行完整分析报告 ===
        银行: {{bank.name}} ({{bank.bank_id}})
        成立日期: {{bank.establishment_date}}
        注册资本: {{bank.registered_capital}}
        === 评级信息 ===
        当前评级: {{bank.current_rating}}
        评级历史: {{rating_history}}
        === 监管指标 ===
        {{regulatory_metrics}}
        === 风险分析 ===
        {{risk_analysis}}
        === 分行网络 ===
        {{branch_network}}
        === 关联贷款 ===
        {{loan_portfolio}}
        === LLM推理结论 ===
        {{llm_insights}}
```

#### 10. instances - 实例数据

```yaml
instances:
  - concept: "Bank"
    data:
      - bank_id: "BANK-001"
        name: "中国商业银行"
        registered_capital:
          value: 10000000000
          currency: "CNY"
        establishment_date: "1990-01-15"

      - bank_id: "BANK-002"
        name: "东亚银行"
        registered_capital:
          value: 5000000000
          currency: "CNY"
        establishment_date: "2005-06-20"

  - concept: "Branch"
    data:
      - branch_id: "BR-001"
        name: "北京分行"
        address: "北京市朝阳区建国路88号"
        belongs_to: "BANK-001"

      - branch_id: "BR-002"
        name: "上海浦东分行"
        address: "上海市浦东新区陆家嘴环路1000号"
        belongs_to: "BANK-001"

      - branch_id: "BR-003"
        name: "深圳分行"
        address: "深圳市福田区深南大道100号"
        belongs_to: "BANK-002"

  - concept: "Customer"
    data:
      - customer_id: "CUST-001"
        name: "张伟"
        id_card: "110101198501011234"
        age: 39
        credit_score: 720
        annual_income:
          value: 500000
          currency: "CNY"
        holds:
          - account_number: "ACC-001"
          - account_number: "ACC-003"
        has_loan:
          - loan_id: "LOAN-001"

      - customer_id: "CUST-002"
        name: "李娜"
        id_card: "310101199003032345"
        age: 33
        credit_score: 680
        annual_income:
          value: 300000
          currency: "CNY"
        holds:
          - account_number: "ACC-002"
        has_loan:
          - loan_id: "LOAN-002"

  - concept: "Account"
    data:
      - account_number: "ACC-001"
        account_type: "CHECKING"
        balance:
          value: 150000
          currency: "CNY"
        open_date: "2015-03-20"
        held_by: "CUST-001"
        branch_of: "BR-001"

      - account_number: "ACC-002"
        account_type: "SAVINGS"
        balance:
          value: 80000
          currency: "CNY"
        open_date: "2018-07-15"
        held_by: "CUST-002"
        branch_of: "BR-002"

      - account_number: "ACC-003"
        account_type: "FIXED_DEPOSIT"
        balance:
          value: 500000
          currency: "CNY"
        open_date: "2020-01-10"
        held_by: "CUST-001"
        branch_of: "BR-001"

  - concept: "Loan"
    data:
      - loan_id: "LOAN-001"
        loan_type: "MORTGAGE"
        principal:
          value: 2000000
          currency: "CNY"
        interest_rate: 4.9
        monthly_payment:
          value: 10614
          currency: "CNY"
        remaining_balance:
          value: 1800000
          currency: "CNY"
        loan_status: "NORMAL"
        granted_by: "BR-001"
        granted_to: "CUST-001"

      - loan_id: "LOAN-002"
        loan_type: "PERSONAL"
        principal:
          value: 100000
          currency: "CNY"
        interest_rate: 8.0
        monthly_payment:
          value: 2500
          currency: "CNY"
        remaining_balance:
          value: 85000
          currency: "CNY"
        loan_status: "OVERDUE"
        granted_by: "BR-002"
        granted_to: "CUST-002"
```

---

## 关键设计决策汇总

| 设计点 | 决策 | 理由 |
|--------|------|------|
| 模块化 | 10个独立模块 | 可独立使用，灵活组合 |
| 双格式 | YAML(人类) + JSON(机器) | 可读性与互操作性兼顾 |
| 对象类型 | `category: "entity"` | 在 concepts 中通过 category 字段区分 entity/concept/event |
| 向量融合 | vector_config内嵌到types/attributes/relations | 语义与向量检索天然对齐 |
| 动态指标 | derived: true + multi_strategy calculation | 支持多种计算策略回退 |
| 规则推理 | graph_pattern + expression + llm 三种条件 | 覆盖符号/图/语义推理 |
| 表达式引擎 | 完整运算符+内置函数库 | 支持算术/比较/逻辑/字符串/集合/时间/图函数 |
| 规则维度 | rule_dimensions + scope机制 | 同一对象在不同业务维度下适用不同规则 |
| 指标取数 | sql/graph/rest_api/stream/file多类型 | 支持从多种数据源取数 |
| LLM集成 | llm_config + 规则内嵌llm | 统一管理+按需调用 |
| 概念分类 | category: entity/concept/event | 区分实例/概念/事件 |
| 派生属性 | compute_on触发 + 多策略回退 | 支持变化触发/定时/手动刷新 |

---

## JSON-LD 等价表示

上述 KGML 可转换为标准 JSON-LD：

```json
{
  "@context": {
    "kgml": "https://example.com/kgml/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#"
  },
  "@graph": [
    {
      "@id": "kgml:Bank",
      "@type": "rdfs:Class",
      "rdfs:label": "银行机构"
    },
    {
      "@id": "kgml:Bank_name",
      "@type": "rdf:Property",
      "rdfs:domain": "kgml:Bank",
      "rdfs:range": "xsd:string"
    },
    {
      "@id": "kgml:has_branch",
      "@type": "owl:ObjectProperty",
      "rdfs:domain": "kgml:Bank",
      "rdfs:range": "kgml:Branch",
      "owl:inverseOf": "kgml:belongs_to"
    }
  ]
}
```

---

## 扩展场景：供应链金融 + 跨境支付

### 场景1：供应链金融（Supply Chain Finance）

在银行评级模型基础上，增加供应链上下游企业、订单、存货、应收账款等实体：

```yaml
# === 扩展 Concepts ===

concepts:
  # 新增实体
  - name: "Enterprise"
    description: "企业客户"
    category: "entity"
    attributes:
      - name: "enterprise_id"
        type: "string"
        required: true
        unique: true
      - name: "name"
        type: "string"
        required: true
        vector_config:
          enabled: true
          weight: 1.0
      - name: "business_type"
        type: "string"
        description: "企业经营类型（核心企业/供应商/经销商）"
      - name: "annual_revenue"
        type: "Money"
    relations:
      - name: "supplies_to"
        target: "Enterprise"
        description: "供货给（供应链上游）"
        cardinality: "0..*"
        inverse: "receives_from"
      - name: "financed_by"
        target: "Bank"
        description: "融资银行"

  - name: "PurchaseOrder"
    description: "采购订单"
    category: "event"
    attributes:
      - name: "order_id"
        type: "string"
        required: true
      - name: "amount"
        type: "Money"
        required: true
      - name: "delivery_date"
        type: "date"
      - name: "order_status"
        type: "string"
        description: "PENDING/SHIPPED/DELIVERED/PAID"

  - name: "AccountsReceivable"
    description: "应收账款"
    category: "entity"
    attributes:
      - name: "ar_id"
        type: "string"
        required: true
      - name: "amount"
        type: "Money"
        required: true
      - name: "due_date"
        type: "date"
        required: true
      - name: "aging_days"
        type: "integer"
        derived: true
        calculation:
          type: "formula"
          expression: "days_between(today(), due_date)"

  - name: "Inventory"
    description: "存货/库存"
    category: "entity"
    attributes:
      - name: "inventory_id"
        type: "string"
        required: true
      - name: "product_name"
        type: "string"
        vector_config:
          enabled: true
          weight: 0.8
      - name: "quantity"
        type: "integer"
      - name: "unit_value"
        type: "Money"

# === 扩展 Metrics ===

metrics:
  - name: "supply_chain_risk_index"
    description: "供应链风险指数"
    type: "float"
    scope: "Enterprise"
    calculation:
      type: "multi_strategy"
      strategies:
        - priority: 1
          type: "graph"
          language: "cypher"
          query: |
            MATCH (e:Enterprise {enterprise_id: $enterprise_id})
            OPTIONAL MATCH (e)-[:supplies_to]->(supplier:Enterprise)
            OPTIONAL MATCH (e)<-[:receives_from]-(buyer:Enterprise)
            RETURN COUNT(supplier) AS supplier_count,
                   COUNT(buyer) AS buyer_count,
                   COUNT(DISTINCT supplier) AS unique_suppliers
        - priority: 2
          type: "llm"
          model: "gpt-4o"
          prompt: |
            分析企业 {enterprise_name} 的供应链风险：
            - 供应商数量: {supplier_count}
            - 采购商数量: {buyer_count}
            - 应收账款账龄: {ar_aging}
            - 存货周转率: {inventory_turnover}
            输出：{"risk_index": float (0-100), "main_risks": [string]}
          variables: ["enterprise_name", "supplier_count", "buyer_count", "ar_aging", "inventory_turnover"]

  - name: "accounts_receivable_aging"
    description: "应收账款账龄分析"
    type: "object"
    scope: "Enterprise"
    calculation:
      type: "graph"
      query: |
        MATCH (e:Enterprise)-[:has_ar]->(ar:AccountsReceivable)
        WHERE ar.due_date < date()
        WITH e, ar,
             CASE
               WHEN ar.due_date < date_sub(today(), 90) THEN 'OVERDUE_90'
               WHEN ar.due_date < date_sub(today(), 60) THEN 'OVERDUE_60'
               WHEN ar.due_date < date_sub(today(), 30) THEN 'OVERDUE_30'
               ELSE 'CURRENT'
             END AS aging_bucket
        RETURN e.enterprise_id AS enterprise_id,
               COLLECT({bucket: aging_bucket, amount: ar.amount.value}) AS aging_detail

# === 扩展 Rules ===

rules:
  - name: "supply_chain_default_risk"
    description: "供应链违约风险传导"
    type: "inference"
    condition:
      type: "graph_pattern"
      language: "cypher"
      pattern: |
        (buyer:Enterprise)-[:has_ar]->(ar:AccountsReceivable)
        WHERE ar.aging_days > 90
        WITH buyer
        MATCH (supplier:Enterprise)-[:supplies_to]->(buyer)
        WHERE supplier.credit_score < 600
    actions:
      - type: "alert"
        severity: "HIGH"
        message: "检测到供应链风险传导：核心企业违约风险上升"
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          分析供应链风险传导：
          - 违约企业: {defaulting_enterprise}
          - 上游供应商: {affected_supplier}
          - 应收账款逾期: {ar_amount}
          输出：{"risk_propagation": string, "recommended_actions": [string]}
        variables: ["defaulting_enterprise", "affected_supplier", "ar_amount"]

  - name: "inventory_financing_collateral"
    description: "存货融资抵押物监控"
    type: "constraint"
    condition:
      type: "expression"
      expression: "inventory.quantity < min_safe_level"
    actions:
      - type: "alert"
        severity: "MEDIUM"
        message: "存货 {inventory_id} 低于安全库存"
      - type: "update"
        field: "inventory.collateral_status"
        value: "AT_RISK"
```

### 场景2：跨境支付（Cross-Border Payment）

```yaml
# === 扩展 Concepts ===

concepts:
  - name: "CorrespondentBank"
    description: "代理银行（跨境清算）"
    category: "entity"
    attributes:
      - name: "bank_id"
        type: "string"
        required: true
      - name: "name"
        type: "string"
        required: true
      - name: "country"
        type: "string"
        description: "所在国家"
      - name: "swift_code"
        type: "string"
        description: "SWIFT代码"
      - name: "risk_rating"
        type: "RatingGrade"

  - name: "CrossBorderTransaction"
    description: "跨境交易"
    category: "event"
    attributes:
      - name: "txn_id"
        type: "string"
        required: true
      - name: "amount"
        type: "Money"
        required: true
      - name: "source_currency"
        type: "string"
      - name: "target_currency"
        type: "string"
      - name: "exchange_rate"
        type: "float"
      - name: "fx_spread"
        type: "float"
        description: "外汇点差"
      - name: "compliance_status"
        type: "string"
        description: "AML/KYC合规状态"
    relations:
      - name: "via_bank"
        target: "CorrespondentBank"
        description: "经由代理银行"
        cardinality: "1..*"
      - name: "sender"
        target: "Customer"
      - name: "receiver"
        target: "Customer"

  - name: "SanctionsList"
    description: "制裁名单"
    category: "concept"
    attributes:
      - name: "entity_name"
        type: "string"
        required: true
      - name: "list_type"
        type: "string"
        description: "OFAC/UN/EU/OTHER"
      - name: "listing_date"
        type: "date"
      - name: "sanction_type"
        type: "string"
        description: "资产冻结/交易禁止/人员限制"

# === 扩展 Metrics ===

metrics:
  - name: "cross_border_txn_volume"
    description: "跨境交易量（按币种/国家）"
    type: "object"
    calculation:
      type: "graph"
      query: |
        MATCH (txn:CrossBorderTransaction)-[:via_bank]->(cb:CorrespondentBank)
        WHERE txn.date >= date_sub(today(), 30)
        RETURN cb.country AS country,
               txn.source_currency AS currency,
               SUM(txn.amount.value) AS total_volume,
               COUNT(*) AS txn_count

  - name: "aml_risk_score"
    description: "反洗钱风险评分"
    type: "float"
    scope: "Customer"
    calculation:
      type: "multi_strategy"
      strategies:
        - priority: 1
          type: "graph"
          query: |
            MATCH (c:Customer)-[:transacts]->(a:Account)-[:transacts]->(txn:Transaction)
            WHERE txn.date >= date_sub(today(), 180, 'DAY')
            WITH c, COUNT(DISTINCT txn.transaction_id) AS txn_count,
                 SUM(txn.amount.value) AS total_amount,
                 MAX(txn.amount.value) AS max_single
            RETURN txn_count * 0.1 + total_amount / 1000000 * 0.3 +
                   max_single / 100000 * 0.6 AS aml_score
        - priority: 2
          type: "llm"
          model: "gpt-4o"
          prompt: |
            分析客户 {customer_name} 的反洗钱风险(0-100)：
            - 180天内交易笔数: {txn_count}
            - 交易总额: {total_amount}
            - 最大单笔金额: {max_single}
            - 跨境交易占比: {cross_border_ratio}
            - 高风险国家交易: {high_risk_country_txns}
            输出：{"aml_risk_score": float, "red_flags": [string]}
          variables: ["customer_name", "txn_count", "total_amount", "max_single", "cross_border_ratio", "high_risk_country_txns"]

# === 扩展 Rules ===

rules:
  - name: "sanctions_screen_check"
    description: "制裁名单筛查"
    type: "constraint"
    condition:
      type: "expression"
      expression: "is_on_sanctions_list(sender) OR is_on_sanctions_list(receiver)"
    actions:
      - type: "reject"
        message: "交易对手在制裁名单中"
      - type: "alert"
        severity: "CRITICAL"
        message: "触发制裁名单警报"
        channels: ["compliance_officer", "regulator"]
      - type: "tool_call"
        name: "submit_suspicious_activity_report"
        parameters:
          txn_id: "{{txn.txn_id}}"
          parties: "{{[sender, receiver]}}"

  - name: "cross_border_high_risk_corridor"
    description: "高风险跨境走廊检测"
    type: "inference"
    condition:
      type: "graph_pattern"
      pattern: |
        (txn:CrossBorderTransaction)-[:via_bank]->(cb:CorrespondentBank)
        WHERE cb.risk_rating IN ['B', 'CCC', 'D']
        AND txn.amount.value > 1000000
    actions:
      - type: "alert"
        severity: "HIGH"
        message: "检测到高风险跨境交易"
      - type: "llm"
        model: "gpt-4o"
        prompt: |
          分析高风险跨境交易：
          - 交易ID: {txn_id}
          - 金额: {amount}
          - 代理银行: {correspondent_bank} (评级: {rating})
          - 交易双方: {sender} -> {receiver}
          输出：{"risk_assessment": string, "enhanced_due_diligence": string}
        variables: ["txn_id", "amount", "correspondent_bank", "rating", "sender", "receiver"]

  - name: "structuring_detection"
    description: "拆分交易检测（化整为零规避报告）"
    type: "inference"
    condition:
      type: "graph_pattern"
      pattern: |
        (c:Customer)-[:transacts]->(a1:Account)-[:transacts]->(t1:Transaction),
        (c)-[:transacts]->(a2:Account)-[:transacts]->(t2:Transaction)
        WHERE t1.date < t2.date
        AND t2.date - t1.date < 24 * 60 * 60 * 1000  -- 24小时内
        AND t1.amount.value + t2.amount.value > 100000
        AND t1.amount.value < 10000
        AND t2.amount.value < 10000
    actions:
      - type: "alert"
        severity: "CRITICAL"
        message: "疑似拆分交易"
      - type: "tool_call"
        name: "file_ctr_report"  # Currency Transaction Report
        parameters:
          customer_id: "{{c.customer_id}}"
          related_transactions: "{{[t1.txn_id, t2.txn_id]}}"
```

---

## 验证计划

1. **格式验证**：使用 JSON Schema 验证 KGML JSON 输出
2. **语义验证**：检查 concept 继承链、relation inverse 一致性
3. **互转验证**：YAML ↔ JSON 双向转换保持语义一致
4. **JSON-LD 导出**：验证到 RDF/OWL 的映射正确性
5. **端到端测试**：
   - 用示例数据构建完整 KGML 文档
   - 模拟 ETL 流程（data_sources → instances）
   - 触发 metrics 计算
   - 执行 rules 推理
   - 调用 LLM 生成解释
