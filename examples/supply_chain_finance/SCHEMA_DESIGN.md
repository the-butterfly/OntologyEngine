# Schema 设计深度分析

## 一、设计哲学：图谱Schema+实例的管理逻辑

### 1.1 核心洞察

在金融风控场景中，**同一实体在不同业务场景下需要不同的分析视角和计算逻辑**。

```
传统方式：
Supplier实体 + 一堆属性（无法区分场景）

KGML方式：
Supplier实体 
  ├── 基础属性（所有场景通用）
  ├── credit_assessment维度属性（融资授信场景）
  ├── transaction_monitoring维度属性（交易监控场景）
  └── risk_early_warning维度属性（风险预警场景）
```

### 1.2 维度上下文设计

```yaml
# 维度定义
rule_dimensions:
  dimensions:
    - name: "credit_assessment"
      description: "融资授信评估维度"
      applicable_entities: ["Supplier"]
      triggers:
        - event: "financing_application_submitted"
        - event: "credit_review_scheduled"

# 维度特定属性
concepts:
  - name: "Supplier"
    dimension_attributes:
      credit_assessment:
        - name: "credit_limit_recommendation"
          description: "仅在融资授信场景下计算的推荐额度"
        - name: "financing_eligibility"
          description: "仅在融资授信场景下判断的融资资格"
```

**价值**：
- 场景隔离：不同业务场景的计算逻辑互不干扰
- 按需计算：仅在激活的维度下计算派生属性
- 规则归属：规则明确归属到特定维度，避免冲突

---

## 二、指标体系：三层架构

### 2.1 原子指标（Atomic）

**定义**：直接来自数据源，不可再分的原始数据

```yaml
metrics:
  - name: "total_invoice_amount_90d"
    description: "近90天发票总金额"
    metric_type: "atomic"
    data_source:
      type: "graph"
      query: "MATCH (s:Supplier)-[:has_invoice]->(i:Invoice) WHERE ... RETURN sum(...)"
```

**特点**：
- 直接查询获得
- 作为计算的输入
- 可追溯至原始数据

### 2.2 派生指标（Derived）

**定义**：由原子指标通过公式计算得出

```yaml
metrics:
  - name: "overdue_invoice_ratio"
    description: "逾期发票占比"
    metric_type: "derived"
    formula: "overdue_invoice_amount.value / total_invoice_amount_90d.value * 100"
    dependencies: ["overdue_invoice_amount", "total_invoice_amount_90d"]
```

**计算链路**：
```
原子指标A + 原子指标B → 派生指标C
  15万(逾期) + 1245万(总额) → 1.2%(逾期率)
```

**特点**：
- 有明确的计算公式
- 依赖原子指标
- 可自动重算

### 2.3 复合指标（Composite）

**定义**：多维度加权聚合的评分指标

```yaml
metrics:
  - name: "credit_score"
    description: "综合信用评分"
    metric_type: "composite"
    components:
      - metric: "business_stability_score"  weight: 0.30
      - metric: "tax_compliance_score"      weight: 0.25
      - metric: "reputation_score"          weight: 0.25
      - metric: "guarantee_risk_score"      weight: 0.20
    formula: "SUM(component_score * weight)"
```

**计算链路**：
```
业务稳定性(80) * 30% = 24
税务合规(85)   * 25% = 21.25
声誉风险(97)   * 25% = 24.4
担保风险(70)   * 20% = 14
─────────────────────────────
综合信用评分 = 83.65
```

**特点**：
- 多维度融合
- 权重可配置
- 结果标准化

### 2.4 图算法指标（Graph）

**定义**：基于图结构计算的指标

```yaml
metrics:
  - name: "guarantee_chain_depth"
    description: "担保链深度"
    metric_type: "graph"
    algorithm: "longest_path"
    graph_query: |
      MATCH path = (s:Supplier)-[:guarantees_for|guaranteed_by*1..10]-(other:Supplier)
      RETURN MAX(LENGTH(path)) AS max_depth
```

**计算链路**：
```
担保关系图:
  A --guarantees_for--> B --guarantees_for--> C
  
对于A：担保链深度 = 2
```

**特点**：
- 利用图结构信息
- 支持图算法（PageRank、社区发现等）
- 发现隐藏风险（如担保圈）

---

## 三、规则引擎：声明式规则定义

### 3.1 规则类型

| 类型 | 说明 | 示例 |
|------|------|------|
| constraint | 约束规则 | 准入检查 |
| inference | 推理规则 | 信用评分计算 |
| alert | 预警规则 | 担保圈检测 |
| decision | 决策规则 | 最终授信决策 |

### 3.2 规则结构

