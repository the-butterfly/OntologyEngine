# 规则管理详细设计方案

## 一、核心设计理念

### 1.1 设计目标

**一句话概括：输入原子指标 → 自动解析依赖 → 执行计算链 → 输出全量结果**

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户视角                                  │
│  输入: {"netAsset": 1亿, "totalGuarantee": 5000万, ...}        │
│  输出: {"riskGrade": "B", "riskScore": 72.5, "alerts": [...]}  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      系统内部                                    │
│  1. 依赖解析 → 构建计算图 (DAG)                                 │
│  2. 拓扑排序 → 确定执行顺序                                     │
│  3. 逐层执行 → 调用算子/规则/外部API                            │
│  4. 结果汇聚 → 返回全量指标                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心概念模型

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│    原子指标     │─────▶│    派生指标     │─────▶│    复合指标     │
│  (Atomic)      │      │  (Derived)     │      │  (Composite)   │
└────────────────┘      └────────────────┘      └────────────────┘
       │                        │                        │
       │                        │                        │
       ▼                        ▼                        ▼
  外部数据源              规则计算得出              多指标聚合
  用户直接输入            单一算子处理             复杂逻辑组合
```

| 概念 | 定义 | 示例 | 来源 |
|------|------|------|------|
| **原子指标** | 不可再分的原始数据 | 净资产、担保金额、交易笔数 | 外部系统/用户输入 |
| **派生指标** | 由原子指标计算得出 | 担保比例、交易活跃度 | 单一算子计算 |
| **复合指标** | 多个指标组合计算 | 综合风险评分、风险等级 | 多算子组合 |
| **规则** | 完整的计算逻辑单元 | 风险评级规则、准入检查规则 | 用户定义 |
| **算子** | 可复用的计算函数 | SUM、AVG、评分卡、逻辑树 | 系统内置/外部注册 |
| **计算图** | 规则依赖关系的DAG | 指标A→指标B→指标C | 自动构建 |

---

## 二、声明式 Schema 设计

### 2.1 整体结构

```yaml
# schema/rule_schema_v1.yaml

# ============================================================
# 规则定义规范 v1.0
# ============================================================

schema_version: "1.0.0"
namespace: "finance.risk"  # 命名空间，支持多租户

# ============================================================
# 元信息
# ============================================================
metadata:
  name: "交易对手风险管理规则集"
  version: "2.1.0"
  owner: "risk_management_dept"
  effective_date: "2024-01-01"
  expiry_date: null
  description: "用于交易对手准入评估、风险评级和持续监控"
  tags: ["risk", "counterparty", "regulation"]

# ============================================================
# 全局配置
# ============================================================
config:
  # 执行模式
  execution:
    mode: "sequential"        # sequential | parallel | hybrid
    timeout: 30000            # 单条规则超时（毫秒）
    max_depth: 10             # 依赖链最大深度
    
  # 缓存策略
  cache:
    enabled: true
    ttl: 3600                 # 缓存时间（秒）
    key_pattern: "{rule_id}:{entity_id}:{date}"
    
  # 异常处理
  error_handling:
    on_missing_input: "error"   # error | skip | default
    on_compute_error: "skip"    # error | skip | fallback
    on_timeout: "skip"          # error | skip | fallback
    
  # 日志级别
  logging:
    level: "INFO"               # DEBUG | INFO | WARN | ERROR
    trace_compute: true         # 是否记录计算过程

# ============================================================
# 全局变量（常量）
# ============================================================
globals:
  # 行业基准值
  industry_benchmarks:
    avg_capital_adequacy_ratio: 0.105
    avg_leverage_ratio: 0.65
    
  # 风险参数
  risk_parameters:
    risk_free_rate: 0.03
    confidence_level: 0.95
    
  # 阈值配置
  thresholds:
    capital_adequacy_warning: 0.08
    capital_adequacy_critical: 0.06
    guarantee_ratio_warning: 0.5
    guarantee_ratio_critical: 0.8

