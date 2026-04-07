# 金融知识图谱优化设计方案

## 设计原则

1. **渐进式落地** - 先跑通核心链路，再扩展高级特性
2. **技术债务最小化** - 优先使用成熟开源组件，避免自研DSL
3. **可解释优先** - 金融场景必须100%可追溯
4. **成本可控** - 明确每层的计算成本和存储成本

---

## 一、整体架构（简化版）

```
┌─────────────────────────────────────────────────────────────────┐
│                        应用层 (Application)                      │
│  风险评估 | 合规检查 | 反洗钱 | 客户画像 | 监管报送              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     服务网关 (API Gateway)                       │
│  REST API | GraphQL | gRPC | 事件订阅                           │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  指标计算引擎  │     │  规则引擎     │     │  查询引擎     │
│  (核心模块)   │     │  (核心模块)   │     │  (核心模块)   │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     知识图谱存储层                               │
│  Neo4j/TuGraph (属性图) + PostgreSQL (关系型) + Redis (缓存)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     本体/Schema层                               │
│  LinkML Schema + JSON-LD Context + 版本管理                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、本体与知识图谱连接设计

### 2.1 简化的本体层次

```
┌─────────────────────────────────────────────────────────────────┐
│ L0 顶层本体 (复用标准)                                          │
│ - schema.org (基础实体类型)                                     │
│ - FIBO (金融行业本体，可选引入)                                 │
└─────────────────────────────────────────────────────────────────┘
        │ 继承
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ L1 领域本体 (行业标准)                                          │
│ - 金融机构 (银行/证券/保险/基金...)                             │
│ - 金融产品 (贷款/债券/衍生品...)                                │
│ - 风险类型 (信用/市场/流动性/操作...)                           │
└─────────────────────────────────────────────────────────────────┘
        │ 继承
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ L2 业务本体 (机构定制)                                          │
│ - 具体产品类型、业务流程、审批节点                              │
│ - 可动态扩展，不影响L0/L1                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 LinkML Schema 定义（示例）

```yaml
# schema/finance.yaml
id: https://example.org/finance/kg
name: FinanceKnowledgeGraph
prefixes:
  finance: https://example.org/finance/
  schema: http://schema.org/
  fibo: https://spec.edmcouncil.org/fibo/ontology/

classes:
  
  # ========== 基础实体 ==========
  FinancialEntity:
    description: "金融实体基类"
    abstract: true
    slots:
      - entityId
      - legalName
      - unifiedCode          # 统一社会信用代码
      - status
      - createdAt
      - updatedAt
    
  Counterparty:
    is_a: FinancialEntity
    description: "交易对手"
    slots:
      - institutionType      # 机构类型
      - riskGrade           # 风险等级
      - netAsset            # 净资产
      - capitalAdequacyRatio # 资本充足率
      - registrationInfo    # 注册信息(嵌套)
    slot_usage:
      entityId:
        identifier: true
        
  # ========== 嵌套对象 ==========
  RegistrationInfo:
    description: "注册信息"
    attributes:
      licenseNo:
        range: string
      regulator:
        range: string
      licenseType:
        range: LicenseTypeEnum
      validFrom:
        range: date
      validTo:
        range: date
        
  # ========== 关系定义 ==========
  GuaranteeRelation:
    description: "担保关系"
    slots:
      - guarantorId          # 担保方
      - guaranteedId         # 被担保方
      - guaranteeAmount      # 担保金额
      - guaranteeType        # 担保类型
      - guaranteeRatio       # 担保比例
      - startDate
      - endDate
      - contractNo           # 合同编号
      - dataQuality          # 数据质量评分

  TransactionRelation:
    description: "交易关系"
    slots:
      - buyerId
      - sellerId
      - productType
      - amount
      - currency
      - transactionDate
      - settlementDate

slots:
  entityId:
    range: string
    identifier: true
    required: true
    
  riskGrade:
    range: RiskGradeEnum
    description: "风险等级 A-E"
    
  netAsset:
    range: decimal
    unit: CNY
    
  capitalAdequacyRatio:
    range: decimal
    description: "资本充足率，小数表示"

enums:
  RiskGradeEnum:
    permissible_values:
      A: "优秀"
      B: "良好"
      C: "一般"
      D: "较差"
      E: "极差"
      
  LicenseTypeEnum:
    permissible_values:
      SECURITIES_BUSINESS: "证券业务许可"
      ASSET_MANAGEMENT: "资产管理许可"
      FUTURES_BUSINESS: "期货业务许可"
```

