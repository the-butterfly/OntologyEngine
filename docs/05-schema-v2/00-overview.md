# Schema v2 设计概览

---
status: accepted
phase: phase1
source_of_truth: true
last_verified: 2026-04-12
verified_against: docs-only
related_docs:
  - 00b-semantic-space-architecture.md
  - 01-fact-objects.md
  - 02-categorization.md
  - 03-analytical-elements.md
  - 04-business-logic.md
  - 06-dataset-and-sync.md
  - 08-version-management.md
  - 09-canonical-schema-spec.md
---

> **Status**: v2.0 (with Semantic Space)
> **Date**: 2026-04-12

## 目录

1. [v1 问题回顾](#1-v1-问题回顾)
2. [核心思想：四层分离](#2-核心思想四层分离)
3. [语义空间 (Semantic Space)](#3-语义空间-semantic-space)
4. [四层详解](#4-四层详解)
5. [声明与实例的分离](#5-声明与实例的分离)
6. [Schema v2 vs v1 对比](#6-schema-v2-vs-v1-对比)
7. [演进示例](#7-演进示例)
8. [相关文档](#8-相关文档)

---

## 1. v1 问题回顾

当前 Schema (v1) 的问题：

1. **概念混杂** —— `attributes` 既存事实又存分析结果
2. **规则与数据绑定** —— 规则写死 entity_type，复用性差
3. **维度理解混乱** —— `dimension_attributes` 被误解为存储字段
4. **缺乏分层** —— 事实、分类、要素、逻辑混在一起
5. **缺少顶层容器** —— Schema 和 Instance 分散，缺乏统一管理

## 2. 核心思想：四层分离

**四层分离 + 语义空间容器**：

```
语义空间 (Semantic Space)
    │
    ├── 声明层 (Declarations)
    │   │
    │   ▼
    │   事实对象 (Factual Objects)     ← L1
    │   │
    │   ▼
    │   归类分析 (Categorization)      ← L2
    │   │
    │   ▼
    │   分析要素 (Analytical Elements) ← L3
    │   │
    │   ▼
    │   业务逻辑 (Business Logic)      ← L4
    │
    └── 实例层 (Instances)
        │
        ├── 实体实例 (Entity Instances)
        ├── 分类标签 (Category Tags)
        └── 指标值 (Metric Values)
```

## 3. 语义空间 (Semantic Space)

语义空间是 OntologyEngine 的顶层容器单位。见 [语义空间架构](./00b-semantic-space-architecture.md) 详细说明。

### 3.1 两类语义空间

| 类型 | 用途 | 特点 |
|------|------|------|
| **管理空间 (Management Space)** | 权威数据源 | 完整控制，可编辑，可同步外部数据 |
| **消费视图 (Consumption View)** | 数据消费方 | 只读，授权获得，可聚合多个管理空间 |

### 3.2 空间状态

```
DRAFT → ACTIVE → ARCHIVED
         │
         └──→ PUBLISHED (版本快照)
```

## 4. 四层详解

### L1: 事实对象 (Factual)

**定义**: 客观存在、可观测、可验证的数据

**声明内容**:
- 实体类型定义 (公司、个人、发票)
- 关系类型定义 (担保、交易、归属)
- 属性定义 (名称、类型、是否必需)

**实例内容**:
- 具体的实体数据 (entity_id, attributes, ...)
- 具体的关系数据 (from, to, relation_type, ...)

**特点**:
- 与业务场景无关
- 可直接从数据源同步
- 结构稳定，变化少

### L2: 归类分析 (Categorization)

**声明内容**:
- 分类方案定义 (行业、规模、风险等级)
- 分类值范畴 (制造业、批发零售、大/中/小微)
- 分类规则定义 (如何打标)

**实例内容**:
- 实体的分类标签 (entity_id → category_name = value)

**特点**:
- 基于规则或模型自动打标
- 多维度可叠加
- 随业务定义变化

### L3: 分析要素 (Analytical Elements)

**声明内容**:
- 基础指标定义 (名称、类型、单位)
- 派生指标公式 (如何计算)
- 图指标定义 (算法参数)

**实例内容**:
- 指标计算结果 (entity_id + metric_id → value)
- 可选择缓存或实时计算

**特点**:
- 有明确的计算公式
- 可缓存，可增量更新
- 不同场景可复用

### L4: 业务逻辑 (Business Logic)

**声明内容 (Rule Definition)**:
- 作用对象 (target_objects)
- 输入要素 (input_elements)
- 输出要素 (output_elements)
- 优先级 (priority)

**实例内容 (Rule Logic)**:
- 条件表达式 (when)
- 动作定义 (then_action, else_action)
- 适用条件 (applicable_conditions)

**特点**:
- 高度场景化
- 需声明作用域
- **一个声明可关联多个实例**（不同条件分支）

## 5. 声明与实例的分离

### 5.1 为什么分离

| 好处 | 说明 |
|------|------|
| **复用性** | 一个声明，多个场景实例 |
| **可维护性** | 修改逻辑不影响声明定义 |
| **版本独立** | 声明和逻辑可独立演进 |
| **清晰度** | 结构更易理解 |

### 5.2 规则：声明 vs 实例

**声明 (Rule Definition)**:
```yaml
rule_definition:
  id: R001_credit_check
  name: 信用检查
  target_objects: [Supplier, CoreEnterprise]
  input_elements: [credit_score, overdue_ratio]
  output_elements: [eligible, risk_level]
  priority: 100
```

**实例 (Rule Logic)**:
```yaml
rule_logic:
  id: R001_logic_manufacturing
  definition_id: R001_credit_check  # 关联声明
  applicable_conditions:
    - classification: industry
      value: 制造业
  when: "credit_score >= 60 AND overdue_ratio <= 0.05"
  then:
    action_type: set_flag
    output: { eligible: true, risk_level: LOW }
  priority: 100
---
rule_logic:
  id: R001_logic_retail
  definition_id: R001_credit_check  # 关联声明
  applicable_conditions:
    - classification: industry
      value: 批发零售
  when: "credit_score >= 70 AND overdue_ratio <= 0.03"
  then:
    action_type: set_flag
    output: { eligible: true, risk_level: MEDIUM }
  priority: 100
```

### 5.3 分类和指标的声明 vs 实例

| 层 | 声明 | 实例 |
|---|------|------|
| L2 | 分类方案 (行业/规模/风险) | 实体的分类标签 |
| L3 | 指标定义 (公式/取数逻辑) | 指标计算结果 |
| L4 | 规则声明 (作用对象+IO) | 规则逻辑 (条件+动作) |

## 6. Schema v2 vs v1 对比

| 维度 | v1 | v2 |
|------|-----|-----|
| 结构 | 扁平 | 四层分层 |
| 复用 | 规则绑定 entity_type | 规则声明 + 多实例 |
| 清晰度 | attributes 混杂 | 事实与分析分离 |
| 灵活性 | 改规则需改 Schema | 规则独立演进 |
| 顶层容器 | 无 | 语义空间 |
| 状态管理 | 无 | DRAFT/ACTIVE/ARCHIVED |
| 消费视图 | 无 | 授权机制 |
| 版本管理 | 无 | 分层版本 |

## 7. 演进示例

### v1 写法
```yaml
concepts:
  - name: Supplier
    attributes:
      - name: registered_capital  # 事实
      - name: credit_score        # 分析结果 ❌ 混在一起

rules:
  - id: R001
    scope:
      entity_types: [Supplier]    # 硬编码绑定
```

### v2 写法

```yaml
# 管理空间: supply_chain_space
# 状态: ACTIVE

# L1: 事实 - 声明
fact_objects:
  - name: Company
    properties:
      - name: registered_capital
        type: float
        unit: CNY

# L2: 归类 - 声明
categorizations:
  - name: IndustryCategory
    values: [制造业, 批发零售, 服务业]
  - name: CompanyScale
    values: [大型, 中型, 小微]

# L3: 要素 - 声明
analytical_elements:
  - id: credit_score
    type: derived
    formula: "financial_score * 0.6 + behavior_score * 0.4"

# L4: 逻辑 - 声明
rule_definitions:
  - id: R001_credit_check
    name: 信用检查
    target_objects: [Company]
    input_elements: [credit_score]
    output_elements: [eligible, risk_level]

# L4: 逻辑 - 实例
rule_logics:
  - id: R001_logic_1
    definition_id: R001_credit_check
    applicable_conditions:
      - classification: industry
        value: 制造业
    when: "credit_score >= 60"
    then:
      action_type: set_flag
      output: { eligible: true }

# 实例数据
entity_instances:
  - entity_id: SUP_001
    _concept: Company
    registered_capital: 10000000
    industry_category: 制造业
    scale: 中型
```

## 8. 相关文档

| 文档 | 说明 |
|------|------|
| [语义空间架构](./00b-semantic-space-architecture.md) | 顶层容器设计、状态机、授权模型 |
| [事实对象](./01-fact-objects.md) | L1 详细说明 |
| [归类分析](./02-categorization.md) | L2 详细说明 |
| [分析要素](./03-analytical-elements.md) | L3 详细说明 |
| [业务逻辑](./04-business-logic.md) | L4 详细说明 |
| [声明与实例分离](./07-rule-declaration-and-instance.md) | 规则声明/实例详细说明 |
| [数据集与同步](./06-dataset-and-sync.md) | Dataset 映射和增量同步 |
| [版本管理](./08-version-management.md) | 分层版本策略 |
| [API 架构](../10-api-architecture.md) | 管理面/消费面 API |
| [前端架构](../09-frontend-architecture.md) | 页面路由和组件 |