# ============================================================
# 输入定义（原子指标）
# ============================================================
inputs:
  # 格式: 指标名: {类型, 描述, 是否必填, 默认值, 校验规则}
  
  # ========== 实体基础信息 ==========
  entity_id:
    type: "string"
    description: "实体唯一标识"
    required: true
    validation:
      pattern: "^[A-Z]{2}\\d{8}$"  # 统一社会信用代码格式
      
  legal_name:
    type: "string"
    description: "机构名称"
    required: true
    
  institution_type:
    type: "enum"
    description: "机构类型"
    required: true
    enum_values: ["bank", "securities", "insurance", "fund", "trust", "other"]
    
  status:
    type: "enum"
    description: "经营状态"
    required: true
    enum_values: ["active", "suspended", "revoked", "liquidation"]
    default: "active"
    
  # ========== 财务指标 ==========
  net_asset:
    type: "decimal"
    description: "净资产（元）"
    required: true
    unit: "CNY"
    validation:
      min: 0
      
  total_asset:
    type: "decimal"
    description: "总资产（元）"
    required: true
    unit: "CNY"
    validation:
      min: 0
      
  registered_capital:
    type: "decimal"
    description: "注册资本（元）"
    required: true
    unit: "CNY"
    
  capital_adequacy_ratio:
    type: "decimal"
    description: "资本充足率"
    required: false
    unit: "ratio"
    validation:
      min: 0
      max: 1
    default: null
    
  # ========== 担保相关 ==========
  total_guarantee_out:
    type: "decimal"
    description: "对外担保总额（元）"
    required: false
    default: 0
    unit: "CNY"
    
  total_guarantee_in:
    type: "decimal"
    description: "接收担保总额（元）"
    required: false
    default: 0
    unit: "CNY"
    
  guarantee_chain_depth:
    type: "integer"
    description: "担保链深度"
    required: false
    default: 0
    
  # ========== 交易相关 ==========
  transaction_count_90d:
    type: "integer"
    description: "近90天交易笔数"
    required: false
    default: 0
    
  transaction_amount_90d:
    type: "decimal"
    description: "近90天交易总额（元）"
    required: false
    default: 0
    unit: "CNY"
    
  high_risk_counterparty_count:
    type: "integer"
    description: "高风险交易对手数量"
    required: false
    default: 0
    
  # ========== 舆情相关 ==========
  negative_news_count_30d:
    type: "integer"
    description: "近30天负面新闻数量"
    required: false
    default: 0
    
  negative_news_sentiment_score:
    type: "decimal"
    description: "负面舆情情感得分"
    required: false
    default: 0
    validation:
      min: -1
      max: 0

# ============================================================
# 输出定义（计算结果）
# ============================================================
outputs:
  # 格式: 指标名: {类型, 描述, 值域}
  
  # ========== 风险评级 ==========
  risk_grade:
    type: "enum"
    description: "风险等级"
    enum_values: ["A", "B", "C", "D", "E"]
    
  risk_score:
    type: "decimal"
    description: "综合风险评分（0-100）"
    validation:
      min: 0
      max: 100
      
  # ========== 风险维度得分 ==========
  capital_score:
    type: "decimal"
    description: "资本充足度得分"
    validation:
      min: 0
      max: 100
      
  guarantee_score:
    type: "decimal"
    description: "担保风险得分"
    validation:
      min: 0
      max: 100
      
  trading_score:
    type: "decimal"
    description: "交易稳定性得分"
    validation:
      min: 0
      max: 100
      
  reputation_score:
    type: "decimal"
    description: "声誉风险得分"
    validation:
      min: 0
      max: 100
      
  # ========== 预警信息 ==========
  alert_level:
    type: "enum"
    description: "预警级别"
    enum_values: ["none", "warning", "critical"]
    
  alert_messages:
    type: "array"
    description: "预警消息列表"
    item_type: "string"
    
  # ========== 决策建议 ==========
  cooperation_strategy:
    type: "enum"
    description: "合作策略建议"
    enum_values: ["expand", "maintain", "monitor", "restrict", "prohibit"]
  
  next_review_date:
    type: "date"
    description: "下次复评日期"