```yaml
rules:
  - id: "R001_basic_eligibility"
    name: "基础准入检查"
    type: "constraint"
    priority: 100
    
    # 规则作用域
    scope:
      dimensions: ["credit_assessment"]
      entity_types: ["Supplier"]
    
    # 触发条件
    when:
      allOf:
        - expression: "status == 'ACTIVE'"
        - expression: "registered_capital.value >= 1000000"
    
    # 执行动作
    then:
      action: "approve_eligibility"
      output:
        eligible: true
    
    # 否则
    else:
      action: "reject_eligibility"
      output:
        eligible: false
        rejection_reason: "不符合基础准入条件"
```

### 3.3 规则链执行

```
输入原子指标
     ↓
R001 基础准入检查 ──不通过──→ 拒绝
     ↓ 通过
R002 信用评分计算
     ↓
R003 担保圈检测 ────发现────→ 预警
     ↓
R004 授信额度计算
     ↓
R005 风险预警检查 ──触发────→ 预警
     ↓
R006 利率定价
     ↓
R007 综合授信决策
     ↓
输出授信结果
```

### 3.4 图查询规则

```yaml
rules:
  - id: "R003_guarantee_circle_detection"
    name: "担保圈风险检测"
    type: "alert"
    
    when:
      # 图查询条件
      graph_query: |
        MATCH cycle = (s:Supplier {supplier_id: $supplier_id})
                      -[:guarantees_for|guaranteed_by*3..10]-(s)
        RETURN count(cycle) > 0 AS has_cycle
    
    then:
      action: "trigger_alert"
      output:
        alert_level: "critical"
        alert_type: "guarantee_circle_detected"
```

**优势**：
- 直接在图数据上执行复杂查询
- 支持路径分析、模式匹配
- 发现传统SQL难以识别的风险

---

## 四、计算图与依赖解析

### 4.1 依赖关系图

```
                    ┌─────────────────────┐
                    │   credit_score      │
                    │    (复合指标)        │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│business_stability│  │reputation_score │  │guarantee_risk  │
│   (派生指标)     │  │   (派生指标)     │  │   (派生指标)    │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│total_invoice    │  │negative_news    │  │guarantee_chain  │
│invoice_count    │  │overdue_ratio    │  │   (图算法)      │
│contract_amount  │  │                 │  │                 │
│  (原子指标)      │  │  (原子指标)      │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 4.2 拓扑排序执行

```python
# 依赖解析器自动构建DAG并拓扑排序
execution_order = [
    # 第一层：原子指标
    "total_invoice_amount_90d",
    "invoice_count_90d",
    "overdue_invoice_amount",
    "total_contract_amount",
    "negative_news_count_90d",
    
    # 第二层：派生指标
    "overdue_invoice_ratio",
    "avg_invoice_amount",
    "contract_utilization_rate",
    "business_stability_score",
    "reputation_score",
    "guarantee_chain_depth",
    "guarantee_risk_score",
    
    # 第三层：复合指标
    "credit_score",
    "credit_grade",
]
```

---

## 五、Schema 与实例分离

### 5.1 设计原则

```
Schema层（schema.yaml）：定义"类"
  ├── Concept定义
  ├── Attribute定义
  ├── Metric定义
  ├── Rule定义
  └── 业务逻辑

实例层（instances.yaml）：定义"对象"
  ├── 具体实体数据
  ├── 关系实例
  └── 激活的维度标记
```

### 5.2 优势

1. **Schema复用**：同一Schema可应用于多个实例集
2. **版本管理**：Schema变更不影响历史实例
3. **多租户**：不同租户共享Schema，隔离实例
4. **权限控制**：Schema层控制元数据权限，实例层控制数据权限

### 5.3 维度激活

```yaml
# 实例层标记激活的维度
instances:
  - concept: "Supplier"
    data:
      - supplier_id: "SUP_2024_001"
        company_name: "深圳智造科技"
        # 标记激活的分析维度
        active_dimensions:
          - "credit_assessment"
          # - "transaction_monitoring"  # 未激活
          # - "aml_monitoring"          # 未激活
```

---

## 六、多策略计算

### 6.1 指标计算策略回退

```yaml
metrics:
  - name: "customer_lifetime_value"
    description: "客户终身价值"
    
    calculation:
      # 多策略聚合模式
      aggregation_mode: "fallback"  # fallback | parallel | weighted
      
      strategies:
        # 策略1：图计算（首选）
        - priority: 1
          type: "graph"
          language: "cypher"
          query: "MATCH ... RETURN ..."
          confidence: 0.9
        
        # 策略2：SQL计算（备选）
        - priority: 2
          type: "sql"
          query: "SELECT ... FROM ..."
          confidence: 0.85
        
        # 策略3：LLM估算（最后备选）
        - priority: 3
          type: "llm"
          model: "gpt-4o"
          prompt: "估算客户终身价值..."
          confidence: 0.7