### 2.3 知识图谱存储映射

```python
# 存储映射规则
class StorageMapping:
    """
    本体 → 图数据库映射
    """
    
    # 节点映射
    NODE_MAPPING = {
        "Counterparty": {
            "label": "Counterparty",
            "indexes": ["entityId", "unifiedCode", "legalName"],
            "constraints": ["entityId UNIQUE"]
        },
        "Person": {
            "label": "Person",
            "indexes": ["idCard", "name"]
        }
    }
    
    # 关系映射
    EDGE_MAPPING = {
        "GuaranteeRelation": {
            "type": "GUARANTEES",
            "from": "guarantorId",
            "to": "guaranteedId",
            "properties": ["guaranteeAmount", "guaranteeType", "guaranteeRatio"]
        },
        "TransactionRelation": {
            "type": "TRADES_WITH",
            "from": "buyerId",
            "to": "sellerId",
            "properties": ["amount", "productType", "transactionDate"]
        }
    }
    
    # 时序数据 → 关系型数据库
    TIME_SERIES_MAPPING = {
        "TransactionRecord": {
            "table": "transactions",
            "partition": "transaction_date",
            "retention_days": 3650  # 10年
        }
    }
```

---

## 三、指标计算引擎（核心设计）

### 3.1 指标定义规范

**核心思想：使用 YAML/JSON 声明式定义，不造DSL**

```yaml
# metrics/counterparty_metrics.yaml

metrics:
  
  # ========== 基础指标 ==========
  trading_intensity:
    name: "交易活跃度"
    description: "近90天交易总额/净资产"
    category: "trading"
    formula: "SUM(transactions.amount, window=90d) / net_asset"
    unit: "ratio"
    granularity: "counterparty"
    updateFrequency: "daily"
    dataSource:
      - type: "graph"
        query: "MATCH (cp:Counterparty)-[:TRADES_WITH]->() WHERE cp.entityId = $entityId"
      - type: "relational"
        table: "transactions"
        filter: "counterparty_id = ? AND transaction_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)"
    
  guarantee_ratio:
    name: "对外担保比例"
    description: "对外担保总额/净资产"
    category: "guarantee"
    formula: "SUM(guarantees.amount) / net_asset"
    unit: "ratio"
    riskThreshold:
      warning: 0.5
      critical: 0.8
      
  high_risk_exposure_ratio:
    name: "高风险敞口占比"
    description: "与高风险对手方交易额/总交易额"
    category: "risk"
    formula: |
      SUM(CASE WHEN counterparty.risk_grade IN ('D', 'E') 
               THEN transaction.amount ELSE 0 END) 
      / SUM(transaction.amount)
    dependencies:
      - "counterparty.risk_grade"
      - "transaction.amount"
    
  # ========== 复合指标 ==========
  comprehensive_risk_score:
    name: "综合风险评分"
    description: "多维度加权综合评分"
    category: "scoring"
    type: "composite"
    components:
      - metric: "capital_adequacy_score"
        weight: 0.25
        transform: "min(value / 0.12, 1.0)"  # 标准化到0-1
      - metric: "guarantee_score"
        weight: 0.20
        transform: "max(0, 1 - guarantee_ratio / 0.8)"
      - metric: "trading_stability_score"
        weight: 0.20
        transform: "std_dev_coefficient(last_12_months_trading)"
      - metric: "negative_news_score"
        weight: 0.15
        transform: "sentiment_analysis(news_articles)"
      - metric: "related_party_risk_score"
        weight: 0.20
        transform: "graph_centrality_risk(entity_id)"
    formula: "SUM(component_score * weight)"
    outputRange: [0, 100]
    
  # ========== 图算法指标 ==========
  guarantee_chain_depth:
    name: "担保链深度"
    description: "该主体在担保网络中的最长路径深度"
    category: "graph"
    algorithm: "longest_path"
    graphQuery: |
      MATCH path = (cp:Counterparty {entityId: $entityId})-[:GUARANTEES*1..10]-(other:Counterparty)
      RETURN MAX(LENGTH(path)) AS max_depth
    timeout: 30000  # ms
    
  risk_propagation_score:
    name: "风险传导评分"
    description: "基于网络传播模型的风险传导评估"
    category: "graph"
    algorithm: "debt_rank"  # 或 PageRank 变体
    parameters:
      dampingFactor: 0.85
      maxIterations: 100
      convergenceThreshold: 0.001
```