# ============================================================
# 中间指标定义（规则间可引用）
# ============================================================
intermediate_metrics:
  # 派生指标：由输入直接计算
  
  guarantee_ratio:
    type: "decimal"
    description: "对外担保比例"
    formula: "total_guarantee_out / net_asset"
    dependencies: ["total_guarantee_out", "net_asset"]
    
  leverage_ratio:
    type: "decimal"
    description: "杠杆率"
    formula: "total_asset / net_asset"
    dependencies: ["total_asset", "net_asset"]
    
  trading_intensity:
    type: "decimal"
    description: "交易活跃度"
    formula: "transaction_amount_90d / net_asset"
    dependencies: ["transaction_amount_90d", "net_asset"]
    
  high_risk_exposure_ratio:
    type: "decimal"
    description: "高风险敞口占比"
    formula: "high_risk_counterparty_count / transaction_count_90d"
    dependencies: ["high_risk_counterparty_count", "transaction_count_90d"]

# ============================================================
# 算子注册表
# ============================================================
operators:
  # ========== 数学算子 ==========
  - name: "ADD"
    category: "math"
    description: "加法"
    parameters:
      operands: {type: "array", item_type: "number"}
      
  - name: "SUB"
    category: "math"
    description: "减法"
    parameters:
      minuend: {type: "number"}
      subtrahend: {type: "number"}
      
  - name: "MUL"
    category: "math"
    description: "乘法"
    parameters:
      factors: {type: "array", item_type: "number"}
      
  - name: "DIV"
    category: "math"
    description: "除法"
    parameters:
      dividend: {type: "number"}
      divisor: {type: "number", nonzero: true}
      
  - name: "SUM"
    category: "math"
    description: "求和"
    parameters:
      values: {type: "array", item_type: "number"}
      
  - name: "AVG"
    category: "math"
    description: "平均值"
    parameters:
      values: {type: "array", item_type: "number"}
      
  - name: "MAX"
    category: "math"
    description: "最大值"
    parameters:
      values: {type: "array", item_type: "number"}
      
  - name: "MIN"
    category: "math"
    description: "最小值"
    parameters:
      values: {type: "array", item_type: "number"}
      
  - name: "PERCENTILE"
    category: "math"
    description: "百分位数"
    parameters:
      values: {type: "array", item_type: "number"}
      percentile: {type: "number", min: 0, max: 100}
      
  - name: "STDDEV"
    category: "math"
    description: "标准差"
    parameters:
      values: {type: "array", item_type: "number"}

  # ========== 逻辑算子 ==========
  - name: "IF"
    category: "logic"
    description: "条件判断"
    parameters:
      condition: {type: "boolean"}
      then_value: {type: "any"}
      else_value: {type: "any"}
      
  - name: "SWITCH"
    category: "logic"
    description: "多分支判断"
    parameters:
      value: {type: "any"}
      cases: {type: "array"}
      default: {type: "any"}
      
  - name: "AND"
    category: "logic"
    description: "逻辑与"
    parameters:
      conditions: {type: "array", item_type: "boolean"}
      
  - name: "OR"
    category: "logic"
    description: "逻辑或"
    parameters:
      conditions: {type: "array", item_type: "boolean"}
      
  - name: "NOT"
    category: "logic"
    description: "逻辑非"
    parameters:
      condition: {type: "boolean"}

  # ========== 比较算子 ==========
  - name: "GT"
    category: "comparison"
    description: "大于"
    parameters:
      left: {type: "number"}
      right: {type: "number"}
      
  - name: "GTE"
    category: "comparison"
    description: "大于等于"
    parameters:
      left: {type: "number"}
      right: {type: "number"}
      
  - name: "LT"
    category: "comparison"
    description: "小于"
    parameters:
      left: {type: "number"}
      right: {type: "number"}
      
  - name: "LTE"
    category: "comparison"
    description: "小于等于"
    parameters:
      left: {type: "number"}
      right: {type: "number"}
      
  - name: "EQ"
    category: "comparison"
    description: "等于"
    parameters:
      left: {type: "any"}
      right: {type: "any"}
      
  - name: "IN"
    category: "comparison"
    description: "包含于"
    parameters:
      value: {type: "any"}
      collection: {type: "array"}

  # ========== 评分卡算子 ==========
  - name: "SCORECARD"
    category: "scoring"
    description: "评分卡模型"
    parameters:
      features: {type: "object"}      # 特征键值对
      scorecard_id: {type: "string"}  # 评分卡配置ID
      version: {type: "string"}       # 版本号
      
  - name: "BINNING"
    category: "scoring"
    description: "分箱转换"
    parameters:
      value: {type: "number"}
      bins: {type: "array"}           # 分箱边界
      scores: {type: "array"}         # 各箱分数
      
  - name: "WOE"
    category: "scoring"
    description: "WOE编码"
    parameters:
      value: {type: "any"}
      woe_map: {type: "object"}       # WOE映射表

  # ========== 逻辑树算子 ==========
  - name: "DECISION_TREE"
    category: "decision"
    description: "决策树"
    parameters:
      tree_id: {type: "string"}       # 决策树配置ID
      inputs: {type: "object"}        # 输入特征
      
  - name: "RULE_CHAIN"
    category: "decision"
    description: "规则链"
    parameters:
      rules: {type: "array"}          # 规则列表
      mode: {type: "enum", values: ["first_match", "all_match"]}
      
  - name: "LOOKUP_TABLE"
    category: "decision"
    description: "查表"
    parameters:
      table_id: {type: "string"}      # 查找表ID
      key: {type: "any"}              # 查找键
      default: {type: "any"}          # 默认值

  # ========== 图计算算子 ==========
  - name: "GRAPH_TRAVERSE"
    category: "graph"
    description: "图遍历"
    parameters:
      start_node: {type: "string"}
      edge_type: {type: "string"}
      direction: {type: "enum", values: ["out", "in", "both"]}
      max_depth: {type: "integer"}
      
  - name: "GRAPH_PATH"
    category: "graph"
    description: "路径查询"
    parameters:
      from_node: {type: "string"}
      to_node: {type: "string"}
      edge_types: {type: "array"}
      algorithm: {type: "enum", values: ["shortest", "all", "longest"]}
      
  - name: "GRAPH_CENTRALITY"
    category: "graph"
    description: "中心性计算"
    parameters:
      node_id: {type: "string"}
      algorithm: {type: "enum", values: ["degree", "betweenness", "pagerank"]}
      
  - name: "GRAPH_COMMUNITY"
    category: "graph"
    description: "社区发现"
    parameters:
      node_id: {type: "string"}
      algorithm: {type: "enum", values: ["louvain", "label_propagation"]}

  # ========== 时间序列算子 ==========
  - name: "TIME_WINDOW"
    category: "timeseries"
    description: "时间窗口聚合"
    parameters:
      values: {type: "array"}         # 时序数据
      window: {type: "string"}        # 窗口大小，如 "90d", "12m"
      agg_func: {type: "enum", values: ["sum", "avg", "max", "min", "count"]}
      
  - name: "TIME_LAG"
    category: "timeseries"
    description: "滞后值"
    parameters:
      values: {type: "array"}
      lag: {type: "integer"}
      
  - name: "GROWTH_RATE"
    category: "timeseries"
    description: "增长率"
    parameters:
      current_value: {type: "number"}
      previous_value: {type: "number"}
      periods: {type: "integer"}      # 周期数

  # ========== 外部模型算子 ==========
  - name: "EXTERNAL_API"
    category: "external"
    description: "外部API调用"
    parameters:
      endpoint: {type: "string"}      # API地址
      method: {type: "enum", values: ["GET", "POST"]}
      headers: {type: "object"}
      body: {type: "object"}
      timeout: {type: "integer"}
      
  - name: "ML_MODEL"
    category: "external"
    description: "机器学习模型"
    parameters:
      model_id: {type: "string"}      # 模型ID
      model_version: {type: "string"} # 模型版本
      features: {type: "object"}      # 特征输入
      endpoint: {type: "string"}      # 推理端点
      
  - name: "LLM_INFERENCE"
    category: "external"
    description: "大模型推理"
    parameters:
      prompt: {type: "string"}
      model: {type: "string"}
      temperature: {type: "number"}
      max_tokens: {type: "integer"}