```

### 6.2 派生属性多策略计算

```yaml
concepts:
  - name: "Supplier"
    attributes:
      - name: "credit_score"
        derived: true
        calculation:
          type: "multi_strategy"
          fallback_mode: "sequential"
          
          strategies:
            # 策略1：本地表达式（最快）
            - priority: 1
              type: "formula"
              engine: "local"
              expression: "..."
            
            # 策略2：图查询
            - priority: 2
              type: "graph"
              language: "cypher"
              query: "..."
            
            # 策略3：外部API
            - priority: 3
              type: "remote"
              service: "credit-scoring-service"
```

---

## 七、设计对比

### 7.1 与传统风控系统的对比

| 特性 | 传统系统 | KGML方案 |
|------|---------|---------|
| 指标定义 | 代码硬编码 | Schema声明式 |
| 指标依赖 | 手动管理 | 自动构建DAG |
| 图关系利用 | 有限 | 原生支持 |
| 规则引擎 | 独立系统 | 与图谱集成 |
| 维度隔离 | 数据库表隔离 | 维度上下文标记 |
| 可解释性 | 弱 | 强（计算链路可追溯）|
| 扩展性 | 需改代码 | 改配置即可 |

### 7.2 与通用知识图谱的对比

| 特性 | 通用KG | KGML Schema |
|------|--------|-------------|
| 属性计算 | 静态 | 动态派生 |
| 业务规则 | 无 | 声明式规则 |
| 指标定义 | 无 | 完整指标体系 |
| 维度上下文 | 无 | 核心特性 |
| 计算图 | 无 | 自动构建DAG |

---

## 八、MVP案例验证

### 8.1 案例设计

| 案例 | 设计意图 | 验证点 |
|------|---------|--------|
| 案例1（优质供应商） | 正常场景 | 准入通过、正常授信、无预警 |
| 案例2（高风险供应商） | 风险场景 | 风险识别、额度限制、预警触发 |
| 案例3（担保圈供应商） | 图算法场景 | 担保圈检测、风险调整、有条件授信 |

### 8.2 验证结果

```
案例1: 深圳智造科技
  - 准入检查: 通过 ✓
  - 信用评分: 83分 (AA级)
  - 授信额度: 3375万
  - 风险预警: 无 ✓
  - 决策: APPROVE ✓

案例2: 某贸易公司
  - 准入检查: 通过（刚好过线）
  - 信用评分: 48分 (CCC级)
  - 授信额度: 30万（严格限制）
  - 风险预警: 逾期率80%、信用分不足、负面新闻 ✓
  - 决策: APPROVE_RESTRICTED ✓

案例3: 供应商A（担保圈）
  - 准入检查: 通过
  - 担保圈检测: 发现A→B→C→A循环 ✓
  - 信用评分: 71分（因担保风险降至20分）
  - 授信额度: 420万（较正常情况降低）
  - 风险预警: 担保圈风险 ✓
  - 决策: APPROVE_WITH_CONDITIONS ✓
```

---

## 九、扩展方向

### 9.1 更多分析维度

```yaml
rule_dimensions:
  - name: "aml_monitoring"
    description: "反洗钱监控维度"
    applicable_entities: ["Supplier", "Transaction"]
  
  - name: "fraud_detection"
    description: "欺诈检测维度"
    applicable_entities: ["Invoice", "Transaction"]
  
  - name: "supply_chain_optimization"
    description: "供应链优化维度"
    applicable_entities: ["Supplier", "CoreEnterprise"]
```

### 9.2 更多计算策略

- **机器学习模型算子**：集成XGBoost、神经网络模型
- **时序分析算子**：ARIMA、Prophet预测
- **知识图谱推理算子**：基于本体推理的规则

### 9.3 实时计算

```yaml
metrics:
  - name: "realtime_risk_score"
    realtime: true
    calculation:
      type: "stream"
      source: "kafka"
      processing:
        window:
          type: "sliding"
          size_seconds: 300
```

---

## 十、总结

本Schema设计实现了：

1. **完整的指标体系**：原子→派生→复合→图算法
2. **维度上下文**：同一实体多场景分析
3. **声明式规则**：YAML定义业务逻辑
4. **自动依赖解析**：DAG构建与拓扑排序
5. **图谱原生集成**：图查询、图算法
6. **多策略回退**：高可用计算

验证通过MVP案例证明该设计可以有效支撑供应链金融授信评估场景。