### 3.2 指标计算引擎实现

```python
# engine/metric_engine.py

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class MetricType(Enum):
    SIMPLE = "simple"          # 简单聚合
    COMPOSITE = "composite"    # 复合计算
    GRAPH = "graph"           # 图算法
    TIME_SERIES = "time_series"  # 时序计算

@dataclass
class MetricDefinition:
    """指标定义"""
    id: str
    name: str
    description: str
    category: str
    metric_type: MetricType
    formula: str
    unit: str
    data_source: Dict
    update_frequency: str
    dependencies: List[str] = None
    risk_threshold: Dict = None
    timeout: int = 30000
    
@dataclass
class MetricResult:
    """计算结果"""
    metric_id: str
    entity_id: str
    value: Any
    unit: str
    calculated_at: datetime
    data_sources: List[str]  # 数据来源追溯
    computation_trace: Dict   # 计算过程追溯
    quality_score: float = 1.0  # 数据质量评分

class MetricEngine:
    """
    指标计算引擎
    
    设计原则：
    1. 声明式定义（YAML），不写代码
    2. 自动依赖解析
    3. 计算过程完整追溯
    4. 支持增量更新
    """
    
    def __init__(self, graph_db, rdbms, cache):
        self.graph_db = graph_db       # Neo4j/TuGraph
        self.rdbms = rdbms             # PostgreSQL
        self.cache = cache             # Redis
        self.metric_registry = {}      # 指标注册表
        self.computation_graph = {}    # 计算依赖图
        
    def register_metric(self, definition: MetricDefinition):
        """注册指标定义"""
        self.metric_registry[definition.id] = definition
        self._build_dependency_graph(definition)
        
    def compute(self, metric_id: str, entity_id: str, 
                as_of_date: datetime = None) -> MetricResult:
        """
        计算单个指标
        """
        definition = self.metric_registry.get(metric_id)
        if not definition:
            raise ValueError(f"Metric {metric_id} not registered")
            
        # 1. 检查缓存
        cache_key = f"metric:{metric_id}:{entity_id}:{as_of_date}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
            
        # 2. 检查依赖
        if definition.dependencies:
            dep_results = self._compute_dependencies(
                definition.dependencies, entity_id, as_of_date
            )
        else:
            dep_results = {}
            
        # 3. 执行计算
        if definition.metric_type == MetricType.SIMPLE:
            result = self._compute_simple(definition, entity_id, as_of_date)
        elif definition.metric_type == MetricType.COMPOSITE:
            result = self._compute_composite(definition, dep_results, entity_id)
        elif definition.metric_type == MetricType.GRAPH:
            result = self._compute_graph(definition, entity_id)
        else:
            raise NotImplementedError(f"Type {definition.metric_type} not supported")
            
        # 4. 记录追溯信息
        result.computation_trace = {
            "formula": definition.formula,
            "data_sources": self._get_data_sources(definition),
            "dependencies": dep_results,
            "execution_time_ms": ...,
            "engine_version": "1.0.0"
        }
        
        # 5. 缓存结果
        self.cache.set(cache_key, result, ttl=3600)
        
        return result
        
    def _compute_simple(self, definition: MetricDefinition, 
                        entity_id: str, as_of_date: datetime) -> MetricResult:
        """
        简单指标计算
        """
        data_source = definition.data_source
        
        # 从图数据库查询
        if data_source.get("type") == "graph":
            query = data_source["query"]
            params = {"entityId": entity_id, "asOfDate": as_of_date}
            raw_data = self.graph_db.run(query, params)
            
        # 从关系数据库查询
        elif data_source.get("type") == "relational":
            table = data_source["table"]
            filter_cond = data_source["filter"]
            raw_data = self.rdbms.query(
                f"SELECT * FROM {table} WHERE {filter_cond}",
                [entity_id, as_of_date]
            )
            
        # 执行公式计算
        value = self._evaluate_formula(definition.formula, raw_data)
        
        return MetricResult(
            metric_id=definition.id,
            entity_id=entity_id,
            value=value,
            unit=definition.unit,
            calculated_at=datetime.now(),
            data_sources=[data_source.get("type")]
        )
        
    def _compute_composite(self, definition: MetricDefinition,
                          dep_results: Dict, entity_id: str) -> MetricResult:
        """
        复合指标计算
        """
        components = definition.components
        total_score = 0.0
        
        component_traces = {}
        
        for comp in components:
            metric_id = comp["metric"]
            weight = comp["weight"]
            transform = comp.get("transform", "value")
            
            # 获取依赖指标值
            raw_value = dep_results.get(metric_id, {}).get("value", 0)
            
            # 应用转换函数
            transformed_value = self._apply_transform(transform, raw_value)
            
            # 加权求和
            weighted_score = transformed_value * weight
            total_score += weighted_score
            
            component_traces[metric_id] = {
                "raw_value": raw_value,
                "transform": transform,
                "transformed_value": transformed_value,
                "weight": weight,
                "weighted_score": weighted_score
            }
            
        # 映射到输出范围
        output_range = definition.outputRange
        final_score = total_score * (output_range[1] - output_range[0]) + output_range[0]
        
        return MetricResult(
            metric_id=definition.id,
            entity_id=entity_id,
            value=round(final_score, 2),
            unit="score",
            calculated_at=datetime.now(),
            data_sources=list(component_traces.keys()),
            computation_trace={"components": component_traces}
        )
        
    def _compute_graph(self, definition: MetricDefinition,
                      entity_id: str) -> MetricResult:
        """
        图算法指标计算
        """
        algorithm = definition.algorithm
        graph_query = definition.graph_query
        params = definition.parameters
        timeout = definition.timeout
        
        # 执行图查询
        if algorithm == "longest_path":
            result = self.graph_db.run(graph_query, {"entityId": entity_id})
            value = result[0]["max_depth"] if result else 0
            
        elif algorithm == "debt_rank":
            # 调用图算法库
            value = self._run_debt_rank(entity_id, params)
            
        elif algorithm == "page_rank":
            value = self.graph_db.page_rank(
                start_node=entity_id,
                **params
            )
        else:
            raise NotImplementedError(f"Algorithm {algorithm} not supported")
            
        return MetricResult(
            metric_id=definition.id,
            entity_id=entity_id,
            value=value,
            unit=definition.unit,
            calculated_at=datetime.now(),
            data_sources=["graph_db"]
        )
        
    def batch_compute(self, metric_ids: List[str], 
                     entity_ids: List[str]) -> Dict[str, MetricResult]:
        """
        批量计算
        """
        results = {}
        for metric_id in metric_ids:
            for entity_id in entity_ids:
                key = f"{metric_id}:{entity_id}"
                results[key] = self.compute(metric_id, entity_id)
        return results
        
    def _build_dependency_graph(self, definition: MetricDefinition):
        """构建指标依赖图"""
        if definition.dependencies:
            self.computation_graph[definition.id] = definition.dependencies
            
    def _compute_dependencies(self, dependencies: List[str], 
                             entity_id: str, as_of_date: datetime) -> Dict:
        """计算依赖指标"""
        results = {}
        for dep_id in dependencies:
            if dep_id in self.metric_registry:
                results[dep_id] = self.compute(dep_id, entity_id, as_of_date)
        return results
```