# ============================================================
# 规则定义
# ============================================================
rules:
  # ----------------------------------------------------------
  # 规则1: 担保比例计算
  # ----------------------------------------------------------
  - id: "R001_guarantee_ratio"
    name: "担保比例计算"
    description: "计算对外担保占净资产的比例"
    category: "derived_metric"
    priority: 100
    
    # 输入声明
    inputs:
      - name: "total_guarantee_out"
        from: "input"                # 来自外部输入
      - name: "net_asset"
        from: "input"
        
    # 计算逻辑
    compute:
      operator: "DIV"
      parameters:
        dividend: "${total_guarantee_out}"
        divisor: "${net_asset}"
        
    # 输出
    outputs:
      - name: "guarantee_ratio"
        type: "decimal"
        
    # 异常处理
    on_error:
      division_by_zero:
        action: "return_default"
        value: 0

  # ----------------------------------------------------------
  # 规则2: 资本充足度评分
  # ----------------------------------------------------------
  - id: "R002_capital_score"
    name: "资本充足度评分"
    description: "根据资本充足率计算得分"
    category: "scoring"
    priority: 90
    
    inputs:
      - name: "capital_adequacy_ratio"
        from: "input"
        required: false
        default: null
        
    compute:
      operator: "IF"
      parameters:
        condition:
          operator: "EQ"
          parameters:
            left: "${capital_adequacy_ratio}"
            right: null
        then_value: 50  # 数据缺失时给中等分数
        else_value:
          operator: "SCORECARD"
          parameters:
            scorecard_id: "capital_adequacy_scorecard_v1"
            features:
              value: "${capital_adequacy_ratio}"
              
    outputs:
      - name: "capital_score"
        type: "decimal"
        range: [0, 100]

  # ----------------------------------------------------------
  # 规则3: 担保风险评分
  # ----------------------------------------------------------
  - id: "R003_guarantee_score"
    name: "担保风险评分"
    description: "根据担保比例和担保链深度计算得分"
    category: "scoring"
    priority: 90
    
    inputs:
      - name: "guarantee_ratio"
        from: "rule"                 # 来自其他规则的输出
        rule_id: "R001_guarantee_ratio"
      - name: "guarantee_chain_depth"
        from: "input"
        
    compute:
      operator: "RULE_CHAIN"
      parameters:
        mode: "first_match"
        rules:
          # 规则链1: 担保比例超高危
          - condition:
              operator: "OR"
              parameters:
                conditions:
                  - operator: "GTE"
                    parameters:
                      left: "${guarantee_ratio}"
                      right: 0.8
                  - operator: "GTE"
                    parameters:
                      left: "${guarantee_chain_depth}"
                      right: 5
            output: 20
            
          # 规则链2: 担保比例高危
          - condition:
              operator: "GTE"
              parameters:
                left: "${guarantee_ratio}"
                right: 0.5
            output: 40
            
          # 规则链3: 担保比例中等
          - condition:
              operator: "GTE"
              parameters:
                left: "${guarantee_ratio}"
                right: 0.3
            output: 60
            
          # 默认
          - condition: true
            output: 80
            
    outputs:
      - name: "guarantee_score"
        type: "decimal"

  # ----------------------------------------------------------
  # 规则4: 交易稳定性评分
  # ----------------------------------------------------------
  - id: "R004_trading_score"
    name: "交易稳定性评分"
    description: "根据交易活跃度和高风险敞口计算得分"
    category: "scoring"
    priority: 90
    
    inputs:
      - name: "trading_intensity"
        from: "intermediate_metric"
      - name: "high_risk_exposure_ratio"
        from: "intermediate_metric"
        
    compute:
      operator: "ADD"
      parameters:
        operands:
          # 基础分
          - 50
          # 交易活跃度加分
          - operator: "IF"
            parameters:
              condition:
                operator: "AND"
                parameters:
                  conditions:
                    - operator: "GT"
                      parameters:
                        left: "${trading_intensity}"
                        right: 0.5
                    - operator: "LTE"
                      parameters:
                        left: "${trading_intensity}"
                        right: 2.0
              then_value: 20
              else_value: 0
          # 高风险敞口扣分
          - operator: "MUL"
            parameters:
              factors:
                - -30
                - "${high_risk_exposure_ratio}"
                
    outputs:
      - name: "trading_score"
        type: "decimal"

  # ----------------------------------------------------------
  # 规则5: 声誉风险评分
  # ----------------------------------------------------------
  - id: "R005_reputation_score"
    name: "声誉风险评分"
    description: "根据负面舆情计算得分"
    category: "scoring"
    priority: 90
    
    inputs:
      - name: "negative_news_count_30d"
        from: "input"
      - name: "negative_news_sentiment_score"
        from: "input"
        
    compute:
      operator: "MAX"
      parameters:
        values:
          - 100  # 最高分
          - operator: "SUB"
            parameters:
              minuend: 100
              subtrahend:
                operator: "ADD"
                parameters:
                  operands:
                    # 负面新闻数量扣分
                    - operator: "MUL"
                      parameters:
                        factors:
                          - "${negative_news_count_30d}"
                          - 5
                    # 情感得分扣分
                    - operator: "MUL"
                      parameters:
                        factors:
                          - "${negative_news_sentiment_score}"
                          - -10
                          
    outputs:
      - name: "reputation_score"
        type: "decimal"

  # ----------------------------------------------------------
  # 规则6: 综合风险评分
  # ----------------------------------------------------------
  - id: "R006_comprehensive_risk_score"
    name: "综合风险评分"
    description: "多维度加权综合评分"
    category: "composite"
    priority: 80
    
    inputs:
      - name: "capital_score"
        from: "rule"
        rule_id: "R002_capital_score"
      - name: "guarantee_score"
        from: "rule"
        rule_id: "R003_guarantee_score"
      - name: "trading_score"
        from: "rule"
        rule_id: "R004_trading_score"
      - name: "reputation_score"
        from: "rule"
        rule_id: "R005_reputation_score"
        
    compute:
      operator: "ADD"
      parameters:
        operands:
          - operator: "MUL"
            parameters:
              factors: ["${capital_score}", 0.25]
          - operator: "MUL"
            parameters:
              factors: ["${guarantee_score}", 0.25]
          - operator: "MUL"
            parameters:
              factors: ["${trading_score}", 0.25]
          - operator: "MUL"
            parameters:
              factors: ["${reputation_score}", 0.25]
              
    outputs:
      - name: "risk_score"
        type: "decimal"

  # ----------------------------------------------------------
  # 规则7: 风险等级判定
  # ----------------------------------------------------------
  - id: "R007_risk_grade"
    name: "风险等级判定"
    description: "根据综合评分判定风险等级"
    category: "decision"
    priority: 70
    
    inputs:
      - name: "risk_score"
        from: "rule"
        rule_id: "R006_comprehensive_risk_score"
        
    compute:
      operator: "SWITCH"
      parameters:
        value: "${risk_score}"
        cases:
          - condition:
              operator: "GTE"
              parameters:
                left: "${risk_score}"
                right: 85
            output:
              risk_grade: "A"
              cooperation_strategy: "expand"
              
          - condition:
              operator: "GTE"
              parameters:
                left: "${risk_score}"
                right: 70
            output:
              risk_grade: "B"
              cooperation_strategy: "maintain"
              
          - condition:
              operator: "GTE"
              parameters:
                left: "${risk_score}"
                right: 55
            output:
              risk_grade: "C"
              cooperation_strategy: "monitor"
              
          - condition:
              operator: "GTE"
              parameters:
                left: "${risk_score}"
                right: 40
            output:
              risk_grade: "D"
              cooperation_strategy: "restrict"
              
        default:
          risk_grade: "E"
          cooperation_strategy: "prohibit"
          
    outputs:
      - name: "risk_grade"
        type: "enum"
      - name: "cooperation_strategy"
        type: "enum"

  # ----------------------------------------------------------
  # 规则8: 预警生成
  # ----------------------------------------------------------
  - id: "R008_alert_generation"
    name: "预警生成"
    description: "根据阈值触发预警"
    category: "alert"
    priority: 60
    
    inputs:
      - name: "guarantee_ratio"
        from: "rule"
        rule_id: "R001_guarantee_ratio"
      - name: "capital_adequacy_ratio"
        from: "input"
      - name: "risk_grade"
        from: "rule"
        rule_id: "R007_risk_grade"
        
    compute:
      operator: "RULE_CHAIN"
      parameters:
        mode: "all_match"
        rules:
          # 预警1: 资本充足率预警
          - condition:
              operator: "LT"
              parameters:
                left: "${capital_adequacy_ratio}"
                right: 0.08
            output:
              alert_level: "critical"
              alert_message: "资本充足率低于8%监管红线"
              
          # 预警2: 担保比例预警
          - condition:
              operator: "GTE"
              parameters:
                left: "${guarantee_ratio}"
                right: 0.8
            output:
              alert_level: "critical"
              alert_message: "对外担保比例超过80%"
              
          # 预警3: 风险等级预警
          - condition:
              operator: "IN"
              parameters:
                left: "${risk_grade}"
                right: ["D", "E"]
            output:
              alert_level: "warning"
              alert_message: "风险等级为${risk_grade}"
              
    outputs:
      - name: "alert_level"
        type: "enum"
      - name: "alert_messages"
        type: "array"

  # ----------------------------------------------------------
  # 规则9: 外部模型调用示例
  # ----------------------------------------------------------
  - id: "R009_ml_risk_prediction"
    name: "ML风险预测"
    description: "调用外部机器学习模型进行风险预测"
    category: "external"
    priority: 50
    
    inputs:
      - name: "entity_id"
        from: "input"
      - name: "net_asset"
        from: "input"
      - name: "total_asset"
        from: "input"
      - name: "guarantee_ratio"
        from: "rule"
        rule_id: "R001_guarantee_ratio"
        
    compute:
      operator: "ML_MODEL"
      parameters:
        model_id: "counterparty_risk_model_v2"
        model_version: "2.1.0"
        endpoint: "https://ml-platform.example.com/predict"
        features:
          entity_id: "${entity_id}"
          net_asset: "${net_asset}"
          total_asset: "${total_asset}"
          leverage_ratio:
            operator: "DIV"
            parameters:
              dividend: "${total_asset}"
              divisor: "${net_asset}"
          guarantee_ratio: "${guarantee_ratio}"
          
    outputs:
      - name: "ml_risk_probability"
        type: "decimal"
      - name: "ml_risk_factors"
        type: "array"
        
    # 外部调用异常处理
    on_error:
      timeout:
        action: "skip"
        log_level: "WARN"
      connection_error:
        action: "fallback"
        fallback_value:
          ml_risk_probability: null
          ml_risk_factors: []

  # ----------------------------------------------------------
  # 规则10: 图计算示例
  # ----------------------------------------------------------
  - id: "R010_guarantee_network_analysis"
    name: "担保网络分析"
    description: "分析实体在担保网络中的位置风险"
    category: "graph"
    priority: 50
    
    inputs:
      - name: "entity_id"
        from: "input"
        
    compute:
      operator: "GRAPH_CENTRALITY"
      parameters:
        node_id: "${entity_id}"
        algorithm: "pagerank"
        
    outputs:
      - name: "network_centrality_score"
        type: "decimal"
        
    # 后处理：归一化到0-100
    post_process:
      operator: "MUL"
      parameters:
        factors:
          - "${network_centrality_score}"
          - 100