### 3.3 指标计算与知识图谱的集成点

```python
# integration/graph_metric_integration.py

class GraphMetricIntegration:
    """
    指标计算引擎 ↔ 知识图谱 集成层
    
    职责：
    1. 从图数据库抽取计算所需的数据
    2. 将计算结果写回图谱（作为属性或关系）
    3. 触发图谱上的推理规则
    """
    
    def __init__(self, metric_engine: MetricEngine, graph_db):
        self.metric_engine = metric_engine
        self.graph_db = graph_db
        
    def extract_graph_data(self, entity_id: str, 
                          metric_def: MetricDefinition) -> pd.DataFrame:
        """
        从图谱抽取数据供指标计算
        """
        data_source = metric_def.data_source
        
        if data_source.get("type") == "graph":
            query = data_source["query"]
            result = self.graph_db.run(query, {"entityId": entity_id})
            return pd.DataFrame(result)
            
        elif data_source.get("type") == "hybrid":
            # 图谱 + 关系型混合
            graph_data = self._extract_from_graph(entity_id, data_source["graph"])
            relational_data = self._extract_from_rdbms(entity_id, data_source["relational"])
            return pd.merge(graph_data, relational_data, on="entity_id")
            
    def write_back_to_graph(self, result: MetricResult):
        """
        将计算结果写回图谱
        
        方式：
        1. 作为节点属性
        2. 作为独立的关系节点
        3. 触发下游推理
        """
        cypher = """
        MATCH (cp:Counterparty {entityId: $entityId})
        SET cp.{metric_id} = $value,
            cp.{metric_id}_calculated_at = $timestamp,
            cp.{metric_id}_data_quality = $quality
        """
        
        self.graph_db.run(cypher, {
            "entityId": result.entity_id,
            "metric_id": result.metric_id,
            "value": result.value,
            "timestamp": result.calculated_at.isoformat(),
            "quality": result.quality_score
        })
        
        # 触发规则检查
        self._trigger_rules(result)
        
    def _trigger_rules(self, result: MetricResult):
        """
        指标更新后，触发相关规则
        """
        # 例如：风险等级变化触发预警
        if result.metric_id == "comprehensive_risk_score":
            self._check_risk_threshold(result)
```

---

## 四、规则引擎设计（核心设计）

### 4.1 技术选型：使用成熟规则引擎

**推荐方案：**

| 场景 | 推荐引擎 | 理由 |
|------|---------|------|
| Java生态 | Drools | 成熟、企业级、IDE支持好 |
| Python生态 | Pydantic + 业务逻辑 | 简单直接，避免过度设计 |
| 云原生 | Open Policy Agent (OPA) | 统一策略管理，跨语言 |
| 轻量级 | json-rules-engine | JS/TS生态，简单场景 |

**不建议自研DSL的原因：**
- 开发成本高（编译器、调试器、IDE插件）
- 生态缺失（没有现成的工具链）
- 人员培养成本
- 社区支持为零

### 4.2 规则定义规范（基于 YAML + 标准表达式）

```yaml
# rules/counterparty_risk_rules.yaml

ruleset:
  id: counterparty_risk_management
  name: "交易对手风险管理规则集"
  version: "2.1.0"
  effectiveDate: "2024-01-01"
  owner: "risk_management_dept"
  
  # 规则引擎配置
  engine:
    type: "drools"  # 或 "pydantic", "opa"
    conflictResolution: "priority"  # 优先级冲突解决
    executionMode: "forward"  # 前向链推理
    
  # 全局变量
  globals:
    industry_avg_car: 0.105  # 行业平均资本充足率
    risk_free_rate: 0.03
    
  rules:
    
    # ========== 准入规则 ==========
    - id: R001_counterparty_admission
      name: "交易对手准入检查"
      description: "新交易对手准入前的基础资质检查"
      priority: 100
      enabled: true
      
      # 条件（使用标准表达式，不自研DSL）
      when:
        allOf:
          - "entity.status == 'active'"
          - "entity.registration.validTo >= today()"
          - "entity.netAsset > 10000000"  # 净资产 > 1000万
          - "entity.capitalAdequacyRatio >= 0.08"  # 资本充足率 >= 8%
          
      then:
        action: "approve_admission"
        output:
          admission_status: "approved"
          next_review_date: "date_add(today(), interval 1 year)"
          
      onViolation:
        action: "reject_admission"
        output:
          admission_status: "rejected"
          rejection_reason: "不符合准入条件"
          
    # ========== 风险评级规则 ==========
    - id: R002_risk_grade_assignment
      name: "风险等级自动评定"
      description: "根据综合评分自动分配风险等级"
      priority: 90
      enabled: true
      
      when:
        - "metric.comprehensive_risk_score != null"
        
      then:
        action: "assign_risk_grade"
        switch:
          - condition: "metric.comprehensive_risk_score >= 85"
            output:
              risk_grade: "A"
              cooperation_strategy: "优先合作"
              
          - condition: "metric.comprehensive_risk_score >= 70"
            output:
              risk_grade: "B"
              cooperation_strategy: "正常合作"
              
          - condition: "metric.comprehensive_risk_score >= 55"
            output:
              risk_grade: "C"
              cooperation_strategy: "加强监控"
              
          - condition: "metric.comprehensive_risk_score >= 40"
            output:
              risk_grade: "D"
              cooperation_strategy: "限制合作"
              
          - condition: "metric.comprehensive_risk_score < 40"
            output:
              risk_grade: "E"
              cooperation_strategy: "禁止新增业务"
              
    # ========== 预警规则 ==========
    - id: R003_guarantee_ratio_alert
      name: "担保比例预警"
      description: "对外担保比例超过阈值时触发预警"
      priority: 80
      enabled: true
      
      when:
        anyOf:
          - "metric.guarantee_ratio >= 0.5 AND metric.guarantee_ratio < 0.8"
          - "metric.guarantee_ratio >= 0.8"
          
      then:
        action: "trigger_alert"
        switch:
          - condition: "metric.guarantee_ratio >= 0.8"
            output:
              alert_level: "critical"
              alert_message: "对外担保比例超过80%，存在重大风险"
              recommended_action: "立即核查担保链条，评估代偿风险"
              
          - condition: "metric.guarantee_ratio >= 0.5"
            output:
              alert_level: "warning"
              alert_message: "对外担保比例超过50%，需要关注"
              recommended_action: "加强担保关系监控"
              
    # ========== 图结构规则 ==========
    - id: R004_guarantee_chain_check
      name: "担保圈风险检查"
      description: "检测是否存在担保圈（循环担保）"
      priority: 85
      enabled: true
      
      # 使用图查询作为条件
      when:
        graphQuery: |
          MATCH cycle = (cp:Counterparty {entityId: $entityId})-[:GUARANTEES*]->(cp)
          WHERE LENGTH(cycle) >= 3
          RETURN COUNT(cycle) > 0 AS has_cycle
          
      then:
        action: "flag_risk"
        output:
          risk_type: "guarantee_circle"
          risk_level: "high"
          description: "检测到担保圈，可能存在循环担保风险"
          
    # ========== 复合规则 ==========
    - id: R005_comprehensive_risk_decision
      name: "综合风险决策"
      description: "多条件综合判断，生成决策建议"
      priority: 70
      enabled: true
      
      when:
        allOf:
          - "entity.risk_grade IN ['D', 'E']"
          - "metric.guarantee_chain_depth >= 3"
          - "metric.high_risk_exposure_ratio >= 0.3"
          
      then:
        action: "generate_decision"
        output:
          decision: "reject_new_business"
          reasons:
            - "风险等级为{entity.risk_grade}"
            - "担保链深度达到{metric.guarantee_chain_depth}层"
            - "高风险敞口占比{metric.high_risk_exposure_ratio}"
          required_approvals:
            - "risk_director"
            - "senior_management"
```

### 4.3 规则引擎实现（基于 Drools/Pydantic）

```python
# engine/rule_engine.py

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum
import yaml
import jmespath  # JSON查询表达式

class RuleAction(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ALERT = "alert"
    FLAG = "flag"
    ASSIGN = "assign"

@dataclass
class RuleContext:
    """规则执行上下文"""
    entity: Dict              # 实体数据
    metrics: Dict             # 指标计算结果
    graph_data: Dict          # 图谱数据
    historical_decisions: List[Dict]  # 历史决策
    
@dataclass
class RuleResult:
    """规则执行结果"""
    rule_id: str
    triggered: bool
    action: str
    output: Dict
    explanation: str
    execution_trace: Dict

class RuleEngine:
    """
    规则引擎
    
    设计原则：
    1. 使用标准表达式语法（JMESPath、标准比较运算）
    2. 支持图查询条件
    3. 完整的执行追踪
    4. 可插拔的后端（Drools/Pydantic/OPA）
    """
    
    def __init__(self, graph_db, metric_engine):
        self.graph_db = graph_db
        self.metric_engine = metric_engine
        self.rule_registry = {}
        self.execution_history = []
        
    def load_rules(self, yaml_path: str):
        """从YAML文件加载规则"""
        with open(yaml_path) as f:
            ruleset = yaml.safe_load(f)
            
        for rule in ruleset["ruleset"]["rules"]:
            self.rule_registry[rule["id"]] = rule
            
    def execute(self, entity_id: str, 
                rule_ids: List[str] = None) -> List[RuleResult]:
        """
        执行规则
        """
        # 1. 构建上下文
        context = self._build_context(entity_id)
        
        # 2. 获取要执行的规则
        rules_to_execute = (
            [self.rule_registry[rid] for rid in rule_ids]
            if rule_ids else list(self.rule_registry.values())
        )
        
        # 3. 按优先级排序
        rules_to_execute.sort(key=lambda r: r.get("priority", 50), reverse=True)
        
        # 4. 依次执行
        results = []
        for rule in rules_to_execute:
            if not rule.get("enabled", True):
                continue
                
            result = self._execute_rule(rule, context)
            results.append(result)
            
            # 记录执行历史
            self.execution_history.append({
                "timestamp": datetime.now().isoformat(),
                "entity_id": entity_id,
                "rule_id": rule["id"],
                "triggered": result.triggered
            })
            
        return results
        
    def _build_context(self, entity_id: str) -> RuleContext:
        """构建规则执行上下文"""
        # 从图谱获取实体
        entity = self.graph_db.run(
            "MATCH (cp:Counterparty {entityId: $id}) RETURN cp",
            {"id": entity_id}
        )[0]["cp"]
        
        # 获取指标
        metrics = {}
        for metric_id in ["comprehensive_risk_score", "guarantee_ratio", 
                          "high_risk_exposure_ratio", "guarantee_chain_depth"]:
            result = self.metric_engine.compute(metric_id, entity_id)
            metrics[metric_id] = result.value
            
        # 获取历史决策
        history = self.graph_db.run(
            """
            MATCH (cp:Counterparty {entityId: $id})-[:HAS_DECISION]->(d:Decision)
            RETURN d ORDER BY d.timestamp DESC LIMIT 10
            """,
            {"id": entity_id}
        )
        
        return RuleContext(
            entity=entity,
            metrics=metrics,
            graph_data={},
            historical_decisions=history
        )
        
    def _execute_rule(self, rule: Dict, context: RuleContext) -> RuleResult:
        """执行单条规则"""
        rule_id = rule["id"]
        when_conditions = rule["when"]
        
        # 评估条件
        triggered, condition_trace = self._evaluate_conditions(
            when_conditions, context
        )
        
        if triggered:
            # 执行then分支
            then_clause = rule["then"]
            action = then_clause["action"]
            output = self._resolve_output(then_clause.get("output", {}), context)
            explanation = self._generate_explanation(rule, output, context)
        else:
            # 执行else分支（如果有）
            else_clause = rule.get("else", {})
            action = else_clause.get("action", "none")
            output = else_clause.get("output", {})
            explanation = "条件不满足，规则未触发"
            
        return RuleResult(
            rule_id=rule_id,
            triggered=triggered,
            action=action,
            output=output,
            explanation=explanation,
            execution_trace=condition_trace
        )
        
    def _evaluate_conditions(self, conditions: Dict, 
                            context: RuleContext) -> tuple[bool, Dict]:
        """
        评估规则条件
        
        支持的条件类型：
        1. 简单表达式：entity.field > value
        2. 逻辑组合：allOf, anyOf
        3. 图查询：graphQuery
        4. JMESPath表达式
        """
        trace = {}
        
        if "allOf" in conditions:
            results = []
            for cond in conditions["allOf"]:
                result, sub_trace = self._evaluate_single_condition(cond, context)
                results.append(result)
                trace[cond] = result
            return all(results), trace
            
        elif "anyOf" in conditions:
            results = []
            for cond in conditions["anyOf"]:
                result, sub_trace = self._evaluate_single_condition(cond, context)
                results.append(result)
                trace[cond] = result
            return any(results), trace
            
        elif "graphQuery" in conditions:
            # 执行图查询条件
            query = conditions["graphQuery"]
            result = self.graph_db.run(query, {"entityId": context.entity["entityId"]})
            has_result = result[0].get("has_cycle", False) if result else False
            return has_result, {"graphQuery": has_result}
            
        else:
            return self._evaluate_single_condition(conditions, context)
            
    def _evaluate_single_condition(self, condition: str, 
                                   context: RuleContext) -> tuple[bool, Dict]:
        """
        评估单个条件表达式
        
        使用安全的表达式求值，不使用eval()
        """
        # 解析表达式
        # 格式: entity.field op value 或 metric.field op value
        
        import re
        pattern = r"(\w+)\.(\w+)\s*(>=|<=|>|<|==|!=|IN|NOT\s+IN)\s*(.+)"
        match = re.match(pattern, condition.strip())
        
        if not match:
            return False, {"error": f"Invalid condition format: {condition}"}
            
        source, field, operator, value_str = match.groups()
        
        # 获取实际值
        if source == "entity":
            actual_value = context.entity.get(field)
        elif source == "metric":
            actual_value = context.metrics.get(field)
        else:
            actual_value = None
            
        # 解析期望值
        expected_value = self._parse_value(value_str)
        
        # 执行比较
        result = self._compare(actual_value, operator, expected_value)
        
        return result, {
            "condition": condition,
            "actual_value": actual_value,
            "expected_value": expected_value,
            "operator": operator,
            "result": result
        }
        
    def _compare(self, actual, operator: str, expected) -> bool:
        """安全比较"""
        if actual is None:
            return False
            
        ops = {
            ">=": lambda a, b: a >= b,